import type { MetadataRoute } from "next";

export default function manifest(): MetadataRoute.Manifest {
  return {
    name: "CodebaseAtlas",
    short_name: "Atlas",
    description:
      "Discover, evaluate, and deeply understand open-source repositories.",
    start_url: "/",
    display: "standalone",
    background_color: "#0a0a0a",
    theme_color: "#c8a96e",
    icons: [
      {
        src: "/favicon.ico",
        sizes: "any",
        type: "image/x-icon",
      },
    ],
  };
}
