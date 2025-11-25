import { handleAuth } from "@auth0/nextjs-auth0";

const handler = handleAuth();

type RouteContext = { params: Record<string, string[]> } | { params: Promise<Record<string, string[]>> };

async function resolveParams(ctx: RouteContext) {
  if ("params" in ctx && ctx.params instanceof Promise) {
    return { params: await ctx.params };
  }
  return ctx as { params: Record<string, string[]> };
}

export async function GET(req: Request, ctx: RouteContext) {
  return handler(req, await resolveParams(ctx));
}

export async function POST(req: Request, ctx: RouteContext) {
  return handler(req, await resolveParams(ctx));
}
