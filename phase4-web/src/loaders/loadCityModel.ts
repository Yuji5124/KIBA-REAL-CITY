import { Box3, Group, Mesh, Vector3 } from 'three';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import type { CityModelInfo, GeoReference } from '../types';

const GLB_URL = `${import.meta.env.BASE_URL}assets/KIBA_REAL_CITY_v07.glb`;
const GEO_URL = `${import.meta.env.BASE_URL}assets/geo_reference_v07.json`;

async function fetchGeoReference(): Promise<GeoReference> {
  const response = await fetch(GEO_URL, { cache: 'no-store' });
  if (!response.ok) throw new Error(`地理参照JSONを取得できません (${response.status})`);
  return (await response.json()) as GeoReference;
}

function validateGeoReference(geo: GeoReference): void {
  if (geo.local_crs !== 'EPSG:6677' || geo.phase3d?.crs !== 'EPSG:6677') {
    throw new Error(`地理参照CRSが想定と異なります: ${geo.local_crs} / ${geo.phase3d?.crs}`);
  }
  if (geo.phase3d_v07?.mode !== 'FLAT' || !geo.phase3d_v07.origin_preserved) {
    throw new Error('v07 FLATまたは共通原点の情報を確認できません');
  }
  const [west, south, east, north] = geo.phase3d.bounds_local_m;
  const width = east - west;
  const height = north - south;
  if (Math.abs(width - geo.phase3d.extent_width_m) > 0.01 || Math.abs(height - geo.phase3d.extent_height_m) > 0.01) {
    throw new Error('地理参照JSONの範囲寸法が一致しません');
  }
}

export async function loadCityModel(onProgress: (fraction: number) => void): Promise<{ info: CityModelInfo; geo: GeoReference }> {
  const start = performance.now();
  const [geo, head] = await Promise.all([
    fetchGeoReference(),
    fetch(GLB_URL, { method: 'HEAD', cache: 'no-store' }),
  ]);
  validateGeoReference(geo);
  if (!head.ok) throw new Error(`v07 GLBを取得できません (${head.status})`);
  const fileSizeBytes = Number(head.headers.get('content-length') ?? 0);
  if (!fileSizeBytes) throw new Error('GLBファイルサイズを取得できません');
  const root = new Group();
  const loader = new GLTFLoader();
  const loaded = await loader.loadAsync(GLB_URL, (event) => {
    if (event.total > 0) onProgress(event.loaded / event.total);
  });
  root.add(loaded.scene);
  root.updateMatrixWorld(true);

  const bounds = new Box3().setFromObject(root);
  if (bounds.isEmpty()) throw new Error('GLBのBounding Boxが空です');
  const extent = bounds.getSize(new Vector3());
  if (![extent.x, extent.y, extent.z].every(Number.isFinite)) throw new Error('GLBの寸法に非有限値があります');
  if (root.scale.distanceTo(new Vector3(1, 1, 1)) > 1e-9) throw new Error('GLB表示グループに単位スケール以外が設定されています');

  let renderMeshes = 0;
  let triangles = 0;
  const buildingBounds = new Map<string, Box3>();
  root.traverse((object) => {
    const id = object.userData.citygml_id;
    if (typeof id === 'string' && id.startsWith('bldg_')) {
      const box = new Box3().setFromObject(object);
      const current = buildingBounds.get(id);
      if (current) current.union(box);
      else buildingBounds.set(id, box);
    }
    const mesh = object as Mesh;
    if (!mesh.isMesh || !mesh.geometry) return;
    renderMeshes += 1;
    const indexCount = mesh.geometry.index?.count ?? mesh.geometry.attributes.position?.count ?? 0;
    triangles += Math.floor(indexCount / 3);
  });

  const meshes = loaded.parser.json.meshes?.length ?? 0;
  if (meshes !== 1070) throw new Error(`GLB mesh定義数が一致しません: ${meshes} (expected 1070)`);
  if (buildingBounds.size !== 583) throw new Error(`CityGML建物IDが一致しません: ${buildingBounds.size} (expected 583)`);
  const [minEast, minNorth, maxEast, maxNorth] = geo.phase3d.bounds_local_m;
  const areaBoundsAreIncluded = bounds.min.x <= minEast + 0.2 && bounds.max.x >= maxEast - 0.2
    && bounds.min.z <= -maxNorth + 0.2 && bounds.max.z >= -minNorth - 0.2;
  if (!areaBoundsAreIncluded) throw new Error('GLBの表示範囲が地理参照JSONの対象範囲を覆っていません');

  return {
    geo,
    info: {
      root,
      bounds,
      meshes,
      renderMeshes,
      triangles,
      buildings: buildingBounds.size,
      buildingBoxes: [...buildingBounds.values()],
      loadMs: performance.now() - start,
      fileSizeBytes,
    },
  };
}
