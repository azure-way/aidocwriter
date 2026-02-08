"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { GlassCard } from "@/components/GlassCard";
import { GradientTitle } from "@/components/GradientTitle";
import { useUser } from "@auth0/nextjs-auth0/client";
import { fetchCompanyProfile, saveCompanyProfile, uploadCompanyProfileDoc } from "@/lib/api";

type CompanyReference = {
  title: string;
  summary: string;
  outcome?: string;
  year?: string;
};

type CompanyProfile = {
  company_name: string;
  overview: string;
  capabilities: string[];
  industries: string[];
  certifications: string[];
  locations: string[];
  references: CompanyReference[];
};

type McpConfig = {
  base_url: string;
  resource_path: string;
  tool_path: string;
};

const emptyProfile: CompanyProfile = {
  company_name: "",
  overview: "",
  capabilities: [],
  industries: [],
  certifications: [],
  locations: [],
  references: [],
};

const emptyMcpConfig: McpConfig = {
  base_url: "",
  resource_path: "",
  tool_path: "",
};

const parseList = (value: string) =>
  value
    .split("\n")
    .map((item) => item.trim())
    .filter(Boolean);

const formatList = (items: string[]) => items.join("\n");

export default function ProfilePage() {
  const { user, isLoading } = useUser();
  const [profile, setProfile] = useState<CompanyProfile>(emptyProfile);
  const [sources, setSources] = useState<Array<{ filename: string; blob_path: string }>>([]);
  const [updated, setUpdated] = useState<number | null>(null);
  const [mcpConfig, setMcpConfig] = useState<McpConfig>(emptyMcpConfig);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [uploading, setUploading] = useState(false);

  const loadProfile = useCallback(async () => {
    if (!user?.sub) return;
    try {
      const data = await fetchCompanyProfile();
      setProfile(data.profile ?? emptyProfile);
      setSources(data.sources ?? []);
      setUpdated(data.updated ?? null);
      setMcpConfig(data.mcp_config ?? emptyMcpConfig);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load profile");
    }
  }, [user?.sub]);

  useEffect(() => {
    loadProfile();
  }, [loadProfile]);

  const handleSave = useCallback(async () => {
    setSaving(true);
    setError(null);
    try {
      const response = await saveCompanyProfile(profile, mcpConfig);
      setProfile(response.profile ?? profile);
      setSources(response.sources ?? sources);
      setUpdated(response.updated ?? updated ?? null);
      setMcpConfig(response.mcp_config ?? mcpConfig);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to save profile");
    } finally {
      setSaving(false);
    }
  }, [profile, sources, updated, mcpConfig]);

  const handleUpload = useCallback(
    async (file: File) => {
      setUploading(true);
      setError(null);
      try {
        const response = await uploadCompanyProfileDoc(file);
        setProfile(response.profile ?? profile);
        setSources(response.sources ?? sources);
        setUpdated(response.updated ?? updated ?? null);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to upload profile document");
      } finally {
        setUploading(false);
      }
    },
    [profile, sources, updated]
  );

  const formattedUpdated = useMemo(() => {
    if (!updated) return "—";
    return new Date(updated * 1000).toLocaleString();
  }, [updated]);

  if (isLoading) {
    return (
      <section className="space-y-6">
        <GlassCard>Checking authentication…</GlassCard>
      </section>
    );
  }

  if (!user) {
    return (
      <section className="space-y-6">
        <GlassCard>Please sign in to manage your company profile.</GlassCard>
      </section>
    );
  }

  return (
    <section className="space-y-8 pb-10">
      <GlassCard className="space-y-4 rounded-[32px] bg-gradient-to-br from-slate-900 via-blue-900 to-sky-700 p-10 text-white">
        <GradientTitle
          title="Company profile"
          subtitle="Keep your company context up to date for proposals and RFP responses."
          className="bg-gradient-to-r from-cyan-200 via-sky-300 to-white text-transparent"
          subtitleClassName="text-white/80"
        />
        <p className="text-sm text-white/70">Last updated: {formattedUpdated}</p>
        <div className="flex flex-wrap gap-3">
          <label className="btn-primary cursor-pointer">
            {uploading ? "Uploading…" : "Upload PDF/DOCX/PPTX"}
            <input
              type="file"
              className="hidden"
              accept=".pdf,.docx,.pptx"
              onChange={(e) => {
                const file = e.target.files?.[0];
                if (file) handleUpload(file);
              }}
              disabled={uploading}
            />
          </label>
          <button className="btn-primary" onClick={handleSave} disabled={saving}>
            {saving ? "Saving…" : "Save profile"}
          </button>
        </div>
        {error ? <p className="text-sm text-red-200">{error}</p> : null}
      </GlassCard>

      <GlassCard className="space-y-4">
        <h2 className="text-lg font-semibold text-slate-900">MCP connection</h2>
        <div className="grid gap-6 md:grid-cols-2">
          <div className="space-y-2">
            <label className="text-xs font-semibold uppercase tracking-[0.3em] text-slate-500">
              Base URL
            </label>
            <input
              className="input-glass"
              value={mcpConfig.base_url}
              onChange={(e) => setMcpConfig((prev) => ({ ...prev, base_url: e.target.value }))}
              placeholder="https://mcp.example.com"
            />
          </div>
          <div className="space-y-2">
            <label className="text-xs font-semibold uppercase tracking-[0.3em] text-slate-500">
              Resource path
            </label>
            <input
              className="input-glass"
              value={mcpConfig.resource_path}
              onChange={(e) => setMcpConfig((prev) => ({ ...prev, resource_path: e.target.value }))}
              placeholder="resources/company.profile"
            />
          </div>
          <div className="space-y-2">
            <label className="text-xs font-semibold uppercase tracking-[0.3em] text-slate-500">
              Tool path
            </label>
            <input
              className="input-glass"
              value={mcpConfig.tool_path}
              onChange={(e) => setMcpConfig((prev) => ({ ...prev, tool_path: e.target.value }))}
              placeholder="tools/company.query"
            />
          </div>
          <div className="text-sm text-slate-500">
            MCP uses your IDP access token from the current session. Health probe checks `/healthz` then `/health`.
          </div>
        </div>
      </GlassCard>

      <GlassCard className="space-y-6">
        <div className="grid gap-6 md:grid-cols-2">
          <div className="space-y-2">
            <label className="text-xs font-semibold uppercase tracking-[0.3em] text-slate-500">
              Company name
            </label>
            <input
              className="input-glass"
              value={profile.company_name}
              onChange={(e) => setProfile((prev) => ({ ...prev, company_name: e.target.value }))}
            />
          </div>
          <div className="space-y-2">
            <label className="text-xs font-semibold uppercase tracking-[0.3em] text-slate-500">
              Overview
            </label>
            <textarea
              className="textarea-glass"
              value={profile.overview}
              onChange={(e) => setProfile((prev) => ({ ...prev, overview: e.target.value }))}
            />
          </div>
        </div>
        <div className="grid gap-6 md:grid-cols-2">
          <div className="space-y-2">
            <label className="text-xs font-semibold uppercase tracking-[0.3em] text-slate-500">
              Capabilities (one per line)
            </label>
            <textarea
              className="textarea-glass"
              value={formatList(profile.capabilities)}
              onChange={(e) =>
                setProfile((prev) => ({ ...prev, capabilities: parseList(e.target.value) }))
              }
            />
          </div>
          <div className="space-y-2">
            <label className="text-xs font-semibold uppercase tracking-[0.3em] text-slate-500">
              Industries (one per line)
            </label>
            <textarea
              className="textarea-glass"
              value={formatList(profile.industries)}
              onChange={(e) =>
                setProfile((prev) => ({ ...prev, industries: parseList(e.target.value) }))
              }
            />
          </div>
          <div className="space-y-2">
            <label className="text-xs font-semibold uppercase tracking-[0.3em] text-slate-500">
              Certifications (one per line)
            </label>
            <textarea
              className="textarea-glass"
              value={formatList(profile.certifications)}
              onChange={(e) =>
                setProfile((prev) => ({ ...prev, certifications: parseList(e.target.value) }))
              }
            />
          </div>
          <div className="space-y-2">
            <label className="text-xs font-semibold uppercase tracking-[0.3em] text-slate-500">
              Locations (one per line)
            </label>
            <textarea
              className="textarea-glass"
              value={formatList(profile.locations)}
              onChange={(e) =>
                setProfile((prev) => ({ ...prev, locations: parseList(e.target.value) }))
              }
            />
          </div>
        </div>
      </GlassCard>

      <GlassCard className="space-y-6">
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-semibold text-slate-900">References</h2>
          <button
            type="button"
            className="rounded-full border border-slate-200 px-4 py-2 text-sm font-semibold text-slate-700 hover:border-slate-400"
            onClick={() =>
              setProfile((prev) => ({
                ...prev,
                references: [
                  ...prev.references,
                  { title: "", summary: "", outcome: "", year: "" },
                ],
              }))
            }
          >
            Add reference
          </button>
        </div>
        {profile.references.length === 0 ? (
          <p className="text-sm text-slate-500">No references yet.</p>
        ) : (
          <div className="space-y-4">
            {profile.references.map((ref, idx) => (
              <div key={`${ref.title}-${idx}`} className="grid gap-4 md:grid-cols-2">
                <input
                  className="input-glass"
                  placeholder="Title"
                  value={ref.title}
                  onChange={(e) =>
                    setProfile((prev) => {
                      const next = [...prev.references];
                      next[idx] = { ...next[idx], title: e.target.value };
                      return { ...prev, references: next };
                    })
                  }
                />
                <input
                  className="input-glass"
                  placeholder="Year"
                  value={ref.year ?? ""}
                  onChange={(e) =>
                    setProfile((prev) => {
                      const next = [...prev.references];
                      next[idx] = { ...next[idx], year: e.target.value };
                      return { ...prev, references: next };
                    })
                  }
                />
                <textarea
                  className="textarea-glass md:col-span-2"
                  placeholder="Summary"
                  value={ref.summary}
                  onChange={(e) =>
                    setProfile((prev) => {
                      const next = [...prev.references];
                      next[idx] = { ...next[idx], summary: e.target.value };
                      return { ...prev, references: next };
                    })
                  }
                />
                <textarea
                  className="textarea-glass md:col-span-2"
                  placeholder="Outcome"
                  value={ref.outcome ?? ""}
                  onChange={(e) =>
                    setProfile((prev) => {
                      const next = [...prev.references];
                      next[idx] = { ...next[idx], outcome: e.target.value };
                      return { ...prev, references: next };
                    })
                  }
                />
              </div>
            ))}
          </div>
        )}
      </GlassCard>

      <GlassCard className="space-y-3">
        <h2 className="text-lg font-semibold text-slate-900">Uploaded sources</h2>
        {sources.length === 0 ? (
          <p className="text-sm text-slate-500">No profile documents uploaded.</p>
        ) : (
          <div className="space-y-1 text-sm text-slate-600">
            {sources.map((source) => (
              <div key={source.blob_path}>{source.filename}</div>
            ))}
          </div>
        )}
      </GlassCard>
    </section>
  );
}
