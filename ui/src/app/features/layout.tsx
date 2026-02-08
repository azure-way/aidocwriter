import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Features",
  description: "Explore DocWriter Studio features for AI-orchestrated Azure documentation and enterprise governance.",
  alternates: {
    canonical: "/features",
  },
  openGraph: {
    title: "DocWriter Studio Features",
    description: "Explore DocWriter Studio features for AI-orchestrated Azure documentation and enterprise governance.",
    url: "/features",
  },
  twitter: {
    title: "DocWriter Studio Features",
    description: "Explore DocWriter Studio features for AI-orchestrated Azure documentation and enterprise governance.",
  },
};

export default function FeaturesLayout({ children }: { children: React.ReactNode }) {
  return children;
}
