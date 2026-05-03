import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Standalone output bundles only what's needed for production,
  // producing a much smaller Docker image than copying all node_modules.
  output: "standalone",

};

export default nextConfig;
