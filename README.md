# Guitar Tab Stitcher

把教学视频中的滚动吉他谱配准、去重并拼成连续长图的本地 Web 应用。核心是视频帧图像配准与重叠区域拼接，**不依赖 OCR 识别谱符**。

## 当前功能

- MP4 / MOV / WebM 上传、视频元信息读取、播放器和逐帧查看
- 手动框选 ROI；也可尝试用平行谱线自动检测
- 后端按时间间隔顺序解码，只把裁剪后的 ROI 帧写入磁盘；始终补取末帧
- ORB 特征 + Lowe ratio + RANSAC 估计位移，纹理不足时用投影轮廓和重叠区相关性补位
- 从多帧中位位移判断左右上下滚动方向；标记低置信度与匹配失败帧
- 仅追加新出现的画面，生成 PNG 长图和 1024 px 图块预览
- 时间轴、特征匹配画面、图层拖动对齐、位移微调、边界偏移、排除帧、重新匹配
- 单页排版：将水平长谱换成多行，默认缩放排进一张 A4；可选 A3 或正常字号的加长单页
- PNG / JPG / 单页 PDF 导出；原始长图模式仍支持分页 PDF
- 后台线程处理和真实进度轮询；上传、ROI、识别、导出均返回明确错误

## MVP 技术方案

前端采用 React 19、TypeScript、Vite 和原生 Canvas/Video API。后端采用 FastAPI、OpenCV、NumPy、Pillow 和 ReportLab。匹配与拼接在服务端执行，浏览器只读取视频和按需预览图块，避免把大量完整帧留在浏览器内存里。任务状态和项目元数据以 JSON 保存在磁盘；开发版使用进程内 `ThreadPoolExecutor`，以后可换为 Celery/Redis。

### 项目结构

```text
frontend/
  src/
    components/             上传、视频、分析、图块查看、拖动对齐、参数、时间轴
    App.tsx                 页面状态与任务轮询
    api.ts                  API 客户端
    types.ts                前端数据类型
    style.css               响应式样式
backend/
  app/
    main.py                 REST API 与校验
    processing.py           后台处理流程
    video.py                视频探测与顺序抽帧
    export.py               图片和分页 PDF
    layout.py               单页换行与纸张尺寸控制
    store.py                项目持久化
    cv/
      detection.py          自动 ROI
      preprocessing.py      灰度、去噪和 CLAHE
      matching.py           ORB/RANSAC、轮廓匹配和置信度
      stitching.py          方向判断、去重、长图及图块
      io.py                 Windows 中文路径安全图片读写
  scripts/generate_demo.py  可复现演示视频
  tests/test_pipeline.py    核心算法与完整 MP4 流程测试
samples/                    H.264 演示视频及其原始谱面
```

## Windows 安装与启动

需要 Python 3.12、Node.js 20+、npm。FFmpeg 用于生成演示视频和视频转码；后端读取视频使用 OpenCV 自带的解码能力。若没有 FFmpeg，可运行 `winget install --id Gyan.FFmpeg -e`，然后在新终端运行 `ffmpeg -version` 检查。

在 **PowerShell** 中，进入项目根目录后运行：

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r backend\requirements.txt
cd frontend
npm install
cd ..
```

终端 1，启动后端：

```powershell
cd backend
..\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

终端 2，启动前端：

```powershell
cd frontend
npm run dev
```

