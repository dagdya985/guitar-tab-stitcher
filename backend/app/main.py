from datetime import datetime, timezone
from contextlib import asynccontextmanager
from pathlib import Path
from uuid import uuid4
import os
import cv2
from fastapi import FastAPI, UploadFile, File, HTTPException, Body
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.responses import Response
from pydantic import BaseModel, Field, model_validator
from .store import DATA, read, write, project_dir
from .video import probe, frame_at
from .cv.detection import detect_tab_roi
from .cv.matching import estimate_motion
from .cv.io import read_image
from .cv.stitching import compose, recalculate_positions
from .processing import submit
from .export import export_image, export_pdf
from .layout import create_one_page, export_single_pdf

@asynccontextmanager
async def lifespan(_app):
    recover_interrupted_jobs()
    yield


app = FastAPI(title="Guitar Tab Stitcher API", version="1.0", lifespan=lifespan)
allowed_origins = ["http://localhost:5173", "http://127.0.0.1:5173"]
allowed_origins += [origin.strip().rstrip("/") for origin in
                    os.environ.get("GTS_ALLOWED_ORIGINS", "").split(",") if origin.strip()]
app.add_middleware(CORSMiddleware, allow_origins=allowed_origins,
                   allow_credentials=True, allow_methods=["*"], allow_headers=["*"])


def recover_interrupted_jobs():
    for path in DATA.glob("*/project.json"):
        try:
            project = read(path.parent.name)
            if project["status"] == "processing":
                project.update(status="failed", stage="任务中断",
                               error="后端服务重启导致任务中断。请重新识别。")
                write(project)
        except (OSError, ValueError, KeyError):
            continue


class ROI(BaseModel):
    x: float = Field(ge=0, lt=1)
    y: float = Field(ge=0, lt=1)
    w: float = Field(gt=0, le=1)
    h: float = Field(gt=0, le=1)

    @model_validator(mode="after")
    def bounds(self):
        if self.x + self.w > 1.001 or self.y + self.h > 1.001:
            raise ValueError("ROI 必须位于视频画面内。")
        return self


class StitchOptions(BaseModel):
    sampling_interval: float = Field(default=.5, ge=.05, le=10)
    scroll_direction: str = Field(default="auto", pattern="^(auto|left|right|up|down)$")


class Adjustment(BaseModel):
    frame_id: int = Field(ge=0)
    dx: float | None = None
    dy: float | None = None
    excluded: bool | None = None
    seam_offset: int | None = Field(default=None, ge=-200, le=200)


class ExportOptions(BaseModel):
    format: str = Field(pattern="^(png|jpg|pdf)$")
    paper: str = Field(default="a4", pattern="^(a4|a3)$")
    orientation: str = Field(default="portrait", pattern="^(landscape|portrait)$")
    layout: str = Field(default="one_page", pattern="^(one_page|strip)$")
    page_mode: str = Field(default="fixed", pattern="^(fixed|long)$")


class LayoutOptions(BaseModel):
    paper: str = Field(default="a4", pattern="^(a4|a3)$")
    orientation: str = Field(default="portrait", pattern="^(landscape|portrait)$")
    page_mode: str = Field(default="fixed", pattern="^(fixed|long)$")


def get_project(project_id):
    try:
        return read(project_id)
    except FileNotFoundError:
        raise HTTPException(404, "项目不存在。")


def require_complete(project):
    if project["status"] != "completed":
        raise HTTPException(409, "请先完成视频识别。")


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.post("/api/projects", status_code=201)
def create_project():
    project_id = uuid4().hex
    (DATA / project_id).mkdir(parents=True)
    project = {"id": project_id, "filename": "", "duration": 0, "fps": 0,
               "width": 0, "height": 0, "codec": "", "roi": None,
               "sampling_interval": .5, "scroll_direction": "auto",
               "detected_direction": None, "status": "created", "stage": "等待上传",
               "progress": 0, "created_at": datetime.now(timezone.utc).isoformat(),
               "frames": [], "result": None, "layout_result": None, "error": None}
    write(project)
    return project


