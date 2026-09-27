import { useEffect, useState } from 'react'
import { ScanSearch } from 'lucide-react'
import type { Frame, Project } from '../types'
import { apiUrl } from '../api'
import TileViewer from './TileViewer'
import AlignmentEditor from './AlignmentEditor'

type Mode = 'raw' | 'features' | 'overlap' | 'result' | 'page'
const modes: { key: Mode; label: string }[] = [
  { key: 'raw', label: '原图' }, { key: 'features', label: '特征匹配' },
  { key: 'overlap', label: '重叠区域' }, { key: 'result', label: '拼接结果' },
  { key: 'page', label: '单页排版' },
]

export default function AnalysisPanel({ project, selected, version, onAdjust }: {
  project: Project; selected: Frame | null; version: number;
  onAdjust: (dx: number, dy: number) => Promise<void>
}) {
  const [mode, setMode] = useState<Mode>('result')
  useEffect(() => { if (project.layout_result) setMode('page') }, [project.layout_result?.width, project.layout_result?.height])
  const ready = project.status === 'completed' && project.result
  return <section className="panel analysis-panel">
    <div className="panel-heading"><div><span className="panel-index">02</span><h2>帧分析与拼接</h2></div>
      <span className="heading-meta">{ready ? `${project.result?.width} × ${project.result?.height} px` : '等待识别'}</span></div>
    <div className="mode-tabs" role="tablist">{modes.map(item => <button key={item.key} role="tab"
      aria-selected={mode === item.key} className={mode === item.key ? 'active' : ''}
      onClick={() => setMode(item.key)}>{item.label}</button>)}</div>
    <div className="analysis-canvas">
      {!ready && <div className="analysis-empty"><ScanSearch size={34} strokeWidth={1.3} />
        <strong>谱面将在这里展开</strong><span>框选视频中的吉他谱，然后开始识别。</span></div>}
      {ready && mode === 'result' && <TileViewer projectId={project.id} result={project.result!} version={version} />}
      {ready && mode === 'page' && project.layout_result && <TileViewer projectId={project.id}
        result={project.layout_result} version={version} tilePath="/api/layout/tile" />}
      {ready && mode === 'page' && !project.layout_result && <div className="analysis-empty">在右侧生成单页预览。</div>}
      {ready && mode === 'raw' && selected && <div className="frame-view"><img src={apiUrl(`/api/stitch/frame/${project.id}/${selected.id}`)} alt={`第 ${selected.id+1} 帧谱面`} /></div>}
      {ready && mode === 'features' && selected && selected.id > 0 &&
        <div className="frame-view"><img src={apiUrl(`/api/stitch/debug/${project.id}/${selected.id}/${mode}?v=${version}`)}
          alt="ORB 特征点匹配" /></div>}
      {ready && mode === 'overlap' && selected && selected.id > 0 &&
        <AlignmentEditor project={project} frame={selected} onAdjust={onAdjust} />}
      {ready && (mode === 'features' || mode === 'overlap') && (!selected || selected.id === 0) &&
        <div className="analysis-empty">在下方时间轴选择第二帧或之后的画面。</div>}
    </div>
    {ready && selected && <div className="analysis-data">
      <span>Frame {String(selected.id+1).padStart(3, '0')}</span>
      <span>dx <b>{selected.dx.toFixed(1)}</b></span><span>dy <b>{selected.dy.toFixed(1)}</b></span>
      <span>重叠 <b>{Math.round(selected.overlap*100)}%</b></span>
      <span>置信度 <b className={selected.confidence < .57 ? 'warn' : ''}>{Math.round(selected.confidence*100)}%</b></span>
    </div>}
  </section>
}
