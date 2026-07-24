"""RT-DETR 기반 원격 레이아웃 서버(`detr` 레포 서빙)를 호출하는 layout 전략.

`detr` 서버(`detr/app/predictor.py`)는 docling-ibm-models의 ``LayoutPredictor`` 를 그대로
얹은 것뿐이라, 원본 docling이 그 예측 위에 적용하는 후처리
(``docling/utils/layout_postprocessor.py`` 의 ``LayoutPostprocessor``)까지 포팅해야 실제
docling과 같은 품질의 category가 나온다. docling은 자신이 직접 추출한 cell들로 완전한
cluster 트리(children/wrapper 등)를 조립하지만, 우리는 이미 추출된 줄(line) 하나하나에
category만 매기면 되므로, 결과에 실질적으로 영향을 주는 부분만 이식했다:

- ``CONFIDENCE_THRESHOLDS``: 카테고리별 최소 confidence(낮으면 region 자체를 버림).
- ``LABEL_REMAPPING``: title -> section_header.
- 페이지 면적의 90% 이상을 덮는 거짓 picture 감지 제거.
- 겹치는 region 제거(``OVERLAP_PARAMS`` + LIST_ITEM/TEXT, CODE 우선순위 규칙,
  ``_should_prefer_cluster``/``_select_best_cluster_from_group`` 그대로).
- 줄 매칭을 "중심점이 포함된 가장 작은 region"에서 "겹침 비율이 가장 큰 region(최소 0.2)"으로
  교체 - docling의 ``LayoutPostprocessor._assign_cells_to_clusters`` 와 동일한 기준.

건너뛴 부분: cell 재조립에 따른 cluster bbox 조정(우리는 줄 bbox를 이미 신뢰하므로 불필요),
FORM/KEY_VALUE_REGION의 children 계층 구성(우리는 평평한 category 목록만 필요),
rtree 기반 공간 인덱스(region 개수가 페이지당 수십 개 수준이라 O(n^2) 전수비교로 충분).

TABLE만은 예외로, docling과 다른 방식이지만 구조를 복원한다: ``table_structure``가 설정되면
(``config.yaml`` 의 ``table_structure.type: tableformer``) "table" region에 속한 줄들을
tableformer 서버(별도 파드, ``docling_ibm_models.tableformer`` 서빙 - 표 3단계 파이프라인) 로
보내 실제 행/열 구조를 얻고, markdown 표 문자열 하나로 합쳐 반환한다(:meth:`_build_items`).
이때는 카테고리 목록이 아니라 ``PRODUCES_ITEMS`` 아이템 목록을 직접 반환한다.
"""

import base64
import json
import urllib.request
from typing import List, Optional, Tuple

from util.tableformer_client import TableFormer
from util.util import CATEGORIES, png_size

# docling의 LayoutPostprocessor.CONFIDENCE_THRESHOLDS 그대로(카테고리명만 우리 CATEGORIES
# 표기로 변환). 여기 없는 카테고리(GenOS 커스텀 학습 라벨 등)는 _DEFAULT_CONFIDENCE_THRESHOLD.
CONFIDENCE_THRESHOLDS = {
    "caption": 0.5,
    "footnote": 0.5,
    "formula": 0.5,
    "list_item": 0.5,
    "page_footer": 0.5,
    "page_header": 0.5,
    "picture": 0.5,
    "section_header": 0.45,
    "table": 0.5,
    "text": 0.5,
    "title": 0.45,
    "code": 0.45,
    "checkbox_selected": 0.45,
    "checkbox_unselected": 0.45,
    "form": 0.45,
    "key_value_region": 0.45,
    "document_index": 0.45,
}
_DEFAULT_CONFIDENCE_THRESHOLD = 0.5

# docling의 LayoutPostprocessor.LABEL_REMAPPING 그대로.
LABEL_REMAPPING = {"title": "section_header"}