@app.get("/api/projects/{project_id}")
def project_detail(project_id: str):
    return get_project(project_id)


@app.post("/api/video/upload/{project_id}")
async def upload_video(project_id: str, file: UploadFile = File(...)):
    project = get_project(project_id)
    if project["status"] == "processing":
        raise HTTPException(409, "当前项目正在处理。")
    ext = Path(file.filename or "").suffix.lower()
    if ext not in (".mp4", ".mov", ".webm"):
        raise HTTPException(415, "仅支持 MP4、MOV 和 WebM。")
    folder = project_dir(project_id)
    target = folder / f"input{ext}"
    size = 0
    max_upload_bytes = int(os.environ.get("GTS_MAX_UPLOAD_MB", "2048")) * 1024**2
    try:
        with target.open("wb") as out:
            while chunk := await file.read(1024*1024):
                size += len(chunk)
                if size > max_upload_bytes:
                    raise HTTPException(413, f"视频超过 {max_upload_bytes // 1024**2} MB 上限。")
                out.write(chunk)
        if not size:
            raise HTTPException(422, "上传文件为空。")
        metadata = probe(target)
    except Exception as exc:
        target.unlink(missing_ok=True)
        if isinstance(exc, HTTPException):
            raise
        raise HTTPException(422, str(exc))
    project.update(metadata)
    project.update(filename=Path(file.filename).name, video_path=target.name,
                   roi=None, status="uploaded", stage="选择谱面区域", progress=0,
                   frames=[], result=None, layout_result=None, error=None)
    write(project)
    return project


@app.get("/api/video/{project_id}")
def video_file(project_id: str):
    project = get_project(project_id)
    if "video_path" not in project:
        raise HTTPException(404, "尚未上传视频。")
    media = {".mp4": "video/mp4", ".mov": "video/quicktime", ".webm": "video/webm"}
    suffix = Path(project["video_path"]).suffix
    return FileResponse(project_dir(project_id) / project["video_path"],
                        media_type=media.get(suffix, "application/octet-stream"),
                        content_disposition_type="inline")


@app.post("/api/video/analyze/{project_id}")
def analyze_video(project_id: str):
    project = get_project(project_id)
    if "video_path" not in project:
        raise HTTPException(409, "请先上传视频。")
    roi = detect_tab_roi(frame_at(project_dir(project_id) / project["video_path"],
                                  min(1.0, project["duration"]*.1)))
    if roi is None:
        raise HTTPException(422, "未找到稳定的谱线。请在视频上手动框选吉他谱区域。")
    return {"roi": roi, "method": "parallel-staff-lines"}


@app.post("/api/roi/{project_id}")
def set_roi(project_id: str, roi: ROI):
    project = get_project(project_id)
    if project["status"] == "processing":
        raise HTTPException(409, "处理期间不能更改 ROI。")
    if "video_path" not in project:
        raise HTTPException(409, "请先上传视频。")
    project["roi"] = roi.model_dump()
    project["status"] = "ready"
    project["stage"] = "可以开始识别"
    write(project)
    return project


@app.post("/api/stitch/start/{project_id}", status_code=202)
def start_stitch(project_id: str, options: StitchOptions):
    project = get_project(project_id)
    if project["status"] == "processing":
        raise HTTPException(409, "任务已在运行。")
    if not project["roi"]:
        raise HTTPException(409, "请先选择吉他谱区域。")
    project.update(options.model_dump())
    project.update(status="processing", stage="正在解析视频", progress=1,
                   analyzed_frames=0, total_frames=0, layout_result=None, error=None)
    write(project)
    submit(project_id)
    return {"task_id": project_id, "status": "processing"}


@app.get("/api/stitch/progress/{project_id}")
def progress(project_id: str):
    p = get_project(project_id)
    return {k: p.get(k) for k in ("id", "status", "stage", "progress", "analyzed_frames",
                                   "total_frames", "error")}


