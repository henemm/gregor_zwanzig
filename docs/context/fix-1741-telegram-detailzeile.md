# Context: fix-1741-telegram-detailzeile

Issue: #1741 · Milestone „Tour KHW 2026-08" · `bug`, `priority:high`, `area:output`
Stand: `origin/main` = `cba7ffa3`, Branch `fix-1741-telegram-detailzeile`

## Request Summary

Für Telegram ausgewählte Metriken ab Slot 8 (sowie alle `secondary`-Größen) erscheinen in
der Telegram-Segment-Tabelle überhaupt nicht. Die Auswahl im Editor bleibt für diese
Metriken wirkungslos.

## Kernbefund: es ist eine Regression, kein liegengebliebener Altcode

`ChannelLayout.detail_metrics` wird berechnet (`channel_layout.py:127`) und **an keiner
Stelle im Produktivcode gelesen**. Die zugehörige Renderfunktion `_detail_lines()`
(`narrow.py:111`) hat null Aufrufstellen.

Das war nicht immer so — Historie über `git log -S "detail_metrics" -- src/`:

| Commit | Datum | Wirkung |
|---|---|---|
| `5f9b57f9` | 2026-05-24 | #360 führt `detail_metrics` **und** `_detail_lines()` ein — **mit** Aufrufstelle |
| `5f8abcb4` | 2026-06-26 | #887 ergänzt `_tg_extra_detail_line()`, liest `table_columns + detail_metrics` |
| `6b27798f` | 2026-07-03 | **#1001 (Telegram-Redesign) entfernt beide Aufrufstellen** |

Aus dem Diff von `6b27798f`:

```
-            if layout.detail_metrics and rows:
-                    _detail_lines(layout.detail_metrics, rows[0], fkeys, width)
-        mid for mid in layout.table_columns + layout.detail_metrics
```

Die Spec des Redesigns (`docs/specs/modules/feat_1001_telegram_redesign.md:36-39`) nennt
ausdrücklich nur die Entfernung von `_tg_extra_detail_line()` und reaktiviert
`_narrow_table()`. Der Wegfall von `_detail_lines()` ist dort **nicht** als Entscheidung
dokumentiert — er sieht nach Kollateralschaden des Rewrites aus.

**Seit 2026-07-03, also rund 7 Wochen, ist `detail_metrics` funktionslos.**

## Wirkung auf echte Produktivdaten

Gemessen an `/var/lib/gregor/users/*/briefings/*.json` (nur gelesen):

**`henning/briefings/5f534011.json` — „KHW 403"**, `display_config.channel_layouts.telegram`:
14 aktive `primary`-Metriken, davon erscheinen 7.

| | Metriken |
|---|---|
| sichtbar (Slot 1–7) | `wind_chill`, `wind`, `wind_direction`, `precipitation`, `rain_probability`, `thunder`, `gust` |
| **unsichtbar** (order 7–13) | `visibility`, `cloud_low`, `cloud_total`, `snowfall_limit`, `uv_index`, `humidity`, `freezing_level` |

Der Bug trifft also die Hälfte einer sorgfältig sortierten Auswahl.

## Einschränkung: der Tour-Trip erreicht diesen Renderer gar nicht

`KHW 403` hat `report_config.telegram_style = "kurzform"`. Die Weiche in
`notification_service.py:469-486` verwirft im Kurzstil die Bubbles und sendet
`report.sms_text`. Der Bubble-Renderer läuft zwar immer (`format_email()` baut ihn
unbedingt), sein Ergebnis wird im Kurzstil aber weggeworfen.

Folgen:

- Auf der Tour ist die **gesamte** 14-Metriken-Telegram-Auswahl ohne Wirkung, nicht nur
  der Überlauf. Was ankommt, sind die 8 SMS-Metriken.
- **#1741 hat keine nutzersichtbare Wirkung während der KHW-Tour** — das
  Aufnahmekriterium des Milestones „Tour KHW 2026-08" trifft für dieses Ticket nicht zu.
