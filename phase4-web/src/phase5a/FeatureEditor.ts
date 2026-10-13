import {
  BufferGeometry, DoubleSide, Float32BufferAttribute, Group, Line, LineBasicMaterial, Mesh, MeshStandardMaterial, Plane, Scene,
  Raycaster, Shape, ShapeGeometry, SphereGeometry, Vector2, Vector3, CylinderGeometry,
} from 'three';
import type { FeaturePatch, Phase5Dataset, Phase5Edits, RoadFeature, TreeFeature, VegetationFeature } from './types';

const ROAD_COLOR = 0x777e7b;
const ROAD_AREA_COLOR = 0x898f8a;
const VEGETATION_COLORS: Record<string, number> = { grass: 0x76a16b, forest: 0x496e4b, wood: 0x537a50, garden: 0x6b965c, flowerbed: 0x92a96e, meadow: 0x83a96f };
const emptyEdits = (sourceSha256 = ''): Phase5Edits => ({ schemaVersion: 1, baseSourceSha256: sourceSha256, edits: {}, additions: {}, deleted: [] });

function clone<T>(value: T): T { return JSON.parse(JSON.stringify(value)) as T; }
function loop(points: [number, number][]): Vector2[] { return points.map(([east, north]) => new Vector2(east, north)); }
function featureClass(feature: RoadFeature | TreeFeature | VegetationFeature): string {
  if ('treeId' in feature) return 'tree';
  if ('highway' in feature) return 'road';
  return 'vegetation';
}

export class FeatureEditor {
  private dataset?: Phase5Dataset;
  private edits = emptyEdits();
  private readonly roads = new Group();
  private readonly trees = new Group();
  private readonly vegetation = new Group();
  private readonly raycaster = new Raycaster();
  private readonly ground = new Plane(new Vector3(0, 1, 0), 0);
  private selectedId?: string;
  private editing = false;
  private dragging = false;
  private dragMoved = false;
  private dragStart = new Vector2();
  private dragPoint?: Vector3;
  private undoStack: Phase5Edits[] = [];
  private readonly layerControls: HTMLInputElement[] = [];
  private readonly selectPanel: HTMLElement;
  private readonly title: HTMLElement;
  private readonly details: HTMLElement;
  private readonly fields: HTMLElement;
  private readonly status: HTMLElement;
  private readonly attribution: HTMLElement;
  private readonly editButton: HTMLButtonElement;
  private readonly addTreeButton: HTMLButtonElement;
  private readonly saveButton: HTMLButtonElement;
  private readonly undoButton: HTMLButtonElement;
  private readonly revertButton: HTMLButtonElement;
  private readonly resetButton: HTMLButtonElement;

  constructor(
    private readonly scene: Scene,
    private readonly canvas: HTMLCanvasElement,
    private readonly camera: import('three').Camera,
    private readonly panel: HTMLDetailsElement,
    private readonly setCameraInputEnabled: (enabled: boolean) => void,
  ) {
    this.scene.add(this.roads, this.vegetation, this.trees);
    this.roads.name = 'Phase5A_Roads_OSM';
    this.trees.name = 'Phase5A_Trees_OSM_and_manual';
    this.vegetation.name = 'Phase5A_Vegetation_OSM';
    this.selectPanel = this.need('#phase5-selection');
    this.title = this.need('#phase5-selection-title');
    this.details = this.need('#phase5-selection-source');
    this.fields = this.need('#phase5-fields');
    this.status = this.need('#phase5-status');
    this.attribution = this.need('#phase5-attribution');
    this.editButton = this.need<HTMLButtonElement>('#phase5-edit-toggle');
    this.addTreeButton = this.need<HTMLButtonElement>('#phase5-add-tree');
    this.saveButton = this.need<HTMLButtonElement>('#phase5-save');
    this.undoButton = this.need<HTMLButtonElement>('#phase5-undo');
    this.revertButton = this.need<HTMLButtonElement>('#phase5-revert');
    this.resetButton = this.need<HTMLButtonElement>('#phase5-reset');
    this.layerControls.push(this.need<HTMLInputElement>('#layer-roads'), this.need<HTMLInputElement>('#layer-trees'), this.need<HTMLInputElement>('#layer-vegetation'));
    this.bindUI();
    this.canvas.addEventListener('pointerdown', this.onPointerDown);
    this.canvas.addEventListener('pointermove', this.onPointerMove);
    this.canvas.addEventListener('pointerup', this.onPointerUp);
    this.canvas.addEventListener('pointercancel', this.onPointerUp);
  }

