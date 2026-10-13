import './styles.css';
import { CityExplorer } from './app/CityExplorer';
import type { AppUI } from './types';

function required<T extends Element>(selector: string): T {
  const element = document.querySelector<T>(selector);
  if (!element) throw new Error(`Required UI element missing: ${selector}`);
  return element;
}

const ui: AppUI = {
  canvas: required<HTMLCanvasElement>('#city-canvas'),
  loadStatus: required('#load-status'),
  errorPanel: required('#error-panel'),
  progress: required('#load-progress span'),
  walkButton: required<HTMLButtonElement>('#walk-button'),
  flyButton: required<HTMLButtonElement>('#fly-button'),
  resetButton: required<HTMLButtonElement>('#reset-button'),
  hint: required('#control-hint'),
  altitudeControls: required('#altitude-controls'),
  ascendButton: required<HTMLButtonElement>('#ascend-button'),
  descendButton: required<HTMLButtonElement>('#descend-button'),
  moveStick: required('#move-stick'),
  lookArea: required('.touch-right'),
  debugPanel: required('#debug-panel'),
};

try {
  const explorer = new CityExplorer(ui);
  void explorer.start();
  window.addEventListener('beforeunload', () => explorer.dispose(), { once: true });
} catch (error) {
  ui.errorPanel.hidden = false;
  ui.errorPanel.textContent = `このブラウザーでWebGLを初期化できませんでした: ${error instanceof Error ? error.message : String(error)}`;
}
