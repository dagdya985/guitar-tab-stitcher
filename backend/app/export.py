from io import BytesIO
from pathlib import Path
from PIL import Image
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4, A3, landscape


def export_image(source: Path, destination: Path, kind: str):
    with Image.open(source) as image:
        image.convert("RGB").save(destination, format="JPEG" if kind == "jpg" else "PNG", quality=95)
    return destination


def _page_break(image, ideal, start, axis):
    """Prefer a low-ink gap around the requested page break."""
    import numpy as np
    limit = image.width if axis == "x" else image.height
    lo, hi = max(start + 1, ideal - 70), min(limit, ideal + 70)
    if hi <= lo:
        return min(ideal, limit)
    if axis == "x":
        sample = image.crop((lo, 0, hi, image.height)).convert("L").resize((hi-lo, min(200, image.height)))
        ink = (np.asarray(sample) < 170).mean(axis=0)
    else:
        sample = image.crop((0, lo, image.width, hi)).convert("L").resize((min(200, image.width), hi-lo))
        ink = (np.asarray(sample) < 170).mean(axis=1)
    return lo + int(np.argmin(ink))


def export_pdf(source: Path, destination: Path, paper="a4", orientation="landscape"):
    page = A3 if paper == "a3" else A4
    if orientation == "landscape":
        page = landscape(page)
    pdf = canvas.Canvas(str(destination), pagesize=page)
    margin = 28
    usable_w, usable_h = page[0]-2*margin, page[1]-2*margin
    with Image.open(source) as image:
        image = image.convert("RGB")
        # Preserve ROI aspect ratio. A horizontal strip is divided along X.
        horizontal = image.width >= image.height
        pixels_per_page = int((usable_w/usable_h)*image.height) if horizontal else int((usable_h/usable_w)*image.width)
        pixels_per_page = max(1, pixels_per_page)
        limit = image.width if horizontal else image.height
        start = 0
        while start < limit:
            end = min(limit, start+pixels_per_page)
            if end < limit:
                end = _page_break(image, end, start, "x" if horizontal else "y")
            end = max(start+1, end)
            segment = image.crop((start, 0, end, image.height) if horizontal else (0, start, image.width, end))
            scale = min(usable_w/segment.width, usable_h/segment.height)
            w, h = segment.width*scale, segment.height*scale
            buffer = BytesIO()
            segment.save(buffer, format="PNG")
            from reportlab.lib.utils import ImageReader
            pdf.drawImage(ImageReader(buffer), margin, page[1]-margin-h, width=w, height=h)
            pdf.showPage()
            start = end
    pdf.save()
    return destination

