---
entity_id: feat_2984_regionszeile_ortsformatierer
type: refactor
created: 2026-11-17
updated: 2026-11-17
status: draft
version: "1.0"
tags: [alarm, amtliche-warnung, ortsformatierer, paritaet, telegram, email]
workflow: feat-2984-regionszeile-ortsformatierer
issue: 2984
---

# Amtliche Warnung: Regionszeile über denselben Ortsformatierer wie die anderen Alarme

## Approval

- [ ] Approved

## Purpose

Im Klartext- und Telegram-Text einer amtlichen Warnung baut die Regionszeile (`Region: Kärnten — Segment 3`) ihre Ortsangabe an einer eigenen Stelle, während Karten-Kopf (`scope_label`) und Betreff die gemessene km-Spanne (`km 12-20`, #2036) zeigen. Folge: Kopf und Regionszeile derselben Nachricht widersprechen sich. Diese Spec führt beide auf EINE Modulfunktion zurück (Paar P03/NEU-3 der Paritäts-Bestandsaufnahme #1986), sodass die Ortsangabe in jeder Zeile einer Nachricht identisch ist.

## Source

- **File:** `src/output/renderers/alert/official_alerts.py`
- **Identifier:** neue Modulfunktion `_official_alert_location` (herausgezogen aus dem inneren `_ort` von `build_official_alert_notices`); `render_official_alert_notice_plain`

> **Schicht-Hinweis:** ausschließlich Python-Core (`src/output/renderers/alert/`, `src/services/notification_service.py`). Kein Frontend, keine Go-API, kein Datenmodell.

> **Querschnitts-Prüfpunkte:**
> - **Trip/Ortsvergleich-Teilung:** kein Compare-Pendant (Trip-Alarm mit amtlicher Warnung); nichts unter `shared/` betroffen.
> - **Mandantentrennung:** keine Nutzerdaten werden bewegt; `user_id`-Pfade unverändert.
> - **Kanäle:** E-Mail (Klartext-Teil) und Telegram-Text ändern sich bei gemessener Spanne. SMS und Premium-SMS bleiben unverändert (eigener Pfad `render_alert_sms`, `sms_scope` aus den Notices). HTML: der Orts-Chip der eingebetteten Warnkarte (`affected_chips`) wurde bisher direkt über `format_segment_reference` gebaut und zeigte bei gemessener Spanne weiter „Segment 3" (Adversary-Befund F001, Runde 1); er übernimmt jetzt `scope_label` (AC-9).

## Estimated Scope

- **LoC:** ca. +60/-15 (Produktivcode ca. +20/-12)
- **Files:** 3 Code/Test, 2 Doku
- **Effort:** low (eine Auflösung wird geteilt; ohne gemessene Spanne byte-identisch)

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `segments.format_alert_location` | function | Geteilte Auflösungsreihenfolge (#1744/#2036), Stufe „gemessene km-Spanne" |
| `segments.format_segment_reference` | function | Segment-Sprache („Segment 3", rohe nicht-numerische Kennungen, #1965) |
| `official_alerts._measured_km_span` | function | Gemeinsame gemessene Spanne eines Segmentbündels |
| `notification_service._measured_event_km` | function | Liefert `{seg_id: (km_von, km_bis)}` nur für gemessene Ereignisse |
| `notification_service._dispatch_alert_message` | function | Einziger Produktiv-Aufrufer des Plain-Renderers; Telegram- und Klartext-Weg |
| i18n `t()` (`warnung.zeile.region`, `warnung.zeit.unbekannt`) | module | Zweisprachigkeit DE/EN, Katalogtexte |
| `docs/specs/modules/fix_2036_alarm_kilometer_ortsangabe.md` | spec | Freigegebene Produktentscheidung: gemessene Spanne verdrängt die Segmentnummer |

## Scope

### Affected Files

| File | Change Type | Description |
|------|-------------|-------------|
| `src/output/renderers/alert/official_alerts.py` | MODIFY | inneres `_ort` wird Modulfunktion `_official_alert_location`; `build_official_alert_notices` und `render_official_alert_notice_plain` (neuer Keyword-Parameter `segment_km=None`) nutzen sie |
| `src/services/notification_service.py` | MODIFY | `_dispatch_alert_message` reicht `_measured_event_km(alert_msg)` auch an den Plain-Renderer weiter (einmal berechnet) |
| `tests/tdd/test_official_alert_location_parity.py` | MODIFY | Paritätstest um die Regionszeile erweitert (gemessen, Fallback, roh, leer, DE/EN) plus Durchstich über `_dispatch_alert_message` |
| `docs/specs/modules/fix_1744_alarm_format_angleichen.md` | MODIFY | veraltete Zeilenangabe Z. 156 auf den heutigen Stand nachziehen |
| `docs/specs/modules/feat_2984_regionszeile_ortsformatierer.md` | CREATE | diese Spec |

### Estimated Changes

- Files: 5
- LoC: ca. +60/-15 (Produktivcode ca. +20/-12)

## Implementation Details

1. Das innere `_ort(sprache)` aus `build_official_alert_notices` wird zur Modulfunktion `_official_alert_location(segment_ids, segment_km, lang) -> str`. Auflösung: gemessene gemeinsame Spanne vorhanden, dann `format_alert_location(None, ids, von, bis, km_measured=True, lang=...)`; sonst `format_segment_reference(ids, lang=...)`. Bei leerer Segmentliste liefert die Funktion `""`; den „unbekannt"-Rückfall setzt weiterhin der Aufrufer (`build_official_alert_notices`).
2. `format_alert_location` wird bewusst NICHT blind im Plain-Renderer aufgerufen: dessen Stufe 3 verwirft nicht-numerische Kennungen und fiele ohne km-Werte auf einen km-Rückfall. Die heutige Regionszeile zeigt solche Kennungen roh (#1965); das bleibt erhalten.
3. `render_official_alert_notice_plain` erhält den additiven Keyword-Parameter `segment_km=None` und nutzt für den Zusatz „ — …" die Modulfunktion. Leere Segmentliste: Zusatz entfällt wie heute.
4. `_dispatch_alert_message` berechnet `_measured_event_km(alert_msg)` einmal und reicht es an HTML-Notices UND Plain-Renderer weiter.
5. Gruppierung bleibt getrennt (Plain nur `dedupe_official_alerts`, Notices zusätzlich `_bundle_by_hazard_level`); geteilt wird nur die Ortsauflösung je Segmentliste.
6. Doku-Nachzug (Teil des Scopes): `fix_1744_alarm_format_angleichen.md` Zeile 156 verweist auf veraltete Zeilen (`official_alerts.py:615-662`) und sagt, der Plain-Renderer bleibe unangetastet; auf den heutigen Stand und die geteilte Ortsauflösung (#2984) korrigieren.
7. HTML-Orts-Chip (AC-9): in `build_official_alert_notices` wird der Chip bei nicht-leerer Segmentliste aus `scope_label` gebildet (`affected = [scope_label]`) statt erneut über `format_segment_reference`; ohne gemessene Spanne ist `scope_label` identisch zum bisherigen Chip.
8. Renderer-Commit-Gate: Klartext- und HTML-Mailinhalt ändern sich bei gemessener Spanne; Modus-Matrix-Test und Mail-Validator müssen vor dem Commit frisch grün sein.

## Expected Behavior

- **Input:** Trip-Alarm mit eingebetteter amtlicher Warnung, optional mit gemessener km-Spanne je Segment.
- **Output:** Regionszeile im Klartext und Telegram-Text trägt dieselbe Ortsangabe wie der Karten-Kopf derselben Nachricht. Ohne gemessene Spanne exakt wie bisher.
- **Side effects:** keine.

## Test Plan

Echte Renderer-Aufrufe, kein `Mock`/`patch`/`MagicMock`.

### Automated Tests (TDD RED)

- [ ] `tests/tdd/test_official_alert_location_parity.py` (erweitert, Regressionswächter): GIVEN Segment 3 mit Spanne 12,31-20,0 WHEN Notices und Plain-Renderer mit demselben `segment_km` laufen THEN Regionszeile enthält exakt `scope_label` (`km 12-20`).
- [ ] Segment-Fallback: GIVEN kein `segment_km` WHEN Plain rendert THEN Regionszeile byte-identisch zu heute (`Segment 3`, Mehrfach-Segmente).
- [ ] Nicht-numerische Kennung ohne km: GIVEN Kennung wie `Etappe-A` ohne km-Werte THEN roh angezeigt, kein km-Rückfall.
- [ ] Leere Segmentliste: Plain ohne „ — …"; Notices „unbekannt".
- [ ] DE und EN parametrisiert.
- [ ] Durchstich über `_dispatch_alert_message`: Klartext-Teil UND Telegram-Text enthalten `km 12-20`, wenn der HTML-Kopf es tut.
- [ ] Baustein-Wächter: Regionszeile und `scope_label` rufen `_official_alert_location` auf; keine zweite Ortsauflösung im Plain-Renderer (Verhaltenstest über Gleichheit bei variierter Eingabe).
- [ ] Bestandstests unverändert grün: `tests/tdd/test_alert_segment_reference.py`, `tests/test_amtliche_warnungen_zweisprachig.py`, `tests/tdd/test_issue_1172_official_alert_dedup_info.py`, `tests/tdd/test_official_alert_warn_section.py`, `tests/tdd/test_official_alert_subject_label_fidelity.py`, `tests/tdd/test_warnmail_official_alert_display.py`, `tests/tdd/test_ampel_css_dots.py`, `tests/tdd/test_alert_location_vocabulary.py`.

## Definition of Done

- [ ] AC-1 bis AC-7 durch den erweiterten Paritätstest und den Durchstich über `_dispatch_alert_message` belegt, vor der Umsetzung rot nachgewiesen (AC-1, AC-2, AC-7), Kern-Schicht grün
- [ ] AC-8: Bestandstests der Regionszeile und SMS-/Snapshot-Tests ohne Anpassung grün
- [ ] Modus-Matrix-Test und Mail-Validator frisch grün (Renderer-Commit-Gate); auf Staging ein echt zugestellter Trip-Alarm mit amtlicher Warnung geprüft
- [ ] Doku-Nachzug `fix_1744_alarm_format_angleichen.md` erledigt
- [ ] Adversary-Verdict VERIFIED inkl. Mutations-Gegenprobe, alle 6 CI-Checks grün, Produktion ausgeliefert, Selftest grün

## Acceptance Criteria

- **AC-1:** Given eine amtliche Warnung betrifft Segment 3 mit gemessener Spanne 12,3-20,0 km / When Klartext-Block und Karten-Kopf derselben Nachricht gerendert werden / Then zeigt die Regionszeile `km 12-20` und stimmt exakt mit dem Karten-Kopf (`scope_label`) überein.
  - Test: Notices und Plain-Renderer laufen mit demselben `segment_km`; die Ortsangabe nach „Region: … — " ist gleich `scope_label`.

- **AC-2:** Given ein Trip-Alarm mit eingebetteter amtlicher Warnung und gemessener Spanne / When `_dispatch_alert_message` Klartext-Mailteil und Telegram-Text erzeugt / Then enthalten beide die Ortsangabe `km 12-20` und nicht mehr `Segment 3`, wie der HTML-Kopf derselben Nachricht.
  - Test: Durchstich über `_dispatch_alert_message` mit echten Renderern; Klartext, Telegram-Text und HTML-Kopf zeigen dieselbe km-Angabe.

- **AC-3:** Given eine amtliche Warnung ohne gemessene Spanne (ein oder mehrere Segmente) / When die Regionszeile gerendert wird / Then ist sie byte-identisch zur heutigen Ausgabe (`Segment 3`, bzw. die bisherige Mehrfach-Segment-Schreibweise).
  - Test: Ausgabe ohne `segment_km` wird gegen den bisherigen Wortlaut verglichen.

- **AC-4:** Given eine Segmentkennung ist nicht numerisch und es liegen keine km-Werte vor / When die Regionszeile gerendert wird / Then wird die Kennung wie heute angezeigt (#1965: erhalten, nicht verworfen, in der bisherigen Segment-Sprache, z. B. `Segment Etappe-A`) und es erscheint kein km-Rückfall.
  - Test: Kennung ohne km-Werte rendern; roher Wert im Text, keine „km"-Angabe.

- **AC-5:** Given eine amtliche Warnung mit leerer Segmentliste / When Klartext und Notices gebaut werden / Then enthält die Regionszeile keinen Zusatz „ — …" und die Notice zeigt weiterhin „unbekannt".
  - Test: Leere Liste in Plain-Renderer und `build_official_alert_notices`; Regionszeile endet nach dem Regionsnamen, `scope_label` ist „unbekannt" bzw. englisches Gegenstück.

- **AC-6:** Given Nutzersprache Deutsch oder Englisch / When die Regionszeile mit gemessener Spanne und im Segment-Fallback gerendert wird / Then erscheinen Beschriftung und Segmentwort in der Sprache des Nutzers, die km-Angabe bleibt `km 12-20`.
  - Test: Parametrisiert für `lang="de"` und `lang="en"`.

- **AC-7:** Given Regionszeile und Karten-Kopf lösen ihre Ortsangabe auf / When der Code geprüft und ausgeführt wird / Then nutzen beide dieselbe Modulfunktion `_official_alert_location`, es gibt keinen zweiten Auflösungspfad, und der erweiterte Paritätstest fällt rot aus, sobald beide auseinanderlaufen.
  - Test: Paritätstest über mehrere Eingaben (gemessen, Fallback, roh, leer); eine Abweichung zwischen Regionszeile und `scope_label` lässt ihn scheitern.

- **AC-8:** Given SMS und Premium-SMS einer amtlichen Warnung / When der Alarm nach der Änderung versendet wird / Then sind beide Texte byte-identisch zu vorher, und alle genannten Bestandstests laufen ohne Anpassung grün.
  - Test: Bestehende SMS-/Snapshot-Tests (`test_official_alert_output_unchanged.py`, `test_official_alert_sms_ortskopf.py`) und die Regionszeilen-Bestandstests unverändert grün.

- **AC-9:** Given ein Trip-Alarm mit eingebetteter amtlicher Warnung für Segment 3 mit gemessener Spanne 12,3-20,0 km / When `_dispatch_alert_message` die HTML-Mail erzeugt / Then zeigt der Orts-Chip der Warnkarte `km 12-20` (nicht `Segment 3`), also dieselbe Ortsangabe wie Regionszeile und `scope_label`; ohne gemessene Spanne bleibt der Chip byte-identisch (`Segment 3`).
  - Test: Durchstich über `_dispatch_alert_message` (HTML über das Transport-Double, nicht `mail_sink`), enge Prüfung am `wb-route`-Chip der Warnkarte; Gegenprobe: Notices ohne `segment_km` bzw. Chip über `format_segment_reference` lässt den Test scheitern.
  - Begründung: Nachzug aus Adversary-Befund F001. Seit #2036 weicht `scope_label` bei gemessener Spanne vom Chip ab; damit gilt auch die Invariante `scope_label == einziger Chip` (#1326a, ADR-0033, `_scope_matches_sole_chip`) nicht mehr. Der Chip über `scope_label` stellt sie wieder her und folgt der freigegebenen Produktentscheidung #2036 (gemessene Spanne verdrängt die Segmentnummer).

## Out of Scope

- `build_official_allclear_notices` (Entwarnung, ca. Z. 2666) nutzt `format_segment_reference` direkt. Entwarnungen tragen keine km-Spanne, ein Widerspruch innerhalb einer Nachricht ist nicht bekannt. Kein Teil von #2984; ggf. eigener Eintrag in der Bestandsaufnahme #1986.
- Angleichung der Gruppierung (Plain vs. Notices).

## Known Limitations

- Plain und Notices können unterschiedliche Segmentlisten je Warnung haben, weil nur die Notices zusätzlich nach Gefahr und Stufe bündeln. Die Ortsauflösung ist je Liste identisch, die Listen selbst nicht.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Reines Zusammenführen zweier Auflösungsstellen auf eine Modulfunktion innerhalb des bestehenden Renderers; bestätigt die Teilungs-Invariante #1744 und die Produktentscheidung #2036, ohne neue Entscheidung.

## Changelog

- 2026-11-17: Initial spec created (Issue #2984)
- 2026-11-17: AC-9 (HTML-Orts-Chip über `scope_label`) nach Adversary-Befund F001 ergänzt; AC-4 präzisiert: „roh" = Kennung bleibt erhalten in der bisherigen Segment-Sprache, kein km-Rückfall
