import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "DocWriter Studio",
  description: "Large-scale AI document generation orchestrated via Azure queues",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body className="min-h-screen text-slate-900">
        <div className="relative min-h-screen overflow-hidden">
          <div className="absolute inset-0 -z-10 bg-[radial-gradient(circle_at_top,_rgba(148,163,184,0.25),_transparent_65%)]" />
          <header className="mx-auto mt-12 w-full max-w-6xl px-6">
            <div className="glass-panel gradient-header flex flex-col gap-8 rounded-[32px] px-12 py-12 text-slate-900 md:flex-row md:items-center md:justify-between">
              <div className="space-y-4 text-slate-900">
                <p className="text-xs uppercase tracking-[0.5em] text-slate-900/70">Docwriter</p>
                <h1 className="font-heading text-3xl font-semibold md:text-4xl">Enterprise Document Orchestration</h1>
                <p className="max-w-2xl text-sm text-slate-800/90">
                  Generate deeply researched, 60+ page technical documents supported by AI planning, writing, and review agents. The entire pipeline is orchestrated on Azure Service Bus.
                </p>
              </div>
              <div className="rounded-3xl bg-white/95 px-8 py-8 text-slate-700 shadow-[0_18px_45px_rgba(59,130,246,0.25)]">
                <p className="text-xs uppercase tracking-[0.4em] text-slate-400">Pipeline status</p>
                <div className="mt-4 flex items-center gap-3 text-sm text-slate-600">
                  <span className="inline-flex h-2.5 w-2.5 rounded-full bg-emerald-400 shadow-[0_0_0_4px_rgba(16,185,129,0.25)]" />
                  <span>Workers connected</span>
                </div>
                <a className="btn-primary mt-6 w-full" href="#intake">
                  Start new document
                </a>
              </div>
            </div>
          </header>

          <main className="mx-auto mt-16 w-full max-w-6xl px-6 pb-24">
            {children}
          </main>
        </div>
      </body>
    </html>
  );
}
