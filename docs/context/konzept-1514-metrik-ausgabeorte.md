# Context: konzept-1514-metrik-ausgabeorte

## Request Summary

Issue #1514 (triage:po): Konzept für eine zentrale, gepflegte Übersicht, die beantwortet:
„Wenn ich Metrik/Signal X ändere — an welchen benannten Stellen, in welchen Kanälen, in
welcher FORM, in welcher REIHENFOLGE erscheint sie, und welcher Test bewacht das?"
Anlass: Bei #1475 (Hagel) brauchte es DREI Recherche-Runden, um 12 Ausgabeorte zu finden;
S5a ging mit 4 von 12 live, ohne dass Adversary oder Entwickler-Report es bemerkten.
Analyse-Phase reicht zunächst — Implementierung eines Registers wäre Folge-Issue.

## Kernbefund der Recherche (Explore-Agent, 2026-08-10)

- **Es gibt KEINE generische Metrik×Kanal-Matrix** — weder als Doku noch als Test.
  Vorhandene Ausgabeort-Tabellen sind metrikspezifisch (Gewitter: 9/12 Orte) oder
  aspektspezifisch (Legende: 4 Stellen, Namensform: 3 Formen, Ampel: 5 Stellen).
- **Der Metrik-Katalog (`src/app/metric_catalog.py`) hat 44 Nicht-Test-Konsumenten**
  in `src/`, `api/`, `scripts/` + Frontend + Go. `MetricDefinition` trägt ~30 Felder,
  viele davon definieren direkt Ausgabeformen (`col_key`/`col_label`, `compact_label`,
  `sms_code`, `alert_label`, `format_modes`, `trip_default_rank`, `selectable`, …).
- **Genau EIN Matrix-Wächter existiert:** `tests/tdd/test_channel_metric_matrix.py`
  (#1677 B) — alle Katalog-Metriken × 3 Trip-Kanäle (E-Mail-Spalten via
  `resolve_metric_col_order`, Telegram-rich via `render_for_channel`, SMS-Kurzform),
  aber nur Auswahl/Abwahl/Reihenfolge-Anwesenheit, keine Werte/Formen, Reihenfolge nur
  paarweise gegen einen festen Partner. Compare fehlt komplett.

## Related Files

