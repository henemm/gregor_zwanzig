# Context: fix-1451-warn-region-dedup

## Request Summary
Issue #1451: In der Übersichtszeile „Amtliche Warnungen" der Vergleichs-Mail fallen zwei
echte amtliche Warnungen derselben Gefahrenart aus **verschiedenen Regionen** (z.B.
Haute-Corse + Corse-du-Sud, beide "Hitze" Stufe 3) fälschlich zu einem Kürzel zusammen.
Die Region muss in die Kollaps-Entscheidung eingehen, ohne den ursprünglichen #1314-Fix
(zwei Warnungen derselben Region mit unterschiedlichem Zeitraum -> ein Kürzel) rückgängig
zu machen.

## Ursache (bereits im Ticket-Kommentar nachgemessen, Gegenprobe geführt)
`d7c2ea8f` (fix #1314 S6) fügte in `_render_warn_cell` einen `seen`-Set über
`visual_key = (short, bg, fg)` ein. `short` kommt aus `_warn_short(alert)` und hängt
NUR an `alert.hazard`, `bg`/`fg` NUR an `alert.level`. Das Gebiet (`region_label`) geht
nirgends ein -> zwei echte Warnungen gleicher Art+Stufe aus verschiedenen Regionen sind
für diesen Schlüssel ununterscheidbar.

## Related Files
| File | Relevance |
|------|-----------|
| `src/output/renderers/email/compare_html.py:392-437` | `_warn_short`, `_dedup_alerts` (Wrapper um kanonische Quelle), `_render_warn_cell` — hier liegt der Fehler (Zeile ~424-436, `seen`-Set ohne Region) |
| `src/output/renderers/alert/official_alerts.py:294-339` | `dedupe_official_alerts` — kanonische Dedup-Quelle (#1217/#1218/#1245), Identität `dedup_id > region_label > label`, Schlüssel zusätzlich `hazard, valid_from, valid_to`. Läuft bereits VOR `_render_warn_cell` (über `_dedup_alerts`), löst das Problem aber nicht, weil sie Perioden bewusst getrennt hält — die Übersicht zeigt aber keine Periode. |
| `src/services/official_alerts/models.py:15-33` | `OfficialAlert`-Datenklasse: Felder `hazard, level, label, valid_from, valid_to, region_label, dedup_id` |
| `tests/tdd/test_mail_alert_dedup.py` | Bestehende Kern-Test-Suite für diesen Bereich. `test_ac5_same_hazard_different_region_not_collapsed` (Zeile 185) ist der rote Wächter für genau diesen Bug. `test_ac7_escalating_massif_closure_dedups_in_briefing` (Zeile 214) prüft die Nachbar-Invariante (eskalierende Massiv-Sperre = 1 Badge) — betrifft den Pro-Ort-Streifen (`render_official_alerts_html`), nicht direkt `_render_warn_cell`, ist aber der Grund, warum keine simple Rückbau-Lösung gewählt werden darf. |

## Existing Patterns
- Identitäts-Präzedenz `dedup_id > region_label > label` ist der etablierte Weg, um
  "gleiche Sache" von "verschiedene Sache" zu unterscheiden (siehe `dedupe_official_alerts`
  Docstring). Der Fix in `_render_warn_cell` sollte dieselbe Präzedenz für den
  Kollaps-Schlüssel verwenden, statt eine neue Logik zu erfinden.
- Massiv-Sperren (`dedup_id` gesetzt, `region_label=None`) werden bereits VOR
  `_render_warn_cell` durch `_dedup_alerts`/`dedupe_official_alerts` auf einen
  Repräsentanten (höchste Stufe) reduziert — die Eskalations-Invariante (AC-7) ist
  unabhängig vom hier zu ändernden `visual_key` bereits sichergestellt.

## Dependencies
- Upstream: `_dedup_alerts` (Zeile 407) liefert die Eingabe für `_render_warn_cell`
  (Zeile 520, 849) — bereits nach kanonischer Identität dedupliziert, aber mit
  Zeitraum in der Identität, daher können zwei Perioden derselben Region durchkommen.
- Downstream: keine — `_render_warn_cell` ist Blatt-Funktion, rendert nur HTML-Chips.

## Existing Specs
Keine dedizierte Modul-Spec für `compare_html.py`/Warn-Kürzel; Verhalten ist über
`tests/tdd/test_mail_alert_dedup.py` (AC-Nummerierung dort) spezifiziert.

## Risks & Considerations
- **Nicht** den `seen`-Set einfach entfernen (regressiert #1314: zwei Perioden derselben
  Region zeigen wieder zwei identische Chips ohne erkennbaren Unterschied).
- Der Fix muss die Region (bzw. `dedup_id`/`region_label`/`label`-Präzedenz) in den
  Kollaps-Schlüssel aufnehmen, Zeitraum aber weiterhin ignorieren (Übersicht zeigt keine
  Periode).
- Der Klartext-Teil der Mail und der Pro-Ort-Streifen sind laut Commit-Message von
  #1314 unberührt und zeigen bereits beide Warnungen korrekt — nicht anfassen,
  nur `_render_warn_cell` betroffen.
- Bestehender Kern-Test `test_ac5_same_hazard_different_region_not_collapsed` ist der
  Bug-Beweis (rot vor Fix). Zusätzlich: Gegenprobe, dass eine #1314-Regression
  (zwei Perioden derselben Region -> weiterhin 1 Chip) nicht eintritt, sollte als Test
  ergänzt/bestätigt werden.

## Analysis

### Type
Bug — nutzersichtbares Fehlverhalten (unterschlagene amtliche Warnung).

### Affected Files (with changes)
| File | Change Type | Description |
|------|-------------|-------------|
| `src/output/renderers/email/compare_html.py` | MODIFY | `_render_warn_cell`: `visual_key` um Regions-/Identitätskomponente erweitern (`region_ident = alert.dedup_id or alert.region_label or alert.label`, dieselbe Präzedenz wie `dedupe_official_alerts`); Docstring-Kommentar ergänzen |
| `tests/tdd/test_mail_alert_dedup.py` | (bereits vorhanden, kein Change nötig) | `test_ac5_same_hazard_different_region_not_collapsed` (Zeile 185) ist der rote Bug-Beweis; wird durch den Fix grün. AC-7 (Massiv-Eskalation) läuft als Regressionsschutz mit. |

### Scope Assessment
- Files: 1 (Produktivcode) + bestehende Testdatei (kein neuer Code, nur Ausführung)
- Estimated LoC: ~2-3 geänderte Zeilen
- Risk Level: LOW — isolierte, gut gekapselte Änderung ohne Signaturänderung; per Plan-Agent-Review gegengecheckt, keine weiteren Fundstellen mit demselben Muster (grep bestätigt: `visual_key`/`seen` nur in `_render_warn_cell`); Pro-Ort-Streifen (`render_official_alerts_html`/`_bundle_by_hazard_level`) sammelt Region bereits korrekt als Aggregat, kein analoger Bug dort.

### Technical Approach
`visual_key` in `_render_warn_cell` von `(short, bg, fg)` auf `(short, bg, fg, region_ident)`
erweitern, mit `region_ident = alert.dedup_id or alert.region_label or alert.label` — exakt
dieselbe Identitäts-Präzedenz wie in `dedupe_official_alerts` (#1217/#1218/#1245). Damit
kollabieren weiterhin zwei Perioden DERSELBEN Region/Identität (ursprünglicher #1314-Zweck),
aber unterschiedliche Regionen bleiben sichtbar getrennt. AC-7 (eskalierende Massiv-Sperre)
bleibt unberührt, weil diese bereits vor `_render_warn_cell` durch `_dedup_alerts` auf einen
Repräsentanten reduziert wird — der `seen`-Mechanismus greift dort praktisch gar nicht mehr.

### Dependencies
Keine neuen Abhängigkeiten. Nutzt vorhandene Felder von `OfficialAlert`
(`dedup_id`, `region_label`, `label`).

### Open Questions
Keine — Ansatz vom Plan-Agenten unabhängig bestätigt, keine offenen Entscheidungen für den PO.
