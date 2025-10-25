import { FC, ReactNode } from "react";
import { MetadataEntry } from "@/components/MetadataGrid";

type JobQuickLinksProps = {
  jobId: string | null;
  statusStage?: string | null;
  statusCycle?: number | null;
  metadata: MetadataEntry[];
  statusMessage?: string | null;
  artifactActions: ReactNode;
  artifactNotice?: string | null;
};

export const JobQuickLinks: FC<JobQuickLinksProps> = ({
  jobId,
  statusStage,
  statusCycle,
  metadata,
  statusMessage,
  artifactActions,
  artifactNotice,
}) => (
  <div className="rounded-3xl border border-white/60 bg-white/80 px-6 py-6 shadow-lg shadow-indigo-100/40">
    <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
      <div>
        <p className="text-xs font-semibold uppercase tracking-[0.35em] text-indigo-400/80">Active Job</p>
        <h3 className="mt-1 text-xl font-semibold text-slate-800">Pipeline snapshot</h3>
        <p className="text-xs text-slate-500">We’ll update this view as workers report back.</p>
      </div>
      <div className="flex flex-wrap items-center gap-3 text-sm">
        <span className="rounded-full border border-slate-200 bg-white px-4 py-1 font-semibold text-slate-700 shadow-sm">
          {statusStage ?? "Pending"}
        </span>
        {statusCycle ? (
          <span className="rounded-full border border-indigo-200 bg-indigo-50 px-4 py-1 text-indigo-600 shadow-sm">
            Cycle {statusCycle}
          </span>
        ) : null}
      </div>
    </div>

    <div className="mt-6 grid gap-4 lg:grid-cols-2">
      <div className="rounded-2xl border border-white/70 bg-white px-5 py-4 shadow-sm shadow-slate-200/50">
        <p className="text-xs uppercase tracking-[0.32em] text-slate-400">Job ID</p>
        <p className="mt-2 break-words font-mono text-sm text-slate-700">{jobId}</p>
      </div>
      <div className="rounded-2xl border border-white/70 bg-gradient-to-r from-indigo-50 via-white to-sky-50 px-5 py-4 shadow-sm shadow-slate-200/50">
        <p className="text-xs uppercase tracking-[0.32em] text-slate-400">Current Stage</p>
        <p className="mt-2 text-lg font-semibold text-slate-800">{statusStage ?? "Pending"}</p>
        {statusMessage && metadata.length === 0 ? (
          <p className="mt-1 text-xs text-slate-500">{statusMessage}</p>
        ) : null}
      </div>
    </div>

    {metadata.length > 0 ? (
      <div className="mt-6 grid gap-4 md:grid-cols-2">
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
    ) : !statusMessage ? (
      <p className="mt-6 text-sm text-slate-500">Waiting for the first worker update...</p>
    ) : null}

    <div className="mt-6 space-y-3">
      {metadata.length === 0 && statusMessage ? (
        <p className="text-sm text-slate-500">{statusMessage}</p>
      ) : null}
      <div className="rounded-2xl border border-slate-100 bg-white px-4 py-3 shadow-inner shadow-white/50">
        <p className="text-xs font-semibold uppercase tracking-[0.3em] text-slate-400">Artifacts</p>
        <div className="mt-3">{artifactActions}</div>
        {artifactNotice ? <p className="mt-2 text-xs text-slate-500">{artifactNotice}</p> : null}
      </div>
    </div>
  </div>
);
