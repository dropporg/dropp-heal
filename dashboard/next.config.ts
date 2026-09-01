import type { NextConfig } from "next";

/**
 * The browser talks only to the dashboard's own origin; src/app/api proxies
 * requests on to the Heal API. The proxy reads HEAL_API_URL per request, so one
 * image runs in every environment - next.config rewrites would not, because
 * their destinations are resolved at build time.
 */
const nextConfig: NextConfig = {
  output: "standalone",
};

export default nextConfig;
