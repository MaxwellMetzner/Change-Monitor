import {
  Activity,
  AlertTriangle,
  Bell,
  ChevronRight,
  CheckCircle2,
  CircleHelp,
  ExternalLink,
  History,
  Loader2,
  MousePointer2,
  Pause,
  Play,
  Plus,
  RefreshCw,
  RotateCcw,
  Save,
  Settings,
  ShieldCheck,
  Trash2
} from "lucide-react";
import React, { FormEvent, useCallback, useEffect, useMemo, useState } from "react";
import { api } from "./lib/api";
import type { Alert, AppSettings, CheckRun, Monitor, PreviewElement, PreviewLoad, PreviewSelection, PushoverProfile } from "./lib/types";

type View = "dashboard" | "new" | "settings" | "detail";

const statusTone: Record<string, string> = {
  ready: "bg-emerald-50 text-emerald-800 border-emerald-200",
  unchanged: "bg-emerald-50 text-emerald-800 border-emerald-200",
  changed: "bg-amber-50 text-amber-900 border-amber-200",
  alert_sent: "bg-rose-50 text-rose-800 border-rose-200",
  failed: "bg-red-50 text-red-800 border-red-200",
  paused: "bg-zinc-100 text-zinc-700 border-zinc-200",
  paused_after_alert: "bg-zinc-100 text-zinc-700 border-zinc-200",
  new: "bg-sky-50 text-sky-800 border-sky-200"
};

const defaultAppSettings: AppSettings = {
  app_base_url: "http://localhost:8000",
  default_check_interval_seconds: 180,
  default_jitter_seconds: 20,
  default_render_wait_ms: 1500,
  max_concurrent_checks: 2,
  data_dir: "",
  settings_path: "",
  settings_hash: "",
  settings_hash_valid: null,
  encryption_key_status: "stored in data volume"
};

function classNames(...values: Array<string | false | null | undefined>) {
  return values.filter(Boolean).join(" ");
}

function domain(url: string) {
  try {
    return new URL(url).hostname.replace(/^www\./, "");
  } catch {
    return url;
  }
}

function timeAgo(value: string | null) {
  if (!value) return "Never";
  const diff = Date.now() - new Date(value).getTime();
  if (diff < 60_000) return "Just now";
  if (diff < 3_600_000) return `${Math.round(diff / 60_000)}m ago`;
  if (diff < 86_400_000) return `${Math.round(diff / 3_600_000)}h ago`;
  return `${Math.round(diff / 86_400_000)}d ago`;
}

function durationLabel(seconds: number) {
  if (seconds < 60) return `${seconds}s`;
  if (seconds % 3600 === 0) return `${seconds / 3600}h`;
  if (seconds % 60 === 0) return `${seconds / 60} minutes`;
  return `${seconds}s`;
}

function waitLabel(ms: number) {
  return `${(ms / 1000).toFixed(ms % 1000 === 0 ? 0 : 1)} seconds`;
}

function elementArea(element: PreviewElement) {
  return element.rect.width * element.rect.height;
}

function rectsOverlap(left: PreviewElement["rect"], right: PreviewElement["rect"]) {
  return !(
    left.x + left.width < right.x ||
    right.x + right.width < left.x ||
    left.y + left.height < right.y ||
    right.y + right.height < left.y
  );
}

function Button({
  children,
  variant = "primary",
  className,
  ...props
}: React.ButtonHTMLAttributes<HTMLButtonElement> & { variant?: "primary" | "secondary" | "danger" | "ghost" }) {
  return (
    <button
      {...props}
      className={classNames(
        "inline-flex min-h-10 items-center justify-center gap-2 rounded-md px-3 py-2 text-sm font-medium transition disabled:cursor-not-allowed disabled:opacity-50",
        variant === "primary" && "bg-teal-700 text-white hover:bg-teal-800",
        variant === "secondary" && "border border-zinc-300 bg-white text-zinc-800 hover:bg-zinc-50",
        variant === "danger" && "border border-red-200 bg-red-50 text-red-700 hover:bg-red-100",
        variant === "ghost" && "text-zinc-700 hover:bg-zinc-100",
        className
      )}
    >
      {children}
    </button>
  );
}

function HelpTip({ text }: { text: string }) {
  return (
    <span
      className="inline-flex h-5 w-5 items-center justify-center rounded-full text-zinc-400 hover:text-teal-700"
      title={text}
      aria-label={text}
    >
      <CircleHelp className="h-4 w-4" />
    </span>
  );
}

function Field({
  label,
  children,
  hint,
  help
}: {
  label: string;
  children: React.ReactNode;
  hint?: string;
  help?: string;
}) {
  return (
    <label className="grid gap-1.5 text-sm font-medium text-zinc-800">
      <span className="flex items-center gap-1.5">
        {label}
        {help ? <HelpTip text={help} /> : null}
      </span>
      {children}
      {hint ? <span className="text-xs font-normal text-zinc-500">{hint}</span> : null}
    </label>
  );
}

function TextInput(props: React.InputHTMLAttributes<HTMLInputElement>) {
  return (
    <input
      {...props}
      className={classNames(
        "h-10 rounded-md border border-zinc-300 bg-white px-3 text-sm text-zinc-900 shadow-sm transition placeholder:text-zinc-400",
        props.className
      )}
    />
  );
}

function Select(props: React.SelectHTMLAttributes<HTMLSelectElement>) {
  return (
    <select
      {...props}
      className={classNames("h-10 rounded-md border border-zinc-300 bg-white px-3 text-sm text-zinc-900 shadow-sm", props.className)}
    />
  );
}

function StatusChip({ status }: { status: string }) {
  return (
    <span className={classNames("inline-flex rounded-md border px-2 py-1 text-xs font-semibold capitalize", statusTone[status] ?? statusTone.new)}>
      {status.replaceAll("_", " ")}
    </span>
  );
}

