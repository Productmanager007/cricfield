import type { NextConfig } from "next";

// Static export: prebuilt HTML, JS and JSON, no server at request time.
// architecture.md §14, "Rendering strategy".
const nextConfig: NextConfig = {
  output: "export",
};

export default nextConfig;
