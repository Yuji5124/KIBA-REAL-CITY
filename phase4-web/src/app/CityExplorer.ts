import { ExplorerControls } from '../controls/ExplorerControls';
import { DebugPanel } from '../diagnostics/DebugPanel';
import { loadCityModel } from '../loaders/loadCityModel';
import { createScene } from '../scene/createScene';
import { FeatureEditor } from '../phase5a/FeatureEditor';
import type { AppUI, ExplorerMode } from '../types';

export class CityExplorer {
  private readonly runtime;
  private controls?: ExplorerControls;
  private debug?: DebugPanel;
  private phase5?: FeatureEditor;
  private animationId = 0;
  private lastFrame = 0;
  private contextLost = false;
  private loadStarted = 0;

  constructor(private readonly ui: AppUI) {
    this.runtime = createScene(ui.canvas);
    this.bindUI();
    this.setControlsEnabled(false);
    window.addEventListener('resize', this.runtime.resize);
    ui.canvas.addEventListener('webglcontextlost', this.onContextLost);
    ui.canvas.addEventListener('webglcontextrestored', this.onContextRestored);
    document.addEventListener('visibilitychange', this.onVisibilityChange);
  }

  async start(): Promise<void> {
    this.loadStarted = performance.now();
    try {
      const { info, geo } = await loadCityModel((fraction) => {
        this.ui.progress.style.transform = `scaleX(${Math.max(0.04, fraction)})`;
      });
      info.root.traverse((object) => {
        if ('isMesh' in object && object.isMesh) {
          object.castShadow = true;
          object.receiveShadow = true;
        }
      });
      this.runtime.scene.add(info.root);
      this.controls = new ExplorerControls(this.runtime.camera, this.ui.canvas, this.ui, geo, info.buildingBoxes, info.bounds);
      this.phase5 = new FeatureEditor(this.runtime.scene, this.ui.canvas, this.runtime.camera, this.ui.phase5Panel,
        (enabled) => this.controls?.setPointerInteractionEnabled(enabled));
      void this.phase5.load();
      this.setControlsEnabled(true);
      this.debug = new DebugPanel(this.ui.debugPanel, this.runtime.renderer, this.runtime.camera, info, geo);
      const width = info.bounds.max.x - info.bounds.min.x;
      const depth = info.bounds.max.z - info.bounds.min.z;
      this.ui.loadStatus.textContent = `${info.meshes.toLocaleString()} meshes · ${info.buildings} buildings`;
      this.ui.progress.classList.add('done');
      this.ui.errorPanel.hidden = true;
      this.reportLoad(info, width, depth, geo.phase3d.extent_width_m, geo.phase3d.extent_height_m, geo.center_projected_m);
      this.lastFrame = performance.now();
      this.animationId = requestAnimationFrame(this.frame);
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      this.ui.loadStatus.textContent = '読み込みに失敗しました';
      this.ui.progress.classList.add('failed');
      this.ui.errorPanel.hidden = false;
      this.ui.errorPanel.textContent = `都市データを読み込めませんでした: ${message}。v07 FLAT GLBと地理参照JSONのファイル・SHA-256を確認してください。`;
      console.error(error);
    }
  }

  dispose(): void {
    cancelAnimationFrame(this.animationId);
    this.controls?.dispose();
    this.phase5?.dispose();
    window.removeEventListener('resize', this.runtime.resize);
    document.removeEventListener('visibilitychange', this.onVisibilityChange);
    this.ui.canvas.removeEventListener('webglcontextlost', this.onContextLost);
    this.ui.canvas.removeEventListener('webglcontextrestored', this.onContextRestored);
    this.runtime.renderer.dispose();
  }

  private bindUI(): void {
    this.ui.walkButton.addEventListener('click', () => this.setMode('walk'));
    this.ui.flyButton.addEventListener('click', () => this.setMode('fly'));
    this.ui.resetButton.addEventListener('click', () => this.controls?.reset());
    this.ui.ascendButton.addEventListener('click', () => this.controls?.changeAltitude(15));
    this.ui.descendButton.addEventListener('click', () => this.controls?.changeAltitude(-15));
  }

  private setControlsEnabled(enabled: boolean): void {
    this.ui.walkButton.disabled = !enabled;
    this.ui.flyButton.disabled = !enabled;
    this.ui.resetButton.disabled = !enabled;
    this.ui.ascendButton.disabled = !enabled;
    this.ui.descendButton.disabled = !enabled;
  }

  private setMode(mode: ExplorerMode): void { this.controls?.setMode(mode); }

  private readonly frame = (now: number): void => {
    this.animationId = requestAnimationFrame(this.frame);
    if (document.hidden || this.contextLost || !this.controls) return;
    const dt = Math.max(0, Math.min((now - this.lastFrame) / 1000, 0.1));
    this.lastFrame = now;
    this.controls.update(dt);
    this.runtime.renderer.render(this.runtime.scene, this.runtime.camera);
    this.debug?.update(dt);
  };

  private readonly onVisibilityChange = (): void => { this.lastFrame = performance.now(); };

  private readonly onContextLost = (event: Event): void => {
    event.preventDefault();
    this.contextLost = true;
    this.ui.loadStatus.textContent = 'WebGLが一時停止しました';
  };

  private readonly onContextRestored = (): void => {
    this.contextLost = false;
    this.lastFrame = performance.now();
    this.ui.loadStatus.textContent = 'WebGLを再開しました';
  };

  private reportLoad(info: Awaited<ReturnType<typeof loadCityModel>>['info'], width: number, depth: number, expectedWidth: number, expectedDepth: number, origin: [number, number]): void {
    const loadMs = performance.now() - this.loadStarted;
    const record = {
      loaded: true,
      glbBytes: info.fileSizeBytes,
      glbLoadMilliseconds: Math.round(loadMs),
      glbMeshDefinitions: info.meshes,
      threeSceneMeshes: info.renderMeshes,
      uniqueBuildingIds: info.buildings,
      triangles: info.triangles,
      modelBoundsThreeYUp: { min: info.bounds.min.toArray(), max: info.bounds.max.toArray() },
      widthX_m: width,
      northSouthZ_m: depth,
      expectedExtent_m: { eastWest: expectedWidth, northSouth: expectedDepth },
      geometryAxisMapping: 'Three.js Y-up: X=east, Y=up, Z=-north; source GLB bytes and geometry are unchanged.',
      centerProjectedEPSG6677_m: origin,
      crs: 'EPSG:6677',
      noGeometryTransformApplied: true,
    };
    console.info('KIBA_REAL_CITY Phase 4A asset check', record);
    this.ui.canvas.dataset.assetLoaded = String(record.loaded);
    this.ui.canvas.dataset.meshCount = String(record.glbMeshDefinitions);
    this.ui.canvas.dataset.sceneMeshCount = String(record.threeSceneMeshes);
    this.ui.canvas.dataset.buildingCount = String(record.uniqueBuildingIds);
    this.ui.canvas.dataset.loadMs = String(record.glbLoadMilliseconds);
  }
}
