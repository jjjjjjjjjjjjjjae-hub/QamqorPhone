# QAMQOR PHONE — AI handoff: 3D phone coordinates and request button

> **Purpose:** Preserve the verified history and exact coordinate method for future AI/developer work.
> **Important:** This file is documentation only. Do not treat it as permission to change `index.html`, `kor.html`, the GLB assets, CI workflows, or the repair flow. Ask the user before making persistent implementation changes.

## 1. Current verified state

- Production viewer element: `.qamqor-phone-model` in `index.html`.
- Production GLB: `QAMQOR-iPhone-18-Pro-Max.glb`.
- Original/source GLB used by the builder and diagnostics: `iPhone 18 pro max.glb`.
- Screen material name: `COLOUR_Blue_Screen`.
- Current generated report: `qamqor-3d-report.json`, generated at `2026-11-08T03:37:17Z` (UTC).
- Current generated button data: `qamqor-3d-button-build.json`.
- The current GLB report shows 44 geometries in total: 43 phone/model geometries plus one generated request-button mesh.
- The current button coordinate in the GLB, report, HTML hotspot and click handler is **(0, 0.0420127507, 0.004502)**.
- The current CI browser report says desktop click and mobile touch both reached `#repair`; the 7-step form is shown as the separate repair page. **The form has NOT yet been embedded inside the physical 3D display.**

## 2. Phone/model coordinate frame and measured bounds

The following values were calculated from the current `qamqor-3d-report.json` geometry rows. For each geometry row, the CI script has already transformed the mesh vertices into the model's common coordinate frame before recording `bounds_min` and `bounds_max`. The phone bounds below exclude the added `QAMQOR_Request_Button` plane.

| Axis | Minimum (m) | Maximum (m) | Size (mm) |
|---|---:|---:|---:|
| X — phone width | -0.0394629985 | 0.0395050012 | 78.968 |
| Y — phone length, bottom to top | -0.0000180000 | 0.1633380055 | 163.356 |
| Z — front/back thickness | -0.0092179999 | 0.0043219998 | 13.540 |

Aggregate model bounding-box centre:
- X: `0.0000210013 m`
- Y: `0.0816600028 m`
- Z: `-0.0024480000 m`

These are the **GLB model-space bounds**, not CSS pixels and not a claim about Apple's published industrial dimensions. The values describe the exported mesh envelope, including its model components.

Coordinate orientation, confirmed by the screen mesh and ray-hit report:
- X runs left ↔ right across the front display.
- Y runs from the phone bottom toward the top; positive Y is upward.
- Z is depth. The front display plane is at positive Z; its outward normal is approximately `(0, 0, 1)`.

## 3. Exact screen coordinates

The screen is not guessed from a visual screenshot. The geometry report identifies:
- Node: `Object_60`
- Mesh: `Object_28`
- Material: `COLOUR_Blue_Screen`
- Vertices: 161
- Faces: 198

Measured vertex bounds:
- `screen_min = [-0.0365150012, 0.00239100005, 0.00432199985]`
- `screen_max = [ 0.0365150012, 0.16087800264, 0.00432199985]`

Therefore:
- Screen width: `0.0730300024 m = 73.030 mm`
- Screen height: `0.1584870026 m = 158.487 mm`
- Front plane Z: `0.00432199985 m`
- Screen centre: approximately `(0, 0.0816345000, 0.00432199985)`

The screen is almost planar in this mesh: the reported min-Z and max-Z are the same.

## 4. How the physical “Өтінім беру” button was located and built

The authoritative construction logic is in `scripts/build_phone_button.py` (historical/current builder version at commit `e529c04c62138e63e8ca9f2610f6b5003020e9b7`).

The builder does the following:

1. Loads `iPhone 18 pro max.glb` using Python `trimesh` as a scene.
2. Iterates through the scene's geometry nodes.
3. Gets each node's transform and geometry, reads its PBR material name, and transforms its vertices into the common model coordinate frame using `trimesh.transform_points(..., transform)`.
4. Keeps meshes whose material name is exactly `COLOUR_Blue_Screen`.
5. If more than one candidate exists, selects the candidate with the greatest number of vertices. It stops with an error if no screen candidate is found.
6. Calculates `screen_min` and `screen_max` from the selected screen vertices. This is the source of the screen measurements above.
7. Creates a small rectangular physical plane slightly in front of the screen. It is not just a 2D HTML button.

Current button formula from the builder:

```python
button_width = screen_width * 0.72
button_height = screen_width * 0.18
button_center_x = (screen_min[0] + screen_max[0]) / 2
button_center_y = screen_min[1] + screen_height * 0.25
button_z = screen_front_z + 0.00018
```

