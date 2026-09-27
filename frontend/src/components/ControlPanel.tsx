import { useState } from 'react'
import { Compass, Download, LoaderCircle, RotateCcw, ScanLine, SlidersHorizontal } from 'lucide-react'
import type { Frame, Project, ROI } from '../types'
import { api } from '../api'

export default function ControlPanel({ project, roi, selected, onProject, onError, onVersion }: {
  project: Project; roi: ROI | null; selected: Frame | null;
  onProject: (project: Project) => void; onError: (error: string) => void; onVersion: () => void
}) {
  const [interval, setIntervalValue] = useState(project.sampling_interval || .5)
  const [direction, setDirection] = useState(project.scroll_direction || 'auto')
  const [busy, setBusy] = useState(false)
  const [format, setFormat] = useState<'png' | 'jpg' | 'pdf'>('png')
  const [paper, setPaper] = useState('a4')
  const [orientation, setOrientation] = useState('portrait')
  const [layout, setLayout] = useState('one_page')
  const [pageMode, setPageMode] = useState('fixed')
  const [debug, setDebug] = useState(false)
  const act = async (operation: () => Promise<unknown>, reload = true) => {
    setBusy(true); onError('')
    try { await operation(); if (reload) onProject(await api.project(project.id)); onVersion() }
    catch (error) { onError((error as Error).message) }
    finally { setBusy(false) }
  }
  return <section className="panel control-panel">
    <div className="panel-heading"><div><span className="panel-index">03</span><h2>识别设置</h2></div><SlidersHorizontal size={17} /></div>
    <div className="control-section">
      <div className="section-label"><span>谱面区域</span><span>{roi ? '已框选' : '未设置'}</span></div>
      <p>在左侧画面中拖动框选。尽量只包含谱面，避开字幕、播放器和水印。</p>
      <button className="secondary-button" disabled={busy || project.status === 'processing'} onClick={() => act(async () => {
        const found = await api.analyze(project.id)
        onProject(await api.roi(project.id, found.roi))
      }, false)}><ScanLine size={16} /> 自动检测谱面</button>
    </div>
    <div className="control-section">
      <div className="section-label"><span>抽帧间隔</span><b>{interval.toFixed(2)} 秒</b></div>
      <input type="range" min="0.1" max="2" step="0.05" value={interval}
        onChange={e => setIntervalValue(Number(e.target.value))} />
      <div className="range-hints"><span>更多细节</span><span>更快处理</span></div>
      <label className="field-label" htmlFor="direction">滚动方向</label>
      <select id="direction" value={direction} onChange={e => setDirection(e.target.value)}>
        <option value="auto">自动判断</option><option value="left">向左</option>
        <option value="right">向右</option><option value="up">向上</option><option value="down">向下</option>
      </select>
      <p>方向根据多帧位移统计；若自动判断不稳定，可手动指定。</p>
    </div>
    <div className="control-section processing-section">
      <button className="primary-button" disabled={!roi || busy || project.status === 'processing'}
        onClick={() => act(() => api.start(project.id, interval, direction))}>
        {project.status === 'processing' ? <LoaderCircle className="spin" size={18} /> : <Compass size={18} />}
        {project.status === 'processing' ? '正在识别' : project.status === 'completed' ? '重新识别' : '开始识别'}
      </button>
      {project.status === 'processing' && <div className="progress-block"><div className="progress-top"><span>{project.stage}</span><b>{project.progress}%</b></div>
        <div className="progress-track"><div style={{ width: `${project.progress}%` }} /></div>
        <small>已分析 {project.analyzed_frames || 0} / {project.total_frames || '…'} 帧</small></div>}
      {project.status === 'failed' && <p className="inline-error">{project.error}</p>}
      {project.status === 'completed' && <div className="completed-note"><span className="pulse" />已拼接 {project.result?.successful_frames} 帧 · 平均置信度 {Math.round((project.result?.average_confidence || 0)*100)}%</div>}
    </div>
    {project.status === 'completed' && <>
      <div className="control-section">
        <div className="section-label"><span>人工检查</span><span>Frame {selected ? selected.id+1 : '—'}</span></div>
        <p>从下方时间轴选帧。调整位移、边界或排除错误帧后，长图会重新生成。</p>
        {selected && <>
          <div className="metric-grid"><span>位移 X<b>{selected.dx.toFixed(1)}</b></span><span>位移 Y<b>{selected.dy.toFixed(1)}</b></span>
            <span>匹配点<b>{selected.matches}</b></span><span>内点<b>{selected.inliers}</b></span></div>
          <div className="nudge-row"><button onClick={() => act(() => api.adjust(project.id, { frame_id: selected.id, dx: selected.dx-1 }))}>← X</button>
            <button onClick={() => act(() => api.adjust(project.id, { frame_id: selected.id, dx: selected.dx+1 }))}>X →</button>
            <button onClick={() => act(() => api.adjust(project.id, { frame_id: selected.id, dy: selected.dy-1 }))}>↑ Y</button>
            <button onClick={() => act(() => api.adjust(project.id, { frame_id: selected.id, dy: selected.dy+1 }))}>Y ↓</button></div>
          <label className="field-label" htmlFor="seam">拼接边界偏移 {selected.seam_offset || 0} px</label>
          <input id="seam" type="range" min="-80" max="80" value={selected.seam_offset || 0}
            onChange={e => onProject({ ...project, frames: project.frames.map(f => f.id === selected.id ? { ...f, seam_offset: Number(e.target.value) } : f) })}
            onPointerUp={() => act(() => api.adjust(project.id, { frame_id: selected.id, seam_offset: selected.seam_offset || 0 }))} />
          <div className="edit-actions"><button disabled={busy} onClick={() => act(() => api.adjust(project.id, { frame_id: selected.id, excluded: !selected.excluded }))}>
            {selected.excluded ? '恢复此帧' : '排除此帧'}</button>
            <button disabled={busy || selected.id === 0} onClick={() => act(() => api.retry(project.id, selected.id))}><RotateCcw size={14} /> 重新匹配</button></div>
        </>}
      </div>
      <div className="control-section export-section">
        <div className="section-label"><span>排版与导出</span></div>
        <label className="field-label" htmlFor="layout">输出布局</label>
        <select id="layout" value={layout} onChange={e => setLayout(e.target.value)}>
          <option value="one_page">合为一页</option><option value="strip">原始长图 / 自动分页</option>
        </select>
        {layout === 'one_page' && <>
          <label className="field-label" htmlFor="page-mode">单页尺寸</label>
          <select id="page-mode" value={pageMode} onChange={e => setPageMode(e.target.value)}>
            <option value="fixed">A4/A3 单张纸，必要时缩小</option>
            <option value="long">正常谱面大小，加长单页</option>
          </select>
        </>}
        <div className="export-options"><select aria-label="纸张" value={paper} onChange={e => setPaper(e.target.value)}><option value="a4">A4</option><option value="a3">A3</option></select>
          <select aria-label="页面方向" value={orientation} onChange={e => setOrientation(e.target.value)}><option value="portrait">纵向</option><option value="landscape">横向</option></select></div>
        {layout === 'one_page' && <button className="secondary-button preview-button" disabled={busy}
          onClick={() => act(() => api.layout(project.id, pageMode, paper, orientation))}>
          <ScanLine size={16} /> 生成单页预览</button>}
        {project.layout_result && layout === 'one_page' && <p className="layout-summary">
          {project.layout_result.rows} 行 · {project.layout_result.paper_width_mm} × {project.layout_result.paper_height_mm} mm
          {project.layout_result.warning && <span>{project.layout_result.warning}</span>}</p>}
        <div className="format-row">{(['png', 'jpg', 'pdf'] as const).map(f => <button key={f} className={format === f ? 'chosen' : ''} onClick={() => setFormat(f)}>{f.toUpperCase()}</button>)}</div>
        <button className="secondary-button" disabled={busy} onClick={() => act(() => api.export(project.id, format, paper, orientation, layout, pageMode))}><Download size={16} /> 导出 {format.toUpperCase()}</button>
      </div>
      <div className="control-section debug-section"><label className="switch-line"><input type="checkbox" checked={debug} onChange={e => setDebug(e.target.checked)} /> 调试数据</label>
        {debug && selected && <pre>{JSON.stringify({ frame: selected.id, method: selected.method, dx: selected.dx,
          dy: selected.dy, overlap: selected.overlap, similarity: selected.similarity,
          matches: selected.matches, inliers: selected.inliers, confidence: selected.confidence }, null, 2)}</pre>}</div>
    </>}
  </section>
}
