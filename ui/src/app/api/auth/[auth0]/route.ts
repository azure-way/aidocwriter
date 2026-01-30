import type { NextRequest } from "next/server";

import { auth0 } from "@/lib/auth0";

// Delegate Auth0 endpoints (login, logout, callback, etc.) to the SDK middleware.
export async function GET(request: NextRequest) {
  return auth0.middleware(request);
}

export async function POST(request: NextRequest) {
  return auth0.middleware(request);
}

export const dynamic = "force-dynamic";