Why these coordinates:
- X centre is the centre of the measured screen.
- Y is 25% of the measured screen height upward from the lower screen boundary (the script comment says model Y grows upward).
- Z is offset by 0.00018 m (0.18 mm) toward the front so the button plane sits just above the screen surface rather than exactly coplanar with it.
- Width is 72% of screen width; height is 18% of screen width.

Current resulting values:
- Centre: `[0, 0.04201275069499388, 0.004501999847888946]`
- Size: `[0.05258160173892975, 0.013145400434732437]` = approximately `52.582 × 13.145 mm`
- Normal: `[0, 0, 1]`
- X limits: approximately `[-0.0262908, +0.0262908]`
- Y limits: approximately `[0.03544005, 0.04858545]`
- Z: `0.004502`
- Texture: `1200 × 320` pixels
- Exported node: `QAMQOR_Request_Button`
- Exported mesh: `QAMQOR_Request_Button_Mesh`
- Material: `QAMQOR_Request_Button_Material`
- Mesh: 4 vertices and 2 triangular faces.

After export, the script reopens the GLB with trimesh and verifies that the button node/mesh exists. The current report confirms `button_mesh_found_after_export: true`.

## 5. Historical coordinate difference — do not copy the stale value

An earlier build/report at commit `2958b2a8fd17a6aac373023153e19a08a4cff5ee` used:
- Button centre Y: `0.0451824907 m`
- Button Y bounds: approximately `0.03860979` to `0.05175519 m`

The current build uses:
- Button centre Y: `0.0420127507 m`
- Button Y bounds: approximately `0.03544005` to `0.04858545 m`

Difference in centre Y: about `0.00316974 m = 3.170 mm`.

The old value corresponds to a higher placement on the display (about 27% of screen height from the bottom); the current builder explicitly uses 25%. **Use the current report + current GLB + current `index.html` as the matching set. Do not mix the old `0.0451825` coordinate with the current GLB.**

## 6. How the 3D button is identified when the user clicks it

Current implementation is at the end of `index.html`, inside script `qamqor-physical-button-click`.

There are two related paths:

### A. 3D-attached touch hitbox

The `<model-viewer>` markup places both an invisible probe and a button hotspot at:
- `data-position="0 0.04201275 0.004502"`
- `data-normal="0 0 1"`

The CSS hitbox is attached to the GLB position by model-viewer. It is transparent (opacity about 0.001), but it receives pointer events. It is enlarged for touch:
- Desktop width: `min(56vw, 220px)`, height 64px.
- Mobile width: `min(56vw, 210px)`, height 68px.

Touch/pen activates on `pointerup`; mouse, keyboard and accessible activation use `click`.

### B. Ray-hit fallback on the actual GLB mesh

The viewer listens for `click` and calls:

```js
viewer.positionAndNormalFromPoint(event.clientX, event.clientY)
```

It then checks whether the returned model-space hit belongs to the button region:
- `abs(hit.x - 0) <= 0.02629 * 1.15`
- `abs(hit.y - 0.04201275) <= 0.0065727 * 1.55`
- `0.004502 - 0.0002 <= hit.z <= 0.004502 + 0.0002`
- `hit.normal.z >= 0.90` (must be a front-facing surface)

Only then does it call the repair-page navigation function.

Important distinction: this code currently opens the separate repair page using `qamqorShowPage("repair", ...)` (or falls back to `#repair`). It does **not** yet render the 7-step form directly on the 3D display surface.

## 7. What `kor.html` actually does — and what it does not do

Current `kor.html` is a **manual diagnostics page**, not a permanent site measurement system.

- Loads the original `iPhone 18 pro max.glb` into `<model-viewer id="phone">`.
- Exposes `window.QAMQOR_DIAGNOSTICS`.
- Waits for the model to load and marks diagnostics as ready.
- It does **not** automatically call `collect()` when the page opens.
- A developer can run `await QAMQOR_DIAGNOSTICS.collect()` in the browser DevTools console after the page reports that the model is ready.
- `collect()` starts from the current camera orbit and samples four camera angles: initial theta + 0°, 90°, 180°, and 270°, keeping phi and radius unchanged.
- For each angle it waits 650 ms, samples a 13-row × 15-column grid (195 attempted sample points), and restores the original camera orbit afterwards.
- Each successful sample records pixel point, normalized screen position, 3D position, surface normal, UV coordinates, material name and `surfaceFromPoint` output (where supported).
- The report also attempts to record model dimensions, bounding-box centre, camera target, initial camera orbit, and glTF meshes/nodes/materials.

### Important coordinate-offset caution in current kor.html

