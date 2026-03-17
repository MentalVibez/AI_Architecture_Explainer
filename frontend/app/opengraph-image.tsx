import { ImageResponse } from "next/og";

export const runtime = "edge";
export const alt = "CodebaseAtlas — Developer Toolkit";
export const size = { width: 1200, height: 630 };
export const contentType = "image/png";

export default function Image() {
  return new ImageResponse(
    (
      <div
        style={{
          background: "#0a0a0a",
          width: "100%",
          height: "100%",
          display: "flex",
          flexDirection: "column",
          justifyContent: "center",
          padding: "80px 96px",
          fontFamily: "monospace",
          position: "relative",
        }}
      >
        {/* Top-right decorative grid dots */}
        <div
          style={{
            position: "absolute",
            top: 60,
            right: 80,
            display: "flex",
            gap: 10,
            opacity: 0.15,
          }}
        >
          {[...Array(5)].map((_, i) => (
            <div key={i} style={{ display: "flex", flexDirection: "column", gap: 10 }}>
              {[...Array(4)].map((_, j) => (
                <div
                  key={j}
                  style={{ width: 4, height: 4, borderRadius: "50%", background: "#c8a96e" }}
                />
              ))}
            </div>
          ))}
        </div>

        {/* Wordmark */}
        <div style={{ display: "flex", alignItems: "center", gap: 16, marginBottom: 48 }}>
          <span style={{ color: "#c8a96e", fontSize: 14, letterSpacing: "0.3em", textTransform: "uppercase" }}>
            Atlas
          </span>
          <div style={{ width: 1, height: 20, background: "#2a2a2a" }} />
          <span style={{ color: "#3a3a3a", fontSize: 14, letterSpacing: "0.2em", textTransform: "uppercase" }}>
            Toolkit
          </span>
        </div>

        {/* Headline */}
        <div style={{ display: "flex", flexDirection: "column", gap: 12, marginBottom: 40 }}>
          <span
            style={{
              color: "#e8e0d4",
              fontSize: 64,
              fontWeight: 700,
              lineHeight: 1,
              letterSpacing: "-0.02em",
            }}
          >
            Understand any
          </span>
          <span
            style={{
              color: "#c8a96e",
              fontSize: 64,
              fontWeight: 700,
              lineHeight: 1,
              letterSpacing: "-0.02em",
            }}
          >
            codebase in seconds.
          </span>
        </div>

        {/* Subheading */}
        <p
          style={{
            color: "#4a4a4a",
            fontSize: 22,
            lineHeight: 1.5,
            maxWidth: 620,
            margin: 0,
          }}
        >
          Architecture diagrams · Framework detection · API surface mapping
        </p>

        {/* Tool pills at bottom */}
        <div style={{ display: "flex", gap: 12, marginTop: 56 }}>
          {[
            { label: "01  RepoScout", color: "#c8a96e" },
            { label: "02  Atlas",     color: "#7cb9c8" },
            { label: "03  Map",       color: "#8ab58a" },
            { label: "04  Review",    color: "#9a7cb8" },
          ].map(({ label, color }) => (
            <div
              key={label}
              style={{
                display: "flex",
                padding: "8px 16px",
                border: `1px solid ${color}30`,
                borderRadius: 6,
                color,
                fontSize: 13,
                letterSpacing: "0.15em",
                textTransform: "uppercase",
                background: `${color}08`,
              }}
            >
              {label}
            </div>
          ))}
        </div>

        {/* Bottom URL */}
        <div
          style={{
            position: "absolute",
            bottom: 48,
            right: 96,
            color: "#2a2a2a",
            fontSize: 14,
            letterSpacing: "0.1em",
          }}
        >
          codebaseatlas.com
        </div>
      </div>
    ),
    { ...size }
  );
}
