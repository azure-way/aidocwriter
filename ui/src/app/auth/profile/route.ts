import type { NextRequest } from "next/server";

import { auth0 } from "@/lib/auth0";

export async function GET(request: NextRequest) {
  // Delegate to Auth0 middleware so the SDK handles profile responses consistently
  return auth0.middleware(request);
}

// Profile must always be dynamic so it can check the current session.
export const dynamic = "force-dynamic";
