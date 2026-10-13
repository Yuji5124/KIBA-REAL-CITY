import {
  ACESFilmicToneMapping,
  Color,
  DirectionalLight,
  HemisphereLight,
  PCFSoftShadowMap,
  PerspectiveCamera,
  Scene,
  SRGBColorSpace,
  WebGLRenderer,
} from 'three';

export interface SceneRuntime {
  scene: Scene;
  camera: PerspectiveCamera;
  renderer: WebGLRenderer;
  isTouch: boolean;
  resize(): void;
}

export function createScene(canvas: HTMLCanvasElement): SceneRuntime {
  const isTouch = navigator.maxTouchPoints > 0 || matchMedia('(pointer: coarse)').matches;
  const scene = new Scene();
  scene.background = new Color('#dce7e8');
  scene.add(new HemisphereLight(0xf7fbff, 0x8a9693, 2.0));

  const sun = new DirectionalLight(0xfff5df, 2.4);
  sun.position.set(-280, 520, 260);
  sun.castShadow = true;
  sun.shadow.mapSize.set(1024, 1024);
  sun.shadow.camera.left = -600;
  sun.shadow.camera.right = 600;
  sun.shadow.camera.top = 700;
  sun.shadow.camera.bottom = -700;
  sun.shadow.camera.near = 1;
  sun.shadow.camera.far = 1800;
  sun.shadow.bias = -0.00015;
  scene.add(sun);

  const renderer = new WebGLRenderer({
    canvas,
    antialias: true,
    alpha: false,
    powerPreference: 'high-performance',
  });
  renderer.outputColorSpace = SRGBColorSpace;
  renderer.toneMapping = ACESFilmicToneMapping;
  renderer.toneMappingExposure = 1.0;
  renderer.shadowMap.enabled = false;
  renderer.shadowMap.type = PCFSoftShadowMap;
  renderer.info.autoReset = true;
  renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, isTouch ? 1.5 : 2));

  const camera = new PerspectiveCamera(62, 1, 0.08, 4000);
  camera.rotation.order = 'YXZ';

  const resize = (): void => {
    const width = Math.max(1, window.innerWidth);
    const height = Math.max(1, window.innerHeight);
    renderer.setSize(width, height, false);
    camera.aspect = width / height;
    camera.updateProjectionMatrix();
  };
  resize();

  return { scene, camera, renderer, isTouch, resize };
}
