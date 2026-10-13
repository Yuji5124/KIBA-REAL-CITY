export type ExplorerMode = 'walk' | 'fly';

export interface GeoReference {
  center_projected_m: [number, number];
  center_wgs84: { latitude: number; longitude: number };
  local_crs: string;
  phase3d: {
    crs: string;
    bounds_local_m: [number, number, number, number];
    extent_width_m: number;
    extent_height_m: number;
  };
  phase3d_v07: {
    mode: string;
    origin_preserved: boolean;
  };
}

export interface CityModelInfo {
  root: import('three').Group;
  bounds: import('three').Box3;
  meshes: number;
  renderMeshes: number;
  triangles: number;
  buildings: number;
  buildingBoxes: import('three').Box3[];
  loadMs: number;
  fileSizeBytes: number;
}

export interface AppUI {
  canvas: HTMLCanvasElement;
  loadStatus: HTMLElement;
  errorPanel: HTMLElement;
  progress: HTMLElement;
  walkButton: HTMLButtonElement;
  flyButton: HTMLButtonElement;
  resetButton: HTMLButtonElement;
  hint: HTMLElement;
  altitudeControls: HTMLElement;
  ascendButton: HTMLButtonElement;
  descendButton: HTMLButtonElement;
  moveStick: HTMLElement;
  lookArea: HTMLElement;
  debugPanel: HTMLElement;
  phase5Panel: HTMLDetailsElement;
}
