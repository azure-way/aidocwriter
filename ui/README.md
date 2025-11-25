## DocWriter UI

This Next.js app powers the DocWriter marketing pages and the authenticated workspace. The UI now relies on Auth0 for identity and talks to the API tier through the environment-configured base URL.

## Prerequisites

- Node.js 18+
- Auth0 tenant with a Regular Web Application
- API endpoint for DocWriter (`NEXT_PUBLIC_API_BASE_URL`)

## Environment variables

Create a `.env.local` in this folder using `.env.example` as a template:

```bash
cp .env.example .env.local
```

Fill in the following values:

| Variable | Description |
| --- | --- |
| `NEXT_PUBLIC_API_BASE_URL` | Base URL for the FastAPI backend used by `/lib/api.ts`. |
| `AUTH0_SECRET` | 32+ char random value used to encrypt Auth0 session cookies. |
| `AUTH0_BASE_URL` | Public URL for this UI (e.g., `http://localhost:3000`). |
| `AUTH0_ISSUER_BASE_URL` | Auth0 tenant domain, e.g., `https://your-tenant.us.auth0.com`. |
| `AUTH0_CLIENT_ID` / `AUTH0_CLIENT_SECRET` | Credentials for the Auth0 Regular Web App. |
| `NEXT_PUBLIC_AUTH0_AUDIENCE` | API identifier configured in Auth0 so the access token carries your backend audience. |
| `NEXT_PUBLIC_AUTH0_SCOPE` | Optional scopes requested when logging in (default `openid profile email`). |

Add these URLs to your Auth0 application settings:

- **Allowed Callback URLs:** `http://localhost:3000/api/auth/callback`
- **Allowed Logout URLs:** `http://localhost:3000`
- **Allowed Web Origins:** `http://localhost:3000`

## Useful commands

```bash
# install deps
npm install

# run dev server
npm run dev

# lint
npm run lint
```

Open [http://localhost:3000](http://localhost:3000) to browse the marketing pages. “Sign in” and “Create account” CTAs redirect to Auth0 Universal Login; upon success you’re returned to `/workspace`, and the header reflects the active session.
