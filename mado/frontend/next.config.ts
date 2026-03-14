import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Prevent Next.js from stripping trailing slashes before proxying
  skipTrailingSlashRedirect: true,
  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination: "http://localhost:8000/api/:path*",
      },
    ];
  },
};

export default nextConfig;
