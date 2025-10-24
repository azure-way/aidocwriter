"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { GlassCard } from "@/components/GlassCard";
import { GradientTitle } from "@/components/GradientTitle";
import {
  createJob,
  fetchIntakeQuestions,
  fetchJobStatus,
  fetchJobTimeline,
  downloadArtifact,
  getArtifactUrl,
  resumeJob,
} from "@/lib/api";

interface IntakeQuestion {
  id: string;
  q: string;
  sample: string;
}

interface StatusPayload {
  job_id: string;
  stage: string;
  artifact?: string;
  message?: string;
  cycle?: number;
  details?: Record<string, unknown> | null;
}

interface TimelineEvent {
  stage: string;
  message?: string;
  artifact?: string;
  ts?: number | string | null;
  cycle?: number | null;
  details?: Record<string, unknown> | null;
  pending?: boolean;
  status?: "pending" | "active" | "complete";
  displayStage?: string;
  sourceStage?: string;
}

type JobDashboardProps = {
  initialJobId?: string;
};

const POLL_INTERVAL_MS = 5000;
const SUMMARY_STAGE_ORDER = [
  "ENQUEUED",
  "INTAKE_READY",
  "INTAKE_RESUME",
  "PLAN",
  "WRITE",
  "REVIEW",
  "VERIFY",
  "REWRITE",
  "FINALIZE",
];
const STAGE_SUFFIX_PATTERN = /_(DONE|START|QUEUED|FAILED|ERROR)$/;

type StagePhase = "queued" | "in_progress" | "complete" | "failed" | "unknown";

const CYCLE_AWARE_STAGES = ["REVIEW", "VERIFY", "REWRITE"] as const;
const CYCLE_AWARE_STAGE_SET = new Set(CYCLE_AWARE_STAGES);

const cycleStatusStyles: Record<StagePhase, { badge: string; container: string }> = {
  complete: {
    badge: "border border-emerald-200 bg-emerald-50 text-emerald-700",
    container: "border border-emerald-200 bg-emerald-50/50",
  },
  in_progress: {
    badge: "border border-indigo-200 bg-indigo-50 text-indigo-700",
    container: "border border-indigo-200 bg-white",
  },
  queued: {
    badge: "border border-slate-200 bg-white text-slate-600",
    container: "border border-slate-200 bg-white",
  },
  failed: {
    badge: "border border-rose-200 bg-rose-50 text-rose-700",
    container: "border border-rose-200 bg-rose-50/60",
  },
  unknown: {
    badge: "border border-slate-200 bg-white text-slate-600",
    container: "border border-slate-200 bg-white",
  },
};

const normalizeStageName = (value: string): string => {
  const base = value.replace(STAGE_SUFFIX_PATTERN, "");
  if (base === "INTAKE_RESUMED") {
    return "INTAKE_RESUME";
  }
  return base;
};

const determineEventPhase = (event: TimelineEvent | undefined): StagePhase => {
  if (!event || typeof event.stage !== "string") {
    return "unknown";
  }
  if (event.pending) {
    return "queued";
  }
  const stage = event.stage;
  if (/_FAILED$/u.test(stage) || /_ERROR$/u.test(stage)) {
    return "failed";
  }
  if (/_DONE$/u.test(stage)) {
    return "complete";
  }
  if (/_START$/u.test(stage)) {
    return "in_progress";
  }
  if (/_QUEUED$/u.test(stage)) {
    return "queued";
  }
  return "complete";
};

const stagePhaseLabel = (phase: StagePhase): string => {
  switch (phase) {
    case "queued":
      return "Queued";
    case "in_progress":
      return "In Progress";
    case "complete":
      return "Completed";
    case "failed":
      return "Failed";
    default:
      return "Update";
  }
};

const cycleStatusLabel = (phase: StagePhase, stageLabel: string): string => {
  switch (phase) {
    case "queued":
      return `${stageLabel} not started`;
    case "in_progress":
      return `${stageLabel} running`;
    case "complete":
      return `${stageLabel} complete`;
    case "failed":
      return `${stageLabel} requires attention`;
    default:
      return `${stageLabel} pending`;
  }
};

