"""Create a small, deterministic scrolling guitar-tab MP4 for local smoke tests."""
from pathlib import Path
import subprocess
import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "samples"
OUT.mkdir(exist_ok=True)

rng = np.random.default_rng(42)
sheet = np.full((180, 1700, 3), 241, np.uint8)
for y in (42, 59, 76, 93, 110, 127):
    cv2.line(sheet, (0, y), (1699, y), (66, 75, 69), 1)
for bar, x in enumerate(range(30, 1680, 110)):
    cv2.line(sheet, (x, 36), (x, 133), (46, 57, 50), 2)
    cv2.putText(sheet, f"{bar+1}", (x+5, 25), cv2.FONT_HERSHEY_SIMPLEX, .48, (51, 58, 53), 1, cv2.LINE_AA)
    for _ in range(3):
        px = x + int(rng.integers(20, 100))
        py = int(rng.choice((42, 59, 76, 93, 110, 127)))
        cv2.rectangle(sheet, (px-3, py-8), (px+13, py+7), (241, 241, 241), -1)
        cv2.putText(sheet, str(rng.integers(0, 10)), (px, py+5),
                    cv2.FONT_HERSHEY_SIMPLEX, .43, (15, 22, 17), 1, cv2.LINE_AA)

cv2.imencode(".png", sheet)[1].tofile(str(OUT / "demo_source.png"))
fps, seconds = 30, 8
raw_video = OUT / "demo_scroll_raw.mp4"
writer = cv2.VideoWriter(str(raw_video), cv2.VideoWriter_fourcc(*"mp4v"), fps, (640, 360))
if not writer.isOpened():
    raise RuntimeError("MP4 编码器不可用")
for frame_number in range(fps*seconds):
    frame = np.full((360, 640, 3), (27, 35, 31), np.uint8)
    cv2.putText(frame, "Guitar Lesson / Demo", (38, 70), cv2.FONT_HERSHEY_SIMPLEX, .8,
                (150, 169, 152), 1, cv2.LINE_AA)
    offset = round(frame_number * 980/(fps*seconds-1))
    frame[145:325] = sheet[:, offset:offset+640]
    writer.write(frame)
writer.release()
subprocess.run(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-i", str(raw_video),
                "-c:v", "libx264", "-preset", "fast", "-crf", "20", "-pix_fmt", "yuv420p",
                str(OUT / "demo_scroll.mp4")], check=True)
raw_video.unlink()
print(OUT / "demo_scroll.mp4")
