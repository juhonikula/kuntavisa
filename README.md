# Kuntavisa

A browser map quiz for Finnish municipalities (kunnat). The player taps the municipality whose name is shown. The whole app is **one self-contained static HTML file**: vanilla JS and inline SVG, with no frameworks, no runtime dependencies, no server and no network requests at runtime.

Live version: https://juhonikula.github.io/kuntavisa/

## Game modes

| Mode | Flow |
|---|---|
| **Maakunta** | The map of Finland shows region (maakunta) names. Tapping a region animates the view to its bounding box, dims the other regions (`pointer-events: none`) and asks for that region's municipalities in random order. At the end you can replay the same region or pick another. |
| **Koko Suomi** | All 308 municipalities in random order, with region borders drawn thicker. Progress is saved to `localStorage` after every answer and can be resumed from the menu. |

Rules are the same in both modes:
- `MAX_TRIES = 3` per municipality.
- First-try hit: green (`ok1`). Hit on try 2 or 3: yellow (`ok2`). Not found after 3 misses: red (`fail`), and the correct municipality blinks.
- A wrong tap flashes the tapped municipality and shows a "Tuo on X" toast. Tapping an already answered municipality shows its name.
- Score is the number of first-try hits, plus total time and total misses.

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

### View and camera
- The camera is the SVG `viewBox`, held in `vb = {x, y, w, h}`. `applyVb()` always forces `vb.h = vb.w * elH / elW`, so the viewBox aspect equals the element aspect. The screen-to-map transform is then a plain scale plus offset: `mapX = vb.x + px / elW * vb.w`. This avoids `getScreenCTM()` and `preserveAspectRatio` letterboxing.
- `zoomAt(px, py, f)` zooms around a screen point. Zoom is clamped by `clampW()` to a view width of 4 km … 2.5 × the full map width.
- `boxView(bbox, pad)` returns an aspect-correct view that contains a bbox.
- `animateTo(target, ms)` animates the view with a `requestAnimationFrame` loop and ease-in-out-quad easing. Any pointerdown cancels it.
- `fitView()` gives the selected region's bbox in Maakunta mode, otherwise the whole of Finland. The ⤢ button uses it.

### Gestures
- Pointer Events handle mouse and touch through one code path, with `touch-action: none` on the SVG.
- Drag pans the map, but only after more than 7 px of movement.
- Pinch works from the two tracked pointers: the change in their distance gives the zoom factor, and the change in their midpoint gives the pan.
- The mouse `wheel` zooms with `exp(-deltaY * 0.0015)`.
- **Tap detection:** on the final `pointerup`, if the gesture never moved and never had two pointers, `document.elementFromPoint()` resolves the tapped `path.k` through `data-id`. The page doesn't listen for `click`, so a pan can never register as an answer.

### Game state
```js
game = { mode: "mk" | "all" | "menu", mk: regionId | null,
         order: [kuntaId…], idx, tries, firstTry, totalMiss,
         failed: [name…], status: { kuntaId: "ok1" | "ok2" | "fail" },
         elapsed /*ms banked*/, t0 /*running-since timestamp or 0*/, locked }
```
- `paint()` derives every path's `class` from `game.status` and `game.mk`. That makes rendering idempotent, and a restored save repaints correctly. Transient animations (`flash`, `reveal`) are added on top of the classes and removed afterwards.
- `onTap(id)` is the state machine:
  - In region-pick phase it starts a round.
  - A correct tap goes to `advance()`.
  - A wrong tap decrements `tries`.
  - At zero tries it marks the municipality `fail`, calls `revealInView()` and sets `locked` for 1.7 s before advancing.
- `revealInView()` pans the view, and zooms if needed, so the missed municipality is on screen and at least ~18 px wide (it targets ~40 px).
- The clock is `elapsed` plus `(now − t0)`. `stopClock()` banks the running time into `elapsed`; the menu and the end screen stop it.

### Persistence
- Koko Suomi only. The whole `game` object is saved under the key `kuntavisa-koko-v1` after every answer and removed when the round finishes. Every access is wrapped in try/catch, because storage can be unavailable in sandboxed iframes.
- If the format changes, bump the key suffix.

### Labels (review view)
- Labels are built on demand: municipality names after a round ("Näytä kartta nimillä"), region names in the pick phase and behind the menu.
- `updateLabels()` runs on every view change. It sets the group's `font-size` to `12 / (px per km)` so text stays 12 px on screen. It hides a label when its feature's on-screen bbox width is less than name length × 6.5 px (3.2 px for region labels). This is a cheap collision heuristic, not real collision detection.

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
- **Small municipalities** in Koko Suomi (Kauniainen, Ahvenanmaa municipalities) need zooming. There are no enlarged hit areas for them.
- **Independent simplification** leaves hairline gaps between neighbours at very high zoom. A real fix is topology-preserving simplification, e.g. mapshaper `-simplify` with shared arcs, or TopoJSON.
- **The data is embedded in the HTML** (~830 KB) to keep the app a single file. If it becomes a multi-file site, `data.json` could be fetched instead and cached separately.
- **UI strings are inline Finnish.** There is no i18n layer. Swedish names (`namn`) are present in the raw data but not emitted.

## Extension points

- **New quiz scopes:** any set of municipality ids works as `game.order`. New groupings can come from other correspondence tables in the classification API (seutukunta, hyvinvointialue, ELY-keskus, kielisuhde) by adding a field like `m` per municipality in `build_data.py`. A new pick phase can reuse the Maakunta-mode pattern.
- **Reverse mode** (show a highlighted shape, pick the name): reuse `paint()`, add a `target` class, and replace the tap handler with name buttons.
- **Additional layers:** add another `<g>` between `#gK` and `#gL`, built the same way as `#gM`, with `pointer-events: none` so taps still reach `path.k`.
- **Stats and high scores** fit the existing try/catch localStorage pattern. Anything shared between users needs a backend.

## License

Code: MIT, see `LICENSE`. Map data: Statistics Finland (Tilastokeskus), CC BY 4.0. The data embedded in `data/data.json` and `docs/index.html` is derived from it.
