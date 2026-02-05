"use client";

import Link from "next/link";
import { useMemo, useState } from "react";

const documents = [
  {
    title: "Azure Governance Approach",
    slug: "azure-governance-approach",
    summary: "Landing zones, guardrails, and operating model guidance for enterprise Azure programs.",
    highlights: ["Landing zones", "Policy-driven guardrails", "Operational excellence"],
  },
  {
    title: "Azure Integration Services - Basic Summary",
    slug: "azure-integration-services-basic-summary",
    summary: "Core services for APIs, messaging, and workflows with a concise integration blueprint.",
    highlights: ["API Management", "Service Bus", "Logic Apps"],
  },
  {
    title: "Azure Network Security",
    slug: "azure-network-security",
    summary: "Defense-in-depth overview including perimeter, segmentation, and identity-aware controls.",
    highlights: ["Zero Trust", "Segmentation", "Threat protection"],
  },
  {
    title: "Hosting Containers Across Different Cloud Providers",
    slug: "hosting-containers-across-different-cloud-providers",
    summary: "Portable container hosting patterns to run consistently across Azure, AWS, and GCP.",
    highlights: ["Kubernetes", "Portability", "Multi-cloud governance"],
  },
];

export default function SampleDocumentsPage() {
  const [selectedSlug, setSelectedSlug] = useState(documents[0].slug);
  const selectedDoc = useMemo(() => documents.find((doc) => doc.slug === selectedSlug) ?? documents[0], [selectedSlug]);

  return (
    <section className="space-y-12 rounded-[32px] border border-white/20 bg-gradient-to-br from-slate-900 via-cyan-900 to-blue-800 p-10 text-white shadow-[0_45px_140px_rgba(15,23,42,0.45)]">
      <header className="space-y-4">
        <p className="text-sm uppercase tracking-[0.35em] text-white/70">Sample documents</p>
        <h1 className="text-4xl font-semibold">Preview ready-to-ship Azure deliverables</h1>
        <p className="text-lg text-white/80">
          Explore example PDFs created with DocWriter Studio. Use them as starting points for your own work or to share with stakeholders.
        </p>
        <div className="flex flex-wrap gap-4">
          <Link href="/" className="rounded-full border border-white/60 px-8 py-3 text-base font-medium text-white transition hover:bg-white/10">
            Back to overview
          </Link>
          <Link href="/workspace" className="rounded-full bg-white px-8 py-3 text-base font-semibold text-slate-900 shadow-lg transition hover:bg-slate-100">
            Open workspace
          </Link>
        </div>
      </header>

      <div className="grid gap-6 lg:grid-cols-[0.8fr_1.2fr]">
        <div className="flex flex-col gap-3">
          {documents.map((doc) => (
            <article key={doc.slug} className="rounded-3xl bg-white/90 p-6 text-slate-900 shadow-[0_28px_75px_rgba(15,23,42,0.3)]">
              <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                <div>
                  <h2 className="text-xl font-semibold">{doc.title}</h2>
                  <p className="mt-1.5 text-sm text-slate-600">{doc.summary}</p>
                  <div className="mt-2 flex flex-wrap gap-2">
                    {doc.highlights.map((tag) => (
                      <span key={tag} className="rounded-full bg-slate-900/5 px-2.5 py-1 text-[11px] font-semibold text-slate-700">
                        {tag}
                      </span>
                    ))}
                  </div>
                </div>
                <div className="flex gap-2 sm:flex-col">
                  <button
                    type="button"
                    onClick={() => setSelectedSlug(doc.slug)}
                    className={`rounded-full border px-4 py-2 text-sm font-semibold transition ${
                      selectedSlug === doc.slug
                        ? "border-slate-900 bg-slate-900 text-white shadow-[0_10px_35px_rgba(15,23,42,0.35)]"
                        : "border-slate-300 text-slate-900 hover:border-slate-400 hover:bg-slate-50"
                    }`}
                  >
                    Preview
                  </button>
                  <a
                    href={`/sample-documents/${doc.slug}.pdf`}
                    target="_blank"
                    rel="noreferrer"
                    className="rounded-full border border-slate-300 px-3.5 py-1.5 text-[13px] font-semibold text-slate-900 transition hover:border-slate-400 hover:bg-slate-50"
                  >
                    View PDF
                  </a>
                  <a
                    href={`/sample-documents/${doc.slug}.pdf`}
                    download
                    className="rounded-full bg-slate-900 px-3.5 py-1.5 text-[13px] font-semibold text-white shadow-[0_10px_35px_rgba(15,23,42,0.35)] transition hover:bg-slate-800"
                  >
                    Download
                  </a>
                </div>
              </div>
            </article>
          ))}
        </div>

        <aside className="rounded-3xl border border-white/25 bg-slate-950/50 p-6 shadow-[0_35px_120px_rgba(15,23,42,0.5)]">
          <p className="text-xs uppercase tracking-[0.35em] text-white/70">Live preview</p>
          <h2 className="mt-2 text-2xl font-semibold text-white">{selectedDoc.title}</h2>
          <p className="mt-2 text-sm text-white/80">{selectedDoc.summary}</p>
          <div className="mt-4 flex flex-wrap gap-2">
            {selectedDoc.highlights.map((tag) => (
              <span key={tag} className="rounded-full bg-white/10 px-3 py-1 text-xs font-semibold text-white">
                {tag}
              </span>
            ))}
          </div>
          <div className="mt-6 overflow-hidden rounded-2xl border border-white/15 bg-black/40 shadow-inner">
            <object
              data={`/sample-documents/${selectedDoc.slug}.pdf`}
              type="application/pdf"
              className="h-[520px] w-full"
            >
              <div className="p-6 text-sm text-white/80">
                Preview not available in this browser.{" "}
                <a href={`/sample-documents/${selectedDoc.slug}.pdf`} target="_blank" rel="noreferrer" className="underline">
                  Open the PDF
                </a>
                .
              </div>
            </object>
          </div>
        </aside>
      </div>
    </section>
  );
}
