import { Box3, PerspectiveCamera, Sphere, Vector2, Vector3 } from 'three';
import type { AppUI, ExplorerMode, GeoReference } from '../types';

const WALK_HEIGHT = 1.6;
const PLAYER_RADIUS = 0.32;
const GRID_SIZE = 50;

export class ExplorerControls {
  mode: ExplorerMode = 'fly';
  private yaw = 0;
  private pitch = -0.52;
  private readonly keys = new Set<string>();
  private draggingId: number | null = null;
  private lastPointer = new Vector2();
  private stickId: number | null = null;
  private stick = new Vector2();
  private readonly touchPointers = new Map<number, Vector2>();
  private pinchDistance = 0;
  private readonly cells = new Map<string, Box3[]>();
  private readonly limits: { minX: number; maxX: number; minZ: number; maxZ: number };
  private disposed = false;

  constructor(
    private readonly camera: PerspectiveCamera,
    private readonly canvas: HTMLCanvasElement,
    private readonly ui: AppUI,
    geo: GeoReference,
    buildingBoxes: Box3[],
    private readonly modelBounds: Box3,
  ) {
    const [minX, minNorth, maxX, maxNorth] = geo.phase3d.bounds_local_m;
    this.limits = { minX: minX + 3, maxX: maxX - 3, minZ: -maxNorth + 3, maxZ: -minNorth - 3 };
    this.buildCollisionGrid(buildingBoxes);
    this.bindEvents();
    this.setMode('fly');
    this.resetFly();
  }

  setMode(mode: ExplorerMode): void {
    this.mode = mode;
    this.ui.walkButton.classList.toggle('active', mode === 'walk');
    this.ui.flyButton.classList.toggle('active', mode === 'fly');
    this.ui.walkButton.setAttribute('aria-pressed', String(mode === 'walk'));
    this.ui.flyButton.setAttribute('aria-pressed', String(mode === 'fly'));
    this.ui.altitudeControls.hidden = mode !== 'fly';
    this.ui.hint.textContent = this.isTouch()
      ? mode === 'walk' ? '左スティックで移動　右側スワイプで視点' : 'WALK / FLY　右側スワイプで視点　＋／−で高度'
      : mode === 'walk' ? 'WASDで移動　ドラッグで視点　Shiftで加速　Escで解除' : 'WASDで移動　ドラッグで視点　E/Qで高度　ホイールでズーム';
    if (mode === 'walk') this.resetWalk();
    else this.resetFly();
  }

  reset(): void {
    if (this.mode === 'walk') this.resetWalk();
    else this.resetFly();
  }

  update(delta: number): void {
    if (this.disposed) return;
    const dt = Math.min(delta, 0.05);
    const input = this.movementInput();
    if (input.lengthSq() > 1) input.normalize();
    const sprint = this.keys.has('shift');
    const speed = this.mode === 'walk' ? (sprint ? 12 : 5) : (sprint ? 150 : 45);
    const right = new Vector3(Math.cos(this.yaw), 0, -Math.sin(this.yaw));
    const forward = new Vector3(-Math.sin(this.yaw), 0, -Math.cos(this.yaw));
    const move = right.multiplyScalar(input.x).addScaledVector(forward, -input.y).multiplyScalar(speed * dt);

    if (this.mode === 'walk') {
      const nextX = this.camera.position.x + move.x;
      const nextZ = this.camera.position.z + move.z;
      if (!this.isBuildingBlocked(nextX, this.camera.position.z)) this.camera.position.x = nextX;
      if (!this.isBuildingBlocked(this.camera.position.x, nextZ)) this.camera.position.z = nextZ;
      this.camera.position.x = this.clamp(this.camera.position.x, this.limits.minX, this.limits.maxX);
      this.camera.position.z = this.clamp(this.camera.position.z, this.limits.minZ, this.limits.maxZ);
      this.camera.position.y = WALK_HEIGHT;
    } else {
      this.camera.position.add(move);
      if (this.keys.has('e')) this.camera.position.y += speed * dt;
      if (this.keys.has('q')) this.camera.position.y -= speed * dt;
      this.camera.position.x = this.clamp(this.camera.position.x, this.limits.minX - 1500, this.limits.maxX + 1500);
      this.camera.position.z = this.clamp(this.camera.position.z, this.limits.minZ - 1500, this.limits.maxZ + 1500);
      this.camera.position.y = this.clamp(this.camera.position.y, 2, 2500);
    }
    this.camera.rotation.set(this.pitch, this.yaw, 0, 'YXZ');
  }

