"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { GlassCard } from "@/components/GlassCard";
import { GradientTitle } from "@/components/GradientTitle";
import { JobQuickLinks } from "@/components/JobQuickLinks";
import { TimelineCard } from "@/components/timeline/TimelineCard";
import { TimelineStageCard } from "@/components/timeline/TimelineStageCard";
import {
  createJob,
  fetchIntakeQuestions,
  fetchJobStatus,
  fetchJobTimeline,
  downloadArtifact,
  downloadDiagramArchive,
  fetchDocuments,
  resumeJob,
} from "@/lib/api";
import {
  CombinedCycleDetail,
  CYCLE_AWARE_STAGE_SET,
  CYCLE_AWARE_STAGES,
  determineEventPhase,
  normalizeStageName,
  StageCycleDetail,
  StageTimelineItem,
  StagePhase,
  stagePhaseLabel,
  TimelineEvent,
} from "@/lib/timeline";
import { useUser } from "@auth0/nextjs-auth0/client";

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

type JobDashboardProps = {
  initialJobId?: string;
};

const POLL_INTERVAL_MS = 20000;
const SUMMARY_STAGE_ORDER = [
  "ENQUEUED",
  "INTAKE_READY",
  "INTAKE_RESUME",
  "PLAN",
  "WRITE",
  "REVIEW",
  "VERIFY",
  "REWRITE",
  "DIAGRAM",
  "FINALIZE",
];

const REVIEW_SUBSTEP_LABELS: Record<string, string> = {
  REVIEW_GENERAL: "General review",
  REVIEW_STYLE: "Style review",
  REVIEW_COHESION: "Cohesion review",
  REVIEW_SUMMARY: "Executive summary",
  VERIFY: "Verify",
  REWRITE: "Rewrite",
};

const reviewStyleEnabled = process.env.NEXT_PUBLIC_REVIEW_STYLE_ENABLED !== "false";
const reviewCohesionEnabled = process.env.NEXT_PUBLIC_REVIEW_COHESION_ENABLED !== "false";
const reviewSummaryEnabled = process.env.NEXT_PUBLIC_REVIEW_SUMMARY_ENABLED !== "false";