export function JobDashboard({ initialJobId }: JobDashboardProps) {
  const primaryButtonClass = "btn-primary";
  const inputClass = "input-glass";
  const [step, setStep] = useState<1 | 2 | 3>(initialJobId ? 3 : 1);
  const [title, setTitle] = useState("");
  const [audience, setAudience] = useState("");
  const [cycles, setCycles] = useState(2);
  const [questions, setQuestions] = useState<IntakeQuestion[]>([]);
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const [jobId, setJobId] = useState<string | null>(initialJobId ?? null);
  const [status, setStatus] = useState<StatusPayload | null>(null);
  const [timeline, setTimeline] = useState<TimelineEvent[]>([]);
  const [timelineMeta, setTimelineMeta] = useState<Record<string, unknown>>({});
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [artifactNotice, setArtifactNotice] = useState<string | null>(null);
  const noticeTimeoutRef = useRef<NodeJS.Timeout | null>(null);

  const clearNotice = useCallback(() => {
    if (noticeTimeoutRef.current) {
      clearTimeout(noticeTimeoutRef.current);
      noticeTimeoutRef.current = null;
    }
    setArtifactNotice(null);
  }, []);

  const showNotice = useCallback(
    (msg: string) => {
      clearNotice();
      setArtifactNotice(msg);
      noticeTimeoutRef.current = setTimeout(() => {
        setArtifactNotice(null);
        noticeTimeoutRef.current = null;
      }, 2500);
    },
    [clearNotice]
  );

  useEffect(() => {
    if (!initialJobId) {
      return;
    }
    setStep(3);
    setTimeline([]);
    setTimelineMeta({});
    clearNotice();
    setJobId((prev) => (prev === initialJobId ? prev : initialJobId));
  }, [initialJobId, clearNotice]);

  useEffect(() => {
    if (!jobId) return;
    const controller = new AbortController();
    const currentJobId = jobId;

    async function poll() {
      try {
        const payload = await fetchJobStatus(currentJobId);
        setStatus(payload);
        const history = await fetchJobTimeline(currentJobId);
        if (history?.events) {
          setTimeline(history.events);
        }
        setTimelineMeta(history?.meta ?? {});
      } catch (e) {
        console.error(e);
      }
    }

    poll();
    const interval = setInterval(poll, POLL_INTERVAL_MS);
    return () => {
      clearInterval(interval);
      controller.abort();
      clearNotice();
    };
  }, [jobId, clearNotice]);

  const handleGenerateQuestions = useCallback(async () => {
    setError(null);
    setLoading(true);
    try {
      if (!title.trim() || !audience.trim()) {
        throw new Error("Provide both title and audience.");
      }
      const data = await fetchIntakeQuestions(title.trim());
      const incomingQuestions = (data.questions ?? []) as IntakeQuestion[];
      setQuestions(incomingQuestions);
      const defaults: Record<string, string> = {};
      incomingQuestions.forEach((q) => {
        defaults[q.id] = q.sample ?? "";
      });
      setAnswers(defaults);
      setStep(2);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to generate questions");
    } finally {
      setLoading(false);
    }
  }, [title, audience]);

  const handleSubmitAnswers = useCallback(async () => {
    setError(null);
    setLoading(true);
    try {
      const trimmedAnswers = Object.fromEntries(
        Object.entries(answers).map(([key, value]) => [key, value.trim()])
      );
      const response = await createJob({
        title: title.trim(),
        audience: audience.trim(),
        cycles,
      });
      const id = response.job_id as string;
      await resumeJob(id, trimmedAnswers);
      setJobId(id);
      setStep(3);
      setTimeline([]);
      setTimelineMeta({});
      clearNotice();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to submit answers");
    } finally {
      setLoading(false);
    }
  }, [answers, title, audience, cycles, clearNotice]);

  const disableSubmit = useMemo(() => {
    return Object.values(answers).some((ans) => !ans.trim());
  }, [answers]);

  const sortedTimeline = useMemo(() => {
    const copy = [...timeline];
    return copy.sort((a, b) => {
      const ta = Number(a.ts ?? 0);
      const tb = Number(b.ts ?? 0);
      return ta - tb;
    });
  }, [timeline]);

  const formatStage = useCallback((stage: string) => {
    return stage.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
  }, []);

  const stageOrder = useMemo(() => {
    const order = timelineMeta?.stage_order;
    if (Array.isArray(order) && order.every((item) => typeof item === "string")) {
      return order as string[];
    }
    return SUMMARY_STAGE_ORDER;
  }, [timelineMeta]);

  const groupedTimeline = useMemo(() => {
    const cycleMap = new Map<number, TimelineEvent[]>();
    sortedTimeline.forEach((event) => {
      if (typeof event.cycle === "number" && event.cycle > 0) {
        const list = cycleMap.get(event.cycle) ?? [];
        list.push(event);
        cycleMap.set(event.cycle, list);
      }
    });
    const expectedCyclesMeta = (() => {
      const raw = timelineMeta?.expected_cycles;
      if (typeof raw === "number") {
        return Math.max(1, Math.floor(raw));
      }
      if (typeof raw === "string") {
        const parsed = Number(raw);
        if (!Number.isNaN(parsed)) {
          return Math.max(1, Math.floor(parsed));
        }
      }
      return undefined;
    })();
    const maxCycleSeen = cycleMap.size
      ? Math.max(...Array.from(cycleMap.keys()))
      : 0;
    const expected = expectedCyclesMeta ?? Math.max(maxCycleSeen, 1);
    const cyclesEntries = Array.from({ length: expected }, (_, idx) => {
      const cycle = idx + 1;
      const events = (cycleMap.get(cycle) ?? []).sort((a, b) => {
        const ta = Number(a.ts ?? 0);
        const tb = Number(b.ts ?? 0);
        return ta - tb;
      });
      if (events.length === 0) {
        return {
          cycle,
          events: [
            {
              stage: "REVIEW_DONE",
              message: `Review cycle ${cycle} pending`,
              cycle,
              pending: true,
            } as TimelineEvent,
          ],
        };
      }
      return { cycle, events };
    });
    const cyclesData = Array.from(cycleMap.entries())
      .sort((a, b) => a[0] - b[0])
      .map(([cycle, events]) => ({
        cycle,
        events: events.sort((a, b) => {
          const ta = Number(a.ts ?? 0);
          const tb = Number(b.ts ?? 0);
          return ta - tb;
        }),
      }));
    const mergedCycles = cyclesEntries.map((entry) => {
      const existing = cyclesData.find((c) => c.cycle === entry.cycle);
      return existing ?? entry;
    });
    return { cycles: mergedCycles };
  }, [sortedTimeline, timelineMeta]);

  const [expandedCycles, setExpandedCycles] = useState<Record<number, boolean>>({});

  useEffect(() => {
    setExpandedCycles((prev) => {
      const next = { ...prev };
      let changed = false;
      const lastCycle = groupedTimeline.cycles[groupedTimeline.cycles.length - 1]?.cycle;
      groupedTimeline.cycles.forEach(({ cycle }) => {
        if (!(cycle in next)) {
          next[cycle] = cycle === lastCycle;
          changed = true;
        }
      });
      return changed ? next : prev;
    });
  }, [groupedTimeline.cycles]);

  const summaryEvents = useMemo(() => {
    const stageEventsByBase = new Map<string, TimelineEvent[]>();
    sortedTimeline.forEach((event) => {
      if (!event.stage) {
        return;
      }
      const base = normalizeStageName(event.stage);
      if (event.cycle != null && !CYCLE_AWARE_STAGE_SET.has(base)) {
        return;
      }
      const existing = stageEventsByBase.get(base) ?? [];
      existing.push(event);
      stageEventsByBase.set(base, existing);
    });

    return stageOrder.map((stage) => {
      const base = normalizeStageName(stage);
      const related = stageEventsByBase.get(base)
        ? [...stageEventsByBase.get(base)!].sort((a, b) => {
            const ta = Number(a.ts ?? 0);
            const tb = Number(b.ts ?? 0);
            return ta - tb;
          })
        : [];

      const completionEvent = [...related].reverse().find((entry) => determineEventPhase(entry) === "complete");
      if (completionEvent) {
        return {
          ...completionEvent,
          stage,
          pending: false,
          status: "complete" as const,
          displayStage: formatStage(base),
          sourceStage: completionEvent.stage,
        };
      }

      const inProgressEvent = [...related].reverse().find((entry) => determineEventPhase(entry) === "in_progress");
      if (inProgressEvent) {
        return {
          ...inProgressEvent,
          stage,
          pending: false,
          status: "active" as const,
          displayStage: formatStage(base),
          sourceStage: inProgressEvent.stage,
        };
      }

      const queuedEvent = [...related].reverse().find((entry) => determineEventPhase(entry) === "queued");
      if (queuedEvent) {
        return {
          ...queuedEvent,
          stage,
          pending: false,
          status: "active" as const,
          displayStage: formatStage(base),
          sourceStage: queuedEvent.stage,
        };
      }

      return {
        stage,
        message: `${formatStage(stage)} pending`,
        pending: true,
        status: "pending" as const,
        displayStage: formatStage(base),
      } as TimelineEvent;
    });
  }, [sortedTimeline, stageOrder, formatStage]);

  const formatTimestamp = useCallback((ts?: number | string | null) => {
    if (!ts && ts !== 0) return "—";
    const value = Number(ts);
    if (Number.isNaN(value)) return "—";
    return new Date(value * 1000).toLocaleString();
  }, []);

  const formatDuration = useCallback((seconds?: number | null) => {
    if (seconds == null) return "n/a";
    const total = Math.max(0, Math.round(seconds));
    const mins = Math.floor(total / 60);
    const secs = total % 60;
    if (mins && secs) return `${mins} min ${secs} sec`;
    if (mins) return `${mins} min`;
    return `${secs} sec`;
  }, []);

  const getMetadataEntries = useCallback(
    (event: TimelineEvent): Array<{ label: string; value: string }> => {
      const entries: Array<{ label: string; value: string }> = [];
      const seen = new Set<string>();
      const parsedRaw =
        event.details && typeof event.details === "object"
          ? (event.details as Record<string, unknown>)["parsed_message"]
          : null;
      const parsed =
        parsedRaw && typeof parsedRaw === "object"
          ? (parsedRaw as Record<string, unknown>)
          : null;

      const addEntry = (label: string, value: unknown) => {
        if (value == null) return;
        const text = String(value).trim();
        if (!text || text.toLowerCase() === "n/a" || seen.has(label)) return;
        entries.push({ label, value: text });
        seen.add(label);
      };

      const stageLabel =
        (parsed?.stage_label && typeof parsed.stage_label === "string" && parsed.stage_label.trim()) ||
        event.displayStage ||
        formatStage(event.stage);
      addEntry("Stage", stageLabel);

      const documentValue =
        (parsed?.document && typeof parsed.document === "string" && parsed.document.trim()) ||
        (typeof event.artifact === "string" && event.artifact.trim()
          ? event.artifact
          : typeof event.details?.artifact === "string"
          ? event.details.artifact
          : null);
      addEntry("Document", documentValue);

      const durationText =
        (parsed?.duration && typeof parsed.duration === "string" && parsed.duration.trim()) ||
        (typeof event.details?.duration_s === "number" ? formatDuration(event.details.duration_s) : null);
      addEntry("Stage Time", durationText);

      const tokensDisplay =
        (typeof parsed?.tokens === "number" && parsed.tokens > 0 && parsed.tokens.toLocaleString()) ||
        (parsed?.tokens_display && typeof parsed.tokens_display === "string" && parsed.tokens_display.trim()) ||
        (typeof event.details?.tokens === "number" && event.details.tokens > 0
          ? event.details.tokens.toLocaleString()
          : null);
      addEntry("Tokens", tokensDisplay);

      const modelValue =
        (parsed?.model && typeof parsed.model === "string" && parsed.model.trim()) ||
        (typeof event.details?.model === "string" ? event.details.model : null);
      addEntry("Model", modelValue);

      const notesValue =
        (parsed?.notes && typeof parsed.notes === "string" && parsed.notes.trim()) ||
        (typeof event.details?.notes === "string" ? event.details.notes : null);
      addEntry("Notes", notesValue);

      return entries;
    },
    [formatDuration, formatStage]
  );

  const openArtifact = useCallback((path: string) => {
    const url = getArtifactUrl(path);
    window.open(url, "_blank", "noopener,noreferrer");
  }, []);

  const copyArtifactLink = useCallback(
    async (path: string) => {
      try {
        const url = getArtifactUrl(path);
        await navigator.clipboard.writeText(url);
        showNotice("Artifact link copied to clipboard");
      } catch (err) {
        console.error(err);
        setError("Failed to copy artifact link");
      }
    },
    [showNotice]
  );

  const downloadArtifactFile = useCallback(
    async (path: string) => {
      try {
        const blob = await downloadArtifact(path);
        const fileName = path.split("/").pop() ?? "artifact";
        const url = URL.createObjectURL(blob);
        const link = document.createElement("a");
        link.href = url;
        link.download = fileName;
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
        URL.revokeObjectURL(url);
        showNotice(`Download started for ${fileName}`);
      } catch (err) {
        console.error(err);
        setError("Failed to download artifact");
      }
    },
    [showNotice]
  );

  const renderArtifactActions = useCallback(
    (path: string, size: "sm" | "md" = "md") => {
      const fileName = path.split("/").pop() ?? path;
      const chipClass =
        "rounded-full bg-white/70 px-3 py-1 text-xs font-semibold text-slate-600 shadow-sm";
      const buttonClass =
        "rounded-full bg-white/80 px-3 py-1 text-xs font-medium text-slate-600 shadow hover:bg-white";
      return (
        <div className={`flex flex-wrap items-center gap-2 ${size === "sm" ? "mt-2 pl-2" : "mt-3"}`}>
          <span className={chipClass}>{fileName}</span>
          <div className="flex flex-wrap gap-2">
            <button
              type="button"
              className={buttonClass}
              onClick={() => openArtifact(path)}
            >
              Open
            </button>
            <button
              type="button"
              className={buttonClass}
              onClick={() => copyArtifactLink(path)}
            >
              Copy link
            </button>
            <button
              type="button"
              className={buttonClass}
              onClick={() => downloadArtifactFile(path)}
            >
              Download
            </button>
          </div>
        </div>
      );
    },
    [copyArtifactLink, downloadArtifactFile, openArtifact]
  );

  useEffect(() => {
    return () => {
      clearNotice();
    };
  }, [clearNotice]);

  const artifactActions = status?.artifact ? renderArtifactActions(status.artifact) : null;
  const statusMetadata = useMemo(() => {
    if (!status) return [];
    const pseudoEvent: TimelineEvent = {
      stage: status.stage,
      message: status.message,
      artifact: status.artifact,
      details: status.details,
    };
    return getMetadataEntries(pseudoEvent);
  }, [status, getMetadataEntries]);

  type StageCycleDetail = {
    cycle: number;
    status: StagePhase;
    metadataEntries: Array<{ label: string; value: string }>;
    timeline: Array<{ key: string; label: string; ts?: number | string | null }>;
    completionTs?: number | string | null;
    lastUpdateTs?: number | string | null;
  };

  const cycleDetailsByStage = useMemo<Map<string, StageCycleDetail[]>>(() => {
    const result = new Map<string, StageCycleDetail[]>();
    CYCLE_AWARE_STAGES.forEach((stageBase) => {
      const stageDetails: StageCycleDetail[] = groupedTimeline.cycles.map(({ cycle, events }) => {
        const sortedEvents = [...events].sort((a, b) => {
          const ta = Number(a.ts ?? 0);
          const tb = Number(b.ts ?? 0);
          return ta - tb;
        });
        const stageEvents = sortedEvents.filter(
          (ev) => normalizeStageName(ev.stage ?? "") === stageBase
        );
        const completionEvent = [...stageEvents]
          .reverse()
          .find((ev) => determineEventPhase(ev) === "complete");
        const failedEvent = [...stageEvents]
          .reverse()
          .find((ev) => determineEventPhase(ev) === "failed");
        const inProgressEvent = [...stageEvents]
          .reverse()
          .find((ev) => determineEventPhase(ev) === "in_progress");
        const queuedEvent = [...stageEvents]
          .reverse()
          .find((ev) => determineEventPhase(ev) === "queued");

        let status: StagePhase = "queued";
        if (failedEvent) {
          status = "failed";
        } else if (completionEvent) {
          status = "complete";
        } else if (inProgressEvent) {
          status = "in_progress";
        } else if (queuedEvent) {
          status = "queued";
        } else if (stageEvents.length === 0) {
          status = "queued";
        } else {
          status = "unknown";
        }

        const metadataSource =
          completionEvent ??
          inProgressEvent ??
          stageEvents[stageEvents.length - 1] ??
          null;
        const metadataEntries = metadataSource ? getMetadataEntries(metadataSource) : [];

        let timeline = stageEvents.map((ev, idx) => ({
          key: `${stageBase}-${cycle}-${idx}-${ev.stage}`,
          label: stagePhaseLabel(determineEventPhase(ev)),
          ts: ev.ts,
        }));
        if (timeline.length === 0) {
          timeline = [
            {
              key: `${stageBase}-${cycle}-not-started`,
              label: "Not started",
              ts: undefined,
            },
          ];
        }

        const completionTs = completionEvent?.ts ?? null;
        const lastUpdateTs =
          metadataSource?.ts ??
          (stageEvents.length
            ? stageEvents[stageEvents.length - 1]?.ts
            : sortedEvents.length
            ? sortedEvents[sortedEvents.length - 1]?.ts
            : null);

        return {
          cycle,
          status,
          metadataEntries,
          timeline,
          completionTs,
          lastUpdateTs,
        };
      });
      result.set(stageBase, stageDetails);
    });
    return result;
  }, [groupedTimeline.cycles, getMetadataEntries]);

  const renderSummaryStage = useCallback(
    (event: TimelineEvent, index: number) => {
      const status = event.status ?? (event.pending ? "pending" : "complete");
      const completed = status === "complete";
      const active = status === "active";
      const label = event.displayStage ?? formatStage(event.stage);
      const statusLabel = completed ? "Completed" : active ? "Running" : "Not started";
      let secondaryText = statusLabel;
      if ((completed || active) && event.ts != null) {
        secondaryText = `${statusLabel} • ${formatTimestamp(event.ts)}`;
      }
      const badgeClass = completed
        ? "bg-indigo-500 text-white"
        : active
        ? "border border-indigo-300 bg-indigo-50 text-indigo-600"
        : "bg-white border border-slate-200 text-slate-400";
      const stageBase = normalizeStageName(event.stage);
      const stageCycleDetails = cycleDetailsByStage.get(stageBase) ?? [];
      const showCycles = stageCycleDetails.length > 0;
      const metadataEntries = getMetadataEntries(event);
      const stageCycleLabel = formatStage(stageBase);
      const completedCycles = showCycles
        ? stageCycleDetails.filter((detail) => detail.status === "complete").length
        : 0;
      const activeCycleDetail = showCycles
        ? stageCycleDetails.find((detail) => detail.status === "in_progress")
        : undefined;
      const failedCycleDetail = showCycles
        ? stageCycleDetails.find((detail) => detail.status === "failed")
        : undefined;
      const totalCycles = showCycles ? stageCycleDetails.length : 0;
      return (
        <div
          key={`summary-${event.stage}-${index}`}
          className="flex items-start gap-4 rounded-2xl bg-white/70 px-4 py-3 shadow-sm"
        >
          <span
            className={`flex h-8 w-8 items-center justify-center rounded-full text-sm font-semibold ${badgeClass}`}
          >
            {index + 1}
          </span>
          <div className="flex-1 space-y-3">
            <div>
              <p className="text-sm font-semibold text-slate-700">
                {label}
              </p>
              <p className="text-xs text-slate-500">{secondaryText}</p>
              {active && event.sourceStage && event.sourceStage !== event.stage ? (
                <p className="mt-1 text-xs text-slate-400">
                  {formatStage(event.sourceStage)}
                </p>
              ) : null}
              {metadataEntries.length > 0 ? (
                <div className="mt-3 grid gap-x-6 gap-y-3 text-xs text-slate-500 sm:grid-cols-2">
                  {metadataEntries.map(({ label, value }) => (
                    <div key={`summary-${event.stage}-${label}`} className="flex flex-col">
                      <span className="font-semibold text-slate-600">{label}</span>
                      <span className="break-words">{value}</span>
                    </div>
                  ))}
                </div>
              ) : event.message && (completed || active) ? (
                <p className="mt-1 text-xs text-slate-500">{event.message}</p>
              ) : null}
              {event.artifact && (completed || active)
                ? renderArtifactActions(event.artifact, "sm")
                : null}
              {showCycles && totalCycles > 0 ? (
                <div className="mt-3 flex flex-wrap gap-2 text-xs">
                  <span className="rounded-full border border-slate-200 bg-white px-3 py-1 text-slate-600">
                    {completedCycles}/{totalCycles} cycles complete
                  </span>
                  {activeCycleDetail ? (
                    <span className="rounded-full border border-indigo-200 bg-indigo-50 px-3 py-1 text-indigo-600">
                      Running cycle: {activeCycleDetail.cycle}
                    </span>
                  ) : null}
                  {failedCycleDetail ? (
                    <span className="rounded-full border border-rose-200 bg-rose-50 px-3 py-1 text-rose-700">
                      Attention: Cycle {failedCycleDetail.cycle}
                    </span>
                  ) : null}
                </div>
              ) : null}
            </div>
            {showCycles ? (
              <div className="space-y-3">
                {stageCycleDetails.map((detail) => {
                  const statusStyle = cycleStatusStyles[detail.status] ?? cycleStatusStyles.unknown;
                  const statusChipLabel = cycleStatusLabel(detail.status, stageCycleLabel);
                  const isExpanded = expandedCycles[detail.cycle] ?? false;
                  return (
                    <div
                      key={`cycle-${detail.cycle}`}
                      className={`rounded-2xl px-4 py-3 shadow-inner shadow-white/30 transition ${statusStyle.container}`}
                    >
                      <button
                        type="button"
                        className="flex w-full items-center justify-between text-left"
                        onClick={() =>
                          setExpandedCycles((prev) => ({
                            ...prev,
                            [detail.cycle]: !isExpanded,
                          }))
                        }
                      >
                        <div>
                          <p className="text-xs font-semibold uppercase tracking-[0.3em] text-slate-400">
                            {stageCycleLabel} cycle {detail.cycle}
                          </p>
                          {detail.completionTs ? (
                            <p className="text-xs text-slate-500">
                              Completed {formatTimestamp(detail.completionTs)}
                            </p>
                          ) : detail.lastUpdateTs ? (
                            <p className="text-xs text-slate-500">
                              Last update {formatTimestamp(detail.lastUpdateTs)}
                            </p>
                          ) : null}
                        </div>
                        <span
                          className={`rounded-full px-3 py-1 text-xs font-medium ${statusStyle.badge}`}
                        >
                          {statusChipLabel}
                        </span>
                        <span className="text-lg text-slate-500">
                          {isExpanded ? "−" : "+"}
                        </span>
                      </button>
                      {isExpanded && (
                        <div className="mt-3 space-y-3 border-t border-slate-100 pt-3">
                          {detail.timeline.length > 0 ? (
                            <ol className="space-y-2 text-xs text-slate-500">
                              {detail.timeline.map((item) => (
                                <li
                                  key={item.key}
                                  className="flex items-center justify-between gap-3"
                                >
                                  <span className="font-semibold text-slate-600">
                                    {item.label}
                                  </span>
                                  <span>{item.ts ? formatTimestamp(item.ts) : "—"}</span>
                                </li>
                              ))}
                            </ol>
                          ) : null}
                          {detail.metadataEntries.length > 0 ? (
                            <div className="grid gap-x-6 gap-y-3 text-xs text-slate-500 sm:grid-cols-2">
                              {detail.metadataEntries.map(({ label, value }) => (
                                <div
                                  key={`cycle-${detail.cycle}-${label}`}
                                  className="flex flex-col"
                                >
                                  <span className="font-semibold text-slate-600">{label}</span>
                                  <span className="break-words">{value}</span>
                                </div>
                              ))}
                            </div>
                          ) : (
                            <p className="text-xs text-slate-500">No updates yet.</p>
                          )}
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            ) : null}
          </div>
        </div>
      );
    },
    [
      expandedCycles,
      formatStage,
      formatTimestamp,
      getMetadataEntries,
      renderArtifactActions,
      cycleDetailsByStage,
    ]
  );

  return (
    <section id="intake" className="space-y-12 pb-10">
      {error ? (
        <GlassCard className="border-red-400/40 bg-red-500/10 text-red-100">
          <p className="text-sm">{error}</p>
        </GlassCard>
      ) : null}

      {step === 1 && (
        <GlassCard className="space-y-7 rounded-[32px] bg-gradient-to-br from-white/95 via-indigo-50/95 to-sky-100/90 px-10 py-10 text-slate-700">
          <GradientTitle
            title="Document details"
            subtitle="Tell us what you need so we can craft a tailored intake questionnaire."
            className="bg-gradient-to-r from-purple-400 via-pink-300 to-sky-400 text-transparent"
            subtitleClassName="text-slate-500"
          />
          <div className="grid gap-8 md:grid-cols-2">
            <div className="space-y-3">
              <label className="text-xs font-semibold uppercase tracking-[0.4em] text-slate-400">
                Working title
              </label>
              <input
                className={inputClass}
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                placeholder="e.g., Asynchronous Integration Patterns"
              />
            </div>
            <div className="space-y-3">
              <label className="text-xs font-semibold uppercase tracking-[0.4em] text-slate-400">
                Primary audience
              </label>
              <input
                className={inputClass}
                value={audience}
                onChange={(e) => setAudience(e.target.value)}
                placeholder="e.g., Enterprise Integration Architects"
              />
            </div>
          </div>
          <div className="flex flex-col gap-6 md:flex-row md:items-end md:justify-between">
            <div className="space-y-3">
              <label className="text-xs font-semibold uppercase tracking-[0.4em] text-slate-400">
                Review cycles
              </label>
              <input
                type="number"
                min={1}
                max={5}
                className={`${inputClass} max-w-[120px]`}
                value={cycles}
                onChange={(e) => setCycles(Number(e.target.value))}
              />
            </div>
            <button
              className={`${primaryButtonClass} w-full md:w-auto`}
              disabled={loading || !title || !audience}
              onClick={handleGenerateQuestions}
            >
              {loading ? "Generating questions..." : "Generate intake questionnaire"}
            </button>
          </div>
        </GlassCard>
      )}

      {step === 2 && (
        <GlassCard className="space-y-8 rounded-[32px] bg-gradient-to-br from-white/95 via-indigo-50/95 to-sky-100/90 px-10 py-10 text-slate-700">
          <GradientTitle
            title="Answer intake questions"
            subtitle="Provide as much context as possible. These answers guide planning and writing."
            className="bg-gradient-to-r from-purple-400 via-pink-300 to-sky-400 text-transparent"
            subtitleClassName="text-slate-500"
          />
          <div className="space-y-6">
            {questions.map((question) => (
              <div key={question.id} className="space-y-2">
                <label className="text-xs font-semibold uppercase tracking-[0.4em] text-slate-400">
                  {question.q}
                </label>
                <textarea
                  className="textarea-glass"
                  value={answers[question.id] ?? ""}
                  onChange={(e) => setAnswers((prev) => ({ ...prev, [question.id]: e.target.value }))}
                  placeholder="Type your response..."
                />
              </div>
            ))}
          </div>
          <div className="flex flex-col gap-4 md:flex-row md:justify-between">
            <button className={`${primaryButtonClass} w-full md:w-auto`} onClick={() => setStep(1)}>
              Back
            </button>
            <button
              className={`${primaryButtonClass} w-full md:w-auto`}
              disabled={loading || disableSubmit}
              onClick={handleSubmitAnswers}
            >
              {loading ? "Submitting..." : "Submit answers & start generation"}
            </button>
          </div>
        </GlassCard>
      )}

      {step === 3 && (
        <div className="space-y-6">
          <GlassCard className="space-y-6 rounded-[32px] bg-gradient-to-br from-white/95 via-indigo-50/95 to-sky-100/90 px-10 py-10 text-slate-700">
            <GradientTitle
              title="Job submitted"
              subtitle="We’re orchestrating the planner, writer, and reviewer agents. The checkpoints below update automatically."
              className="bg-gradient-to-r from-purple-400 via-pink-300 to-sky-400 text-transparent"
              subtitleClassName="text-slate-500"
            />
            <div className="grid gap-6 md:grid-cols-2">
              <div className="rounded-3xl border border-white/70 bg-white px-6 py-5 shadow-lg shadow-slate-200/50">
                <p className="text-xs uppercase tracking-[0.38em] text-slate-400">Job ID</p>
                <p className="mt-3 break-all font-mono text-sm text-slate-700">{jobId}</p>
              </div>
              <div className="rounded-3xl border border-white/70 bg-white px-6 py-5 shadow-lg shadow-slate-200/50">
                <p className="text-xs uppercase tracking-[0.38em] text-slate-400">Current stage</p>
                <p className="mt-3 text-xl font-semibold text-slate-800">
                  {status?.stage ?? "Pending"}
                </p>
                {status?.cycle && (
                  <p className="text-sm text-slate-600">Cycle {status.cycle}</p>
                )}
              </div>
            </div>
            <div className="space-y-4">
              {statusMetadata.length > 0 ? (
                <div className="grid gap-x-6 gap-y-3 text-xs text-slate-500 sm:grid-cols-2">
                  {statusMetadata.map(({ label, value }) => (
                    <div key={`status-${label}`} className="flex flex-col">
                      <span className="font-semibold text-slate-600">{label}</span>
                      <span className="break-words">{value}</span>
                    </div>
                  ))}
                </div>
              ) : status?.message ? (
                <p className="text-sm text-slate-500">{status.message}</p>
              ) : (
                <p className="text-sm text-slate-500">
                  Waiting for the first worker update...
                </p>
              )}
              {artifactActions}
              {artifactNotice && (
                <p className="text-xs text-slate-500">{artifactNotice}</p>
              )}
            </div>
            <div className="rounded-3xl border border-white/70 bg-white/80 px-6 py-6 shadow-inner shadow-white/30">
              <div className="flex items-center justify-between">
                <p className="text-xs uppercase tracking-[0.38em] text-slate-400">
                  Timeline
                </p>
                <span className="text-xs text-slate-500">
                  {sortedTimeline.length} events
                </span>
              </div>
              <div className="mt-4 space-y-4">
                <div className="space-y-3">
                  {summaryEvents.map((event, idx) =>
                    renderSummaryStage(event, idx)
                  )}
                </div>
                {summaryEvents.every((event) => event.pending) && (
                  <p className="text-sm text-slate-500">
                    Timeline updates will appear here as the pipeline progresses.
                  </p>
                )}
              </div>
            </div>
          </GlassCard>
        </div>
      )}
    </section>
  );
}

export default function Home() {
  return <JobDashboard />;
}
