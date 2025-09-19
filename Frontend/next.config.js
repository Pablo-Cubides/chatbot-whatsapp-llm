/** @type {import('next').NextConfig} */
const nextConfig = {
  async rewrites() {
    return [
      {
        source: '/api/backend/:path*',
        destination: 'http://localhost:8003/api/:path*',
      },
    ];
  },
  env: {
    BACKEND_URL: process.env.BACKEND_URL || 'http://localhost:8003',
    WEBSOCKET_URL: process.env.WEBSOCKET_URL || 'ws://localhost:8003',
  },
};

module.exports = nextConfig;