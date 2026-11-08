import json
import os
import re
import subprocess
import tempfile
from pathlib import Path

from .config import settings


class RemarkableClient:
    """Read-only cloud integration through maintained ddvk/rmapi.

    Never invokes upload, delete or move. Device registration is an explicit
    interactive server-side CLI step; tokens stay in a private mounted volume.
    """

    def _run(self, args: list[str], cwd: str | None = None) -> str:
        cfg = settings()
        if not cfg.rmapi_config.is_file():
            raise RuntimeError("reMarkable is not paired. Run the documented rmapi pairing command first.")
        env = {**os.environ, "RMAPI_CONFIG": str(cfg.rmapi_config.resolve())}
        try:
            result = subprocess.run(
                [cfg.rmapi_binary, "-ni", *args],
                cwd=cwd,
                env=env,
                capture_output=True,
                text=True,
                timeout=180,
            )
        except subprocess.TimeoutExpired as exc:
            raise RuntimeError("reMarkable cloud request timed out") from exc
        if result.returncode:
            # CLI errors may contain tokens. Never return raw stdout/stderr.
            raise RuntimeError(
                "reMarkable cloud request failed. Check pairing and rmapi compatibility on the server."
            )
        return result.stdout

    def list_documents(self) -> list[dict]:
        output = self._run(["-json", "find", "/"])
        nodes = json.loads(output)
        if not isinstance(nodes, list):
            raise ValueError("Unexpected rmapi JSON response")
        return [n for n in nodes if n.get("type") == "DocumentType"]

    def download(self, document_id: str) -> bytes:
        if not re.fullmatch(r"[0-9a-fA-F-]{36}", document_id):
            raise ValueError("Invalid reMarkable document ID")
        with tempfile.TemporaryDirectory() as folder:
            self._run(["get", "--id", document_id], cwd=folder)
            files = list(Path(folder).glob("*.rmdoc"))
            if len(files) != 1:
                raise RuntimeError("reMarkable download returned an unexpected file")
            if files[0].stat().st_size > settings().max_upload_mb * 1024 * 1024:
                raise ValueError("Cloud notebook exceeds upload limit")
            return files[0].read_bytes()