function EmptyState({ onCreate }: { onCreate: () => void }) {
  return (
    <section className="grid min-h-80 place-items-center rounded-md border border-dashed border-zinc-300 bg-white px-6 text-center">
      <div className="max-w-sm">
        <ShieldCheck className="mx-auto h-10 w-10 text-teal-700" />
        <h2 className="mt-4 text-xl font-semibold text-zinc-900">No monitors yet</h2>
        <p className="mt-2 text-sm text-zinc-600">Create a monitor from a rendered page preview and store a baseline before the scheduler starts checking it.</p>
        <Button className="mt-5" onClick={onCreate}>
          <Plus className="h-4 w-4" />
          New monitor
        </Button>
      </div>
    </section>
  );
}

function Dashboard({
  monitors,
  alerts,
  busyId,
  onCreate,
  onOpen,
  onRefresh,
  onCheck,
  onPauseResume,
  onDelete
}: {
  monitors: Monitor[];
  alerts: Alert[];
  busyId: number | null;
  onCreate: () => void;
  onOpen: (id: number) => void;
  onRefresh: () => void;
  onCheck: (id: number) => void;
  onPauseResume: (monitor: Monitor) => void;
  onDelete: (id: number) => void;
}) {
  if (monitors.length === 0) return <EmptyState onCreate={onCreate} />;

  return (
    <div className="grid gap-5">
      <section className="overflow-hidden rounded-md border border-zinc-200 bg-white shadow-soft">
        <div className="flex flex-wrap items-center justify-between gap-3 border-b border-zinc-200 px-4 py-3">
          <div>
            <h2 className="text-base font-semibold text-zinc-950">Monitors</h2>
            <p className="text-sm text-zinc-500">{monitors.length} configured</p>
          </div>
          <div className="flex flex-wrap gap-2">
            <Button variant="secondary" onClick={onRefresh}>
              <RefreshCw className="h-4 w-4" />
              Refresh
            </Button>
            <Button onClick={onCreate}>
              <Plus className="h-4 w-4" />
              New
            </Button>
          </div>
        </div>
        <div className="divide-y divide-zinc-200">
          {monitors.map((monitor) => (
            <article key={monitor.id} className="grid gap-4 px-4 py-4 lg:grid-cols-[1fr_auto] lg:items-center">
              <button className="min-w-0 text-left" onClick={() => onOpen(monitor.id)}>
                <div className="flex flex-wrap items-center gap-2">
                  <h3 className="truncate text-base font-semibold text-zinc-950">{monitor.name}</h3>
                  <StatusChip status={monitor.enabled ? monitor.status : "paused"} />
                </div>
                <div className="mt-1 flex flex-wrap gap-x-4 gap-y-1 text-sm text-zinc-500">
                  <span>{domain(monitor.url)}</span>
                  <span>{monitor.mode.replaceAll("_", " ")}</span>
                  <span>{Math.round(monitor.interval_seconds / 60)}m interval</span>
                  <span>{(monitor.render_wait_ms / 1000).toFixed(1)}s wait</span>
                  <span>Last check {timeAgo(monitor.last_checked_at)}</span>
                  <span>Last alert {timeAgo(monitor.last_alerted_at)}</span>
                </div>
              </button>
              <div className="flex flex-wrap gap-2">
                <Button variant="secondary" onClick={() => onOpen(monitor.id)} title="Open monitor details">
                  Details
                  <ChevronRight className="h-4 w-4" />
                </Button>
                <Button variant="secondary" onClick={() => onCheck(monitor.id)} disabled={busyId === monitor.id} title="Check now">
                  {busyId === monitor.id ? <Loader2 className="h-4 w-4 animate-spin" /> : <Activity className="h-4 w-4" />}
                </Button>
                <Button variant="secondary" onClick={() => onPauseResume(monitor)} title={monitor.enabled ? "Pause" : "Resume"}>
                  {monitor.enabled ? <Pause className="h-4 w-4" /> : <Play className="h-4 w-4" />}
                </Button>
                <Button variant="secondary" onClick={() => window.open(monitor.url, "_blank", "noopener,noreferrer")} title="Open page">
                  <ExternalLink className="h-4 w-4" />
                </Button>
                <Button variant="danger" onClick={() => onDelete(monitor.id)} title="Delete">
                  <Trash2 className="h-4 w-4" />
                </Button>
              </div>
            </article>
          ))}
        </div>
      </section>

      <section className="rounded-md border border-zinc-200 bg-white shadow-soft">
        <div className="border-b border-zinc-200 px-4 py-3">
          <h2 className="text-base font-semibold text-zinc-950">Recent Alerts</h2>
        </div>
        <div className="divide-y divide-zinc-200">
          {alerts.slice(0, 5).map((alert) => (
            <div key={alert.id} className="grid gap-1 px-4 py-3 text-sm">
              <div className="flex flex-wrap items-center gap-2">
                <Bell className="h-4 w-4 text-teal-700" />
                <span className="font-medium text-zinc-900">{alert.title}</span>
                <StatusChip status={alert.status} />
                <span className="text-zinc-500">{timeAgo(alert.created_at)}</span>
              </div>
              <p className="line-clamp-2 text-zinc-600">{alert.message}</p>
            </div>
          ))}
          {alerts.length === 0 ? <p className="px-4 py-5 text-sm text-zinc-500">No alert records yet.</p> : null}
        </div>
      </section>
    </div>
  );
}

