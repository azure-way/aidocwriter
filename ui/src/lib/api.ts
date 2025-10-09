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
