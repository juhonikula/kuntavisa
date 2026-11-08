# Kuntavisa

A browser map quiz for Finnish municipalities (kunnat). The player taps the municipality whose name is shown. The whole app is **one self-contained static HTML file**: vanilla JS and inline SVG, with no frameworks, no runtime dependencies, no server and no network requests at runtime.

Live version: https://juhonikula.github.io/kuntavisa/

## Game modes

| Mode | Flow |
|---|---|
| **Maakunta** | The map of Finland shows region (maakunta) names. Tapping a region animates the view to its bounding box, dims the other regions (`pointer-events: none`) and asks for that region's municipalities in random order. At the end you can replay the same region or pick another. |
| **Koko Suomi** | All 308 municipalities in random order, with region borders drawn thicker. Progress is saved to `localStorage` after every answer and can be resumed from the menu. |
| **Harjoitus** | Offered on the end card when something was missed: replays only the missed municipalities. Not scored and not saved. |

Rules are the same in both modes:
- 3 tries per municipality, or 1 in the settings' hard mode (`game.max`).
- First-try hit: green (`ok1`). Hit on a later try: yellow (`ok2`). Not found after the last miss: red (`fail`), and the correct municipality blinks.
- A wrong tap flashes the tapped municipality and shows a "Tuo on X" toast. Tapping an already answered municipality shows its name.
- Score is the number of first-try hits, plus total time and total misses.

Menus and extras:
- **☰ menu:** its ✕ (or Esc) returns to whatever was open before: the running round (the clock resumes), the region pick, the end card or the stats map.
- **Ennätykset:** the top 5 results per region and for Koko Suomi, kept separately for 1 and 3 tries. Ranked by first-try hits, then fewer misses, then time.
- **Tilastokartta** (the top button of the Ennätykset card): every municipality, or with the toggle every region, coloured by its all-time first-try share. Tapping shows the numbers.
- **Asetukset:** game text size, menu text size, theme, tries per municipality, reduced animations, and whether the region pick map is shaded by best score.

The UI language is Finnish, and municipalities use their Finnish names (`nimi`).

## Repository layout

```
kuntavisa/
├── README.md
├── LICENSE                  # MIT (code)
├── src/
│   └── template.html        # the app: HTML + CSS + JS, with a single __DATA__ placeholder
├── tools/
│   ├── fetch_data.sh        # downloads raw data from Statistics Finland
│   ├── build_data.py        # raw GeoJSON -> simplified SVG paths (data/data.json)
│   ├── assemble.py          # template + data.json -> docs/index.html
│   └── smoke_test.py        # headless Playwright play-through
├── data/
│   ├── raw/                 # downloaded source files (EPSG:3067 GeoJSON + correspondence table)
│   └── data.json            # generated
└── docs/
    └── index.html           # generated, deployable page served by GitHub Pages (~830 KB, ~310 KB gzipped)
```

## Build

Requirements: bash, curl and Python 3 (stdlib only). The smoke test also needs Python Playwright with Chromium.

```bash
tools/fetch_data.sh 2025                       # -> data/raw/*.json (skip if already present)
python3 tools/build_data.py \
    data/raw/kunta1000k_2025.json \
    data/raw/maakunta1000k_2025.json \
    data/raw/kunta_maakunta_2025.json \
    data/data.json                             # prints counts + path size
python3 tools/assemble.py src/template.html data/data.json docs/index.html
python3 tools/smoke_test.py docs/index.html /tmp   # expect "errors: []"
```

GitHub Pages serves `docs/` from the `main` branch, so commit the rebuilt `docs/index.html` together with the template change. The file also works on any other static host and can be embedded with an `<iframe>`.

When you edit the app, edit `src/template.html`, never `docs/index.html`. Re-run `assemble.py` after every change.

## Data sources

All data comes from Statistics Finland (Tilastokeskus) and is licensed **CC BY 4.0**.

