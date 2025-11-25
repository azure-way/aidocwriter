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
  fetchDocuments,
  fetchIntakeQuestions,
  fetchJobStatus,
  fetchJobTimeline,
  downloadArtifact,
  getArtifactUrl,
  resumeJob,
} from "@/lib/api";
import {
  CombinedCycleDetail,
  CYCLE_AWARE_STAGE_SET,
  CYCLE_AWARE_STAGES,
  determineEventPhase,
  normalizeStageName,
  StageCycleDetail,
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

interface DocumentSummary {
  job_id: string;
  title?: string;
  audience?: string;
  stage?: string;
  message?: string;
  updated?: number;
  artifact?: string;
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
  "DIAGRAM",
  "FINALIZE",
];

const SUBSTEP_LABELS: Record<string, string> = {
  REVIEW: "Review",
  VERIFY: "Verify",
  REWRITE: "Rewrite",
};

export function JobDashboard({ initialJobId }: JobDashboardProps) {
  const { user, isLoading: authLoading, error: authError } = useUser();
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
  const [documents, setDocuments] = useState<DocumentSummary[]>([]);
  const [documentsLoading, setDocumentsLoading] = useState(false);
  const [documentsError, setDocumentsError] = useState<string | null>(null);
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

  const refreshDocuments = useCallback(async () => {
    if (!user?.sub) return;
    setDocumentsLoading(true);
    try {
      const data = await fetchDocuments(user.sub);
      setDocuments(data.documents ?? []);
      setDocumentsError(null);
    } catch (docErr) {
      setDocumentsError(docErr instanceof Error ? docErr.message : "Failed to load documents");
    } finally {
      setDocumentsLoading(false);
    }
  }, [user?.sub]);

  useEffect(() => {
    refreshDocuments();
  }, [refreshDocuments]);

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
    if (!user?.sub) {
      setError("Sign in required to create a document");
      return;
    }
    try {
      const trimmedAnswers = Object.fromEntries(
        Object.entries(answers).map(([key, value]) => [key, value.trim()])
      );
      const response = await createJob(
        {
          title: title.trim(),
          audience: audience.trim(),
          cycles,
        },
        user.sub
      );
      const id = response.job_id as string;
      await resumeJob(id, trimmedAnswers, user.sub);
      setJobId(id);
      setStep(3);
      setTimeline([]);
      setTimelineMeta({});
      clearNotice();
      refreshDocuments();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to submit answers");
    } finally {
      setLoading(false);
    }
  }, [answers, title, audience, cycles, clearNotice, refreshDocuments, user?.sub]);

  const disableSubmit = useMemo(() => {
    return Object.values(answers).some((ans) => !ans.trim());
  }, [answers]);

  const formatDocumentTimestamp = useCallback((value?: number) => {
    if (!value && value !== 0) return "—";
    const date = new Date(Number(value) * 1000);
    return date.toLocaleString();
  }, []);

  const handleSelectDocument = useCallback(
    (doc: DocumentSummary) => {
      setJobId(doc.job_id);
      setStep(3);
      setTimeline([]);
      setTimelineMeta({});
      clearNotice();
    },
    [clearNotice]
  );

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
        "flex items-center gap-2 rounded-full bg-white/70 px-3 py-1 text-xs font-semibold text-slate-600 shadow-sm";
      const badgeClass =
        "rounded-full bg-indigo-50 px-2 py-[2px] text-[10px] font-semibold uppercase tracking-[0.3em] text-indigo-500";
      const buttonClass =
        "rounded-full bg-white/80 px-3 py-1 text-xs font-medium text-slate-600 shadow hover:bg-white";
      const containerClass = size === "sm" ? "mt-2 space-y-2 pl-2" : "mt-3 space-y-3";
      const hasMarkdown = fileName.toLowerCase().endsWith(".md");
      const basePath = hasMarkdown ? path.replace(/\.[^/.]+$/, "") : path;
      const variants = hasMarkdown
        ? [
            { label: "Markdown", display: fileName, artifactPath: path },
            {
              label: "PDF",
              display: fileName.replace(/\.md$/i, ".pdf"),
              artifactPath: `${basePath}.pdf`,
            },
            {
              label: "Word",
              display: fileName.replace(/\.md$/i, ".docx"),
              artifactPath: `${basePath}.docx`,
            },
          ]
        : [{ label: undefined, display: fileName, artifactPath: path }];

      return (
        <div className={containerClass}>
          {variants.map(({ label: variantLabel, display, artifactPath }) => (
            <div key={`${artifactPath}-${variantLabel ?? "default"}`} className="flex flex-wrap items-center gap-2">
              <span className={chipClass}>
                {display}
                {variantLabel ? <span className={badgeClass}>{variantLabel}</span> : null}
              </span>
              <div className="flex flex-wrap gap-2">
                <button
                  type="button"
                  className={buttonClass}
                  onClick={() => openArtifact(artifactPath)}
                >
                  Open
                </button>
                <button
                  type="button"
                  className={buttonClass}
                  onClick={() => copyArtifactLink(artifactPath)}
                >
                  Copy link
                </button>
                <button
                  type="button"
                  className={buttonClass}
                  onClick={() => downloadArtifactFile(artifactPath)}
                >
                  Download
                </button>
              </div>
            </div>
          ))}
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

  const combinedReviewCycles = useMemo<CombinedCycleDetail[]>(() => {
    const reviewDetails = cycleDetailsByStage.get("REVIEW") ?? [];
    const verifyDetails = cycleDetailsByStage.get("VERIFY") ?? [];
    const rewriteDetails = cycleDetailsByStage.get("REWRITE") ?? [];

    const indexByCycle = (details: StageCycleDetail[]) =>
      new Map(details.map((detail) => [detail.cycle, detail]));

    const reviewMap = indexByCycle(reviewDetails);
    const verifyMap = indexByCycle(verifyDetails);
    const rewriteMap = indexByCycle(rewriteDetails);

    const createDefaultDetail = (stageBase: "REVIEW" | "VERIFY" | "REWRITE", cycle: number): StageCycleDetail => ({
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

    return groupedTimeline.cycles.map(({ cycle }) => {
      const reviewDetail = reviewMap.get(cycle) ?? createDefaultDetail("REVIEW", cycle);
      const verifyDetail = verifyMap.get(cycle) ?? createDefaultDetail("VERIFY", cycle);
      const rewriteDetail = rewriteMap.get(cycle) ?? createDefaultDetail("REWRITE", cycle);
      return {
        cycle,
        substeps: [
          { stage: "REVIEW", label: SUBSTEP_LABELS.REVIEW, detail: reviewDetail },
          { stage: "VERIFY", label: SUBSTEP_LABELS.VERIFY, detail: verifyDetail },
          { stage: "REWRITE", label: SUBSTEP_LABELS.REWRITE, detail: rewriteDetail },
        ],
      };
    });
  }, [cycleDetailsByStage, groupedTimeline.cycles]);

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
          <Link href="/api/auth/login?returnTo=/workspace" className="btn-primary w-full sm:w-auto">
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

      <GlassCard className="space-y-6">
        <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <p className="text-xs uppercase tracking-[0.4em] text-slate-500">Documents</p>
            <h2 className="text-2xl font-semibold text-slate-900">Your document workspace</h2>
            <p className="text-sm text-slate-500">Select an existing document to view details or start a new one.</p>
          </div>
          <button
            type="button"
            className="btn-primary"
            onClick={() => {
              setJobId(null);
              setStep(1);
            }}
          >
            Create new document
          </button>
        </div>
        {documentsError ? <p className="text-sm text-red-500">{documentsError}</p> : null}
        {documentsLoading ? (
          <p className="text-sm text-slate-500">Loading documents…</p>
        ) : documents.length ? (
          <div className="space-y-3">
            {documents.map((doc) => (
              <div
                key={doc.job_id}
                className="flex flex-col gap-3 rounded-2xl border border-slate-100/80 bg-white/70 px-4 py-4 text-slate-800 shadow-[0_15px_50px_rgba(15,23,42,0.08)] sm:flex-row sm:items-center sm:justify-between"
              >
                <div>
                  <p className="text-base font-semibold text-slate-900">{doc.title || "Untitled document"}</p>
                  <p className="text-sm text-slate-500">{doc.message || "No updates yet"}</p>
                </div>
                <div className="flex flex-col gap-1 text-sm text-slate-500 sm:flex-row sm:items-center sm:gap-6">
                  <span className="font-semibold text-slate-800">{doc.stage || "—"}</span>
                  <span>{formatDocumentTimestamp(doc.updated)}</span>
                </div>
                <div className="flex flex-wrap gap-3">
                  <button
                    type="button"
                    className="rounded-full border border-slate-200 px-4 py-2 text-sm font-semibold text-slate-700 hover:border-slate-400"
                    onClick={() => handleSelectDocument(doc)}
                  >
                    Open details
                  </button>
                  {doc.artifact ? (
                    <a
                      href={getArtifactUrl(doc.artifact)}
                      className="rounded-full border border-slate-200 px-4 py-2 text-sm font-semibold text-slate-700 hover:border-slate-400"
                      target="_blank"
                      rel="noopener noreferrer"
                    >
                      Download artifact
                    </a>
                  ) : null}
                </div>
              </div>
            ))}
          </div>
        ) : (
          <p className="text-sm text-slate-500">No documents yet. Start by creating a new document.</p>
        )}
      </GlassCard>

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

export default function WorkspacePage() {
  return (
    <div className="space-y-12">
      <section className="space-y-6 rounded-[32px] border border-white/25 bg-gradient-to-br from-slate-900 via-blue-900 to-sky-700 p-10 text-white shadow-[0_45px_140px_rgba(15,23,42,0.4)]">
        <p className="text-sm uppercase tracking-[0.35em] text-white/80">Workspace</p>
        <h1 className="text-4xl font-semibold">Operate every document pipeline from one cockpit</h1>
        <p className="text-lg text-white/80">
          Create new jobs, monitor multi-stage timelines, download artifacts, and resume drafts all within the DocWriter workspace. Every action stays synced with Azure queues, blobs, and tables.
        </p>
        <div className="flex flex-wrap gap-4">
          <a
            href="#intake"
            className="rounded-full bg-white px-8 py-3 text-base font-semibold text-slate-900 shadow-lg transition hover:bg-slate-100"
          >
            Create new document
          </a>
          <span className="inline-flex items-center rounded-full border border-white/50 px-6 py-3 text-base text-white/80">
            Track live status, tokens, and artifacts in real time
          </span>
        </div>
        <dl className="grid gap-6 text-white/75 sm:grid-cols-3">
          <div>
            <dt className="text-xs uppercase tracking-[0.3em]">Stages</dt>
            <dd className="mt-2 text-3xl font-semibold text-white">8</dd>
          </div>
          <div>
            <dt className="text-xs uppercase tracking-[0.3em]">Artifacts per job</dt>
            <dd className="mt-2 text-3xl font-semibold text-white">10+</dd>
          </div>
          <div>
            <dt className="text-xs uppercase tracking-[0.3em]">Live metrics</dt>
            <dd className="mt-2 text-3xl font-semibold text-white">Cycle-aware</dd>
          </div>
        </dl>
      </section>

      <JobDashboard />
    </div>
  );
}
