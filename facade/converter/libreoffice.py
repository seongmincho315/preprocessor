"""LibreOffice(soffice)로 다른 포맷을 PDF로 변환한 뒤 pymupdf pdf 로더로 읽는 컨버터.
전용 로더가 없는 확장자(ppt/pptx 등)에 대해 ``preprocessor.py`` 가 대체(fallback)로 쓴다.

rhwp.py와 달리 soffice는 ``--outdir`` 에 원본 파일명을 딴 이름으로 pdf를 쓰기 때문에,
동시/반복 변환이 서로 덮어쓰지 않도록 매 변환마다 새 임시 디렉터리를 만들고, 다 읽고
나면(finally) 지운다. 격리된 ``UserInstallation`` 프로필도 동시 변환 시 soffice 프로필
잠금 충돌을 피하기 위한 것이다.
"""

import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import List

from loader.pdf.pymupdf import Loader as PdfLoader

LIBREOFFICE_TIMEOUT_SEC = 600


def soffice_binary() -> Path:
    """soffice 바이너리 경로. ``SOFFICE_BIN`` 환경변수로 override 가능(로컬 dev 시
    다른 위치 설치). 빈/공백 값은 unset으로 취급해 기본 경로를 쓴다."""
    env = os.environ.get("SOFFICE_BIN", "").strip()
    return Path(env) if env else Path("/usr/bin/soffice")


def soffice_available() -> bool:
    """soffice 바이너리가 존재하고 실행 권한이 있는지 확인한다."""
    binary = soffice_binary()
    return binary.is_file() and os.access(binary, os.X_OK)


class Loader(PdfLoader):
    """soffice로 ppt/pptx 등을 PDF로 변환한 뒤, pymupdf 로더로 페이지를 읽는다."""

    def _extract_pages(self, file_path: str) -> List[list]:
        """파일을 soffice로 PDF 변환한 뒤, 부모(``PdfLoader``)의 pymupdf 추출 로직으로
        페이지를 낸다.

        Args:
            file_path: 변환할 원본 파일 경로(ppt/pptx 등).

        Yields:
            :meth:`loader.pdf.pymupdf.Loader._extract_pages` 와 동일한 ``(lines, image)`` 튜플.

        Raises:
            RuntimeError: soffice 바이너리가 없거나 변환에 실패했을 때.
        """
        pdf_path, tmp_dir = self._convert_to_pdf(file_path)
        try:
            yield from super()._extract_pages(pdf_path)
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)

    @staticmethod
    def _convert_to_pdf(file_path: str):
        """``soffice --headless --convert-to pdf``로 변환해 ``(pdf_path, tmp_dir)`` 를 반환한다."""
        binary = soffice_binary()
        if not soffice_available():
            raise RuntimeError(
                f"soffice(LibreOffice) 바이너리를 찾을 수 없습니다: {binary} "
                "(SOFFICE_BIN 환경변수로 경로를 지정하거나 이미지에 LibreOffice를 설치하세요.)"
            )

        in_path = Path(file_path).resolve()
        tmp_dir = Path(tempfile.mkdtemp(prefix="libreoffice_convert_"))

        env = os.environ.copy()
        env.setdefault("LANG", "C.UTF-8")
        env.setdefault("LC_ALL", "C.UTF-8")

        cmd = [
            str(binary),
            "--headless",
            "--norestore",
            f"-env:UserInstallation=file://{tmp_dir / 'profile'}",
            "--convert-to",
            "pdf",
            "--outdir",
            str(tmp_dir),
            str(in_path),
        ]
        try:
            proc = subprocess.run(cmd, env=env, capture_output=True, text=True, timeout=LIBREOFFICE_TIMEOUT_SEC)
        except subprocess.TimeoutExpired as e:
            shutil.rmtree(tmp_dir, ignore_errors=True)
            raise RuntimeError(f"LibreOffice 변환이 {e.timeout}초를 넘겨 중단됐습니다: {file_path}") from e

        produced = list(tmp_dir.glob("*.pdf"))
        if proc.returncode != 0 or not produced:
            shutil.rmtree(tmp_dir, ignore_errors=True)
            raise RuntimeError(f"LibreOffice 변환 실패(rc={proc.returncode}): {file_path}\n{proc.stderr[:500]}")
        return str(produced[0]), tmp_dir
