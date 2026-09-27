export type ROI = { x: number; y: number; w: number; h: number }
export type Frame = {
  id: number; timestamp: number; path: string; dx: number; dy: number;
  confidence: number; overlap: number; similarity: number; matches: number;
  inliers: number; method: string; status: 'first' | 'success' | 'low' | 'failed';
  x: number; y: number; excluded?: boolean; seam_offset?: number
}
export type StitchResult = {
  width: number; height: number; frame_count: number; successful_frames: number;
  failed_frames: number; average_confidence: number; output_path: string
}
export type LayoutResult = { width: number; height: number; rows: number; scale: number;
  paper_width_mm: number; paper_height_mm: number; warning: string | null }
export type Project = {
  id: string; filename: string; duration: number; fps: number; width: number;
  height: number; codec: string; roi: ROI | null; sampling_interval: number;
  scroll_direction: string; detected_direction: string | null;
  status: string; stage: string; progress: number; error: string | null;
  analyzed_frames?: number; total_frames?: number; frames: Frame[];
  result: StitchResult | null; layout_result: LayoutResult | null
}
