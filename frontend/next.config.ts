import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  devIndicators: false,
  images: {
    remotePatterns: [
      { protocol: "https", hostname: "crests.football-data.org" },
      { protocol: "https", hostname: "media.api-sports.io" },
    ],
  },
};

export default nextConfig;