  dispose(): void {
    this.disposed = true;
    window.removeEventListener('keydown', this.onKeyDown);
    window.removeEventListener('keyup', this.onKeyUp);
    window.removeEventListener('blur', this.clearInput);
    this.canvas.removeEventListener('pointerdown', this.onCanvasPointerDown);
    this.canvas.removeEventListener('pointermove', this.onCanvasPointerMove);
    this.canvas.removeEventListener('pointerup', this.onCanvasPointerUp);
    this.canvas.removeEventListener('pointercancel', this.onCanvasPointerUp);
    this.canvas.removeEventListener('wheel', this.onWheel);
    this.ui.lookArea.removeEventListener('pointerdown', this.onLookDown);
    this.ui.lookArea.removeEventListener('pointermove', this.onLookMove);
    this.ui.lookArea.removeEventListener('pointerup', this.onLookUp);
    this.ui.lookArea.removeEventListener('pointercancel', this.onLookUp);
    this.ui.moveStick.removeEventListener('pointerdown', this.onStickDown);
    this.ui.moveStick.removeEventListener('pointermove', this.onStickMove);
    this.ui.moveStick.removeEventListener('pointerup', this.onStickUp);
    this.ui.moveStick.removeEventListener('pointercancel', this.onStickUp);
  }

  private bindEvents(): void {
    window.addEventListener('keydown', this.onKeyDown);
    window.addEventListener('keyup', this.onKeyUp);
    window.addEventListener('blur', this.clearInput);
    this.canvas.addEventListener('pointerdown', this.onCanvasPointerDown);
    this.canvas.addEventListener('pointermove', this.onCanvasPointerMove);
    this.canvas.addEventListener('pointerup', this.onCanvasPointerUp);
    this.canvas.addEventListener('pointercancel', this.onCanvasPointerUp);
    this.canvas.addEventListener('wheel', this.onWheel, { passive: false });
    this.ui.lookArea.addEventListener('pointerdown', this.onLookDown);
    this.ui.lookArea.addEventListener('pointermove', this.onLookMove);
    this.ui.lookArea.addEventListener('pointerup', this.onLookUp);
    this.ui.lookArea.addEventListener('pointercancel', this.onLookUp);
    this.ui.moveStick.addEventListener('pointerdown', this.onStickDown);
    this.ui.moveStick.addEventListener('pointermove', this.onStickMove);
    this.ui.moveStick.addEventListener('pointerup', this.onStickUp);
    this.ui.moveStick.addEventListener('pointercancel', this.onStickUp);
  }

  private readonly onKeyDown = (event: KeyboardEvent): void => {
    const key = event.key.toLowerCase();
    if (key === 'escape') {
      this.draggingId = null;
      return;
    }
    if (['w', 'a', 's', 'd', 'q', 'e', 'shift', 'arrowup', 'arrowdown', 'arrowleft', 'arrowright'].includes(key)) {
      this.keys.add(key);
      event.preventDefault();
    }
  };

  private readonly onKeyUp = (event: KeyboardEvent): void => { this.keys.delete(event.key.toLowerCase()); };
  private readonly clearInput = (): void => { this.keys.clear(); this.stick.set(0, 0); this.draggingId = null; };

  private readonly onCanvasPointerDown = (event: PointerEvent): void => {
    if (event.pointerType === 'touch') return;
    if (event.button !== 0) return;
    this.draggingId = event.pointerId;
    this.lastPointer.set(event.clientX, event.clientY);
    this.canvas.setPointerCapture(event.pointerId);
  };

