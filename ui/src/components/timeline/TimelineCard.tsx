import { FC, ReactNode } from "react";
type TimelineCardProps = {
  totalEvents: number;
  renderedStages: ReactNode[];
  showPendingMessage: boolean;
};

export const TimelineCard: FC<TimelineCardProps> = ({
  totalEvents,
  renderedStages,
  showPendingMessage,
}) => (
  <div className="rounded-3xl border border-white/70 bg-white/80 px-4 py-5 shadow-inner shadow-white/30 sm:px-6 sm:py-6">
    <div className="flex items-center justify-between">
      <p className="text-xs uppercase tracking-[0.3em] text-slate-400 sm:tracking-[0.38em]">Timeline</p>
      <span className="text-xs text-slate-500">{totalEvents} events</span>
    </div>
    <div className="mt-4 space-y-4">
      <div className="space-y-3">{renderedStages}</div>
      {showPendingMessage ? (
        <p className="text-sm text-slate-500">
          Timeline updates will appear here as the pipeline progresses.
        </p>
      ) : null}
    </div>
  </div>
);
