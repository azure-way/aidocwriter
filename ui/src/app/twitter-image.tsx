import { ImageResponse } from "next/og";

export const size = {
  width: 1200,
  height: 630,
};

export const contentType = "image/png";

export default function TwitterImage() {
  return new ImageResponse(
    (
      <div
        style={{
          width: "100%",
          height: "100%",
          display: "flex",
          flexDirection: "column",
          justifyContent: "center",
          padding: "80px",
          background: "linear-gradient(135deg, #0f172a 0%, #1e3a8a 55%, #0284c7 100%)",
          color: "#ffffff",
          fontFamily: "ui-sans-serif, system-ui, -apple-system, Segoe UI, sans-serif",
        }}
      >
        <div style={{ fontSize: 64, fontWeight: 700, letterSpacing: "-0.02em" }}>DocWriter Studio</div>
        <div style={{ marginTop: 24, fontSize: 32, fontWeight: 500, maxWidth: 900 }}>
          AI-orchestrated Azure documentation at enterprise scale
        </div>
        <div style={{ marginTop: 40, fontSize: 20, opacity: 0.8 }}>
          Intake - Planning - Writing - Review - Diagramming - Governance
        </div>
      </div>
    ),
    size
  );
}