function PreviewPicker({
  preview,
  selected,
  onSelect
}: {
  preview: PreviewLoad;
  selected: PreviewElement | null;
  onSelect: (element: PreviewElement) => void;
}) {
  const imageSrc = `data:image/png;base64,${preview.screenshot_base64}`;
  return (
    <div className="overflow-hidden rounded-md border border-zinc-300 bg-zinc-100">
      <div className="relative max-h-[720px] overflow-auto scrollbar-thin">
        <div className="relative min-w-[720px]" style={{ width: "100%" }}>
          <img src={imageSrc} alt="Rendered page preview" className="block w-full select-none" draggable={false} />
          {preview.elements.map((element) => {
            const area = elementArea(element);
            const style = {
              left: `${(element.rect.x / preview.screenshot_width) * 100}%`,
              top: `${(element.rect.y / preview.screenshot_height) * 100}%`,
              width: `${(element.rect.width / preview.screenshot_width) * 100}%`,
              height: `${(element.rect.height / preview.screenshot_height) * 100}%`,
              zIndex: selected?.selector === element.selector ? 1000 : Math.max(1, 900 - Math.round(Math.sqrt(area)))
            };
            const isSelected = selected?.selector === element.selector;
            return (
              <button
                key={`${element.selector}-${element.rect.x}-${element.rect.y}`}
                type="button"
                title={element.label}
                onClick={() => onSelect(element)}
                className={classNames(
                  "absolute border-2 bg-teal-400/5 transition hover:bg-amber-300/20",
                  isSelected ? "border-amber-500 bg-amber-300/25" : "border-teal-500/70"
                )}
                style={style}
              />
            );
          })}
        </div>
      </div>
    </div>
  );
}

function NewMonitorWizard({
  profiles,
  appSettings,
  onCreated,
  onCancel
}: {
  profiles: PushoverProfile[];
  appSettings: AppSettings;
  onCreated: (monitor: Monitor) => void;
  onCancel: () => void;
}) {
  const [url, setUrl] = useState("");
  const [name, setName] = useState("");
  const [interval, setIntervalValue] = useState(appSettings.default_check_interval_seconds);
  const [renderWaitMs, setRenderWaitMs] = useState(appSettings.default_render_wait_ms);
  const [profileId, setProfileId] = useState<string>("");
  const [priority, setPriority] = useState(0);
  const [currentStateBad, setCurrentStateBad] = useState(true);
  const [preview, setPreview] = useState<PreviewLoad | null>(null);
  const [selected, setSelected] = useState<PreviewElement | null>(null);
  const [selection, setSelection] = useState<PreviewSelection | null>(null);
  const [loadingPreview, setLoadingPreview] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const intervalOptions = useMemo(
    () => Array.from(new Set([appSettings.default_check_interval_seconds, 60, 180, 900, 1800])).sort((left, right) => left - right),
    [appSettings.default_check_interval_seconds]
  );
  const waitOptions = useMemo(
    () => Array.from(new Set([appSettings.default_render_wait_ms, 1500, 3000, 5000, 8000])).sort((left, right) => left - right),
    [appSettings.default_render_wait_ms]
  );

  const suggestedName = useMemo(() => {
    if (name.trim()) return name;
    if (!url) return "";
    return `${domain(url)} watch`;
  }, [name, url]);

  const nearbyElements = useMemo(() => {
    if (!preview || !selected) return [];
    const selectedArea = elementArea(selected);
    return preview.elements
      .filter((element) => element.selector !== selected.selector)
      .filter((element) => rectsOverlap(element.rect, selected.rect))
      .sort((left, right) => {
        const leftArea = elementArea(left);
        const rightArea = elementArea(right);
        const leftSmaller = leftArea <= selectedArea;
        const rightSmaller = rightArea <= selectedArea;
        if (leftSmaller !== rightSmaller) return leftSmaller ? -1 : 1;
        return leftArea - rightArea;
      })
      .slice(0, 8);
  }, [preview, selected]);

  async function loadPreview(event?: FormEvent) {
    event?.preventDefault();
    setError(null);
    setLoadingPreview(true);
    setPreview(null);
    setSelected(null);
    setSelection(null);
    try {
      const nextPreview = await api.previewLoad({ url, wait_ms: renderWaitMs });
      setPreview(nextPreview);
      if (!name.trim()) setName(`${domain(nextPreview.final_url || url)} watch`);
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : "Preview failed");
    } finally {
      setLoadingPreview(false);
    }
  }

  async function selectElement(element: PreviewElement) {
    setSelected(element);
    setError(null);
    try {
      const selectedElement = await api.previewSelect({ url, selector: element.selector, wait_ms: renderWaitMs });
      setSelection(selectedElement);
    } catch (exc) {
      setSelection(null);
      setError(exc instanceof Error ? exc.message : "Selection failed");
    }
  }

  async function saveMonitor() {
    setError(null);
    setSaving(true);
    try {
      const monitor = await api.createMonitor({
        name: suggestedName,
        url,
        mode: selected ? (currentStateBad ? "bad_state" : "element_text") : "whole_page_text",
        selector: selected?.selector ?? null,
        interval_seconds: interval,
        jitter_seconds: appSettings.default_jitter_seconds,
        render_wait_ms: renderWaitMs,
        cooldown_seconds: 1800,
        pushover_profile_id: profileId ? Number(profileId) : null,
        priority,
        pause_after_alert: false,
        current_state_is_bad: currentStateBad,
        wait_ms: renderWaitMs
      });
      onCreated(monitor);
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : "Save failed");
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="grid gap-5">
      <section className="rounded-md border border-zinc-200 bg-white p-4 shadow-soft">
        <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
          <div>
            <h2 className="text-lg font-semibold text-zinc-950">New Monitor</h2>
            <p className="text-sm text-zinc-500">Render a page, choose the watched area, and capture a baseline.</p>
          </div>
          <Button variant="secondary" onClick={onCancel}>
            Back
          </Button>
        </div>

        <form onSubmit={loadPreview} className="grid gap-3 md:grid-cols-[1fr_auto] md:items-end">
          <Field label="URL">
            <TextInput required type="url" value={url} onChange={(event) => setUrl(event.target.value)} placeholder="https://example.com/product" />
          </Field>
          <Button type="submit" disabled={!url || loadingPreview}>
            {loadingPreview ? <Loader2 className="h-4 w-4 animate-spin" /> : <MousePointer2 className="h-4 w-4" />}
            Load
          </Button>
        </form>
      </section>

      {error ? (
        <div className="flex items-start gap-2 rounded-md border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800">
          <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
          <span>{error}</span>
        </div>
      ) : null}

      {preview ? (
        <section className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_380px]">
          <PreviewPicker preview={preview} selected={selected} onSelect={selectElement} />

          <aside className="grid content-start gap-4 rounded-md border border-zinc-200 bg-white p-4 shadow-soft">
            <div>
              <h3 className="text-base font-semibold text-zinc-950">{preview.page_title || domain(preview.final_url || url)}</h3>
              <p className="break-all text-sm text-zinc-500">{preview.final_url || url}</p>
            </div>

            <Field label="Name">
              <TextInput value={name} onChange={(event) => setName(event.target.value)} placeholder={suggestedName || "Product watch"} />
            </Field>

            <div className="grid grid-cols-2 gap-3">
              <Field label="Interval">
                <Select value={interval} onChange={(event) => setIntervalValue(Number(event.target.value))}>
                  {intervalOptions.map((value) => (
                    <option key={value} value={value}>
                      {durationLabel(value)}
                    </option>
                  ))}
                </Select>
              </Field>
              <Field label="Priority">
                <Select value={priority} onChange={(event) => setPriority(Number(event.target.value))}>
                  <option value={0}>Normal</option>
                  <option value={1}>High</option>
                  <option value={-1}>Quiet</option>
                </Select>
              </Field>
            </div>

            <Field label="After-load wait" hint="Use a longer wait when the page shows a temporary message before the real stock state.">
              <Select value={renderWaitMs} onChange={(event) => setRenderWaitMs(Number(event.target.value))}>
                {waitOptions.map((value) => (
                  <option key={value} value={value}>
                    {waitLabel(value)}
                  </option>
                ))}
              </Select>
            </Field>

            <Field label="Pushover">
              <Select value={profileId} onChange={(event) => setProfileId(event.target.value)}>
                <option value="">No profile</option>
                {profiles.map((profile) => (
                  <option key={profile.id} value={profile.id}>
                    {profile.name}
                  </option>
                ))}
              </Select>
            </Field>

            <label className="flex items-start gap-3 rounded-md border border-amber-200 bg-amber-50 p-3 text-sm text-amber-950">
              <input
                type="checkbox"
                className="mt-1 h-4 w-4 accent-teal-700"
                checked={currentStateBad}
                onChange={(event) => setCurrentStateBad(event.target.checked)}
              />
              <span>This page currently shows the unavailable state. Notify me when this changes.</span>
            </label>

            <div className="rounded-md border border-zinc-200 bg-zinc-50 p-3">
              <div className="mb-2 flex items-center justify-between gap-2">
                <span className="text-sm font-semibold text-zinc-900">Selection</span>
                {selected ? <span className="text-xs text-zinc-500">{selected.selector_quality}</span> : null}
              </div>
              {selected ? (
                <div className="grid gap-2 text-sm">
                  <p className="break-all font-mono text-xs text-zinc-600">{selected.selector}</p>
                  <p className="max-h-28 overflow-auto whitespace-pre-wrap text-zinc-800 scrollbar-thin">{selection?.text || selected.text}</p>
                  {selection?.match_count && selection.match_count > 1 ? (
                    <p className="text-xs text-amber-800">Selector matches {selection.match_count} elements.</p>
                  ) : null}
                  {nearbyElements.length > 0 ? (
                    <div className="mt-2 grid gap-2">
                      <p className="text-xs font-semibold uppercase tracking-wide text-zinc-500">Nearby choices</p>
                      <div className="grid max-h-44 gap-2 overflow-auto pr-1 scrollbar-thin">
                        {nearbyElements.map((element) => (
                          <button
                            key={`${element.selector}-${element.rect.x}-${element.rect.y}-nearby`}
                            type="button"
                            className="grid min-w-0 gap-1 rounded-md border border-zinc-200 bg-white px-2 py-2 text-left hover:border-teal-500"
                            onClick={() => selectElement(element)}
                          >
                            <span className="text-xs font-semibold uppercase text-teal-800">{element.tag}</span>
                            <span className="min-w-0 break-words text-xs text-zinc-700">{element.label}</span>
                          </button>
                        ))}
                      </div>
                    </div>
                  ) : null}
                </div>
              ) : (
                <p className="text-sm text-zinc-500">Click an outlined area, or save as a whole page text monitor.</p>
              )}
            </div>

            <Button onClick={saveMonitor} disabled={!url || saving}>
              {saving ? <Loader2 className="h-4 w-4 animate-spin" /> : <Save className="h-4 w-4" />}
              Save monitor
            </Button>
          </aside>
        </section>
      ) : null}
    </div>
  );
}

