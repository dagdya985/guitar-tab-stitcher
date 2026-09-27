from pathlib import Path
import cv2
import numpy as np


def read_image(path: Path):
    try:
        data = np.fromfile(str(path), dtype=np.uint8)
        return cv2.imdecode(data, cv2.IMREAD_COLOR)
    except (OSError, ValueError):
        return None


def write_image(path: Path, image):
    ok, encoded = cv2.imencode(path.suffix or ".png", image)
    if not ok:
        return False
    encoded.tofile(str(path))
    return True

