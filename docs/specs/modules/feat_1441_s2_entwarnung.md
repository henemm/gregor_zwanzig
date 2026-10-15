---
entity_id: feat_1441_s2_entwarnung
type: module
created: 2026-10-15
updated: 2026-10-15
status: draft
version: "1.0"
tags: [official-alert, entwarnung, alarm, trip, ortsvergleich, vier-kanaele, issue-1441]
---

# Entwarnung bei amtlichen Warnungen (#1441 Scheibe S2)

## Approval

- [ ] Approved

## Purpose

Sinkt oder endet eine amtliche Warnung (alle Quellen, nicht nur Lawine), meldet das System dies als **Entwarnung** über alle vier Kanäle (E-Mail, Telegram, SMS, Premium-SMS) in beiden Flächen (Trip-Alarm und Ortsvergleich-Alarm) — mit der Dringlichkeit des **alten** Werts. Ein Quellenausfall, eine Neuausgabe oder eine Folgeperiode ist nie eine Entwarnung; pro Nutzer kommt die Entwarnung nur einmal. Das Produkt liefert dabei nur Daten („Stufe 4 → 2", „beendet"), nie eine Handlungsempfehlung.

## Beschlossene Vorgaben (Product Owner)

- **13.10.2026:** Entwarnung für ALLE amtlichen Warnquellen, alle vier Kanäle, beide Flächen. Quellenausfall, Neuausgabe, Folgeperiode ist nie Entwarnung; pro Nutzer nur einmal.
- **Dringlichkeit des ALTEN Werts:** Kanalauswahl und Schwelle richten sich nach der alten Stufe (Entwarnung von „hoch" erreicht auch Premium-SMS).
- **15.10.2026:** Hat ein zugestelltes Briefing die niedrigere Stufe bzw. das Fehlen der Warnung bereits gezeigt, gilt der Nutzer als informiert — **kein** Entwarnungs-Alarm.
- Telegram-Kurzform folgt der SMS-Auswahl (beschlossen). Nur Daten, keine Handlungsempfehlung. Alle vier Kanäle sind gleichrangig.

## Source

- **Schicht:** Python-Core (`src/services/`, `src/output/renderers/alert/`) plus Validator unter `.claude/hooks/`. Keine Änderung an Go-API oder Frontend.
- **File:** `src/services/official_alert_allclear.py` (neu, Kern der Erkennung)
- **Neue Datei:** `src/services/official_alert_allclear.py` — reine Erkennungsfunktion
- **Identifier:** `detect_official_allclear(...)` (neu, `official_alert_allclear.py`), `get_official_alerts_with_sources(...)` (neu, `base.py`), geändert: `check_official_alert_triggers`, `record_official_alerts_reported`, `official_alert_state_entry`, `send_official_alert`, `send_multi_location_official_alert`, `urgency_from_official_transition`
- **Geänderte Dateien:** `src/services/official_alerts/base.py`, `src/output/renderers/alert/official_alerts.py`, `src/services/alert_briefing_anchor.py`, `src/services/alert_state.py`, `src/services/trip_alert.py`, `src/services/compare_official_alert.py`, `src/services/notification_service.py`, `src/services/alert_urgency.py`, `src/services/trip_report_scheduler.py`, `src/services/scheduler_dispatch_service.py`, `.claude/hooks/official_alert_mail_validator.py`

## Estimated Scope

Ehrliche Schätzung produktiver Zeilen (nur `src/` und der Validator unter `.claude/hooks/`; Tests und Doku zählen nicht):

| Datei | LoC (netto, ca.) | Inhalt |
|---|---|---|
| `src/services/official_alerts/base.py` | 60 | `get_official_alerts_with_sources(...)` → `{quelle: (ok, alerts)}` vor dem Merge, nach dem Fensterfilter; Signaturen der 37 Aufrufer unverändert |
| `src/services/official_alert_allclear.py` (neu) | 130 | Erkennung „gesenkt / vorzeitig beendet / nichts", Identität+Überlappung, Quellen-Gesundheit, `absent_since`-Bestätigung |
| `src/output/renderers/alert/official_alerts.py` | 150 | Gedächtnis-Eintrag um `source`/`scope`/`level`/`absent_since`/`ended_at`; Senk-/Tombstone-Schreibweg; Entwarnungs-Notice; Builder Trip + Ortsvergleich; Betreff, HTML, Plain, Telegram, SMS/Premium-SMS |
| `src/services/alert_briefing_anchor.py` | 50 | Briefing-Schreibpfad: neue Felder, Senken/Tombstone nach Zustellung bei gesunder Quelle |
| `src/services/alert_state.py` | 25 | GC abgelaufener `official_alert:`-Einträge |
| `src/services/trip_alert.py` | 90 | Quellenstatus, Erkennung, Rückgabe erweitern, `_send_official_alert_only` für reine Entwarnung, Gate/Schwelle/Retry nach alter Stufe, Senken nach Zustellung |
| `src/services/compare_official_alert.py` | 60 | `_detect`, `_record_state`, Stapel-Dringlichkeit inkl. alter Stufen |
| `src/services/notification_service.py` | 40 | Entwarnungen durch `send_official_alert` / `send_multi_location_official_alert` / `_dispatch_compare_official_*` reichen |
| `src/services/alert_urgency.py` | 10 | `urgency_from_official_transition` produktiv nutzen |
| `src/services/trip_report_scheduler.py` | 20 | Trip-Briefing (~:1806): Record-Pfad auch bei leerer Warnliste aufrufen (sonst nie Tombstone) und Quellen-Gesundheit des Briefing-Laufs durchreichen |
| `src/services/scheduler_dispatch_service.py` | 20 | Ortsvergleich-Briefing (~:690): dasselbe für den Briefing-Pfad des Ortsvergleichs |
| `.claude/hooks/official_alert_mail_validator.py` | 50 | Entwarnungs-Plausibilität |
| **Summe produktiv** | **~705** | |

- **LoC:** ~705 produktiv (Tabelle oben)
- **Files:** 12 produktive (1 neu), 4 bestehende Test-/Fixture-Anpassungen, 2 neue Testdateien (+ ggf. Kanal-Matrix), 4 Doku-Dateien + 1 ADR.
- **Effort:** high. **Risk:** HIGH — eine Schein-Entwarnung ist sicherheitskritisch (Wanderer läuft in eine fortbestehende Gefahr).
- **LoC-Limit:** Die Ursprungsschätzung (~450) war vor dem Briefing-Senk-Pfad (PO 15.10.) entstanden; ehrlich sind ~705 produktive Zeilen (Revision 1: zwei Briefing-Aufrufstellen ergänzt). Der Workflow braucht `workflow.py set-field loc_limit_override 800`. Spec-Schnitt in zwei Specs wird bewusst verworfen: beide Flächen teilen Erkennung, gemeinsames Gedächtnis und Briefing-Pfad; ein Schnitt lieferte zuerst ein Fundament ohne Nutzerwirkung und streckte die Freigabe. `/40` deckt ALLE ACs ab.

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `official_alerts/*` (Registry), `warn_egress` | Upstream | Quellen, Fehlschlag-/Nicht-zuständig-/Unvollständig-Marker pro Quelle |
| `AlertStateService` (`alert_state.py`) | Upstream | Melde-Gedächtnis `official_alert:`-Schlüssel |
| `alert_urgency.py` | Upstream | Dringlichkeit, Kanal-Schwelle (ADR-0046) |
| Ereignis-Identitäts-Gate, Retry-Backoff (`trip_alert.py`) | Upstream | Unverändert, aber mit alter Stufe als Eingabe |
| Trip-Briefing-Versand (#1614, `trip_report_scheduler.py`), Ortsvergleich-Briefing (`scheduler_dispatch_service.py`), Briefing-Reset (#1460 P2) | Downstream | Schreiben dasselbe Gedächtnis über `record_official_alerts_reported` |
| SMS-Token-Katalog (`sms_official_alert_tokens.md`), Renderer-Commit-Gate | Downstream | Token-Form, Mail-Validator |
| ADR-0043, 0016, 0046, 0082, 0086, 0089 | Entscheidungen | Grundsatz Entwarnung, additiver Typ, Kanal-Schwelle, „nicht bestimmbar ≠ Entwarnung", Erfolg = Zustellung, Lawine zweite Skala |

## Implementation Details

### 1. Gedächtnis-Schema (erweitert, abwärtskompatibel)

Schlüssel bleibt `official_alert:{id|region|label}:{hazard}:{valid_from}:{valid_to}` (`official_alert_state_key`). Wert bisher `{last_reported_value, reported_at, valid_from, valid_to}`; neu zusätzlich:

| Feld | Bedeutung |
|---|---|
| `source` | meldende Quelle (Name aus der Registry) zum Zeitpunkt der Meldung |
| `scope` | Ort bzw. Trip-Segment, auf das sich die Meldung bezieht (für Darstellung und Fensterabgleich) |
| `level` | alte Stufe in der Dringlichkeits-Skala (für Kanal-Schwelle der Entwarnung); `last_reported_value` bleibt der vergleichbare Rang (`comparable_level`, ADR-0089) |
| `absent_since` | Zeitstempel des ersten Laufs, in dem die Warnung bei gesunder Quelle fehlte |
| `ended_at` | Tombstone: Warnung gilt als beendet gemeldet (Rang 0) |

Einträge **ohne** `source` (Alt-Bestand) erzeugen nie eine Entwarnung (einmalige Lücke, bewusst; der Bestand läuft über `valid_to` aus und wird vom GC entfernt).

### 2. Pro-Quelle-Ergebnis (Variante C)

`get_official_alerts_with_sources(...)` liefert `{quelle: (ok, alerts)}` **nach** dem Fensterfilter und **vor** dem Quellen-Merge pro Gefahrenart. `ok` ist nur dann wahr, wenn die Quelle ohne Exception, ohne `fetch_status.failed`, nicht `not_covered` und nicht `fetch_incomplete` geantwortet hat. Das bisherige Aggregat-`unavailable` (`covering>0 and failed>=covering`) reicht nicht, weil es Teilausfall ausgleicht.

### 3. Erkennung (`official_alert_allclear.py`)

Abgleich nicht über den vollen Schlüssel, sondern über **Identität + Gefahrenart** (`_identity_hazard_prefix`) und **Zeitraum-Überlappung** mit dem aktuell abgefragten Fenster. Bewertet werden nur gespeicherte Einträge mit `source`, deren Zeitraum das Fenster überlappt und deren `ended_at` nicht gesetzt ist. Verglichen wird auf dem Pre-Merge-Satz der **meldenden** Quelle:

- aktueller Rang < gespeicherter Rang, Quelle `ok` → **gesenkt** (sofort, keine Bestätigung: der niedrigere Wert steht explizit in den Daten)
- keine passende Warnung, Quelle `ok`, `valid_to` noch in der Zukunft → **Kandidat „beendet"**: erster Lauf setzt `absent_since`, still; zweiter aufeinanderfolgender Lauf bestätigt → **vorzeitig beendet**. Taucht die Warnung dazwischen wieder auf, wird `absent_since` gelöscht.
- Quelle nicht `ok` → nichts (und `absent_since` unverändert, weil der Lauf keine Information liefert)
- sonst → nichts

### 4. Wirkung

Dringlichkeit und Kanal-Schwelle der Entwarnung kommen aus `urgency_from_official_transition(alte Stufe aus level, neue Stufe)` (max) — an der Wirkstelle (`split_by_threshold` / Kanalauswahl), nicht nur im Helfer. Ortsvergleich: Stapel-Max über Warnungen und alte Stufen der Entwarnungen. Retry-Backoff und Ereignis-Identitäts-Gate laufen mit der alten Stufe.

Nach **Zustellung** (ADR-0086): „gesenkt" → `last_reported_value`/`level` auf neuen Wert **senken**; „beendet" → Tombstone (`ended_at`, Rang 0). Expliziter Schreibweg, getrennt vom Revision-Merge (der weiter `max` behält). Fehlversand schreibt nichts → Wiederholung im nächsten Lauf.

### 5. Briefing-Schreibpfad (PO 15.10.)

`alert_briefing_anchor.record_official_alerts_reported` — aufgerufen vom Trip-Briefing (`trip_report_scheduler.py`) **und** vom Ortsvergleich-Briefing (`scheduler_dispatch_service.py`) — schreibt künftig `source`/`scope`/`level` mit (sonst gäbe es nach Briefing-Erstmeldung nie eine Entwarnung). Zusätzlich **senkt** es das Gedächtnis auf die im Briefing gezeigte Stufe bzw. setzt den Tombstone für eine nicht mehr gezeigte Warnung — **nur** nach erfolgreicher Zustellung des Briefings und **nur**, wenn die meldende Quelle im Briefing-Lauf `ok` war (sonst zeigt das Briefing „nicht abrufbar"; das ist keine Information über ein Ende). Gleiche Erkennungsfunktion, gleiche Ausfall-/Folgeperioden-/Fensterregeln. Beide Aufrufstellen rufen den Record-Pfad heute nur bei **nicht leerer** Warnliste auf — das muss entfallen (sonst kann ein Briefing nie einen Tombstone setzen), und sie reichen die Quellen-Gesundheit des Briefing-Laufs mit durch.

### 6. Wechselwirkung Briefing-Tombstone und `absent_since` (festgelegt)

- Briefing zeigt die Warnung **nicht mehr** (Quelle `ok`, zugestellt) → Tombstone wird gesetzt, `absent_since` gelöscht. Der nächste Alarm-Lauf findet `ended_at` und meldet nichts: das Briefing hat informiert. Reihenfolge (Alarm-Lauf 1 setzt `absent_since`, Briefing, Alarm-Lauf 2) ergibt damit genau **keine** Entwarnung — weder doppelt noch verschluckt (der Nutzer hat die Information im Briefing erhalten).
- Briefing zeigt die Warnung **noch** auf unveränderter Stufe (Quelle `ok`, zugestellt) → die Quelle hat die Warnung in diesem Lauf geliefert, die Abwesenheit ist damit **nicht** aufeinanderfolgend bestätigt: `absent_since` wird **gelöscht** (gleiche Regel wie „taucht wieder auf" in Abschnitt 3). Ablauf: Alarm-Lauf 1 abwesend (`absent_since` gesetzt) → Briefing zeigt Stufe 4 → `absent_since` gelöscht → Alarm-Lauf 2 abwesend: still, `absent_since` neu gesetzt → Alarm-Lauf 3 abwesend: Entwarnung „beendet". Begründung (Revision 1, Tech-Lead-Entscheid): Ein Flackern abwesend → anwesend → abwesend ist genau das, wogegen die Zwei-Lauf-Regel schützt, und der Nutzer hat die Warnung gerade im Briefing als aktiv gesehen. Die Entwarnung kommt höchstens einen Lauf später, nie fälschlich.
- Briefing zeigt eine **niedrigere** Stufe → Gedächtnis wird gesenkt; Alarm-Lauf findet gleichen Rang, nichts zu melden.

### 7. Darstellung (nur Daten, keine Empfehlung)

- **Mail (HTML + Plain):** eigener Abschnitt „Entwarnung" nach den Warnungen, je Eintrag Gefahr, Region/Ort, „Stufe alt → neu" bzw. „beendet". Betreff enthält „Entwarnung" (bei gemischter Nachricht: Warnung zuerst, dann „+ Entwarnung"). Marker-Header `X-GZ-Mail-Type: official-alert` bleibt.
- **Telegram:** gleicher Aufbau, Kurzform folgt der SMS-Form (beschlossen).
- **SMS / Premium-SMS — Token-Form (Tech-Lead-Entscheid):** Die Warn-Token (`sms_official_alert_tokens.md`) tragen `!` als Block-Marker und `{Kürzel}:{Stufenbuchstabe}`; Lawine (numerische Skala) `AV{Rang}`. Entwarnung bekommt einen **eigenen Block-Marker `+`** (GSM-7-Basiszeichen, 1 Septett, kein Konflikt mit `!`) und trägt den Übergang mit `>`:
  - gesenkt: `+TS:H>L` (Gefahrkürzel, alte Stufe, `>`, neue Stufe); Lawine numerisch `+AV4>2`
  - beendet: `+TS:H>0` bzw. `+AV4>0` (`0` ist als Endmarker eindeutig, weil Stufenbuchstaben `- L M H` bzw. Rang ≥ 1 sind)
  - Kürzel aus dem bestehenden Katalog (`src/output/tokens/hazard_symbols.py`, z. B. Gewitter `TS`, Hitze `HT`).
  - Folgetoken im Block ohne zweites `+`, getrennt durch Leerzeichen, wie beim `!`-Block.
  - Begründung: kein neues Kürzel pro Gefahr nötig (bestehender Katalog bleibt gültig, 1 Zeichen pro Gefahr bleibt gewahrt), nur ASCII/GSM-7-Basiszeichen (kein Emoji, keine Erweiterungstabelle wie `~`), ohne Zeitangabe kürzer als ein Warn-Token, und für den Leser ohne Legende als „von … auf …" lesbar. Aufhebung ist kein Befehl, sondern eine reine Zustandsangabe.

### 8. Gemeinsamer Lauf mit neuer Warnung

EINE Nachricht: Warnungen zuerst, Entwarnungs-Abschnitt (bzw. `+`-Block) danach; Dringlichkeit = Max aus Warnungen und alten Stufen der Entwarnungen. Bei SMS-Kürzung haben Warnungen Vorrang; fällt die Entwarnung der Kürzung zum Opfer, gilt sie als nicht zugestellt (kein Gedächtnis-Schreiben) und kommt im nächsten Lauf.

### 9. Festgeschriebene Test-Annahmen (aus TDD RED, Revision 1)

- Gedächtnisfelder: `source` == Registry-Name == `OfficialAlert.source`; `scope` nicht leer; `level` int (alte bzw. nach Senkung neue Stufe); `absent_since` truthy/falsy; `ended_at` truthy beim Tombstone. Nach Senken gilt `last_reported_value` == neuer Rang. Felder werden nur per `.get()` gelesen (Alt-Einträge ohne Felder bleiben ladbar).
- Erkennungsmerkmal: Wort „Entwarnung" in Mail-Betreff, Mail-HTML/-Plain und Telegram-Vollform; `+`-Block in SMS, Premium-SMS und Telegram-Kurzform; „beendet" für das vorzeitige Ende. Mail und Telegram zeigen den Übergang **mit Ziffern** (`4 → 2`), nicht nur mit Farbwörtern.
- Gemeinsame Nachricht: Warnung steht in Klartext und Betreff vor „Entwarnung"; `!`-Block vor `+`-Block.
- Ereignis-Identitäts-Gate: darf eine Entwarnung einer `wet`-Gefahr (z. B. Gewitter) nicht als Dublette der früheren Warnung verschlucken.
- Briefing-Zeitfenster im Testunterbau: Morgen-Briefing liegt bei Ortsstunde+3 (#1594); Alarm-Läufe im Test bei t0+60 min oder früher.

### 10. Reihenfolge der Umsetzung

ADR → Spec → RED (alle ACs) → `base.py` + Erkennung + Gedächtnis → Renderer → Trip-Verdrahtung → Ortsvergleich-Verdrahtung → Briefing-Senk-Pfad → GC → Validator.

## Expected Behavior

- **Input:** Melde-Gedächtnis des Nutzers (pro Trip bzw. `preset_id:loc_id`), Pro-Quelle-Ergebnisse des aktuellen Laufs, abgefragtes Fenster.
- **Output:** null oder mehr Entwarnungs-Notices („gesenkt" mit alt→neu, „beendet"), zusammen mit neuen Warnungen in einer Nachricht je Kanal.
- **Side effects:** Gedächtnis wird nur nach Zustellung gesenkt bzw. mit Tombstone versehen; `absent_since` wird gesetzt/gelöscht; GC entfernt abgelaufene Einträge.

## Acceptance Criteria

- **AC-1:** [Gesenkt] Given eine gemeldete amtliche Warnung der Stufe 4 und die meldende Quelle antwortet im aktuellen Lauf erfolgreich mit Stufe 2 für dieselbe Gefahr, denselben Ort und überlappenden Zeitraum / When der Alarm-Lauf läuft / Then erhält der Nutzer genau eine Entwarnung „Stufe 4 → 2" mit Gefahr und Region bzw. Ort, und das Gedächtnis steht danach auf Stufe 2.
  - Test: `tests/tdd/test_official_alert_allclear.py` — Gedächtnis mit Stufe 4, Quelle liefert 2; Entwarnung vorhanden, Text enthält „4" und „2", Gedächtnis gesenkt.

- **AC-2:** [Vorzeitig beendet, zwei Läufe] Given eine gemeldete Warnung mit `valid_to` in der Zukunft und die meldende Quelle antwortet erfolgreich, enthält die Warnung aber nicht mehr / When Lauf 1 stattfindet, Then bleibt es still und `absent_since` ist gesetzt; When Lauf 2 die Abwesenheit bestätigt, Then erhält der Nutzer eine Entwarnung „beendet" und das Gedächtnis trägt den Tombstone.
  - Test: `tests/tdd/test_official_alert_allclear.py` — nach Lauf 1 keine Nachricht, nach Lauf 2 genau eine „beendet"; taucht die Warnung zwischen den Läufen wieder auf, ist `absent_since` gelöscht und Lauf 2 still.

- **AC-3:** [Matrix 4 Kanäle × 2 Flächen] Given eine Entwarnung entsteht im Trip-Alarm bzw. im Ortsvergleich-Alarm / When sie versendet wird / Then kommt sie in beiden Flächen über jeden der vier Kanäle E-Mail, Telegram, SMS und Premium-SMS an — Premium-SMS ausdrücklich auch im Ortsvergleich — jeweils mit demselben Inhalt (Gefahr, Ort, alt → neu bzw. beendet) in kanalgerechter Form.
  - Test: `tests/tdd/test_official_alert_allclear_channels.py` — 4 × 2 parametrisiert, am echten Versandpfad (`send_official_alert` / `send_multi_location_official_alert`) mit aufgezeichnetem Transport, jede der acht Zellen prüft Zustellung und Inhalt.

- **AC-4:** [Dringlichkeit nach alter Stufe, an der Wirkstelle] Given eine Warnung der Stufe „hoch" sinkt auf „niedrig" / When die Entwarnung versendet wird / Then erreicht sie genau die Kanäle, die für „hoch" gelten (einschließlich Premium-SMS); eine Entwarnung von „niedrig" auf „keine" erreicht Premium-SMS nicht.
  - Test: `tests/tdd/test_official_alert_allclear_channels.py` — beobachtet, **welche Kanäle tatsächlich versenden** (Trip und Ortsvergleich), nicht nur den Rückgabewert von `urgency_from_official_transition`. Mutation: Dringlichkeit aus neuer statt alter Stufe → Test rot.

- **AC-5:** [Zwei-Nutzer-Isolation] Given zwei verschiedene Nutzer mit je eigenem Gedächtnis, nur Nutzer A hat die Warnung gemeldet bekommen / When die Entwarnung entsteht / Then erhält nur Nutzer A sie, Nutzer B bekommt nichts, und Nutzer Bs Gedächtnis bleibt unverändert; beide Flächen.
  - Test: `tests/tdd/test_official_alert_allclear.py` — zwei `user_id`, getrennte Datenordner, nie `"default"`.

- **AC-6:** [Teilausfall ist keine Entwarnung] Given die meldende (beste) Quelle fällt aus — Exception, `fetch_failed`, `not_covered` oder `fetch_incomplete` — und eine andere Quelle liefert leer / When der Alarm-Lauf läuft (auch über zwei Läufe) / Then entsteht keine Entwarnung und das Gedächtnis bleibt unverändert.
  - Test: `tests/tdd/test_official_alert_allclear.py` — vier Ausfallarten parametrisiert, zweite Quelle leer und gesund; das Aggregat-`unavailable` ist dabei `False`, damit der Test den Pro-Quelle-Schutz bewacht.

- **AC-7:** [Quellenwechsel der besten Quelle] Given die Warnung wurde von Quelle X (höchste Stufe) gemeldet und im aktuellen Lauf ist Quelle Y mit niedrigerer Stufe die beste für dieselbe Gefahrenart, Quelle X selbst liefert aber weiterhin Stufe 4 / When der Alarm-Lauf läuft / Then entsteht keine Entwarnung.
  - Test: `tests/tdd/test_official_alert_allclear.py` — verglichen wird auf dem Pre-Merge-Satz der meldenden Quelle; Gegenprobe: liefert X selbst Stufe 2, dann Entwarnung.

- **AC-8:** [Folgeperiode, Neuausgabe, Fenster] Given (a) eine Neuausgabe oder Folgeperiode mit neuem Zeitraum-Schlüssel für dieselbe Gefahr, (b) ein bereits vergangenes Trip-Segment oder (c) das Tagesfenster-Ende im Ortsvergleich / When der Alarm-Lauf läuft / Then entsteht in keinem der drei Fälle eine Entwarnung, weil der Abgleich über Identität+Gefahr und Zeitraum-Überlappung läuft und nicht überlappende Einträge nicht bewertet werden.
  - Test: `tests/tdd/test_official_alert_allclear.py` — drei Konstellationen, jeweils keine Entwarnung; Gegenprobe überlappender Zeitraum mit niedrigerer Stufe → Entwarnung.

- **AC-9:** [Planmäßiger Ablauf ist keine Entwarnung — Tech-Lead-Entscheid] Given eine gemeldete Warnung, deren `valid_to` erreicht oder überschritten ist / When die Warnung im Lauf nicht mehr erscheint / Then entsteht keine Entwarnung, und der abgelaufene Gedächtnis-Eintrag wird vom GC entfernt.
  - **Tech-Lead-Entscheid, keine PO-Vorgabe.** Begründung: Das Ende stand bereits in der Warnung selbst, der Nutzer kannte es; zudem ist ein planmäßiges Auslaufen am Feed nicht von Ausfall oder Rotation unterscheidbar. Die Entwarnung trägt dadurch nur dort Information, wo das Ende vorher nicht bekannt war (vorzeitig beendet, gesenkt). Wird mit dieser Spec freigegeben; abweichender Wunsch wäre eine Änderung dieser AC.
  - Test: `tests/tdd/test_official_alert_allclear.py` — `valid_to` knapp vor/auf jetzt → keine Nachricht; GC-Test in `tests/tdd/test_official_alert_allclear.py`: Eintrag mit `valid_to < jetzt` ist nach dem Lauf entfernt, `official_alert:`-Einträge mit Zukunft bleiben (inkl. `reset()`-Schonung).

- **AC-10:** [Nur einmal] Given eine zugestellte Entwarnung (gesenkt oder beendet) / When der nächste Lauf mit gleicher Lage stattfindet / Then kommt keine zweite Entwarnung, weil das Gedächtnis gesenkt bzw. der Tombstone gesetzt ist; steigt die Stufe später wieder, wird das als ganz normale neue Warnung gemeldet.
  - Test: `tests/tdd/test_official_alert_allclear.py` — zweimal derselbe Lauf: eine Nachricht; danach Stufe wieder 4 → reguläre Warnung (kein Entwarnungs-Abschnitt).

- **AC-11:** [Fehlversand wiederholt] Given der Versand der Entwarnung scheitert auf allen Kanälen / When der nächste Lauf stattfindet / Then wird die Entwarnung erneut versucht, weil nach Fehlversand kein Gedächtnis geschrieben wurde (ADR-0086).
  - Test: `tests/tdd/test_official_alert_allclear.py` — Transport schlägt fehl: Gedächtnis unverändert; nächster Lauf mit funktionierendem Transport liefert die Entwarnung.

- **AC-12:** [Gemeinsam mit neuer Warnung] Given im selben Lauf liegen eine neue Warnung und eine Entwarnung vor / When die Nachricht erzeugt wird / Then ist es EINE Nachricht je Kanal mit den Warnungen zuerst und dem Entwarnungs-Abschnitt danach, und die Dringlichkeit ist das Maximum aus beiden; bei SMS-Kürzung bleibt die Warnung erhalten, eine dabei verdrängte Entwarnung gilt als nicht zugestellt (kein Gedächtnis-Schreiben) und kommt im nächsten Lauf.
  - Test: `tests/tdd/test_official_alert_allclear_channels.py` — eine Nachricht, Reihenfolge, Max-Dringlichkeit; SMS knapp über der Renderer-Grenze: Warn-Token vorhanden, Gedächtnis der Entwarnung unverändert.

- **AC-13:** [Briefing informiert — keine Entwarnung, Trip UND Ortsvergleich] Given nach einem Alarm der Stufe 4 zeigt ein zugestelltes Briefing (Trip-Briefing bzw. Ortsvergleich-Briefing) bereits Stufe 2 bei erfolgreich antwortender meldender Quelle / When der nächste Alarm-Lauf stattfindet / Then entsteht keine Entwarnung, weil der Briefing-Schreibpfad das Gedächtnis auf Stufe 2 gesenkt hat. Gegenprobe: Given das Briefing zeigte „nicht abrufbar" bei ausgefallener meldender Quelle / When der nächste Alarm-Lauf bei gesunder Quelle Stufe 2 sieht / Then bleibt die Entwarnung möglich und wird gesendet.
  - Test: `tests/tdd/test_official_alert_allclear.py` — Briefing-Versand real über beide Aufrufstellen (Trip-Briefing `trip_report_scheduler.py`, Ortsvergleich-Briefing `scheduler_dispatch_service.py`); beide Fälle je Fläche; Briefing nicht zugestellt → Gedächtnis unverändert → Entwarnung kommt.

- **AC-14:** [Wechselwirkung Tombstone ↔ `absent_since`] Given Alarm-Lauf 1 sieht die Warnung bei gesunder Quelle nicht (`absent_since` gesetzt) / When danach ein zugestelltes Briefing ohne die Warnung den Tombstone setzt und Alarm-Lauf 2 folgt / Then kommt genau keine Entwarnung (weder doppelt noch verschluckt: das Briefing hat informiert). Umgekehrt: Given Alarm-Lauf 1 sieht die Warnung nicht (`absent_since` gesetzt) und das danach zugestellte Briefing zeigt sie bei gesunder Quelle noch mit unveränderter Stufe / When Alarm-Lauf 2 und Alarm-Lauf 3 die Warnung weiter nicht sehen / Then ist `absent_since` durch das Briefing gelöscht, Alarm-Lauf 2 bleibt still (erste Abwesenheit neu), und erst Alarm-Lauf 3 meldet die Entwarnung „beendet" — genau einmal.
  - Test: `tests/tdd/test_official_alert_allclear.py` — Ablauf Alarm-Lauf, Briefing, Alarm-Lauf (Tombstone-Fall) bzw. Alarm-Lauf, Briefing, Alarm-Lauf, Alarm-Lauf (Briefing zeigt Warnung noch); geprüft werden gesendete Nachrichten und `absent_since`/`ended_at`.

- **AC-15:** [Briefing schreibt die neuen Felder; Alt-Einträge] Given eine Warnung wird zuerst per Briefing gemeldet (nicht per Alarm) / When das Briefing zugestellt ist / Then enthält der Gedächtnis-Eintrag `source`, `scope` und `level`, und eine spätere Absenkung erzeugt eine Entwarnung; Given ein Alt-Eintrag ohne `source` / When die Lage sinkt oder endet / Then entsteht nie eine Entwarnung (einmalige Lücke, bewusst).
  - Test: `tests/tdd/test_official_alert_allclear.py` — Eintrag nach realem Briefing-Versand enthält die drei Felder; Alt-Eintrag ohne `source` → still. Mutation: Briefing-Pfad schreibt keine Felder → Test rot.

- **AC-16:** [Darstellung] Given eine Entwarnung wird versendet / When die Nachricht erzeugt wird / Then enthält die Mail (HTML und Plain) einen eigenen Abschnitt „Entwarnung" mit Gefahr, Region/Ort und „Stufe alt → neu" bzw. „beendet", der Betreff das Wort „Entwarnung", Telegram denselben Inhalt in SMS-Kurzform, und SMS/Premium-SMS den GSM-7-Block `+TS:H>L` (gesenkt), `+AV4>2` (Lawine) bzw. `+TS:H>0` (beendet) — ohne Emoji, nur ASCII, ohne Handlungsempfehlung.
  - Test: `tests/tdd/test_official_alert_allclear_channels.py` — Renderer-Ausgaben je Kanal; `sms.isascii()`, Länge innerhalb der Renderer-Grenze des Kanals (SMS 140, Premium-SMS 153), keines der Wörter `sicher`, `kannst`, `empfehlen`, `gefahrlos`, `aufbrechen`, `losgehen` (Groß-/Kleinschreibung egal). Staging: `official_alert_mail_validator.py` bestanden gegen echt zugestellte Staging-Mail (Exit 0).

- **AC-17:** [Scope-Grenze MeteoAlarm AllClear] Given eine amtliche Meldung mit `responseType: AllClear` (DE) / When die Warnungen ausgewertet werden / Then wird sie weiterhin verworfen und löst keine Entwarnung aus; nur das Verschwinden bei gesunder Quelle nach AC-2 oder die Absenkung nach AC-1 trägt.
  - Test: `tests/tdd/test_official_alert_allclear.py` — AllClear-Meldung in der DE-Quelle ändert das Ergebnis nicht.

## Test Plan

Kern-Schicht (deterministisch, ohne Netz; aufgezeichnete Quell-Antworten als Fixtures):

- [ ] `tests/tdd/test_official_alert_allclear.py` — Erkennung und Gedächtnis: AC-1, AC-2, AC-5 bis AC-11, AC-13 bis AC-15, AC-17
- [ ] `tests/tdd/test_official_alert_allclear_channels.py` — Versandpfade beider Flächen, vier Kanäle, Dringlichkeit an der Wirkstelle, Darstellung: AC-3, AC-4, AC-12, AC-16
- [ ] Bewusst umgestellte Alt-Tests (Abschnitt unten): `tests/test_avalanche_report_escalation.py` AC-13, `tests/tdd/test_official_alert_revision_dedup.py` `test_f004`

Live-Schicht (`/e2e-verify`): echt zugestellte Staging-Entwarnungsmail, `.claude/hooks/official_alert_mail_validator.py` Exit 0 (AC-16).

## Bewusst geänderte Alt-Tests

Die folgenden Tests bewachen heute „Absenkung still, Höchstwert bleibt". Revision 1 (nach TDD RED): Ihre **Urteils-Zusicherungen bleiben stehen** — das reine Revisions-Urteil meldet eine Absenkung weiterhin nicht als *neue Warnung*, und der Revision-Merge behält `max` (sonst ginge der f004-Mutationsschutz verloren). Das neue Soll „Entwarnung, Gedächtnis gesenkt" tragen **zusätzliche End-to-End-Tests** am echten Alarmpfad:

| Test | Alt | Neu |
|---|---|---|
| `tests/test_avalanche_report_escalation.py` :151 | Urteil `melden=False` bei Absenkung | unverändert |
| dieselbe Datei :159/:178 | „Absenkung still, Höchstwert bleibt" | Begründung umformuliert: das Urteil schreibt nichts, der Revision-Merge senkt nie; gesenkt wird nach Zustellung der Entwarnung |
| dieselbe Datei, **neu** `test_ac13_nachtrags_absenkung_4_auf_2_ergibt_entwarnung_und_senkt_das_gedaechtnis` | — | echter Trip-Alarmlauf mit aufgezeichneten Bulletins: `+AV4>2`, Gedächtnis auf 2 |
| `tests/tdd/test_official_alert_revision_dedup.py` `test_f004` (:459) | Höchstwert wird nicht gesenkt | `max`-Zusicherung bleibt, Begründung neu |
| dieselbe Datei, **neu** `test_f004_sinkende_stufe_bei_gesunder_meldender_quelle_ergibt_entwarnung_und_senkt` | — | Revision 3→2 am echten Alarmpfad: Entwarnung, Gedächtnis auf 2 |
| dieselbe Datei :527 (Trip), :603/:615 (Compare) | Ketten mit konstanter Stufe | unverändert |

Begründung: Der Höchstwert-Schutz war eine S1-Begrenzung (Adversary F003, Helfer ohne Aufrufer), keine Produktentscheidung gegen die Entwarnung.

## Weitere betroffene Tests (nicht umzudrehen, aber nachlaufen lassen)

`tests/tdd/test_alert_state_briefing_reset.py` (AC-20..23, :853 Fehlversand-Gedächtnis, :935-1050), `test_issue_1088_official_alert_triggers.py`, `test_official_alert_dedup_timespan.py`, `test_official_alert_time_window.py`, `test_alarm_amtliche_warnungen_kette.py`, `test_compare_official_alert*.py`, `test_alert_change_urgency_grading.py:303`, `test_avalanche_official_alert_channels.py`, `test_alarm_totalausfall_wird_wiederholt.py`; Fixtures `tests/tdd/_alarm_amtlich_fixtures.py`, `tests/helpers/official_alert_gate_fixtures.py`.

## E2E- und Staging-Strecke

Mail-Validator ist `.claude/hooks/official_alert_mail_validator.py` (Header `X-GZ-Mail-Type: official-alert`), erweitert um Entwarnungs-Plausibilität (alte Stufe > neue Stufe bzw. „beendet", Abschnitt „Entwarnung" vorhanden, Betreff enthält „Entwarnung", keine Handlungsempfehlung). **Nicht** der Compare- oder der Briefing-Validator. Prüfung gegen echt zugestellte Staging-Mail über einen Wegwerf-Nutzer (`gregor-test+…`), mit Test-Trip, kein Sammelversand. Das Renderer-Commit-Gate greift (Modus-Matrix-Test und Validator frisch grün).

## Doku-Lieferumfang

- Neue ADR `docs/adr/0090-entwarnung-amtlicher-warnungen.md` (nächste freie Nummer nach 0089) plus Eintrag in `docs/adr/README.md` (Drift-Test `tests/test_adr_index_drift.py`). Inhalt: Entwarnung für alle Quellen, Variante C+D, Dringlichkeit nach altem Wert, Briefing senkt das Gedächtnis, Ablauf ist keine Entwarnung (Tech-Lead-Entscheid), ergänzt ADR-0016/0043/0089.
- Nachzug `docs/specs/modules/avalanche_report_bulletin.md` (Abschnitt 8, AC-13, Known Limitations, Changelog), `docs/specs/modules/feat_1681_meteoalarm_de.md` (AC-5, Known Limitations, Out of Scope: Aufhebung führt über das Verschwinden bei gesunder Quelle zur Entwarnung, nicht über AllClear), `docs/specs/modules/sms_official_alert_tokens.md` (`+`-Block, Entwarnungs-Token).

## Known Limitations

- **Alt-Bestand ohne `source`:** einmalige Lücke — bereits gemeldete Warnungen aus der Zeit vor S2 erzeugen keine Entwarnung (bewusst, im Zweifel still).
- **Verzögerung bei „beendet":** Bestätigung in zwei aufeinanderfolgenden Läufen kostet ein Prüfintervall (Schutz gegen erfolgreich-aber-unvollständige Antworten); „gesenkt" kommt sofort.
- **Planmäßiges Ende** wird nicht gemeldet (AC-9, Tech-Lead-Entscheid).
- **Gedächtnis ohne Segment-Bezug im Alt-Format:** Ort/Etappe der Entwarnung stammt aus `scope`; Einträge ohne `scope` bleiben still.
- **Briefing ohne gesunde Quelle** senkt nicht; dann kann eine spätere Entwarnung doppelt zur Briefing-Anzeige wirken — bewusst die sichere Richtung.
- Erfolgreich-aber-fälschlich-leere Antworten einer Quelle über zwei Läufe hinweg sind nicht erkennbar; das Restrisiko ist durch die Zwei-Läufe-Bestätigung klein, nicht null.

## Out of Scope

- MeteoAlarm `responseType: AllClear` auswerten (bleibt verworfen, AC-17).
- Hauseigene Wetter-Entwarnung (Gewitter etc.) — bereits #1503/ADR-0043.
- Handlungsempfehlungen („jetzt wieder gehbar").
- Änderung der Warnerkennung (neue/gestiegene Warnungen), Kanal-Schwellen, Go-API oder Frontend.
- Migration des Alt-Bestands.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** ADR-0090 (neu, mit dieser Scheibe)
- **Rationale:** Keine bestehende ADR regelt die Entwarnung amtlicher Warnungen (0043 nur hauseigene Wetterwerte, 0016/0089 berührt). Ausfallsicherheit, Gedächtnis-Schema und Briefing-Wechselwirkung sind übergreifende Entscheidungen und gehören dokumentiert, damit sie nicht still rückgängig gemacht werden.

## Changelog

- 2026-10-15: Revision 1 (v1.1) nach TDD RED: Widerspruch AC-14 ↔ Abschnitt 6 aufgelöst (Briefing zeigt Warnung noch ⇒ `absent_since` gelöscht, „beendet" erst im übernächsten Alarm-Lauf); AC-13 ausdrücklich für Trip- UND Ortsvergleich-Briefing; Briefing-Aufrufstellen `trip_report_scheduler.py`/`scheduler_dispatch_service.py` in Source und Scope (~705 LoC); Gewitter-Kürzel `TS` statt `TH`; SMS-Grenze = Renderer-Grenze statt 160; Alt-Test-Tabelle an tatsächliche Umstellung angepasst; Test-Annahmen festgeschrieben (Abschnitt 9).
- 2026-10-15: Initial spec created (v1.0, draft). Grundlage: Kontext-Dokument `docs/context/feat-1441-s2-entwarnung.md`, PO-Entscheide 13.10. und 15.10.2026.
