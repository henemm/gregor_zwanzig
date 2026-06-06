# Context: #587 — Wetter-Metriken-Tab v2 (Desktop)

## Request Summary
Der „Wetter"-Tab im Trip-Bearbeiten-Screen ist heute nur eine Read-Only-Karte. Er soll
zum vollen **Wetter-Metriken-Tab v2** werden: 4 Abschnitte (Profil · Grundauswahl ·
Reihenfolge & Darstellung · Kanäle) links, **Live-Mail-Vorschau rechts (sticky)** mit
Diff-Highlight. Modell (PO-Entscheidung 2026-06-06): **zwei Zustände** `spalte`/`aus`,
**zwei Modi** `raw`/`indicator`, **keine Detail-Zeile**, **kein Signal**, Telegram-Limit 8.

## Verbindliche Quelle
- `claude-code-handoff/.../body-23-config-change-flow.md` (Feature-Spec)
- JSX `screen-trip-edit-v2-weather.jsx` / `-main.jsx` — **ABER:** der Detail-Bucket/`secondary`
  im JSX ist veraltet; PO-Entscheidung „keine Detail-Zeile" gewinnt. JSX-Bereinigung läuft
  separat über Claude Design, blockiert hier nicht.

## Related Files (IST)
| Datei | Relevanz |
|------|-----------|
| `frontend/src/lib/components/edit/TripEditView.svelte` | Edit-Shell, 5 Tabs; `wetter`-Tab = nur `WeatherSummaryCard` (read-only) |
| `frontend/src/lib/components/edit/WeatherSummaryCard.svelte` | wird durch v2-Tab ersetzt |
| `frontend/src/lib/components/trip-detail/WeatherMetricsTab.svelte` | bestehender 2-Spalten-Editor (Vorbild, im Detail) |
| `frontend/src/lib/components/shared/OutputLayoutEditor.svelte` | wiederverwendbarer Bucket-/Reihenfolge-Editor |
| `frontend/src/lib/components/trip-detail/ChannelPreviewBlock.svelte` | Live-Vorschau (Email/Telegram/SMS, signal-frei) |
| `frontend/src/lib/components/trip-detail/metricsEditor.ts` | Modell-Helfer; `CHANNEL_COL_BUDGET.telegram = 7` → muss 8 |
| `src/output/renderers/channel_layout.py` | Backend: `signal: max 6` raus, `_PRIMARY_SLOTS 5→8` |

## Fundament-Stand
- #610 Schritt 1/2 (Frontend Signal-frei): ✅ auf origin/main (3675fd0d), verifiziert.
- #610 Schritt 2/2 (Backend Signal komplett): offen, **nicht blockierend** (kein Nutzer).

## Abhängigkeiten
- Upstream: metricsEditor.ts-Modell (signal-frei ✓), OutputLayoutEditor, ChannelPreviewBlock.
- Downstream: #616 (Tab-IA/Umbenennung), #617 (Kanal-Verkettung Zeitplan/Alerts), #618 (Mobile) — **separate Slices**.

## Risiken
- Großer Frontend-Bau → LoC > 250, ggf. Slicing/Override mit PO-Freigabe.
- JSX vs. PO-Entscheidung (Detail-Bucket) — nach PO bauen, nicht nach JSX-Rest.
- Telegram-Budget-Drift Frontend(7)/Backend(8/PRIMARY_SLOTS 5) vereinheitlichen.
- Pixel-Diff-Hard-Gate (#603) gegen SOLL.