function MonitorDetail({
  monitor,
  runs,
  busyId,
  onBack,
  onRefresh,
  onCheck,
  onPauseResume,
  onRebaseline,
  onUpdateWait
}: {
  monitor: Monitor;
  runs: CheckRun[];
  busyId: number | null;
  onBack: () => void;
  onRefresh: () => void;
  onCheck: (id: number) => void;
  onPauseResume: (monitor: Monitor) => void;
  onRebaseline: (id: number) => void;
  onUpdateWait: (id: number, renderWaitMs: number) => void;
}) {
  const baselineImage = monitor.baseline?.element_screenshot_url || monitor.baseline?.screenshot_url;
  const latestImage = monitor.latest_snapshot?.element_screenshot_url || monitor.latest_snapshot?.screenshot_url;

  return (
    <div className="grid gap-5">
      <section className="rounded-md border border-zinc-200 bg-white p-4 shadow-soft">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-2">
              <h2 className="truncate text-xl font-semibold text-zinc-950">{monitor.name}</h2>
              <StatusChip status={monitor.enabled ? monitor.status : "paused"} />
            </div>
            <p className="mt-1 break-all text-sm text-zinc-500">{monitor.url}</p>
            <p className="mt-1 text-sm text-zinc-500">
              Checks wait {(monitor.render_wait_ms / 1000).toFixed(1)}s after load before capturing.
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            <Button variant="secondary" onClick={onBack}>
              Back
            </Button>
            <Button variant="secondary" onClick={onRefresh}>
              <RefreshCw className="h-4 w-4" />
            </Button>
            <Button variant="secondary" onClick={() => onCheck(monitor.id)} disabled={busyId === monitor.id}>
              {busyId === monitor.id ? <Loader2 className="h-4 w-4 animate-spin" /> : <Activity className="h-4 w-4" />}
              Check
            </Button>
            <Button variant="secondary" onClick={() => onPauseResume(monitor)}>
              {monitor.enabled ? <Pause className="h-4 w-4" /> : <Play className="h-4 w-4" />}
            </Button>
            <Button onClick={() => onRebaseline(monitor.id)}>
              <RotateCcw className="h-4 w-4" />
              Baseline
            </Button>
          </div>
        </div>
        <div className="mt-4 max-w-xs">
          <Field label="After-load wait" hint="Raise this if the page shows a temporary busy/loading status before the final stock text.">
            <Select value={monitor.render_wait_ms} onChange={(event) => onUpdateWait(monitor.id, Number(event.target.value))}>
              <option value={1500}>1.5 seconds</option>
              <option value={3000}>3 seconds</option>
              <option value={5000}>5 seconds</option>
              <option value={8000}>8 seconds</option>
            </Select>
          </Field>
        </div>
      </section>

      <section className="grid gap-5 xl:grid-cols-2">
        <div className="rounded-md border border-zinc-200 bg-white p-4 shadow-soft">
          <h3 className="mb-3 text-base font-semibold text-zinc-950">Baseline</h3>
          {baselineImage ? <img className="max-h-96 w-full rounded-md border border-zinc-200 object-contain" src={baselineImage} alt="Baseline capture" /> : null}
          <pre className="mt-3 max-h-64 overflow-auto whitespace-pre-wrap rounded-md bg-zinc-950 p-3 text-xs text-zinc-100 scrollbar-thin">
            {monitor.baseline?.raw_text || "No baseline text stored."}
          </pre>
        </div>
        <div className="rounded-md border border-zinc-200 bg-white p-4 shadow-soft">
          <h3 className="mb-3 text-base font-semibold text-zinc-950">Latest</h3>
          {latestImage ? <img className="max-h-96 w-full rounded-md border border-zinc-200 object-contain" src={latestImage} alt="Latest capture" /> : null}
          <pre className="mt-3 max-h-64 overflow-auto whitespace-pre-wrap rounded-md bg-zinc-950 p-3 text-xs text-zinc-100 scrollbar-thin">
            {monitor.latest_snapshot?.raw_text || "No latest text stored."}
          </pre>
        </div>
      </section>

      <section className="grid gap-5 xl:grid-cols-[minmax(0,360px)_minmax(0,1fr)]">
        <div className="min-w-0 overflow-hidden rounded-md border border-zinc-200 bg-white p-4 shadow-soft">
          <h3 className="mb-3 text-base font-semibold text-zinc-950">Rules</h3>
          <div className="grid min-w-0 gap-3">
            {monitor.rules.map((rule) => (
              <div key={rule.id} className="min-w-0 overflow-hidden rounded-md border border-zinc-200 bg-zinc-50 p-3">
                <div className="flex min-w-0 flex-wrap items-center justify-between gap-2">
                  <span className="min-w-0 break-words text-sm font-semibold text-zinc-900">{rule.type.replaceAll("_", " ")}</span>
                  <StatusChip status={rule.enabled ? "ready" : "paused"} />
                </div>
                <pre className="mt-2 max-w-full overflow-auto whitespace-pre-wrap break-words text-xs text-zinc-600 scrollbar-thin">
                  {JSON.stringify(rule.config, null, 2)}
                </pre>
              </div>
            ))}
          </div>
        </div>

        <div className="min-w-0 rounded-md border border-zinc-200 bg-white shadow-soft">
          <div className="flex items-center gap-2 border-b border-zinc-200 px-4 py-3">
            <History className="h-4 w-4 text-teal-700" />
            <h3 className="text-base font-semibold text-zinc-950">History</h3>
          </div>
          <div className="divide-y divide-zinc-200">
            {runs.map((run) => (
              <div key={run.id} className="grid gap-2 px-4 py-3 text-sm">
                <div className="flex flex-wrap items-center gap-2">
                  <StatusChip status={run.status} />
                  <span className="font-medium text-zinc-900">{timeAgo(run.started_at)}</span>
                  <span className="text-zinc-500">score {Math.round(run.change_score * 100)}%</span>
                  {run.snapshot_id ? <span className="text-zinc-500">snapshot #{run.snapshot_id}</span> : null}
                </div>
                {run.triggered_rules.length ? (
                  <pre className="overflow-auto rounded-md bg-zinc-50 p-2 text-xs text-zinc-700 scrollbar-thin">
                    {JSON.stringify(run.triggered_rules, null, 2)}
                  </pre>
                ) : null}
                {run.error_message ? <p className="text-red-700">{run.error_message}</p> : null}
              </div>
            ))}
            {runs.length === 0 ? <p className="px-4 py-5 text-sm text-zinc-500">No check runs yet.</p> : null}
          </div>
        </div>
      </section>
    </div>
  );
}

function SettingsView({
  appSettings,
  profiles,
  alerts,
  onCreated,
  onSettingsSaved,
  onTest
}: {
  appSettings: AppSettings;
  profiles: PushoverProfile[];
  alerts: Alert[];
  onCreated: () => void;
  onSettingsSaved: (settings: AppSettings) => void;
  onTest: (id: number) => void;
}) {
  const [appBaseUrl, setAppBaseUrl] = useState(appSettings.app_base_url);
  const [defaultInterval, setDefaultInterval] = useState(appSettings.default_check_interval_seconds);
  const [defaultJitter, setDefaultJitter] = useState(appSettings.default_jitter_seconds);
  const [defaultRenderWait, setDefaultRenderWait] = useState(appSettings.default_render_wait_ms);
  const [maxConcurrent, setMaxConcurrent] = useState(appSettings.max_concurrent_checks);
  const [name, setName] = useState("");
  const [userKey, setUserKey] = useState("");
  const [appToken, setAppToken] = useState("");
  const [device, setDevice] = useState("");
  const [priority, setPriority] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [settingsError, setSettingsError] = useState<string | null>(null);
  const [settingsSaved, setSettingsSaved] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [savingSettings, setSavingSettings] = useState(false);

  useEffect(() => {
    setAppBaseUrl(appSettings.app_base_url);
    setDefaultInterval(appSettings.default_check_interval_seconds);
    setDefaultJitter(appSettings.default_jitter_seconds);
    setDefaultRenderWait(appSettings.default_render_wait_ms);
    setMaxConcurrent(appSettings.max_concurrent_checks);
  }, [appSettings]);

  async function saveAppSettings(event: FormEvent) {
    event.preventDefault();
    setSavingSettings(true);
    setSettingsError(null);
    setSettingsSaved(null);
    try {
      const nextSettings = await api.updateAppSettings({
        app_base_url: appBaseUrl,
        default_check_interval_seconds: defaultInterval,
        default_jitter_seconds: defaultJitter,
        default_render_wait_ms: defaultRenderWait,
        max_concurrent_checks: maxConcurrent
      });
      onSettingsSaved(nextSettings);
      setSettingsSaved("Settings saved");
    } catch (exc) {
      setSettingsError(exc instanceof Error ? exc.message : "Settings save failed");
    } finally {
      setSavingSettings(false);
    }
  }

  async function createProfile(event: FormEvent) {
    event.preventDefault();
    setSaving(true);
    setError(null);
    try {
      await api.createProfile({
        name,
        user_key: userKey,
        app_token: appToken,
        default_device: device || null,
        default_priority: priority
      });
      setName("");
      setUserKey("");
      setAppToken("");
      setDevice("");
      setPriority(0);
      onCreated();
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : "Profile save failed");
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="grid gap-5 xl:grid-cols-[460px_1fr]">
      <section className="grid content-start gap-5">
        <div className="rounded-md border border-zinc-200 bg-white p-4 shadow-soft">
          <h2 className="text-lg font-semibold text-zinc-950">App Settings</h2>
          <form className="mt-4 grid gap-3" onSubmit={saveAppSettings}>
            <Field label="Public URL" help="The external URL people use to open this app. It is saved in the data volume and is applied on the next backend restart if CORS needs it.">
              <TextInput required type="url" value={appBaseUrl} onChange={(event) => setAppBaseUrl(event.target.value)} />
            </Field>
            <div className="grid grid-cols-2 gap-3">
              <Field label="Default interval" help="The starting check cadence for new monitors. Existing monitors keep their own interval.">
                <TextInput
                  required
                  type="number"
                  min={60}
                  max={86400}
                  step={60}
                  value={defaultInterval}
                  onChange={(event) => setDefaultInterval(Number(event.target.value))}
                />
              </Field>
              <Field label="Default jitter" help="Adds a small random offset to scheduled checks so multiple monitors do not fire at the same instant.">
                <TextInput
                  required
                  type="number"
                  min={0}
                  max={3600}
                  step={5}
                  value={defaultJitter}
                  onChange={(event) => setDefaultJitter(Number(event.target.value))}
                />
              </Field>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <Field label="Default wait" help="Milliseconds to wait after page load before text and screenshots are captured.">
                <TextInput
                  required
                  type="number"
                  min={0}
                  max={15000}
                  step={250}
                  value={defaultRenderWait}
                  onChange={(event) => setDefaultRenderWait(Number(event.target.value))}
                />
              </Field>
              <Field label="Concurrent checks" help="Limits how many browser checks the scheduler can run at the same time.">
                <TextInput
                  required
                  type="number"
                  min={1}
                  max={8}
                  value={maxConcurrent}
                  onChange={(event) => setMaxConcurrent(Number(event.target.value))}
                />
              </Field>
            </div>
            <div className="rounded-md border border-zinc-200 bg-zinc-50 p-3 text-xs text-zinc-600">
              <p className="break-all">Settings file: {appSettings.settings_path}</p>
              <p className="mt-1 break-all">Hash: {appSettings.settings_hash}</p>
              <p className="mt-1">Encryption key: {appSettings.encryption_key_status}</p>
            </div>
            {settingsError ? <p className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-800">{settingsError}</p> : null}
            {settingsSaved ? <p className="rounded-md border border-emerald-200 bg-emerald-50 px-3 py-2 text-sm text-emerald-800">{settingsSaved}</p> : null}
            <Button type="submit" disabled={savingSettings}>
              {savingSettings ? <Loader2 className="h-4 w-4 animate-spin" /> : <Save className="h-4 w-4" />}
              Save settings
            </Button>
          </form>
        </div>

        <div className="rounded-md border border-zinc-200 bg-white p-4 shadow-soft">
          <h2 className="text-lg font-semibold text-zinc-950">Pushover Profile</h2>
          <form className="mt-4 grid gap-3" onSubmit={createProfile}>
            <Field label="Name">
              <TextInput required value={name} onChange={(event) => setName(event.target.value)} placeholder="Personal" />
            </Field>
            <Field label="User key" help="Your Pushover user or group key. It is encrypted before being saved in the volume.">
              <TextInput required value={userKey} onChange={(event) => setUserKey(event.target.value)} />
            </Field>
            <Field label="App token" help="The API token from your Pushover application. It is encrypted before being saved in the volume.">
              <TextInput required value={appToken} onChange={(event) => setAppToken(event.target.value)} />
            </Field>
            <Field label="Device" help="Optional Pushover device name if alerts should go to one device only.">
              <TextInput value={device} onChange={(event) => setDevice(event.target.value)} placeholder="Optional" />
            </Field>
            <Field label="Default priority" help="The Pushover priority used unless a monitor overrides it.">
              <Select value={priority} onChange={(event) => setPriority(Number(event.target.value))}>
                <option value={0}>Normal</option>
                <option value={1}>High</option>
                <option value={-1}>Quiet</option>
              </Select>
            </Field>
            {error ? <p className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-800">{error}</p> : null}
            <Button type="submit" disabled={saving}>
              {saving ? <Loader2 className="h-4 w-4 animate-spin" /> : <Save className="h-4 w-4" />}
              Save profile
            </Button>
          </form>
        </div>
      </section>

      <section className="grid content-start gap-5">
        <div className="rounded-md border border-zinc-200 bg-white shadow-soft">
          <div className="border-b border-zinc-200 px-4 py-3">
            <h2 className="text-base font-semibold text-zinc-950">Profiles</h2>
          </div>
          <div className="divide-y divide-zinc-200">
            {profiles.map((profile) => (
              <div key={profile.id} className="flex flex-wrap items-center justify-between gap-3 px-4 py-3">
                <div>
                  <p className="font-medium text-zinc-950">{profile.name}</p>
                  <p className="text-sm text-zinc-500">Priority {profile.default_priority}</p>
                </div>
                <Button variant="secondary" onClick={() => onTest(profile.id)}>
                  <Bell className="h-4 w-4" />
                  Test
                </Button>
              </div>
            ))}
            {profiles.length === 0 ? <p className="px-4 py-5 text-sm text-zinc-500">No Pushover profiles saved.</p> : null}
          </div>
        </div>

        <div className="rounded-md border border-zinc-200 bg-white shadow-soft">
          <div className="border-b border-zinc-200 px-4 py-3">
            <h2 className="text-base font-semibold text-zinc-950">Alert Log</h2>
          </div>
          <div className="divide-y divide-zinc-200">
            {alerts.map((alert) => (
              <div key={alert.id} className="grid gap-1 px-4 py-3 text-sm">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="font-medium text-zinc-950">{alert.title}</span>
                  <StatusChip status={alert.status} />
                  <span className="text-zinc-500">{timeAgo(alert.created_at)}</span>
                </div>
                <p className="text-zinc-600">{alert.message}</p>
              </div>
            ))}
            {alerts.length === 0 ? <p className="px-4 py-5 text-sm text-zinc-500">No alerts have been recorded.</p> : null}
          </div>
        </div>
      </section>
    </div>
  );
}

export default function App() {
  const [view, setView] = useState<View>("dashboard");
  const [monitors, setMonitors] = useState<Monitor[]>([]);
  const [profiles, setProfiles] = useState<PushoverProfile[]>([]);
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [appSettings, setAppSettings] = useState<AppSettings>(defaultAppSettings);
  const [runs, setRuns] = useState<CheckRun[]>([]);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [busyId, setBusyId] = useState<number | null>(null);
  const [loading, setLoading] = useState(true);
  const [toast, setToast] = useState<string | null>(null);

  const selectedMonitor = monitors.find((monitor) => monitor.id === selectedId) ?? null;

  const refresh = useCallback(async () => {
    const [nextMonitors, nextProfiles, nextAlerts, nextAppSettings] = await Promise.all([
      api.monitors(),
      api.profiles(),
      api.alerts(),
      api.appSettings()
    ]);
    setMonitors(nextMonitors);
    setProfiles(nextProfiles);
    setAlerts(nextAlerts);
    setAppSettings(nextAppSettings);
  }, []);

  const loadRuns = useCallback(async (id: number) => {
    setRuns(await api.runs(id));
  }, []);

  useEffect(() => {
    refresh()
      .catch((exc) => setToast(exc instanceof Error ? exc.message : "Load failed"))
      .finally(() => setLoading(false));
  }, [refresh]);

  useEffect(() => {
    if (selectedId) {
      loadRuns(selectedId).catch((exc) => setToast(exc instanceof Error ? exc.message : "History load failed"));
    }
  }, [selectedId, loadRuns]);

  async function openMonitor(id: number) {
    setSelectedId(id);
    setView("detail");
    await loadRuns(id);
  }

  async function checkNow(id: number) {
    setBusyId(id);
    setToast(null);
    try {
      await api.checkNow(id);
      await refresh();
      await loadRuns(id);
    } catch (exc) {
      setToast(exc instanceof Error ? exc.message : "Check failed");
    } finally {
      setBusyId(null);
    }
  }

  async function pauseResume(monitor: Monitor) {
    try {
      if (monitor.enabled) await api.pause(monitor.id);
      else await api.resume(monitor.id);
      await refresh();
    } catch (exc) {
      setToast(exc instanceof Error ? exc.message : "Update failed");
    }
  }

  async function removeMonitor(id: number) {
    if (!window.confirm("Delete this monitor and its history?")) return;
    try {
      await api.deleteMonitor(id);
      if (selectedId === id) {
        setSelectedId(null);
        setView("dashboard");
      }
      await refresh();
    } catch (exc) {
      setToast(exc instanceof Error ? exc.message : "Delete failed");
    }
  }

  async function rebaseline(id: number) {
    setBusyId(id);
    try {
      await api.rebaseline(id);
      await refresh();
      await loadRuns(id);
    } catch (exc) {
      setToast(exc instanceof Error ? exc.message : "Rebaseline failed");
    } finally {
      setBusyId(null);
    }
  }

  async function updateRenderWait(id: number, renderWaitMs: number) {
    try {
      await api.updateMonitor(id, { render_wait_ms: renderWaitMs });
      await refresh();
      setToast("After-load wait updated. Rebaseline if the old baseline captured a temporary state.");
    } catch (exc) {
      setToast(exc instanceof Error ? exc.message : "Wait update failed");
    }
  }

  async function testProfile(id: number) {
    try {
      const result = await api.testProfile(id, { title: "Change Monitor test", message: "Pushover is connected." });
      setToast(`Test ${result.status}`);
    } catch (exc) {
      setToast(exc instanceof Error ? exc.message : "Test failed");
    }
  }

  const activeCounts = useMemo(() => {
    return {
      enabled: monitors.filter((monitor) => monitor.enabled).length,
      alerts: alerts.length,
      failed: monitors.filter((monitor) => monitor.status === "failed").length
    };
  }, [monitors, alerts]);

  const unconfiguredMonitorCount = useMemo(
    () => monitors.filter((monitor) => monitor.enabled && !monitor.pushover_profile_id).length,
    [monitors]
  );

  const notificationWarning = useMemo(() => {
    if (profiles.length === 0) {
      return "Pushover is not configured. Alerts will be recorded locally but no push message can be sent. Configure it under Settings.";
    }
    if (unconfiguredMonitorCount > 0) {
      return `${unconfiguredMonitorCount} enabled monitor${unconfiguredMonitorCount === 1 ? "" : "s"} without a Pushover profile. Configure this under Settings.`;
    }
    return null;
  }, [profiles.length, unconfiguredMonitorCount]);

  return (
    <div className="min-h-screen bg-[#f7f7f4] text-zinc-900">
      <header className="border-b border-zinc-200 bg-white">
        <div className="mx-auto flex max-w-7xl flex-wrap items-center justify-between gap-4 px-4 py-4 lg:px-6">
          <button className="flex items-center gap-3" onClick={() => setView("dashboard")}>
            <span className="grid h-10 w-10 place-items-center rounded-md bg-teal-700 text-white">
              <Activity className="h-5 w-5" />
            </span>
            <span className="text-left">
              <span className="block text-lg font-semibold text-zinc-950">Change Monitor</span>
              <span className="block text-sm text-zinc-500">Self-hosted availability watcher</span>
            </span>
          </button>

          <nav className="flex flex-wrap items-center gap-2">
            <Button variant={view === "dashboard" ? "primary" : "secondary"} onClick={() => setView("dashboard")}>
              <CheckCircle2 className="h-4 w-4" />
              Dashboard
            </Button>
            <Button variant={view === "new" ? "primary" : "secondary"} onClick={() => setView("new")}>
              <Plus className="h-4 w-4" />
              New
            </Button>
            <Button variant={view === "settings" ? "primary" : "secondary"} onClick={() => setView("settings")}>
              <Settings className="h-4 w-4" />
              Settings
            </Button>
            {profiles.length > 0 ? (
              <Button variant="secondary" onClick={() => testProfile(profiles[0].id)}>
                <Bell className="h-4 w-4" />
                Test
              </Button>
            ) : null}
          </nav>
        </div>
        {notificationWarning ? (
          <div className="mx-auto flex max-w-7xl flex-wrap items-center justify-between gap-3 px-4 pb-4 lg:px-6">
            <button
              className="flex min-w-0 items-start gap-2 rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-left text-sm text-amber-950"
              onClick={() => setView("settings")}
            >
              <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
              <span className="min-w-0 break-words">{notificationWarning}</span>
            </button>
            {profiles.length > 0 ? (
              <Button variant="secondary" onClick={() => testProfile(profiles[0].id)}>
                <Bell className="h-4 w-4" />
                Test Pushover
              </Button>
            ) : null}
          </div>
        ) : null}
      </header>

      <main className="mx-auto grid max-w-7xl gap-5 px-4 py-5 lg:px-6">
        <section className="grid gap-3 sm:grid-cols-3">
          <div className="rounded-md border border-zinc-200 bg-white p-4 shadow-soft">
            <p className="text-sm text-zinc-500">Enabled</p>
            <p className="mt-1 text-2xl font-semibold text-zinc-950">{activeCounts.enabled}</p>
          </div>
          <div className="rounded-md border border-zinc-200 bg-white p-4 shadow-soft">
            <p className="text-sm text-zinc-500">Alerts</p>
            <p className="mt-1 text-2xl font-semibold text-zinc-950">{activeCounts.alerts}</p>
          </div>
          <div className="rounded-md border border-zinc-200 bg-white p-4 shadow-soft">
            <p className="text-sm text-zinc-500">Failed</p>
            <p className="mt-1 text-2xl font-semibold text-zinc-950">{activeCounts.failed}</p>
          </div>
        </section>

        {toast ? (
          <div className="flex items-start justify-between gap-3 rounded-md border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-950">
            <span>{toast}</span>
            <button className="font-semibold" onClick={() => setToast(null)}>
              Dismiss
            </button>
          </div>
        ) : null}

        {loading ? (
          <section className="grid min-h-80 place-items-center rounded-md border border-zinc-200 bg-white">
            <Loader2 className="h-8 w-8 animate-spin text-teal-700" />
          </section>
        ) : null}

        {!loading && view === "dashboard" ? (
          <Dashboard
            monitors={monitors}
            alerts={alerts}
            busyId={busyId}
            onCreate={() => setView("new")}
            onOpen={openMonitor}
            onRefresh={() => refresh().catch((exc) => setToast(exc instanceof Error ? exc.message : "Refresh failed"))}
            onCheck={checkNow}
            onPauseResume={pauseResume}
            onDelete={removeMonitor}
          />
        ) : null}

        {!loading && view === "new" ? (
          <NewMonitorWizard
            profiles={profiles}
            appSettings={appSettings}
            onCancel={() => setView("dashboard")}
            onCreated={async (monitor) => {
              setSelectedId(monitor.id);
              await refresh();
              await loadRuns(monitor.id);
              setView("detail");
            }}
          />
        ) : null}

        {!loading && view === "detail" && selectedMonitor ? (
          <MonitorDetail
            monitor={selectedMonitor}
            runs={runs}
            busyId={busyId}
            onBack={() => setView("dashboard")}
            onRefresh={() => refresh().catch((exc) => setToast(exc instanceof Error ? exc.message : "Refresh failed"))}
            onCheck={checkNow}
            onPauseResume={pauseResume}
            onRebaseline={rebaseline}
            onUpdateWait={updateRenderWait}
          />
        ) : null}

        {!loading && view === "settings" ? (
          <SettingsView
            appSettings={appSettings}
            profiles={profiles}
            alerts={alerts}
            onCreated={refresh}
            onSettingsSaved={setAppSettings}
            onTest={testProfile}
          />
        ) : null}
      </main>
    </div>
  );
}
