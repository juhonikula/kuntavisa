"""Build quiz data: municipalities (kunnat) + region (maakunta) outlines as SVG paths.

Inputs (EPSG:3067 GeoJSON from Statistics Finland + classification correspondence):
  kunta1000k_2025.json, maakunta1000k_2025.json, kunta_maakunta_2025.json
Output: data.json = {w, h, kunnat:[{id,n,m,d,cx,cy,b:[x0,y0,x1,y1]}], maakunnat:[{id,n,d,b}]}
1 SVG unit = 1 km, y axis flipped (north up).
"""
import json
import sys

KUNTA, MAAK, CORR, OUT = sys.argv[1:5]
SCALE = 1 / 1000.0


def dp(pts, tol):
    """Iterative Douglas-Peucker simplification of an open polyline."""
    if len(pts) < 3:
        return pts
    keep = [False] * len(pts)
    keep[0] = keep[-1] = True
    stack = [(0, len(pts) - 1)]
    while stack:
        a, b = stack.pop()
        ax, ay = pts[a]; bx, by = pts[b]
        dx, dy = bx - ax, by - ay
        L = (dx * dx + dy * dy) ** 0.5 or 1e-9
        best, idx = -1.0, -1
        for i in range(a + 1, b):
            px, py = pts[i]
            d = abs(dy * px - dx * py + bx * ay - by * ax) / L
            if d > best:
                best, idx = d, i
        if best > tol:
            keep[idx] = True
            stack += [(a, idx), (idx, b)]
    return [p for p, k in zip(pts, keep) if k]


def area(r):
    return abs(sum(r[i][0] * r[i - 1][1] - r[i - 1][0] * r[i][1] for i in range(len(r)))) / 2


def centroid(R):
    """Shoelace centroid of a closed ring."""
    A2 = ox = oy = 0.0
    for i in range(len(R) - 1):
        c = R[i][0] * R[i + 1][1] - R[i + 1][0] * R[i][1]
        A2 += c; ox += (R[i][0] + R[i + 1][0]) * c; oy += (R[i][1] + R[i + 1][1]) * c
    return ox / (3 * A2), oy / (3 * A2)


def load(path):
    d = json.load(open(path))
    for f in d["features"]:
        g = f["geometry"]
        if g["type"] == "Polygon":
            g["coordinates"] = [g["coordinates"]]
    return d


kun, maa = load(KUNTA), load(MAAK)
allx = [p[0] for f in maa["features"] for poly in f["geometry"]["coordinates"] for ring in poly for p in ring]
ally = [p[1] for f in maa["features"] for poly in f["geometry"]["coordinates"] for ring in poly for p in ring]
minx, maxy = min(allx), max(ally)
tx = lambda x: round((x - minx) * SCALE, 2)
ty = lambda y: round((maxy - y) * SCALE, 2)


def to_path(polys, tol, min_island, min_hole):
    """Simplify a MultiPolygon to an SVG path string; returns (d, bbox, centroid of biggest ring)."""
    outer = [area(p[0]) for p in polys]
    big = max(outer)
    parts, xs, ys = [], [], []
    for poly, oa in zip(polys, outer):
        if oa < min_island and oa != big:
            continue
        for ri, ring in enumerate(poly):
            if ri > 0 and area(ring) < min_hole:
                continue
            r = ring[:-1]; m = len(r) // 2               # closed ring -> two halves for DP
            s = dp(r[:m + 1], tol)[:-1] + dp(r[m:] + [r[0]], tol)[:-1]
            if len(s) < 3:
                continue
            pts = [(tx(x), ty(y)) for x, y in s]
            if ri == 0:
                xs += [p[0] for p in pts]; ys += [p[1] for p in pts]
            parts.append("M" + "L".join(f"{x:.2f},{y:.2f}".replace(".00","") for x, y in pts) + "Z")
    cx, cy = centroid(polys[outer.index(big)][0])
    return "".join(parts), [min(xs), min(ys), max(xs), max(ys)], (tx(cx), ty(cy))


# kunta code -> maakunta code
corr = {c["sourceLocalId"].split("/")[1]: c["targetLocalId"].split("/")[1] for c in json.load(open(CORR))}

kunnat = []
for f in kun["features"]:
    p = f["properties"]
    d, b, (cx, cy) = to_path(f["geometry"]["coordinates"], 100, 0.4e6, 3e6)
    kunnat.append({"id": p["kunta"], "n": p["nimi"], "m": corr[p["kunta"]], "d": d,
                   "cx": round(cx, 1), "cy": round(cy, 1), "b": [round(v, 1) for v in b]})

maakunnat = []
for f in maa["features"]:
    p = f["properties"]
    d, b, _ = to_path(f["geometry"]["coordinates"], 100, 30e6, 3e6)
    maakunnat.append({"id": p["maakunta"], "n": p["nimi"], "d": d, "b": [round(v, 1) for v in b]})

W = (max(allx) - minx) * SCALE; H = (maxy - min(ally)) * SCALE
json.dump({"w": round(W, 1), "h": round(H, 1), "kunnat": kunnat, "maakunnat": maakunnat},
          open(OUT, "w"), ensure_ascii=False, separators=(",", ":"))
missing = {k["m"] for k in kunnat} - {m["id"] for m in maakunnat}
print(f"{len(kunnat)} kunnat, {len(maakunnat)} maakunnat, missing={missing}, "
      f"{sum(len(k['d']) for k in kunnat) // 1024} KiB kunta paths")
