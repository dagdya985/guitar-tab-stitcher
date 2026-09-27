from concurrent.futures import ThreadPoolExecutor
import cv2
import numpy as np
from .cv.io import read_image
from .store import read, write, project_dir
from .video import sampled_frames
from .cv.matching import estimate_motion
from .cv.stitching import compose, infer_direction, recalculate_positions

POOL = ThreadPoolExecutor(max_workers=2)


def update(project_id, **fields):
    project = read(project_id)
    project.update(fields)
    write(project)


def run(project_id):
    try:
        project = read(project_id)
        folder = project_dir(project_id)
        interval = project["sampling_interval"]
        expected = max(1, round(project["duration"] / interval))
        update(project_id, status="processing", stage="正在抽取视频帧", progress=2)

        def extraction_progress(index, total):
            update(project_id, progress=min(26, 2+round(24*index/max(total, 1))))

        raw = sampled_frames(folder / project["video_path"], project["roi"], interval,
                             folder / "frames", extraction_progress)
        if len(raw) < 2:
            raise ValueError("有效抽帧少于两帧。请缩短抽帧间隔或检查视频。")
        update(project_id, stage="正在匹配相邻帧", analyzed_frames=0,
               total_frames=len(raw), progress=28)
        frames = []
        previous = None
        last_accepted = None
        directions = []
        for i, record in enumerate(raw):
            current = read_image(folder / "frames" / record["path"])
            if current is None:
                raise ValueError(f"无法读取第 {i+1} 帧。")
            if i == 0:
                frame = {**record, "dx": 0, "dy": 0, "confidence": 1.0,
                         "matches": 0, "inliers": 0, "overlap": 1.0,
                         "similarity": 1.0, "method": "first", "status": "first"}
                previous, last_accepted = current, frame
            else:
                mode = project.get("scroll_direction", "auto")
                motion = estimate_motion(previous, current, mode)
                # A sudden cut is compared with the last reliable keyframe before rejection.
                if motion.confidence < .38 and last_accepted and last_accepted["id"] != i-1:
                    key = read_image(folder / "frames" / last_accepted["path"])
                    alternative = estimate_motion(key, current, mode)
                    if alternative.confidence > motion.confidence:
                        motion = alternative
                dx, dy = motion.dx, motion.dy
                if motion.confidence < .27:
                    status = "failed"
                    dx = dy = 0
                elif motion.confidence < .57:
                    status = "low"
                else:
                    status = "success"
                frame = {**record, **motion.as_dict(), "dx": dx, "dy": dy, "status": status}
                if status != "failed":
                    last_accepted = frame
                    if abs(dx) + abs(dy) >= 1.5:
                        directions.append((dx, dy))
                previous = current
            frames.append(frame)
            if i % 3 == 0 or i == len(raw)-1:
                update(project_id, analyzed_frames=i+1,
                       progress=min(88, 28+round(60*(i+1)/len(raw))))
        recalculate_positions(frames)
        direction = infer_direction(frames)
        if direction == "none":
            raise ValueError("检测不到持续滚动。请确认 ROI 覆盖谱面，并缩短抽帧间隔。")
        if len(directions) >= 5:
            axis = 0 if direction in ("left", "right") else 1
            signs = [np.sign(v[axis]) for v in directions if abs(v[axis]) >= 2]
            if signs and abs(np.mean(signs)) < .6:
                raise ValueError("滚动方向多次变化，无法生成连续长图。请截取单一滚动段。")
        update(project_id, stage="正在去重并拼接", progress=90,
               frames=frames, detected_direction=direction)
        result = compose(frames, folder / "frames", folder / "result.png", direction)
        update(project_id, stage="完成", status="completed", progress=100, result=result)
    except Exception as exc:
        update(project_id, status="failed", stage="处理失败", error=str(exc))


def submit(project_id):
    POOL.submit(run, project_id)
