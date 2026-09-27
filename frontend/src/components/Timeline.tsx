import type { Frame } from '../types'
import { fmtTime } from '../api'

export default function Timeline({ frames, selected, onSelect, duration }: {
  frames: Frame[]; selected: number; onSelect: (id: number) => void; duration: number
}) {
  return <section className="timeline-panel">
    <div className="timeline-heading"><h2>视频时间轴</h2><span><i className="legend good" /> 成功 <i className="legend low" /> 低置信度 <i className="legend bad" /> 失败</span></div>
    <div className="timeline-ruler"><span>00:00</span><span>{fmtTime(duration/2)}</span><span>{fmtTime(duration)}</span></div>
    <div className="timeline-track">{frames.map(frame => <button key={frame.id}
      className={`frame-marker ${frame.status} ${frame.excluded ? 'excluded' : ''} ${selected === frame.id ? 'selected' : ''}`}
      style={{ left: `${duration ? frame.timestamp/duration*100 : 0}%` }}
      onClick={() => onSelect(frame.id)} title={`Frame ${frame.id+1} · ${fmtTime(frame.timestamp)} · ${Math.round(frame.confidence*100)}%`} />)}</div>
    <div className="timeline-tip">点击标记查看匹配画面并修复拼接位置</div>
  </section>
}

