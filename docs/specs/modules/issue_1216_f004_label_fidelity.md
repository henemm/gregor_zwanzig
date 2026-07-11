---
entity_id: issue_1216_f004_label_fidelity
type: bugfix
created: 2026-07-11
updated: 2026-07-11
status: draft
version: "1.0"
tags: [official-alerts, mail-subject, label-fidelity, access-ban, vigilance]
---

# Betreff-Label-Fidelity amtlicher Warnungen (#1216 F004)

## Approval

- [x] Approved (PO 'go', 2026-07-11)

## Purpose

Der Mail-**Betreff** amtlicher Warnungen zeigt aktuell nur ein sauberes
Typ-Wort statt des vollen Detail-Labels, das die Quelle bereits liefert. Bei
**Massiv-Sperren** (`hazard=access_ban`) geht dadurch der Massiv-Name verloren
(sicherheitskritisch — welches Gebiet gesperrt ist, ist unmittelbar aus dem
Betreff nicht erkennbar). Bei **Vigilance-Extremhitze** (`hazard=extreme_heat`,
Météo-France) wird „Extreme Hitze" zu „Hitze" verkürzt. Diese Spec macht den
Betreff-Typ-Tag detailtreu zum vorhandenen `alert.label`, ohne die bereits
korrekten Standardfälle (Label == Typ-Wort) zu verändern.

## Source

- **File:** `src/output/renderers/alert/official_alerts.py` — `_typ_tag()` (Zeile 314-318), aufgerufen von `render_official_alert_subject()` (Zeile 321-334)
- **Identifier:** `_typ_tag`, `_hazard_display`, `render_official_alert_subject`

Schicht: **Python-Core / Domain-Backend** (`src/output/renderers/`, reiner Präsentations-Renderer, kein Provider-/DTO-Eingriff).

## Estimated Scope

- **LoC:** ~+40/-10
- **Files:** 2 (1 MODIFY Renderer, 1 MODIFY/CREATE Testsuite)
- **Effort:** low-medium (Risk: MEDIUM — Mail-Betreff ist sicherheitsrelevant für den Massiv-Namen; Standardfälle müssen invariant bleiben)

### Affected Files

| File | Change Type | Description |
|------|-------------|--------------|
| `src/output/renderers/alert/official_alerts.py` | MODIFY | `_typ_tag()` bevorzugt `alert.label` gegenüber dem reinen Typ-Wort, wenn das Label reicher ist |
| Alert-Renderer-Testsuite (`tests/…/test_*official_alert*`) | MODIFY/CREATE | Betreff-Fidelity-Tests für access_ban (3 Varianten), Vigilance, Invarianz, Bündelung, Truncation |

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `_hazard_display()` (`official_alerts.py:269-276`) | intern | Liefert bisheriges Typ-Wort `w` als Ausgangsbasis; unverändert für SMS-Kurzcode |
| `OfficialAlert.label` (`src/services/official_alerts/models.py:15-33`) | Domain-Modell | Trägt bereits das volle Detail (kein neues Feld nötig) |
| `massif_closure.py:61-67` | Provider (FR-Massiv) | Erzeugt Label `"Zugang {eingeschränkt/gesperrt/gesperrt (total)} — {Massiv}"` |
| `vigilance.py:48-52` | Provider (Météo-France) | Erzeugt Label `"Extreme Hitze"` für `hazard="extreme_heat"` |
| `_sms_truncate()` (`official_alerts.py:459-476`) | intern (Muster) | Referenz-Kürzungslogik (ganze Tokens droppen, nie Mid-Wort) — Vorbild für die Betreff-Kürzung, nicht direkt wiederverwendet (SMS-Pfad bleibt unverändert) |
| `notification_service.py:482,575` | Downstream | Trip- UND Compare-Pfad rufen `render_official_alert_subject()` identisch auf — beide profitieren automatisch |

## Implementation Details

`_typ_tag()` ändern: statt bedingungslos `_hazard_display(alert)[0]` (Typ-Wort
`w`) zu verwenden, wird `alert.label` bevorzugt, wenn es **reicher** ist als
`w` (Label ≠ `w`, insbesondere wenn es mit `w` beginnt oder eine bekannte
Vigilance-Bezeichnung ist). Ist Label == `w` (GeoSphere-Standardfall), bleibt
das Verhalten exakt wie bisher. Der Wochentag-Suffix `(Tag)` wird unverändert
angehängt.

Ergebnis-Beispiele:
- `access_ban`, Label `"Zugang gesperrt — Rotwand-Massiv"` → Typ-Tag `"Zugang gesperrt — Rotwand-Massiv (Sa)"`.
- `extreme_heat` (Vigilance), Label `"Extreme Hitze"` → Typ-Tag `"Extreme Hitze (Sa)"` statt `"Hitze (Sa)"`.
- `thunderstorm` (GeoSphere-Standard), Label `"Gewitter"` == `w` → Typ-Tag unverändert `"Gewitter (Sa)"`.

