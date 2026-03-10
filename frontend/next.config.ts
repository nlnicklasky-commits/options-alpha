import type { NextConfig } from "next";

// Use BACKEND_URL (server-only) for the rewrite proxy destination.
// Falls back to NEXT_PUBLIC_API_URL for backward compat, then localhost.
const backendUrl =
  process.env.BACKEND_URL ||
  process.env.NEXT_PUBLIC_API_URL ||
  "http://localhost:8000";

const nextConfig: NextConfig = {
  output: "standalone",
  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination: `${backendUrl}/api/:path*`,
      },
    ];
  },
};

export default nextConfig;
