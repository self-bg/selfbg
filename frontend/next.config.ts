import type { NextConfig } from "next";

const apiTarget = process.env.SELFBG_API_ORIGIN ?? "http://api:8000";

const nextConfig: NextConfig = {
  output: "standalone",
  // Videos can be well over the default 10 MB. Match the backend's video
  // upload cap so a big video isn't cut off at the proxy.
  experimental: {
    middlewareClientMaxBodySize: "250mb",
  },
  async rewrites() {
    return [
      { source: "/api/:path*", destination: `${apiTarget}/:path*` },
    ];
  },
};

export default nextConfig;
