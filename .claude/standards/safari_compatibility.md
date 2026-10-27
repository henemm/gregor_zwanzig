# Safari Compatibility Standard — OBSOLET

**Status:** obsolet seit Issue #129 Phase A.3 (Commit `f53830178`, „NiceGUI-UI ersatzlos
entfernen"). Die hier früher beschriebene Factory-Pattern-Regel für NiceGUI-`ui.button`-Handler
betraf ausschließlich die entfernte NiceGUI-Oberfläche. Die produktive Oberfläche ist das
SvelteKit-Frontend (`frontend/`).

Für UI-Verifikation gilt: `staging-validator`-Agent bzw. `/e2e-verify` Schritt 3a gegen
Staging, Frontend-Browser-Gate (`docs/reference/gates_und_ratschen.md`), Fresh-Eyes bei
UI-Änderungen (CLAUDE.md).

Die Datei bleibt als Stub bestehen, weil `tests/tdd/test_issue_316_docs_cleanup.py` sie als
Tooling-Datei referenziert. Historische Bugfix-Specs: `docs/specs/bugfix/locations_add_button_fix.md`,
`docs/specs/bugfix/safari_subscriptions_fix.md`.
