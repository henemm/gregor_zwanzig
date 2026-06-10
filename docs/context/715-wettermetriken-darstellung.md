# Context: #715 — Paket Wettermetriken-Darstellung (#711, #710, #712)

## Request Summary
Sammel-Issue für drei zusammengehörende Darstellungs-Bugs der Wettermetriken im Trip-Editor/Wizard (gleiche Komponenten-Familie): (#711) Emojis/Ampel in der „einfach"-Variante zurückholen, (#710) ungewollte „Sicherheit"-Metrik wieder ausblenden, (#712) Vorschau klar als Beispieldaten kennzeichnen. Parent-Framing: rein frontend, ein Staging-Durchlauf, ein Deploy.

## Related Files
| File | Relevance |
|------|-----------|
| `frontend/src/lib/components/trip-detail/WeatherV2MailPreview.svelte` | #711 + #712: hartcodierte Sample-Daten `WM2_S` (Z.26–52) mit Text-Indikatoren (`'ruhig'`,`'bed.'`,`'gut'`); `cell()` Z.55–60 wählt ind vs raw; echt wirkende Etappe „Etappe 4: Hochweißsteinhaus → Wolayersee" / „KHW 403" hartcodiert (Z.187/191/192/242); einziges Label „So kommt es an" (Eyebrow Z.138) |
| `frontend/src/lib/components/trip-wizard/steps/Step3Weather.svelte` | #710 root cause: Z.116–127 initialisiert ALLE Katalog-Metriken mit `enabled: true` (Z.121), ignoriert `m.default_enabled` → `confidence`/„Sicherheit" (default_enabled=False) erscheint |
| `frontend/src/lib/components/trip-detail/WeatherMetricsTab.svelte` | Trip-Editor-Pendant — Z.176 filtert KORREKT auf `default_enabled` (kein Bug hier) |
| `frontend/src/lib/components/trip-detail/metricsEditor.ts` | `INDICATOR_MAP` (Z.22–39): Text-Skalen je Metrik (`cape: 'niedrig / mittel / hoch / extrem'` …). Steuert nur Frontend-UI, nicht den Formatter |
| `src/app/metric_catalog.py` | `confidence` MetricDefinition Z.171–182, `label_de="Sicherheit"`, `default_enabled=False` ✓ (Backend korrekt) |
| `src/output/renderers/email/helpers.py` | `fmt_val` Z.353+: `mode=="simplified"` → **Text-Adjektiv** (Z.386–403); Emoji nur in `symbol`-Mode (cloud ☀️🌤️⛅ Z.414–426, cape 🟢🟡🟠🔴 Z.453–467). „Einfach" = simplified → rendert AKTUELL Text, nicht Emoji |
| `api/routers/config.py` | `/api/metrics` liefert `default_enabled` ✓ |

## Existing Patterns
- Format-Modi-Modell (Issue #435): `raw` / `scale` / `simplified` / `symbol`. Emojis lebten im `symbol`-Mode.
- Issue #629 / PO-Entscheidung #620 (2026-06-07, Commit 7ae9221d): UI auf nur noch **Roh/Einfach** reduziert; `scale` + `symbol` aus der Oberfläche entfernt. „Einfach" mappt auf `simplified` (Text-Adjektive). Backend-Emoji-Logik (`symbol`) blieb im Code, ist aber nicht mehr aus der UI erreichbar.
- Katalog-getriebene Defaults: `default_enabled` ist die Single Source of Truth, welche Metriken vorausgewählt sind.

## Dependencies
- Upstream: Backend-Katalog `/api/metrics` (default_enabled, has_friendly_format), Formatter `fmt_val`.
- Downstream: gesendete E-Mail (echtes simplified-Rendering) — MUSS mit der Vorschau übereinstimmen, sonst lügt die Vorschau.

## Existing Specs
- `docs/specs/modules/issue_435_metric_format_modes.md` — Format-Modi-Modell
- `docs/context/issue-629-format-reduktion.md` — Reduktion auf Roh/Einfach (#620)
- `docs/specs/modules/epic_138_174_178_metriken_ui.md` — Metriken-Editor / INDICATOR_MAP

## Risks & Considerations
- **#711 Scope-Konflikt (BLOCKER für PO):** Das aktuelle „Einfach"-Rendering im echten E-Mail-Versand ist TEXT (`simplified`-Adjektive) — die Vorschau ist dadurch heute KONSISTENT. Würden wir nur die Vorschau-Mock auf Emojis umstellen, würde die Vorschau lügen (Versand zeigt weiterhin Text). Echtes Wiederherstellen der Emojis ist eine **Backend-Verhaltensänderung** (simplified→Emoji ODER symbol-Mode reaktivieren) und damit **full-stack**, im Widerspruch zum „rein frontend"-Framing des Parent-Issues. Außerdem reversiert es teilweise die PO-Entscheidung #620/#629. → **PO-Klärung nötig.**
- #710: Echte Regression, lokalisiert (Step3Weather.svelte Z.121 `enabled: true` hardcoded). Frontend-only, niedriges Risiko. Editor-Pfad ist nicht betroffen.
- #712: Reines Label/Hinweis-Hinzufügen (Beispieldaten kennzeichnen). Frontend-only, niedriges Risiko. Evtl. auch die echt wirkenden hartcodierten Etappennamen entschärfen.
- Mandantentrennung: keine neuen daten-/nutzerbezogenen Endpoints betroffen.
