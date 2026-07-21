"""pytest에서 자동 로드되는 공통 설정. 여기 정의된 fixture는 다른 테스트에서
import 없이 바로 쓸 수 있다."""

import socket
import sys
from pathlib import Path
from urllib.parse import urlparse

import pytest
import yaml

FACADE_DIR = Path(__file__).resolve().parents[1] / "facade"
if str(FACADE_DIR) not in sys.path:
    sys.path.insert(0, str(FACADE_DIR))


@pytest.fixture(scope="session")
def facade_dir() -> Path:
    return FACADE_DIR


@pytest.fixture(scope="session")
def sample_dir() -> Path:
    return FACADE_DIR.parent / "sample"


@pytest.fixture(scope="session")
def sample_pdf() -> Path:
    path = FACADE_DIR.parent / "sample" / "pdf" / "long(eng)" / "Information Theory.pdf"
    if not path.exists():
        pytest.skip(f"샘플 파일 없음: {path}")
    return path


def _load_port(config_name: str) -> int:
    with open(FACADE_DIR / "resource" / config_name, encoding="utf-8") as f:
        config = yaml.safe_load(f)
    return urlparse(config["url"]).port


def _port_open(host: str, port: int, timeout: float = 1.0) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


@pytest.fixture(scope="session")
def local_services_available() -> bool:
    """resource/detr.yaml, resource/paddle.yaml에 설정된 로컬 파드(NodePort)가 떠 있는지 확인."""
    return _port_open("localhost", _load_port("detr.yaml")) and _port_open("localhost", _load_port("paddle.yaml"))


@pytest.fixture(scope="session")
def document_processor(local_services_available):
    """로컬 통합 테스트용 DocumentProcessor. detr/paddle 파드가 없으면 자동 skip."""
    if not local_services_available:
        pytest.skip("detr/paddle 로컬 파드가 떠 있지 않음 - 로컬 통합 테스트는 파드가 필요함")
    from preprocessor import DocumentProcessor

    return DocumentProcessor()
