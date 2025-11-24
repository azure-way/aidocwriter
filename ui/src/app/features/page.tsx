import Link from "next/link";

const pillars = [
  {
    title: "Orchestrated pipeline",
    details: "Planner, writer, reviewer, verifier, and diagram agents collaborate through Azure Service Bus queues so every stage stays observable.",
  },
  {
    title: "Integrated diagramming",
    details: "Diagram prep services convert architecture prompts into PlantUML renderings and embed them alongside narrative sections.",
  },
  {
    title: "Artifact lifecycle",
    details: "Each job stores answers, drafts, rewrites, final Markdown, PDF, DOCX, and diagrams in Azure Blob Storage for instant download.",
  },
  {
    title: "Telemetry & governance",
    details: "Every run emits tokens, durations, and status events into Azure Tables so teams can audit progress and performance trends.",
  },
];

const workflow = [
  {
    label: "Intake",
    description: "Auto-generated interviews collect scope, stakeholder, and success criteria within minutes.",
  },
  {
    label: "Planning",
    description: "Planner agents map sections, diagrams, and research packets aligned to your playbooks.",
  },
  {
    label: "Writing",
    description: "Writers, reviewers, and verifiers iterate until tone, guidance, and facts align.",
  },
  {
    label: "Diagramming",
    description: "Dedicated functions prep and render PlantUML diagrams referenced throughout the doc.",
  },
  {
    label: "Finalize",
    description: "Final Markdown, PDF, DOCX, and diagrams land in Azure Blob Storage.",
  },
];

export default function FeaturesPage() {
  return (
    <section className="space-y-12 rounded-[32px] border border-white/25 bg-gradient-to-br from-slate-900 via-indigo-900 to-blue-700 p-10 text-white shadow-[0_45px_140px_rgba(15,23,42,0.45)]">
      <header className="space-y-4">
        <p className="text-sm uppercase tracking-[0.35em] text-white/70">Feature overview</p>
        <h1 className="text-4xl font-semibold">Why teams adopt DocWriter Studio</h1>
        <p className="text-lg text-white/80">
          DocWriter orchestrates Azure-native services and specialized agents so enterprises can ship accurate, audit-ready documentation programs.
        </p>
        <div className="flex flex-wrap gap-4">
          <Link href="/workspace" className="rounded-full bg-white px-8 py-3 text-base font-semibold text-slate-900 shadow-lg transition hover:bg-slate-100">
            Jump into workspace
          </Link>
          <Link href="/" className="rounded-full border border-white/60 px-8 py-3 text-base font-medium text-white transition hover:bg-white/10">
            Back to overview
          </Link>
        </div>
      </header>

      <div className="grid gap-8 md:grid-cols-2">
        {pillars.map((pillar) => (
          <article key={pillar.title} className="rounded-3xl bg-white/85 p-8 text-slate-900 shadow-[0_35px_90px_rgba(15,23,42,0.35)]">
            <h2 className="text-2xl font-semibold">{pillar.title}</h2>
            <p className="mt-4 text-base text-slate-600">{pillar.details}</p>
          </article>
        ))}
      </div>

      <div className="rounded-3xl border border-white/20 bg-white/10 p-8">
        <p className="text-sm uppercase tracking-[0.35em] text-white/75">Pipeline walkthrough</p>
        <div className="mt-6 grid gap-6 md:grid-cols-2">
          {workflow.map((step) => (
            <div key={step.label} className="rounded-2xl bg-slate-900/40 p-5">
              <h3 className="text-xl font-semibold text-white">{step.label}</h3>
              <p className="mt-2 text-base text-white/80">{step.description}</p>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
