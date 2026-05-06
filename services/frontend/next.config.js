const os = require('os');

function normalizeOriginHost(value) {
  if (!value) return '';
  return value
    .trim()
    .replace(/^https?:\/\//i, '')
    .replace(/\/.*/, '')
    .trim();
}

function getLanIpv4Hosts() {
  const interfaces = os.networkInterfaces();
  const hosts = [];

  Object.values(interfaces).forEach((entries) => {
    (entries || []).forEach((entry) => {
      if (entry && entry.family === 'IPv4' && !entry.internal) {
        hosts.push(entry.address);
      }
    });
  });

  return hosts;
}

function getEnvAllowedHosts() {
  const raw = process.env.NEXT_ALLOWED_DEV_ORIGINS || '';
  return raw
    .split(',')
    .map(normalizeOriginHost)
    .filter(Boolean);
}

const allowedDevOrigins = [
  'localhost',
  '127.0.0.1',
  ...getLanIpv4Hosts(),
  ...getEnvAllowedHosts(),
];

/** @type {import('next').NextConfig} */
const nextConfig = {
  output: 'standalone',
  allowedDevOrigins: [...new Set(allowedDevOrigins)],
  turbopack: {
    root: __dirname,
  },
};

module.exports = nextConfig;
