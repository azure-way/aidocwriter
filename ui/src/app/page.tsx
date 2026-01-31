import Link from "next/link";

const benefits = [
  {
    title: "Accelerated delivery",
    description: "DocWriter orchestrates planners, writers, and reviewers in parallel so 60+ page deliverables arrive days faster than manual workflows.",
  },
  {
    title: "Audit-ready output",
    description: "Every stage emits artifacts, metrics, and timestamps, giving stakeholders confidence in quality and compliance.",
  },
  {
    title: "Azure-first architecture",
    description: "All data, queues, and storage run on Azure services—ideal for enterprise security and governance.",
  },
];

const capabilities = [
  {
    label: "Intelligent Intake",
    copy: "LLM-powered interviews capture scope, audience, and constraints without lengthy kickoff meetings.",
  },
  {
    label: "Coordinated Planning",
    copy: "Planner agents decompose work into sections, diagrams, and research tracks ready for generation.",
  },
  {
    label: "Multistage Writing",
    copy: "Writer, reviewer, and verifier agents iterate until guidance, tone, and factual checks align.",
  },
  {
    label: "Diagram Automation",
    copy: "Diagram prep and rendering functions convert textual specs into PlantUML diagrams inside each deliverable.",
  },
  {
    label: "Artifact Management",
    copy: "Markdown, PDF, DOCX, and diagram assets stay versioned in Azure Blob Storage and surface instantly in the workspace.",
  },
  {
    label: "Performance Telemetry",
    copy: "Live metrics expose token use, stage durations, and worker health for every document pipeline.",
  },
];

export default function HomePage() {
  return (
    <div className="space-y-24">
      <section className="space-y-12 rounded-[32px] border border-white/20 bg-gradient-to-br from-slate-900 via-blue-900 to-sky-700 p-10 text-white shadow-[0_45px_140px_rgba(15,23,42,0.45)]">
        <div className="grid gap-12 lg:grid-cols-[1.1fr_0.9fr]">
          <div className="space-y-8">
            <p className="text-sm uppercase tracking-[0.35em] text-white/70">DocWriter Studio</p>
            <h1 className="font-heading text-4xl font-semibold sm:text-5xl">
              Large-scale document creation orchestrated by AI and Azure
            </h1>
            <p className="text-lg text-white/80">
              Launch research-heavy technical documents with confidence. DocWriter coordinates intake, planning, writing, verification, and diagramming agents so your teams focus on decisions—not formatting.
            </p>
            <div className="flex flex-wrap gap-4">
              <Link href="/workspace" className="rounded-full bg-white px-8 py-3 text-base font-semibold text-slate-900 shadow-lg transition hover:bg-slate-100">
                Explore workspace
              </Link>
              <Link
                href="/features"
                className="rounded-full border border-white/60 px-8 py-3 text-base font-medium text-white transition hover:bg-white/10"
              >
                View full feature list
              </Link>
            </div>
            <dl className="mt-6 grid gap-6 text-white/80 sm:grid-cols-3">
              <div>
                <dt className="text-xs uppercase tracking-[0.3em]">Avg. delivery speed</dt>
                <dd className="mt-2 text-3xl font-semibold text-white">10 minutes</dd>
              </div>
              <div>
                <dt className="text-xs uppercase tracking-[0.3em]">Pages per document</dt>
                <dd className="mt-2 text-3xl font-semibold text-white">+50</dd>
              </div>
              <div>
                <dt className="text-xs uppercase tracking-[0.3em]">AI agents involved</dt>
                <dd className="mt-2 text-3xl font-semibold text-white">10</dd>
              </div>
            </dl>
          </div>
          <div className="space-y-6 rounded-3xl border border-white/20 bg-white/10 p-8">
            <p className="text-sm uppercase tracking-[0.35em] text-white/80">Benefits</p>
            <ul className="space-y-5 text-base text-white/85">
              {benefits.map((benefit) => (
                <li key={benefit.title} className="rounded-2xl bg-slate-900/30 p-5">
                  <p className="font-semibold text-white">{benefit.title}</p>
                  <p className="mt-2 text-sm text-white/80">{benefit.description}</p>
                </li>
              ))}
            </ul>
          </div>
        </div>

        <div className="space-y-4">
          <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
            <div>
              <p className="text-xs uppercase tracking-[0.4em] text-white/70">Capabilities</p>
              <h2 className="mt-2 text-3xl font-semibold">End-to-end orchestration at enterprise scale</h2>
            </div>
            <Link href="/workspace" className="text-sm font-semibold text-white hover:text-white/80">
              See it in action →
            </Link>
          </div>
          <div className="grid gap-6 md:grid-cols-2">
            {capabilities.map((capability) => (
              <article key={capability.label} className="rounded-3xl bg-white/85 p-6 text-slate-900 shadow-[0_35px_90px_rgba(15,23,42,0.35)]">
                <h3 className="text-xl font-semibold">{capability.label}</h3>
                <p className="mt-3 text-base text-slate-600">{capability.copy}</p>
              </article>
            ))}
          </div>
        </div>
      </section>
    </div>
  );
}
