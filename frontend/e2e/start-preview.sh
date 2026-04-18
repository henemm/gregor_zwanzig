#!/bin/bash
# Load env from project root for E2E tests
set -a
source "$(dirname "$0")/../../.env"
set +a
export NODE_ENV=test
npm run build && npm run preview -- --port 4173
