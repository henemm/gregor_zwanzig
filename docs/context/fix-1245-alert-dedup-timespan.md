# Context: fix-1245-alert-dedup-timespan

## Request Summary
Amtliche Warnungen derselben Region+Gefahr, aber mit **unterschiedlichen Gültigkeitszeiträumen**, kollabieren in `dedupe_official_alerts` zu einer einzigen Warnung — der zweite Zeitraum verschwindet still. Folge: Die Mail meldet einen zu kurzen Warnzeitraum, der Empfänger unterschätzt die Dauer der Gefahr (Issue #1245, `type:bug`, `priority:medium`).

## Reproduzierbarer Fall (aus dem Issue)
Météo-France liefert für dieselbe Region zwei Hitzewarnungen:
- 13.07. 04:00–22:00 UTC
- 13.07. 22:00 – 14.07. 22:00 UTC

Beide: gleiches `region_label`, gleicher `hazard` (`extreme_heat`), gleiche Stufe. `dedupe_official_alerts` gruppiert nach `((dedup_id|region_label|label), hazard)` — der Zeitraum ist **nicht** Teil des Schlüssels. Beide fallen auf denselben Key; bei Stufengleichstand überlebt das erste Vorkommen. Die zweite Periode fällt ersatzlos weg. Mail sagt „Hitze bis Di 14.07. 00:00", amtlich gewarnt ist bis **Mi 00:00**.

## Related Files
| Datei | Zeile | Relevanz |
|---|---|---|
| `src/output/renderers/alert/official_alerts.py` | 254–298 | **Bug-Ursache** `dedupe_official_alerts`: Key `(ident, hazard)` ohne Zeitraum (Z.290), nur max-level überlebt (Z.295) |
| `src/output/renderers/alert/official_alerts.py` | 301–376 | `_bundle_by_hazard_level`: nimmt Zeitraum in Key (Z.364 `key=(hazard,level,label,valid_from,valid_to)`), läuft aber **nach/stromab** der bereits verlustbehafteten Dedup |
| `src/services/official_alerts/models.py` | 14–33 | `OfficialAlert`-Dataclass (frozen); Zeitraum = `valid_from`/`valid_to` (Optional[datetime], Z.24–25), Identität `dedup_id`(33)/`region_label`(27)/`label`(23), `hazard`(21)/`level`(22) |
| `src/output/renderers/alert/official_alerts.py` | 508–526 | `_format_validity` — Zeitraum-Text „Fr 10.07. · 06:00–20:00" |
| `src/output/renderers/alert/official_alerts.py` | 400–416 | `render_official_alert_notice_plain` — Konsument + „Gültig:"-Zeile |

## Konsumenten von `dedupe_official_alerts` (alle 8 laufen durch die Fehlerstelle)
| Aufrufer | Datei:Zeile | Nutzt `_bundle_by_hazard_level`? | Bemerkung |
|---|---|---|---|
| `render_official_alert_notice_plain` | `official_alerts.py:400` | Nein | Plain-Notice, rendert „Gültig:"-Zeile je Rest-Alert |
| `collect_trip_alert_entries` | `official_alerts.py:439` | Nein | Badge/plain-Trip-Renderer |
| `build_official_alert_notices` | `official_alerts.py:1615` | **Ja** | Trip-Standalone-Alarm |
| `build_compare_official_alert_notices` | `official_alerts.py:1685` | **Ja** | Compare-Standalone-Alarm |
| Compare-Badge-Streifen | `compare_html.py:263–268` | Nein | Dünner Wrapper |
| HTML-Trip-Warnblock | `html.py:36,1433–1450` | **Nein** | Zeitraum geht hier auch ohne zweite Stufe verloren |
| Compare-Alarm-Trigger | `compare_official_alert.py:29,151–169` | Nein | Neu/Eskalation, Zustands-Key ohne Zeitraum |
| Trip-Alarm-Trigger | `trip_alert.py:929–939` | Nein | Eskalations-Key ohne Zeitraum |

## Herkunft der Alerts (welche Quellen tragen Zeiträume)
| Quelle | Datei:Zeile | Zeitraum gesetzt? | Bug-relevant |
|---|---|---|---|
| Météo-France Vigilance | `vigilance.py:139–147` | **Ja** (mehrere `period`-Blöcke → mehrere Alerts gleicher Gefahr) | **Ja — Ur-Reproduktion** |
| MeteoAlarm (CAP) | `meteoalarm.py:189–197` | **Ja** (onset/expires → valid_from/valid_to) | Ja |
| GeoSphere Austria | `geosphere_warn.py:125–131` | **Ja** | Ja |
| Météo-France Waldbrand | `meteo_forets.py:113–119` | Nein | — |
| Präfektur Massiv-Sperre | `massif_closure.py:66–68` | **Nein**, setzt aber `dedup_id` | Non-Regression-Anker |

## Existing Patterns
- **Zwei-Stufen-Verdichtung:** (1) Identitäts-Dedup `dedupe_official_alerts` (kanonisch, speist ALLE Pfade), (2) `_bundle_by_hazard_level` (nur Warn-Sektion-Notice-Builder). Die zweite Stufe hält den Zeitraum bereits als Schlüssel — das Muster „Zeitraum in den Schlüssel" existiert also schon und ist Adversary-gehärtet (F003).
- **Namespace-getrennte Identität:** `("id",dedup_id)` / `("region",region_label)` / `("label",label)` — ein zufällig gleicher String über Namespaces hinweg kollabiert nicht (F002).
- **Massiv-Eskalation:** stabile `dedup_id` konstant über alle Stufen → 3→4 kollabiert zum höchsten Level (#1172/#1200/#1217/#1218). Massiv-Sperren tragen **keinen** Zeitraum.

## Dependencies
- **Upstream:** `OfficialAlert` (frozen dataclass) mit `valid_from`/`valid_to`; Provider-Adapter setzen diese.
- **Downstream:** 8 Renderer-/Trigger-Pfade (s.o.) — Mail-HTML, Plain, SMS, Badges, Compare-Streifen, sowie **Alarm-Trigger** (Neu/Eskalation-Zustandslogik). Änderung an der Dedup-Semantik wirkt auf alle.

## Existing Specs
- `docs/specs/modules/issue_1172_official_alert_dedup_info.md` — Ur-Spec der Dedup
- `docs/specs/modules/issue_1217_1218_mail_alert_dedup.md` — Konsolidierung / `dedup_id`
- `docs/specs/modules/issue_1200_alert_segment_reference.md` — Segment-ID-Vereinigung
- `docs/specs/modules/issue_1035_*` (Vigilance), `issue_1086_meteoalarm_source.md`, `issue_1037_official_alerts_massif_closure.md`
- **Lücke:** Zu #1238/#1239 (`_bundle_by_hazard_level`, AC-13/AC-14) existiert **keine** Spec-Datei — die Historie steht nur in Docstrings (Z.271–358) und Tests.

## Testabdeckung
- `tests/tdd/test_official_alert_warn_section.py:423` `test_ac13_different_validity_periods_not_bundled` — **prüft aber zwei verschiedene `region_label`** → `dedupe_official_alerts` trennt schon über `ident`; der eigentliche Bug-Fall (GLEICHE Region/Identität + unterschiedlicher Zeitraum) ist **ungetestet**.
- `tests/tdd/test_official_alert_warn_section.py:561` `test_ac14_massif_escalation_still_collapses_to_highest_level` — Non-Regression-Anker.
- `tests/tdd/test_issue_1172_...py:43–61`, `test_mail_alert_dedup.py:318`, `test_alert_segment_reference.py:115`.

## Risks & Considerations
1. **Non-Regression Massiv-Eskalation (#1172/#1200/#1217/#1218):** `dedup_id`-Warnungen (Massiv) müssen weiter über alle Stufen kollabieren (3→4). Sie tragen keinen Zeitraum → wenn die Lösung den Zeitraum **nur im `region_label`/`label`-Namespace** in den Schlüssel nimmt und den `dedup_id`-Namespace zeitraum-invariant lässt, bleibt die Eskalation strukturell geschützt. Ist eine bewusste Design-Entscheidung, keine Nebenwirkung.
2. **Offene Soll-Semantik (PO-Entscheidung in Phase 2):** getrennt anzeigen **vs.** aneinander anschließende/überlappende Zeiträume zu EINEM zusammenhängenden Intervall verschmelzen. Der Ur-Fall (04:00–22:00 + 22:00–…) schließt exakt an → Merge ergäbe „bis Mi 22:00" in einer Karte.
3. **Blast Radius:** Alle 8 Konsumenten betroffen, darunter Alarm-**Trigger** (Neu/Eskalations-Zustand). Ändert sich die Anzahl der entdoppelten Warnungen, kann sich das Trigger-Verhalten (neue Alarme) verschieben — muss in der Spec bedacht werden.
4. **Interval-Merge-Kanten (falls Merge gewählt):** „schließt an" = exakt gleiche Grenze? Überlappung? Toleranz? Zeitzonen (alles UTC-Vergleich, Rendering lokal). Unterschiedliche Stufe → nicht mergen (bleibt Mixed-Level-Pfad).
5. **`_bundle_by_hazard_level` würde bei Option „getrennt" die zwei getrennten Zeiträume NICHT bündeln** (unterschiedlicher Schlüssel) → zwei Karten für dieselbe durchgehende Gefahr; kosmetisch, aber korrekt.

## Analysis

### Type
Bug (Bestandsverhalten, gefunden bei Staging-E2E zu #1238/#1239).

### PO-Entscheidung (2026-07-15, Semantik)
**„Zwei getrennte Warnungen zeigen"** — jede gemeldete Periode bleibt eine eigene Warn-Karte. **KEIN** Interval-Merging bei Anschluss. Konsequenz: Der Fix reduziert sich auf „Zeitraum wird unterscheidungsrelevant im Dedup-Schlüssel". Bei echter zeitlicher Lücke, unterschiedlicher Stufe oder unterschiedlichem Zeitraum bleiben Einträge getrennt; nichts verschwindet still.

### Technical Approach (Fix-Lokation: `dedupe_official_alerts`, kanonische Stufe)
Der Fix gehört in `dedupe_official_alerts` (Z.254–298), NICHT in `_bundle_by_hazard_level` — nur die kanonische Stufe speist alle 8 Konsumenten (inkl. HTML-Warnblock und Trigger, die `_bundle_by_hazard_level` nicht durchlaufen).

Dedup-Schlüssel künftig **namespace-abhängig**:
- **`dedup_id`-Namespace (Massiv-Sperren):** unverändert `(("id",dedup_id), hazard)` — **zeitraum-invariant**. Schützt AC-14 Massiv-Eskalation 3→4 strukturell (stabile ID = „dieselbe Sperre, nur Stufe aktualisiert"; Massiv trägt ohnehin keinen Zeitraum).
- **`region_label`/`label`-Namespace (Vigilance/MeteoAlarm/GeoSphere):** `(ident, hazard, valid_from, valid_to)` — **Zeitraum unterscheidet**. Folgen:
  - unterschiedlicher Zeitraum → getrennte Einträge (Bugfix);
  - gleicher Zeitraum + unterschiedliche Stufe → max-level-Kollaps (echte Eskalation am selben Zeitraum, unverändert);
  - beide-`None`-Zeitraum → max-level-Kollaps (zeitlose Warnungen wie Waldbrand, unverändert);
  - unterschiedliches label/id → schon heute getrennt (#1134 AC-2a, unberührt).

### Challenger-Befunde (analysis-challenger, VERDICT: NEEDS REVIEW → Scope erweitert)
Root Cause **korrekt**, Fix-Ort **korrekt**. Zwei bestätigte Blocker + eine Vereinfachung:

- **B1 — Trigger-State-Key-Kollision (BESTÄTIGT, Blocker):** `trip_alert.py:935,952` + `compare_official_alert.py:161,179` bauen `official_alert:{region_label}:{hazard}` ohne Zeitraum. Nach dem Fix liefern zwei Perioden gleiche Region+Gefahr → last-write-wins im Zustand: `_record_official_alert_state`/`_record_state` überschreiben; `check_official_alert_triggers`/`_detect` lesen für beide denselben `prev` → eine echte neue Periode wird als „nicht neu" unterdrückt (Standalone-Alarm feuert nie) ODER Flapping. **MUSS im selben Fix repariert werden.**
- **B2 — Vier stumme Renderer (BESTÄTIGT, Blocker):** `render_official_alerts_html` (Z.154–210, Compare-Badge via `compare_html.py:539,556`) und `render_official_alerts_plain` (Z.213–221, Compare-Plain `comparison.py:118`, Trip-Plain `plain.py:203`, Trip-Compact `compact.py:160`) zeigen keine Uhrzeit → zwei Perioden = zwei textgleiche Einträge/Badges (wirkt wie Duplikat).
- **Vereinfachung:** `(valid_from, valid_to)` **einheitlich in alle drei Namespaces** statt Sonderfall-Verzweigung. Massiv (`dedup_id`) setzt nie einen Zeitraum (`massif_closure.py:66–69` → immer `None`/`None`) → kein Verhaltensunterschied, aber kein Sonderfall-Code und keine künftige `dedup_id`-mit-Zeitraum-Falle. **Übernommen.**
- **Zusatzfund (kohärent mitbehoben, s.u.):** Massiv-State-Key ist heute für JEDES Massiv identisch `official_alert:None:access_ban` (`region_label=None`) → zwei verschiedene Massive überschreiben sich schon jetzt im Zustand. Wird durch die Invariante „State-Key = Dedup-Identität" (inkl. `dedup_id` via `ident`) automatisch mitbehoben — mit eigenem AC + Test.
- **Test-Fixture-Warnung:** `test_official_alert_warn_section.py:568–574` (test_ac14) nutzt Default `vf=FR_FROM/vt=FR_TO` statt produktionsrealer `None`/`None`. Neuer Massiv-Test referenziert die realistische Fixture `test_mail_alert_dedup.py:202–232` (`_massif_alert`).

### PO-Entscheidung 2 (2026-07-15, Sichtbarkeit)
**„Zeiträume ergänzen"** — die vier stummen Renderer erhalten einen kompakten Zeitraum-Zusatz, sodass zwei Perioden unterscheidbar sind (Badge: „Extreme Hitze · Mo 04–22"; Kurzliste: „… (Mo 04:00–22:00)").

### Affected Files (with changes)
| Datei | Change Type | Beschreibung |
|---|---|---|
| `src/output/renderers/alert/official_alerts.py` | MODIFY | (a) `dedupe_official_alerts` Z.254–298: `(valid_from,valid_to)` einheitlich in Schlüssel; (b) `render_official_alerts_html` + `render_official_alerts_plain`: kompakter Zeitraum-Zusatz |
| `src/services/trip_alert.py` | MODIFY | State-Key Z.935,952 spiegelt Dedup-Identität (inkl. Zeitraum) |
| `src/services/compare_official_alert.py` | MODIFY | State-Key Z.161,179 analog |
| `tests/tdd/test_official_alert_warn_section.py` (o. neue Modul-Suite) | CREATE/MODIFY | RED-Tests: (1) gleiche Identität + versch. Zeitraum → 2 Einträge; (2) Trigger 2 Perioden → beide unabhängig neu/eskaliert + gespeichert; (3) stummer Renderer mit 2-Perioden-Fixture zeigt Zeit; (4) Massiv-Eskalation (None/None) kollabiert weiter |

### Scope Assessment
- Files: 3 Quellcode + 1–2 Testdateien
- Estimated LoC: +60–100 (über LoC-Limit 250? Nein — voraussichtlich darunter; Tests/Docs zählen nicht)
- Risk Level: **MEDIUM-HIGH** (kanonische Funktion, 8 Konsumenten, Alarm-Trigger-Zustand)

### Invariante (Kern des Fixes)
**Der Alarm-Zustands-Key spiegelt exakt die Dedup-Identität einer Warnung `(ident, hazard, valid_from, valid_to)` wider.** Aus dieser einen Invariante folgen B1-Fix und der Massiv-Zusatzfund gemeinsam — genau das Auseinanderdriften von Dedup-Kardinalität und State-Key war die Blocker-Ursache.

### Open Questions
- [x] Trigger-Key-Kollision → bestätigt, im Scope (B1)
- [x] Massiv-Non-Regression → `dedup_id` trägt nie Zeitraum; einheitliche Regel unschädlich; Test auf None/None
- [x] Merge-freie Semantik → identischer Zeitraum + gleiche Stufe = Dublette, kollabiert weiter (bestehende `level >`-Logik greift)
- [x] Sichtbarkeit stumme Renderer → PO: Zeiträume ergänzen
