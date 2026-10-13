export type LocalEN = [number, number];

export interface RoadFeature {
  featureId: string;
  osmId: string;
  sourceHash: string;
  nodeIds?: string[];
  memberWayIds?: string[];
  tags: Record<string, string>;
  highway: string;
  name?: string | null;
  surface?: string | null;
  geometryType: 'line' | 'area';
  widthM: number;
  widthSource: string;
  observedWidthM?: number | null;
  coordinatesLocalEN: LocalEN[];
  polygonsLocalEN?: Array<{ outer: LocalEN[]; holes: LocalEN[][] }>;
}

export interface TreeFeature {
  featureId: string;
  treeId: string;
  sourceOsmId: string;
  sourceHash?: string;
  latitude: number | null;
  longitude: number | null;
  localX: number;
  localNorth: number;
  height: number | null;
  crownDiameter: number | null;
  trunkDiameter: number | null;
  species: string | null;
  genus?: string | null;
  modelType: string;
  rotation: number;
  source: string;
  confidence: string;
  edited: boolean;
  tags?: Record<string, string>;
}

export interface VegetationFeature {
  featureId: string;
  osmId: string;
  sourceHash: string;
  tags: Record<string, string>;
  vegetationClass: string;
  geometryType: 'line' | 'area';
  coordinatesLocalEN: LocalEN[];
  polygonsLocalEN?: Array<{ outer: LocalEN[]; holes: LocalEN[][] }>;
}

export interface Phase5Dataset {
  schemaVersion: number;
  sourceSha256: string;
  crs: 'EPSG:6677';
  centerProjectedM: [number, number];
  boundsLocalM: [number, number, number, number];
  threeAxes: string;
  source: { license: string; attribution: string; attributionUrl: string };
  roads: RoadFeature[];
  trees: TreeFeature[];
  vegetation: VegetationFeature[];
  terrain: { status: string; reason: string };
}

export interface FeaturePatch {
  baseFeatureHash: string;
  set?: Record<string, number | string | null>;
  controlPoint?: { index: number; eastM: number; northM: number };
  deleted?: boolean;
}

export interface Phase5Edits {
  schemaVersion: number;
  baseSourceSha256: string;
  edits: Record<string, FeaturePatch>;
  additions: Record<string, TreeFeature>;
  deleted: string[];
}
