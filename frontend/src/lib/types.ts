export type Rule = {
  id: number;
  type: string;
  config: Record<string, unknown>;
  enabled: boolean;
  created_at: string;
  updated_at: string;
};

export type Snapshot = {
  id: number;
  monitor_id: number;
  created_at: string;
  final_url: string | null;
  page_title: string | null;
  http_status: number | null;
  raw_text: string | null;
  normalized_text: string | null;
  screenshot_url: string | null;
  element_screenshot_url: string | null;
  text_hash: string | null;
  visual_hash: string | null;
  metadata: Record<string, unknown>;
};

export type Monitor = {
  id: number;
  name: string;
  url: string;
  enabled: boolean;
  mode: string;
  selector: string | null;
  baseline_snapshot_id: number | null;
  interval_seconds: number;
  jitter_seconds: number;
  render_wait_ms: number;
  cooldown_seconds: number;
  pushover_profile_id: number | null;
  priority: number;
  pause_after_alert: boolean;
  status: string;
  failure_count: number;
  created_at: string;
  updated_at: string;
  last_checked_at: string | null;
  last_changed_at: string | null;
  last_alerted_at: string | null;
  rules: Rule[];
  baseline: Snapshot | null;
  latest_snapshot: Snapshot | null;
};

export type CheckRun = {
  id: number;
  monitor_id: number;
  started_at: string;
  finished_at: string | null;
  status: string;
  change_score: number;
  triggered_rules: Array<Record<string, unknown>>;
  error_message: string | null;
  snapshot_id: number | null;
  alert_id: number | null;
};

export type Alert = {
  id: number;
  monitor_id: number;
  check_run_id: number | null;
  created_at: string;
  status: string;
  title: string;
  message: string;
  url: string | null;
  retry_count: number;
  deduplication_key: string;
};

export type PreviewElement = {
  selector: string;
  tag: string;
  label: string;
  text: string;
  rect: { x: number; y: number; width: number; height: number };
  match_count: number;
  selector_quality: string;
};

export type PreviewLoad = {
  url: string;
  final_url: string | null;
  page_title: string | null;
  http_status: number | null;
  screenshot_base64: string;
  screenshot_width: number;
  screenshot_height: number;
  elements: PreviewElement[];
  captured_text: string;
};

export type PreviewSelection = {
  selector: string;
  text: string;
  html: string;
  match_count: number;
  rect: { x: number; y: number; width: number; height: number } | null;
  screenshot_base64: string | null;
};

export type PushoverProfile = {
  id: number;
  name: string;
  default_device: string | null;
  default_priority: number;
  created_at: string;
  updated_at: string;
};
