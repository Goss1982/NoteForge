import hashlib
import os
import tempfile
from pathlib import Path

from .config import settings


def store_original(data: bytes, suffix: str) -> tuple[str, str]:
    digest = hashlib.sha256(data).hexdigest()
    folder = settings().data_dir / "originals" / digest[:2]
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{digest}{suffix}"
    if not path.exists():
        fd, temp = tempfile.mkstemp(dir=folder)
        try:
            with os.fdopen(fd, "wb") as f:
                f.write(data)
                f.flush()
                os.fsync(f.fileno())
            os.chmod(temp, 0o600)
            os.replace(temp, path)
        finally:
            if os.path.exists(temp):
                os.unlink(temp)
    return digest, str(path.resolve())


def safe_path(path: str) -> Path:
    resolved = Path(path).resolve()
    if not resolved.is_relative_to(settings().data_dir.resolve()):
        raise ValueError("File outside data directory")
    return resolved
