# Context: fix-1362-1399-compare-kurzformen

Zwei Issues, beide betreffen die **Kurznachrichten des Ortsvergleichs** (Telegram + SMS).
Etappe **S5** aus Epic #1372 (Dach #1374).

## Request Summary

- **#1362** — Der Nutzer kann 26 Wettergrößen wählen, der Kanal-Renderer kennt 6.
  Der Rest verschwindet **still**, ohne Hinweis.
- **#1399** — Uhrzeiten im Telegram-Kurztext angeblich in Weltzeit statt Ortszeit.
  **Vermutlich bereits erledigt** (s.u.) — vor jeder Arbeit zu beweisen.

## Befund zu #1399: die Fundstelle existiert nicht mehr

Das Issue nennt `compact_summary.py:484 _location_tz()`. Diese Funktion wurde mit
**#1402** (Zeitzonen-Wächter, Commit `46738a8f`) **entfernt** — heute steht dort nur
noch ein erklärender Kommentar (`compact_summary.py:622-627`).

| Prüfung | Ergebnis |
|---|---|
| `grep _location_tz src/` | nur eine Kommentarzeile, keine Funktion |
| Aufrufer von `format_location_summary` | **keiner im Produktivcode** (nur `tests/unit/test_trip_summary_text.py:13`) |
| Uhrzeiten im Compare-Telegram | ausschließlich `location_tz()` / `resolve_location_tz()` (`comparison.py:182,246,504,603`) |

Der zentrale Auflöser `resolve_location_tz(location)` (`src/utils/timezone.py:40`)
nimmt `SavedLocation.timezone` mit Vorrang und fällt sonst auf `tz_for_coords(lat,lon)`
zurück — genau die Lücke, die #1399 beschreibt, ist damit geschlossen. Gehütet von
`tests/test_output_timezone_guard.py`.

**Offen bleibt allein die Testabdeckung:** `tests/tdd/test_compare_local_time_basis.py`
importiert nur `render_compare_email` und `render_compare_sms` — **kein Telegram**
(791 Zeilen, `context="vergleich"` kommt nicht vor).

⇒ **Vorgehen:** Ein Test, der den Fehler aus Nutzersicht reproduzieren *würde*
(Ort ohne gespeichertes Zeitzonenfeld, Telegram-Kurztext, Uhrzeit prüfen). Bleibt er
grün, ist #1399 gegenstandslos und wird mit diesem Nachweis geschlossen — der Test
bleibt als Abdeckung der Lücke bestehen. Wird er rot, ist es doch ein Fehler.
Vorbild für dieses Vorgehen: #1414.

## Befund zu #1362: der Trip hat die Lösung vollständig, Compare nutzt sie nicht

### Ist-Zustand Compare

| Stelle | Verhalten |
|---|---|
| `comparison.py:380-387` | `_CHANNEL_METRICS` — feste Sechserliste: temp_max, wind_max, sunny_hours, cloud_avg, snow_depth_cm, snow_new_cm |
| `comparison.py:415-436` | `_channel_metric_cells()` bildet die **Schnittmenge** aus Nutzerauswahl und dieser Liste |
| `comparison.py:394-412` | `_format_channel_metric()` — eigene if-Kette über dieselben 6 IDs, alles andere → `None` |
| `comparison.py:391,605` | `_SMS_METRICS_PER_LOCATION = 2`, bei amtlicher Warnung 1 |
| `comparison.py:452,632` | liest die Kanalgrenzen, rechnet Budget aber selbst (`metric_slots`, `+k`) |

**Zwei Stellen verwerfen still** — die Schnittmenge und die if-Kette. Der Mail-Klartext
bedient dagegen alle 26 (`comparison.py:81-100` `_PLAIN_ROWS`).

### Der Trip-Weg (vorhanden, erprobt, ungenutzt von Compare)