  async load(): Promise<void> {
    try {
      const [dataResponse, editsResponse] = await Promise.all([fetch('/phase5a-api/features'), fetch('/phase5a-api/edits')]);
      if (!dataResponse.ok) throw new Error((await dataResponse.json()).error ?? `Feature data HTTP ${dataResponse.status}`);
      if (!editsResponse.ok) throw new Error(`Edit data HTTP ${editsResponse.status}`);
      const dataset = await dataResponse.json() as Phase5Dataset;
      if (dataset.crs !== 'EPSG:6677' || dataset.threeAxes !== 'X=east, Y=up, Z=-north' || !Array.isArray(dataset.roads) || !Array.isArray(dataset.trees) || !Array.isArray(dataset.vegetation)) {
        throw new Error('Phase 5A data schema or georeference mismatch');
      }
      const edits = await editsResponse.json() as Phase5Edits;
      if (edits.baseSourceSha256 && edits.baseSourceSha256 !== dataset.sourceSha256) throw new Error('Saved edit diff is based on a different OSM snapshot; resolve import conflict before applying.');
      this.dataset = dataset;
      this.edits = edits.baseSourceSha256 ? edits : emptyEdits(dataset.sourceSha256);
      this.buildLayers();
      this.layerControls.forEach((control) => { control.disabled = false; });
      this.editButton.disabled = this.addTreeButton.disabled = this.saveButton.disabled = this.resetButton.disabled = false;
      this.undoButton.disabled = this.revertButton.disabled = false;
      this.attribution.textContent = `${dataset.source.attribution} · ${dataset.source.license}; 利用条件の全文確認は保留中。データと差分はローカル保存。`;
      this.status.textContent = `EPSG:6677整合 · 道路 ${dataset.roads.length} · 個別樹木 ${dataset.trees.length} · 植栽 ${dataset.vegetation.length} · 地形 BLOCKED`;
    } catch (error) {
      this.status.textContent = `OSMレイヤーを読み込めません: ${error instanceof Error ? error.message : String(error)}`;
      this.attribution.textContent = '標高は未生成です。既存v07表示はそのまま利用できます。';
    }
  }

  dispose(): void {
    this.canvas.removeEventListener('pointerdown', this.onPointerDown);
    this.canvas.removeEventListener('pointermove', this.onPointerMove);
    this.canvas.removeEventListener('pointerup', this.onPointerUp);
    this.canvas.removeEventListener('pointercancel', this.onPointerUp);
    for (const group of [this.roads, this.trees, this.vegetation]) this.disposeGroup(group);
  }

  private need<T extends HTMLElement = HTMLElement>(selector: string): T {
    const node = this.panel.querySelector<T>(selector);
    if (!node) throw new Error(`Phase 5A editor element missing: ${selector}`);
    return node;
  }

  private bindUI(): void {
    this.layerControls.forEach((control) => control.addEventListener('change', () => this.updateLayerVisibility()));
    this.editButton.addEventListener('click', () => this.setEditing(!this.editing));
    this.addTreeButton.addEventListener('click', () => this.addTree());
    this.saveButton.addEventListener('click', () => void this.save());
    this.undoButton.addEventListener('click', () => this.undo());
    this.revertButton.addEventListener('click', () => this.revertSelected());
    this.resetButton.addEventListener('click', () => this.resetEdits());
    this.need<HTMLButtonElement>('#phase5-apply').addEventListener('click', () => this.applyFields());
    this.need<HTMLButtonElement>('#phase5-delete').addEventListener('click', () => this.flagDelete());
  }

  private setEditing(enabled: boolean): void {
    this.editing = enabled;
    this.panel.classList.toggle('editing', enabled);
    document.body.classList.toggle('feature-edit-mode', enabled);
    this.canvas.classList.toggle('feature-editing', enabled);
    this.setCameraInputEnabled(!enabled);
    this.editButton.textContent = enabled ? '編集モード終了' : '編集モード';
    this.status.textContent = enabled ? '編集モード：地物をクリックして選択。樹木はドラッグ移動、道路は先頭制御点をドラッグ。' : `編集モード終了 · 道路 ${this.dataset?.roads.length ?? 0} · 樹木 ${this.dataset?.trees.length ?? 0}`;
  }

  private effective<T extends RoadFeature | TreeFeature | VegetationFeature>(feature: T): T {
    const copy = clone(feature);
    const patch = this.edits.edits[feature.featureId];
    if (patch) this.applyPatch(copy, patch);
    return copy;
  }