The current diagnostic code sets:
`x = viewer.clientWidth * u` and `y = viewer.clientHeight * v`, then passes `x, y` directly to `positionAndNormalFromPoint`, `materialFromPoint` and `surfaceFromPoint`.

However, the later CI diagnostic explicitly compares:
- a local/canvas coordinate pair, and
- a viewport coordinate pair created by adding `viewer.getBoundingClientRect().left/top`.

In the recorded current report, the global/viewport ray hit succeeded while `local` was `null`. Therefore, when interpreting or reusing `kor.html` samples, account for the viewer's page offset. A future approved diagnostic correction would calculate:
`const rect = viewer.getBoundingClientRect(); const x = rect.left + viewer.clientWidth * u; const y = rect.top + viewer.clientHeight * v;`
Do not silently change `kor.html`; ask the user first.

Also, `kor.html`'s four-view sampling is a visual/ray-hit diagnostic. The exact screen bounds used to build the current physical button came from the GLB vertex geometry parsed by `scripts/build_phone_button.py`, not from guessing a pixel coordinate in `kor.html`.

## 8. Verified CI results and recorded failures

The report history shows both a failure and a later successful test:

### Earlier failing report
At commit `2958b2a8fd17a6aac373023153e19a08a4cff5ee` (report generated `2026-11-08T02:51:46Z`):
- Button mesh existed.
- Desktop front-facing visibility and back-facing hidden checks passed.
- Projected button width was about 253.09 px front-on and 89.33 px near the side.
- But `mobile_front` was `null`.
- `front_button_click_hash` was empty.
- `click_reached_request_form` was `false`.
- `browser_errors` was empty.

The report does not specify the precise cause of that failure. Do not claim it was a 30-second timeout: that explanation is not present in the recorded report.

### Later successful report
At commit `e529c04c62138e63e8ca9f2610f6b5003020e9b7` (report generated `2026-11-08T03:24:03Z`) and the current report at `main`:
- Button mesh exists and was found after export.
- Front view visible; back view hidden.
- Current report projected width: about 252.48 px front-on and 91.20 px near the side.
- Mobile viewer was 366 × 709 CSS px in a 390 × 844 test viewport.
- The mobile front probe was facing the camera.
- Mobile touch changed hash to `#repair` and the repair page was visible.
- Desktop front-button click changed hash to `#repair`.
- `browser_errors` was empty.

These are GitHub Actions/Playwright test results. They are useful evidence, but they are not a substitute for checking the actual published page on the user's device.

## 9. Current source files to read first

- `kor.html` — manual four-view ray/material/surface diagnostics.
- `scripts/build_phone_button.py` — authoritative method that measures `COLOUR_Blue_Screen` mesh bounds and builds the physical button.
- `qamqor-3d-button-build.json` — concise current screen/button coordinates produced by the builder.
- `qamqor-3d-report.json` — transformed geometry bounds, visual rotation probes, mobile/desktop click results, browser errors.
- `QAMQOR-iPhone-18-Pro-Max.glb` — generated model that production `index.html` loads.
- `index.html` — production model-viewer markup, hotspot position, touch hitbox, ray-hit fallback, and page navigation.
- `.github/workflows/qamqor-3d-diagnostics.yml` — Playwright/Trimesh diagnostics and report-generation workflow.

Useful Git history:
- Earlier button/hit-test snapshot: `2958b2a8fd17a6aac373023153e19a08a4cff5ee`
- Later successful build/report snapshot: `e529c04c62138e63e8ca9f2610f6b5003020e9b7`
- Current report's source commit: `2227134f058d7edbe7b5f80b4ee55f0256cb8052`

## 10. Rules for the next AI/developer

1. Start by reading this file and the current report/build JSON; do not guess coordinates.
2. Use the current physical button centre `(0, 0.0420127507, 0.004502)` only with the current generated GLB.
3. Do not reuse the older `y = 0.0451825` value unless intentionally rebuilding the GLB and updating every dependent location consistently.
4. Do not add continuous, automatic, repeated, multi-angle or startup measurements to the production page. The user explicitly asked not to introduce a permanent measurement system without asking first.
5. `kor.html` is a diagnostic tool; keep it separate from production behavior unless the user explicitly approves a change.
6. Before changing code, explain exactly which files will change and why, and get the user's approval.
7. Preserve Telegram, WhatsApp, Cloudflare, map, 7-step wizard, quote and receipt functionality when working on the form.
8. The requested future feature is to show the existing repair form inside the 3D phone display after the user presses the physical request button. The present code still navigates to a separate `repair` page. Plan any overlay against the measured screen rectangle/plane and verify the visual result; do not claim it is done based only on a successful button-click test.