### Single Source of Truth + Kaskade
| File | Relevance |
|------|-----------|
| `src/app/metric_catalog.py` | SSoT: `MetricDefinition` (Z. 28–90) mit ~30 Feldern; 26 Metriken; 44 Konsumenten |
| `src/app/models.py:649-671,762-814` | Kanal-Kaskade: `cascade_source_for_channel()` + `get_metrics_for_channel()` — EIN Ableitungsweg (#1677 DEC-2), 3 Ebenen (per_report → per_channel → global) |
| `src/output/renderers/channel_layout.py:75-110` | `render_for_channel()`, `CHANNEL_LIMITS`; Z. 87–89: `_NIGHT_SCALAR_IDS` als handkodierte Ausnahme |
| `src/app/loader.py:834-915,1326-1339,1538-1551` | Persistenz der Kanal-Layouts (Lesen 1×, Schreiben 2×) |

### Kanal-Renderer Trip
| File | Relevance |
|------|-----------|
| `src/output/renderers/email/helpers.py:302-315` | `resolve_metric_col_order()` — zentraler Knoten, speist `html.py:1021` UND `plain.py:144` |
| `src/output/renderers/email/outlook.py` | 3-Tages-Ausblick; `_THUNDER_TOKEN_RE` (Z. 38), dritte LOW/MED/HIGH-Übersetzung (Z. 193–198) |
| `src/output/renderers/sms_trip.py:114-120,170ff` | `SMS_SYMBOL_BY_METRIC` aus `get_sms_code()`; `_SMS_SYMBOL_GRAMMAR` (2 Ausnahmen); `SMS_MULTI_SYMBOLS_BY_METRIC` (1 Metrik → MEHRERE Kürzel — Katalog kann 1:n strukturell nicht) |
| `src/output/tokens/builder.py:17-29,47-66,78-99,112` | Handgepflegte Tabellen: `PRIORITY` (40+ Symbole), `POSITIONAL` (33), `DEFAULTS`, Gewitter-Grammatik-Konstanten |
| `src/output/renderers/narrow.py:346,530,588-597` | Telegram; 3 hartkodierte Gewitter-Sonderzweige |
| `src/output/renderers/compact_summary.py:242,567-600` | `_format_thunder()` — einzige Metrik mit eigener Methode |
| `src/output/renderers/trip_report.py:29,301` | Orchestrierer; SMS-Aktivierungs-Gate |
| `src/services/trip_command_processor.py:161,228,627-632` | `_DRILLDOWN_METRICS`: genau 3 Metriken Telegram-drilldown-fähig, als Regex eingefroren |

### Kanal-Renderer Compare (die „2 komplett neuen Kanäle" aus #1514)
| File | Relevance |
|------|-----------|
| `src/output/renderers/compare_metric_catalog.py:51` | Compare-Katalog aus zentralem Katalog ABGELEITET (nicht getippt) |
| `src/output/renderers/email/compare_html.py:294,384-406,428-449` | `CV2_METRICS`, `_HOUR_FMT_OVERRIDES` (10) + `_HOUR_SEV_OVERRIDES` (3), Stundentabelle via `hourly_selectable_metric_ids()` |
| `src/output/renderers/comparison.py:55-110` | `_DAILY_PLAIN_ROWS`/`_PLAIN_ROWS`: je Zeile handgetipptes Tupel (ID, Label, Format-Lambda) — Beleg-Instanz Doppel-Quelle #1356 |
| `compare_hourly_metric_ids.py` / `compare_metric_ids.py` / `compare_outlook_metric_ids.py` | ID-Auswahl-Module, Neuformat `{"metric_id","aggregation"}` |

### Alarme + amtliche Warnungen (Sonderstrecken)
| File | Relevance |
|------|-----------|
| `src/output/renderers/alert/render.py:10,35,448,549,617` | Generisch aus Registry (Betreff/Mail/Telegram/SMS), ABER `_HANDLED_UNITS`-Whitelist: fremde Einheit → stiller Ersatzpfad. KEIN Vollständigkeits-Wächter |
| `src/output/tokens/hazard_symbols.py` + `api/routers/config.py:66` | Amtliche Warnungen: eigenes Symbolregister NEBEN dem Metrikkatalog |
| `src/services/weather_change_detection.py` | Alarm-Auswertungskette (5 Katalog-Importe) |

### Datenkanäle NEBEN dem Katalog
| File | Relevance |
|------|-----------|
| `src/services/trip_report_scheduler.py:1665-1761` | `_build_thunder_forecast()`: eigener Datenkanal ohne Katalogeintrag/Editor-Auswahl, speist ≥3 Kanäle (Fernwirkung, #1475 Lücke 3) |
| `notification_service.py:71,323` → `trip_report.py` → `sms_trip.py:616,682-700` + `email/html.py:962,1312` | Durchreiche-Kette des `thunder_forecast`-Dicts |

### Editor / API (Anzeige-Seite der Matrix)
| File | Relevance |
|------|-----------|
| `api/routers/config.py:74-110` | `GET /api/metrics`: 15 Katalogfelder ans Frontend, Filter `selectable` |
| `frontend/.../WeatherMetricsTab.svelte:233,411,755-771` + `channelMetricLayouts.ts` | Trip: Reihenfolge JE KANAL (`channel_layouts`) |
| `frontend/.../compareWizardState.svelte.ts:31` + `compareEditorSave.ts:117-126` | Compare: EINE globale Liste (`wiz.activeMetricKeys`) — **struktureller Bruch**, dokumentiert als Known Limitation in `docs/specs/modules/fix_1677_sms_reihenfolge.md` (Z. 238–246); Kanal-Tabs für Compare = offene PO-Entscheidung |

## Existing Patterns

- **Ableitungs-Muster (gut):** `SMS_SYMBOL_BY_METRIC` aus `get_sms_code()` + Ratsche;
  `compare_metric_catalog.py` aus zentralem Katalog abgeleitet; Kaskade mit EINEM
  Ableitungsweg (`cascade_source_for_channel`). → „Register + Drift-Ratsche" ist das
  im Projekt etablierte Muster gegen Doppel-Quellen.
- **Matrix-Test-Muster (#1677 B):** parametrisiert über `get_all_metrics()` × Kanäle —
  erweiterbar um Dimensionen (Form, Compare-Kanäle).
- **Vorbild für Ort-Vollständigkeit EINER Metrik:** `tests/tdd/test_thunder_low_output_channels.py`
  (6 Renderpfade für eine Metrik) — strukturell bestes Vorbild laut Recherche.
- **Einziger Wirkungs-Vollständigkeitstest:** `tests/unit/test_compare_hourly_catalog_columns.py:122`
  (jede Katalogmetrik hat Compare-Stundenspalte, benannte Ausnahmen).
- **Doku-Muster:** `docs/features/gewitter-gesamtkonzept.md` §8 (Ort-Tabelle mit Fundstelle);
  `docs/context/feat-1585-thunder-probability.md:97-113` unterscheidet als EINZIGES Dokument
  *generisch über metric_id* vs. *einzeln zu verdrahten* — diese Unterscheidung ist für
  #1514 zentral. ADR-0042 (Namensform × Platzgrenze) liefert die Form-Taxonomie der Labels.

## Bekannte unbewachte Flächen (aus der Recherche, Kandidaten fürs Konzept)

1. Alle Metriken × **Alarm-Renderer** — alarmfähiger Katalogeintrag ohne Alarm-Mail-Zeile fällt nirgends auf
2. Alle Metriken × **Ausblick-Tabelle** (`outlook_columns`, Trip- UND Compare-Mail) — größte unbewachte Fläche
3. Alle Metriken × **Kurzform-/Compact-Mail** (`email/compact.py`, `_render_mobile_compact_rows`)
4. Compare-Übersichtstabelle: **Zellwert** je Metrik (nur Zeilen-Existenz bewacht)
5. **Reihenfolge** in allen Kanälen außer E-Mail/Telegram-rich; Compare-Plain nutzt Nutzer-Reihenfolge nur als Sichtbarkeitsfilter (#1356)
6. **Nicht-wählbare Register-Metriken** (z.B. `temperature_cold` mit `sms_code`) fallen aus jedem Vollständigkeitstest, weil alles über `get_all_metrics()` (= selectable) iteriert
7. **Telegram-Kurzform** als eigener Ausgabeort ohne Matrix-Eintrag
8. **Einheiten/Nachkommastellen je Kanal** unbewacht außer Compare-Legende
9. **Frontend** ohne Metrik×Kanal-Matrix
10. **Trip-SMS liest die Kaskade nicht** (`format_sms`, dokumentiert in `fix_1575_channel_metric_selection.md`) — Kanal hängt teilweise neben der Konfiguration

## Dependencies

- Upstream (Bausteine, die das Konzept einsammelt): #1677 (Matrix-Test, `cascade_source_for_channel`),
  #1660/#1435 (`sms_code`-SSoT + Ratsche), #1475 (12-Orte-Belege), ADR-0042 (Namensformen),
  Memory `reference_weather_metric_has_many_output_locations` (9-Punkte-Checkliste)
- Downstream: jede künftige Metrik-/Signal-Arbeit (Epic #1419 Gewitter, Epic #1372 Metrik-Zielbild);
  offene PO-Entscheidung Compare-Kanal-Tabs; Folge-Issue #1689 (format_sms-Merge)

## Existing Specs / Doku

- `docs/reference/api_contract.md` §15 — vollständigste Feldreferenz (`compact_label` fehlt dort)
- `docs/reference/sms_format.md` v2.23 — gepflegtes SMS-Token-Register (Muster für „Register-Doku")
- `docs/reference/renderer_email_spec.md` — E-Mail-Vollformat („Metric Display Contract")
- `docs/features/gewitter-gesamtkonzept.md` §8 — beste vorhandene Ort-Tabelle (metrikspezifisch)
- Veraltet/irreführend: `docs/specs/modules/telegram_output.md` (Signal-Referenzen!),
  `output_channel_renderers.md` (kennt Compare/Kaskade nicht), `layout_tab_*.md` (vor #1575)

## Risks & Considerations

- **Wartungslast vs. Nutzen** (Issue-Kernfrage): Ein reines Dokument veraltet wie
  `output_channel_renderers.md`; ein maschinenlesbares Register braucht Ratschen,
  vergrößert aber das Gate-Budget (Regel-Budget-Pflicht: Prüfdatum oder Ersatz!).
- **1:n-Strukturbruch:** Eine Metrik kann MEHRERE SMS-Kürzel (Grammatik-Klassen) und
  mehrere Darstellungsformen haben — der Katalog bildet 1:1 ab. Ein Register muss die
  Form-Dimension (Aggregation, `format_mode`, Token-Grammatik) explizit modellieren
  oder bewusst ausklammern.
- **Sonderstrecken ohne Katalogbezug:** `thunder_forecast`-Datenkanal, Alarm-Kurznachrichten,
  Hazard-Symbole, System-Blöcke der Kurzform (DEC-4), `TokenLine.filter_for_subject` (Stub),
  Wintersport-Block — eine Übersicht, die nur Katalog-Konsumenten erfasst, wiederholt
  exakt den #1475-Fehler.
- **Architektur-Mismatch Trip/Compare-Editor** ist eine PO-Entscheidung, die das Konzept
  vorbereiten, aber nicht vorwegnehmen darf.
- **Adversary-Blindstelle:** Berichte behaupteten zweimal unbelegt Vollständigkeit —
  das Konzept sollte definieren, wie „vollständig" MESSBAR wird (Leitfrage je Zelle:
  welcher Test bewacht das?).

## Analysis

### Type
Feature (Konzept-Auftrag, triage:po) — Liefer-Artefakt ist ein Referenzdokument mit
Entscheidungsvorlage, KEIN Produktivcode in diesem Workflow.

### Strategische Bewertung (Plan-Agent, 2026-08-10)

**Empfehlung: Option C (Hybrid).** Den bestehenden Matrix-Test
`tests/tdd/test_channel_metric_matrix.py` (#1677 B) schrittweise um Achsen erweitern
(Alarm-Renderer, Ausblick-Tabelle, Compare, Formen), plus EIN kompaktes Referenzdokument
NUR für das, was Tests nicht ausdrücken können (Sonderstrecken, Datenkanäle,
Architektur-Begründungen). Alles Prüfbare gehört in Assertions, nicht in Prosa.

Verworfen:
- **Option A (reines Dokument):** veraltet nachweislich genau in diesem Projekt
  (`output_channel_renderers.md` kennt Compare/Kaskade nicht; `telegram_output.md`
  referenziert noch Signal). Nutzen bei der nächsten Metrik-Änderung ≈ null.
- **Option B (zweites maschinenlesbares Register neben dem Katalog):** verstößt gegen
  Regel-Budget (mehrere NEUE Gates) und wiederholt das Doppel-Quellen-Muster (#1356);
  Sonderstrecken wie `thunder_forecast` sind durch KEIN Katalog-Register erfassbar —
  ein „vollständiges" Register wäre Fiktion.

Regel-Budget-Argument für C: jede neue Achse ist **Erweiterung eines bestehenden,
bereits budgetierten Gates** (#1677 B), kein neues Pflicht-Gate.

### Kernentscheidungen der Empfehlung

1. **Form-Dimension = eigene Achse, nicht in die Hauptmatrix.** Die Matrix ist
   1 Zeile = 1 Metrik; die Symbol-Grammatik ist 1:n (`SMS_MULTI_SYMBOLS_BY_METRIC`).
   `format_modes`/`default_format_mode` (1:1-Katalogfelder) können dagegen in die
   Hauptmatrix. Eigener kleiner Wächter iteriert über Grammatik-Klassen
   (`PRIORITY`/`POSITIONAL` in `tokens/builder.py`), nicht über Metrik-IDs.
2. **Kein Gewitter-Pilot — volle 26 Metriken je neuer Achse.** Gewitter ist bereits
   der bestbewachte Fall; der teure Teil ist die Assertion-Logik pro Zelle, nicht die
   Metrik-Anzahl (Parametrisierung ist billig). Benannte Ausnahmen, wo strukturell
   keine Zelle existiert (Muster: `_NIGHT_SCALAR_IDS`-Ausnahmen im Bestand).
3. **Anti-Veraltung, drei Bausteine (alle etabliert):** (a) Drift durch Parametrisierung
   über den Katalog (automatisch), (b) NEU: kleiner Test über das volle `_METRICS`
   statt `get_all_metrics()` — schließt die strukturelle Blindstelle, dass
   `selectable=False`-Metriken (z.B. `temperature_cold` MIT `sms_code`) aus JEDER
   Vollständigkeitsprüfung fallen (`metric_catalog.py:695`), (c) `doc-compliance-test`
   für die Prosa-Teile (Muster: `test_adr_index_drift.py`). Generierte Doku aus Code:
   verworfen (Wartungslast > Nutzen).

### Affected Files (dieses Workflows)
| File | Change Type | Description |
|------|-------------|-------------|
| `docs/reference/metric_output_matrix.md` | CREATE | Konzept-/Referenzdokument (~250–400 Z.): Dimensionen, unbewachte Flächen mit Priorität, Sonderstrecken-Katalog, Entscheidungsvorlage |
| `docs/context/konzept-1514-metrik-ausgabeorte.md` | MODIFY | dieses Dokument (Recherche + Analyse) |

### Scope Assessment
- Files: 1 neu (Doku), 0 Code
- Estimated LoC: ~250–400 Doku-Zeilen (zählt nicht ins LoC-Limit: `docs/`)
- Risk Level: LOW (reine Doku in diesem Workflow; Risiken liegen in den Folge-Scheiben)

### Folge-Scheiben (Empfehlung, je eigenes Issue)
1. Alarm-Renderer × alle `_METRICS` (höchstes Risiko: `_HANDLED_UNITS`-Whitelist weicht still aus)
2. Ausblick-Tabelle Trip+Compare (größte unbewachte Fläche)
3. Nicht-wählbare Register-Metriken (klein, schließt Blindstelle aller Matrix-Tests)
4. Kurzform-/Compact-Mail + Telegram-Kurzform als eigener Matrix-Ort
5. Compare-Zellwert-Vollständigkeit
6. Form-Wächter (Grammatik-Klassen) — parallel möglich
7. Reihenfolge-Wächter jenseits E-Mail/Telegram-rich — NACH PO-Entscheidung Compare-Kanal-Tabs
8. Optional (PO): Compare-Kanal-Tabs Frontend (eigenes größeres Vorhaben)

### Open Questions (PO-Entscheidungsvorlage in der Spec)
- [ ] Compare-Kanal-Tabs ja/nein (struktureller Bruch `wiz.activeMetricKeys` vs. `channel_layouts`)?
- [ ] Form-Dimension als eigene Achse (Empfehlung) bestätigen?
- [ ] Folge-Scheiben als benanntes Epic bündeln oder Einzel-Issues?