  private applyPatch(feature: RoadFeature | TreeFeature | VegetationFeature, patch: FeaturePatch): void {
    if (patch.set) for (const [key, value] of Object.entries(patch.set)) (feature as unknown as Record<string, unknown>)[key] = value;
    if (patch.controlPoint) {
      const point = [patch.controlPoint.eastM, patch.controlPoint.northM] as [number, number];
      if ('treeId' in feature) { feature.localX = point[0]; feature.localNorth = point[1]; }
      else if ('coordinatesLocalEN' in feature && feature.coordinatesLocalEN.length) feature.coordinatesLocalEN[patch.controlPoint.index] = point;
    }
  }

  private buildLayers(): void {
    if (!this.dataset) return;
    for (const group of [this.roads, this.trees, this.vegetation]) this.disposeGroup(group);
    this.roads.clear(); this.trees.clear(); this.vegetation.clear();
    const deleted = new Set(this.edits.deleted);
    for (const source of this.dataset.roads) if (!deleted.has(source.featureId)) this.drawRoad(this.effective(source));
    for (const source of this.dataset.vegetation) if (!deleted.has(source.featureId)) this.drawVegetation(this.effective(source));
    for (const source of this.dataset.trees) if (!deleted.has(source.featureId)) this.drawTree(this.effective(source));
    for (const feature of Object.values(this.edits.additions)) if (!deleted.has(feature.featureId)) this.drawTree(feature);
    this.updateLayerVisibility();
    this.hideDuplicateV07Displays();
    this.refreshSelection();
  }

  private drawRoad(feature: RoadFeature): void {
    const color = feature.geometryType === 'area' ? ROAD_AREA_COLOR : ROAD_COLOR;
    if (feature.geometryType === 'area' && feature.polygonsLocalEN?.length) {
      this.drawPolygons(this.roads, feature.featureId, feature.polygonsLocalEN, color, 0.065, feature);
      return;
    }
    const points = feature.coordinatesLocalEN;
    if (points.length < 2) return;
    const half = Math.max(0.6, Math.min(12, feature.widthM / 2));
    const positions: number[] = [];
    const indices: number[] = [];
    for (let i = 0; i < points.length; i += 1) {
      const before = points[Math.max(0, i - 1)];
      const after = points[Math.min(points.length - 1, i + 1)];
      const dx = after[0] - before[0]; const dn = after[1] - before[1];
      const length = Math.hypot(dx, dn) || 1;
      const ox = -(dn / length) * half; const on = (dx / length) * half;
      positions.push(points[i][0] + ox, 0, -points[i][1] - on, points[i][0] - ox, 0, -points[i][1] + on);
      if (i > 0) { const a = (i - 1) * 2; indices.push(a, a + 1, a + 2, a + 1, a + 3, a + 2); }
    }
    const geometry = new BufferGeometry(); geometry.setAttribute('position', new Float32BufferAttribute(positions, 3)); geometry.setIndex(indices); geometry.computeVertexNormals();
    const mesh = new Mesh(geometry, new MeshStandardMaterial({ color, roughness: 0.92, side: DoubleSide }));
    mesh.position.y = 0.065; mesh.userData = { featureId: feature.featureId, featureKind: 'road', feature };
    mesh.receiveShadow = true; this.roads.add(mesh);
  }

  private drawVegetation(feature: VegetationFeature): void {
    const polys = feature.polygonsLocalEN ?? [];
    if (polys.length) this.drawPolygons(this.vegetation, feature.featureId, polys, this.vegetationColor(feature.vegetationClass), 0.035, feature);
    else if (feature.coordinatesLocalEN.length > 1) {
      const material = new LineBasicMaterial({ color: this.vegetationColor(feature.vegetationClass), linewidth: 2 });
      const line = new Line(new BufferGeometry().setFromPoints(feature.coordinatesLocalEN.map(([x, north]) => new Vector3(x, 0.04, -north))), material);
      line.userData = { featureId: feature.featureId, featureKind: 'vegetation', feature }; this.vegetation.add(line);
    }
  }

