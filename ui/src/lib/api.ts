const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL;

async function request(path: string, options: RequestInit = {}) {
  if (!API_BASE) {
    throw new Error("NEXT_PUBLIC_API_BASE_URL is not set");
  }

  const res = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...(options.headers || {}),
    },
    cache: "no-store",
  });

  if (!res.ok) {
    const message = await res.text();
    throw new Error(message || `Request failed: ${res.status}`);
  }
  return res.json();
}

export function getArtifactUrl(path: string): string {
  if (!API_BASE) {
    throw new Error("NEXT_PUBLIC_API_BASE_URL is not set");
  }
  const url = new URL("/jobs/artifacts", API_BASE);
  url.searchParams.set("path", path);
  return url.toString();
}

export async function downloadArtifact(path: string): Promise<Blob> {
  const url = getArtifactUrl(path);
  const res = await fetch(url, { cache: "no-store" });
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
  });
}

export async function resumeJob(jobId: string, answers: Record<string, unknown>) {
  return request(`/jobs/${jobId}/resume`, {
    method: "POST",
    body: JSON.stringify({ answers }),
  });
}

export async function fetchJobStatus(jobId: string) {
  return request(`/jobs/${jobId}/status`);
}

export async function fetchJobTimeline(jobId: string) {
  return request(`/jobs/${jobId}/timeline`);
}
