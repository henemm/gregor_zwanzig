#!/bin/bash
# Load env from project root for E2E tests
set -a
source "$(dirname "$0")/../../.env"
[ -f "$(dirname "$0")/../../.env.e2e" ] && source "$(dirname "$0")/../../.env.e2e"
set +a
export NODE_ENV=test
npm run build && npm run preview -- --port 4173
