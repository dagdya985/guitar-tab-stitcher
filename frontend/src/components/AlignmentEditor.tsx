import { useEffect, useRef, useState } from 'react'
import type { Frame, Project } from '../types'
import { apiUrl } from '../api'

export default function AlignmentEditor({ project, frame, onAdjust }: {
  project: Project; frame: Frame; onAdjust: (dx: number, dy: number) => Promise<void>
}) {
  const host = useRef<HTMLDivElement>(null)
  const drag = useRef<{ x: number; y: number; dx: number; dy: number } | null>(null)
  const [size, setSize] = useState(500)
  const [offset, setOffset] = useState({ dx: frame.dx, dy: frame.dy })
  useEffect(() => setOffset({ dx: frame.dx, dy: frame.dy }), [frame.id, frame.dx, frame.dy])
  useEffect(() => {
    if (!host.current) return
    const observer = new ResizeObserver(entries => setSize(entries[0].contentRect.width))
    observer.observe(host.current)
    return () => observer.disconnect()
  }, [])
  const fw = project.width*(project.roi?.w || 1)
  const fh = project.height*(project.roi?.h || 1)
  const scale = Math.min((size-58)/fw, 2)
  return <div className="alignment-editor" ref={host}>
    <div className="alignment-stage" style={{ width: fw*scale, height: fh*scale }}>
      <img src={apiUrl(`/api/stitch/frame/${project.id}/${frame.id-1}`)} alt="前一帧" draggable={false} />
      <img className="alignment-current" src={apiUrl(`/api/stitch/frame/${project.id}/${frame.id}`)} alt="当前帧，拖动对齐"
        draggable={false} style={{ transform: `translate(${offset.dx*scale}px, ${offset.dy*scale}px)` }}
        onPointerDown={e => { e.currentTarget.setPointerCapture(e.pointerId); drag.current = { x: e.clientX, y: e.clientY, ...offset } }}
        onPointerMove={e => { if (!drag.current) return; setOffset({ dx: drag.current.dx+(e.clientX-drag.current.x)/scale,
          dy: drag.current.dy+(e.clientY-drag.current.y)/scale }) }}
        onPointerUp={() => { drag.current = null; void onAdjust(offset.dx, offset.dy) }} />
    </div>
    <div className="alignment-hint">拖动浅绿色图层，使数字与谱线重合 · dx {offset.dx.toFixed(1)} / dy {offset.dy.toFixed(1)}</div>
  </div>
}
