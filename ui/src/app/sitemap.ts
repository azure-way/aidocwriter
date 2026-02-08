import type { MetadataRoute } from "next";
import { readdirSync, existsSync } from "node:fs";
import path from "node:path";

const BASE_URL = "https://docwriter-studio.azureway.cloud";

function getSampleDocumentUrls(): string[] {
  const samplesDir = path.join(process.cwd(), "public", "sample-documents");
  if (!existsSync(samplesDir)) {
    return [];
  }
  return readdirSync(samplesDir)
    .filter((file) => file.endsWith(".pdf"))
    .map((file) => `/sample-documents/${file}`);
}

export default function sitemap(): MetadataRoute.Sitemap {
  const lastModified = new Date();
  const entries: MetadataRoute.Sitemap = [
    {
      url: `${BASE_URL}/`,
      lastModified,
      changeFrequency: "weekly",
      priority: 1,
    },
    {
      url: `${BASE_URL}/features`,
      lastModified,
      changeFrequency: "monthly",
      priority: 0.7,
    },
    {
      url: `${BASE_URL}/sample-documents`,
      lastModified,
      changeFrequency: "monthly",
      priority: 0.7,
    },
  ];

  const sampleDocs = getSampleDocumentUrls();
  for (const doc of sampleDocs) {
    entries.push({
      url: `${BASE_URL}${doc}`,
      lastModified,
      changeFrequency: "yearly",
      priority: 0.4,
    });
  }

  return entries;
}
