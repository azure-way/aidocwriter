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

const deriveArtifactPath = (rawPath: string): { relativePath: string; fileName: string } => {
  if (!rawPath) {
    throw new Error("Artifact path missing");
  }
  const cleaned = rawPath.replace(/^\/+/, "");
  const segments = cleaned.split("/").filter(Boolean);
  if (!segments.length) {
    throw new Error("Artifact path missing");
  }
  const fileName = segments[segments.length - 1] || cleaned;
  const relativePath =
    segments.length >= 3 && segments[0] === "jobs" ? segments.slice(3).join("/") : segments.join("/");
  return { relativePath: relativePath || fileName, fileName };
};

const parseContentDispositionName = (header: string | null): string | null => {
  if (!header) return null;
  const filenameStarMatch = header.match(/filename\*=UTF-8''([^;]+)/i);
  if (filenameStarMatch?.[1]) {
    try {
      return decodeURIComponent(filenameStarMatch[1]);
    } catch {
      return filenameStarMatch[1];
    }
  }
  const filenameMatch = header.match(/filename="?([^\";]+)"?/i);
  return filenameMatch?.[1] ?? null;
};

const inferExtensionFromContentType = (contentType?: string | null): string | null => {
  if (!contentType) return null;
  const normalized = contentType.split(";")[0]?.trim().toLowerCase();
  if (!normalized) return null;
  const map: Record<string, string> = {
    "application/pdf": "pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "docx",
    "text/markdown": "md",
    "text/x-markdown": "md",
    "text/plain": "txt",
  };
  return map[normalized] ?? null;
};

export type ArtifactDownload = {
  blob: Blob;
  fileName: string;
  contentType?: string;
};

export async function downloadArtifact(jobId: string, rawPath: string): Promise<ArtifactDownload> {
  if (!API_BASE) {
    throw new Error("NEXT_PUBLIC_API_BASE_URL is not set");
  }
  if (!jobId) {
    throw new Error("jobId is required to download artifacts");
  }
  const token = await getAccessToken();
  const url = new URL("/jobs/artifacts", API_BASE);
  const { relativePath, fileName: artifactFileName } = deriveArtifactPath(rawPath);
  url.searchParams.set("job_id", jobId);
  url.searchParams.set("name", relativePath);
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
  const contentType = res.headers.get("content-type") ?? undefined;
  const headerName = parseContentDispositionName(res.headers.get("content-disposition"));
  const preferredName = headerName?.trim() || artifactFileName || "artifact";
  const hasExtension = /\.[^./\s]+$/.test(preferredName);
  const fallbackExt = inferExtensionFromContentType(contentType);
  const fileName = hasExtension || !fallbackExt ? preferredName : `${preferredName}.${fallbackExt}`;

  const blob = await res.blob();
  return { blob, fileName, contentType };
}

export async function downloadDiagramArchive(jobId: string): Promise<ArtifactDownload> {
  if (!API_BASE) {
    throw new Error("NEXT_PUBLIC_API_BASE_URL is not set");
  }
  if (!jobId) {
    throw new Error("jobId is required to download diagram archive");
  }
  const token = await getAccessToken();
  const url = new URL(`/jobs/${encodeURIComponent(jobId)}/diagrams/archive`, API_BASE);
  const res = await fetch(url.toString(), {
    cache: "no-store",
    headers: {
      Authorization: `Bearer ${token}`,
    },
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(text || `Failed to download diagram archive (${res.status})`);
  }
  const contentType = res.headers.get("content-type") ?? undefined;
  const headerName = parseContentDispositionName(res.headers.get("content-disposition"));
  const preferredName = headerName?.trim() || `${jobId}-diagrams.zip`;
  const blob = await res.blob();
  return { blob, fileName: preferredName, contentType };
}

export async function fetchIntakeQuestions(title: string) {
  return request("/intake/questions", {
    method: "POST",
    body: JSON.stringify({ title }),
  });
}

export async function fetchJobIntakeQuestions(jobId: string) {
  return request(`/jobs/${jobId}/intake/questions`, { auth: true });
}

export async function createJob(payload: { title: string; audience: string; cycles: number }) {
  return request("/jobs", {
    method: "POST",
    body: JSON.stringify(payload),
    auth: true,
  });
}

export async function createRfpJob(payload: {
  file?: File;
  files?: File[];
  cycles?: number;
}) {
  if (!API_BASE) {
    throw new Error("NEXT_PUBLIC_API_BASE_URL is not set");
  }
  const token = await getAccessToken();
  const form = new FormData();
  if (payload.file) {
    form.append("file", payload.file);
  }
  if (payload.files?.length) {
    payload.files.forEach((item) => form.append("files", item));
  }
  if (payload.cycles) {
    form.append("cycles", String(payload.cycles));
  }
  const res = await fetch(`${API_BASE}/jobs/rfp`, {
    method: "POST",
    headers: { Authorization: `Bearer ${token}` },
    body: form,
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(text || `Request failed: ${res.status}`);
  }
  return res.json();
}

export async function resumeJob(jobId: string, answers: Record<string, unknown>) {
  return request(`/jobs/${jobId}/resume`, {
    method: "POST",
    body: JSON.stringify({ answers }),
    auth: true,
  });
}

export async function fetchCompanyProfile() {
  return request("/profile/company", { auth: true });
}

export async function fetchFeatureFlags() {
  return request("/profile/features", { auth: true });
}

export async function saveCompanyProfile(
  profile: Record<string, unknown>,
  mcpConfig?: { base_url?: string; resource_path?: string; tool_path?: string }
) {
  return request("/profile/company", {
    method: "PUT",
    body: JSON.stringify({ profile, mcp_config: mcpConfig }),
    auth: true,
  });
}

export async function uploadCompanyProfileDoc(file: File) {
  if (!API_BASE) {
    throw new Error("NEXT_PUBLIC_API_BASE_URL is not set");
  }
  const token = await getAccessToken();
  const form = new FormData();
  form.append("file", file);
  const res = await fetch(`${API_BASE}/profile/company/upload`, {
    method: "POST",
    headers: { Authorization: `Bearer ${token}` },
    body: form,
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(text || `Request failed: ${res.status}`);
  }
  return res.json();
}

export async function discoverMcp(baseUrl: string) {
  return request("/profile/mcp/discover", {
    method: "POST",
    body: JSON.stringify({ base_url: baseUrl }),
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