打开 [http://127.0.0.1:5173/](http://127.0.0.1:5173/)。API 文档在 [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)。前端开发服务器把 `/api` 代理到后端。

### 快速试用

仓库中的 `samples/demo_scroll.mp4` 是可在浏览器播放的 H.264 测试视频。上传后可点“自动检测谱面”，再点“开始识别”。该演示视频的预期长图宽度约 1620 px。要重新生成样本：

```powershell
.\.venv\Scripts\python.exe backend\scripts\generate_demo.py
```

真实视频建议先选一段滚动方向稳定、谱面不被字幕遮盖的片段。自动 ROI 失败时手动框选。滚动较快时将抽帧间隔调至 0.1–0.3 秒；若画面几乎不动，可调至 0.5–1 秒。识别完成后在右侧“排版与导出”选择“合为一页”，默认 A4 纵向，点击“生成单页预览”，再导出 PDF、PNG 或 JPG。若固定纸张中的谱面太小，改选 A3 或“正常谱面大小，加长单页”。

## API

JSON 接口以 `/api` 为前缀。错误响应使用 FastAPI 的 `{"detail":"..."}` 格式，常见状态码：`404` 不存在、`409` 状态冲突、`413` 上传过大、`415` 格式不支持、`422` 内容或参数无效、`500` 导出失败。

| 方法与路径 | 请求 | 响应 |
| --- | --- | --- |
| `POST /projects` | 空 | `Project`，201 |
| `GET /projects/{id}` | 无 | `Project` |
| `POST /video/upload/{id}` | multipart `file` | 含时长、FPS、尺寸、编码的 `Project` |
| `GET /video/{id}` | 无 | 视频流，支持 Range |
| `POST /video/analyze/{id}` | 空 | `{roi, method}`；找不到谱线时 422 |
| `POST /roi/{id}` | `{x,y,w,h}`，均为 0–1 相对坐标 | `Project` |
| `POST /stitch/start/{id}` | `{sampling_interval, scroll_direction}` | `{task_id,status}`，202 |
| `GET /stitch/progress/{id}` | 无 | `{status,stage,progress,analyzed_frames,total_frames,error}` |
| `GET /stitch/result/{id}` | 无 | `{result,frames,detected_direction}` |
| `GET /stitch/image/{id}` | 无 | 完整 PNG |
| `GET /stitch/tile/{id}/{col}/{row}` | 无 | 1024 px JPEG 图块 |
| `GET /stitch/frame/{id}/{frame_id}` | 无 | ROI 帧 PNG |
| `GET /stitch/debug/{id}/{frame_id}/{mode}` | `mode=features|overlap` | 调试 JPG |
| `POST /layout/{id}` | `{page_mode:"fixed"|"long",paper:"a4"|"a3",orientation:"portrait"|"landscape"}` | 单页尺寸、行数、缩放与提示 |
| `GET /layout/image/{id}` | 无 | 单页 PNG |
| `GET /layout/tile/{id}/{col}/{row}` | 无 | 单页预览图块 |
| `POST /stitch/manual-adjust/{id}` | `{frame_id,dx?,dy?,excluded?,seam_offset?}` | 新 `result` 和 `frame` |
| `POST /stitch/retry/{id}/{frame_id}` | 空 | 使用后备算法重新匹配 |
| `POST /export/{id}` | `{format:"png"|"jpg"|"pdf",layout:"one_page"|"strip",page_mode:"fixed"|"long",paper:"a4"|"a3",orientation:"portrait"|"landscape"}` | 附件下载；默认 A4 单页 |

项目数据包含 `id`、文件名、视频元信息、ROI、抽帧间隔、滚动方向、任务状态和创建时间。每帧记录时间、位移、匹配数、RANSAC 内点数、重叠率、相似度、置信度、位置及人工调整。结果记录尺寸、成功/失败帧数与平均置信度。

## 算法简述

1. 视频顺序解码，按帧率换算抽帧步长，只保存 ROI；最后一帧单独补取。
2. ROI 灰度化、轻度去噪并用 CLAHE 增强局部对比度。
3. ORB 描述子经 BFMatcher、Lowe ratio 和 RANSAC 估算当前帧在上一帧坐标系中的位置。估计不可靠时，对边缘投影做一维候选搜索，再以真实重叠像素的归一化相关性评分。
4. 多帧中位位移决定主要滚动方向。置信度由内点比例、实际重叠相关性、内点数量和重叠面积组成；低置信度帧在时间轴标黄。
5. 根据累计位移把各 ROI 放到统一坐标系，沿主滚动方向仅粘贴新露出的条带。生成 PNG 后预切图块供浏览器查看。

## 验证

```powershell
cd backend
..\.venv\Scripts\python.exe -m pytest -q
```

测试覆盖左/右/上/下、慢速/快速/静止、80% 重叠只追加 20%、30/60 FPS 编码 MP4 的上传至 PDF 导出流程，以及 A4 单页和正常尺寸加长单页。当前 11 项测试通过。用演示视频在浏览器中跑通后，得到 1620 × 187 px 长图；与原始谱面对应区域比较，平均像素绝对差约 4.16，深色谱线像素一致率约 99.79%。实际上传的 2 分 32 秒教学视频生成 13626 × 234 px 长图，并排为 A4 单页 8 行；导出的 PDF 为 1 页。不同视频仍需人工检查谱符是否被遮挡或发生跳页。

## 环境变量与数据

`GTS_DATA_DIR` 可指定项目文件、ROI 帧、长图和图块的保存目录；默认 `backend/data`。Windows PowerShell 示例：

```powershell
$env:GTS_DATA_DIR = "D:\GuitarTabData"
```

默认只监听 `127.0.0.1`，适合本机使用。上传限制为 2 GB。任务在后台线程执行；后端重启会把未完成任务标为失败，随后可重新识别。

## 公网部署

公开仓库：[dagdya985/guitar-tab-stitcher](https://github.com/dagdya985/guitar-tab-stitcher)。前端地址：[guitar-tab-stitcher-dagdya985.pages.dev](https://guitar-tab-stitcher-dagdya985.pages.dev/)。前端部署到 Cloudflare Pages；OpenCV/FastAPI 后端使用 Render Web Service，配置见 `render.yaml`。Pages 只负责静态网页，无法直接运行本项目的 Python 视频处理服务。

1. 在 Render 中以此仓库创建 Blueprint（`render.yaml`），或创建 Docker Web Service，根目录为仓库根目录，Dockerfile 为 `backend/Dockerfile`，上下文为 `backend/`。健康检查路径为 `/api/health`。
2. 确认 Render 后端的实际公网地址。构建前端时在 `frontend/` 目录设置 `VITE_API_ORIGIN` 为这个 HTTPS 地址（不带末尾 `/`），运行 `npm ci`、`npm run build`。
3. 在仓库根目录运行 `npx wrangler pages deploy frontend/dist --project-name guitar-tab-stitcher-dagdya985`。Pages 项目配置在 `wrangler.jsonc`。如使用 Cloudflare 的 Git 构建，构建命令为 `cd frontend && npm ci && npm run build`，输出目录为 `frontend/dist`，并在 Pages 环境变量中设置相同的 `VITE_API_ORIGIN`。
4. 在 Render 将 `GTS_ALLOWED_ORIGINS` 设置为 Pages 的正式地址，多个地址用逗号分隔。前端开发代理无需配置该变量。

Render 免费实例在无流量时会休眠，重启或重新部署会丢失其本地文件，因而上传视频、项目记录与识别结果都只适合临时使用；请及时下载导出结果。线上部署通过 `GTS_MAX_UPLOAD_MB=100` 把上传限制设为 100 MB；本地仍为 2 GB。长视频可能超出免费实例的内存或处理能力。

## 常见问题与边界

- **视频能上传但不能播放**：浏览器不一定支持文件内部的视频编码。用 FFmpeg 转为 H.264：`ffmpeg -i input.mov -c:v libx264 -pix_fmt yuv420p output.mp4`。
- **自动 ROI 找不到谱面**：谱线可能太淡、遮挡或不是标准平行线。手动框选最可靠。
- **长图重复或断裂**：缩小 ROI 去掉动态字幕，缩短抽帧间隔，查看时间轴中的低置信度帧并拖动图层对齐。
- **谱面不滚动、突然跳页或中途改方向**：当前版本需要单一连续滚动片段；建议先裁出独立片段再处理。
- **特别长的结果**：浏览器预览使用图块；后端单张 PNG 合成目前设有 2.2 亿像素上限，超过上限需分段处理。
- **A4 单页谱面太小**：固定纸张必须按内容量缩放。选择 A3，或“正常谱面大小，加长单页”。
- **换行位置**：单页排版优先在小节线附近换行；谱面模糊时可能切在别处，请检查预览。
- **原长图 PDF 分页**：目前寻找低墨量切口，不能保证每次都准确落在小节线。

## 后续路线

当前版本完成了可运行的核心链路和常用人工修复。下一阶段计划加入按滚动速度自适应抽帧、跨更多关键帧的全局校准、图层替换与局部裁剪、专门的小节线分页，以及 Celery/Redis 和超长图的磁盘流式合成。对复杂真实视频的适配需要更多样本验证。
