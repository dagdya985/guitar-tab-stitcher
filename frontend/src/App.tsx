import { useEffect, useState } from 'react'
import { AudioLines, CircleHelp, RotateCcw, X } from 'lucide-react'
import { api } from './api'
import type { Project, ROI } from './types'
import UploadScreen from './components/UploadScreen'
import VideoPanel from './components/VideoPanel'
import AnalysisPanel from './components/AnalysisPanel'
import ControlPanel from './components/ControlPanel'
import Timeline from './components/Timeline'

export default function App() {
  const [project, setProject] = useState<Project | null>(null)
  const [error, setError] = useState('')
  const [uploading, setUploading] = useState(false)
  const [selectedId, setSelectedId] = useState(0)
  const [version, setVersion] = useState(0)
  const [help, setHelp] = useState(false)
  const reload = async (id: string) => {
    try {
      const next = await api.project(id)
      localStorage.setItem('gts-project', id)
      setProject(previous => {
        if (next.status === 'completed' && previous?.status !== 'completed')
          setSelectedId(Math.max(0, next.frames.length-1))
        return next
      })
    } catch { localStorage.removeItem('gts-project') }
  }
  useEffect(() => {
    const id = new URLSearchParams(window.location.search).get('project') || localStorage.getItem('gts-project')
    if (id) void reload(id)
  }, [])
  useEffect(() => {
    if (!project || project.status !== 'processing') return
    const timer = window.setInterval(() => void reload(project.id), 650)
    return () => window.clearInterval(timer)
  }, [project?.id, project?.status])
  const setCurrent = (next: Project) => {
    if (next.status === 'completed' && project?.status !== 'completed') setSelectedId(Math.max(0, next.frames.length-1))
    setProject(next)
    window.history.replaceState({}, '', `/?project=${next.id}`)
  }
  const upload = async (file: File) => {
    setError(''); setUploading(true)
    try {
      const created = await api.create()
      const uploaded = await api.upload(created.id, file)
      localStorage.setItem('gts-project', uploaded.id)
      setCurrent(uploaded)
    } catch (err) { setError((err as Error).message) }
    finally { setUploading(false) }
  }
  const saveRoi = async (roi: ROI) => {
    if (!project) return
    setError('')
    try { setCurrent(await api.roi(project.id, roi)) }
    catch (err) { setError((err as Error).message) }
  }
  const reset = () => {
    localStorage.removeItem('gts-project'); window.history.replaceState({}, '', '/')
    setProject(null); setSelectedId(0); setError('')
  }
  const adjustByDrag = async (dx: number, dy: number) => {
    if (!project || !selected) return
    try {
      await api.adjust(project.id, { frame_id: selected.id, dx, dy })
      setCurrent(await api.project(project.id))
      setVersion(v => v+1)
    } catch (err) { setError((err as Error).message) }
  }
  const selected = project?.frames?.[selectedId] || null
  return <div className="app-shell">
    <header className="topbar"><button className="brand" onClick={reset} title="返回上传页"><span className="brand-mark"><AudioLines size={21} strokeWidth={2.2} /></span>
      <span>Guitar Tab <strong>Stitcher</strong></span></button>
      <div className="top-actions">{project?.filename && <span className="file-pill">{project.filename}</span>}
        {project && <button className="top-link" onClick={reset}><RotateCcw size={15} /> 新建项目</button>}
        <button className="icon-button help-button" aria-label="使用说明" onClick={() => setHelp(true)}><CircleHelp size={19} /></button></div></header>
    {!project || project.status === 'created' ? <UploadScreen onFile={upload} busy={uploading} /> :
      <main className="workspace">
        <div className="workspace-title"><div><h1>工作台</h1><p>选中谱面，追踪画面位移，检查每一次拼接。</p></div>
          <div className="project-status"><span className={`status-dot ${project.status}`} />{project.status === 'completed' ? '已完成' : project.status === 'processing' ? '识别中' : project.status === 'failed' ? '处理失败' : '待识别'}</div></div>
        <div className="workspace-grid">
          <VideoPanel project={project} roi={project.roi} onRoi={saveRoi} />
          <AnalysisPanel project={project} selected={selected} version={version} onAdjust={adjustByDrag} />
          <ControlPanel project={project} roi={project.roi} selected={selected} onProject={setCurrent}
            onError={setError} onVersion={() => setVersion(v => v+1)} />
        </div>
        {project.frames?.length > 0 && <Timeline frames={project.frames} selected={selectedId} onSelect={setSelectedId} duration={project.duration} />}
      </main>}
    {error && <div className="toast" role="alert"><span>{error}</span><button onClick={() => setError('')} aria-label="关闭错误"><X size={16} /></button></div>}
    {help && <div className="modal-backdrop" onClick={() => setHelp(false)}><div className="help-modal" onClick={e => e.stopPropagation()}>
      <button className="modal-close" onClick={() => setHelp(false)} aria-label="关闭"><X size={20} /></button>
      <h2>如何获得更完整的谱面</h2>
      <ol><li>上传含滚动谱面的 MP4、MOV 或 WebM 视频。</li><li>在左侧画面拖出只覆盖谱面的矩形。避免播放器控件和字幕。</li>
        <li>按滚动速度选择抽帧间隔。滚动快时建议 0.1–0.3 秒。</li><li>开始识别后，在时间轴查看黄色和红色帧，调整位移或排除错误帧。</li>
        <li>在右侧导出长图或分页 PDF。</li></ol>
      <p>特征不足、谱面跳页或方向切换会降低匹配置信度。可缩小 ROI、缩短抽帧间隔后重新识别。</p>
    </div></div>}
  </div>
}
