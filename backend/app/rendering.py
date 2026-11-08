import io
import json
import re
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path, PurePosixPath

import cairosvg
import fitz
from PIL import Image

from .config import settings


class UnsupportedFormat(ValueError):
    pass


def validate_upload(data: bytes, suffix: str):
    if suffix == ".pdf":
        with fitz.open(stream=data, filetype="pdf") as doc:
            if doc.needs_pass or not 1 <= len(doc) <= settings().max_pages:
                raise ValueError("PDF is encrypted, empty or exceeds the page limit")
    elif suffix in (".png", ".jpg", ".jpeg"):
        with Image.open(io.BytesIO(data)) as image:
            if (
                image.format not in ("PNG", "JPEG")
                or image.width * image.height > settings().max_image_pixels
            ):
                raise ValueError("Invalid or oversized image")
            image.verify()
    elif suffix in (".rmdoc", ".zip"):
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            validate_archive(archive)
    else:
        raise ValueError("Supported formats: PDF, PNG, JPEG and reMarkable RMDOC")


def validate_archive(archive):
    entries = archive.infolist()
    if len(entries) > 5000 or sum(e.file_size for e in entries) > 250_000_000:
        raise ValueError("Archive exceeds safe extraction limits")
    for e in entries:
        p = PurePosixPath(e.filename)
        if p.is_absolute() or ".." in p.parts or "\\" in e.filename or e.flag_bits & 1:
            raise ValueError("Unsafe archive entry")
        if e.compress_size and e.file_size / e.compress_size > 1000:
            raise ValueError("Suspicious archive compression ratio")


def _archive_pdf(source: Path, output: Path) -> str:
    """Render v6 strokes in .content order and overlay them onto base PDF pages.

    Preserve archive bytes separately. Reject ambiguous ordering and unsupported
    versions instead of silently OCRing an unannotated base PDF.
    """
    with tempfile.TemporaryDirectory() as folder, zipfile.ZipFile(source) as archive:
        validate_archive(archive)
        root = Path(folder)
        archive.extractall(root)
        contents = list(root.rglob("*.content"))
        if len(contents) != 1:
            raise UnsupportedFormat("Expected one .content file in reMarkable archive")
        meta = json.loads(contents[0].read_text())
        ids = meta.get("pages")
        cpages = meta.get("cPages", {}).get("pages", [])
        if cpages:
            # cPages is a CRDT list: physical JSON array order is not page order.
            # Match rmapi's idx.value ordering and deleted-marker semantics.
            live = [p for p in cpages if p.get("deleted") is None]
            keys = [p.get("idx", {}).get("value") for p in live]
            if any(not isinstance(key, str) for key in keys) or len(set(keys)) != len(keys):
                raise UnsupportedFormat("Unknown CRDT page ordering; import an exported PDF")
            ids = [p["id"] for p in sorted(live, key=lambda p: p["idx"]["value"])]
        if not ids:
            raise UnsupportedFormat("Unsupported page ordering; import a PDF exported by reMarkable")
        if len(set(ids)) != len(ids):
            raise UnsupportedFormat("Duplicate page identifiers in archive")
        if len(ids) > settings().max_pages:
            raise ValueError("Notebook exceeds page limit")
        base_files = list(root.rglob("*.pdf"))
        if len(base_files) > 1:
            raise UnsupportedFormat("Multiple base PDFs are unsupported")
        base = fitz.open(base_files[0]) if base_files else None
        result = fitz.open()
        try:
            redir = meta.get("redirectionPageMap")
            cpage_by_id = {p["id"]: p for p in cpages}
            for index, page_id in enumerate(ids):
                if not isinstance(page_id, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,100}", page_id):
                    raise ValueError("Invalid page ID")
                base_index = redir[index] if redir and index < len(redir) else index
                info = cpage_by_id.get(page_id, {})
                if info:
                    base_index = info.get("redir", {}).get("value", -1)
                if base and 0 <= base_index < len(base):
                    result.insert_pdf(base, from_page=base_index, to_page=base_index)
                    page = result[-1]
                else:
                    page = result.new_page(width=1404, height=1872)
                strokes = list(root.rglob(f"{page_id}.rm"))
                if len(strokes) > 1:
                    raise UnsupportedFormat("Ambiguous stroke files")
                if strokes:
                    header = strokes[0].read_bytes()[:43]
                    if b"version=6" not in header:
                        raise UnsupportedFormat("Only v6 strokes supported; export this notebook as PDF")
                    rendered = root / "stroke.pdf"
                    svg = root / "stroke.svg"
                    try:
                        subprocess.run(
                            [str(Path(sys.executable).with_name("rmc")), str(strokes[0]), "-o", str(svg)],
                            check=True,
                            capture_output=True,
                            timeout=90,
                        )
                        cairosvg.svg2pdf(url=str(svg), write_to=str(rendered))
                    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
                        raise UnsupportedFormat("Stroke rendering failed; import an exported PDF") from exc
                    with fitz.open(rendered) as overlay:
                        if len(overlay) != 1:
                            raise UnsupportedFormat("Unexpected stroke page count")
                        if overlay[0].get_contents():
                            page.show_pdf_page(page.rect, overlay, 0)
                elif not base or not 0 <= base_index < len(base):
                    # Blank notebook page; original archive remains authoritative.
                    pass
            result.save(output)
        finally:
            result.close()
            if base:
                base.close()
    return "Community renderer: check source preview against your tablet; templates and text-box layout may differ."


def render_pages(source: Path, revision_id: str) -> tuple[list[Path], str | None]:
    folder = settings().data_dir / "pages" / revision_id
    folder.mkdir(parents=True, exist_ok=True)
    warning = None
    suffix = source.suffix.lower()
    if suffix in (".png", ".jpg", ".jpeg"):
        with Image.open(source) as image:
            if image.width * image.height > settings().max_image_pixels:
                raise ValueError("Image exceeds pixel limit")
            image = image.convert("RGB")
            image.thumbnail((1800, 2400))
            path = folder / "1.png"
            image.save(path)
        return [path.resolve()], warning
    if suffix in (".rmdoc", ".zip"):
        output = folder / "rendered.pdf"
        warning = _archive_pdf(source, output)
        source = output
    paths = []
    with fitz.open(source) as pdf:
        if pdf.needs_pass or not 1 <= len(pdf) <= settings().max_pages:
            raise ValueError("Invalid, encrypted or oversized PDF")
        for i, page in enumerate(pdf):
            if page.rect.width <= 0 or page.rect.height <= 0:
                raise ValueError("Invalid page dimensions")
            scale = min(1800 / page.rect.width, 2400 / page.rect.height, 2)
            path = folder / f"{i + 1}.png"
            page.get_pixmap(matrix=fitz.Matrix(scale, scale), alpha=False).save(path)
            paths.append(path.resolve())
    return paths, warning
