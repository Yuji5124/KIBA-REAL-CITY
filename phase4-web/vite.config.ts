import { createHash } from 'node:crypto';
import { readFileSync, statSync } from 'node:fs';
import { resolve } from 'node:path';
import { defineConfig, type Plugin } from 'vite';

const repositoryRoot = resolve(import.meta.dirname, '..');
const assets = [
  {
    fileName: 'assets/KIBA_REAL_CITY_v07.glb',
    source: resolve(repositoryRoot, 'output/KIBA_REAL_CITY_v07.glb'),
    sha256: '4830f6f43a0cadcf8ac0388b5ff5fa519a9c72fe8bed9b596d87afc30991eebb',
    mime: 'model/gltf-binary',
  },
  {
    fileName: 'assets/geo_reference_v07.json',
    source: resolve(repositoryRoot, 'output/geo_reference_v07.json'),
    sha256: 'ac0ad9987c51c5798c3abd99c805f86d22405dabbeeae5cc7e85709843b5b4dc',
    mime: 'application/json; charset=utf-8',
  },
] as const;

function readVerifiedAsset(asset: (typeof assets)[number]): Buffer {
  const bytes = readFileSync(asset.source);
  const hash = createHash('sha256').update(bytes).digest('hex');
  if (hash !== asset.sha256) {
    throw new Error(`Protected v07 asset hash mismatch for ${asset.source}: ${hash}`);
  }
  return bytes;
}

function localCityAssets(): Plugin {
  return {
    name: 'kiba-local-city-assets',
    configureServer(server) {
      server.middlewares.use((req, res, next) => {
        const url = req.url?.split('?')[0]?.replace(/^\//, '');
        const asset = assets.find((candidate) => candidate.fileName === url);
        if (!asset) return next();
        try {
          const bytes = readVerifiedAsset(asset);
          res.statusCode = 200;
          res.setHeader('Content-Type', asset.mime);
          res.setHeader('Content-Length', bytes.byteLength);
          res.setHeader('Cache-Control', 'no-store');
          res.setHeader('X-Content-Type-Options', 'nosniff');
          res.end(bytes);
        } catch (error) {
          res.statusCode = 500;
          res.end(error instanceof Error ? error.message : 'Unable to read protected local asset');
        }
      });
    },
    buildStart() {
      for (const asset of assets) {
        const stat = statSync(asset.source);
        if (!stat.isFile()) throw new Error(`Expected file: ${asset.source}`);
        readVerifiedAsset(asset);
      }
    },
    generateBundle() {
      for (const asset of assets) {
        this.emitFile({ type: 'asset', fileName: asset.fileName, source: readVerifiedAsset(asset) });
      }
    },
  };
}

export default defineConfig({
  plugins: [localCityAssets()],
  base: './',
  publicDir: false,
  server: {
    host: '127.0.0.1',
    port: 4173,
    strictPort: true,
  },
  build: {
    outDir: 'dist',
    emptyOutDir: true,
    sourcemap: false,
    assetsInlineLimit: 0,
  },
});
