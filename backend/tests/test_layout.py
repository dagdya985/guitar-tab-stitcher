from pathlib import Path
from PIL import Image
from pypdf import PdfReader

from app.layout import create_one_page, export_single_pdf


def make_score(path: Path, width=6000):
    from PIL import ImageDraw
    image = Image.new("RGB", (width, 160), "white")
    draw = ImageDraw.Draw(image)
    for y in (30, 45, 60, 75, 90, 105):
        draw.line((0, y, width, y), fill="black", width=1)
    for x in range(50, width, 120):
        draw.line((x, 25, x, 110), fill="black", width=2)
        draw.text((x+15, 69), str(x//120), fill="black")
    image.save(path)


def test_fixed_a4_single_page(tmp_path):
    source = tmp_path / "score.png"
    make_score(source)
    result = create_one_page(source, tmp_path / "page.png", "fixed", "a4", "portrait")
    assert result["rows"] > 1
    assert result["width"] == 1654
    assert result["height"] == 2339
    pdf_path = export_single_pdf(tmp_path / "page.png", tmp_path / "page.pdf")
    assert len(PdfReader(str(pdf_path)).pages) == 1


def test_normal_size_long_page(tmp_path):
    source = tmp_path / "score.png"
    make_score(source, width=22000)
    fixed = create_one_page(source, tmp_path / "fixed.png", "fixed", "a4", "portrait")
    long = create_one_page(source, tmp_path / "long.png", "long", "a4", "portrait")
    assert long["height"] > 2339
    assert long["scale"] > fixed["scale"]
    assert long["rows"] >= fixed["rows"]

