import type { Metadata } from "next";
import Link from "next/link";
import { UserProvider } from "@auth0/nextjs-auth0/client";
import { AuthControls } from "@/components/auth/AuthControls";
import "./globals.css";

export const metadata: Metadata = {
  title: "DocWriter Studio",
  description: "Large-scale AI document generation orchestrated via Azure queues",
};

const navItems = [
  { href: "/", label: "Home" },
  { href: "/features", label: "Features" },
  { href: "/workspace", label: "Workspace" },
];

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body className="min-h-screen bg-slate-50 text-slate-900">
        <UserProvider>
          <div className="relative min-h-screen overflow-hidden">
            <div className="absolute inset-0 -z-10 bg-[radial-gradient(circle_at_top,_rgba(148,163,184,0.25),_transparent_65%)]" />
            <div className="flex min-h-screen w-full flex-col gap-12 px-4 py-8 sm:px-8 lg:px-12">
              <header className="glass-panel w-full flex flex-col gap-6 border border-white/50 p-6 shadow-[0_35px_90px_rgba(15,23,42,0.25)] backdrop-blur-xl sm:flex-row sm:items-center sm:justify-between">
                <Link href="/" className="font-heading text-2xl font-semibold tracking-tight text-slate-900">
                  DocWriter Studio
                </Link>
                <nav className="flex flex-wrap items-center gap-4 text-base font-semibold text-slate-600">
                  {navItems.map((item) => (
                    <Link
                      key={item.href}
                      href={item.href}
                      className="rounded-full border border-transparent bg-white/50 px-6 py-2.5 text-slate-600 shadow-[inset_0_1px_0_rgba(255,255,255,0.9)] transition hover:border-slate-300 hover:bg-white hover:text-slate-900"
                    >
                      {item.label}
                    </Link>
                  ))}
                </nav>
                <AuthControls />
              </header>

              <main className="w-full flex-1 pb-16">
                {children}
              </main>
            </div>
          </div>
        </UserProvider>
      </body>
    </html>
  );
}
