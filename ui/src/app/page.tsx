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

export default function Home() {
  const primaryButtonClass = "btn-primary";
  const inputClass = "input-glass";
  const [step, setStep] = useState<1 | 2 | 3>(1);
  const [title, setTitle] = useState("");
  const [audience, setAudience] = useState("");
  const [cycles, setCycles] = useState(2);
  const [questions, setQuestions] = useState<IntakeQuestion[]>([]);
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const [jobId, setJobId] = useState<string | null>(null);
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
    if (!jobId) return;
    const controller = new AbortController();

    async function poll() {
      try {
        const payload = await fetchJobStatus(jobId);
        setStatus(payload);
        const history = await fetchJobTimeline(jobId);
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
    const normalizeStage = (value: string) => {
      const base = value.replace(STAGE_SUFFIX_PATTERN, "");
      if (base === "INTAKE_RESUMED") {
        return "INTAKE_RESUME";
      }
      return base;
    };
    const isCompletionEvent = (stage: string) => {
      if (!stage) return false;
      return !/(?:_QUEUED|_START|_FAILED|_ERROR)$/u.test(stage);
    };
    const stageEventsByBase = new Map<string, TimelineEvent[]>();
    sortedTimeline.forEach((event) => {
      if (!event.stage || event.cycle != null) {
        return;
      }
      const base = normalizeStage(event.stage);
      const existing = stageEventsByBase.get(base) ?? [];
      existing.push(event);
      stageEventsByBase.set(base, existing);
    });

    return stageOrder.map((stage) => {
      const base = normalizeStage(stage);
      const related = stageEventsByBase.get(base)
        ? [...stageEventsByBase.get(base)!].sort((a, b) => {
            const ta = Number(a.ts ?? 0);
            const tb = Number(b.ts ?? 0);
            return ta - tb;
          })
        : [];

      const completionEvent = [...related].reverse().find((entry) => isCompletionEvent(entry.stage));
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

      const latestRelated = related[related.length - 1];
      if (latestRelated) {
        return {
          ...latestRelated,
          stage,
          pending: false,
          status: "active" as const,
          displayStage: formatStage(base),
          sourceStage: latestRelated.stage,
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

  const renderEvent = useCallback(
    (event: TimelineEvent, key: string) => {
      const tokens =
        typeof event.details?.tokens === "number" ? event.details.tokens : null;
      const duration =
        typeof event.details?.duration_s === "number" ? event.details.duration_s : null;
      const model =
        typeof event.details?.model === "string" ? event.details.model : null;
      const notes =
        typeof event.details?.notes === "string" ? event.details.notes : null;
      const parsedMessage = (() => {
        if (!event.details || typeof event.details !== "object") {
          return null;
        }
        const raw = (event.details as Record<string, unknown>)["parsed_message"];
        return raw && typeof raw === "object" ? (raw as Record<string, unknown>) : null;
      })();
      const parsedFields = (() => {
        if (!parsedMessage) {
          return null;
        }
        const stageLabel = parsedMessage["stage_label"];
        const document = parsedMessage["document"];
        const durationText = parsedMessage["duration"];
        const tokensNumber = parsedMessage["tokens"];
        const tokensDisplay = parsedMessage["tokens_display"];
        const parsedModel = parsedMessage["model"];
        const parsedNotes = parsedMessage["notes"];
        const entries: Array<{ label: string; value: string }> = [];
        if (typeof stageLabel === "string" && stageLabel.trim() && stageLabel.toLowerCase() !== "n/a") {
          entries.push({ label: "Stage", value: stageLabel.trim() });
        }
        if (typeof document === "string" && document.trim() && document.toLowerCase() !== "n/a") {
          entries.push({ label: "Document", value: document.trim() });
        }
        if (typeof durationText === "string" && durationText.trim() && durationText.toLowerCase() !== "n/a") {
          entries.push({ label: "Stage Time", value: durationText.trim() });
        }
        if (typeof tokensNumber === "number") {
          entries.push({ label: "Tokens", value: tokensNumber.toLocaleString() });
        } else if (typeof tokensDisplay === "string" && tokensDisplay.trim() && tokensDisplay.toLowerCase() !== "n/a") {
          entries.push({ label: "Tokens", value: tokensDisplay.trim() });
        }
        if (typeof parsedModel === "string" && parsedModel.trim() && parsedModel.toLowerCase() !== "n/a") {
          entries.push({ label: "Model", value: parsedModel.trim() });
        }
        if (typeof parsedNotes === "string" && parsedNotes.trim() && parsedNotes.toLowerCase() !== "n/a") {
          entries.push({ label: "Notes", value: parsedNotes.trim() });
        }
        return entries.length ? entries : null;
      })();

      return (
        <div
          key={key}
          className="rounded-2xl bg-white/80 px-4 py-3 shadow-sm shadow-white/50"
        >
          <div className="flex items-start justify-between gap-3">
            <div>
              <p className="text-sm font-semibold text-slate-700">
                {formatStage(event.stage)}
              </p>
              <p className="text-xs text-slate-500">
                {formatTimestamp(event.ts)}
                {event.cycle ? ` · Cycle ${event.cycle}` : ""}
              </p>
            </div>
            {tokens !== null && (
              <span className="rounded-full bg-slate-100 px-3 py-1 text-xs font-semibold text-slate-600">
                {tokens.toLocaleString()} tokens
              </span>
            )}
          </div>
          {parsedFields ? (
            <div className="mt-2 grid gap-x-4 gap-y-2 text-xs text-slate-500 sm:grid-cols-2">
              {parsedFields.map(({ label, value }) => (
                <div key={`${key}-${label}`} className="flex flex-col">
                  <span className="font-semibold text-slate-600">{label}</span>
                  <span>{value}</span>
                </div>
              ))}
            </div>
          ) : event.message ? (
            <p className="mt-2 text-sm text-slate-600">{event.message}</p>
          ) : null}
          <div className="mt-2 flex flex-wrap gap-2 text-xs text-slate-500">
            {duration !== null && (
              <span className="rounded-full bg-slate-100 px-3 py-1">
                {`Duration: ${formatDuration(duration)}`}
              </span>
            )}
            {model && (
              <span className="rounded-full bg-slate-100 px-3 py-1">
                {`Model: ${model}`}
              </span>
            )}
            {notes && (
              <span className="rounded-full bg-slate-100 px-3 py-1">
                {notes}
              </span>
            )}
          </div>
          {event.artifact ? renderArtifactActions(event.artifact, "sm") : null}
        </div>
      );
    },
    [formatDuration, formatStage, formatTimestamp, renderArtifactActions]
  );

  useEffect(() => {
    return () => {
      clearNotice();
    };
  }, [clearNotice]);

  const artifactActions = status?.artifact ? renderArtifactActions(status.artifact) : null;

  const renderSummaryStage = useCallback(
    (event: TimelineEvent, index: number) => {
      const status = event.status ?? (event.pending ? "pending" : "complete");
      const completed = status === "complete";
      const active = status === "active";
      const label = event.displayStage ?? formatStage(event.stage);
      const statusLabel = completed ? "Completed" : active ? "Active" : "Pending";
      let secondaryText = statusLabel;
      if ((completed || active) && event.ts != null) {
        secondaryText = `${statusLabel} • ${formatTimestamp(event.ts)}`;
      }
      const badgeClass = completed
        ? "bg-indigo-500 text-white"
        : active
        ? "border border-indigo-300 bg-indigo-50 text-indigo-600"
        : "bg-white border border-slate-200 text-slate-400";
      const showCycles = event.stage === "REVIEW" && groupedTimeline.cycles.length > 0;
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
              {event.message && (completed || active) ? (
                <p className="mt-1 text-xs text-slate-500">{event.message}</p>
              ) : null}
              {event.artifact && (completed || active)
                ? renderArtifactActions(event.artifact, "sm")
                : null}
            </div>
            {showCycles ? (
              <div className="space-y-3">
                {groupedTimeline.cycles.map(({ cycle, events: cycleEvents }) => {
                  const isExpanded = expandedCycles[cycle] ?? false;
                  const latest = cycleEvents[cycleEvents.length - 1];
                  return (
                    <div
                      key={`cycle-${cycle}`}
                      className="rounded-2xl border border-slate-100 bg-white/80 px-4 py-3 shadow-inner shadow-white/30"
                    >
                      <button
                        type="button"
                        className="flex w-full items-center justify-between text-left"
                        onClick={() =>
                          setExpandedCycles((prev) => ({
                            ...prev,
                            [cycle]: !isExpanded,
                          }))
                        }
                      >
                        <div>
                          <p className="text-xs font-semibold uppercase tracking-[0.3em] text-slate-400">
                            Review cycle {cycle}
                          </p>
                          {latest?.ts ? (
                            <p className="text-xs text-slate-500">
                              Completed {formatTimestamp(latest.ts)}
                            </p>
                          ) : null}
                          {typeof latest?.details?.duration_s === "number" && (
                            <p className="text-xs text-slate-500">
                              Duration: {formatDuration(latest.details.duration_s)}
                            </p>
                          )}
                        </div>
                        <span className="text-lg text-slate-500">
                          {isExpanded ? "−" : "+"}
                        </span>
                      </button>
                      {isExpanded && (
                        <div className="mt-3 space-y-2 border-t border-slate-100 pt-3">
                          {cycleEvents.map((cycleEvent, cycleIdx) =>
                            renderEvent(
                              cycleEvent,
                              `cycle-${cycle}-${cycleIdx}-${cycleEvent.stage}`
                            )
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
      formatDuration,
      formatStage,
      formatTimestamp,
      groupedTimeline.cycles,
      renderArtifactActions,
      renderEvent,
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
              {status?.message ? (
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
