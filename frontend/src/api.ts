import type { Project, ROI } from './types'

const API_ORIGIN = (import.meta.env.VITE_API_ORIGIN || '').replace(/\/$/, '')
export const apiUrl = (path: string) => `${API_ORIGIN}${path}`

async function request<T>(url: string, options?: RequestInit): Promise<T> {
  let response: Response
  try { response = await fetch(apiUrl(url), options) }
  catch { throw new Error('无法连接视频处理服务，请稍后重试。') }
  if (!response.ok) {
    let detail = `请求失败（${response.status}）`
    try {
      const body = await response.json()
      detail = typeof body.detail === 'string' ? body.detail : JSON.stringify(body.detail)
    } catch { /* keep status */ }
    throw new Error(detail)
  }
  return response.json() as Promise<T>
}

const json = (data: unknown): RequestInit => ({
  method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(data),
})

export const api = {
  create: () => request<Project>('/api/projects', { method: 'POST' }),
  project: (id: string) => request<Project>(`/api/projects/${id}`),
  upload: async (id: string, file: File) => {
    const body = new FormData()
    body.append('file', file)
    return request<Project>(`/api/video/upload/${id}`, { method: 'POST', body })
  },
  analyze: (id: string) => request<{ roi: ROI }>(`/api/video/analyze/${id}`, { method: 'POST' }),
  roi: (id: string, roi: ROI) => request<Project>(`/api/roi/${id}`, json(roi)),
  start: (id: string, sampling_interval: number, scroll_direction: string) =>
    request(`/api/stitch/start/${id}`, json({ sampling_interval, scroll_direction })),
  progress: (id: string) => request<Project>(`/api/stitch/progress/${id}`),
  adjust: (id: string, data: { frame_id: number; dx?: number; dy?: number; excluded?: boolean; seam_offset?: number }) =>
    request(`/api/stitch/manual-adjust/${id}`, json(data)),
  retry: (id: string, frameId: number) => request(`/api/stitch/retry/${id}/${frameId}`, { method: 'POST' }),
  layout: (id: string, page_mode: string, paper: string, orientation: string) =>
    request(`/api/layout/${id}`, json({ page_mode, paper, orientation })),
  export: async (id: string, format: 'png' | 'jpg' | 'pdf', paper: string, orientation: string,
                 layout: string, page_mode: string) => {
    const response = await fetch(apiUrl(`/api/export/${id}`), json({ format, paper, orientation, layout, page_mode }))
    if (!response.ok) {
      const body = await response.json()
      throw new Error(body.detail || '导出失败。')
    }
    const blob = await response.blob()
    const link = document.createElement('a')
    link.href = URL.createObjectURL(blob)
    link.download = `guitar-tab.${format}`
    link.click()
    setTimeout(() => URL.revokeObjectURL(link.href), 1000)
  },
}

export const fmtTime = (seconds: number) => {
  const s = Math.floor(seconds || 0)
  return `${String(Math.floor(s / 60)).padStart(2, '0')}:${String(s % 60).padStart(2, '0')}`
}