@app.get("/api/stitch/result/{project_id}")
def stitch_result(project_id: str):
    p = get_project(project_id)
    require_complete(p)
    return {"result": p["result"], "frames": p["frames"],
            "detected_direction": p["detected_direction"]}


@app.get("/api/stitch/image/{project_id}")
def result_image(project_id: str):
    p = get_project(project_id)
    require_complete(p)
    return FileResponse(project_dir(project_id) / "result.png", media_type="image/png")


@app.get("/api/stitch/frame/{project_id}/{frame_id}")
def frame_image(project_id: str, frame_id: int):
    p = get_project(project_id)
    if frame_id < 0 or frame_id >= len(p["frames"]):
        raise HTTPException(404, "帧不存在。")
    return FileResponse(project_dir(project_id) / "frames" / p["frames"][frame_id]["path"],
                        media_type="image/png")


@app.get("/api/stitch/tile/{project_id}/{col}/{row}")
def result_tile(project_id: str, col: int, row: int):
    p = get_project(project_id)
    require_complete(p)
    if col < 0 or row < 0 or col*1024 >= p["result"]["width"] or row*1024 >= p["result"]["height"]:
        raise HTTPException(404, "图块不存在。")
    return FileResponse(project_dir(project_id) / "tiles" / f"{col}_{row}.jpg",
                        media_type="image/jpeg")


@app.post("/api/layout/{project_id}")
def build_one_page(project_id: str, options: LayoutOptions):
    p = get_project(project_id)
    require_complete(p)
    folder = project_dir(project_id)
    try:
        result = create_one_page(folder / "result.png", folder / "layout.png",
                                 options.page_mode, options.paper, options.orientation)
    except ValueError as exc:
        raise HTTPException(422, str(exc))
    p["layout_result"] = result
    p["layout_options"] = options.model_dump()
    write(p)
    return result


@app.get("/api/layout/image/{project_id}")
def one_page_image(project_id: str):
    p = get_project(project_id)
    require_complete(p)
    if not p.get("layout_result"):
        raise HTTPException(409, "请先生成单页排版。")
    return FileResponse(project_dir(project_id) / "layout.png", media_type="image/png")


@app.get("/api/layout/tile/{project_id}/{col}/{row}")
def one_page_tile(project_id: str, col: int, row: int):
    p = get_project(project_id)
    require_complete(p)
    layout = p.get("layout_result")
    if not layout:
        raise HTTPException(409, "请先生成单页排版。")
    if col < 0 or row < 0 or col*1024 >= layout["width"] or row*1024 >= layout["height"]:
        raise HTTPException(404, "图块不存在。")
    return FileResponse(project_dir(project_id) / "layout_tiles" / f"{col}_{row}.jpg",
                        media_type="image/jpeg")


@app.get("/api/stitch/debug/{project_id}/{frame_id}/{mode}")
def debug_image(project_id: str, frame_id: int, mode: str):
    p = get_project(project_id)
    require_complete(p)
    if frame_id < 1 or frame_id >= len(p["frames"]) or mode not in ("features", "overlap"):
        raise HTTPException(404, "调试画面不存在。")
    folder = project_dir(project_id) / "frames"
    a = read_image(folder / p["frames"][frame_id-1]["path"])
    b = read_image(folder / p["frames"][frame_id]["path"])
    if mode == "features":
        orb = cv2.ORB_create(nfeatures=700)
        ka, da = orb.detectAndCompute(a, None)
        kb, db = orb.detectAndCompute(b, None)
        if da is not None and db is not None and len(da) >= 2 and len(db) >= 2:
            pairs = cv2.BFMatcher(cv2.NORM_HAMMING).knnMatch(da, db, k=2)
            good = [m for m, n in pairs if m.distance < .78*n.distance][:60]
            image = cv2.drawMatches(a, ka, b, kb, good, None,
                                    flags=cv2.DrawMatchesFlags_NOT_DRAW_SINGLE_POINTS)
        else:
            image = cv2.hconcat([a, b])
    else:
        frame = p["frames"][frame_id]
        dx, dy = round(frame["dx"]), round(frame["dy"])
        h, w = a.shape[:2]
        image = cv2.hconcat([a.copy(), b.copy()])
        cv2.rectangle(image, (max(0, dx), max(0, dy)),
                      (min(w, w+dx)-1, min(h, h+dy)-1), (66, 203, 171), 2)
        cv2.putText(image, f"dx {dx}  dy {dy}  overlap {frame['overlap']:.0%}",
                    (12, 25), cv2.FONT_HERSHEY_SIMPLEX, .6, (40, 210, 160), 2)
    ok, encoded = cv2.imencode(".jpg", image)
    if not ok:
        raise HTTPException(500, "调试图像生成失败。")
    return Response(encoded.tobytes(), media_type="image/jpeg")


