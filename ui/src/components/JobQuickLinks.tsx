import { FC, ReactNode } from "react";
import { MetadataEntry, MetadataGrid } from "@/components/MetadataGrid";

type JobQuickLinksProps = {
  jobId: string | null;
  documentTitle?: string | null;
  statusStage?: string | null;
  statusCycle?: number | null;
  metadata: MetadataEntry[];
  statusMessage?: string | null;
  artifactActions: ReactNode;
  artifactNotice?: string | null;
};

export const JobQuickLinks: FC<JobQuickLinksProps> = ({
  jobId,
  documentTitle,
  statusStage,
  statusCycle,
  metadata,
  statusMessage,
  artifactActions,
  artifactNotice,
}) => (
  <div className="rounded-3xl border border-white/60 bg-white/80 px-3 py-4 shadow-lg shadow-indigo-100/40 sm:px-6 sm:py-6">
    <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
      <div>
        <p className="text-[11px] font-semibold uppercase tracking-[0.22em] text-indigo-400/80 sm:text-xs sm:tracking-[0.35em]">
          Active Job
        </p>
        {documentTitle ? (
          <p className="mt-2 text-[15px] font-semibold text-slate-700 sm:text-base">{documentTitle}</p>
        ) : null}
        <h3 className="mt-1 text-base font-semibold text-slate-800 sm:text-xl">Pipeline snapshot</h3>
        <p className="hidden text-xs text-slate-500 sm:block">We’ll update this view as workers report back.</p>
      </div>
      <div className="flex flex-wrap items-center gap-2 text-sm sm:gap-3">
        <span className="rounded-full border border-slate-200 bg-white px-3 py-1 text-xs font-semibold text-slate-700 shadow-sm sm:px-4 sm:text-sm">
          {statusStage ?? "Pending"}
        </span>
        {statusCycle ? (
          <span className="rounded-full border border-indigo-200 bg-indigo-50 px-3 py-1 text-xs text-indigo-600 shadow-sm sm:px-4 sm:text-sm">
            Cycle {statusCycle}
          </span>
        ) : null}
      </div>
    </div>

    <div className="mt-4 grid gap-3 lg:mt-6 lg:grid-cols-2 lg:gap-4">
      <div className="rounded-2xl border border-white/70 bg-white px-4 py-3 shadow-sm shadow-slate-200/50 sm:px-5 sm:py-4">
        <p className="text-[11px] uppercase tracking-[0.22em] text-slate-400 sm:text-xs sm:tracking-[0.32em]">Job ID</p>
        <p className="mt-2 break-words font-mono text-sm text-slate-700">{jobId}</p>
      </div>
      <div className="rounded-2xl border border-white/70 bg-gradient-to-r from-indigo-50 via-white to-sky-50 px-4 py-3 shadow-sm shadow-slate-200/50 sm:px-5 sm:py-4">
        <p className="text-[11px] uppercase tracking-[0.22em] text-slate-400 sm:text-xs sm:tracking-[0.32em]">Current Stage</p>
        <p className="mt-1 text-base font-semibold text-slate-800 sm:mt-2 sm:text-lg">{statusStage ?? "Pending"}</p>
        {statusMessage && metadata.length === 0 ? (
          <p className="mt-1 text-xs text-slate-500">{statusMessage}</p>
        ) : null}
      </div>
    </div>

    {metadata.length > 0 ? (
      <>
        <div className="mt-4 rounded-2xl border border-slate-100 bg-white/80 px-4 py-3 shadow-sm sm:hidden">
          <MetadataGrid
            entries={metadata}
            className="grid-cols-1 gap-y-2 text-[11px]"
            itemClassName="flex flex-col gap-1 border-b border-slate-100 pb-2 last:border-b-0 last:pb-0"
          />
        </div>
        <div className="mt-6 hidden gap-4 md:grid md:grid-cols-2">
          {metadata.map(({ label, value }) => (
            <div
              key={`quick-metadata-${label}`}
              className="rounded-2xl border border-slate-100 bg-white px-4 py-3 shadow-sm shadow-slate-200/40"
            >
              <p className="text-[10px] font-semibold uppercase tracking-[0.3em] text-slate-400">{label}</p>
              <p className="mt-2 break-words text-sm font-medium text-slate-800">{value}</p>
            </div>
          ))}
        </div>
      </>
    ) : !statusMessage ? (
      <p className="mt-6 text-sm text-slate-500">Waiting for the first worker update...</p>
    ) : null}

    <div className="mt-4 space-y-3 sm:mt-6">
      {metadata.length === 0 && statusMessage ? (
        <p className="text-sm text-slate-500">{statusMessage}</p>
      ) : null}
      <div className="rounded-2xl border border-slate-100 bg-white px-4 py-3 shadow-inner shadow-white/50">
        <p className="text-xs font-semibold uppercase tracking-[0.26em] text-slate-400 sm:tracking-[0.3em]">
          Artifacts
        </p>
        <div className="mt-3">{artifactActions}</div>
        {artifactNotice ? <p className="mt-2 text-xs text-slate-500">{artifactNotice}</p> : null}
      </div>
    </div>
  </div>
);
