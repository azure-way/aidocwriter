"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";
import { GlassCard } from "@/components/GlassCard";
import { useUser } from "@auth0/nextjs-auth0/client";
import { downloadArtifact, downloadDiagramArchive, fetchDocuments, resumeJob } from "@/lib/api";
import { determineEventPhase, normalizeStageName } from "@/lib/timeline";

interface DocumentSummary {
  job_id: string;
  title?: string;
  audience?: string;
  stage?: string;
  message?: string;
  updated?: number;
  artifact?: string;
  cycles_requested?: number;
  cycles_completed?: number;
  has_error?: boolean;
  last_error?: string;
}

type StageFilter = "all" | "active" | "completed" | "error";

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

function formatTimestamp(value?: number) {
  if (!value && value !== 0) return "—";
  return new Date(Number(value) * 1000).toLocaleString();
}

export default function WorkspacePage() {
  const { user } = useUser();
  const [documents, setDocuments] = useState<DocumentSummary[]>([]);
  const [documentsLoading, setDocumentsLoading] = useState(false);
  const [documentsError, setDocumentsError] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState("");
  const [stageFilter, setStageFilter] = useState<StageFilter>("all");
  const [resumeJobId, setResumeJobId] = useState<string | null>(null);
  const totalStages = SUMMARY_STAGE_ORDER.length;
  const resolveFileBaseName = useCallback((doc?: DocumentSummary, fallback?: string) => {
    const raw = (doc?.title && doc.title.trim()) || (fallback ?? "");
    const safe = raw || "artifact";
    return safe.replace(/\s+/g, "-");
  }, []);

  const refreshDocuments = useCallback(async () => {
    if (!user?.sub) {
      setDocuments([]);
      return;
    }
    setDocumentsLoading(true);
    try {
      const data = await fetchDocuments();
      setDocuments(data.documents ?? []);
      setDocumentsError(null);
    } catch (err) {
      setDocumentsError(err instanceof Error ? err.message : "Failed to load documents");
    } finally {
      setDocumentsLoading(false);
    }
  }, [user?.sub]);

  useEffect(() => {
    refreshDocuments();
  }, [refreshDocuments]);

  const handleResumeDocument = useCallback(
    async (doc: DocumentSummary) => {
      setResumeJobId(doc.job_id);
      try {
        await resumeJob(doc.job_id, {});
        await refreshDocuments();
      } catch (err) {
        console.error(err);
      } finally {
        setResumeJobId(null);
      }
    },
    [refreshDocuments]
  );

  const downloadArtifactFile = useCallback(async (doc: DocumentSummary, path: string) => {
    try {
      const { blob, fileName, contentType } = await downloadArtifact(doc.job_id, path);
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
      const baseName = resolveFileBaseName(doc, doc.job_id);
      const resolvedName = ext ? `${baseName}.${ext}` : baseName;
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = resolvedName;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      URL.revokeObjectURL(url);
    } catch (err) {
      console.error(err);
    }
  }, [resolveFileBaseName]);

  const downloadDiagramArchiveFile = useCallback(async (doc: DocumentSummary) => {
    try {
      const { blob } = await downloadDiagramArchive(doc.job_id);
      const baseName = `${resolveFileBaseName(doc, doc.job_id)}-diagrams`;
      const resolvedName = `${baseName}.zip`;
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = resolvedName;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      URL.revokeObjectURL(url);
    } catch (err) {
      console.error(err);
    }
  }, [resolveFileBaseName]);

  const filteredDocuments = useMemo(() => {
    const query = searchQuery.trim().toLowerCase();
    return documents.filter((doc) => {
      const stageUpper = (doc.stage ?? "").toUpperCase();
      const completed = stageUpper.startsWith("FINALIZE") || stageUpper === "FINALIZE_DONE";
      const errored = Boolean(doc.has_error || stageUpper.endsWith("_FAILED"));
      const matchesFilter =
        stageFilter === "all" ||
        (stageFilter === "completed" && completed && !errored) ||
        (stageFilter === "error" && errored) ||
        (stageFilter === "active" && !completed && !errored);
      if (!matchesFilter) return false;
      if (!query) return true;
      const haystack = `${doc.title ?? ""} ${doc.message ?? ""} ${doc.stage ?? ""}`.toLowerCase();
      return haystack.includes(query);
    });
  }, [documents, searchQuery, stageFilter]);

  return (
    <div className="space-y-12">
      <section className="space-y-6 rounded-[32px] border border-white/25 bg-gradient-to-br from-slate-900 via-blue-900 to-sky-700 p-10 text-white shadow-[0_45px_140px_rgba(15,23,42,0.4)]">
        <p className="text-sm uppercase tracking-[0.35em] text-white/80">Workspace</p>
        <h1 className="text-4xl font-semibold">Operate every document pipeline from one cockpit</h1>
        <p className="text-lg text-white/80">
          Track live status, download artifacts, and resume stalled documents. Create new jobs from the dedicated form when you need fresh deliverables.
        </p>
        <div className="flex flex-wrap gap-4">
          <Link
            href="/newdocument"
            className="rounded-full bg-white px-8 py-3 text-base font-semibold text-slate-900 shadow-lg transition hover:bg-slate-100"
          >
            Create new document
          </Link>
          <span className="inline-flex items-center rounded-full border border-white/50 px-6 py-3 text-base text-white/80">
            Track live status, tokens, and artifacts in real time
          </span>
        </div>
      </section>

      <GlassCard className="space-y-6">
        <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <p className="text-xs uppercase tracking-[0.4em] text-slate-500">Documents</p>
            <h2 className="text-2xl font-semibold text-slate-900">Your document workspace</h2>
            <p className="text-sm text-slate-500">Filter by status, search titles, and resume runs that need attention.</p>
          </div>
          <div className="flex flex-wrap gap-3">
            <button
              type="button"
              className="rounded-full border border-slate-200 px-4 py-2 text-sm font-semibold text-slate-700 hover:border-slate-400"
              onClick={refreshDocuments}
              disabled={documentsLoading}
            >
              {documentsLoading ? "Refreshing…" : "Refresh list"}
            </button>
            <Link href="/newdocument" className="btn-primary">
              New document
            </Link>
          </div>
        </div>
        <div className="flex flex-col gap-3 md:flex-row md:items-stretch">
          <input
            className="input-glass w-full md:flex-[3]"
            placeholder="Search title, stage, or notes"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
          />
          <select
            className="input-glass w-full md:flex-[1] md:min-w-[14rem]"
            value={stageFilter}
            onChange={(e) => setStageFilter(e.target.value as StageFilter)}
          >
            <option value="all">All documents</option>
            <option value="active">Active</option>
            <option value="completed">Completed</option>
            <option value="error">Needs attention</option>
          </select>
        </div>
        {documentsError ? <p className="text-sm text-red-500">{documentsError}</p> : null}
        {documentsLoading && !documents.length ? (
          <p className="text-sm text-slate-500">Loading documents…</p>
        ) : filteredDocuments.length ? (
          <div className="space-y-3">
            {filteredDocuments.map((doc) => {
              const stageUpper = (doc.stage ?? "").toUpperCase();
              const stageLabel = doc.stage ? doc.stage.replace(/_/g, " ") : "Pending";
              const completed = stageUpper.startsWith("FINALIZE") || stageUpper === "FINALIZE_DONE";
              const errored = Boolean(doc.has_error || stageUpper.endsWith("_FAILED"));
              const normalizedStage = doc.stage ? normalizeStageName(stageUpper) : null;
              const isFinalStage = normalizedStage === "FINALIZE";
              const stagePosition = normalizedStage ? SUMMARY_STAGE_ORDER.indexOf(normalizedStage) : -1;
              const stagePhase = determineEventPhase(doc.stage ? { stage: doc.stage } : undefined);
              const completedSteps = (() => {
                if (stagePosition < 0) {
                  return 0;
                }
                if (stagePhase === "complete" || stagePhase === "failed") {
                  return Math.min(totalStages, stagePosition + 1);
                }
                return Math.max(0, stagePosition);
              })();
              const stepsRemaining = Math.max(0, totalStages - completedSteps);
              return (
                <div
                  key={doc.job_id}
                  className="flex flex-col gap-3 rounded-2xl border border-slate-100/80 bg-white/70 px-4 py-4 text-slate-800 shadow-[0_15px_50px_rgba(15,23,42,0.08)]"
                >
                  <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
                    <div>
                      <p className="text-base font-semibold text-slate-900">{doc.title || "Untitled document"}</p>
                      <p className="text-sm text-slate-500">{doc.message || "No updates yet"}</p>
                    </div>
                    <div className="flex flex-wrap items-center gap-2">
                      <span
                        className={`rounded-full px-3 py-1 text-xs font-semibold ${errored ? "bg-red-100 text-red-700" : completed ? "bg-emerald-100 text-emerald-700" : "bg-slate-100 text-slate-700"}`}
                      >
                        {stageLabel}
                      </span>
                      <span className="text-xs text-slate-500">{formatTimestamp(doc.updated)}</span>
                    </div>
                  </div>
                  <div className="flex flex-wrap items-center gap-2 text-xs text-slate-500">
                    <span>
                      <span className="font-semibold text-slate-700">{completedSteps}</span> of {totalStages} steps completed
                    </span>
                    <span className="text-slate-400">•</span>
                    <span>
                      <span className="font-semibold text-slate-700">{stepsRemaining}</span> left
                    </span>
                  </div>
                  {doc.last_error && <p className="rounded-xl bg-red-50 px-3 py-2 text-sm text-red-600">{doc.last_error}</p>}
                  <div className="flex flex-wrap gap-3">
                    <Link
                      href={`/job/${encodeURIComponent(doc.job_id)}`}
                      className="rounded-full border border-slate-200 px-4 py-2 text-sm font-semibold text-slate-700 hover:border-slate-400"
                    >
                      View timeline
                    </Link>
                    {doc.artifact ? (
                      <button
                        type="button"
                        className="rounded-full border border-slate-200 px-4 py-2 text-sm font-semibold text-slate-700 hover:border-slate-400"
                        onClick={() => downloadArtifactFile(doc, doc.artifact!)}
                      >
                        Download artifact
                      </button>
                    ) : null}
                    {doc.artifact && isFinalStage ? (
                      <button
                        type="button"
                        className="rounded-full border border-slate-200 px-4 py-2 text-sm font-semibold text-slate-700 hover:border-slate-400"
                        onClick={() => downloadDiagramArchiveFile(doc)}
                      >
                        Download diagrams
                      </button>
                    ) : null}
                    {errored ? (
                      <button
                        type="button"
                        className="rounded-full border border-slate-200 px-4 py-2 text-sm font-semibold text-slate-700 hover:border-slate-400"
                        onClick={() => handleResumeDocument(doc)}
                        disabled={resumeJobId === doc.job_id}
                      >
                        {resumeJobId === doc.job_id ? "Resuming…" : "Resume"}
                      </button>
                    ) : null}
                  </div>
                </div>
              );
            })}
          </div>
        ) : (
          <p className="text-sm text-slate-500">No documents yet. Start by creating a new document.</p>
        )}
      </GlassCard>
    </div>
  );
}
