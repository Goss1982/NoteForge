from fastapi import HTTPException
from starlette.responses import JSONResponse

from .config import settings


class UploadBodyLimit:
    """Bound multipart data before the framework spools the entire upload."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or scope.get("path") != "/api/notebooks/import":
            return await self.app(scope, receive, send)
        limit = (settings().max_upload_mb + 1) * 1024 * 1024
        headers = dict(scope.get("headers", []))
        try:
            size = int(headers.get(b"content-length", b"0"))
        except ValueError:
            return await JSONResponse({"detail": "Invalid content length"}, status_code=400)(
                scope, receive, send
            )
        if size > limit:
            return await JSONResponse({"detail": "Upload exceeds configured limit"}, status_code=413)(
                scope, receive, send
            )
        total = 0

        async def limited_receive():
            nonlocal total
            message = await receive()
            total += len(message.get("body", b""))
            if total > limit:
                raise HTTPException(413, "Upload exceeds configured limit")
            return message

        return await self.app(scope, limited_receive, send)
