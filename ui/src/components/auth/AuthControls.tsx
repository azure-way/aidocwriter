"use client";

import Image from "next/image";
import Link from "next/link";
import { useUser } from "@auth0/nextjs-auth0/client";

export function AuthControls() {
  const { user, error, isLoading } = useUser();
  const audience = process.env.NEXT_PUBLIC_AUTH0_AUDIENCE;
  const scope = process.env.NEXT_PUBLIC_AUTH0_SCOPE || "openid profile email api";
  const audienceParam = audience ? `&audience=${encodeURIComponent(audience)}` : "";
  const scopeParam = scope ? `&scope=${encodeURIComponent(scope)}` : "";
  const baseLogin = `/api/auth/login?returnTo=/workspace${audienceParam}${scopeParam}`;

  if (isLoading) {
    return (
      <span className="rounded-full border border-white/60 bg-white/70 px-6 py-2 text-sm font-semibold text-slate-500">
        Checking session…
      </span>
    );
  }

  if (!user) {
    return (
      <div className="flex flex-wrap gap-3">
        <Link
          href={baseLogin}
          prefetch={false}
          className="inline-flex items-center justify-center whitespace-nowrap rounded-full bg-gradient-to-r from-fuchsia-500 via-purple-500 to-sky-500 px-7 py-3 text-base font-semibold text-white shadow-[0_22px_45px_rgba(109,40,217,0.35)] transition hover:scale-105"
        >
          {error ? "Try again" : "Sign in"}
        </Link>
        <Link
          href={`${baseLogin}&screen_hint=signup`}
          prefetch={false}
          className="inline-flex items-center justify-center whitespace-nowrap rounded-full border border-white/70 px-7 py-3 text-base font-semibold text-slate-800 shadow-[0_12px_25px_rgba(15,23,42,0.15)] transition hover:bg-white"
        >
          Create account
        </Link>
      </div>
    );
  }

  return (
    <div className="flex items-center gap-3 rounded-full border border-white/60 bg-white/80 px-4 py-2">
      {user.picture ? (
        <Image
          src={user.picture}
          alt={user.name ?? user.email ?? "User avatar"}
          width={36}
          height={36}
          className="h-9 w-9 rounded-full object-cover"
          priority
        />
      ) : (
        <span className="inline-flex h-9 w-9 items-center justify-center rounded-full bg-slate-200 text-base font-semibold text-slate-600">
          {(user.name || user.email || "?").charAt(0).toUpperCase()}
        </span>
      )}
      <div className="flex flex-col">
        <span className="text-sm font-semibold text-slate-800">{user.name ?? user.email}</span>
        <span className="text-xs text-slate-500">Authenticated</span>
      </div>
      <Link href="/api/auth/logout" className="text-xs font-semibold text-slate-500 hover:text-slate-900">
        Sign out
      </Link>
    </div>
  );
}