- Betroffen sind Trips im `rich`-Stil: `default/gr221-mallorca` (explizit `rich`) und alle
  ohne gesetzten Stil (Default `rich`).

Diese Einordnung ist eine PO-Entscheidung und wird hier nur festgehalten, nicht vollzogen.

## Entwarnung: der SMS-Pfad ist nicht betroffen

Naheliegende Sorge: für SMS gilt `max_table_cols = 0`, also landen dort **alle** Metriken
in `detail_metrics` — bei totem `detail_metrics` wäre der SMS-Text metrikfrei.

Das ist nicht der Fall. `sms_trip.py` importiert `channel_layout` überhaupt nicht, sondern
baut über `build_token_line` / `render_sms` aus
`get_metrics_for_channel("sms", report_type)` (`trip_report.py:335-347`, `:439-447`;
`max_length=160` wird fest übergeben). Der Zweig `limit == 0` in
`channel_layout.py:119-120` ist damit **struktureller Testcode** — kein Renderer betritt ihn.

## Related Files

| Datei | Relevanz |
|---|---|
| `src/output/renderers/narrow.py:111` | `_detail_lines()` — fertige Renderfunktion, null Aufrufstellen |
| `src/output/renderers/narrow.py:700` | `render_for_channel("telegram", …)` — einziger Trip-Aufrufer |
| `src/output/renderers/narrow.py:855-856` | einzige Nutzung von `layout.*` — nur `table_columns` |
| `src/output/renderers/narrow.py:770-807` | Kurzübersicht-Bubble — liest `dc.get_enabled_metric_ids()`, also eine **andere Quelle** |
| `src/output/renderers/channel_layout.py:86,127` | `detail_metrics` — Definition und einzige Befüllung |
| `src/output/renderers/channel_layout.py:119-120` | SMS-Zweig `limit == 0`, unerreichbar |
| `src/output/renderers/comparison.py:701,762,768-769` | Ortsvergleich — liest `table_columns` **und** `demoted_count` |
| `src/output/renderers/comparison.py:854-867` | `_telegram_metric_notice()` — „+N weitere Wettergrößen je Ort (Telegram-Limit)" |
| `src/services/notification_service.py:469-486` | Kurzstil-Weiche (verwirft Bubbles, sendet `sms_text`) |
| `src/output/renderers/trip_report.py:293` | einzige produktive Aufrufstelle von `render_telegram_bubbles()` |
| `frontend/src/lib/components/trip-detail/metricsEditor.ts:379-404` | Frontend-Nachbau `applyChannel()` mit `inTable`/`detail`/`demoted` |

## Existing Patterns

**Der Ortsvergleich löst dasselbe Problem bereits sichtbar.** `render_compare_telegram()`
liest `demoted_count` und schreibt eine Hinweiszeile „+N weitere Wettergrößen je Ort
(Telegram-Limit)" (`comparison.py:768-769`, `:854-867`). Der Trip-Pfad hat kein Pendant.

Das ist relevant für die Code-Teilungs-Vorgabe aus `CLAUDE.md`: Trip und Ortsvergleich
sollen möglichst viel teilen. Hier existiert eine gelöste Compare-Variante und eine
kaputte Trip-Variante desselben Problems — ein geteilter Baustein ist ein ernsthafter
Kandidat und muss in der Spec ausdrücklich abgewogen werden.

## Dependencies

- **Upstream:** `UnifiedWeatherDisplayConfig.get_metrics_for_channel()`,
  `render_for_channel()`, `CHANNEL_LIMITS`, `_cell()`/`_compact_label()`/`_wrap()`
- **Downstream:** `TripReport.telegram_bubbles` (`models.py:1078`) →
  `notification_service.py:489-511` (Versand) und `preview_service.py:398` (Vorschau)

## Existing Specs

- `docs/specs/modules/feat_1001_telegram_redesign.md` — verursachende Spec; dokumentiert
  den Wegfall von `_detail_lines()` **nicht**