Betreff-Platzierung: Detail wandert in den Typ-Tag (nicht in `scope_label`,
das die Reichweite/„welche Orte" trägt) — technisch sauberer, da beide
Informationen unterschiedliche Dimensionen sind. Gesamt-Betreff bleibt
strukturell `[{prefix}] {scope_label} · {Stufe(n)} {Typ-Tag} + …`.

Bündelung (`render_official_alert_subject`) bleibt strukturell unverändert:
Sortierung nach Level, „ + "-Trenner, führende Warnung bestimmt `scope_label`.
Nur der Aufruf von `_typ_tag()` je Warnung liefert ggf. mehr Text — betroffene
Warnungen zeigen Detail, unbetroffene (Label==Typ-Wort) bleiben kompakt.

Betreff-Kürzung: analog zum bestehenden `_sms_truncate`-Prinzip (ganze
Tags/Wörter droppen statt Mid-Wort-Schnitt) muss ein sehr langer Bündel-Betreff
mit mehreren Detail-Tags sauber gekürzt werden, ohne den Massiv-Namen oder das
Vigilance-Wort mitten im Wort abzuschneiden.

Body (HTML/Plain-Notice) und SMS bleiben unangetastet: Body zeigt `alert.label`
bereits vollständig (`official_alerts.py:104-124, 218-225`), SMS nutzt den
unveränderten Kurzcode aus `_hazard_display()[1]` (`official_alerts.py:497,502`).

## Expected Behavior

- **Input:** `OfficialAlertNotice`-Liste mit `alert.hazard`, `alert.label`, `alert.level`, `alert.valid_from`.
- **Output:** Mail-Betreff-String mit detailtreuem Typ-Tag für access_ban/Vigilance, unverändert für Standardfälle.
- **Side effects:** keine (reine Präsentationsfunktion, kein State/Schreibzugriff).

## Test Plan

Konsolidierte Testliste (Kern-Schicht, deterministisch, keine Mocks — echte
`OfficialAlert`/`OfficialAlertNotice`-Objekte mit fixierten Labels):

- [ ] Test 1: GIVEN `access_ban`-Alert mit Label `"Zugang gesperrt — Rotwand-Massiv"` WHEN `render_official_alert_subject` rendert THEN enthält der Betreff `"Zugang gesperrt — Rotwand-Massiv"`.
- [ ] Test 2: GIVEN dieselbe Warnung mit den Label-Varianten `"Zugang eingeschränkt — {Massiv}"` und `"Zugang gesperrt (total) — {Massiv}"` WHEN gerendert wird THEN erscheint jeweils der Massiv-Name im Betreff.
- [ ] Test 3: GIVEN `extreme_heat`-Vigilance-Alert mit Label `"Extreme Hitze"` WHEN gerendert wird THEN zeigt der Betreff `"Extreme Hitze"`, nicht nur `"Hitze"`.
- [ ] Test 4: GIVEN ein GeoSphere-Standardfall mit Label == Typ-Wort (z.B. `"Gewitter"`, `"Hitze"`, `"Sturm"`) WHEN gerendert wird (einzeln UND gebündelt) THEN ist der Betreff bit-identisch zum bisherigen (dokumentierten) Verhalten.
- [ ] Test 5: GIVEN ein Bündel aus einer access_ban-Warnung und einer Standard-Warnung WHEN der Betreff gerendert wird THEN trägt nur der access_ban-Tag Detail, der Standard-Tag bleibt kompakt, Reihenfolge/Stufen-Logik unverändert.
- [ ] Test 6: GIVEN dieselben access_ban-/Vigilance-Warnungen WHEN HTML-Notice, Plain-Notice, SMS gerendert werden THEN bleiben deren Ausgaben unverändert gegenüber dem Vorher-Stand.
- [ ] Test 7: GIVEN ein access_ban-Alarm sowohl im Trip- als auch im Compare-Standalone-Alarm-Pfad WHEN beide `render_official_alert_subject` aufrufen THEN zeigen beide Pfade denselben detailtreuen Betreff (keine Divergenz).
- [ ] Test 8 (F001, PO-bestätigt): GIVEN ein Vigilance-`wind_gust`-Alert mit Label `"Sturmböen"` (Typ-Wort „Sturm") WHEN der Betreff gerendert wird THEN zeigt der Typ-Tag `"Sturmböen"` statt „Sturm" — die Vigilance-Detailtreue gilt generisch, nicht nur für „Extreme Hitze".

## Acceptance Criteria

- **AC-1:** Given ein `access_ban`-Alert mit Label `"Zugang gesperrt — Rotwand-Massiv"` (Voll-Sperre) / When `render_official_alert_subject()` den Betreff rendert / Then enthält der Typ-Tag den vollen Text `"Zugang gesperrt — Rotwand-Massiv"` statt nur `"Zugang gesperrt"`.
  - Test: Test 1 im Test Plan.

- **AC-2:** Given `access_ban`-Alerts mit den beiden weiteren Label-Varianten `"Zugang eingeschränkt — {Massiv}"` und `"Zugang gesperrt (total) — {Massiv}"` / When der Betreff gerendert wird / Then erscheint jeweils das volle Label inklusive Massiv-Name im Typ-Tag, unabhängig von der Formulierungs-Variante.
  - Test: Test 2 im Test Plan.

- **AC-3:** Given ein Vigilance-Alert mit `hazard="extreme_heat"` und Label `"Extreme Hitze"` (Météo-France) / When der Betreff gerendert wird / Then zeigt der Typ-Tag `"Extreme Hitze"` statt nur `"Hitze"`.
  - Test: Test 3 im Test Plan.

- **AC-4 (Invariante):** Given ein GeoSphere-Standardfall, bei dem `alert.label == w` (Typ-Wort, z.B. `"Hitze"`, `"Gewitter"`, `"Sturm"`) / When der Betreff für Einzel- UND Bündel-Fälle gerendert wird / Then ist der resultierende Betreff bit-identisch zum bisherigen Verhalten — keine Regression für saubere Fälle.
  - Test: Test 4 im Test Plan.

- **AC-5:** Given ein gebündelter Betreff mit einer access_ban-Warnung (Detail-Label) UND einer Standard-Warnung (Label == Typ-Wort) im selben Betreff (" + "-Trenner) / When der Betreff gerendert wird / Then trägt nur der access_ban-Tag den Massiv-Namen, der Standard-Tag bleibt kompakt, und Reihenfolge sowie Stufen-Logik (Level-Sortierung, Trenner) bleiben strukturell unverändert.
  - Test: Test 5 im Test Plan.

- **AC-6:** Given dieselben access_ban- bzw. Vigilance-Warnungen / When HTML-Notice, Plain-Notice und SMS gerendert werden / Then bleiben deren Ausgaben gegenüber dem Vorher-Stand unverändert (Body zeigte das Label bereits vollständig; SMS nutzt weiterhin ausschließlich den unveränderten Kurzcode aus `_hazard_display()[1]`).
  - Test: Test 6 im Test Plan.

- **AC-7:** Given ein access_ban-Alarm sowohl im Trip-Standalone-Alarm-Pfad (`notification_service.py:482`) als auch im Compare-Standalone-Alarm-Pfad (`notification_service.py:575`) / When beide Pfade `render_official_alert_subject()` aufrufen / Then zeigen beide denselben detailtreuen Betreff mit Massiv-Name — keine Divergenz zwischen Trip und Compare.
  - Test: Test 7 im Test Plan.

## Known Limitations

- Pragmatische Lösung ohne formale Design-Vorlage (PO-Entscheidung 2026-07-11): die genaue Platzierung des Details im Typ-Tag (statt z.B. in `scope_label`) ist eine Tech-Lead-Wahl, vom PO über die obigen ACs bestätigt.
- **Vigilance-Detailtreue gilt generisch (PO-bestätigt 2026-07-11):** Die Regel
  greift für JEDE Vigilance-Bezeichnung, die reicher ist als das generische
  Typ-Wort — nicht nur `extreme_heat` („Extreme Hitze"), sondern auch
  `wind_gust` → Betreff zeigt **„Sturmböen"** statt „Sturm" (der genauere
  Météo-France-Begriff). Adversary-Randbefund F001, vom PO als gewollt bestätigt
  (mehr Detail = konsistent mit dem Feature-Zweck). Abgedeckt durch Test 8.
- **Betreff wird nicht gekürzt (bewusst):** `render_official_alert_subject` hat heute keine Längenbegrenzung (nur der SMS-Pfad `_sms_truncate` kürzt). Detail-Labels wie Massiv-Namen sind kurz; ein etwas längerer Betreff ist akzeptabel. Diese Scheibe führt **keine** neue Betreff-Truncation ein — ein solcher Mechanismus wäre ein eigenes Thema.
- Unbekannte Hazards (fallen in `_hazard_display` bereits auf `alert.label` zurück, `official_alerts.py:269-276`) sind von dieser Änderung nicht betroffen — sie zeigten das volle Label schon vorher.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Reine Formatierungs-/Fidelity-Korrektur innerhalb einer bestehenden Präsentationsfunktion (`_typ_tag`), kein neues Subsystem, kein neues Datenmodell-Feld, kein Architekturmuster-Wechsel.

## Changelog

- 2026-07-11: Initial spec created
