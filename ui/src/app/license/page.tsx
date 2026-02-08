import type { Metadata } from "next";
import { notFound } from "next/navigation";

export const metadata: Metadata = {
  title: "License",
  description: "License and commercial use terms for DocWriter Studio, including License vs SaaS options.",
  alternates: {
    canonical: "/license",
  },
  openGraph: {
    title: "License | DocWriter Studio",
    description: "Compare license and SaaS access options for DocWriter Studio.",
    url: "/license",
  },
  twitter: {
    title: "License | DocWriter Studio",
    description: "Compare license and SaaS access options for DocWriter Studio.",
  },
};

const comparisonRows = [
  {
    label: "Deployment model",
    license: "Self-managed in your environment or internal tools stack.",
    saas: "AzureWay-hosted SaaS with optional private deployment as a separate instance.",
  },
  {
    label: "Data isolation",
    license: "Data stays in your Azure tenant and storage accounts.",
    saas: "Tenant isolation with dedicated instance available for strict separation.",
  },
  {
    label: "SSO & governance",
    license: "Align to your identity provider, policies, and governance.",
    saas: "Managed SSO setup with governance controls aligned to enterprise needs.",
  },
  {
    label: "Support & SLA",
    license: "Priority support and onboarding for commercial customers.",
    saas: "SLA-backed support with monitored uptime and incident response.",
  },
  {
    label: "Billing",
    license: "Annual or multi-year commercial licensing.",
    saas: "Subscription access with predictable monthly or annual billing.",
  },
  {
    label: "Customization",
    license: "Custom workflows, agents, and integrations for your team.",
    saas: "Configuration options plus private instance for deeper customization.",
  },
];

const commercialUseExamples = [
  "Internal company use across a team or department.",
  "Deliverables created for clients or paid engagements.",
  "Revenue-generating documentation products or services.",
];

export default function LicensePage() {
  notFound();

  return (
    <div className="space-y-16">
      <section className="rounded-[32px] border border-white/20 bg-gradient-to-br from-slate-900 via-blue-900 to-sky-700 p-10 text-white shadow-[0_45px_140px_rgba(15,23,42,0.45)]">
        <div className="space-y-6">
          <p className="text-xs uppercase tracking-[0.35em] text-white/70">Licensing</p>
          <h1 className="font-heading text-4xl font-semibold sm:text-5xl">License and commercial use</h1>
          <p className="text-lg text-white/80">
            DocWriter Studio is free for personal and private use. Commercial use requires a paid license or SaaS access
            with enterprise support and governance options.
          </p>
          <div className="grid gap-4 rounded-3xl border border-white/20 bg-white/10 p-6 text-white/80 shadow-[0_30px_90px_rgba(15,23,42,0.35)] md:grid-cols-[0.9fr_1.1fr]">
            <div>
              <h2 className="text-lg font-semibold text-white">Free use</h2>
              <p className="mt-2 text-sm text-white/75">
                Personal projects, private experimentation, and individual research work are free to run and share.
              </p>
            </div>
            <div>
              <h2 className="text-lg font-semibold text-white">Commercial use</h2>
              <ul className="mt-2 list-disc space-y-1 pl-4 text-sm text-white/75">
                {commercialUseExamples.map((item) => (
                  <li key={item}>{item}</li>
                ))}
              </ul>
            </div>
          </div>
        </div>
      </section>

      <section className="space-y-6 rounded-[32px] border border-white/20 bg-white/80 p-10 text-slate-900 shadow-[0_35px_90px_rgba(15,23,42,0.18)]">
        <div className="space-y-2">
          <p className="text-xs uppercase tracking-[0.35em] text-slate-500">Comparison</p>
          <h2 className="text-3xl font-semibold">License vs SaaS access</h2>
          <p className="text-sm text-slate-600">
            Choose a commercial license to deploy in your environment or subscribe to the hosted SaaS with enterprise
            controls.
          </p>
        </div>

        <div className="overflow-hidden rounded-3xl border border-slate-200 bg-white shadow-[0_24px_70px_rgba(15,23,42,0.12)]">
          <div className="grid grid-cols-1 border-b border-slate-200 bg-slate-50 text-sm font-semibold text-slate-600 md:grid-cols-[1.1fr_1fr_1fr]">
            <div className="px-6 py-4">Capability</div>
            <div className="px-6 py-4">Commercial license</div>
            <div className="px-6 py-4">SaaS access</div>
          </div>
          <div className="divide-y divide-slate-100 text-sm text-slate-700">
            {comparisonRows.map((row) => (
              <div key={row.label} className="grid grid-cols-1 gap-4 px-6 py-5 md:grid-cols-[1.1fr_1fr_1fr]">
                <div className="font-semibold text-slate-900">{row.label}</div>
                <div>{row.license}</div>
                <div>{row.saas}</div>
              </div>
            ))}
          </div>
        </div>

        <div className="rounded-3xl border border-slate-200 bg-slate-50 p-6 text-sm text-slate-600">
          This page is a summary of licensing options and is not legal advice.
        </div>
      </section>

      <section className="rounded-[32px] border border-white/30 bg-gradient-to-br from-slate-900 via-slate-800 to-slate-700 p-10 text-white shadow-[0_35px_90px_rgba(15,23,42,0.35)]">
        <div className="space-y-4">
          <p className="text-xs uppercase tracking-[0.35em] text-white/70">Commercial inquiries</p>
          <h2 className="text-3xl font-semibold">Request a commercial license or SaaS access</h2>
          <p className="text-sm text-white/75">
            Reach out for pricing, onboarding, and a tailored deployment plan.
          </p>
          <a
            href="mailto:sales@azureway.cloud"
            className="inline-flex items-center justify-center rounded-full bg-white px-8 py-3 text-base font-semibold text-slate-900 shadow-lg transition hover:bg-slate-100"
          >
            Contact sales
          </a>
        </div>
      </section>
    </div>
  );
}
