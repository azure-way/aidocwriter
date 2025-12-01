import type { NextRequest } from "next/server";
import { NextResponse } from "next/server";

import { auth0 } from "./src/lib/auth0";

const PROTECTED_PATHS = ["/workspace", "/newdocument"];
const LOGIN_PATH = "/api/auth/login";

const isProtected = (pathname: string) =>
  PROTECTED_PATHS.some((base) => pathname === base || pathname.startsWith(`${base}/`));

export async function middleware(request: NextRequest) {
  const authResponse = await auth0.middleware(request);

  const pathname = request.nextUrl.pathname;
  if (!isProtected(pathname) || pathname.startsWith("/api/auth")) {
    return authResponse;
  }

  const session = await auth0.getSession(request);
  if (session) {
    return authResponse;
  }

  const loginUrl = new URL(LOGIN_PATH, request.url);
  loginUrl.searchParams.set("returnTo", pathname + request.nextUrl.search);
  return NextResponse.redirect(loginUrl);
}

export const config = {
  matcher: [
    "/api/auth/:path*",
    "/workspace",
    "/workspace/:path*",
    "/newdocument",
    "/newdocument/:path*",
  ],
};