  private drawPolygons(group: Group, featureId: string, polys: Array<{ outer: [number, number][]; holes: [number, number][][] }>, color: number, y: number, feature: RoadFeature | VegetationFeature): void {
    for (const polygon of polys) {
      if (polygon.outer.length < 4) continue;
      const shape = new Shape(loop(polygon.outer)); shape.closePath();
      shape.holes = polygon.holes.map((points) => { const hole = new Shape(loop(points)); hole.closePath(); return hole; });
      const mesh = new Mesh(new ShapeGeometry(shape), new MeshStandardMaterial({ color, roughness: 0.9, side: DoubleSide }));
      mesh.rotation.x = -Math.PI / 2; mesh.position.y = y; mesh.userData = { featureId, featureKind: featureClass(feature), feature };
      mesh.receiveShadow = true; group.add(mesh);
    }
  }

  private drawTree(feature: TreeFeature): void {
    const height = feature.height ?? 6;
    const crown = feature.crownDiameter ?? 4;
    const root = new Group(); root.position.set(feature.localX, 0, -feature.localNorth); root.rotation.y = feature.rotation ?? 0;
    const estimated = feature.height == null || feature.crownDiameter == null;
    const trunkMaterial = new MeshStandardMaterial({ color: 0x6c5140, roughness: 1 });
    const leaves = new MeshStandardMaterial({ color: feature.modelType === 'columnar' ? 0x577a55 : 0x62865a, roughness: 0.94 });
    const trunk = new Mesh(new CylinderGeometry(0.13, 0.2, height * 0.56, 6), trunkMaterial); trunk.position.y = height * 0.28; root.add(trunk);
    const crownGeom = feature.modelType === 'columnar' ? new CylinderGeometry(crown * 0.22, crown * 0.42, height * 0.6, 7) : new SphereGeometry(crown * 0.5, 8, 6);
    const canopy = new Mesh(crownGeom, leaves); canopy.position.y = height * 0.72; if (feature.modelType !== 'columnar') canopy.scale.y = 1.12; root.add(canopy);
    root.traverse((object) => { if (object instanceof Mesh) { object.castShadow = true; object.userData = { featureId: feature.featureId, featureKind: 'tree', feature, estimatedDisplaySize: estimated }; } });
    root.userData = { featureId: feature.featureId, featureKind: 'tree', feature, estimatedDisplaySize: estimated };
    this.trees.add(root);
  }

  private vegetationColor(type: string): number {
    const key = type.toLowerCase(); return Object.entries(VEGETATION_COLORS).find(([part]) => key.includes(part))?.[1] ?? 0x6f955f;
  }

  private updateLayerVisibility(): void {
    this.roads.visible = this.layerControls[0].checked;
    this.trees.visible = this.layerControls[1].checked;
    this.vegetation.visible = this.layerControls[2].checked;
  }

  private hideDuplicateV07Displays(): void {
    // OSM layers replace corresponding v07 display overlays only; buildings, parks, water, and bridges remain untouched.
    this.scene.traverse((object) => {
      if (object === this.roads || object === this.trees || object === this.vegetation) return;
      const type = object.userData?.feature_type;
      if (type === 'road_display' && this.dataset?.roads.length) object.visible = false;
      if (type === 'tree_visual' && this.dataset?.trees.length) object.visible = false;
      if (type === 'green_display' && this.dataset?.vegetation.length) object.visible = false;
    });
  }

  private readonly onPointerDown = (event: PointerEvent): void => {
    if (!this.editing || event.button !== 0 || (event.target as Element).closest('.phase5-panel')) return;
    this.dragging = true; this.dragMoved = false; this.dragStart.set(event.clientX, event.clientY); this.dragPoint = undefined;
    this.canvas.setPointerCapture(event.pointerId);
    const hit = this.pick(event);
    if (!hit) { this.select(undefined); return; }
    const id = hit.object.userData.featureId as string | undefined;
    if (!id) return;
    this.select(id);
    this.dragPoint = new Vector3();
    this.raycaster.setFromCamera(this.pointerNdc(event), this.camera);
    this.raycaster.ray.intersectPlane(this.ground, this.dragPoint);
  };