| File | Source | Notes |
|---|---|---|
| `kunta1000k_YYYY.json` | WFS `tilastointialueet:kunta1000k_YYYY` on `geo.stat.fi` | Municipality polygons, 1:1 000 000 generalisation. Props: `kunta` (3-digit code), `nimi`, `namn`, `name`. |
| `maakunta1000k_YYYY.json` | WFS `tilastointialueet:maakunta1000k_YYYY` | Region polygons. Props: `maakunta` (2-digit code), `nimi`, … |
| `kunta_maakunta_YYYY.json` | Classification API correspondence table `kunta_1_YYYY0101#maakunta_1_YYYY0101` on `data.stat.fi` | Municipality → region mapping. Fields `sourceLocalId` and `targetLocalId` look like `kunta_1_20250101/636` and `maakunta_1_20250101/02`. |

All geometry is requested in **EPSG:3067** (ETRS-TM35FIN, metres). That projection is used as-is for drawing: it is the national standard and gives an undistorted-looking map of Finland. A `kunta4500k_YYYY` layer also exists if a coarser generalisation is ever needed.

**Attribution requirement:** a public deployment must credit the source, for example *"Kunta- ja maakuntarajat: Tilastokeskus, ladattu rajapintapalvelusta DD.MM.YYYY, CC BY 4.0"*. The start menu shows it.

## Data pipeline (`tools/build_data.py`)

1. **Normalisation:** `Polygon` geometries are wrapped into `MultiPolygon`.
2. **Coordinate transform:** x' = (x − minx)/1000 and y' = (maxy − y)/1000. The result is **1 SVG unit = 1 km** with the y axis flipped so north is up. The origin comes from the bounds of the maakunta layer. The extent is about 659 × 1144 km.
3. **Simplification:** Douglas–Peucker on each ring, done iteratively with an explicit stack.
   - Tolerance is **100 m** for both layers.
   - A closed ring has first point = last point, which makes DP's baseline degenerate. Each ring is therefore split into two halves that are simplified separately.
   - Shared borders are simplified independently in each polygon, so adjacent edges can mismatch by up to about the tolerance. That isn't visible at normal zoom. It was chosen over building a topology because the 60 m variant cost about 25 % more bytes for little visible gain.
4. **Island and hole filtering:**
   - Municipalities: islands smaller than 0.4 km² are dropped, but the largest polygon is always kept. Holes smaller than 3 km² are dropped.
   - Maakunta outline layer: islands smaller than **30 km²** are dropped, so the thick region stroke doesn't turn the archipelago into a dark mass.
5. **Per-feature output:**
   - Municipality: `{id, n, m, d, cx, cy, b}`. `d` is the SVG path, `m` the region code, (`cx`, `cy`) the shoelace centroid of the largest outer ring (used for labels), and `b` the bbox `[x0, y0, x1, y1]` in km.
   - Region: `{id, n, d, b}`.
   - Coordinates are written with 2 decimals (10 m), with a trailing `.00` stripped.

`data.json` shape:
```json
{ "w": 659.1, "h": 1144.2,
  "kunnat":    [{ "id": "837", "n": "Tampere", "m": "06", "d": "M…Z", "cx": 0, "cy": 0, "b": [0,0,0,0] }],
  "maakunnat": [{ "id": "06", "n": "Pirkanmaa", "d": "M…Z", "b": [0,0,0,0] }] }
```

## App architecture (`src/template.html`)

The script is a single `<script>` block divided into commented sections.

### Map construction
- SVG layers in z-order: `#gK` (municipality fills, `path.k`), `#gM` (region outlines, `path.mk`, `pointer-events: none`) and `#gL` (labels).
- Lookup tables: `K[id]` holds the municipality data plus `.el` (its `<path>`). `MK[id]` holds the region data plus `.kunnat` (an array of municipality ids).
- Paths use `fill-rule: evenodd`, so lake holes and enclaves render correctly.
- Strokes use `vector-effect: non-scaling-stroke`: line width stays fixed in screen pixels at every zoom level.
- Dimmed municipalities (`path.k.out`) use pre-blended `--dim`/`--dimS` colours rather than `opacity`, because per-element opacity costs an offscreen pass per path on every redraw.

