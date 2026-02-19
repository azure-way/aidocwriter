import type { Metadata } from "next";
import Link from "next/link";

export const metadata: Metadata = {
  title: "About the Author",
  description: "Meet the Azure MVP behind Azure Way and DocWriter Studio.",
  alternates: {
    canonical: "/about-author",
  },
  openGraph: {
    title: "About the Author",
    description: "Meet the Azure MVP behind Azure Way and DocWriter Studio.",
    url: "/about-author",
  },
  twitter: {
    title: "About the Author",
    description: "Meet the Azure MVP behind Azure Way and DocWriter Studio.",
  },
};

const focusAreas = [
  "Azure architecture creation using Terraform",
  "Azure DevOps",
  "Azure cost optimization",
  "Azure Security",
  "Azure Networking",
];

export default function AboutAuthorPage() {
  return (
    <section className="space-y-10 rounded-[32px] border border-white/25 bg-gradient-to-br from-slate-900 via-sky-900 to-blue-700 p-10 text-white shadow-[0_45px_140px_rgba(15,23,42,0.45)]">
      <header className="space-y-4">
        <p className="text-sm uppercase tracking-[0.35em] text-white/70">About the author</p>
        <h1 className="text-4xl font-semibold">Karol Pieciukiewicz, Microsoft MVP</h1>
        <p className="text-lg text-white/80">
          Microsoft technology enthusiast for 13+ years and Microsoft MVP in the Azure category. Dedicated Azure advocate
          focused on custom applications and identity solutions. Strong believer in automation across application
          development and infrastructure, with a practical focus on Terraform scripting.
        </p>
      </header>

      <div className="grid gap-8 lg:grid-cols-[1.2fr_0.8fr]">
        <article className="rounded-3xl bg-white/90 p-8 text-slate-900 shadow-[0_35px_90px_rgba(15,23,42,0.35)]">
          <h2 className="text-2xl font-semibold">Primary focus areas</h2>
          <p className="mt-3 text-base text-slate-600">
            Azure Way concentrates on practical, experience-based guidance across core Azure disciplines.
          </p>
          <ul className="mt-6 space-y-3 text-base text-slate-700">
            {focusAreas.map((item) => (
              <li key={item} className="flex items-start gap-3">
                <span className="mt-2 inline-block h-2 w-2 rounded-full bg-slate-900/70" />
                <span>{item}</span>
              </li>
            ))}
          </ul>
        </article>

        <aside className="rounded-3xl border border-white/20 bg-white/10 p-8">
          <h2 className="text-xl font-semibold text-white">Get in touch</h2>
          <p className="mt-3 text-base text-white/80">
            Suggestions or critiques are welcome. Reach out by email or connect on LinkedIn.
          </p>
          <div className="mt-6 space-y-4">
            <a
              href="mailto:contact@azureway.cloud"
              className="block rounded-2xl bg-white/90 px-5 py-4 text-base font-semibold text-slate-900 shadow-[0_20px_50px_rgba(15,23,42,0.25)] transition hover:bg-white"
            >
              contact@azureway.cloud
            </a>
            <a
              href="https://www.linkedin.com/in/karol-pieciukiewicz/"
              target="_blank"
              rel="noreferrer"
              className="block rounded-2xl border border-white/60 px-5 py-4 text-base font-semibold text-white transition hover:bg-white/10"
            >
              LinkedIn profile
            </a>
          </div>
        </aside>
      </div>

      <div className="flex flex-wrap gap-4">
        <Link href="/features" className="rounded-full bg-white px-8 py-3 text-base font-semibold text-slate-900 shadow-lg transition hover:bg-slate-100">
          Explore platform features
        </Link>
        <Link href="/sample-documents" className="rounded-full border border-white/60 px-8 py-3 text-base font-medium text-white transition hover:bg-white/10">
          Browse sample documents
        </Link>
      </div>
    </section>
  );
}
