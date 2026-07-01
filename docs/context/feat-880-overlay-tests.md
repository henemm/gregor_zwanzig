# Context — feat_880 Autospeicher-Overlay: E2E-Tests nachziehen (Issue #947)

## Ausgangslage

Die Autospeicher-Anzeige hat zwei Spec-Ebenen:

- **`issue_758_save_indicator.md`** (live, getestet): Vier-Zustands-Indikator `idle/dirty/saving/error`, Auto-Save im Trip-Editor, expliziter Save im Compare-Editor. Abgedeckt durch `frontend/e2e/issue-758-save-indicator.spec.ts` (AC-1..AC-7).
- **`feat_880_autosave_overlay.md`** (implementiert + live, aber Spec war `draft`/nicht freigegeben, **null Testabdeckung**): Umbau zu fixem Overlay unten rechts + **Zeitstempel des letzten Speicherns** (`✓ Gespeichert 14:32`).

## Befund (Root Cause)

feat_880 ist vollständig im Code:
- `frontend/src/lib/stores/saveStatusStore.svelte.ts` — `savedAt: Date`, `setSaved()` setzt Timestamp.
- `frontend/src/lib/components/ui/SaveIndicator.svelte` — HH:MM-Anzeige (`.save-time`), `position: fixed; bottom/right`, Mobile-Query über BottomNav, Idle-Dimming `gz-save-fade` → opacity 0.5, Fehler-Zustand `animation: none; opacity: 1`.

Aber: kein einziger Test prüft diese Anforderungen. Der 758-Test prüft nur die Zustandslogik/Labels. Das Feature ging ohne Spec-Freigabe und ohne Testabdeckung live — Prozessloch (Issue #947).

## Ziel dieses Workflows

Neue E2E-Test-Datei `frontend/e2e/feat-880-autosave-overlay.spec.ts`, die die 7 ACs aus `feat_880` gegen den laufenden Stack (Staging) prüft — Playwright, kein Mock. Kern: die „Wann zuletzt gespeichert"-Anzeige (Timestamp HH:MM). Kein `src/`-Code wird geändert (Regressions-/Charakterisierungstests für live-Code).

## Test-Grundlage: feat_880 ACs

- AC-1: Overlay `position: fixed`, kein Inline-Indikator in Header-Statuszeile.
- AC-2: nach Auto-Save Text „Gespeichert" + Uhrzeit HH:MM (**Kern**).
- AC-3: Idle-Dimming opacity ≤ 0.5 nach 3 s, bleibt sichtbar (`display != none`).
- AC-4: Fehler-Zustand dauerhaft opacity 1, kein Dimming.
- AC-5: Mobile (≤899 px) Overlay über BottomNav, BottomNav klickbar.
- AC-6: Cross-Tab-Isolation des Timestamps.
- AC-7: Compare-Editor — genau ein `save-indicator` im DOM.

## Referenzen

- Vorbild-Test (Seed/Login/Struktur): `frontend/e2e/issue-758-save-indicator.spec.ts`
- Spec: `docs/specs/modules/feat_880_autosave_overlay.md`
