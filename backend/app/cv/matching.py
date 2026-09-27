from dataclasses import dataclass, asdict
import cv2
import numpy as np
from .preprocessing import prepare, edge_image


@dataclass
class Motion:
    dx: float = 0.0
    dy: float = 0.0
    matches: int = 0
    inliers: int = 0
    overlap: float = 0.0
    similarity: float = 0.0
    confidence: float = 0.0
    method: str = "none"

    def as_dict(self):
        return asdict(self)


def overlap_fraction(shape, dx, dy):
    h, w = shape[:2]
    return max(0.0, 1 - abs(dx) / w) * max(0.0, 1 - abs(dy) / h)


def similarity(a, b, dx, dy):
    """Correlation over the actual shared pixels; dx/dy place B in A coordinates."""
    h, w = a.shape[:2]
    dx, dy = int(round(dx)), int(round(dy))
    ax0, ay0 = max(0, dx), max(0, dy)
    bx0, by0 = max(0, -dx), max(0, -dy)
    ww, hh = w - abs(dx), h - abs(dy)
    if ww < w * .18 or hh < h * .35:
        return 0.0
    aa = a[ay0:ay0+hh, ax0:ax0+ww].astype(np.float32)
    bb = b[by0:by0+hh, bx0:bx0+ww].astype(np.float32)
    # Gradients suppress static backgrounds and colour changes.
    aa = edge_image(aa)
    bb = edge_image(bb)
    aa -= aa.mean()
    bb -= bb.mean()
    denom = np.linalg.norm(aa) * np.linalg.norm(bb)
    return float(np.clip(np.sum(aa * bb) / denom, 0, 1)) if denom > 1e-5 else 0.0


def _orb(a, b):
    orb = cv2.ORB_create(nfeatures=1600, fastThreshold=8, edgeThreshold=12)
    ka, da = orb.detectAndCompute(a, None)
    kb, db = orb.detectAndCompute(b, None)
    if da is None or db is None or len(ka) < 8 or len(kb) < 8:
        return None
    pairs = cv2.BFMatcher(cv2.NORM_HAMMING).knnMatch(db, da, k=2)
    good = [m for m, n in pairs if m.distance < .78 * n.distance]
    if len(good) < 7:
        return None
    src = np.float32([kb[m.queryIdx].pt for m in good])
    dst = np.float32([ka[m.trainIdx].pt for m in good])
    matrix, mask = cv2.estimateAffinePartial2D(src, dst, method=cv2.RANSAC,
                                                ransacReprojThreshold=3.0)
    if matrix is None or mask is None:
        return None
    scale = np.hypot(matrix[0, 0], matrix[1, 0])
    if not .94 <= scale <= 1.06:
        return None
    dx, dy = float(matrix[0, 2]), float(matrix[1, 2])
    inliers = int(mask.sum())
    if inliers < 6 or overlap_fraction(a.shape, dx, dy) < .16:
        return None
    return Motion(dx=dx, dy=dy, matches=len(good), inliers=inliers, method="ORB/RANSAC")


def _profile_candidates(a, b, axis):
    h, w = a.shape
    max_dim = 720
    scale = min(1.0, max_dim / max(h, w))
    if scale < 1:
        size = (max(1, round(w * scale)), max(1, round(h * scale)))
        a, b = cv2.resize(a, size), cv2.resize(b, size)
    ea, eb = edge_image(a), edge_image(b)
    pa = ea.mean(axis=0 if axis == "y" else 1)
    pb = eb.mean(axis=0 if axis == "y" else 1)
    n = len(pa)
    max_shift = int(n * .72)
    scores = []
    for d in range(-max_shift, max_shift + 1):
        if d >= 0:
            u, v = pa[d:], pb[:n-d]
        else:
            u, v = pa[:n+d], pb[-d:]
        if len(u) < n * .22:
            continue
        u, v = u - u.mean(), v - v.mean()
        den = np.linalg.norm(u) * np.linalg.norm(v)
        score = float(np.dot(u, v) / den) if den > 1e-4 else 0
        scores.append((score, d))
    scores.sort(reverse=True)
    chosen = []
    for _, d in scores:
        if all(abs(d - old) > 3 for old in chosen):
            chosen.append(d)
        if len(chosen) == 6:
            break
    return [d / scale for d in chosen]


def _fallback(a, b, axis):
    candidates = _profile_candidates(a, b, axis)
    if not candidates:
        return Motion()
    best = Motion()
    for raw in candidates:
        for d in range(round(raw)-3, round(raw)+4):
            dx, dy = (d, 0) if axis == "x" else (0, d)
            sim = similarity(a, b, dx, dy)
            overlap = overlap_fraction(a.shape, dx, dy)
            score = sim * (.65 + .35 * overlap)
            if score > best.similarity * (.65 + .35 * best.overlap):
                best = Motion(dx=dx, dy=dy, overlap=overlap, similarity=sim,
                              method="profile/NCC")
    best.confidence = float(np.clip(best.similarity * min(1, best.overlap / .4), 0, 1))
    return best


def estimate_motion(previous, current, direction="auto", force_fallback=False):
    """Returns where current ROI starts in previous ROI's coordinate system."""
    a, b = prepare(previous), prepare(current)
    orb = None if force_fallback else _orb(a, b)
    if orb:
        orb.overlap = overlap_fraction(a.shape, orb.dx, orb.dy)
        orb.similarity = similarity(a, b, orb.dx, orb.dy)
        ratio = orb.inliers / max(orb.matches, 1)
        orb.confidence = float(np.clip(.48 * ratio + .34 * orb.similarity +
                                       .18 * min(orb.inliers / 35, 1), 0, 1))
    axes = ["x", "y"] if direction == "auto" else (["x"] if direction in ("left", "right") else ["y"])
    fallbacks = [_fallback(a, b, axis) for axis in axes]
    fallback = max(fallbacks, key=lambda m: m.confidence)
    if orb and orb.confidence >= .52:
        return orb
    if orb and orb.confidence > fallback.confidence:
        return orb
    return fallback

