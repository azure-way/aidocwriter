import { Auth0Client } from "@auth0/nextjs-auth0/server";

export const auth0 = new Auth0Client({
  domain: process.env.AUTH0_DOMAIN ?? process.env.AUTH0_ISSUER_BASE_URL,
  appBaseUrl: process.env.APP_BASE_URL ?? process.env.AUTH0_BASE_URL,
  clientId: process.env.AUTH0_CLIENT_ID,
  clientSecret: process.env.AUTH0_CLIENT_SECRET,
  secret: process.env.AUTH0_SECRET,
  // Return 204 for unauthenticated profile requests so public pages don't see errors
  noContentProfileResponseWhenUnauthenticated: true,
  routes: {
    login: "/api/auth/login",
    logout: "/api/auth/logout",
    callback: "/api/auth/callback",
    backChannelLogout: "/api/auth/backchannel-logout",
    connectAccount: "/api/auth/connect",
  },
});
