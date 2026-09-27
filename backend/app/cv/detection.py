import cv2
import numpy as np


def detect_tab_roi(frame):
    """Find a dense group of roughly equally spaced horizontal staff lines."""
    h, w = frame.shape[:2]
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    edges = cv2.Canny(gray, 50, 150)
    lines = cv2.HoughLinesP(edges, 1, np.pi / 180, threshold=max(35, w // 8),
                            minLineLength=max(50, w // 3), maxLineGap=25)
    if lines is None:
        return None
    rows = []
    for line in lines.reshape(-1, 4):
        x1, y1, x2, y2 = line
        if abs(y2-y1) <= 2 and abs(x2-x1) >= w * .3:
            rows.append((y1+y2)/2)
    unique = []
    for y in sorted(rows):
        if not unique or y - unique[-1] > 3:
            unique.append(y)
    best = None
    for i in range(len(unique)):
        for count in (6, 5):
            group = unique[i:i+count]
            if len(group) != count:
                continue
            gaps = np.diff(group)
            if 5 <= np.median(gaps) <= 45 and np.std(gaps) / np.mean(gaps) < .22:
                score = count + group[-1]/h * .2
                if best is None or score > best[0]:
                    best = (score, group)
    if best is None:
        return None
    group = best[1]
    margin = max(18, int(np.median(np.diff(group)) * 3))
    top, bottom = max(0, int(group[0])-margin), min(h, int(group[-1])+margin)
    return {"x": 0.0, "y": top/h, "w": 1.0, "h": (bottom-top)/h}
