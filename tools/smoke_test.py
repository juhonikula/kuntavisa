"""Headless smoke test: plays a Maakunta round (Pirkanmaa) and starts/resumes Koko Suomi.

Usage: python3 tools/smoke_test.py [docs/index.html] [outdir]
Needs Python Playwright + Chromium. Writes screenshots to outdir, prints page errors (expect []).
"""
import pathlib, sys
PAGE = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else "docs/index.html").resolve().as_uri()
OUTDIR = sys.argv[2] if len(sys.argv) > 2 else "/tmp"
from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    b = p.chromium.launch()
    pg = b.new_page(viewport={"width": 390, "height": 800}, has_touch=True, is_mobile=True)
    errs = []; pg.on("pageerror", lambda e: errs.append(str(e))); pg.on("console", lambda m: m.type=="error" and errs.append(m.text))
    pg.goto(PAGE); pg.wait_for_timeout(300)
    pg.screenshot(path=f"{OUTDIR}/a0.png")
    pg.click("#modeMk"); pg.wait_for_timeout(600); pg.screenshot(path=f"{OUTDIR}/a1.png")
    # real tap (mouse click) on Pirkanmaa: Tampere centroid
    k = pg.evaluate("(()=>{const t=Object.values(K).find(k=>k.n==='Tampere');const r=svg.getBoundingClientRect();return [r.left+(t.cx-vb.x)/vb.w*elW, r.top+(t.cy-vb.y)/vb.h*elH]})()")
    pg.mouse.click(*k); pg.wait_for_timeout(800); pg.screenshot(path=f"{OUTDIR}/a2.png")
    n = pg.evaluate("game.order.length"); print("pirkanmaa kunnat", n, pg.evaluate("MK[game.mk].n"))
    for i in range(n):
        tid = pg.evaluate("game.order[game.idx]")
        if i == 1:
            other = pg.evaluate("game.order[game.idx+1]"); pg.evaluate(f"onTap('{other}')")
        if i == 3:
            for j in range(3): pg.evaluate(f"onTap(game.order[game.order.length-1-{j}])")
            pg.wait_for_timeout(1800); continue
        # click via real mouse at kunta centroid to exercise hit testing
        xy = pg.evaluate(f"(()=>{{const t=K['{tid}'];const r=svg.getBoundingClientRect();return [r.left+(t.cx-vb.x)/vb.w*elW, r.top+(t.cy-vb.y)/vb.h*elH]}})()")
        el = pg.evaluate(f"(document.elementFromPoint({xy[0]},{xy[1]})||{{}}).dataset?.id")
        if el == tid: pg.mouse.click(*xy)
        else: pg.evaluate(f"onTap('{tid}')")
        if i == 8: pg.screenshot(path=f"{OUTDIR}/a3.png")
    pg.wait_for_timeout(600); pg.screenshot(path=f"{OUTDIR}/a4.png")
    pg.click("#viewMap"); pg.wait_for_timeout(200); pg.screenshot(path=f"{OUTDIR}/a5.png")
    # whole Finland
    pg.click("#menuBtn"); pg.click("#modeAll"); pg.wait_for_timeout(700)
    for i in range(5): pg.evaluate("onTap(game.order[game.idx])")
    pg.screenshot(path=f"{OUTDIR}/b1.png")
    # wheel zoom near Helsinki
    xy = pg.evaluate("(()=>{const t=Object.values(K).find(k=>k.n==='Helsinki');const r=svg.getBoundingClientRect();return [r.left+(t.cx-vb.x)/vb.w*elW, r.top+(t.cy-vb.y)/vb.h*elH]})()")
    pg.mouse.move(*xy)
    for _ in range(8): pg.mouse.wheel(0, -300); pg.wait_for_timeout(30)
    pg.screenshot(path=f"{OUTDIR}/b2.png")
    pg.reload(); pg.wait_for_timeout(300); pg.screenshot(path=f"{OUTDIR}/b3.png")
    print("resume:", pg.text_content("#resumeAll"))
    print("errors:", errs)
    b.close()
