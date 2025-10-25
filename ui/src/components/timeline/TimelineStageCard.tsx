import { Dispatch, FC, ReactNode, SetStateAction } from "react";
import {
  CombinedCycleDetail,
  cycleStatusLabel,
  cycleStatusStyles,
  StageCycleDetail,
  StagePhase,
  TimelineEvent,
} from "@/lib/timeline";
import { MetadataEntry, MetadataGrid } from "@/components/MetadataGrid";
import { TimelineStageDetails } from "./TimelineStageDetails";

type ExpansionState = Record<number, boolean>;
type SubstepExpansionState = Record<number, Record<string, boolean>>;
type SummaryExpansionState = Record<string, boolean>;

type TimelineStageCardProps = {
  event: TimelineEvent;
  index: number;
  stageBase: string;
  formatStage: (stage: string) => string;
  formatTimestamp: (ts?: number | string | null) => string;
  getMetadataEntries: (event: TimelineEvent) => MetadataEntry[];
  renderArtifactActions: (path: string, size?: "sm" | "md") => ReactNode;
  combinedReviewCycles: CombinedCycleDetail[];
  cycleDetailsByStage: Map<string, StageCycleDetail[]>;
  expandedSummaryStages: SummaryExpansionState;
  setExpandedSummaryStages: Dispatch<SetStateAction<SummaryExpansionState>>;
  expandedCycles: ExpansionState;
  setExpandedCycles: Dispatch<SetStateAction<ExpansionState>>;
  expandedSubsteps: SubstepExpansionState;
  setExpandedSubsteps: Dispatch<SetStateAction<SubstepExpansionState>>;
};

const getBadgeClass = (status: "complete" | "active" | "pending") => {
  if (status === "complete") {
    return "bg-indigo-500 text-white";
  }
  if (status === "active") {
    return "border border-indigo-300 bg-indigo-50 text-indigo-600";
  }
  return "bg-white border border-slate-200 text-slate-400";
};