  private readonly onCanvasPointerMove = (event: PointerEvent): void => {
    if (this.draggingId !== event.pointerId) return;
    this.rotateBy(event.clientX - this.lastPointer.x, event.clientY - this.lastPointer.y);
    this.lastPointer.set(event.clientX, event.clientY);
  };

  private readonly onCanvasPointerUp = (event: PointerEvent): void => {
    if (this.draggingId === event.pointerId) this.draggingId = null;
  };

  private readonly onLookDown = (event: PointerEvent): void => {
    if (event.pointerType !== 'touch') return;
    this.ui.lookArea.setPointerCapture(event.pointerId);
    this.touchPointers.set(event.pointerId, new Vector2(event.clientX, event.clientY));
    if (this.touchPointers.size === 1) {
      this.draggingId = event.pointerId;
      this.lastPointer.set(event.clientX, event.clientY);
    } else if (this.touchPointers.size === 2) {
      this.draggingId = null;
      this.pinchDistance = this.currentPinchDistance();
    }
    event.preventDefault();
  };

  private readonly onLookMove = (event: PointerEvent): void => {
    if (!this.touchPointers.has(event.pointerId)) return;
    this.touchPointers.set(event.pointerId, new Vector2(event.clientX, event.clientY));
    if (this.touchPointers.size >= 2) {
      const distance = this.currentPinchDistance();
      if (this.pinchDistance > 0) {
        this.camera.translateZ((this.pinchDistance - distance) * 0.75);
        this.camera.position.y = this.clamp(this.camera.position.y, 2, 2500);
      }
      this.pinchDistance = distance;
    } else if (this.draggingId === event.pointerId) {
      this.rotateBy(event.clientX - this.lastPointer.x, event.clientY - this.lastPointer.y);
      this.lastPointer.set(event.clientX, event.clientY);
    }
    event.preventDefault();
  };

  private readonly onLookUp = (event: PointerEvent): void => {
    this.touchPointers.delete(event.pointerId);
    if (this.draggingId === event.pointerId) this.draggingId = null;
    this.pinchDistance = this.touchPointers.size === 2 ? this.currentPinchDistance() : 0;
    if (this.touchPointers.size === 1) {
      const [id, point] = [...this.touchPointers.entries()][0];
      this.draggingId = id;
      this.lastPointer.copy(point);
    }
  };

  private readonly onWheel = (event: WheelEvent): void => {
    if (this.mode !== 'fly') return;
    event.preventDefault();
    this.camera.translateZ(Math.sign(event.deltaY) * Math.min(Math.abs(event.deltaY) * 0.45, 180));
    this.camera.position.y = this.clamp(this.camera.position.y, 2, 2500);
  };

  changeAltitude(delta: number): void {
    if (this.mode !== 'fly') return;
    this.camera.position.y = this.clamp(this.camera.position.y + delta, 2, 2500);
  }

  private readonly onStickDown = (event: PointerEvent): void => {
    this.stickId = event.pointerId;
    this.ui.moveStick.setPointerCapture(event.pointerId);
    this.updateStick(event);
  };

  private readonly onStickMove = (event: PointerEvent): void => { if (event.pointerId === this.stickId) this.updateStick(event); };
  private readonly onStickUp = (event: PointerEvent): void => {
    if (event.pointerId !== this.stickId) return;
    this.stickId = null;
    this.stick.set(0, 0);
    this.setStickVisual(0, 0);
  };

  private updateStick(event: PointerEvent): void {
    const rect = this.ui.moveStick.getBoundingClientRect();
    const radius = Math.min(rect.width, rect.height) * 0.37;
    const dx = event.clientX - (rect.left + rect.width / 2);
    const dy = event.clientY - (rect.top + rect.height / 2);
    const length = Math.hypot(dx, dy);
    const scale = length > radius ? radius / length : 1;
    const x = dx * scale;
    const y = dy * scale;
    this.stick.set(x / radius, y / radius);
    this.setStickVisual(x, y);
  }

  private currentPinchDistance(): number {
    const points = [...this.touchPointers.values()];
    return points.length < 2 ? 0 : points[0].distanceTo(points[1]);
  }

