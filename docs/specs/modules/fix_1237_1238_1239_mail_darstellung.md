---
entity_id: fix_1237_1238_1239_mail_darstellung
type: module
created: 2026-07-13
updated: 2026-07-13
status: draft
version: "1.0"
tags: [official-alerts, compare, email, hour-table, subject, design-fidelity]
---

# #1237/#1238/#1239 — Ortsvergleich-Stundentabelle & amtliche-Warnung-Mail: Darstellungs-Fixes

## Approval

- [x] Approved (PO-go 2026-07-13)

## Purpose

Behebt zehn Darstellungsmängel derselben Mail-Familie, gebündelt in drei Issues: die Stundentabelle der Ortsvergleichs-Mail zeigt unnötig breite Zeit-/Sicht-Zellen (#1237); die amtliche-Warnung-Sektion (Trip- **und** Ortsvergleich-Standalone-Alarm) widerspricht sich an mehreren Stellen — doppelter Warn-Titel, „Gültig: unbekannt", eine Quelle-Box, die nicht zu allen Chips passt, ein redundanter Freitext-Satz, ein im Ortsvergleich falsches Label „Route:" (#1238); und der Ortsvergleich-Pfad hat zusätzlich einen unlesbaren Betreff, eine redundante Überschrift, eine Chip-Explosion und fehlende Bündelung gleichartiger Warnungen (#1239). Der Trip-Briefing-Stundentabellen-Pfad und der Trip-Warn-Chip-Pfad sind bereits korrekt und dürfen sich nicht ändern.

## Source

- **File:** `src/output/renderers/email/compare_html.py` (MODIFY — Stundentabelle, Einheiten-Legende)
- **File:** `src/output/renderers/alert/official_alerts.py` (MODIFY — Warn-Titel, Gültigkeits-Zeile, Quelle-Box, Route/Orte-Chips, Bündelung, Betreff, Headline, CSS-Spaltenbreite)
- **File:** `src/output/renderers/email/helpers.py` (ggf. MODIFY — falls die Einheiten-Legende der Ortsvergleichs-Tabelle einen gemeinsamen Helfer mit der Trip-Briefing-Legende nutzt)
- **File:** `src/services/notification_service.py` (ggf. MODIFY — nur falls der Aufruf der Betreff-/Bündelungs-Funktionen Parameter-Änderungen braucht)
- **Identifier:** `_render_hour_row`, `_render_hour_table`, `_render_legend` (compare_html.py); `_standalone_warn_type_html`, `_typ_tag`, `_format_validity`, `_standalone_src_sentence`, `_standalone_warn_grid_html`, `_standalone_warn_stacked_html`, `dedupe_official_alerts`, `build_compare_official_alert_notices`, `render_official_alert_subject`, `_standalone_headline_html` (official_alerts.py)

Schicht: **Python-Core / Domain-Backend** (`src/output/renderers/`, `src/services/`) — kein Frontend, kein Go.

## Estimated Scope

- **LoC:** ~250–350 (Renderer-Änderungen in zwei Dateien + Test-Anpassungen an sechs Bestandstests + 2–3 neue Testdateien für Bündelung/Betreff-Kompaktierung). Liegt nahe am oder über dem 250-LoC-Standardbudget — bei Überschreitung PO vor `loc_limit_override` fragen.
- **Files:** 2–4 Quell-Dateien (MODIFY) + ~6 Bestandstests (MODIFY) + 1–3 neue Testdateien (CREATE, nach Verhalten benannt) + 2 Goldens (ggf. MODIFY, nur bei Änderung am embedded Pfad durch E4)
- **Effort:** high

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `app/metric_catalog.py` (`display_unit`) | reuse | Einheit je Metrik für die neue Ortsvergleichs-Einheiten-Legende |
| `email/helpers.py::build_units_legend` | reuse (Vorbild) | Trip-Briefing-Legende als funktionales Vorbild für die neue Compare-Legende |
| `_hazard_display` (official_alerts.py) | reuse | Liefert das normalisierte Typ-Wort; wird von SMS/Telegram mitgenutzt — Änderungen am Typ-Wort selbst sind **nicht** Teil dieser Spec (nur die Titel-Kombination ändert sich) |
| `dedupe_official_alerts` (official_alerts.py:212-246) | modify (additiv) | Bestehende Identitäts-Dedup (dedup_id/region_label/label + hazard) bleibt Basis; neue Bündelung nach (hazard, level) baut darauf auf, ohne die bestehende Massiv-Eskalations-Semantik zu brechen |
| `_sort_notices`, `render_official_alert_subject`, `_typ_tag` (official_alerts.py) | reuse/modify | Reihenfolge nach Stufe bleibt Basis für die neue Betreff-Kompaktierung |
| `_format_validity` (official_alerts.py:328-346) | modify | Liefert bisher „unbekannt" bei fehlenden Zeiten — Aufrufer müssen künftig die ganze „Gültig:"-Zeile weglassen können |
| `.claude/hooks/official_alert_mail_validator.py` (Regel P-3) | consume | Verlangt aktuell „Gültig:" bedingungslos im Body — wird in Issue #1240 (eigener Vorlauf-Workflow) auf „Gültig:" nur bei bekannter Zeit angepasst; diese Spec setzt die angepasste Regel voraus |

## Betroffene Tests

Bestand (werden angepasst, nicht als Regression liegengelassen):
`tests/tdd/test_issue_1106_hourly_metrics_config.py:407,437,473,481-482`, `tests/tdd/test_issue_1110_compare_mail_v2.py:486,506,528`, `tests/tdd/test_official_alert_standalone_render.py:363`, `test_warn_block_render.py`, `test_official_alert_template_render.py`, `test_official_alert_subject_label_fidelity.py:55-157,214,218`, `test_official_alert_mail_validator.py`, `test_issue_1037_massif_closure.py`.

Goldens (nur bei Änderung am embedded Pfad durch E4 betroffen): `tests/golden/email/corsica-vigilance-{html,plain}.txt`.

Neu (nach Verhalten benannt, NICHT nach Issue-Nummer — Gate `test_naming_gate.py`): z. B. `test_official_alert_subject_compact.py` (E8-Betreffkompaktierung), `test_official_alert_hazard_bundling.py` (E7-Bündelung), `test_compare_hour_table_units_legend.py` (E1-Legende).

## Implementation Details

### E1 — Ortsvergleichs-Stundentabelle (#1237)
`_render_hour_row` formatiert die Zeit-Zelle heute mit `%H:%M`; sie soll nur die Stunde zeigen (analog zur bereits korrekten Trip-Briefing-Formatierung `helpers.py:89,140`). `_fmt_visibility` hängt heute „ km" an; die Zelle soll nur den gerundeten Zahlenwert zeigen. Die Spaltenköpfe „Zeit"/„Sicht" bleiben unverändert. `_render_legend` (heute nur Ampel-/Warn-Kürzel) bekommt eine zusätzliche Einheiten-Zeile, die alle einheitentragenden Spalten der aktuell sichtbaren `HOUR_METRICS` abdeckt (nicht nur Sicht) — Quelle der Einheit ist `metric_catalog.display_unit`, analog zum Trip-Briefing-Vorbild `build_units_legend`.

### E2/E3 — Warn-Titel (#1238, M1/M10)
`_standalone_warn_type_html` konkateniert heute Typ-Wort und vollen Quell-Label mit „ — "; sie soll stattdessen dieselbe **Ersetz**-Logik wie `_typ_tag` (Betreff, Zeile 358-378) übernehmen: der reichere Quell-Label ersetzt das Typ-Wort, wenn er es erweitert, sonst bleibt nur das Typ-Wort. Zusätzlich darf der Titel keine numerische Quell-Stufe mehr zeigen, wenn dieselbe Stufe bereits im Eskalations-Meter/Stufenwort der Zeile steht (`_standalone_warn_stacked_html`).

### E4 — Gültig-Zeile bei fehlender Zeit (#1238, M2)
Warnungen ohne `valid_from`/`valid_to` (Präfektur-Zugangssperren, Waldbrand-Tagesstufen) lassen die gesamte „Gültig:"-Zeile weg, statt „Gültig: unbekannt" zu zeigen — betrifft Standalone-Grid, Standalone-Stacked und den embedded Pfad gleichermaßen.

### E5 — Quelle-Box (#1238, M3)
`_standalone_src_sentence` leitet ihren zusammenfassenden Satz nur aus der ersten (führenden) Warnung ab. Er darf nur noch erscheinen, wenn **alle** Warnungen denselben betroffenen Umfang haben; bei unterschiedlichem Umfang tritt ein neutraler Satz an seine Stelle, der auf die Einzelangaben der Warnungen oben verweist statt zu verallgemeinern.

### E6 — Route- vs. Orte-Chips (#1238/#1239, M4/M5/M9)
Trip-Pfad bleibt unverändert (Segment-Chips, durchgestrichene freie Segmente, Hinweistext, Label „Route:"). Im Compare-Pfad (`build_compare_official_alert_notices`) entfallen die freien (nicht betroffenen) Orts-Chips und der zugehörige Hinweistext vollständig; nur die betroffenen Orte werden als Chips gezeigt. Das Feld heißt dort „Orte:" statt „Route:".

### E7 — Bündelung gleichartiger Warnungen (#1239, M8)
`dedupe_official_alerts` trennt heute strikt nach Identität (dedup_id/region_label/label) + hazard — zwei Waldbrand-Stufe-3-Warnungen in unterschiedlichen Zonen bleiben getrennt. Zusätzlich zur bestehenden Identitäts-Dedup wird eine Bündelung nach (Gefahren-Typ, Stufe) ergänzt: Warnungen mit gleichem Typ und gleicher Stufe werden zu einer Warnung mit vereinigter Orts-/Segmentliste zusammengeführt. Die bestehende Massiv-Eskalations-Dedup (unterschiedliche Stufe derselben Massiv-ID kollabiert zur höchsten Stufe) bleibt als Vorstufe erhalten.

### E8 — Betreff-Kompaktierung (#1239, M6)
`render_official_alert_subject` zeigt bei mehr als zwei betroffenen Orten eine Mengenangabe (z. B. „7 von 8 Orten") statt der vollständigen Namensliste; bei 1–2 betroffenen Orten bleiben die Namen. „alle Orte"/„gesamte Route" bleiben als Sonderfall unverändert. Höchstens zwei Warnungen werden ausgeschrieben (schwerste zuerst), weitere als „+N weitere" zusammengefasst.

### E9 — H1-Redundanz (#1239, M7)
`_standalone_headline_html` nennt heute erneut die vollständige Ortsliste aus `scope_label`. Sie nennt künftig die Gefahren-Typen, verzichtet aber bei vielen betroffenen Orten auf die Wiederholung der vollständigen Namensliste (die steht bereits in den Chips).

### E10 — Wortumbruch (#1239, M11, kosmetisch)
Die Grid-Spaltenbreite `130px` in `_standalone_warn_grid_html`/`_standalone_warn_stacked_html` ist zu schmal für „ORANGE" im Titel-/Meter-Bereich; die Spalte wird verbreitert bzw. der Wortumbruch innerhalb des Stufenworts unterbunden.

## Expected Behavior

- **Input:** Ortsvergleichs-Stundendaten je Ort (`LocationResult.hourly_data`); deduplizierte `OfficialAlertNotice`-Listen für Trip- und Compare-Standalone-Alarm.
- **Output:** kompaktere Stundentabelle mit Einheiten-Legende (Ortsvergleich); widerspruchsfreie, gebündelte, lesbare Warn-Sektion inkl. kompaktem Betreff und kompakter Überschrift für beide Standalone-Alarm-Pfade.
- **Side effects:** keine — reine Präsentationsänderung, kein neuer Versand-Trigger, kein State-Effekt.

## Acceptance Criteria

- **AC-1:** Given die Stundentabelle der Ortsvergleichs-Mail zeigt mehrere Zeitpunkte / When die Mail gerendert wird / Then zeigt die Zeit-Spalte je Zeile nur die Stunde (z. B. „07") ohne Minutenanteil.
  - Test: Assert auf den Zellinhalt der Zeit-Spalte in `_render_hour_row`-Ausgabe für einen Ortsvergleichs-Datenpunkt; kein Dateiinhalt-Check.

- **AC-2:** Given dieselbe Stundentabelle enthält eine Sicht-Spalte mit Werten / When die Mail gerendert wird / Then steht in der Sicht-Zelle nur der Zahlenwert ohne Einheit, und unter der Tabelle erscheint eine Einheiten-Legende, die die Einheit aller einheitentragenden sichtbaren Spalten benennt.
  - Test: Assert, dass die Sicht-Zelle keine Einheit enthält, während die neue Legenden-Zeile die Einheit (u. a. „km") separat ausweist.

- **AC-3:** Given die Stundentabelle im Trip-Briefing zeigt bereits Stunden ohne Minuten und Sicht ohne Einheit / When die Mail nach diesem Fix gerendert wird / Then bleibt ihre Darstellung inklusive bestehender Legende unverändert.
  - Test: Non-Regression-Assert auf unveränderten Trip-Briefing-Stundentabellen-Output vor/nach dem Fix.

- **AC-4:** Given eine amtliche Warnung mit einem reicheren Quell-Label (z. B. eine Zugangssperre mit Massiv-Namen) / When der Warn-Titel im Standalone-Alarm gerendert wird / Then erscheint der Gefahren-Typ genau einmal — der reichere Label ersetzt das allgemeine Typ-Wort, statt es zu wiederholen.
  - Test: Assert, dass der gerenderte Titel-Text kein doppeltes Stufen-/Typ-Wort mehr enthält (z. B. nicht mehr „Zugang gesperrt — Zugang eingeschränkt — Maures").

- **AC-5:** Given eine Standard-Warnung ohne zusätzlichen Quell-Label (z. B. Hitze oder Gewitter direkt aus der Wettervorhersage) / When der Warn-Titel gerendert wird / Then bleibt der Titeltext bit-identisch zum Stand vor diesem Fix.
  - Test: Non-Regression-Assert auf bekannten Standardfällen aus `test_official_alert_subject_label_fidelity.py`.

- **AC-6:** Given eine Warnung, deren Eskalationsstufe bereits als Eskalations-Meter/Stufenwort in derselben Zeile angezeigt wird / When der Warn-Titel gerendert wird / Then nennt der Titel den Gefahren-Typ, aber keine zusätzliche numerische Quell-Stufe mehr.
  - Test: Assert, dass „Waldbrand-Gefahr — Stufe 3" im Titel nicht mehr neben einem Meter „ORANGE · 2/3" für dieselbe Warnung erscheint.

- **AC-7:** Given eine amtliche Warnung ohne bekannten Gültigkeitszeitraum (z. B. eine tagesbezogene Zugangssperre oder Waldbrand-Stufe ohne Uhrzeiten) / When die Warn-Sektion gerendert wird / Then erscheint für diese Warnung keine „Gültig:"-Zeile mehr.
  - Test: Assert auf Abwesenheit der „Gültig:"-Zeile bei einem `OfficialAlertNotice` ohne `valid_from`/`valid_to`, sowohl im Standalone- als auch im embedded Pfad.

- **AC-8:** Given eine amtliche Warnung mit bekanntem Gültigkeitszeitraum / When die Warn-Sektion gerendert wird / Then erscheint die „Gültig:"-Zeile weiterhin mit dem formatierten Zeitraum wie vor diesem Fix.
  - Test: Non-Regression-Assert für eine Warnung mit gesetztem `valid_from`/`valid_to`.

- **AC-9:** Given mehrere amtliche Warnungen mit unterschiedlichem betroffenem Umfang (unterschiedliche Orte oder Streckenabschnitte) / When die Quelle-Box gerendert wird / Then verallgemeinert ihr Satz nicht mehr den Umfang der ersten Warnung, sondern verweist neutral auf die Einzelangaben der Warnungen oben.
  - Test: Assert, dass der Quelle-Box-Satz bei abweichenden Umfängen nicht mehr ausschließlich `ordered[0]`-Scope wiedergibt.

- **AC-10:** Given mehrere amtliche Warnungen, die alle denselben betroffenen Umfang haben / When die Quelle-Box gerendert wird / Then bleibt ihr zusammenfassender Satz wie vor diesem Fix.
  - Test: Non-Regression-Assert auf uniformen Scope-Fall.

- **AC-11:** Given eine Trip-Standalone-Alarmmail mit Warnungen, die nur einen Teil der Route betreffen / When die Warn-Sektion gerendert wird / Then zeigt sie weiterhin Segment-Chips inklusive durchgestrichener freier Segmente und den erklärenden Hinweistext, unverändert zum Stand vor diesem Fix.
  - Test: Non-Regression-Assert auf `test_official_alert_standalone_render.py` (Trip-Fall).

- **AC-12:** Given eine Ortsvergleich-Standalone-Alarmmail mit Warnungen, die nur einen Teil der verglichenen Orte betreffen / When die Warn-Sektion gerendert wird / Then zeigt sie ausschließlich die betroffenen Orte als Chips ohne durchgestrichene freie Orte und ohne den bisherigen „übrige Strecke frei"-Hinweistext, und das Feld heißt „Orte:" statt „Route:".
  - Test: Assert auf Chip-Anzahl (nur betroffene) sowie Feld-Label im Compare-Fall.

- **AC-13:** Given zwei amtliche Warnungen mit demselben Gefahren-Typ und derselben Stufe, aber unterschiedlichen betroffenen Zonen oder Orten / When die Warn-Sektion gerendert wird / Then erscheinen sie als eine einzige Warnung mit einer vereinigten Orts-/Segmentliste statt als zwei getrennte Warnungen.
  - Test: Assert auf Anzahl der gerenderten Warn-Einträge (eins statt zwei) und auf die vereinigte Chip-Liste.

- **AC-14:** Given eine Massiv-Zugangssperre, die von Stufe 3 auf Stufe 4 eskaliert (bestehender Bündelungsfall über eine stabile Massiv-Kennung) / When die Warn-Sektion gerendert wird / Then bleibt sie weiterhin als eine Warnung mit der höchsten Stufe dargestellt, wie vor diesem Fix.
  - Test: Non-Regression-Assert auf `test_issue_1037_massif_closure.py`.

- **AC-15:** Given eine Ortsvergleich-Alarmmail mit mehr als zwei betroffenen Orten und mehr als zwei gleichzeitigen Warnungen / When der Betreff gerendert wird / Then nennt er die Reichweite als Mengenangabe statt aller Ortsnamen und führt höchstens zwei Warnungen aus, den Rest als „+N weitere".
  - Test: Betreff-String-Assert für ein Preset mit acht betroffenen Orten und mehreren Warnungen; Vergleich mit der Vorlagen-Länge.

- **AC-16:** Given eine Alarmmail (Trip oder Ortsvergleich) mit höchstens zwei betroffenen Orten und höchstens zwei Warnungen / When der Betreff gerendert wird / Then bleibt sein Text bit-identisch zum Stand vor diesem Fix, einschließlich der Sonderfälle „alle Orte"/„gesamte Route".
  - Test: Non-Regression-Assert auf `test_official_alert_subject_label_fidelity.py`-Fällen mit ≤2 Orten/Warnungen.

- **AC-17:** Given eine Ortsvergleich-Alarmmail mit vielen betroffenen Orten / When die Überschrift im Mail-Text gerendert wird / Then nennt sie die betroffenen Gefahren-Typen, wiederholt aber nicht mehr die vollständige Liste der Ortsnamen aus dem Betreff.
  - Test: Assert, dass die Überschrift bei vielen Orten keine vollständige Kommaliste mehr enthält.

- **AC-18:** Given eine Warnstufe mit einem langen Stufenwort (z. B. „ORANGE") / When der Warn-Titel-Bereich gerendert wird / Then bricht das Stufenwort nicht mehr mitten im Wort um.
  - Test: strukturelle Prüfung der CSS-Spaltenbreite/Umbruchverhinderung im gerenderten HTML.

## Ersetzt/Überschreibt

Diese Spec **überschreibt** `docs/specs/modules/issue_1216_official_alert_template.md`, Abschnitt „Gültigkeit-Formatierung" (Zeile 84-87) sowie **AC-6** dieser Spec (Zeile 130-131), soweit dort „Gültig: unbekannt" bei fehlenden Zeiten vorgeschrieben wird. Diese Vorschrift wird durch AC-7/AC-8 der vorliegenden Spec ersetzt: Fehlt der Gültigkeitszeitraum, entfällt die „Gültig:"-Zeile vollständig, statt einen Platzhalter-Wert zu zeigen. Begründung (PO-Entscheidung): tagesbezogene Warnungen (Präfektur-Zugangssperren, Waldbrand-Tagesstufen) haben strukturell keine Uhrzeit — „unbekannt" suggeriert fälschlich eine fehlende Dateneigenschaft statt einer erwarteten Eigenschaft der Warnungsart. Die alte Spec-Datei wird **nicht** editiert (Transparenz-Prinzip); dieser Abschnitt dokumentiert die Ablösung. Die zugehörige Mail-Prüfregel P-3 (`.claude/hooks/official_alert_mail_validator.py:172-173`, verlangt „Gültig:" bedingungslos) wird in einem eigenen Vorlauf-Workflow zu Issue #1240 angepasst; diese Spec setzt die angepasste Regel voraus und kann erst nach deren Abschluss vollständig implementiert werden.

## Known Limitations

- **Reihenfolge-Abhängigkeit zu #1240:** AC-7 kann erst grün werden bzw. das Renderer-Commit-Gate erst passieren, wenn die Mail-Prüfregel P-3 in Issue #1240 angepasst ist. Bis dahin bleibt der Implementierungsschritt für E4 blockiert oder muss mit einer vorläufigen, expliziten Ausnahme im Validator koordiniert werden.
- **Telegram/SMS nicht Teil dieser Spec:** Die Betreff-Kompaktierung (E8) betrifft ausschließlich `render_official_alert_subject` (E-Mail-Betreff). Telegram- und SMS-Renderer der amtlichen Warnung nutzen andere Funktionen und sind hier nicht adressiert, sofern sie nicht denselben Betreff-Text wiederverwenden.
- **Bündelung nur bei exakt gleichem Typ und gleicher Stufe (E7):** Warnungen desselben Typs mit unterschiedlicher Stufe bleiben getrennt und folgen weiterhin dem bestehenden Mixed-Level-Pfad (Eskalations-Meter je Warnung).
- **Design-Vorlage bleibt Referenz für Chip-Form:** Die Design-Vorlage sieht eigentlich Segment-Chips auch im Vergleichs-Kontext vor; die PO-Entscheidung E6 weicht davon bewusst ab (Orte statt Segmente sind für den Nutzer informativer) — kein Fidelity-Verstoß, sondern dokumentierte Abweichung.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine (ADR-0011, bestehend — gemeinsamer Renderer für amtliche Warnungen, bleibt gültig)
- **Rationale:** Reine Präsentations-/Formatierungskorrekturen an bereits mit ADR-0011 etablierten, kontext-agnostischen Renderern. Keine neue Architektur, kein neuer Konsument, keine neue Datenstruktur — die Bündelung (E7) erweitert eine bestehende Dedup-Funktion additiv, ersetzt sie nicht.

## Changelog

- 2026-07-13: Initial spec created (Bugbündel #1237/#1238/#1239, Kontext `docs/context/fix-1237-1238-mail-darstellung.md`, PO-Entscheidungen E1-E10 wörtlich übernommen).
