from pathlib import Path
from PIL import Image
import numpy as np


def infer_direction(frames):
    good = [f for f in frames[1:] if f.get("status") == "success" and
            max(abs(f.get("dx", 0)), abs(f.get("dy", 0))) >= 1.5]
    if not good:
        return "none"
    dx, dy = np.median([f["dx"] for f in good]), np.median([f["dy"] for f in good])
    if abs(dx) >= abs(dy):
        return "left" if dx > 0 else "right"
    return "up" if dy > 0 else "down"


def recalculate_positions(frames):
    x = y = 0.0
    for f in frames:
        if f["id"]:
            x += f.get("dx", 0)
            y += f.get("dy", 0)
        f["x"], f["y"] = round(x), round(y)
    return frames


def compose(frames, source: Path, destination: Path, direction: str):
    chosen = [f for f in frames if f.get("status") in ("success", "low", "first") and
              not f.get("excluded")]
    if not chosen:
        raise ValueError("没有可拼接的帧。请检查 ROI 或重新识别。")
    with Image.open(source / chosen[0]["path"]) as first:
        fw, fh = first.size
    minx = min(f["x"] for f in chosen)
    miny = min(f["y"] for f in chosen)
    maxx = max(f["x"] + fw for f in chosen)
    maxy = max(f["y"] + fh for f in chosen)
    width, height = maxx-minx, maxy-miny
    if width * height > 220_000_000:
        raise ValueError("长图超过当前单图上限。请提高抽帧间隔或缩小 ROI。")
    result = Image.new("RGB", (width, height), "white")
    covered = None
    for f in chosen:
        with Image.open(source / f["path"]) as image:
            image = image.convert("RGB")
            x, y = f["x"]-minx, f["y"]-miny
            if covered is None or direction == "none":
                result.paste(image, (x, y))
            elif direction in ("left", "right"):
                if direction == "left":
                    cut = max(0, covered[2]-x)
                    cut = min(cut + int(f.get("seam_offset", 0)), fw)
                    if cut < fw:
                        result.paste(image.crop((cut, 0, fw, fh)), (x+cut, y))
                else:
                    cut = max(0, x+fw-covered[0])
                    cut = max(0, min(cut - int(f.get("seam_offset", 0)), fw))
                    if cut < fw:
                        result.paste(image.crop((0, 0, fw-cut, fh)), (x, y))
            else:
                if direction == "up":
                    cut = max(0, covered[3]-y)
                    cut = min(cut + int(f.get("seam_offset", 0)), fh)
                    if cut < fh:
                        result.paste(image.crop((0, cut, fw, fh)), (x, y+cut))
                else:
                    cut = max(0, y+fh-covered[1])
                    cut = max(0, min(cut - int(f.get("seam_offset", 0)), fh))
                    if cut < fh:
                        result.paste(image.crop((0, 0, fw, fh-cut)), (x, y))
        box = (x, y, x+fw, y+fh)
        covered = box if covered is None else (min(covered[0], box[0]), min(covered[1], box[1]),
                                                 max(covered[2], box[2]), max(covered[3], box[3]))
    destination.parent.mkdir(parents=True, exist_ok=True)
    result.save(destination, optimize=True)
    tiles = destination.parent / "tiles"
    tiles.mkdir(exist_ok=True)
    for row, top in enumerate(range(0, height, 1024)):
        for col, left in enumerate(range(0, width, 1024)):
            result.crop((left, top, min(left+1024, width), min(top+1024, height))).save(
                tiles / f"{col}_{row}.jpg", quality=88, subsampling=0)
    return {"width": width, "height": height, "output_path": destination.name,
            "frame_count": len(frames), "successful_frames": len(chosen),
            "failed_frames": len(frames)-len(chosen),
            "average_confidence": round(float(np.mean([f.get("confidence", 0) for f in chosen])), 3)}
