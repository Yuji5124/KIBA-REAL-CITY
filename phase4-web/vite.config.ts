import { createHash } from 'node:crypto';
import { readFileSync, statSync, writeFileSync, mkdirSync, existsSync } from 'node:fs';
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

function phase5LocalData(): Plugin {
  const dataPath = resolve(repositoryRoot, 'phase5a/processed/viewer_features.json');
  const editsPath = resolve(repositoryRoot, 'phase5a/edits/edits.json');
  const sameOrigin = (origin: string | undefined, host: string | undefined): boolean => {
    if (!origin || !host) return false;
    try {
      const parsed = new URL(origin);
      return parsed.host === host && ['localhost', '127.0.0.1'].includes(parsed.hostname);
    } catch { return false; }
  };
  const sendJson = (res: import('node:http').ServerResponse, code: number, payload: unknown): void => {
    const body = Buffer.from(JSON.stringify(payload));
    res.statusCode = code;
    res.setHeader('Content-Type', 'application/json; charset=utf-8');
    res.setHeader('Cache-Control', 'no-store');
    res.setHeader('X-Content-Type-Options', 'nosniff');
    res.end(body);
  };
  return {
    name: 'kiba-phase5a-local-edit-api',
    configureServer(server) {
      server.middlewares.use(async (req, res, next) => {
        const path = req.url?.split('?')[0];
        if (!path?.startsWith('/phase5a-api/')) return next();
        if (!req.headers.host || !['localhost', '127.0.0.1'].includes(new URL(`http://${req.headers.host}`).hostname)) return sendJson(res, 403, { error: 'Loopback host only' });
        if (req.method !== 'GET' && !sameOrigin(req.headers.origin, req.headers.host)) return sendJson(res, 403, { error: 'Local same-origin writes only' });
        if (req.method === 'GET' && req.headers.origin && !sameOrigin(req.headers.origin, req.headers.host)) return sendJson(res, 403, { error: 'Local same-origin requests only' });
        if (path === '/phase5a-api/features' && req.method === 'GET') {
          if (!existsSync(dataPath)) return sendJson(res, 404, { error: 'Phase 5A local feature data is missing. Run scripts/build_feature_data.py.' });
          res.statusCode = 200;
          res.setHeader('Content-Type', 'application/json; charset=utf-8');
          res.setHeader('Cache-Control', 'no-store');
          return res.end(readFileSync(dataPath));
        }
        if (path === '/phase5a-api/edits' && req.method === 'GET') {
          const dataset = existsSync(dataPath) ? JSON.parse(readFileSync(dataPath, 'utf8')) : null;
          const edits = existsSync(editsPath) ? JSON.parse(readFileSync(editsPath, 'utf8')) : {
            schemaVersion: 1, baseSourceSha256: dataset?.sourceSha256 ?? '', edits: {}, additions: {}, deleted: [],
          };
          return sendJson(res, 200, edits);
        }
        if (path === '/phase5a-api/edits' && req.method === 'PUT') {
          if (!existsSync(dataPath)) return sendJson(res, 409, { error: 'Feature dataset missing' });
          const chunks: Buffer[] = [];
          let size = 0;
          try {
            for await (const chunk of req) {
              const buffer = Buffer.isBuffer(chunk) ? chunk : Buffer.from(chunk);
              size += buffer.byteLength;
              if (size > 1_000_000) return sendJson(res, 413, { error: 'Edit diff exceeds 1 MB' });
              chunks.push(buffer);
            }
            const dataset = JSON.parse(readFileSync(dataPath, 'utf8'));
            const edits = JSON.parse(Buffer.concat(chunks).toString('utf8'));
            if (edits?.schemaVersion !== 1 || edits?.baseSourceSha256 !== dataset.sourceSha256 ||
                typeof edits.edits !== 'object' || typeof edits.additions !== 'object' || !Array.isArray(edits.deleted)) {
              return sendJson(res, 409, { error: 'Edit schema or source snapshot mismatch' });
            }
            const byId = new Map<string, string>();
            for (const feature of [...dataset.roads, ...dataset.trees, ...dataset.vegetation]) byId.set(feature.featureId, feature.sourceHash);
            for (const [id, patch] of Object.entries(edits.edits) as [string, any][]) {
              if (!byId.has(id) || patch?.baseFeatureHash !== byId.get(id)) return sendJson(res, 409, { error: `Stale or unknown feature: ${id}` });
            }
            for (const [id, feature] of Object.entries(edits.additions) as [string, any][]) {
              if (!id.startsWith('manual:') || feature?.featureId !== id || feature?.source !== 'manual') return sendJson(res, 400, { error: `Invalid manual feature: ${id}` });
            }
            for (const id of edits.deleted) if (!byId.has(id) && !id.startsWith('manual:')) return sendJson(res, 400, { error: `Unknown deletion: ${id}` });
            mkdirSync(resolve(repositoryRoot, 'phase5a/edits'), { recursive: true });
            writeFileSync(editsPath, `${JSON.stringify(edits, null, 2)}\n`, { encoding: 'utf8', flag: 'w' });
            return sendJson(res, 200, { saved: true, edits: Object.keys(edits.edits).length, additions: Object.keys(edits.additions).length, deleted: edits.deleted.length });
          } catch (error) {
            return sendJson(res, 400, { error: error instanceof Error ? error.message : 'Invalid JSON' });
          }
        }
        return sendJson(res, 405, { error: 'Method not allowed' });
      });
    },
  };
}

export default defineConfig({
  plugins: [localCityAssets(), phase5LocalData()],
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
