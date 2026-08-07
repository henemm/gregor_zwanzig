#!/bin/bash
# Issue #1289: gezielter statt blanket Env-Load — .env.e2e ist secret-frei
# (git-getrackt, öffentliches Repo!) und wird weiter komplett gesourced;
# aus der Haupt-.env werden NUR GZ_SESSION_SECRET + GZ_GOOGLE_CLIENT_ID
# gezogen (siehe e2e-env.sh) statt aller 41 Schlüssel dort.
source "$(dirname "$0")/e2e-env.sh"
set -a
[ -f "$(dirname "$0")/../../.env.e2e" ] && source "$(dirname "$0")/../../.env.e2e"
set +a
export NODE_ENV=test
# Issue #1284 Fix-Loop 5: SvelteKit-Server-Routen (src/routes/api/[...path],
# src/routes/login/+page.server.ts) rufen apiBase() auf (frontend/src/lib/
# server/apiBase.ts), NICHT den Vite-Proxy (API_PROXY_TARGET). Ohne diese
# Zeile fällt jeder E2E-Lauf mangels gesetztem GZ_API_BASE auf apiBase()s
# Prod-Default (localhost:8090) zurück -- der eigentliche Bug hinter #1284.
# ${GZ_API_BASE:-...} respektiert einen bereits von außen gesetzten Wert.
export GZ_API_BASE="${GZ_API_BASE:-http://localhost:8091}"
npm run build && npm run preview -- --port 4173
