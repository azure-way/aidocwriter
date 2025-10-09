"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { GlassCard } from "@/components/GlassCard";
import { GradientTitle } from "@/components/GradientTitle";
import {
  createJob,
  fetchIntakeQuestions,
  fetchJobStatus,
  resumeJob,
} from "@/lib/api";

interface IntakeQuestion {
  id: string;
  q: string;
}

interface StatusPayload {
  job_id: string;
  stage: string;
  artifact?: string;
  message?: string;
  cycle?: number;
}

const POLL_INTERVAL_MS = 5000;

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
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!jobId) return;
    const controller = new AbortController();

    async function poll() {
      try {
        const payload = await fetchJobStatus(jobId);
        setStatus(payload);
      } catch (e) {
        console.error(e);
      }
    }

    poll();
    const interval = setInterval(poll, POLL_INTERVAL_MS);
    return () => {
      clearInterval(interval);
      controller.abort();
    };
  }, [jobId]);

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
        defaults[q.id] = "";
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
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to submit answers");
    } finally {
      setLoading(false);
    }
  }, [answers, title, audience, cycles]);

  const disableSubmit = useMemo(() => {
    return Object.values(answers).some((ans) => !ans.trim());
  }, [answers]);

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
                <p className="text-sm text-slate-500">Waiting for the first worker update...</p>
              )}
              {status?.artifact && (
                <a
                  className={`${primaryButtonClass} inline-flex items-center gap-2`}
                  href={status.artifact}
                  target="_blank"
                  rel="noreferrer"
                >
                  View latest artifact
                </a>
              )}
            </div>
          </GlassCard>
        </div>
      )}
    </section>
  );
}