@app.post("/api/stitch/manual-adjust/{project_id}")
def manual_adjust(project_id: str, adjustment: Adjustment):
    p = get_project(project_id)
    require_complete(p)
    frames = p["frames"]
    if adjustment.frame_id >= len(frames):
        raise HTTPException(404, "帧不存在。")
    f = frames[adjustment.frame_id]
    for key in ("dx", "dy", "excluded", "seam_offset"):
        value = getattr(adjustment, key)
        if value is not None:
            f[key] = value
    recalculate_positions(frames)
    try:
        result = compose(frames, project_dir(project_id) / "frames",
                         project_dir(project_id) / "result.png", p["detected_direction"])
    except ValueError as exc:
        raise HTTPException(422, str(exc))
    p.update(frames=frames, result=result, layout_result=None)
    write(p)
    return {"result": result, "frame": f}


@app.post("/api/stitch/retry/{project_id}/{frame_id}")
def retry_match(project_id: str, frame_id: int):
    p = get_project(project_id)
    require_complete(p)
    if frame_id < 1 or frame_id >= len(p["frames"]):
        raise HTTPException(404, "无法重新匹配该帧。")
    folder = project_dir(project_id) / "frames"
    previous = read_image(folder / p["frames"][frame_id-1]["path"])
    current = read_image(folder / p["frames"][frame_id]["path"])
    motion = estimate_motion(previous, current, p["scroll_direction"], force_fallback=True)
    f = p["frames"][frame_id]
    f.update(motion.as_dict())
    f["status"] = "success" if motion.confidence >= .57 else ("low" if motion.confidence >= .27 else "failed")
    recalculate_positions(p["frames"])
    p["result"] = compose(p["frames"], folder, project_dir(project_id) / "result.png",
                          p["detected_direction"])
    p["layout_result"] = None
    write(p)
    return {"frame": f, "result": p["result"]}


@app.post("/api/export/{project_id}")
def export(project_id: str, options: ExportOptions):
    p = get_project(project_id)
    require_complete(p)
    folder = project_dir(project_id)
    source = folder / "result.png"
    destination = folder / f"guitar-tab.{options.format}"
    try:
        if options.layout == "one_page":
            settings = {"paper": options.paper, "orientation": options.orientation,
                        "page_mode": options.page_mode}
            if p.get("layout_result") is None or p.get("layout_options") != settings:
                p["layout_result"] = create_one_page(source, folder / "layout.png",
                                                      options.page_mode, options.paper, options.orientation)
                p["layout_options"] = settings
                write(p)
            source = folder / "layout.png"
        if options.format == "pdf" and options.layout == "one_page":
            export_single_pdf(source, destination)
        elif options.format == "pdf":
            export_pdf(source, destination, options.paper, options.orientation)
        else:
            export_image(source, destination, options.format)
    except ValueError as exc:
        raise HTTPException(422, str(exc))
    except Exception as exc:
        raise HTTPException(500, f"导出失败：{exc}")
    return FileResponse(destination, filename=destination.name)
