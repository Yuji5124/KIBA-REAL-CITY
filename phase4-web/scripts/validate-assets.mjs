import { createHash } from 'node:crypto';
import { readFile, stat, mkdir, writeFile } from 'node:fs/promises';

const files = {
  glb: new URL('../dist/assets/KIBA_REAL_CITY_v07.glb', import.meta.url),
  geo: new URL('../dist/assets/geo_reference_v07.json', import.meta.url),
};
const expected = {
  glb: '4830f6f43a0cadcf8ac0388b5ff5fa519a9c72fe8bed9b596d87afc30991eebb',
  geo: 'ac0ad9987c51c5798c3abd99c805f86d22405dabbeeae5cc7e85709843b5b4dc',
};
const results = { generatedAt: new Date().toISOString(), checks: [], files: {} };
const check = (name, pass, details = {}) => results.checks.push({ name, status: pass ? 'PASS' : 'FAIL', ...details });

for (const name of ['glb', 'geo']) {
  try {
    const bytes = await readFile(files[name]);
    const sha256 = createHash('sha256').update(bytes).digest('hex');
    const size = (await stat(files[name])).size;
    results.files[name] = { path: files[name].pathname, sizeBytes: size, sha256 };
    check(`${name} exact source asset`, sha256 === expected[name], { sha256, expectedSha256: expected[name], sizeBytes: size });
  } catch (error) {
    results.files[name] = { error: String(error) };
    check(`${name} exact source asset`, false, { error: String(error) });
  }
}

if (results.files.glb?.sha256 === expected.glb) {
  const bytes = await readFile(files.glb);
  const magic = bytes.toString('ascii', 0, 4);
  const version = bytes.readUInt32LE(4);
  const totalLength = bytes.readUInt32LE(8);
  const jsonLength = bytes.readUInt32LE(12);
  const gltf = JSON.parse(bytes.toString('utf8', 20, 20 + jsonLength));
  const ids = new Set(gltf.nodes.map((node) => node.extras?.citygml_id).filter((id) => typeof id === 'string' && id.startsWith('bldg_')));
  check('GLB v2 container', magic === 'glTF' && version === 2 && totalLength === bytes.byteLength, { magic, version, totalLength, bytes: bytes.byteLength });
  check('GLB mesh count', gltf.meshes?.length === 1070, { meshes: gltf.meshes?.length });
  check('unique CityGML building IDs', ids.size === 583, { count: ids.size });
  check('no external textures or extensions', !(gltf.extensionsUsed?.length) && !(gltf.images?.length), { extensions: gltf.extensionsUsed ?? [], images: gltf.images?.length ?? 0 });
}

if (results.files.geo?.sha256 === expected.geo) {
  const geo = JSON.parse(await readFile(files.geo, 'utf8'));
  const dims = geo.phase3d;
  check('EPSG:6677 georeference and unchanged origin', geo.local_crs === 'EPSG:6677' && dims?.crs === 'EPSG:6677' && geo.phase3d_v07?.origin_preserved === true, { crs: geo.local_crs, originProjectedM: geo.center_projected_m });
  check('extent dimensions', Math.abs(dims.extent_width_m - 505.2403830586759) < 0.01 && Math.abs(dims.extent_height_m - 990.8604533191901) < 0.01, { eastWestM: dims.extent_width_m, northSouthM: dims.extent_height_m });
}

const failures = results.checks.filter((item) => item.status !== 'PASS');
await mkdir(new URL('../reports/', import.meta.url), { recursive: true });
await writeFile(new URL('../reports/phase4a_asset_validation.json', import.meta.url), JSON.stringify(results, null, 2) + '\n');
console.log(JSON.stringify(results, null, 2));
if (failures.length) process.exitCode = 1;