  private readonly onPointerMove = (event: PointerEvent): void => {
    if (!this.editing || !this.dragging || !this.selectedId || !this.dragPoint) return;
    if (Math.hypot(event.clientX - this.dragStart.x, event.clientY - this.dragStart.y) < 3) return;
    const feature = this.getFeature(this.selectedId); if (!feature) return;
    const world = new Vector3(); this.raycaster.setFromCamera(this.pointerNdc(event), this.camera);
    if (!this.raycaster.ray.intersectPlane(this.ground, world)) return;
    if (!this.dragMoved) this.pushUndo();
    this.dragMoved = true;
    let patch = this.edits.edits[this.selectedId] ?? { baseFeatureHash: feature.sourceHash ?? '' };
    if ('treeId' in feature && this.edits.additions[this.selectedId]) {
      const addition = this.edits.additions[this.selectedId]; addition.localX = world.x; addition.localNorth = -world.z;
    } else if ('treeId' in feature) {
      patch.controlPoint = { index: 0, eastM: world.x, northM: -world.z };
    } else if ('highway' in feature && feature.coordinatesLocalEN.length) {
      const current = feature.coordinatesLocalEN[0];
      const dx = world.x - this.dragPoint.x; const dn = -world.z + this.dragPoint.z;
      patch.controlPoint = { index: 0, eastM: current[0] + dx, northM: current[1] + dn };
    }
    this.edits.edits[this.selectedId] = patch;
    this.dragPoint.copy(world);
    this.buildLayers();
  };

  private readonly onPointerUp = (event: PointerEvent): void => {
    if (!this.dragging) return;
    this.dragging = false;
    if (!this.dragMoved && this.editing) {
      const hit = this.pick(event); this.select(hit?.object.userData.featureId as string | undefined);
    }
  };

  private pointerNdc(event: PointerEvent): Vector2 {
    const rect = this.canvas.getBoundingClientRect(); return new Vector2(((event.clientX - rect.left) / rect.width) * 2 - 1, -((event.clientY - rect.top) / rect.height) * 2 + 1);
  }

  private pick(event: PointerEvent): import('three').Intersection | undefined {
    this.raycaster.setFromCamera(this.pointerNdc(event), this.camera);
    const objects: import('three').Object3D[] = [];
    for (const group of [this.roads, this.trees, this.vegetation]) if (group.visible) objects.push(...group.children);
    return this.raycaster.intersectObjects(objects, true).find((hit) => Boolean(hit.object.userData.featureId));
  }

  private select(id?: string): void {
    this.selectedId = id; this.selectPanel.hidden = !id;
    if (!id) return;
    const feature = this.getFeature(id); if (!feature) return;
    this.title.textContent = `${featureClass(feature).toUpperCase()} · ${id}`;
    const patch = this.edits.edits[id];
    const src = 'source' in feature ? feature.source : 'OpenStreetMap';
    this.details.textContent = `${src} · ${'widthSource' in feature ? feature.widthSource : 'treeId' in feature ? feature.confidence : feature.vegetationClass} · ${patch ? '編集差分あり' : '元データ'}`;
    this.renderFields(feature);
  }

  private refreshSelection(): void { if (this.selectedId) this.select(this.selectedId); }

  private renderFields(feature: RoadFeature | TreeFeature | VegetationFeature): void {
    this.fields.replaceChildren();
    const addInput = (labelText: string, key: string, value: string | number | null | undefined, type = 'text'): void => {
      const label = document.createElement('label'); label.textContent = labelText;
      const input = document.createElement('input'); input.dataset.key = key; input.type = type; input.value = value == null ? '' : String(value); label.append(input); this.fields.append(label);
    };
    if ('highway' in feature) {
      addInput('幅 m（未計測は推定）', 'widthM', feature.widthM, 'number'); addInput('道路種別', 'highway', feature.highway); addInput('舗装', 'surface', feature.surface);
      const point = feature.coordinatesLocalEN[0]; if (point) { addInput('先頭点 東 m', 'pointEast', point[0], 'number'); addInput('先頭点 北 m', 'pointNorth', point[1], 'number'); }
    } else if ('treeId' in feature) {
      addInput('東 m', 'localX', feature.localX, 'number'); addInput('北 m', 'localNorth', feature.localNorth, 'number');
      addInput('高さ m（推定値を含む）', 'height', feature.height, 'number'); addInput('樹冠径 m（推定値を含む）', 'crownDiameter', feature.crownDiameter, 'number');
      addInput('樹種', 'species', feature.species); addInput('表示モデル', 'modelType', feature.modelType);
      addInput('回転 rad', 'rotation', feature.rotation, 'number');
    } else {
      const note = document.createElement('p'); note.textContent = '植栽ポリゴンは元データ保持のため読取専用です。'; this.fields.append(note);
    }
  }

