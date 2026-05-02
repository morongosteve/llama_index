/** @type {import('next').NextConfig} */
const nextConfig = {
  experimental: {
    // Allow reading/writing the JSON data file at runtime in serverless envs.
    // On Vercel the filesystem is read-only outside /tmp, so writes degrade
    // gracefully (see lib/store.ts).
  },
};

export default nextConfig;
