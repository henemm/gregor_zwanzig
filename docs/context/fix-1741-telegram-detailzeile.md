# Context: fix-1741-telegram-detailzeile

Issue: #1741 · Milestone „Tour KHW 2026-08" · `bug`, `priority:high`, `area:output`
Stand: `origin/main` = `cba7ffa3`, Branch `fix-1741-telegram-detailzeile`

## Request Summary

Für Telegram ausgewählte Metriken ab Slot 8 (sowie alle `secondary`-Größen) erscheinen in
der Telegram-Segment-Tabelle überhaupt nicht. Die Auswahl im Editor bleibt für diese
Metriken wirkungslos.

## Kernbefund: toter Pfad — Umsetzung eines PO-Entscheids, NICHT eine Regression

> **Achtung, Lesereihenfolge:** Der erste Eindruck aus der Commit-Historie war „unbeabsichtigte
> Regression". Die Analyse weiter unten widerlegt das: der Wegfall setzt die PO-Entscheidung
> vom 2026-06-06 um. Dieser Abschnitt hält nur die Historie fest.

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
`_narrow_table()`. Der Wegfall von `_detail_lines()` ist dort **nicht** protokolliert —
was den Eindruck eines Kollateralschadens erzeugt. Die Analyse zeigt: er folgt dem
PO-Entscheid vom 2026-06-06 (#587), der die Detail-Zeile abgeschafft hat. Fehlend ist die
Dokumentation, nicht die Entscheidung.

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
| `src/output/renderers/narrow.py:770-807` | Kurzübersicht-Bubble — zeigt **alle** aktiven Telegram-Metriken als Tagesaussage |
| `src/output/renderers/trip_report.py:275-292` | baut `_dc_telegram` (kanal-kaskadiert) — EINE Quelle für Tabelle + Kurzübersicht |
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

4. ~~**Zwei Quellen in einer Nachricht.**~~ **WIDERLEGT in der Analyse.** Die
   Kurzübersicht liest zwar `dc.get_enabled_metric_ids()` (`narrow.py:780`), bekommt aber
   ein bereits kanal-kaskadiertes `dc`: `trip_report.py:275-278` baut `_dc_telegram` aus
   `get_metrics_for_channel("telegram", report_type)`. Der ausführliche Kommentar
   `trip_report.py:280-292` hält fest, dass genau diese Falle als Adversary-Finding F004
   (#1719 S2) gefangen wurde. Es gibt EINE Quelle für Tabelle, Kurzübersicht und Fußzeile.

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

---

## Analysis

### Type

Bug — aber mit deutlich kleinerem Schaden als das Ticket beschreibt, und teils auf einer
falschen Prämisse.

### Was wirklich passiert (Trip „KHW 403", 14 Telegram-Metriken)

| Ort | Was erscheint |
|---|---|
| Kurzübersicht-Bubble (`narrow.py:780-807`) | **alle 14** Metriken, je eine Tagesaussage-Zeile |
| Segment-Tabelle (`narrow.py:855-856`) | **7** Metriken, stündliche Werte |

Verloren geht also **nicht die Metrik, sondern ihre stündliche Auflösung**. Die
Ticket-Formulierung „verschwindet aus der Tabelle" trifft zu; „die Auswahl bleibt
wirkungslos" trifft **nicht** zu.

### Drei Ticket-Prämissen, die die Untersuchung nicht bestätigt

1. **„ohne Hinweis" — falsch.** Der Editor warnt dreifach:
   Chip `−N` am Kanalreiter (`LTChannelPicker.svelte:50-53`), gestrichelte Schnittlinie
   „✂ ab hier Telegram-Limit (max 7)" (`LTCutLine.svelte:20`), warngefärbter Hinweis
   „Telegram: N Metriken · zu breit — max 7, weiter vorne = sicherer"
   (`ltChannels.ts:130-149`, gerendert `LTCapNote.svelte:47-49`). Der Versand-Reiter sagt
   „Telegram die ersten 7" (`vtBriefingChannelsText.ts:34`).

2. **„die dafür gebaute Detailzeile" — irreführend.** Es gibt eine dokumentierte
   **PO-Entscheidung vom 2026-06-06**: „Kein ‚→ Detail'-Knopf, keine Detail-Zeile"
   (`WeatherV2Reihenfolge.svelte:4`, Issue #587). Seither ist der `secondary`-Bucket
   immer leer (`WeatherMetricsTab.svelte:220`, erzwungen `:436`/`:682`); die Design-Quelle
   von #622 nennt den Editor-Screen ausdrücklich „(Roh/Einfach, kein Detail)".
   ⇒ Der Wegfall in #1001 (`6b27798f`, 2026-07-03) setzt diesen Entscheid um. Er ist
   **keine unbeabsichtigte Regression** — nur in der #1001-Spec nicht protokolliert.
   Option 1 des Tickets („`_detail_lines()` aufrufen") widerspricht dem Entscheid direkt.

3. **Tour-Relevanz — nicht gegeben.** `KHW 403` fährt `telegram_style = kurzform`
   (siehe oben). Der Bubble-Renderer wird auf der Tour nicht ausgeliefert.

### Die verbleibende echte Lücke

**Die Telegram-Nachricht selbst trägt keinen Kappungshinweis.** Der Ortsvergleich hat auf
demselben Kanal längst einen: `comparison.py:768-769` liest `demoted_count` und schreibt
über `_telegram_metric_notice()` (`:854-867`) die Zeile „+N weitere Wettergrößen je Ort
(Telegram-Limit)". Der Trip-Pfad hat kein Pendant, obwohl `demoted_count` dort berechnet
wird und bereitliegt.

Wer das Briefing liest, ohne den Editor offen zu haben — also unterwegs —, kann nicht
wissen, dass die Tabelle beschnitten ist. Das ist der Rest von #1741, der Bestand hat.

### Toter Code als Nebenwirkung

`detail_metrics` (`channel_layout.py:127`) und `_detail_lines()` (`narrow.py:111`) sind
seit `6b27798f` produziert-aber-nie-konsumiert. Genau diese Leiche hat das Ticket erzeugt:
Sie sieht aus wie eine vorhandene, nur nicht verkabelte Fähigkeit, ist aber das Gegenteil —
eine abgeschaffte. Solange sie steht, wird sie erneut als Bug gemeldet werden.

Ebenfalls tot, gleiche Familie:
- `applyChannel()`/`ChannelLayout` im Frontend (`metricsEditor.ts:379-405`) — nur Tests
- SMS-Zweig `limit == 0` (`channel_layout.py:119-120`) — kein Renderer betritt ihn
- `SavePresetDialog.svelte:205-213` zeigt dauerhaft „0 Detail" (`secondary` immer leer)

### Affected Files (Vorschlag, abhängig von der PO-Richtung)

| Datei | Change | Beschreibung |
|---|---|---|
| `src/output/renderers/narrow.py` | MODIFY | Kappungshinweis in der Segment-Bubble; `_detail_lines()` entfernen |
| `src/output/renderers/comparison.py` | MODIFY | `_telegram_metric_notice()` zum geteilten Baustein heben |
| `src/output/renderers/channel_layout.py` | MODIFY | `detail_metrics` entfernen; `demoted_count` bleibt |
| `tests/tdd/test_issue_887_report_inkonsistenz.py:229` | MODIFY | prüft veraltetes Verhalten (trivial wahr) |
| `tests/tdd/test_issue_360_channel_renderer.py`, `test_issue_429_channel_layouts.py`, `test_channel_metric_matrix.py`, `test_felt_night_catalog_exclusions.py`, `test_temp_tagesrichtung_aufloesung.py` | MODIFY | lesen `detail_metrics` |
| `frontend/.../metricsEditor.ts` + `.test.ts` | MODIFY | tote `applyChannel()`/`ChannelLayout` |

### Scope Assessment

- Dateien: 4 Produktiv + ~7 Test (bei voller Aufräumung)
- Geschätzte LoC: +40 / −90
- Risiko: **LOW** — der Hinweistext ist additiv; das Entfernen betrifft ausschließlich
  Code ohne Konsumenten. Einziges echtes Risiko: die Test-Anpassungen sind breit gestreut.

### Technical Approach (Empfehlung)

**Nicht Option 1.** Sie widerspricht dem PO-Entscheid vom 2026-06-06.

Empfohlen ist die Kombination aus Option 2 und 3, in dieser Reihenfolge:

1. **Kappungshinweis in der Trip-Telegram-Nachricht**, wortgleich zum Ortsvergleich, über
   einen **geteilten Baustein** (`_telegram_metric_notice()` aus `comparison.py` heben).
   Das erfüllt die Code-Teilungs-Vorgabe und schließt die einzige Lücke, die unterwegs
   spürbar ist. Quelle ist `demoted_count`, das bereits berechnet wird.
2. **`detail_metrics` + `_detail_lines()` ersatzlos entfernen**, damit der tote Pfad keine
   abgeschaffte Fähigkeit mehr vortäuscht. Der Entscheid von 2026-06-06 wird dabei in der
   Spec dokumentiert — das Versäumnis von #1001 wird nachgeholt.

Nachweis-Pflicht: Der Test muss die **gerenderten Bubbles** prüfen, nicht das
Layout-Ergebnis. Alle heutigen Tests prüfen die Berechnung (siehe Risiko 1) und würden
eine erneute Entkopplung nicht bemerken.

### Open Questions (PO)

- [ ] Bestätigst du, dass die Detail-Zeile abgeschafft bleibt (Entscheid 2026-06-06)?
- [ ] Soll die Telegram-Nachricht einen Kappungshinweis tragen — oder genügt die Warnung
      im Editor, sodass #1741 als „so gewollt" geschlossen wird?
- [ ] Bleibt #1741 im Milestone „Tour KHW 2026-08", obwohl der Tour-Trip im Kurzstil fährt?
