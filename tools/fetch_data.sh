#!/usr/bin/env bash
# Download raw source data from Statistics Finland (Tilastokeskus), CC BY 4.0.
# Usage: tools/fetch_data.sh [YEAR]   (default 2025)
set -euo pipefail
YEAR="${1:-2025}"
OUT="$(dirname "$0")/../data/raw"
mkdir -p "$OUT"
WFS="https://geo.stat.fi/geoserver/tilastointialueet/wfs?service=WFS&version=2.0.0&request=GetFeature&outputFormat=json&srsName=EPSG:3067"

# Municipality and region polygons, 1:1 000 000 generalisation, ETRS-TM35FIN (EPSG:3067)
curl -fsS -o "$OUT/kunta1000k_${YEAR}.json"    "${WFS}&typeName=tilastointialueet:kunta1000k_${YEAR}"
curl -fsS -o "$OUT/maakunta1000k_${YEAR}.json" "${WFS}&typeName=tilastointialueet:maakunta1000k_${YEAR}"

# Municipality -> region correspondence table (classification API)
curl -fsS -o "$OUT/kunta_maakunta_${YEAR}.json" \
  "https://data.stat.fi/api/classifications/v2/correspondenceTables/kunta_1_${YEAR}0101%23maakunta_1_${YEAR}0101/maps?content=data&meta=max&lang=fi&format=json"

echo "Fetched $YEAR data into $OUT (downloaded $(date -I))"
