import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Sample Documents",
  description: "Preview sample Azure deliverables produced by DocWriter Studio, including PDFs and architecture references.",
  alternates: {
    canonical: "/sample-documents",
  },
  openGraph: {
    title: "DocWriter Studio Sample Documents",
    description: "Preview sample Azure deliverables produced by DocWriter Studio, including PDFs and architecture references.",
    url: "/sample-documents",
  },
  twitter: {
    title: "DocWriter Studio Sample Documents",
    description: "Preview sample Azure deliverables produced by DocWriter Studio, including PDFs and architecture references.",
  },
};

export default function SampleDocumentsLayout({ children }: { children: React.ReactNode }) {
  return children;
}