export const TimelineStageCard: FC<TimelineStageCardProps> = ({
  event,
  index,
  stageBase,
  formatStage,
  formatTimestamp,
  getMetadataEntries,
  renderArtifactActions,
  combinedReviewCycles,
  cycleDetailsByStage,
  expandedSummaryStages,
  setExpandedSummaryStages,
  expandedCycles,
  setExpandedCycles,
  expandedSubsteps,
  setExpandedSubsteps,
}) => {
  const status = event.status ?? (event.pending ? "pending" : "complete");
  const completed = status === "complete";
  const active = status === "active";
  const label = event.displayStage ?? formatStage(event.stage);
  const statusLabel = completed ? "Completed" : active ? "Running" : "Not started";
  const secondaryText =
    (completed || active) && event.ts != null
      ? `${statusLabel} • ${formatTimestamp(event.ts)}`
      : statusLabel;
  const badgeClass = getBadgeClass(status);
  const metadataEntries = getMetadataEntries(event);
  const tokensEntry = metadataEntries.find(({ label: entryLabel }) => entryLabel.toLowerCase() === "tokens");
  const tokensDisplay = tokensEntry?.value ?? null;
  const stageKey = stageBase;
  const isStageExpanded = expandedSummaryStages[stageKey] ?? false;
  const toggleStageExpansion = () =>
    setExpandedSummaryStages((prev) => ({
      ...prev,
      [stageKey]: !isStageExpanded,
    }));

  if (stageBase === "REVIEW") {
    const reviewCycles = combinedReviewCycles;
    const stageCycleLabel = formatStage(stageBase);
    const showCycles = reviewCycles.length > 0;
    const totalCycles = reviewCycles.length;

    const isSubstepComplete = (substep: CombinedCycleDetail["substeps"][number]) => {
      if (substep.detail.status === "complete") {
        return true;
      }
      if (
        substep.stage === "REWRITE" &&
        substep.detail.status === "queued" &&
        substep.detail.timeline.length === 1 &&
        substep.detail.timeline[0].label === "Not started"
      ) {
        return true;
      }
      return false;
    };

    const isCycleComplete = (cycleDetail: CombinedCycleDetail) => cycleDetail.substeps.every(isSubstepComplete);

    const completedCycles = showCycles ? reviewCycles.filter(isCycleComplete).length : 0;
    const runningCycleNumber = reviewCycles.find((cycleDetail) =>
      cycleDetail.substeps.some((sub) => sub.detail.status === "in_progress")
    )?.cycle;
    const failedCycleNumber = reviewCycles.find((cycleDetail) =>
      cycleDetail.substeps.some((sub) => sub.detail.status === "failed")
    )?.cycle;

    const sourceStageLabel =
      active && event.sourceStage && event.sourceStage !== event.stage ? formatStage(event.sourceStage) : undefined;

    return (
      <div className="flex items-start gap-4 rounded-2xl bg-white/70 px-4 py-3 shadow-sm">
        <span className={`flex h-8 w-8 items-center justify-center rounded-full text-sm	font-semibold ${badgeClass}`}>
          {index + 1}
        </span>
        <div className="flex-1 space-y-3">
          <button
            type="button"
            className="flex w-full items-start justify-between text-left"
            onClick={toggleStageExpansion}
          >
            <div>
              <p className="text-sm font-semibold text-slate-700">{label}</p>
              <p className="text-xs text-slate-500">{secondaryText}</p>
              {tokensDisplay ? <p className="mt-1 text-xs text-slate-500">Tokens: {tokensDisplay}</p> : null}
            </div>
            <span className="text-lg text-slate-500">{isStageExpanded ? "−" : "+"}</span>
          </button>
          {isStageExpanded ? (
            <TimelineStageDetails
              sourceStageLabel={sourceStageLabel}
              showSourceStage={Boolean(sourceStageLabel)}
              metadataEntries={metadataEntries}
              message={event.message}
              showMessage={completed || active}
              artifact={event.artifact}
              renderArtifactActions={renderArtifactActions}
            >
              {showCycles ? (
                <>
                  <div className="mt-3 flex flex-wrap gap-2 text-xs">
                    <span className="rounded-full border border-slate-200 bg-white px-3 py-1 text-slate-600">
                      {completedCycles}/{totalCycles} cycles complete
                    </span>
                    {runningCycleNumber ? (
                      <span className="rounded-full border border-indigo-200 bg-indigo-50 px-3 py-1 text-indigo-600">
                        Running cycle: {runningCycleNumber}
                      </span>
                    ) : null}
                    {failedCycleNumber ? (
                      <span className="rounded-full border border-rose-200 bg-rose-50 px-3 py-1 text-rose-700">
                        Attention: Cycle {failedCycleNumber}
                      </span>
                    ) : null}
                  </div>
                  <div className="space-y-3">
                    {reviewCycles.map((cycleDetail) => {
                      const cycleStatus: StagePhase = cycleDetail.substeps.some(
                        (sub) => sub.detail.status === "failed"
                      )
                        ? "failed"
                        : cycleDetail.substeps.some((sub) => sub.detail.status === "in_progress")
                        ? "in_progress"
                        : isCycleComplete(cycleDetail)
                        ? "complete"
                        : "queued";
                      const statusStyle = cycleStatusStyles[cycleStatus] ?? cycleStatusStyles.unknown;
                      const statusChipLabel = cycleStatusLabel(cycleStatus, stageCycleLabel);
                      const isCycleExpanded = expandedCycles[cycleDetail.cycle] ?? false;
                      return (
                        <div
                          key={`cycle-${cycleDetail.cycle}`}
                          className={`rounded-2xl px-4 py-3 shadow-inner shadow-white/30 transition ${statusStyle.container}`}
                        >
                          <button
                            type="button"
                            className="flex w-full items-center justify-between text-left"
                            onClick={() =>
                              setExpandedCycles((prev) => ({
                                ...prev,
                                [cycleDetail.cycle]: !isCycleExpanded,
                              }))
                            }
                          >
                            <div>
                              <p className="text-xs font-semibold uppercase tracking-[0.3em] text-slate-400">
                                {stageCycleLabel} cycle {cycleDetail.cycle}
                              </p>
                              {cycleDetail.substeps.some((sub) => sub.detail.completionTs) ? (
                                <p className="text-xs text-slate-500">
                                  Completed{" "}
                                  {formatTimestamp(
                                    cycleDetail.substeps
                                      .map((sub) => sub.detail.completionTs ?? null)
                                      .filter((value) => value != null)
                                      .sort((a, b) => Number(a ?? 0) - Number(b ?? 0))
                                      .pop() ?? null
                                  )}
                                </p>
                              ) : cycleDetail.substeps.some((sub) => sub.detail.lastUpdateTs) ? (
                                <p className="text-xs text-slate-500">
                                  Last update{" "}
                                  {formatTimestamp(
                                    cycleDetail.substeps
                                      .map((sub) => sub.detail.lastUpdateTs ?? null)
                                      .filter((value) => value != null)
                                      .sort((a, b) => Number(a ?? 0) - Number(b ?? 0))
                                      .pop() ?? null
                                  )}
                                </p>
                              ) : null}
                            </div>
                            <span className={`rounded-full px-3 py-1 text-xs font-medium ${statusStyle.badge}`}>
                              {statusChipLabel}
                            </span>
                            <span className="text-lg text-slate-500">{isCycleExpanded ? "−" : "+"}</span>
                          </button>
                          {isCycleExpanded && (
                            <div className="mt-3 space-y-3 border-t border-slate-100 pt-3">
                              {cycleDetail.substeps.map((substep) => {
                                const subStatus = substep.detail.status;
                                const subStatusStyle =
                                  cycleStatusStyles[subStatus] ?? cycleStatusStyles.unknown;
                                const subStatusLabel = cycleStatusLabel(subStatus, substep.label);
                                const isSubExpanded =
                                  expandedSubsteps[cycleDetail.cycle]?.[substep.stage] ?? false;
                                return (
                                  <div
                                    key={`cycle-${cycleDetail.cycle}-${substep.stage}`}
                                    className="rounded-xl border border-slate-200 bg-white/90 px-4 py-3"
                                  >
                                    <button
                                      type="button"
                                      className="flex w-full items-center justify-between text-left"
                                      onClick={() =>
                                        setExpandedSubsteps((prev) => {
                                          const current = { ...(prev[cycleDetail.cycle] ?? {}) };
                                          current[substep.stage] = !isSubExpanded;
                                          return { ...prev, [cycleDetail.cycle]: current };
                                        })
                                      }
                                    >
                                      <div>
                                        <p className="text-xs font-semibold uppercase tracking-[0.3em] text-slate-400">
                                          {substep.label}
                                        </p>
                                        {substep.detail.completionTs ? (
                                          <p className="text-xs text-slate-500">
                                            Completed {formatTimestamp(substep.detail.completionTs)}
                                          </p>
                                        ) : substep.detail.lastUpdateTs ? (
                                          <p className="text-xs text-slate-500">
                                            Last update {formatTimestamp(substep.detail.lastUpdateTs)}
                                          </p>
                                        ) : null}
                                      </div>
                                      <span
                                        className={`rounded-full px-3 py-1 text-xs font-medium ${subStatusStyle.badge}`}
                                      >
                                        {subStatusLabel}
                                      </span>
                                      <span className="text-lg text-slate-500">
                                        {isSubExpanded ? "−" : "+"}
                                      </span>
                                    </button>
                                    {isSubExpanded && (
                                      <div className="mt-3 space-y-3 border-t border-slate-100 pt-3">
                                        {substep.detail.timeline.length > 0 ? (
                                          <ol className="space-y-2 text-xs text-slate-500">
                                            {substep.detail.timeline.map((item) => (
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
                                        {substep.detail.metadataEntries.length > 0 ? (
                                          <MetadataGrid entries={substep.detail.metadataEntries} />
                                        ) : (
                                          <p className="text-xs text-slate-500">No updates yet.</p>
                                        )}
                                      </div>
                                    )}
                                  </div>
                                );
                              })}
                            </div>
                          )}
                        </div>
                      );
                    })}
                  </div>
                </>
              ) : null}
            </TimelineStageDetails>
          ) : null}
        </div>
      </div>
    );
  }

  const stageCycleDetails = cycleDetailsByStage.get(stageBase) ?? [];
  const showCycles = stageCycleDetails.length > 0;
  const stageCycleLabel = formatStage(stageBase);
  const completedCycles = showCycles ? stageCycleDetails.filter((detail) => detail.status === "complete").length : 0;
  const activeCycleDetail = showCycles ? stageCycleDetails.find((detail) => detail.status === "in_progress") : undefined;
  const failedCycleDetail = showCycles ? stageCycleDetails.find((detail) => detail.status === "failed") : undefined;
  const totalCycles = showCycles ? stageCycleDetails.length : 0;
  const sourceStageLabel =
    active && event.sourceStage && event.sourceStage !== event.stage ? formatStage(event.sourceStage) : undefined;

  return (
    <div className="flex items-start gap-4 rounded-2xl bg-white/70 px-4 py-3 shadow-sm">
      <span className={`flex h-8 w-8 items-center justify-center rounded-full text-sm font-semibold ${badgeClass}`}>
        {index + 1}
      </span>
      <div className="flex-1 space-y-3">
        <button
          type="button"
          className="flex w-full items-start justify-between text-left"
          onClick={toggleStageExpansion}
        >
          <div>
            <p className="text-sm font-semibold text-slate-700">{label}</p>
            <p className="text-xs text-slate-500">{secondaryText}</p>
            {tokensDisplay ? <p className="mt-1 text-xs text-slate-500">Tokens: {tokensDisplay}</p> : null}
          </div>
          <span className="text-lg text-slate-500">{isStageExpanded ? "−" : "+"}</span>
        </button>
        {isStageExpanded ? (
          <TimelineStageDetails
            sourceStageLabel={sourceStageLabel}
            showSourceStage={Boolean(sourceStageLabel)}
            metadataEntries={metadataEntries}
            message={event.message}
            showMessage={completed || active}
            artifact={event.artifact}
            renderArtifactActions={renderArtifactActions}
          >
            {showCycles && totalCycles > 0 ? (
              <>
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
                <div className="space-y-3">
                  {stageCycleDetails.map((detail) => {
                    const statusStyle = cycleStatusStyles[detail.status] ?? cycleStatusStyles.unknown;
                    const statusChipLabel = cycleStatusLabel(detail.status, stageCycleLabel);
                    const isCycleExpanded = expandedCycles[detail.cycle] ?? false;
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
                              [detail.cycle]: !isCycleExpanded,
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
                          <span className={`rounded-full px-3 py-1 text-xs font-medium ${statusStyle.badge}`}>
                            {statusChipLabel}
                          </span>
                          <span className="text-lg text-slate-500">{isCycleExpanded ? "−" : "+"}</span>
                        </button>
                        {isCycleExpanded && (
                          <div className="mt-3 space-y-3 border-t border-slate-100 pt-3">
                            {detail.timeline.length > 0 ? (
                              <ol className="space-y-2 text-xs text-slate-500">
                                {detail.timeline.map((item) => (
                                  <li key={item.key} className="flex items-center justify-between gap-3">
                                    <span className="font-semibold text-slate-600">{item.label}</span>
                                    <span>{item.ts ? formatTimestamp(item.ts) : "—"}</span>
                                  </li>
                                ))}
                              </ol>
                            ) : null}
                            {detail.metadataEntries.length > 0 ? (
                              <MetadataGrid entries={detail.metadataEntries} />
                            ) : (
                              <p className="text-xs text-slate-500">No updates yet.</p>
                            )}
                          </div>
                        )}
                      </div>
                    );
                  })}
                </div>
              </>
            ) : null}
          </TimelineStageDetails>
        ) : null}
      </div>
    </div>
  );
};
