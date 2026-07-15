"""rhwp 바이너리로 HWP/HWPX를 PDF로 변환한 뒤 pymupdf pdf 로더로 읽는 컨버터.

이미지 빌드 시 Rust로 빌드된 ``genonai/genos-rhwp`` 의 ``rhwp`` 바이너리를 컨테이너
안에서 subprocess로 호출한다 (외부 서비스/네트워크 의존 없음). ``ext.hwpx: rhwp`` 로
선택하면 ``loader.hwpx.rhwp`` 모듈이 없어 ``preprocessor.py`` 가 대체(fallback)로
이 모듈을 쓴다.
"""

import os
import subprocess
from pathlib import Path
from typing import List

from loader.pdf.pymupdf import Loader as PdfLoader

RHWP_TIMEOUT_SEC = 600


def rhwp_binary() -> Path:
    """rhwp 바이너리 경로. ``RHWP_BIN`` 환경변수로 override 가능(로컬 dev 시 다른 위치 빌드).

    기본값은 이미지 빌드 시 rhwp_builder stage(cargo build)가 설치하는 경로다.
    빈/공백 값은 unset으로 취급해 기본 경로를 쓴다.
    """
    env = os.environ.get("RHWP_BIN", "").strip()
    return Path(env) if env else Path("/usr/local/bin/rhwp")


def rhwp_available() -> bool:
    """rhwp 바이너리가 존재하고 실행 권한이 있는지 확인한다."""
    binary = rhwp_binary()
    return binary.is_file() and os.access(binary, os.X_OK)


class Loader(PdfLoader):
    """rhwp(``export-pdf``)로 HWP/HWPX를 PDF로 변환한 뒤, pymupdf 로더로 페이지를 읽는다.

    ``PdfLoader`` 를 상속해 변환된 PDF를 읽는 부분(``_extract_pages``/``_extract_lines``)을
    그대로 재사용하고, 이 클래스는 rhwp 변환 단계만 앞에 추가한다.
    """

    def _extract_pages(self, file_path: str) -> List[list]:
        """파일을 rhwp로 PDF 변환한 뒤, 부모(``PdfLoader``)의 pymupdf 추출 로직으로 페이지를 낸다.

        Args:
            file_path: 변환할 원본 파일 경로(hwp/hwpx).

        Yields:
            :meth:`loader.pdf.pymupdf.Loader._extract_pages` 와 동일한 ``(lines, image)`` 튜플.

        Raises:
            RuntimeError: rhwp 바이너리가 없거나 변환에 실패했을 때.
        """
        pdf_path = self._convert_to_pdf(file_path)
        yield from super()._extract_pages(pdf_path)

    @staticmethod
    def _convert_to_pdf(file_path: str) -> str:
        """rhwp CLI(``rhwp export-pdf <input> -o <output.pdf>``)로 변환해 PDF 경로를 반환한다."""
        binary = rhwp_binary()
        if not rhwp_available():
            raise RuntimeError(
                f"rhwp 바이너리를 찾을 수 없습니다: {binary} "
                "(RHWP_BIN 환경변수로 경로를 지정하거나 이미지에 rhwp를 설치하세요.)"
            )

        in_path = Path(file_path).resolve()
        out_path = in_path.with_suffix(".pdf")

        env = os.environ.copy()
        env.setdefault("LANG", "C.UTF-8")
        env.setdefault("LC_ALL", "C.UTF-8")

        cmd = [str(binary), "export-pdf", str(in_path), "-o", str(out_path)]
        try:
            proc = subprocess.run(cmd, env=env, capture_output=True, text=True, timeout=RHWP_TIMEOUT_SEC)
        except subprocess.TimeoutExpired as e:
            raise RuntimeError(f"rhwp 변환이 {e.timeout}초를 넘겨 중단됐습니다: {file_path}") from e

        if proc.returncode != 0 or not out_path.exists() or out_path.stat().st_size == 0:
            raise RuntimeError(f"rhwp 변환 실패(rc={proc.returncode}): {file_path}\n{proc.stderr[:500]}")
        return str(out_path)