# docling의 WRAPPER_TYPES/SPECIAL_TYPES 그대로 - 겹침 제거 시 이 그룹들을 따로 취급한다.
WRAPPER_CATEGORIES = {"form", "key_value_region", "table", "document_index"}
SPECIAL_CATEGORIES = WRAPPER_CATEGORIES | {"picture"}

# docling의 LayoutPostprocessor.OVERLAP_PARAMS 그대로.
OVERLAP_PARAMS = {
    "regular": {"area_threshold": 1.3, "conf_threshold": 0.05},
    "picture": {"area_threshold": 2.0, "conf_threshold": 0.3},
    "wrapper": {"area_threshold": 2.0, "conf_threshold": 0.2},
}

# docling의 _assign_cells_to_clusters(min_overlap=0.2) 그대로.
_MIN_LINE_OVERLAP = 0.2

_OVERLAP_THRESHOLD = 0.8
_CONTAINMENT_THRESHOLD = 0.8


class DetrLayout:
    """페이지 이미지를 detr 서버 `/detect` 로 보내 감지된 region으로 각 줄의 category를 매긴다.

    Attributes:
        url (str): detr 서버 base URL.
        image_dpi (int): 페이지 이미지를 렌더링한 DPI(줄 bbox와 스케일을 맞추는 데 쓰임).
        timeout (int): HTTP 요청 타임아웃(초).
    """

    NEEDS_IMAGE = True
    """항상 ``True`` — 이 전략은 페이지 이미지가 반드시 필요하다."""

    NEEDS_WORDS = True
    """항상 ``True`` - PDF 원본 단어 단위 bbox를 받을 수 있으면 받는다(``table_structure``가
    켜졌을 때 tableformer cell 매칭에 씀; 못 받으면 줄 단위 근사로 대체한다)."""

    def __init__(self, config: dict = None):
        """
        Args:
            config: ``url``, ``image_dpi``, ``timeout``, (optional) ``table_structure`` 를
                담은 설정 dict(예: ``resource/detr.yaml`` 내용 + ``preprocessor.py`` 가 병합한
                ``table_structure`` 서브 설정).

        Raises:
            ValueError: ``config`` 에 ``url`` 이 없을 때.
        """
        config = config or {}
        self.url = config.get("url")
        if not self.url:
            raise ValueError("layout.type=detr을 쓰려면 detr.yaml에 url을 설정해야 합니다.")
        self.image_dpi = config.get("image_dpi", 150)
        self.timeout = config.get("timeout", 60)
        table_structure_config = config.get("table_structure")
        self.tableformer = TableFormer(table_structure_config) if table_structure_config else None
        # table_structure가 켜지면 "table" region을 여러 줄이 아니라 markdown 표 하나로 합쳐야
        # 해서, 카테고리 목록이 아니라 {"text","category","bbox"} 아이템 목록을 직접 반환한다
        # (dots_mocr_all 등과 같은 계약). 꺼져있으면 기존과 동일하게 카테고리 목록만 반환한다.
        self.PRODUCES_ITEMS = self.tableformer is not None

    def __call__(
        self,
        lines: List[Tuple[str, Tuple[float, float, float, float], float]],
        image: Optional[bytes] = None,
        words: Optional[List[Tuple[str, Tuple[float, float, float, float]]]] = None,
    ) -> List[str]:
        """줄마다 카테고리를 매긴다.

        Args:
            lines: ``(text, bbox, font_size)`` 튜플 목록.
            image: 페이지 이미지(PNG bytes). ``None`` 이면 모든 줄을 ``"text"`` 로 취급한다.
            words: PDF 원본 단어 단위 ``(text, bbox)`` 목록(``NEEDS_WORDS`` 덕에 로더가 낼 수
                있으면 넘겨준다). ``table_structure`` 켜졌을 때 tableformer cell 매칭에 쓰고,
                없으면(``None`` - PDF가 아니거나 이 페이지가 OCR로 대체됨) 줄 단위 근사로
                대체한다(:meth:`_line_to_word_tokens`).

        Returns:
            ``table_structure`` 가 꺼져있으면 ``lines`` 와 같은 길이의 카테고리 문자열 목록.
            켜져있으면(``PRODUCES_ITEMS``) ``{"text","category","bbox"}`` 아이템 목록 -
            "table" region에 속한 줄들은 tableformer가 재구성한 HTML 표 하나로 합쳐진다
            (그만큼 아이템 개수가 ``lines`` 개수보다 적어질 수 있다). 이 모드에서는
            ``reorder_by_category`` 에 의한 다단 레이아웃 읽기순서 보정이 적용되지 않는다
            (``base_loader`` 가 ``PRODUCES_ITEMS`` 전략에는 그 보정을 안 태우므로 - dots_mocr_all
            등과 동일한 제약).
        """
        if not lines:
            return []
        if image is None:
            if self.tableformer:
                return [
                    {
                        "text": text,
                        "category": "text",
                        "bbox": {"x0": bbox[0], "y0": bbox[1], "x1": bbox[2], "y1": bbox[3]},
                    }
                    for text, bbox, _ in lines
                ]
            return ["text"] * len(lines)

        raw_regions = self._detect(image)
        # detr region bbox는 image_dpi 기준 픽셀 좌표라, 줄 bbox(PDF 포인트, 72dpi 기준)와 스케일을 맞춘다.
        scale = self.image_dpi / 72.0
        regions = [
            {
                "category": self._to_category(r["label"]),
                "confidence": r["confidence"],
                "l": r["l"] / scale,
                "t": r["t"] / scale,
                "r": r["r"] / scale,
                "b": r["b"] / scale,
            }
            for r in raw_regions
        ]

        page_size = png_size(image)
        page_area = (page_size[0] / scale) * (page_size[1] / scale) if page_size else None
        regions = self._postprocess(regions, page_area)

        if not self.tableformer:
            return [self._match_category(bbox, regions) for _, bbox, _ in lines]
        return self._build_items(lines, image, regions, scale, words)

    def _build_items(
        self,
        lines: List[Tuple[str, Tuple[float, float, float, float], float]],
        image: bytes,
        regions: List[dict],
        scale: float,
        words: Optional[List[Tuple[str, Tuple[float, float, float, float]]]] = None,
    ) -> List[dict]:
        """table_structure가 켜졌을 때, "table" region에 속한 줄들을 tableformer로 재구성한
        HTML 표 아이템(``<table><tr><td rowspan=.. colspan=..>``, 병합 셀 보존)으로 합치고,
        나머지는 기존과 동일하게 줄 하나당 아이템 하나로 낸다. doc_parser의
        ``chunking_processor.py::_extract_table_text`` 기본값(``export_to_html=1``)과 동등한
        방식 - 같은 tableformer 출력을 렌더링만 다르게 한다."""
        line_regions = [self._match_region(bbox, regions) for _, bbox, _ in lines]

        table_regions = [r for r in regions if r["category"] == "table"]
        structures = []
        if table_regions:
            if words is not None:
                # PDF 원본 단어 bbox 그대로 - doc_parser가 get_cells_in_bbox(WORD)로 하는 것과
                # 동등하게, 문자 수 근사가 아니라 실제 glyph 위치를 쓴다.
                page_tokens = [
                    {"id": i, "text": text, "bbox": [b[0] * scale, b[1] * scale, b[2] * scale, b[3] * scale]}
                    for i, (text, b) in enumerate(words)
                ]
            else:
                # 단어 bbox가 없으면(비-PDF 로더이거나 이 페이지가 OCR로 대체됨) 줄을 공백
                # 기준으로 쪼개 문자 수 비례로 근사한다.
                page_tokens = []
                next_id = 0
                for text, bbox, _ in lines:
                    scaled_bbox = (bbox[0] * scale, bbox[1] * scale, bbox[2] * scale, bbox[3] * scale)
                    word_tokens, next_id = self._line_to_word_tokens(text, scaled_bbox, next_id)
                    page_tokens.extend(word_tokens)
            table_bboxes_px = [(r["l"] * scale, r["t"] * scale, r["r"] * scale, r["b"] * scale) for r in table_regions]
            structures = self.tableformer.structure(image, table_bboxes_px, page_tokens)
        table_html = {id(r): TableFormer.to_html(s) for r, s in zip(table_regions, structures)}

        items = []
        consumed_tables = set()
        for (text, bbox, _), region in zip(lines, line_regions):
            if region is not None and region["category"] == "table":
                key = id(region)
                if key in consumed_tables:
                    continue  # 이 table region은 이미 HTML 표 아이템 하나로 냈다.
                consumed_tables.add(key)
                table_text = table_html.get(key, "").strip()
                items.append(
                    {
                        "text": table_text if table_text else text,
                        "category": "table",
                        "bbox": {"x0": region["l"], "y0": region["t"], "x1": region["r"], "y1": region["b"]},
                    }
                )
                continue
            items.append(
                {
                    "text": text,
                    "category": region["category"] if region else "text",
                    "bbox": {"x0": bbox[0], "y0": bbox[1], "x1": bbox[2], "y1": bbox[3]},
                }
            )
        return items

    @staticmethod
    def _line_to_word_tokens(
        text: str, bbox: Tuple[float, float, float, float], next_id: int
    ) -> Tuple[List[dict], int]:
        """줄 텍스트를 공백 기준 단어로 쪼개, 문자 수에 비례해 가로 위치를 근사 배분한다.

        tableformer의 cell 매칭(``do_matching``)은 원래 PDF 단어 단위 토큰(정확한 개별 bbox)을
        기대하는데, 우리는 줄 전체를 문자열 하나로만 갖고 있어 정확한 단어별 bbox가 없다.
        줄 bbox 폭을 (단어 글자 수 + 단어 사이 공백 1칸씩) 비례로 나눠 근사한다 - 폰트가
        고정폭이 아니면 다소 어긋나지만, 매칭 목적(어느 표 셀에 속하는지)에는 줄 전체를
        토큰 하나로 주는 것보다 훨씬 낫다.

        Args:
            text: 줄 텍스트.
            bbox: 줄의 ``(x0, y0, x1, y1)`` (이미 tableformer가 기대하는 좌표계로 스케일 완료).
            next_id: 다음에 배정할 토큰 id(tableformer 쪽 스키마가 ``int`` 를 요구해 줄을
                넘나드는 전역 카운터로 관리).

        Returns:
            ``(단어 토큰 목록, 다음 next_id)``.
        """
        words = text.split()
        if not words:
            return [], next_id

        x0, y0, x1, y1 = bbox
        total_chars = sum(len(w) for w in words)
        total_units = total_chars + max(0, len(words) - 1)  # 단어 사이 공백도 1칸으로 계산
        unit_width = (x1 - x0) / total_units if total_units > 0 else 0.0

        tokens = []
        cursor = x0
        for word in words:
            word_width = len(word) * unit_width
            tokens.append({"id": next_id, "text": word, "bbox": [cursor, y0, cursor + word_width, y1]})
            next_id += 1
            cursor += word_width + unit_width
        return tokens, next_id

    def _detect(self, image: bytes) -> List[dict]:
        """detr 서버 ``/detect`` 를 호출해 이미지 하나의 감지 region 목록을 받는다.

        Args:
            image: 페이지 이미지(PNG bytes).

        Returns:
            ``{"label", "confidence", "l", "t", "r", "b"}`` 형태의 region 목록.
        """
        payload = json.dumps({"images": [base64.b64encode(image).decode("ascii")]}).encode("utf-8")
        req = urllib.request.Request(
            self.url.rstrip("/") + "/detect",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=self.timeout) as resp:
            result = json.loads(resp.read())
        return result["results"][0]

    @staticmethod
    def _postprocess(regions: List[dict], page_area: Optional[float]) -> List[dict]:
        """docling의 ``LayoutPostprocessor`` 중 카테고리 판정에 영향을 주는 부분만 적용한다.

        순서(docling과 동일): confidence 필터 -> label remap -> 전체 페이지 picture 제거
        -> 그룹별(regular/picture/wrapper) 겹침 제거.
        """
        regions = [
            r
            for r in regions
            if r["confidence"] >= CONFIDENCE_THRESHOLDS.get(r["category"], _DEFAULT_CONFIDENCE_THRESHOLD)
        ]
        for r in regions:
            if r["category"] in LABEL_REMAPPING:
                r["category"] = LABEL_REMAPPING[r["category"]]

        if page_area:
            regions = [
                r
                for r in regions
                if not (r["category"] == "picture" and DetrLayout._area(r) / page_area > 0.90)
            ]

        picture = [r for r in regions if r["category"] == "picture"]
        wrapper = [r for r in regions if r["category"] in WRAPPER_CATEGORIES]
        regular = [r for r in regions if r["category"] not in SPECIAL_CATEGORIES]

        return (
            DetrLayout._remove_overlapping(regular, OVERLAP_PARAMS["regular"])
            + DetrLayout._remove_overlapping(picture, OVERLAP_PARAMS["picture"])
            + DetrLayout._remove_overlapping(wrapper, OVERLAP_PARAMS["wrapper"])
        )

    @staticmethod
    def _remove_overlapping(regions: List[dict], params: dict) -> List[dict]:
        """겹치거나 서로를 포함하는 region을 union-find로 묶어 그룹마다 하나만 남긴다.

        docling의 ``_remove_overlapping_clusters`` 를 그대로 따르되, 공간 인덱스(rtree) 대신
        O(n^2) 전수비교를 쓴다 - 페이지당 region 수가 적어(수십 개 수준) 충분하다.
        """
        if not regions:
            return []

        n = len(regions)
        parent = list(range(n))

        def find(x: int) -> int:
            while parent[x] != x:
                parent[x] = parent[parent[x]]
                x = parent[x]
            return x

        def union(x: int, y: int) -> None:
            rx, ry = find(x), find(y)
            if rx != ry:
                parent[ry] = rx

        for i in range(n):
            for j in range(i + 1, n):
                if DetrLayout._overlaps(regions[i], regions[j]):
                    union(i, j)

        groups: dict = {}
        for i in range(n):
            groups.setdefault(find(i), []).append(i)

        result = []
        for indices in groups.values():
            if len(indices) == 1:
                result.append(regions[indices[0]])
                continue
            result.append(DetrLayout._select_best(indices, regions, params))
        return result

    @staticmethod
    def _overlaps(a: dict, b: dict) -> bool:
        """docling의 ``SpatialClusterIndex.check_overlap`` 그대로: IoU 또는 어느 한쪽이
        상대에 충분히 포함되면 겹친다고 본다."""
        area_a, area_b = DetrLayout._area(a), DetrLayout._area(b)
        if area_a <= 0 or area_b <= 0:
            return False
        inter = DetrLayout._intersection(a, b)
        iou = inter / (area_a + area_b - inter) if (area_a + area_b - inter) > 0 else 0.0
        containment_a = inter / area_a
        containment_b = inter / area_b
        return (
            iou > _OVERLAP_THRESHOLD
            or containment_a > _CONTAINMENT_THRESHOLD
            or containment_b > _CONTAINMENT_THRESHOLD
        )

    @staticmethod
    def _select_best(indices: List[int], regions: List[dict], params: dict) -> dict:
        """docling의 ``_select_best_cluster_from_group`` 그대로: 겹치는 region 그룹에서
        규칙에 따라 하나만 고른다."""
        group = [regions[i] for i in indices]
        best = None
        for candidate in group:
            should_select = True
            for other in group:
                if other is candidate:
                    continue
                if not DetrLayout._should_prefer(candidate, other, params):
                    should_select = False
                    break
            if should_select:
                if best is None:
                    best = candidate
                elif (
                    DetrLayout._area(candidate) > DetrLayout._area(best)
                    and best["confidence"] - candidate["confidence"] <= params["conf_threshold"]
                ):
                    best = candidate
        return best if best is not None else group[0]

    @staticmethod
    def _should_prefer(candidate: dict, other: dict, params: dict) -> bool:
        """docling의 ``_should_prefer_cluster`` 그대로: candidate를 other보다 우선할지 결정한다."""
        if candidate["category"] == "list_item" and other["category"] == "text":
            area_ratio = DetrLayout._area(candidate) / DetrLayout._area(other)
            if abs(1 - area_ratio) < 0.2:
                return True

        if candidate["category"] == "code":
            containment = DetrLayout._intersection(other, candidate) / DetrLayout._area(other)
            if containment > 0.8:
                return True

        area_ratio = DetrLayout._area(candidate) / DetrLayout._area(other)
        conf_diff = other["confidence"] - candidate["confidence"]
        if area_ratio <= params["area_threshold"] and conf_diff > params["conf_threshold"]:
            return False
        return True

    @staticmethod
    def _match_region(bbox: Tuple[float, float, float, float], regions: List[dict]) -> Optional[dict]:
        """줄의 bbox와 겹침 비율(줄 면적 기준)이 가장 큰 region을 고른다.

        docling의 ``_assign_cells_to_clusters`` 와 동일하게, 중심점 포함이 아니라 겹침
        비율(``intersection_over_self``, 최소 0.2)로 판단한다 - 줄이 region 경계에 걸쳐 있어도
        더 많이 겹치는 쪽으로 매칭된다.

        Args:
            bbox: 줄의 ``(x0, y0, x1, y1)``.
            regions: 스케일/후처리 완료된 region 목록.

        Returns:
            매칭되는 region이 없으면 ``None``.
        """
        line_area = (bbox[2] - bbox[0]) * (bbox[3] - bbox[1])
        if line_area <= 0:
            return None

        best_overlap = _MIN_LINE_OVERLAP
        best_region = None
        for r in regions:
            inter = DetrLayout._intersection_with_bbox(bbox, r)
            overlap_ratio = inter / line_area
            if overlap_ratio > best_overlap:
                best_overlap = overlap_ratio
                best_region = r

        return best_region

    @staticmethod
    def _match_category(bbox: Tuple[float, float, float, float], regions: List[dict]) -> str:
        """:meth:`_match_region` 의 카테고리만 뽑는다(매칭 안 되면 ``"text"``)."""
        region = DetrLayout._match_region(bbox, regions)
        return region["category"] if region else "text"

    @staticmethod
    def _area(region: dict) -> float:
        return max(0.0, region["r"] - region["l"]) * max(0.0, region["b"] - region["t"])

    @staticmethod
    def _intersection(a: dict, b: dict) -> float:
        l = max(a["l"], b["l"])
        t = max(a["t"], b["t"])
        r = min(a["r"], b["r"])
        btm = min(a["b"], b["b"])
        if r <= l or btm <= t:
            return 0.0
        return (r - l) * (btm - t)

    @staticmethod
    def _intersection_with_bbox(bbox: Tuple[float, float, float, float], region: dict) -> float:
        x0, y0, x1, y1 = bbox
        l = max(x0, region["l"])
        t = max(y0, region["t"])
        r = min(x1, region["r"])
        b = min(y1, region["b"])
        if r <= l or b <= t:
            return 0.0
        return (r - l) * (b - t)

    @staticmethod
    def _to_category(label: str) -> str:
        """detr region label을 :data:`util.util.CATEGORIES` 값으로 정규화한다.

        Args:
            label: detr이 반환한 원본 label 문자열(예: ``"Section Header"``).

        Returns:
            ``CATEGORIES`` 에 속하는 정규화된 카테고리, 없으면 ``"text"``.
        """
        key = label.lower().replace(" ", "_").replace("-", "_")
        return key if key in CATEGORIES else "text"
