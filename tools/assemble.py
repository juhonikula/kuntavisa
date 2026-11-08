"""Inject the generated data JSON into the HTML template -> single self-contained page.

Usage: python3 tools/assemble.py src/template.html data/data.json docs/index.html
The template contains exactly one `__DATA__` placeholder (inside `const DATA = __DATA__;`).
"""
import sys

template, data, out = sys.argv[1:4]
html = open(template, encoding="utf-8").read()
assert html.count("__DATA__") == 1, "template must contain exactly one __DATA__ placeholder"
payload = open(data, encoding="utf-8").read()
# Guard against "</script>" ever appearing in the JSON and closing the script tag early.
payload = payload.replace("</", "<\\/")
open(out, "w", encoding="utf-8").write(html.replace("__DATA__", payload))
print(f"wrote {out} ({len(html) + len(payload):,} bytes)")