- `docs/specs/modules/feat_1260_telegram_kurzstil.md` — Kurzstil-Weiche
- `docs/specs/modules/issue_365_channel_preview_mobile.md` — Frontend-Kanalvorschau
- `docs/specs/_archive/modules/fix_887_report_inkonsistenz.md` — Ursprung der entfernten
  `_tg_extra_detail_line()`

## Risks & Considerations

1. **Die Testschicht kennt den Bug und weicht ihm aus.** `tests/tdd/test_channel_metric_matrix.py:800-806`
   hält im Klartext fest, dass `_detail_lines()` null Aufrufstellen hat und „überzählig"
   deshalb „gar nicht sichtbar" bedeutet. Der Test wählt daraufhin bewusst
   `freezing_level` (außerhalb des Budgets) und prüft es **nur** in der Kanal-Auswahl
   `table_columns + detail_metrics`, nicht in der Ausgabe (`:1395`). Kein einziger Test
   prüft eine gerenderte Telegram-Ausgabe auf eine `detail_metrics`-Metrik.
   ⇒ Ein Fix muss den Nachweis **an der Wirkstelle** führen (gerenderte Bubbles), sonst
   bewacht er nichts. Die vorhandenen Tests würden eine erneute Entkopplung nicht fangen.

2. **Altlast-Test, der die Regression zementiert:** `tests/tdd/test_issue_887_report_inkonsistenz.py:229`
   prüft, dass **keine** Detail-Zeile erscheint („Rain%" not in result) — seit dem Wegfall
   trivial wahr. Bei einem Fix wird dieser Test rot; er prüft veraltetes Verhalten und ist
   dann zu korrigieren oder zu löschen, nicht zu umgehen.

3. **Frontend verspricht möglicherweise etwas, das nicht geliefert wird.** `applyChannel()`
   berechnet `detail` und `demoted` für eine Nutzer-Vorschau. Ob diese Vorschau tatsächlich
   gerendert wird, ist noch offen (Agent `fe-vorschau` läuft, mit Positivkontroll-Pflicht,
   weil `grep` auf `WeatherMetricsTab.svelte` falsch-negative Treffer liefert). Wenn ja,
   ist das der eigentliche Beleg für „Bedienelement ohne Wirkung".

4. **Zwei Quellen in einer Nachricht.** Die Kurzübersicht-Bubble liest
   `dc.get_enabled_metric_ids()` (`narrow.py:780`), die Tabelle `layout.table_columns`.
   Die Kurzübersicht ignoriert damit die **kanalspezifische** Auswahl. Vermutete
   Konsequenz: eine für Telegram *abgewählte* Metrik erscheint dort trotzdem — das wäre
   derselbe Fehler in der Gegenrichtung. Noch nicht verifiziert, gehört in `/20-analyse`.

5. **Platzbudget ist real.** `_TG_TABLE_WIDTH` existiert, damit auf einem
   iPhone-Standardbildschirm kein Umbruch entsteht (`narrow.py:57-60`). Eine Detailzeile
   darf dieses Versprechen nicht aufweichen; `_detail_lines()` bricht selbst um, die
   Zielbreite ist aber zu wählen (`_TG_TABLE_WIDTH` vs. `_TG_PROSE_WIDTH`).

6. **Wächter aus #1480:** In `narrow.py` liegen Duldungs-Marker gegen lokale Kopien der
   Gewitter-Stufenskala. Stufenwerte nur über `THUNDER_LABEL_DE` aus
   `src/output/metric_format.py`, nie lokal nachbauen.

7. **Offene Richtungsentscheidung (PO).** Die drei Optionen des Tickets sind nach der
   Historie nicht mehr gleichwertig: Option 3 („ersatzlos entfernen") würde eine
   unbeabsichtigte Regression nachträglich zur Entscheidung erklären. Vorlage erfolgt mit
   der Spec.
