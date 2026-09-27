import { useRef, useState } from 'react'
import { Maximize2, Minus, Plus } from 'lucide-react'
import { apiUrl } from '../api'

export default function TileViewer({ projectId, result, version, tilePath = '/api/stitch/tile' }: {
  projectId: string; result: { width: number; height: number }; version: number; tilePath?: string
}) {
  const [zoom, setZoom] = useState(.5)
  const [pan, setPan] = useState({ x: 24, y: 24 })
  const drag = useRef<{ x: number; y: number; px: number; py: number } | null>(null)
  const host = useRef<HTMLDivElement>(null)
  const cols = Math.ceil(result.width/1024), rows = Math.ceil(result.height/1024)
  const tiles = Array.from({ length: cols*rows }, (_, i) => ({ col: i%cols, row: Math.floor(i/cols) }))
  const setLimitedZoom = (value: number) => setZoom(Math.max(.25, Math.min(2, value)))
  return <div className="tile-viewer" ref={host} onWheel={e => {
      if (e.ctrlKey || e.altKey) { e.preventDefault(); setLimitedZoom(zoom*(e.deltaY > 0 ? .9 : 1.1)) }
      else setPan(p => ({ x: p.x-e.deltaX, y: p.y-e.deltaY }))
    }} onPointerDown={e => { host.current?.setPointerCapture(e.pointerId); drag.current = { x: e.clientX, y: e.clientY, px: pan.x, py: pan.y } }}
    onPointerMove={e => { if (drag.current) setPan({ x: drag.current.px+e.clientX-drag.current.x, y: drag.current.py+e.clientY-drag.current.y }) }}
    onPointerUp={() => { drag.current = null }}>
    <div className="tile-surface" style={{ width: result.width, height: result.height,
      transform: `translate(${pan.x}px, ${pan.y}px) scale(${zoom})` }}>
      {tiles.map(({ col, row }) => <img key={`${col}-${row}`} draggable={false}
        src={apiUrl(`${tilePath}/${projectId}/${col}/${row}?v=${version}`)}
        style={{ left: col*1024, top: row*1024, width: Math.min(1024, result.width-col*1024),
          height: Math.min(1024, result.height-row*1024) }} alt="吉他谱图块" />)}
    </div>
    <div className="viewer-controls" onPointerDown={e => e.stopPropagation()}>
      <button title="缩小" onClick={() => setLimitedZoom(zoom/1.25)}><Minus size={16} /></button>
      <span>{Math.round(zoom*100)}%</span>
      <button title="放大" onClick={() => setLimitedZoom(zoom*1.25)}><Plus size={16} /></button>
      <button title="全屏" onClick={() => host.current?.requestFullscreen()}><Maximize2 size={16} /></button>
    </div>
  </div>
}
