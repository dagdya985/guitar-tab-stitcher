import io
import os
import time
from pathlib import Path

import cv2
import numpy as np
import pytest
from fastapi.testclient import TestClient
from pypdf import PdfReader

from app.cv.matching import estimate_motion, overlap_fraction
from app.cv.stitching import compose, recalculate_positions


def tab(width=1400, height=160, seed=4):
    rng = np.random.default_rng(seed)
    image = np.full((height, width, 3), 248, np.uint8)
    for y in [38, 52, 66, 80, 94, 108]:
        cv2.line(image, (0, y), (width-1, y), (58, 58, 58), 1)
    for x in range(35, width, 80):
        cv2.line(image, (x, 30), (x, 116), (45, 45, 45), 2)
        for j in range(2):
            y = int(rng.choice([38, 52, 66, 80, 94, 108]))
            digit = str(rng.integers(0, 10))
            cv2.putText(image, digit, (x+int(rng.integers(13, 65)), y+4),
                        cv2.FONT_HERSHEY_SIMPLEX, .42, (5, 5, 5), 1, cv2.LINE_AA)
        cv2.putText(image, str(x//80), (x+5, 21), cv2.FONT_HERSHEY_SIMPLEX,
                    .45, (15, 15, 15), 1, cv2.LINE_AA)
    return image


@pytest.mark.parametrize("axis,shift", [("x", 40), ("x", -40), ("y", 24), ("y", -24),
                                          ("x", 4), ("x", 130)])
def test_motion(axis, shift):
    sheet = tab(1500, 900)
    if axis == "y":
        # Add distinct horizontal groups for the vertical case.
        for y in range(200, 850, 120):
            cv2.putText(sheet, f"Line {y}", (20, y), cv2.FONT_HERSHEY_SIMPLEX,
                        1, (0, 0, 0), 2)
        a, b = sheet[:500, :500], sheet[shift:shift+500, :500] if shift > 0 else sheet[:500, :500]
        if shift < 0:
            a, b = sheet[-shift:-shift+500, :500], sheet[:500, :500]
    else:
        a = sheet[:, 200:700]
        b = sheet[:, 200+shift:700+shift]
    motion = estimate_motion(a, b)
    target = shift if axis == "x" else abs(shift) if shift > 0 else shift
    # In both cases B starts at the supplied signed offset in A coordinates.
    assert abs((motion.dx if axis == "x" else motion.dy) - target) <= 3, motion
    assert motion.confidence > .25


def test_no_motion_and_80_percent_overlap(tmp_path):
    sheet = tab(600, 160)
    a, b = sheet[:, :300], sheet[:, 60:360]
    still = estimate_motion(a, a)
    assert abs(still.dx) < 2 and abs(still.dy) < 2
    assert overlap_fraction(a.shape, 60, 0) == pytest.approx(.8)
    move = estimate_motion(a, b, "left")
    assert abs(move.dx-60) <= 3
    source = tmp_path / "frames"
    source.mkdir()
    cv2.imwrite(str(source / "a.png"), a)
    cv2.imwrite(str(source / "b.png"), b)
    frames = [{"id": 0, "path": "a.png", "status": "first", "dx": 0, "dy": 0,
               "confidence": 1},
              {"id": 1, "path": "b.png", "status": "success", "dx": 60, "dy": 0,
               "confidence": .9}]
    recalculate_positions(frames)
    result = compose(frames, source, tmp_path / "result.png", "left")
    assert result["width"] == 360
    actual = cv2.imread(str(tmp_path / "result.png"))
    assert np.mean(np.abs(actual.astype(np.int16)-sheet[:, :360].astype(np.int16))) < 2


@pytest.mark.parametrize("fps", [30, 60])
def test_encoded_video_end_to_end(tmp_path, monkeypatch, fps):
    monkeypatch.setenv("GTS_DATA_DIR", str(tmp_path / "data"))
    import app.store as store
    import app.main as main
    store.DATA = tmp_path / "data"
    store.DATA.mkdir(exist_ok=True)
    main.DATA = store.DATA
    sheet = tab(1200, 160)
    video = tmp_path / f"{fps}.mp4"
    writer = cv2.VideoWriter(str(video), cv2.VideoWriter_fourcc(*"mp4v"), fps, (400, 220))
    assert writer.isOpened()
    for i in range(fps * 2):
        frame = np.full((220, 400, 3), 31, np.uint8)
        x = min(600, int(i * 120 / fps))
        frame[30:190] = sheet[:, x:x+400]
        writer.write(frame)
    writer.release()
    client = TestClient(main.app)
    project = client.post("/api/projects").json()
    pid = project["id"]
    with video.open("rb") as file:
        response = client.post(f"/api/video/upload/{pid}", files={"file": (video.name, file, "video/mp4")})
    assert response.status_code == 200, response.text
    assert response.json()["fps"] == pytest.approx(fps)
    assert client.post(f"/api/roi/{pid}", json={"x": 0, "y": 30/220, "w": 1, "h": 160/220}).status_code == 200
    assert client.post(f"/api/stitch/start/{pid}", json={"sampling_interval": .25,
                                                      "scroll_direction": "left"}).status_code == 202
    deadline = time.time()+30
    while time.time() < deadline:
        progress = client.get(f"/api/stitch/progress/{pid}").json()
        if progress["status"] in ("completed", "failed"):
            break
        time.sleep(.1)
    assert progress["status"] == "completed", progress
    result = client.get(f"/api/stitch/result/{pid}").json()
    assert 628 <= result["result"]["width"] <= 640
    assert result["result"]["successful_frames"] >= 4
    assert client.get(f"/api/stitch/image/{pid}").status_code == 200
    layout_response = client.post(f"/api/layout/{pid}", json={"page_mode": "fixed", "paper": "a4", "orientation": "portrait"})
    assert layout_response.status_code == 200, layout_response.text
    layout = layout_response.json()
    assert layout["width"] == 1654 and layout["height"] == 2339
    assert client.get(f"/api/layout/tile/{pid}/0/0").status_code == 200
    pdf = client.post(f"/api/export/{pid}", json={"format": "pdf", "layout": "one_page"})
    assert pdf.status_code == 200
    assert len(PdfReader(io.BytesIO(pdf.content)).pages) == 1
