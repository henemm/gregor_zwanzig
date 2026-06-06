# Context: #624 — SMS/Telegram-Kurzform Schwellwerte pro Metrik konfigurierbar

## Request Summary
Die Schwellwerte, die in der SMS-/Telegram-Kurzform bestimmen, wann der „erste-
Überschreitung"-Wert (`R0.2@15`) erscheint, sind heute fest eingebaut. Sie sollen
pro Metrik im Trip-Editor (Wetter-Metriken-Tab) einstellbar werden.

## Wie der Schwellwert heute wirkt
`render_threshold_peak_value` (`src/output/tokens/metrics.py:29`): erster Wert =
erste Stunde mit `value >= threshold`, Klammerwert = Tagesmaximum. Bei `threshold is None`
fällt `first` auf den Peak (Klammer entfällt).

## Related Files
| Datei | Relevanz |
|------|-----------|
| `src/output/tokens/builder.py:77` | `DEFAULTS = {"R":0.2,"PR":20,"W":10,"G":20,...}` — fixe Schwellwerte |
| `src/output/tokens/builder.py:104-113` | `_mk_metric` — `thr = spec.threshold or DEFAULTS.get(symbol)` (Andock-Punkt) |
| `src/output/tokens/dto.py:54-61` | `MetricSpec.threshold: Optional[float]` — Feld existiert, wird im SMS-Pfad NIE befüllt |
| `src/output/tokens/metrics.py:29-52` | Render-Logik erste-Überschreitung + Peak |
| `src/formatters/sms_trip.py:107-166` | `format_sms()` — **bekommt KEINE display_config**, `config=None` (außer WE-Spec) |
| `src/output/adapters/trip_result.py:191-206` | `_wintersport_default_config()` — einzige Stelle mit threshold-MetricSpecs (W=10,G=20) |
| `src/formatters/trip_report.py` | Ruft `format_sms()` für SMS UND (seit #614) Telegram-Kurzform |
| `src/app/models.py:480-504` | `MetricConfig` (User-Editor-Datenmodell) — hat `alert_threshold` (Alarme, anders!), KEIN Anzeige-Schwellwert |
| `src/app/metric_catalog.py:30-52` | Catalog-Entry — hat `display_thresholds` (E-Mail-Farbe, anders!), KEIN SMS-Symbol |
| `src/app/loader.py` | DisplayConfig-Roundtrip (zwei Serialisierungsblöcke: Location + Trip) |
| `frontend/.../trip-detail/WeatherMetricsTab.svelte` | Editor — neuer Schwellwert-Input pro Metrik |

## Existing Patterns
- Additive Konfig-Felder + Read-Modify-Write-Merge (zuletzt #614 `telegram_kurzform`): models.py-Feld → loader.py beide Blöcke → Go-API DisplayConfig-Map (kein Struct-Change) → Frontend-Input.
- #435 `format_mode` pro Metrik: Catalog liefert erlaubte Werte + Default, MetricConfig trägt Override.

## Architektonische Lücken (für Scope wichtig)
1. **`format_sms()` ist schwellwert-blind:** nimmt keine display_config; Thresholds kommen rein aus `DEFAULTS`. Signatur + Aufrufer (trip_report.py, 2 Stellen) müssen erweitert werden.
2. **Kein `metric_id`→SMS-Symbol-Mapping:** Catalog kennt metric_ids (`rain_probability`,`gust`), Builder kennt POSITIONAL-Symbole (`PR`,`G`). Map muss neu (kleine Tabelle oder Catalog-Feld).
3. Nur 4 Metriken nutzen überhaupt einen Schwellwert (R, PR, W, G); N/D/Level-Metriken nicht.

## Dependencies
- Upstream: `build_token_line`, `MetricSpec`, `MetricConfig`, `MetricCatalog`.
- Downstream: SMS-Versand + Telegram-Kurzform (#614) — beide teilen den Token-Renderer; E-Mail-Tabelle nutzt separate `display_thresholds` (nicht betroffen, außer wir wollen es vereinheitlichen).

## Existing Specs
- `docs/specs/modules/sms_format.md` v2.0/§5 (Threshold+Peak, golden-master)
- `docs/specs/modules/output_token_builder.md`
- `docs/specs/modules/issue_435_metric_format_modes.md` (Vorbild: Override pro Metrik)
- `docs/specs/modules/issue_614_615_telegram_kurzform.md` (#614, teilt den Renderer)

## Risks & Considerations
- **Scope/LoC:** Backend-Threading + neues Mapping + Frontend-Editor → vermutlich nahe/über 250 LoC. Kandidat zum Splitten (Backend zuerst, Frontend danach) oder MVP auf die 4 threshold-fähigen Metriken begrenzen.
- **Golden-Master SMS:** Ohne Konfiguration MUSS Output bit-identisch bleiben (Defaults als Fallback). AC-Guard nötig.
- **Datenverlust:** additives Feld, Read-Modify-Write-Merge beachten (CLAUDE.md Schema-Regel).
- **Begriffsverwechslung:** `alert_threshold` (Alarme) und Catalog-`display_thresholds` (E-Mail-Farbe) sind NICHT dasselbe — neues Feld klar benennen (z.B. `sms_threshold`).
