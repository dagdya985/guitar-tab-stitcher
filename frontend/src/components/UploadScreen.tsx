import { useRef, useState } from 'react'
import { ArrowUpRight, FileVideo2, UploadCloud } from 'lucide-react'

export default function UploadScreen({ onFile, busy }: { onFile: (file: File) => void; busy: boolean }) {
  const input = useRef<HTMLInputElement>(null)
  const [dragging, setDragging] = useState(false)
  const choose = (file?: File) => { if (file) onFile(file) }
  return <main className="landing">
    <div className="landing-inner">
      <div className="landing-note"><span className="pulse" /> 视频谱面整理工作台</div>
      <h1>让滚动的谱面<br /><span>回到纸上。</span></h1>
      <p className="landing-copy">从教学视频里找回完整吉他谱。选中谱面区域，系统分析每一帧的移动与重叠，拼出连续长图。</p>
      <div className={`dropzone ${dragging ? 'dragging' : ''}`} role="button" tabIndex={0}
        onKeyDown={e => { if (e.key === 'Enter' || e.key === ' ') input.current?.click() }}
        onClick={() => input.current?.click()}
        onDragOver={e => { e.preventDefault(); setDragging(true) }}
        onDragLeave={() => setDragging(false)}
        onDrop={e => { e.preventDefault(); setDragging(false); choose(e.dataTransfer.files[0]) }}>
        <input ref={input} type="file" accept=".mp4,.mov,.webm,video/mp4,video/quicktime,video/webm"
          hidden onChange={e => choose(e.target.files?.[0])} />
        <span className="drop-icon"><UploadCloud size={28} strokeWidth={1.6} /></span>
        <div><strong>{busy ? '正在上传视频…' : '将视频拖到这里'}</strong><span>或点击选择文件</span></div>
        <span className="drop-formats">MP4 / MOV / WEBM <ArrowUpRight size={15} /></span>
      </div>
      <div className="landing-foot"><FileVideo2 size={16} /> 处理在本机服务中完成；长图可导出为 PNG、JPG 或 PDF。</div>
    </div>
    <div className="hero-score" aria-hidden="true">
      <div className="score-label">TAB / MOTION STUDY</div>
      <div className="score-lines">
        {[0, 1, 2, 3, 4, 5].map((i) => <div key={i} className="score-line"><span>{['e', 'B', 'G', 'D', 'A', 'E'][i]}</span><b>{[7, 5, 9, 7, 5, 3][i]}</b><b>{[9, 7, 11, 9, 7, 5][i]}</b><b>{[10, 8, 12, 10, 8, 7][i]}</b></div>)}
      </div>
      <div className="score-caption">把碎片还原为一段完整的演奏</div>
    </div>
  </main>
}