### View and camera
- The camera is the SVG `viewBox`, held in `vb = {x, y, w, h}`. `applyVb()` always forces `vb.h = vb.w * elH / elW`, so the viewBox aspect equals the element aspect. The screen-to-map transform is then a plain scale plus offset: `mapX = vb.x + px / elW * vb.w`. This avoids `getScreenCTM()` and `preserveAspectRatio` letterboxing.
- `applyVb()` batches `viewBox` writes to one per animation frame (`flushVb()`), because input events can arrive several times per frame and every write redraws all paths. Code that already runs inside `requestAnimationFrame` calls `applyVb(true)` to write immediately.
- The element rect (`elW`, `elH`, `elL`, `elT`) is cached by `measure()` and refreshed by a `ResizeObserver`, so gesture handlers never force a layout.
- `zoomAt(px, py, f)` zooms around a screen point. Zoom is clamped by `clampW()` to a view width of 4 km … 2.5 × the full map width.
- `boxView(bbox, pad)` returns an aspect-correct view that contains a bbox.
- `animateTo(target, ms)` animates the view with a `requestAnimationFrame` loop and ease-in-out-quad easing. Any pointerdown cancels it. With reduced animations it jumps straight to the target.
- `fitView()` gives the selected region's bbox in Maakunta mode, otherwise the whole of Finland. The ⤢ button uses it.

### Gestures
- Pointer Events handle mouse and touch through one code path, with `touch-action: none` on the SVG.
- Drag pans the map, but only after more than 7 px of movement.
- Pinch works from the two tracked pointers: the change in their distance gives the zoom factor, and the change in their midpoint gives the pan.
- The mouse `wheel` zooms with `exp(-deltaY * 0.0015)`.
- **Tap detection:** on the final `pointerup`, if the gesture never moved and never had two pointers, `document.elementFromPoint()` resolves the tapped `path.k` through `data-id`. The page doesn't listen for `click`, so a pan can never register as an answer.
- **Tap tolerance:** `tapTarget()` returns the exact hit first. If the tap landed on sea or background, it probes 8 directions at 5 px and then 10 px and takes the first municipality found. Dimmed paths have `pointer-events: none`, so the probe never finds them.

### Game state
```js
game = { mode: "mk" | "all" | "menu" | "stats", mk: regionId | null, view /*stats: "k" | "m"*/,
         practice, order: [kuntaId…], idx, max /*tries setting*/, tries, firstTry, totalMiss,
         failed: [name…], failedIds: [kuntaId…], status: { kuntaId: "ok1" | "ok2" | "fail" },
         elapsed /*ms banked*/, t0 /*running-since timestamp or 0*/, locked }
```
- `paint()` derives every path's `class` from `game.status`, `game.mk` and `shading()`. `shading()` returns a ramp step `s0…s4` (20 % bands) per municipality: on the pick map from the best score of its region, on the stats map from the per-municipality or per-region first-try share. That makes rendering idempotent, and a restored save repaints correctly. Transient animations (`flash`, `reveal`) are added on top of the classes and removed afterwards.
- `onTap(id)` is the state machine:
  - In region-pick phase it starts a round.
  - A correct tap goes to `advance()`.
  - A wrong tap decrements `tries`.
  - At zero tries it marks the municipality `fail`, calls `revealInView()` and sets `locked` for 1.7 s (0.7 s with reduced animations) before advancing. ☰ is ignored while `locked`.
  - Every resolved municipality updates the per-municipality stats (`record()`).
- `revealInView()` pans the view, and zooms if needed, so the missed municipality is on screen and at least ~18 px wide (it targets ~40 px).
- The clock is `elapsed` plus `(now − t0)`. `stopClock()` banks the running time into `elapsed`; the menu and the end screen stop it, and the menu's ✕ restarts it.
- `menuReturn` records what the menu's ✕ goes back to (`null` at startup, otherwise whether the end card was open).
- `finish()` calls `addScore()`, which inserts the result into the top 5 and returns its rank for the end card.

### Persistence
All `localStorage` access goes through `load()`/`store()`, which wrap it in try/catch because storage can be unavailable in sandboxed iframes. If a format changes, bump its key suffix.