export function JobDashboard({ initialJobId }: JobDashboardProps) {
  const { user, isLoading: authLoading, error: authError } = useUser();
  const primaryButtonClass = "btn-primary";
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
  const [documentTitle, setDocumentTitle] = useState<string | null>(null);
  const noticeTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  const enabledReviewSubstages = useMemo(() => {
    const list: string[] = ["REVIEW_GENERAL"];
    if (reviewStyleEnabled) list.push("REVIEW_STYLE");
    if (reviewCohesionEnabled) list.push("REVIEW_COHESION");
    if (reviewSummaryEnabled) list.push("REVIEW_SUMMARY");
    list.push("VERIFY", "REWRITE");
    return list;
  }, []);

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
    if (!title.trim()) {
      return;
    }
    setDocumentTitle(title.trim());
  }, [title]);

  useEffect(() => {
    if (!jobId || documentTitle) return;
    let cancelled = false;
    async function loadTitle() {
      try {
        const docs = await fetchDocuments();
        const match = (docs?.documents ?? []).find(
          (doc: { job_id?: string; title?: string | null }) => doc.job_id === jobId
        );
        if (!cancelled && match?.title) {
          setDocumentTitle(match.title.trim());
        }
      } catch (err) {
        console.error(err);
      }
    }
    loadTitle();
    return () => {
      cancelled = true;
    };
  }, [jobId, documentTitle]);

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
    if (!user?.sub) {
      setError("Sign in required to create a document");
      setLoading(false);
      return;
    }
    try {
      const trimmedAnswers = Object.fromEntries(
        Object.entries(answers).map(([key, value]) => [key, value.trim()])
      );
      const response = await createJob({
        title: title.trim(),
        audience: audience.trim(),
        cycles,
      });
      setDocumentTitle(title.trim());
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
  }, [answers, title, audience, cycles, clearNotice, user?.sub]);

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

  const baseStageName = useCallback((stage?: string | null) => {
    if (!stage) return "";
    return stage.replace(/_(DONE|START|QUEUED|FAILED|ERROR|IN_PROGRESS)$/u, "");
  }, []);

  const resolveFileBaseName = useCallback(
    (fallback?: string | null) => {
      const raw =
        (documentTitle && documentTitle.trim()) || (title && title.trim()) || (fallback ?? "");
      const safe = raw || "artifact";
      return safe.replace(/\s+/g, "-");
    },
    [documentTitle, title]
  );

  const stageOrder = useMemo(() => {
    const canonical = SUMMARY_STAGE_ORDER;
    const raw = timelineMeta?.stage_order;
    const extras: string[] = [];
    if (Array.isArray(raw)) {
      raw.forEach((item) => {
        if (typeof item !== "string") return;
        const base = normalizeStageName(item).toUpperCase();
        if (canonical.includes(base) || extras.includes(base)) {
          return;
        }
        extras.push(base);
      });
    }
    return [...canonical, ...extras];
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

  const extractParsedMessage = useCallback((event: TimelineEvent) => {
    const parsedRaw =
      event.details && typeof event.details === "object"
        ? (event.details as Record<string, unknown>)["parsed_message"]
        : null;
    const parsed =
      parsedRaw && typeof parsedRaw === "object"
        ? (parsedRaw as Record<string, unknown>)
        : null;
    return parsed;
  }, []);

  const getTokensFromEvent = useCallback(
    (event: TimelineEvent): number | null => {
      const parsed = extractParsedMessage(event);
      const parsedDisplay = parsed?.tokens_display;
      const fromDisplay =
        typeof parsedDisplay === "string" && parsedDisplay.trim()
          ? Number(parsedDisplay.replace(/,/g, ""))
          : null;
      if (typeof parsed?.tokens === "number" && parsed.tokens > 0) {
        return parsed.tokens;
      }
      if (typeof fromDisplay === "number" && Number.isFinite(fromDisplay) && fromDisplay > 0) {
        return fromDisplay;
      }
      if (typeof event.details?.tokens === "number" && event.details.tokens > 0) {
        return event.details.tokens;
      }
      return null;
    },
    [extractParsedMessage]
  );

  const computeStageDurationSeconds = useCallback((stageBase: string, events: TimelineEvent[]): number | null => {
    if (!events.length) return null;
    const sorted = [...events].sort((a, b) => Number(a.ts ?? 0) - Number(b.ts ?? 0));
    const startEvent =
      sorted.find((ev) => (ev.stage ?? "").startsWith(`${stageBase}_QUEUED`)) ?? sorted[0];
    const endEvent =
      [...sorted].reverse().find((ev) => (ev.stage ?? "").startsWith(`${stageBase}_DONE`)) ??
      [...sorted].reverse().find((ev) => (ev.stage ?? "").startsWith(`${stageBase}_IN_PROGRESS`)) ??
      sorted[sorted.length - 1];
    const startTs = Number(startEvent?.ts);
    const endTs = Number(endEvent?.ts);
    if (Number.isFinite(startTs) && Number.isFinite(endTs) && endTs >= startTs) {
        return endTs - startTs;
    }
    return null;
  }, []);

  const applyStageAggregation = useCallback(
    (event: TimelineEvent, relatedEvents: TimelineEvent[]): TimelineEvent => {
      const base = normalizeStageName(event.stage ?? "");
      if (base !== "REVIEW" && base !== "WRITE") {
        return event;
      }
      const stageOnly = relatedEvents.filter((ev) => normalizeStageName(ev.stage ?? "") === base);
      const durationOverrideSeconds = computeStageDurationSeconds(base, stageOnly);
      const tokensTotal =
        base === "WRITE"
          ? (() => {
              const completion = stageOnly.find((ev) => determineEventPhase(ev) === "complete");
              const completionTokens = completion ? getTokensFromEvent(completion) : null;
              if (typeof completionTokens === "number" && completionTokens > 0) {
                return completionTokens;
              }
              const latestInProgress = [...stageOnly].reverse().find((ev) => determineEventPhase(ev) === "in_progress");
              const inProgressTokens = latestInProgress ? getTokensFromEvent(latestInProgress) : null;
              return typeof inProgressTokens === "number" && inProgressTokens > 0 ? inProgressTokens : 0;
            })()
          : stageOnly.reduce((acc, ev) => acc + (getTokensFromEvent(ev) ?? 0), 0);
      const parsed = extractParsedMessage(event);
      const tokensDisplay = tokensTotal > 0 ? tokensTotal.toLocaleString() : undefined;
      const nextDetails: Record<string, unknown> = { ...(event.details ?? {}) };
      if (tokensTotal > 0) {
        nextDetails.tokens = tokensTotal;
        nextDetails.tokens_display = tokensDisplay;
      }
      if (durationOverrideSeconds != null) {
        nextDetails.duration_s = durationOverrideSeconds;
      }
      if (parsed) {
        nextDetails.parsed_message = {
          ...parsed,
          ...(tokensTotal > 0 ? { tokens: tokensTotal, tokens_display: tokensDisplay } : {}),
        };
      }
      return { ...event, details: nextDetails };
    },
    [computeStageDurationSeconds, extractParsedMessage, getTokensFromEvent]
  );

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
      if (base === "REVIEW_STYLE" && !reviewStyleEnabled) {
        return null;
      }
      if (base === "REVIEW_COHESION" && !reviewCohesionEnabled) {
        return null;
      }
      if (base === "REVIEW_SUMMARY" && !reviewSummaryEnabled) {
        return null;
      }
      const related = stageEventsByBase.get(base)
        ? [...stageEventsByBase.get(base)!].sort((a, b) => {
            const ta = Number(a.ts ?? 0);
            const tb = Number(b.ts ?? 0);
            return ta - tb;
          })
        : [];

      if (base === "REVIEW") {
        const failedEvent = [...related].reverse().find((entry) => determineEventPhase(entry) === "failed");
        const summaryCompletion = [...related]
          .reverse()
          .find((entry) => {
            const stageName = entry.stage?.toUpperCase() ?? "";
            return (
              determineEventPhase(entry) === "complete" &&
              (stageName.includes("REVIEW_SUMMARY_DONE") || stageName === "REVIEW_DONE" || stageName === "REVIEW")
            );
          });
        if (failedEvent) {
          return applyStageAggregation(
            {
              ...failedEvent,
              stage,
              pending: false,
              status: "failed" as const,
              displayStage: formatStage(base),
              sourceStage: failedEvent.stage,
            },
            related
          );
        }
        if (summaryCompletion) {
          return applyStageAggregation(
            {
              ...summaryCompletion,
              stage,
              pending: false,
              status: "complete" as const,
              displayStage: formatStage(base),
              sourceStage: summaryCompletion.stage,
            },
            related
          );
        }
        const inProgressEvent = [...related].reverse().find((entry) => determineEventPhase(entry) === "in_progress");
        if (inProgressEvent) {
          return applyStageAggregation(
            {
              ...inProgressEvent,
              stage,
              pending: false,
              status: "active" as const,
              displayStage: formatStage(base),
              sourceStage: inProgressEvent.stage,
            },
            related
          );
        }
        const queuedEvent = [...related].reverse().find((entry) => determineEventPhase(entry) === "queued");
        if (queuedEvent) {
          return applyStageAggregation(
            {
              ...queuedEvent,
              stage,
              pending: false,
              status: "active" as const,
              displayStage: formatStage(base),
              sourceStage: queuedEvent.stage,
            },
            related
          );
        }
        const latest = related[related.length - 1];
        if (latest) {
          return applyStageAggregation(
            {
              ...latest,
              stage,
              pending: false,
              status: "active" as const,
              displayStage: formatStage(base),
              sourceStage: latest.stage,
            },
            related
          );
        }
      }

      const completionEvent = [...related].reverse().find((entry) => determineEventPhase(entry) === "complete");
      const failedEvent = [...related].reverse().find((entry) => determineEventPhase(entry) === "failed");
      if (completionEvent) {
        return applyStageAggregation(
          {
            ...completionEvent,
            stage,
            pending: false,
            status: "complete" as const,
            displayStage: formatStage(base),
            sourceStage: completionEvent.stage,
          },
          related
        );
      }

      if (failedEvent) {
        return applyStageAggregation(
          {
            ...failedEvent,
            stage,
            pending: false,
            status: "failed" as const,
            displayStage: formatStage(base),
            sourceStage: failedEvent.stage,
          },
          related
        );
      }

      const inProgressEvent = [...related].reverse().find((entry) => determineEventPhase(entry) === "in_progress");
      if (inProgressEvent) {
        return applyStageAggregation(
          {
            ...inProgressEvent,
            stage,
            pending: false,
            status: "active" as const,
            displayStage: formatStage(base),
            sourceStage: inProgressEvent.stage,
          },
          related
        );
      }

      const queuedEvent = [...related].reverse().find((entry) => determineEventPhase(entry) === "queued");
      if (queuedEvent) {
        return applyStageAggregation(
          {
            ...queuedEvent,
            stage,
            pending: false,
            status: "active" as const,
            displayStage: formatStage(base),
            sourceStage: queuedEvent.stage,
          },
          related
        );
      }

      return applyStageAggregation(
        {
          stage,
          message: `${formatStage(stage)} pending`,
          pending: true,
          status: "pending" as const,
          displayStage: formatStage(base),
        } as TimelineEvent,
        related
      );
    }).filter((event): event is TimelineEvent => Boolean(event));
  }, [applyStageAggregation, formatStage, sortedTimeline, stageOrder]);

  const summaryEventsToRender = useMemo(() => {
    return summaryEvents.filter((event) => {
      const base = normalizeStageName(event.stage);
      return base !== "VERIFY" && base !== "REWRITE";
    });
  }, [summaryEvents]);

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
    (event: TimelineEvent, durationOverrideSeconds?: number | null): Array<{ label: string; value: string }> => {
      const entries: Array<{ label: string; value: string }> = [];
      const seen = new Set<string>();
      const parsed = extractParsedMessage(event);

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
        (durationOverrideSeconds != null ? formatDuration(durationOverrideSeconds) : null) ||
        (typeof event.details?.duration_s === "number" ? formatDuration(event.details.duration_s) : null) ||
        (parsed?.duration && typeof parsed.duration === "string" && parsed.duration.trim());
      addEntry("Stage Time", durationText);

      const tokensValue = getTokensFromEvent(event);
      const tokensDisplay =
        (typeof tokensValue === "number" && tokensValue > 0 && tokensValue.toLocaleString()) ||
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

      const messageValue =
        (typeof event.message === "string" && event.message.trim()) ||
        (typeof parsed?.message === "string" && parsed.message.trim()) ||
        null;
      addEntry("Message", messageValue);

      return entries;
    },
    [extractParsedMessage, formatDuration, formatStage, getTokensFromEvent]
  );

  const downloadArtifactFile = useCallback(
    async (job: string | null, path: string) => {
      if (!job) {
        console.warn("Attempted to download artifact without job ID");
        return;
      }
      try {
        const { blob, fileName, contentType } = await downloadArtifact(job, path);
        const rawName = (fileName || path.split("/").pop() || "artifact").trim();
        const existingExt = rawName.match(/\.([^\.\s/]+)$/)?.[1];
        const pathExt = path.match(/\.([^\.\s/]+)$/)?.[1];
        const typeExtMap: Record<string, string> = {
          "application/pdf": "pdf",
          "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "docx",
          "text/markdown": "md",
          "text/x-markdown": "md",
        };
        const typeExt = contentType ? typeExtMap[contentType.split(";")[0]?.trim().toLowerCase() || ""] : undefined;
        const ext = existingExt || pathExt || typeExt || "";
        const baseName = resolveFileBaseName(job);
        const resolvedName = ext ? `${baseName}.${ext}` : baseName;
        const url = URL.createObjectURL(blob);
        const link = document.createElement("a");
        link.href = url;
        link.download = resolvedName;
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
        URL.revokeObjectURL(url);
        showNotice(`Download started for ${resolvedName}`);
      } catch (err) {
        console.error(err);
        setError("Failed to download artifact");
      }
    },
    [showNotice, resolveFileBaseName]
  );

  const downloadDiagramArchiveFile = useCallback(
    async (job: string | null) => {
      if (!job) {
        console.warn("Attempted to download diagram archive without job ID");
        return;
      }
      try {
        const { blob } = await downloadDiagramArchive(job);
        const baseName = resolveFileBaseName(job);
        const resolvedName = `${baseName}-diagrams.zip`;
        const url = URL.createObjectURL(blob);
        const link = document.createElement("a");
        link.href = url;
        link.download = resolvedName;
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
        URL.revokeObjectURL(url);
        showNotice(`Download started for ${resolvedName}`);
      } catch (err) {
        console.error(err);
        setError("Failed to download diagram archive");
      }
    },
    [showNotice, resolveFileBaseName]
  );

  const renderArtifactActions = useCallback(
    (path: string, size: "sm" | "md" = "md", stageBase?: string) => {
      const fileName = path.split("/").pop() ?? path;
      const chipClass =
        "flex items-center gap-2 rounded-full bg-white/70 px-3 py-1 text-xs font-semibold text-slate-600 shadow-sm";
      const badgeClass =
        "rounded-full bg-indigo-50 px-2 py-[2px] text-[10px] font-semibold uppercase tracking-[0.3em] text-indigo-500";
      const buttonClass =
        "rounded-full bg-white/80 px-3 py-1 text-xs font-medium text-slate-600 shadow hover:bg-white cursor-pointer";
      const containerClass = size === "sm" ? "mt-2 space-y-2 pl-2" : "mt-3 space-y-3";
      const hasMarkdown = fileName.toLowerCase().endsWith(".md");
      const basePath = hasMarkdown ? path.replace(/\.[^/.]+$/, "") : path;
      const allowRichFormats = stageBase === "FINALIZE";
      const variants = hasMarkdown
        ? [
            { label: "Markdown", display: fileName, artifactPath: path },
            ...(allowRichFormats
              ? [
                  { label: "PDF", display: "PDF", artifactPath: `${basePath}.pdf` },
                  { label: "Word", display: "Word", artifactPath: `${basePath}.docx` },
                ]
              : []),
          ]
        : [{ label: undefined, display: fileName, artifactPath: path }];

      const showDiagramAssets = stageBase === "FINALIZE";

      return (
        <div className={containerClass}>
          {allowRichFormats && hasMarkdown ? (
            <div className="flex flex-wrap gap-2">
              {[...variants, ...(showDiagramAssets ? [{ label: "Diagrams", artifactPath: "diagrams" }] : [])].map(
                ({ label: variantLabel, artifactPath }) => {
                  if (variantLabel === "Diagrams") {
                    return (
                      <button
                        key="diagram-assets"
                        type="button"
                        className={buttonClass}
                        onClick={() => downloadDiagramArchiveFile(jobId)}
                      >
                        Download diagram assets
                      </button>
                    );
                  }
                  return (
                    <button
                      key={`${artifactPath}-${variantLabel ?? "default"}`}
                      type="button"
                      className={buttonClass}
                      onClick={() => downloadArtifactFile(jobId, artifactPath)}
                    >
                      {variantLabel ? `Download ${variantLabel}` : "Download"}
                    </button>
                  );
                }
              )}
            </div>
          ) : (
            variants.map(({ label: variantLabel, display, artifactPath }) => (
              <div key={`${artifactPath}-${variantLabel ?? "default"}`} className="flex flex-wrap items-center gap-2">
                <span className={chipClass}>
                  {display}
                  {variantLabel ? <span className={badgeClass}>{variantLabel}</span> : null}
                </span>
                <div className="flex flex-wrap gap-2">
                  <button
                    type="button"
                    className={buttonClass}
                    onClick={() => downloadArtifactFile(jobId, artifactPath)}
                  >
                    Download
                  </button>
                </div>
              </div>
            ))
          )}
        </div>
      );
    },
    [downloadArtifactFile, downloadDiagramArchiveFile, jobId]
  );

  useEffect(() => {
    return () => {
      clearNotice();
    };
  }, [clearNotice]);

  const artifactActions = status?.artifact
    ? renderArtifactActions(status.artifact, "md", status.stage ? normalizeStageName(status.stage) : undefined)
    : null;
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
        let durationOverride: number | null = null;
        if (stageBase === "REVIEW") {
          durationOverride = computeStageDurationSeconds("REVIEW", stageEvents);
        }

        const metadataEntries = metadataSource ? getMetadataEntries(metadataSource, durationOverride) : [];

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
  }, [computeStageDurationSeconds, groupedTimeline.cycles, getMetadataEntries]);

  const combinedReviewCycles = useMemo<CombinedCycleDetail[]>(() => {
    const defaultDetail = (stageBase: string, cycle: number): StageCycleDetail => ({
      cycle,
      status: "queued",
      metadataEntries: [],
      timeline: [
        {
          key: `${stageBase}-${cycle}-pending`,
          label: "Not started",
          ts: undefined,
        },
      ],
      completionTs: null,
      lastUpdateTs: null,
    });

    const buildDetail = (stageBase: string, cycle: number, events: TimelineEvent[]): StageCycleDetail => {
      const stageEvents = events.filter((ev) => baseStageName(ev.stage ?? "") === stageBase);
      const completionEvent = [...stageEvents].reverse().find((ev) => determineEventPhase(ev) === "complete");
      const failedEvent = [...stageEvents].reverse().find((ev) => determineEventPhase(ev) === "failed");
      const inProgressEvent = [...stageEvents].reverse().find((ev) => determineEventPhase(ev) === "in_progress");
      const queuedEvent = [...stageEvents].reverse().find((ev) => determineEventPhase(ev) === "queued");

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

      let timeline: StageTimelineItem[] = stageEvents.map((ev, idx) => ({
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
        (stageEvents.length ? stageEvents[stageEvents.length - 1]?.ts : null);

      return {
        cycle,
        status,
        metadataEntries,
        timeline,
        completionTs,
        lastUpdateTs,
      };
    };

    return groupedTimeline.cycles.map(({ cycle, events }) => {
      const sortedEvents = [...events].sort((a, b) => {
        const ta = Number(a.ts ?? 0);
        const tb = Number(b.ts ?? 0);
        return ta - tb;
      });
      const substeps = enabledReviewSubstages.map((stageBase) => {
        const label = REVIEW_SUBSTEP_LABELS[stageBase] ?? formatStage(stageBase);
        const detail = buildDetail(stageBase, cycle, sortedEvents) || defaultDetail(stageBase, cycle);
        return {
          stage: stageBase as CombinedCycleDetail["substeps"][number]["stage"],
          label,
          detail,
        };
      });
      return { cycle, substeps };
    });
  }, [baseStageName, enabledReviewSubstages, formatStage, getMetadataEntries, groupedTimeline.cycles]);

  const [expandedCycles, setExpandedCycles] = useState<Record<number, boolean>>({});
  const [expandedSubsteps, setExpandedSubsteps] = useState<Record<number, Record<string, boolean>>>({});
  const [expandedSummaryStages, setExpandedSummaryStages] = useState<Record<string, boolean>>({});

  useEffect(() => {
    setExpandedSummaryStages((prev) => {
      const next = { ...prev };
      let changed = false;
      summaryEvents.forEach((event) => {
        const base = normalizeStageName(event.stage);
        if (!(base in next)) {
          next[base] = event.status === "active";
          changed = true;
        } else if (event.status === "active" && !next[base]) {
          next[base] = true;
          changed = true;
        }
      });
      return changed ? next : prev;
    });
  }, [summaryEvents]);

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

  useEffect(() => {
    setExpandedSubsteps((prev) => {
      let changed = false;
      const next: Record<number, Record<string, boolean>> = { ...prev };
      combinedReviewCycles.forEach(({ cycle, substeps }) => {
        const current = { ...(next[cycle] ?? {}) };
        substeps.forEach(({ stage, detail }) => {
          if (!(stage in current)) {
            current[stage] = detail.status === "in_progress";
            changed = true;
          }
        });
        if (Object.keys(current).length > 0) {
          next[cycle] = current;
        }
      });
      return changed ? { ...next } : prev;
    });
  }, [combinedReviewCycles]);

  const renderSummaryStage = useCallback(
    (stageEvent: TimelineEvent, index: number) => (
      <TimelineStageCard
        key={`summary-${stageEvent.stage}-${index}`}
        event={stageEvent}
        index={index}
        stageBase={normalizeStageName(stageEvent.stage)}
        formatStage={formatStage}
        formatTimestamp={formatTimestamp}
        getMetadataEntries={getMetadataEntries}
        renderArtifactActions={renderArtifactActions}
        combinedReviewCycles={combinedReviewCycles}
        cycleDetailsByStage={cycleDetailsByStage}
        expandedSummaryStages={expandedSummaryStages}
        setExpandedSummaryStages={setExpandedSummaryStages}
        expandedCycles={expandedCycles}
        setExpandedCycles={setExpandedCycles}
        expandedSubsteps={expandedSubsteps}
        setExpandedSubsteps={setExpandedSubsteps}
      />
    ),
    [
      combinedReviewCycles,
      cycleDetailsByStage,
      expandedCycles,
      expandedSubsteps,
      expandedSummaryStages,
      formatStage,
      formatTimestamp,
      getMetadataEntries,
      renderArtifactActions,
      setExpandedCycles,
      setExpandedSubsteps,
      setExpandedSummaryStages,
    ]
  );

  if (authLoading) {
    return (
      <section id="intake" className="space-y-12 pb-10">
        <GlassCard className="text-slate-600">
          <p className="text-lg font-semibold">Checking authentication…</p>
        </GlassCard>
      </section>
    );
  }

  if (!user) {
    return (
      <section id="intake" className="space-y-12 pb-10">
        <GlassCard className="space-y-4 text-slate-800">
          <h2 className="text-2xl font-semibold text-slate-900">Sign in required</h2>
          <p className="text-slate-600">Your session expired. Please sign in again to continue.</p>
          <Link
            href="/api/auth/login?returnTo=/workspace"
            prefetch={false}
            className="btn-primary w-full sm:w-auto"
          >
            Go to sign in
          </Link>
          {authError ? <p className="text-sm text-red-500">{authError.message}</p> : null}
        </GlassCard>
      </section>
    );
  }

  return (
    <section id="intake" className="space-y-12 pb-10">
      {error ? (
        <GlassCard className="border-red-400/40 bg-red-500/10 text-red-100">
          <p className="text-sm">{error}</p>
        </GlassCard>
      ) : null}

      {step === 1 && (
        <div className="space-y-8 rounded-[32px] border border-white/25 bg-gradient-to-br from-slate-900 via-blue-900 to-sky-800 px-10 py-10 text-white shadow-[0_45px_140px_rgba(15,23,42,0.45)]">
          <div className="space-y-2">
            <h2 className="text-3xl font-semibold text-white">Document details</h2>
            <p className="text-sm text-white/80">
              Tell us what you need so we can craft a tailored intake questionnaire.
            </p>
          </div>
          <div className="grid gap-8 md:grid-cols-2">
            <div className="space-y-3">
              <label className="text-xs font-semibold uppercase tracking-[0.4em] text-white/70">
                Working title
              </label>
              <input
                className="input-glass border-white/40 bg-white/95 text-slate-900 placeholder:text-slate-500"
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                placeholder="e.g., Asynchronous Integration Patterns"
              />
            </div>
            <div className="space-y-3">
              <label className="text-xs font-semibold uppercase tracking-[0.4em] text-white/70">
                Primary audience
              </label>
              <input
                className="input-glass border-white/40 bg-white/95 text-slate-900 placeholder:text-slate-500"
                value={audience}
                onChange={(e) => setAudience(e.target.value)}
                placeholder="e.g., Enterprise Integration Architects"
              />
            </div>
          </div>
          <div className="flex flex-col gap-6 md:flex-row md:items-end md:justify-between">
            <div className="space-y-3">
              <label className="text-xs font-semibold uppercase tracking-[0.4em] text-white/70">
                Review cycles
              </label>
              <input
                type="number"
                min={1}
                max={5}
                className="input-glass max-w-[120px] border-white/40 bg-white/95 text-slate-900"
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
        </div>
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
            <JobQuickLinks
              jobId={jobId}
              statusStage={
                status?.stage ? formatStage(normalizeStageName(status.stage)) : null
              }
              statusCycle={status?.cycle ?? null}
              metadata={statusMetadata}
              statusMessage={status?.message ?? null}
              artifactActions={artifactActions}
              artifactNotice={artifactNotice}
            />
            <TimelineCard
              totalEvents={sortedTimeline.length}
              renderedStages={summaryEventsToRender.map((timelineEvent, idx) =>
                renderSummaryStage(timelineEvent, idx)
              )}
              showPendingMessage={summaryEvents.every((timelineEvent) => timelineEvent.pending)}
            />
          </GlassCard>
        </div>
      )}
    </section>
  );
}

export default function NewDocumentPage() {
  return (
    <div className="space-y-12">
      <section className="space-y-6 rounded-[32px] border border-white/25 bg-gradient-to-br from-slate-900 via-blue-900 to-sky-700 p-10 text-white shadow-[0_45px_140px_rgba(15,23,42,0.4)]">
        <p className="text-sm uppercase tracking-[0.35em] text-white/80">New document</p>
        <h1 className="text-4xl font-semibold">Launch a DocWriter pipeline</h1>
        <p className="text-lg text-white/80">
          Provide a title, audience, and desired review cycles. DocWriter will interview you, plan the structure, and orchestrate writers, reviewers, and verifiers automatically.
        </p>
        <div className="flex flex-wrap gap-4">
          <a
            href="#intake"
            className="rounded-full bg-white px-8 py-3 text-base font-semibold text-slate-900 shadow-lg transition hover:bg-slate-100"
          >
            Start intake
          </a>
          <span className="inline-flex items-center rounded-full border border-white/50 px-6 py-3 text-base text-white/80">
            Track every stage, from plan to finalize
          </span>
        </div>
      </section>

      <JobDashboard />
    </div>
  );
}