  private setStickVisual(x: number, y: number): void {
    this.ui.moveStick.style.setProperty('--stick-x', `${x}px`);
    this.ui.moveStick.style.setProperty('--stick-y', `${y}px`);
  }

  private rotateBy(dx: number, dy: number): void {
    this.yaw -= dx * 0.0035;
    this.pitch = this.clamp(this.pitch - dy * 0.003, -1.48, 1.48);
    this.camera.rotation.set(this.pitch, this.yaw, 0, 'YXZ');
  }

  private movementInput(): Vector2 {
    const x = Number(this.keys.has('d') || this.keys.has('arrowright')) - Number(this.keys.has('a') || this.keys.has('arrowleft')) + this.stick.x;
    const y = Number(this.keys.has('s') || this.keys.has('arrowdown')) - Number(this.keys.has('w') || this.keys.has('arrowup')) + this.stick.y;
    return new Vector2(this.clamp(x, -1, 1), this.clamp(y, -1, 1));
  }

  private resetWalk(): void {
    const safe = this.findSafeSpawn();
    this.camera.position.set(safe.x, WALK_HEIGHT, safe.y);
    this.yaw = 0;
    this.pitch = 0;
    this.camera.rotation.set(this.pitch, this.yaw, 0, 'YXZ');
  }

  private resetFly(): void {
    const center = this.modelBounds.getCenter(new Vector3());
    const radius = this.modelBounds.getBoundingSphere(new Sphere()).radius;
    const aspect = Math.max(this.camera.aspect, 0.1);
    const fitFov = 2 * Math.atan(Math.tan((this.camera.fov * Math.PI) / 360) * Math.min(1, aspect));
    const distance = radius / Math.sin(fitFov / 2) * 1.2;
    const direction = new Vector3(0.34, 0.76, 0.56).normalize();
    this.camera.position.copy(center).addScaledVector(direction, distance);
    this.camera.lookAt(center);
    this.yaw = this.camera.rotation.y;
    this.pitch = this.camera.rotation.x;
  }

  private findSafeSpawn(): Vector2 {
    const candidates = [new Vector2(0, 0)];
    for (let radius = 8; radius <= 100; radius += 8) {
      for (let step = 0; step < 16; step += 1) {
        const angle = (Math.PI * 2 * step) / 16;
        candidates.push(new Vector2(Math.cos(angle) * radius, Math.sin(angle) * radius));
      }
    }
    return candidates.find((point) => !this.isBuildingBlocked(point.x, point.y)) ?? new Vector2(0, 0);
  }

  private buildCollisionGrid(boxes: Box3[]): void {
    for (const box of boxes) {
      if (box.max.y < 0 || box.min.y > WALK_HEIGHT + 1) continue;
      const minCellX = Math.floor(box.min.x / GRID_SIZE);
      const maxCellX = Math.floor(box.max.x / GRID_SIZE);
      const minCellZ = Math.floor(box.min.z / GRID_SIZE);
      const maxCellZ = Math.floor(box.max.z / GRID_SIZE);
      for (let x = minCellX; x <= maxCellX; x += 1) {
        for (let z = minCellZ; z <= maxCellZ; z += 1) {
          const key = `${x},${z}`;
          const cell = this.cells.get(key) ?? [];
          cell.push(box);
          this.cells.set(key, cell);
        }
      }
    }
  }

  private isBuildingBlocked(x: number, z: number): boolean {
    const key = `${Math.floor(x / GRID_SIZE)},${Math.floor(z / GRID_SIZE)}`;
    for (const box of this.cells.get(key) ?? []) {
      if (box.max.y <= 0 || box.min.y > WALK_HEIGHT + 0.3) continue;
      if (x + PLAYER_RADIUS > box.min.x && x - PLAYER_RADIUS < box.max.x && z + PLAYER_RADIUS > box.min.z && z - PLAYER_RADIUS < box.max.z) return true;
    }
    return false;
  }

  private isTouch(): boolean { return navigator.maxTouchPoints > 0 || matchMedia('(pointer: coarse)').matches; }
  private clamp(value: number, min: number, max: number): number { return Math.max(min, Math.min(max, value)); }
}
