const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL;

const authAudience = process.env.NEXT_PUBLIC_AUTH0_AUDIENCE;
const authScope = process.env.NEXT_PUBLIC_AUTH0_SCOPE || "openid profile email";

let accessTokenPromise: Promise<string> | null = null;

async function fetchAccessToken(): Promise<string> {
  const params = new URLSearchParams();
  if (authAudience) {
    params.set("audience", authAudience);
  }
  if (authScope) {
    params.set("scope", authScope);
  }
  const url = `/api/auth/token${params.toString() ? `?${params.toString()}` : ""}`;
  const res = await fetch(url, { cache: "no-store" });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(text || "Failed to fetch access token");
  }
  const data = await res.json();
  if (!data.accessToken) {
    throw new Error("No access token returned");
  }
  return data.accessToken as string;
}

async function getAccessToken(): Promise<string> {
  if (!accessTokenPromise) {
    accessTokenPromise = fetchAccessToken().catch((err) => {
      accessTokenPromise = null;
      throw err;
    });
  }
  return accessTokenPromise;
}

type RequestOptions = RequestInit & { auth?: boolean };

async function request(path: string, options: RequestOptions = {}) {
  if (!API_BASE) {
    throw new Error("NEXT_PUBLIC_API_BASE_URL is not set");
  }

  const { auth, ...rest } = options;

  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(rest.headers as Record<string, string> | undefined),
  };

  if (auth) {
    const token = await getAccessToken();
    headers["Authorization"] = `Bearer ${token}`;
  }

  const res = await fetch(`${API_BASE}${path}`, {
    ...rest,
    headers,
    cache: "no-store",
  });

  if (!res.ok) {
    const message = await res.text();
    throw new Error(message || `Request failed: ${res.status}`);
  }
  return res.json();
}

export async function downloadArtifact(path: string): Promise<Blob> {
  if (!API_BASE) {
    throw new Error("NEXT_PUBLIC_API_BASE_URL is not set");
  }
  const token = await getAccessToken();
  const url = new URL("/jobs/artifacts", API_BASE);
  url.searchParams.set("path", path);
  const res = await fetch(url.toString(), {
    cache: "no-store",
    headers: {
      Authorization: `Bearer ${token}`,
    },
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(text || `Failed to download artifact (${res.status})`);
  }
  return res.blob();
}

export async function fetchIntakeQuestions(title: string) {
  return request("/intake/questions", {
    method: "POST",
    body: JSON.stringify({ title }),
  });
}

export async function createJob(payload: { title: string; audience: string; cycles: number }) {
  return request("/jobs", {
    method: "POST",
    body: JSON.stringify(payload),
    auth: true,
  });
}

export async function resumeJob(jobId: string, answers: Record<string, unknown>) {
  return request(`/jobs/${jobId}/resume`, {
    method: "POST",
    body: JSON.stringify({ answers }),
    auth: true,
  });
}

export async function fetchJobStatus(jobId: string) {
  return request(`/jobs/${jobId}/status`, { auth: true });
}

export async function fetchJobTimeline(jobId: string) {
  return request(`/jobs/${jobId}/timeline`, { auth: true });
}

export async function fetchDocuments() {
  return request("/jobs", { auth: true });
}