| Key | Contents |
|---|---|
| `kuntavisa-koko-v1` | The running Koko Suomi `game`, saved after every answer and removed when the round finishes. Practice rounds are never saved. |
| `kuntavisa-scores-v1` | `{"<regionId or all>|<tries>": [{h, n, miss, ms, d}…]}`, top 5 per key, best first. |
| `kuntavisa-stats-v1` | `{kuntaId: [seen, firstTry, laterTry, failed]}` over all rounds, practice included. |
| `kuntavisa-settings-v1` | `{fs, mfs, theme, tries, anim, shade}`. `applySettings()` turns it into CSS variables on `<html>`: `--fs` for the game (header and toast sizes are in `rem`) and `--mfs` for the menu cards (`.card` sets an absolute base size and its contents are in `em`). It also sets `data-theme` and the `calm` class. |

### Labels (review view)
- Labels are built on demand: municipality names after a round ("Näytä kartta nimillä"), region names in the pick phase and behind the menu.
- `updateLabels()` runs on every view change. It sets the group's `font-size` to `12 × text scale / (px per km)` so text stays 12 px (times the text size setting) on screen. It hides a label when its feature's on-screen bbox width is less than name length × 6.5 px × text scale (3.2 px for region labels). This is a cheap collision heuristic, not real collision detection.

## Testing

`tools/smoke_test.py` uses a 390 × 800 mobile viewport with touch enabled. It:
1. Opens the menu and enters Maakunta mode.
2. Picks Pirkanmaa with a real mouse click at Tampere's centroid.
3. Plays the 23 municipalities: correct taps go through real clicks whenever the centroid hits the right path, and it scripts one wrong tap and one full 3-miss failure.
4. Opens the labelled review map.
5. Starts Koko Suomi, answers 5, wheel-zooms near Helsinki, reloads and checks that the menu offers to resume.

It prints page errors and writes screenshots `a0…a5` and `b1…b3`. It does not verify pinch, because real touch pinch isn't simulated.

## Known limitations / TODO

- **Hard-coded to 2025 boundaries.** For another year, run `fetch_data.sh` with that year and rebuild. Municipality mergers change ids and counts; the code assumes nothing about the 308 count.
- **Label placement** uses the centroid of the largest ring. For concave or archipelago municipalities it can fall outside the shape or in the sea. A pole-of-inaccessibility calculation (polylabel) in `build_data.py` would fix this.
- **No lakes layer.** Large lakes (Saimaa, Päijänne) aren't drawn, which makes eastern Finland harder to read.
- **Small municipalities** in Koko Suomi (Kauniainen, Ahvenanmaa municipalities) still need some zooming. Tap tolerance only helps when the tap lands on sea or background, not on a larger neighbour.
- **Scores and stats are per browser.** Clearing site data deletes them, and there is no export.
- **Independent simplification** leaves hairline gaps between neighbours at very high zoom. A real fix is topology-preserving simplification, e.g. mapshaper `-simplify` with shared arcs, or TopoJSON.
- **The data is embedded in the HTML** (~830 KB) to keep the app a single file. If it becomes a multi-file site, `data.json` could be fetched instead and cached separately.
- **UI strings are inline Finnish.** There is no i18n layer. Swedish names (`namn`) are present in the raw data but not emitted.

## Extension points

- **New quiz scopes:** any set of municipality ids works as `game.order`. New groupings can come from other correspondence tables in the classification API (seutukunta, hyvinvointialue, ELY-keskus, kielisuhde) by adding a field like `m` per municipality in `build_data.py`. A new pick phase can reuse the Maakunta-mode pattern.
- **Reverse mode** (show a highlighted shape, pick the name): reuse `paint()`, add a `target` class, and replace the tap handler with name buttons.
- **Additional layers:** add another `<g>` between `#gK` and `#gL`, built the same way as `#gM`, with `pointer-events: none` so taps still reach `path.k`.
- **More per-browser data** (e.g. streaks, per-region time trends) fits the `load()`/`store()` pattern. Anything shared between users needs a backend.

## License

Code: MIT, see `LICENSE`. Map data: Statistics Finland (Tilastokeskus), CC BY 4.0. The data embedded in `data/data.json` and `docs/index.html` is derived from it.
