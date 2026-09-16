import type { NextConfig } from "next";

const apiTarget = process.env.SELFBG_API_ORIGIN ?? "http://api:8000";

const nextConfig: NextConfig = {
  output: "standalone",
  async rewrites() {
    return [
      { source: "/api/:path*", destination: `${apiTarget}/:path*` },
    ];
  },
};

export default nextConfig;
