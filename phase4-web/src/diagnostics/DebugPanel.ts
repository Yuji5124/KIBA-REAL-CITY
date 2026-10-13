import type { Box3, Camera, WebGLRenderer } from 'three';
import type { CityModelInfo, GeoReference } from '../types';

const fmt = (value: number): string => Number.isFinite(value) ? value.toFixed(2) : '取得不可';

export class DebugPanel {
  private readonly enabled = new URLSearchParams(location.search).get('debug') === '1';
  private frameTimes: number[] = [];
  private lastPaint = 0;
  private readonly rows = new Map<string, HTMLElement>();

  constructor(
    private readonly element: HTMLElement,
    private readonly renderer: WebGLRenderer,
    private readonly camera: Camera,
    model: CityModelInfo,
    private readonly geo: GeoReference,
  ) {
    element.hidden = !this.enabled;
    if (!this.enabled) return;
    element.innerHTML = `
      <div class="debug-title">診断 <button id="debug-close" type="button" aria-label="診断を閉じる">×</button></div>
      <div class="debug-grid"></div>
      <label class="shadow-toggle"><input id="shadow-toggle" type="checkbox"> 影を有効化（負荷増）</label>`;
    const grid = element.querySelector('.debug-grid');
    const fields = ['FPS', 'Frame', 'Draw Calls', 'Triangles', 'GLB Meshes', 'Scene Meshes', 'Buildings', 'GLB Load', 'Camera', 'Camera Angle', 'Camera Y', 'Projected EN', 'Model Bounds', 'WebGL', 'Pixel Ratio'];
    for (const name of fields) {
      const row = document.createElement('div');
      row.className = 'debug-row';
      row.innerHTML = `<span>${name}</span><strong>取得不可</strong>`;
      grid?.append(row);
      this.rows.set(name, row.querySelector('strong')!);
    }
    element.querySelector<HTMLButtonElement>('#debug-close')?.addEventListener('click', () => { element.hidden = true; });
    const toggle = element.querySelector<HTMLInputElement>('#shadow-toggle');
    toggle?.addEventListener('change', () => { renderer.shadowMap.enabled = toggle.checked; });
    const gl = renderer.getContext();
    const extension = gl.getExtension('WEBGL_debug_renderer_info');
    const rendererName = extension ? gl.getParameter(extension.UNMASKED_RENDERER_WEBGL) as string : gl.getParameter(gl.RENDERER) as string;
    this.set('WebGL', rendererName || '取得不可');
    this.set('GLB Meshes', String(model.meshes));
    this.set('Scene Meshes', String(model.renderMeshes));
    this.set('Buildings', String(model.buildings));
    this.set('GLB Load', `${(model.loadMs / 1000).toFixed(2)} s`);
    this.set('Pixel Ratio', fmt(renderer.getPixelRatio()));
    this.set('Model Bounds', `${fmt(model.bounds.min.x)}..${fmt(model.bounds.max.x)} X / ${fmt(model.bounds.min.z)}..${fmt(model.bounds.max.z)} Z`);
  }

  update(deltaSeconds: number): void {
    if (!this.enabled || this.element.hidden) return;
    this.frameTimes.push(Math.max(0, deltaSeconds * 1000));
    if (this.frameTimes.length > 60) this.frameTimes.shift();
    const now = performance.now();
    if (now - this.lastPaint < 250) return;
    this.lastPaint = now;
    const average = this.frameTimes.reduce((sum, item) => sum + item, 0) / Math.max(this.frameTimes.length, 1);
    const p = this.camera.position;
    this.set('FPS', fmt(average > 0 ? 1000 / average : NaN));
    this.set('Frame', `${fmt(average)} ms`);
    this.set('Draw Calls', String(this.renderer.info.render.calls));
    this.set('Triangles', this.renderer.info.render.triangles.toLocaleString());
    this.set('Camera', `${fmt(p.x)}, ${fmt(p.y)}, ${fmt(p.z)}`);
    this.set('Camera Angle', `${fmt(this.camera.rotation.y)} yaw / ${fmt(this.camera.rotation.x)} pitch`);
    this.set('Camera Y', `${fmt(p.y)} m`);
    this.set('Projected EN', `${fmt(this.geo.center_projected_m[0] + p.x)}, ${fmt(this.geo.center_projected_m[1] - p.z)}`);
  }

  private set(name: string, value: string): void {
    const row = this.rows.get(name);
    if (row) row.textContent = value;
  }
}

export function modelBoundsAsArray(bounds: Box3): number[] {
  return [...bounds.min.toArray(), ...bounds.max.toArray()];
}
