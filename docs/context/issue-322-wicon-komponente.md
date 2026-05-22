# Context: Issue #322 — Wetter-Emojis durch WIcon-Komponente ersetzen

## Request Summary
AP-009 (Design-System-Verbot für Emojis im UI) verletzt: `weatherEmoji.ts` und `StageDetailRow.svelte` nutzen Emoji-Zeichen für Wetter-Icons. Diese müssen durch die kanonische `<WIcon>`-Komponente ersetzt werden, die laut `COMPONENTS.md §3` mit `kind`-Props arbeitet.

## Betroffene Dateien

| Datei | Relevanz |
|-------|----------|
| `frontend/src/lib/utils/weatherEmoji.ts` | Enthält das komplette WMO→Emoji-Mapping + `degToCardinal()`. Muss ersetzt werden. |
| `frontend/src/lib/components/trip-detail/StageDetailRow.svelte` | Inline `stageWeatherEmoji()` Funktion + 💧-Emoji in Z. 145. |
| `frontend/src/lib/components/compare/HourlyMatrix.svelte` | Nutzt `import { weatherEmoji }` aus weatherEmoji.ts |
| `frontend/src/routes/weather/+page.svelte` | Nutzt `import { weatherEmoji, degToCardinal }` |
| `frontend/src/routes/compare/+page.svelte` | Nutzt `import { weatherEmoji }` |

## WIcon-Spezifikation (aus COMPONENTS.md §3)

```
<WIcon kind="sun|cloud|rain|thunder|snow|wind|moon|headlamp" size color />
```

**WIcon existiert noch nicht** — muss neu erstellt werden.

## Lucide-Icons (verfügbar via @lucide/svelte)

| WIcon kind | Lucide-Icon |
|-----------|-------------|
| `sun` | `sun` |
| `cloud` | `cloud` oder `cloudy` |
| `rain` | `cloud-rain` |
| `thunder` | `cloud-lightning` |
| `snow` | `cloud-snow` oder `snowflake` |
| `wind` | `wind` |
| `moon` | `moon` |
| `headlamp` | (kein direktes Icon — `bolt` als Fallback) |

Weitere nützliche: `cloud-sun`, `cloud-moon`, `cloud-fog`, `cloud-drizzle`, `cloud-hail`, `cloud-sun-rain`

## WMO-Code → WIcon kind Mapping

Die bestehende Logik in `weatherEmoji.ts` muss auf WIcon kinds gemappt werden:

| WMO-Codes | Wetter | Emoji bisher | WIcon kind |
|-----------|--------|-------------|-----------|
| 45, 48 | Nebel | 🌫️ | `cloud` (+ cloud-fog) |
| 51, 53 | Nieselregen leicht | 🌦️ | `rain` |
| 55–57 | Nieselregen stark/gefrierend | 🌧️ | `rain` |
| 61–67 | Regen | 🌧️/🌨️ | `rain` |
| 71–77 | Schnee | ❄️ | `snow` |
| 80–82 | Regenschauer | 🌦️/🌧️ | `rain` |
| 85–86 | Schneeschauer | 🌨️ | `snow` |
| 95–99 | Gewitter | ⛈️ | `thunder` |
| isDay=0 + wolkig | Bewölkte Nacht | ☁️ | `cloud` |
| isDay=0 + klar | Klare Nacht | 🌙 | `moon` |
| DNI > 500 | Sonnig | ☀️ | `sun` |
| DNI 200–500 | Leicht bewölkt | 🌤️ | `sun` (cloud-sun) |
| DNI 50–200 | Teilweise bewölkt | ⛅ | `cloud` |
| DNI < 50 | Bewölkt | ☁️ | `cloud` |

## `degToCardinal()` — kein Emoji, bleibt erhalten

Die Funktion `degToCardinal()` in `weatherEmoji.ts` gibt Text zurück (N, NE etc.) — kein Emoji. Muss in neue Datei `weatherUtils.ts` verschoben werden.

## Existierende Patterns

- Icons werden via `@lucide/svelte` eingebunden: `import SunIcon from '@lucide/svelte/icons/sun'`
- Komponenten liegen in `frontend/src/lib/components/ui/<name>/index.ts`
- Beispiel-Komponente: `frontend/src/lib/components/ui/dot/` (Dot.svelte + index.ts)

## Abhängigkeiten

- **Upstream:** `@lucide/svelte` (bereits installiert, v1.8.0)
- **Downstream:** 4 Dateien importieren `weatherEmoji`; `StageDetailRow` hat zusätzlich inline-Logik

## Risks & Considerations

- `kind="headlamp"` ist im Katalog definiert, hat aber kein passendes Lucide-Icon — `Flashlight` oder `bolt` als Provisorium, oder in WIcon bewusst kein Icon für headlamp (da es nicht für WMO-Mapping gebraucht wird)
- Das 💧-Emoji in `StageDetailRow.svelte` Z. 145 fällt ebenfalls unter AP-009 → durch Text „Regen" oder `cloud-rain`-Icon ersetzen
- `weather/+page.svelte` ist eine interne Dev-Seite (kein Prod-UI), trotzdem bereinigen

## Vorhandene Specs

- `docs/design-system/COMPONENTS.md §3` — WIcon-Definition
- `docs/design-system/ANTI-PATTERNS.md → AP-009` — Emoji-Verbot
- `docs/design-system/CHARTER.md §5` — AP-009-Quelle
