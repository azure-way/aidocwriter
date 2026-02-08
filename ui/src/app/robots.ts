import type { MetadataRoute } from "next";

export default function robots(): MetadataRoute.Robots {
  return {
    rules: [
      {
        userAgent: "*",
        allow: ["/", "/features", "/sample-documents"],
        disallow: ["/workspace", "/newdocument", "/job", "/auth", "/api"],
      },
    ],
    sitemap: "https://docwriter-studio.azureway.cloud/sitemap.xml",
  };
}
