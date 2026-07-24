from pathlib import Path

import fitz
import pytest

from converter.rhwp import Loader, rhwp_available, rhwp_binary

pytestmark = pytest.mark.unit


def test_rhwp_binary_defaults_when_env_unset(monkeypatch):
    monkeypatch.delenv("RHWP_BIN", raising=False)
    assert rhwp_binary() == Path("/usr/local/bin/rhwp")


def test_rhwp_binary_blank_env_falls_back_to_default(monkeypatch):
    monkeypatch.setenv("RHWP_BIN", "   ")
    assert rhwp_binary() == Path("/usr/local/bin/rhwp")


def test_rhwp_binary_respects_env_override(monkeypatch, tmp_path):
    fake = tmp_path / "rhwp"
    fake.write_text("#!/bin/sh\nexit 0\n")
    fake.chmod(0o755)
    monkeypatch.setenv("RHWP_BIN", str(fake))

    assert rhwp_binary() == fake
    assert rhwp_available() is True


def test_missing_binary_raises_runtime_error(monkeypatch, tmp_path):
    monkeypatch.setenv("RHWP_BIN", str(tmp_path / "no-such-rhwp"))

    with pytest.raises(RuntimeError, match="rhwp 바이너리를 찾을 수 없습니다"):
        Loader._convert_to_pdf(str(tmp_path / "sample.hwpx"))


def test_conversion_failure_raises_runtime_error(monkeypatch, tmp_path):
    # 실행은 되지만 출력 pdf를 만들지 않는 rhwp - rc!=0 이나 out_path 미생성을 실패로 처리해야 한다.
    fake = tmp_path / "rhwp"
    fake.write_text("#!/bin/sh\nexit 1\n")
    fake.chmod(0o755)
    monkeypatch.setenv("RHWP_BIN", str(fake))

    hwpx_path = tmp_path / "broken.hwpx"
    hwpx_path.write_bytes(b"not a real hwpx")

    with pytest.raises(RuntimeError, match="rhwp 변환 실패"):
        Loader._convert_to_pdf(str(hwpx_path))


@pytest.fixture
def sample_pdf(tmp_path):
    path = tmp_path / "converted_by_rhwp.pdf"
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), "hello rhwp")
    doc.save(str(path))
    doc.close()
    return path


@pytest.fixture
def fake_rhwp(tmp_path, sample_pdf, monkeypatch):
    # 실제 rhwp 바이너리 대신, `export-pdf <in> -o <out>` 호출을 받아 준비된 샘플 pdf를
    # out 경로로 복사하는 스텁. subprocess 인자 순서(cmd[4] == -o 다음 값)만 맞으면 된다.
    script = tmp_path / "rhwp"
    script.write_text(f'#!/bin/sh\ncp "{sample_pdf}" "$4"\n')
    script.chmod(0o755)
    monkeypatch.setenv("RHWP_BIN", str(script))
    return script


def test_extract_pages_converts_via_rhwp_then_reads_with_pymupdf(fake_rhwp, tmp_path):
    hwpx_path = tmp_path / "sample.hwpx"
    hwpx_path.write_bytes(b"fake hwpx content")

    loader = Loader()
    pages = list(loader._extract_pages(str(hwpx_path)))

    assert len(pages) == 1
    lines, image, words = pages[0]
    assert image is None
    assert words is None
    assert lines[0][0] == "hello rhwp"


def test_extract_pages_writes_pdf_next_to_input(fake_rhwp, tmp_path):
    hwpx_path = tmp_path / "sample.hwpx"
    hwpx_path.write_bytes(b"fake hwpx content")

    list(Loader()._extract_pages(str(hwpx_path)))

    assert hwpx_path.with_suffix(".pdf").exists()