| Baustein | Datei | Leistung |
|---|---|---|
| Kanal-Aufteilung | `src/output/renderers/channel_layout.py:50-81` `render_for_channel(channel, dc, report_type)` | sortiert nach `bucket`/`order`, kappt an `CHANNEL_LIMITS` (`:20-24`) und **verschiebt Überzähliges nach `detail_metrics` statt es zu verwerfen** — `demoted_count` als Beleg |
| Priorisierung | `channel_layout.py:29-36` `METRIC_PRIORITY` (25 Katalog-IDs) + `auto_distribute()` (`:84-109`) | entscheidet, was bei Platzmangel vorn steht |
| Trip-Telegram | `src/output/renderers/narrow.py:502-535` | nutzt genau das |
| SMS-Kürzel | `metric_catalog.py:57` Feld `sms_code`, Getter `:741` `get_sms_code()` | zentral je Größe (D, N, W, G, R, TH, CP, NL, SD …) |
| SMS-Kürzung | `src/output/tokens/builder.py:36-47` `PRIORITY`, `src/output/tokens/render.py:42-101` `_truncate` | wirft **ganze Token** ab, nie mitten im Wort |

**Grenzen:** SMS 140 Zeichen (`channel_layout.py:23`), Telegram 4096 / max. 8 Spalten (`:22`).

⇒ Damit ist die Frage „26 Größen passen nicht in 140 Zeichen" **bereits beantwortet** —
nicht durch Wegwerfen, sondern durch Priorisieren und Verschieben mit sichtbarem Zähler.
Eine PO-Entscheidung ist dafür nicht nötig; die Projektvorgabe (CLAUDE.md,
Trip/Compare-Teilung) verlangt ohnehin, den Trip-Weg zu nutzen statt neu zu bauen.

## Auswahlweg (wie die Nutzerauswahl ankommt)

`display_config.active_metrics` → `resolve_compare_render_options()`
(`src/services/report_config_resolver.py:209`) → `CompareRenderOptions.enabled_metrics`
→ `scheduler_dispatch_service.py:394-397`, `compare_preview_service.py:61-66,98,115`
→ `render_compare_telegram` / `render_compare_sms`.

Vokabular: `src/output/renderers/compare_metric_ids.py:15-57`
(`FRONTEND_TO_RENDERER_METRIC_ID`, 26 Einträge).

## Risks & Considerations

1. **Ein Bestandstest zementiert den Missstand als Sollwert.**
   `tests/unit/test_compare_mail_blocks.py:343-379`
   `test_telegram_and_sms_output_unchanged_by_summary_block_removal` vergleicht mit `==`
   gegen aufgezeichnete Strings: bei Auswahl `["temp_max_c","precip_sum_mm"]` erwartet er
   wörtlich `"Andermatt\n   Temp 16°C"` — **`precip_sum` fehlt, und das ist als „muss
   grün bleiben" festgeschrieben.** Muss begründet umgestellt werden, nicht stillschweigend.
   Zweiter, weicherer Zeuge: `tests/unit/test_compare_metric_order.py:229-296` benennt
   `_CHANNEL_METRICS` ausdrücklich als heutige Quelle.
2. **`CompareRenderOptions.enabled_metrics` ist noch `Optional[set]`**
   (`report_config_resolver.py:157`), obwohl die Reihenfolge seit #1359 trägt. Beim
   Umbau auf den geteilten Baustein ist die Ordnung zu erhalten.
3. **Die Trip-Mechanik arbeitet auf `UnifiedWeatherDisplayConfig`**, Compare übergibt
   eine Liste von Renderer-IDs. Die Naht zwischen beiden ist der eigentliche Umbau —
   hier entscheidet sich, ob es eine echte Teilung wird oder eine dritte Variante.
4. **`detail_metrics` braucht im Compare-Kontext eine Entsprechung.** Der Trip zeigt
   Verschobenes an anderer Stelle; ob das im Ortsvergleich sinnvoll ist oder ob dort
   der Zähler allein genügt, ist in der Spec zu klären.
5. Beide Issues berühren dieselbe Datei (`comparison.py`), aber verschiedene Funktionen
   und Zeilen — #1362 in `:380-436`, #1399 (falls überhaupt) im Warnblock `:496-508`.
   Keine Kollision.

## Existing Specs

- `docs/specs/modules/rework_1300_compare_summary_block_removal.md` — Rückbau des
  Zusammenfassungssatzes, erklärt warum `format_location_summary` aufruferlos ist
- `docs/reference/sms_format.md`, `docs/reference/sms_briefing_overview.md`