  private applyFields(): void {
    if (!this.selectedId) return;
    const feature = this.getFeature(this.selectedId); if (!feature || 'vegetationClass' in feature) return;
    this.pushUndo();
    const set: Record<string, string | number | null> = {};
    for (const input of this.fields.querySelectorAll<HTMLInputElement>('input[data-key]')) {
      const key = input.dataset.key!;
      if (key === 'pointEast' || key === 'pointNorth') continue;
      const numeric = input.type === 'number';
      set[key] = input.value === '' ? null : numeric ? Number(input.value) : input.value;
    }
    for (const value of Object.values(set)) if (typeof value === 'number' && !Number.isFinite(value)) {
      this.status.textContent = '入力エラー: 数値は有限値で指定してください。'; return;
    }
    const addition = this.edits.additions[this.selectedId];
    if (addition) {
      Object.assign(addition, set);
      this.buildLayers(); return;
    }
    const patch = this.edits.edits[this.selectedId] ?? { baseFeatureHash: feature.sourceHash ?? '' };
    patch.set = { ...patch.set, ...set };
    if ('highway' in feature) {
      const east = Number(this.fields.querySelector<HTMLInputElement>('[data-key="pointEast"]')?.value);
      const north = Number(this.fields.querySelector<HTMLInputElement>('[data-key="pointNorth"]')?.value);
      if (Number.isFinite(east) && Number.isFinite(north)) patch.controlPoint = { index: 0, eastM: east, northM: north };
    }
    this.edits.edits[this.selectedId] = patch;
    this.buildLayers();
  }

  private getFeature(id: string): RoadFeature | TreeFeature | VegetationFeature | undefined {
    if (this.edits.additions[id]) return this.edits.additions[id];
    const source = [...(this.dataset?.roads ?? []), ...(this.dataset?.trees ?? []), ...(this.dataset?.vegetation ?? [])].find((feature) => feature.featureId === id);
    return source ? this.effective(source) : undefined;
  }

  private addTree(): void {
    if (!this.dataset) return;
    this.pushUndo();
    const id = `manual:${crypto.randomUUID()}`;
    const [minX, minN, maxX, maxN] = this.dataset.boundsLocalM;
    const feature: TreeFeature = { featureId: id, treeId: id, sourceOsmId: id, sourceHash: '', latitude: null, longitude: null,
      localX: (minX + maxX) / 2, localNorth: (minN + maxN) / 2, height: null, crownDiameter: null, trunkDiameter: null,
      species: null, modelType: 'generic-tree', rotation: 0, source: 'manual', confidence: 'manual placement; unverified', edited: true };
    this.edits.additions[id] = feature; this.select(id); this.buildLayers(); this.status.textContent = '手動樹木：位置と寸法は未検証。推定表示サイズを使用します。';
  }

  private pushUndo(): void { this.undoStack.push(clone(this.edits)); if (this.undoStack.length > 20) this.undoStack.shift(); }
  private undo(): void { const previous = this.undoStack.pop(); if (!previous) return; this.edits = previous; this.buildLayers(); }
  private revertSelected(): void {
    if (!this.selectedId) return;
    this.pushUndo(); delete this.edits.edits[this.selectedId];
    if (this.edits.additions[this.selectedId]) delete this.edits.additions[this.selectedId];
    this.edits.deleted = this.edits.deleted.filter((id) => id !== this.selectedId);
    this.buildLayers();
  }
  private flagDelete(): void {
    if (!this.selectedId) return;
    const feature = this.getFeature(this.selectedId); if (!feature) return;
    this.pushUndo();
    if (!this.edits.deleted.includes(this.selectedId)) this.edits.deleted.push(this.selectedId);
    this.buildLayers(); this.selectPanel.hidden = true;
    this.status.textContent = `削除フラグを差分に保存しました: ${this.selectedId}`;
  }
  private resetEdits(): void { if (!this.dataset) return; this.pushUndo(); this.edits = emptyEdits(this.dataset.sourceSha256); this.buildLayers(); }

  private async save(): Promise<void> {
    const response = await fetch('/phase5a-api/edits', { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(this.edits) });
    const result = await response.json();
    this.status.textContent = response.ok ? `ローカル保存済み · 差分 ${result.edits} · 手動追加 ${result.additions}` : `保存失敗: ${result.error ?? response.status}`;
  }

  private disposeGroup(group: Group): void {
    group.traverse((object) => {
      if (object instanceof Mesh) { object.geometry.dispose(); const materials = Array.isArray(object.material) ? object.material : [object.material]; materials.forEach((material) => material.dispose()); }
      else if ('geometry' in object && object.geometry instanceof BufferGeometry) { object.geometry.dispose(); }
    });
  }
}
