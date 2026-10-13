# KIBA REAL CITY — Phase 4A Web Explorer

## Phase 5A local OSM editor

Prepare ignored local feature files from the retained snapshot, then launch Vite:

```sh
cd ..
python phase5a/scripts/build_feature_data.py
cd phase4-web
npm ci
npm run dev
```

The Phase 5A panel adds independent roads, individual OSM tree points, and vegetation layers. Road attributes and a control point are editable; trees can be moved and have display dimensions/model fields changed; manual trees are marked unverified. Changes save to the ignored local `phase5a/edits/edits.json`, separate from the OSM source snapshot. The API only accepts same-origin edits on loopback. Do not expose the dev server on a public interface.

Terrain is disabled pending confirmation of official GSI product metadata, vertical datum, and usage terms. OSM-derived features remain local while complete current redistribution terms are unverified. See `../phase5a/README.md` and `../LICENSE_DATA.md` before sharing derived data or screenshots.

Local-only Three.js explorer for the unchanged Phase 3D v07 FLAT GLB. It supports walk mode, fly mode, compact building-AABB collision, desktop mouse/keyboard controls, and touch controls for iPad-sized screens. The viewer loads the repository's v07 GLB and georeference directly through a Vite asset plugin; its SHA-256 values are pinned and checked before serving or bundling. No geometry, materials, scale, or source files are rewritten.

## Requirements

- Node.js 20.19 or newer (tested with Node 24)
- npm
- WebGL 2-capable browser; recent desktop Chrome/Edge or iPad Safari
- Existing `../output/KIBA_REAL_CITY_v07.glb` and `../output/geo_reference_v07.json`

## Run locally

```sh
npm ci
npm run dev
```

Open the local address shown by Vite (default `http://127.0.0.1:4173`). To test on an iPad on the same private Wi-Fi, run `npm run dev -- --host 0.0.0.0`, then open the PC's private LAN address on the iPad. This is a local development server; do not forward ports, create a public tunnel, or deploy it.

For a static local build, run `npm run build`, then `npm run preview`. `dist/` includes copies of the source GLB and georeference solely so Vite Preview works locally. It is ignored by Git and must not be uploaded or published.

## Controls

- **WALK:** WASD, mouse drag to look, Shift to sprint, Esc to stop looking. On touch screens, use the left virtual stick and swipe the right side to look. Walking remains on the flat reference level and uses conservative building bounding boxes as blockers.
- **FLY:** WASD to move, E/Q to ascend/descend, mouse drag or right-side touch swipe to look, wheel or pinch to zoom. The +/− buttons adjust altitude.
- **RESET:** Returns WALK to the park spawn or FLY to the full-area overview.
- Add `?debug=1` to show measured FPS/frame time, renderer calls/triangles, GLB counts and load time, camera position, projected coordinates, model bounds, renderer string, and pixel ratio. Shadow maps default off for stable mobile performance and can be toggled in the debug panel.

## Validation

```sh
npm run typecheck
npm run build
npm run validate
```

Browser interaction tests and screenshots are kept under `reports/` locally. See the root `LICENSE_DATA.md`; the model and data-derived screenshots are not approved for public redistribution. No GitHub Pages, external hosting, or push is part of this workflow.

## Windows PC + iPad Air (3rd generation) device test

The app is local-only. Run the server on the Windows PC that shares a trusted private Wi-Fi network with the iPad; a cloud/Linux workspace cannot expose the PC's private LAN address.

In PowerShell:

```powershell
cd C:\path\to\KIBA-REAL-CITY\phase4-web
npm ci
npm run dev -- --host 0.0.0.0
```

Keep this terminal open. Vite should print the local URL and a Network URL. On the PC open `http://localhost:4173/?debug=1`. On the iPad, use `http://<Windows-IPv4-address>:4173/?debug=1`. Find the Windows IPv4 address with `ipconfig` and select the adapter connected to the same Wi-Fi. Do not use a public address, router port forwarding, VPN tunnel, or public tunnel. Stop the server with Ctrl+C when testing is complete.

If the iPad cannot connect, first confirm both devices are on the same trusted private Wi-Fi and that the router does not have client/AP isolation enabled. Only then, if Windows Firewall prompts, allow Node.js on **Private networks only**. If the prompt was dismissed, an administrator can add a narrowly scoped rule in elevated PowerShell:

```powershell
New-NetFirewallRule -DisplayName "KIBA Phase 4A local test" -Direction Inbound -Action Allow -Protocol TCP -LocalPort 4173 -Profile Private -RemoteAddress LocalSubnet
```

Remove it after testing with:

```powershell
Remove-NetFirewallRule -DisplayName "KIBA Phase 4A local test"
```

Do not enable this rule on Public networks or disable Windows Firewall. Do not publish, forward, or expose port 4173 to the Internet.

### 30-second measurements

Open `?debug=1` on both devices. After the city finishes loading, run three separate 30-second intervals: (1) standing still in FLY, (2) continuous WALK movement/look, and (3) continuous FLY movement/look. For each interval, note the displayed FPS and Frame approximately every five seconds (six readings); report their average and lowest observed sample, along with Draw Calls and Triangles. These are sampled values, not a true 1% low. Record GLB Load once, and classify controls, collision, flicker/striping, and heat subjectively. Keep the device awake and close other GPU-heavy apps. Do not treat prior emulator measurements as physical-device results.

Fill in `reports/phase4a_device_test_results.md` and `.json` after the real device tests. Leave unavailable fields null and statuses BLOCKED; never mark emulation as a hardware PASS.
