from pathlib import Path
import cv2
from .cv.io import write_image


def probe(path: Path):
    cap = cv2.VideoCapture(str(path))
    try:
        if not cap.isOpened():
            raise ValueError("无法读取视频。请检查文件是否为有效的 MP4、MOV 或 WebM。")
        fps = cap.get(cv2.CAP_PROP_FPS)
        count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        width, height = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)), int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        if not fps or fps <= 0 or not width or not height:
            raise ValueError("视频缺少有效的帧率或分辨率信息。")
        fourcc = int(cap.get(cv2.CAP_PROP_FOURCC))
        codec = "".join(chr((fourcc >> (8*i)) & 255) for i in range(4)).strip("\x00")
        return {"duration": count/fps, "fps": fps, "width": width, "height": height,
                "frame_count": count, "codec": codec}
    finally:
        cap.release()


def frame_at(path: Path, seconds: float):
    cap = cv2.VideoCapture(str(path))
    try:
        cap.set(cv2.CAP_PROP_POS_MSEC, max(0, seconds)*1000)
        ok, frame = cap.read()
        if not ok:
            raise ValueError("无法读取指定时间的视频画面。")
        return frame
    finally:
        cap.release()


def sampled_frames(path: Path, roi, interval: float, output: Path, progress=None):
    """Decode sequentially, keeping only the ROI of selected frames on disk."""
    cap = cv2.VideoCapture(str(path))
    if not cap.isOpened():
        raise ValueError("无法打开视频。")
    fps = cap.get(cv2.CAP_PROP_FPS)
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    step = max(1, round(interval * fps))
    output.mkdir(parents=True, exist_ok=True)
    index, selected = 0, []
    last_selected_index = -1
    def save_crop(frame, source_index):
        h, w = frame.shape[:2]
        x0 = max(0, min(w-1, round(roi["x"]*w)))
        y0 = max(0, min(h-1, round(roi["y"]*h)))
        x1 = max(x0+1, min(w, round((roi["x"]+roi["w"])*w)))
        y1 = max(y0+1, min(h, round((roi["y"]+roi["h"])*h)))
        crop = frame[y0:y1, x0:x1]
        name = f"{len(selected):05d}.png"
        if not write_image(output / name, crop):
            raise RuntimeError("无法保存抽取的视频帧。")
        selected.append({"id": len(selected), "timestamp": source_index/fps, "path": name})
    try:
        while True:
            if index % step == 0:
                ok, frame = cap.read()
                if not ok:
                    break
                save_crop(frame, index)
                last_selected_index = index
            else:
                if not cap.grab():
                    break
            index += 1
            if progress and index % max(step, int(fps)) == 0:
                progress(index, total)
        if total > 1 and last_selected_index < total-1:
            cap.set(cv2.CAP_PROP_POS_FRAMES, total-1)
            ok, frame = cap.read()
            if ok:
                save_crop(frame, total-1)
    finally:
        cap.release()
    return selected
