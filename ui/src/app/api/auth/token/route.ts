import { getAccessToken } from "@auth0/nextjs-auth0";
import { NextRequest, NextResponse } from "next/server";

function buildArgs(request: NextRequest) {
  const params = request.nextUrl.searchParams;
  const audience = params.get("audience") ?? process.env.NEXT_PUBLIC_AUTH0_AUDIENCE ?? process.env.AUTH0_AUDIENCE;
  const scopeParam = params.get("scope") ?? process.env.NEXT_PUBLIC_AUTH0_SCOPE ?? process.env.AUTH0_SCOPE;
  const scopes = scopeParam
    ? scopeParam
        .split(/\s+/)
        .map((entry) => entry.trim())
        .filter(Boolean)
    : undefined;
  return { audience, scopes };
}

async function obtainToken(request: NextRequest) {
  const args = buildArgs(request);
  const response = NextResponse.next();
  const token = await getAccessToken(request, response, {
    refresh: true,
    audience: args.audience,
    scopes: args.scopes,
  });
  return { response, token };
}

export async function GET(request: NextRequest) {
  try {
    const { response, token } = await obtainToken(request);
    const body = NextResponse.json({ accessToken: token.accessToken });
    response.cookies.getAll().forEach((cookie) => {
      body.cookies.set(cookie);
    });
    return body;
  } catch (error: any) {
    const status = error?.status ?? 401;
    const message = error?.message ?? "Unable to fetch access token";
    return NextResponse.json({ error: message }, { status });
  }
}

export const dynamic = "force-dynamic";
