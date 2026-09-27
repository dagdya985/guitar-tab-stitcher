import { useEffect, useRef, useState } from 'react'
import { Camera, Pause, Play, SkipBack, SkipForward } from 'lucide-react'
import type { Project, ROI } from '../types'
import { apiUrl, fmtTime } from '../api'

export default function VideoPanel({ project, roi, onRoi }: {
  project: Project; roi: ROI | null; onRoi: (roi: ROI) => void
}) {
  const video = useRef<HTMLVideoElement>(null)
  const overlay = useRef<HTMLDivElement>(null)
  const start = useRef<{ x: number; y: number } | null>(null)
  const [draft, setDraft] = useState<ROI | null>(null)
  const [playing, setPlaying] = useState(false)
  const [time, setTime] = useState(0)
  const [speed, setSpeed] = useState(1)
  const active = draft || roi
  const point = (e: React.PointerEvent) => {
    const box = overlay.current!.getBoundingClientRect()
    return { x: Math.max(0, Math.min(1, (e.clientX-box.left)/box.width)),
             y: Math.max(0, Math.min(1, (e.clientY-box.top)/box.height)) }
  }
  const pointerDown = (e: React.PointerEvent) => {
    overlay.current?.setPointerCapture(e.pointerId)
    start.current = point(e)
    setDraft(null)
  }
  const pointerMove = (e: React.PointerEvent) => {
    if (!start.current) return
    const end = point(e), origin = start.current
    setDraft({ x: Math.min(origin.x, end.x), y: Math.min(origin.y, end.y),
               w: Math.abs(origin.x-end.x), h: Math.abs(origin.y-end.y) })
  }
  const pointerUp = (e: React.PointerEvent) => {
    if (!start.current) return
    const end = point(e), origin = start.current
    const next = { x: Math.min(origin.x, end.x), y: Math.min(origin.y, end.y),
                   w: Math.abs(origin.x-end.x), h: Math.abs(origin.y-end.y) }
    if (next.w > .02 && next.h > .02) onRoi(next)
    setDraft(null)
    start.current = null
  }
  const step = (n: number) => {
    if (!video.current) return
    video.current.pause(); setPlaying(false)
    video.current.currentTime = Math.max(0, Math.min(project.duration, video.current.currentTime+n/project.fps))
  }
  const shot = () => {
    if (!video.current) return
    const canvas = document.createElement('canvas')
    canvas.width = project.width; canvas.height = project.height
    canvas.getContext('2d')?.drawImage(video.current, 0, 0)
    canvas.toBlob(blob => {
      if (!blob) return
      const url = URL.createObjectURL(blob)
      const link = document.createElement('a'); link.href = url; link.download = `frame-${fmtTime(time).replace(':', '-')}.png`; link.click()
      setTimeout(() => URL.revokeObjectURL(url), 1000)
    })
  }
  useEffect(() => { if (video.current) video.current.playbackRate = speed }, [speed])
  return <section className="panel video-panel">
    <div className="panel-heading"><div><span className="panel-index">01</span><h2>视频与识别区域</h2></div><span className="heading-meta">原始画面</span></div>
    <div className="video-stage" style={{ aspectRatio: `${project.width}/${project.height}` }}>
      <video ref={video} src={apiUrl(`/api/video/${project.id}`)} playsInline onTimeUpdate={e => setTime(e.currentTarget.currentTime)}
        onEnded={() => setPlaying(false)} />
      <div ref={overlay} className="roi-overlay" onPointerDown={pointerDown} onPointerMove={pointerMove} onPointerUp={pointerUp}>
        {active && <div className="roi-box" style={{ left: `${active.x*100}%`, top: `${active.y*100}%`,
          width: `${active.w*100}%`, height: `${active.h*100}%` }}><span>谱面识别区域</span></div>}
      </div>
      {!active && <span className="roi-hint">拖动框选吉他谱区域</span>}
    </div>
    <div className="player-controls">
      <button className="icon-button" aria-label={playing ? '暂停' : '播放'} onClick={() => {
        if (!video.current) return
        if (playing) video.current.pause(); else video.current.play()
        setPlaying(!playing)
      }}>{playing ? <Pause size={17} /> : <Play size={17} />}</button>
      <button className="icon-button" aria-label="上一帧" onClick={() => step(-1)}><SkipBack size={15} /></button>
      <button className="icon-button" aria-label="下一帧" onClick={() => step(1)}><SkipForward size={15} /></button>
      <span className="time-readout">{fmtTime(time)} <i>/</i> {fmtTime(project.duration)}</span>
      <select className="speed-select" aria-label="播放速度" value={speed} onChange={e => setSpeed(Number(e.target.value))}>
        {[.5, 1, 1.5, 2].map(n => <option key={n} value={n}>{n}×</option>)}
      </select>
      <button className="icon-button" aria-label="截图" title="保存当前视频帧" onClick={shot}><Camera size={16} /></button>
    </div>
    <input className="video-seek" aria-label="视频进度" type="range" min="0" max={project.duration || 1}
      value={time} step={1/project.fps} onChange={e => { if (video.current) video.current.currentTime = Number(e.target.value) }} />
    <div className="video-meta"><span>{project.width} × {project.height}</span><span>{project.fps.toFixed(1)} FPS</span><span>{project.codec || 'VIDEO'}</span></div>
  </section>
}
