"""Wrap a stitched horizontal score into a single printable page."""
from pathlib import Path
import math
import numpy as np
from PIL import Image
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader

DPI = 200
PAPER_MM = {"a4": (210, 297), "a3": (297, 420)}


def _staff_scale(image: Image.Image) -> float:
    """Normalize common staff spacing to approximately 18 px at 200 DPI."""
    sample = image.crop((0, 0, min(image.width, 1200), image.height)).convert("L")
    array = np.asarray(sample)
    profile = (array < 125).mean(axis=1)
    peaks = [i for i in range(1, len(profile)-1)
             if profile[i] > .42 and profile[i] >= profile[i-1] and profile[i] >= profile[i+1]]
    gaps = np.diff(peaks)
    gaps = gaps[(gaps >= 5) & (gaps <= 45)]
    if len(gaps) < 3:
        return 1.0
    return float(np.clip(18 / np.median(gaps), .5, 2.0))


def _break_at_barline(image: Image.Image, target: int, start: int, maximum: int) -> int:
    """Prefer a detected barline; otherwise pick a low-ink column near target."""
    lo = max(start+1, target-90)
    hi = min(image.width-1, maximum, target+90)
    if hi <= lo:
        return min(maximum, max(start+1, target))
    gray = np.asarray(image.crop((lo, 0, hi+1, image.height)).convert("L"))
    dark = (gray < 110).sum(axis=0)
    # A vertical barline occupies many rows; break several pixels after it.
    barlines = np.flatnonzero(dark > max(25, image.height * .34))
    if len(barlines):
        nearest = int(barlines[np.argmin(np.abs(barlines + lo - target))]) + lo
        return min(maximum, nearest + 4)
    ink = (gray < 170).mean(axis=0)
    distance = np.abs(np.arange(lo, hi+1)-target) / 90
    return int(np.argmin(ink + distance*.08)) + lo


def _segments(image: Image.Image, available_source_width: int):
    width = image.width
    count = max(1, math.ceil(width / available_source_width))
    starts = [0]
    for row in range(count-1):
        start = starts[-1]
        remaining_rows = count-row
        target = start + round((width-start)/remaining_rows)
        minimum = max(start+1, width-(remaining_rows-1)*available_source_width)
        maximum = min(width-(remaining_rows-1), start+available_source_width)
        cut = _break_at_barline(image, target, start, maximum)
        starts.append(max(minimum, min(maximum, cut)))
    starts.append(width)
    return list(zip(starts[:-1], starts[1:]))


def _choose_fixed_scale(image, usable_w, usable_h, preferred, gap):
    # Row count changes discontinuously, so test the exact wrapped height.
    low, high = .01, preferred*1.35
    for _ in range(40):
        scale = (low+high)/2
        capacity = max(1, math.floor(usable_w/scale))
        rows = math.ceil(image.width/capacity)
        height = rows*max(1, round(image.height*scale))+(rows-1)*gap
        if height <= usable_h:
            low = scale
        else:
            high = scale
    return low


def create_one_page(source: Path, destination: Path, mode="long", paper="a4", orientation="portrait"):
    page_mm = PAPER_MM[paper]
    if orientation == "landscape":
        page_mm = page_mm[::-1]
    paper_w, paper_h = (round(mm*DPI/25.4) for mm in page_mm)
    margin = round(12*DPI/25.4)
    gap = round(6*DPI/25.4)
    usable_w, usable_h = paper_w-2*margin, paper_h-2*margin
    with Image.open(source) as input_image:
        score = input_image.convert("RGB")
        if score.width < score.height:
            raise ValueError("单页换行当前适用于水平滚动谱；垂直滚动请使用原长图导出。")
        preferred = _staff_scale(score)
        scale = preferred if mode == "long" else _choose_fixed_scale(score, usable_w, usable_h, preferred, gap)
        capacity = max(1, math.floor(usable_w/scale))
        pieces = _segments(score, capacity)
        row_h = max(1, round(score.height*scale))
        content_h = 2*margin + len(pieces)*row_h + (len(pieces)-1)*gap
        output_h = max(paper_h, content_h) if mode == "long" else paper_h
        if paper_w*output_h > 220_000_000:
            raise ValueError("单页尺寸超过当前输出上限，请改用分页导出。")
        if mode == "fixed" and content_h > paper_h+2:
            raise ValueError("内容无法排进指定纸张。请选 A3、横向或正常尺寸加长单页。")
        page = Image.new("RGB", (paper_w, output_h), "white")
        y = margin
        for left, right in pieces:
            segment = score.crop((left, 0, right, score.height))
            segment = segment.resize((max(1, round(segment.width*scale)), row_h), Image.Resampling.LANCZOS)
            page.paste(segment, (margin, y))
            y += row_h+gap
        destination.parent.mkdir(parents=True, exist_ok=True)
        page.save(destination, optimize=True)
        tiles = destination.parent / "layout_tiles"
        tiles.mkdir(exist_ok=True)
        for row, top in enumerate(range(0, output_h, 1024)):
            for col, left in enumerate(range(0, paper_w, 1024)):
                page.crop((left, top, min(left+1024, paper_w), min(top+1024, output_h))).save(
                    tiles / f"{col}_{row}.jpg", quality=88, subsampling=0)
        return {"width": paper_w, "height": output_h, "rows": len(pieces),
                "scale": round(scale, 3), "paper_width_mm": round(paper_w*25.4/DPI, 1),
                "paper_height_mm": round(output_h*25.4/DPI, 1),
                "warning": "单张纸内容较密，建议使用加长单页或 A3。" if scale < preferred*.7 else None}


def export_single_pdf(image_path: Path, destination: Path):
    with Image.open(image_path) as page:
        width_pt = page.width*72/DPI
        height_pt = page.height*72/DPI
        pdf = canvas.Canvas(str(destination), pagesize=(width_pt, height_pt))
        pdf.drawImage(ImageReader(page.convert("RGB")), 0, 0, width=width_pt, height=height_pt)
        pdf.showPage()
        pdf.save()
    return destination
