import { MetadataEntry } from "@/components/MetadataGrid";

export type StagePhase = "queued" | "in_progress" | "complete" | "failed" | "unknown";

export interface TimelineEvent {
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

export type StageTimelineItem = {
  key: string;
  label: string;
  ts?: number | string | null;
};

export type StageCycleDetail = {
  cycle: number;
  status: StagePhase;
  metadataEntries: MetadataEntry[];
  timeline: StageTimelineItem[];
  completionTs?: number | string | null;
  lastUpdateTs?: number | string | null;
};

export type CombinedCycleDetail = {
  cycle: number;
  substeps: Array<{
    stage:
      | "REVIEW"
      | "REVIEW_GENERAL"
      | "REVIEW_STYLE"
      | "REVIEW_COHESION"
      | "REVIEW_SUMMARY"
      | "VERIFY"
      | "REWRITE";
    label: string;
    detail: StageCycleDetail;
  }>;
};

export const CYCLE_AWARE_STAGES = ["REVIEW", "VERIFY", "REWRITE"] as const;
export const CYCLE_AWARE_STAGE_SET = new Set<string>(CYCLE_AWARE_STAGES);

export const cycleStatusStyles: Record<StagePhase, { badge: string; container: string }> = {
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

export const normalizeStageName = (value: string): string => {
  const base = value.replace(/_(DONE|START|QUEUED|FAILED|ERROR|IN_PROGRESS)$/u, "");
  if (
    base === "REVIEW_GENERAL" ||
    base === "REVIEW_STYLE" ||
    base === "REVIEW_COHESION" ||
    base === "REVIEW_SUMMARY"
  ) {
    return "REVIEW";
  }
  if (base === "INTAKE_RESUMED") {
    return "INTAKE_RESUME";
  }
  return base;
};

export const determineEventPhase = (event: TimelineEvent | undefined): StagePhase => {
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
  if (/_START$/u.test(stage) || /_IN_PROGRESS$/u.test(stage)) {
    return "in_progress";
  }
  if (/_QUEUED$/u.test(stage)) {
    return "queued";
  }
  return "complete";
};

export const stagePhaseLabel = (phase: StagePhase): string => {
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

export const cycleStatusLabel = (phase: StagePhase, stageLabel: string): string => {
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
