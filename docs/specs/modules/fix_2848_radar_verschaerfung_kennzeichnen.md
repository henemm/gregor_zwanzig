---
entity_id: fix_2848_radar_verschaerfung_kennzeichnen
type: module
created: 2026-11-08
updated: 2026-11-08
status: implemented
workflow: fix-2848-radar-alarm-dreifach
version: "1.0"
tags: [alarm, nowcast, radar, verschaerfung, kanal-paritaet, i18n]
---

# Radar-Verschärfungs-Alarm kennzeichnen (Issue #2848)

## Approval

- [x] Approved — automatische Spec-Freigabe im Auto-Modus (`workflow.py approvals`: spec · auto · 2026-11-08T09:45); fachliche Grundlage: PO-Entscheid Option B vom 2026-11-08 per AskUserQuestion (`docs/context/fix-2848-radar-alarm-dreifach.md`).

## Purpose

Am 24.08.2026 erhielt der Nutzer für denselben Regen drei Radar-Alarme (12:22, 12:37, 13:07), die
alle gleich aussahen („Regen in 53/38/8 Min", gleiche Ereigniszeit) und wie ein dreifacher
Doppel-Alarm wirkten. Die Analyse (`docs/context/fix-2848-radar-alarm-dreifach.md`, Prod-Journal)
zeigt: **kein Defekt der Entdopplung.** Lauf 2 (1,0 → 3,1 mm) und Lauf 3 (3,1 → 7,3 mm) waren
gewollte Mengen-Durchbrüche nach #2065; Lauf 12:52 (5,2 mm, Faktor 1,68) blieb korrekt still.

PO-Entscheid 2026-11-08 (Option B): Der Durchbruch-Mechanismus bleibt **unverändert**. Ein
Radar-Alarm, der per Mengen-Durchbruch durchkommt, sagt künftig ausdrücklich, dass es **dasselbe
Ereignis ist und jetzt stärker**, mit den beiden Zahlen — sinngemäß „Dasselbe Ereignis, jetzt
stärker: 7,3 statt 3,1 mm" — in allen vier Kanälen mit demselben Inhalt (ADR-0095).

## Source

- **File:** `src/services/alert_gate.py` (`GateResult`, `check_event_identity_gate`)
- **File:** `src/services/trip_alert.py` (`TripAlertService.check_radar_alerts`, ~2441-2474 und ~2818-2900)
- **File:** `src/services/notification_service.py` (`RadarAlertRequest`, `send_radar_alert`)
- **File:** `src/output/renderers/alert/model.py` (`AlertMessage`), `src/output/renderers/alert/render.py`
  (`_onset_mail`, `_render_telegram_onset`, `render_sms`)
- **File:** `src/i18n/messages/de/alarm.json`, `src/i18n/messages/en/alarm.json`
- **File:** `src/services/alert_log.py` (`append_entry`, additive Felder)
- **Identifier:** neues Kennzeichen „Verschärfung desselben Ereignisses" (Arbeitstitel
  `AlertMessage.verschaerfung`, Wertepaar `(basis_mm, menge_mm)`)

> Schicht: ausschließlich Python-Core (`src/services/`, `src/output/`, `src/i18n/`). Kein Go-,
> kein Frontend-Anteil. Die Go-API liest den Alarmlog; die neuen Log-Felder sind additiv (Muster
> `is_addendum`), Entwickler prüft vor dem Merge, dass die Go-Seite unbekannte Felder toleriert.

> **Querschnitts-Prüfpunkte**
> - **Trip/Ortsvergleich-Teilung:** Die Renderer (`render.py`, `model.py`) sind geteilt (ADR-0021);
>   das Kennzeichen ist dort ein optionales Feld, das **nur gesetzt** wird, wenn der Aufrufer es
>   setzt. Der Mengen-Durchbruch (#2065) existiert nur im Trip-Pfad (`radar_overtakes_cooldown`
>   wird ausschließlich in `trip_alert.py` aufgerufen; im Ortsvergleich ist er PO-zurückgestellt).
>   Der Ortsvergleich setzt das Kennzeichen daher **nie**; sein Radar-Alarm bleibt byte-identisch.
>   Es entsteht kein Trip-only-Renderer, also keine Pendant-Verletzung.
> - **Mandantentrennung:** Es werden keine neuen Nutzerdaten gespeichert außer zwei additiven
>   Zahlenfeldern im bestehenden Alarmlog des Nutzers; `user_id` kommt wie bisher aus dem Dienst
>   (`self._user_id`), nie `"default"`. Test mit zwei Nutzern (AC-9).
> - **Kanäle:** E-Mail · Telegram (Langform und Kurzform) · SMS · Premium-SMS — alle vier benannt.

## Scope

- **In Scope:** Kennzeichnung des Radar-Folge-Alarms nach Mengen-Durchbruch (#2065) im Trip-Pfad,
  in allen vier Kanälen (E-Mail, Telegram, SMS, Premium-SMS), DE/EN; zwei additive Alarmlog-Felder;
  Wächter-Nachbau des 24.08.-Ablaufs; Doku des SMS-Tokens in `sms_format.md`/`premium_sms_format.md`.
- **Out of Scope:** Änderung des Durchbruch-Verhaltens (wann ein Alarm durchkommt), Deckel je Ereignis
  (Option C), Ortsvergleich-Kennzeichnung (#2065 wirkt dort nicht), Kennzeichnung reiner Stufen-Eskalation.

## Estimated Scope

- **LoC:** ~150-200 (Produktivcode ~90, i18n ~6, Tests ~100-150 in eigenen Dateien)
- **Files:** 7 Produktiv-/Katalogdateien + 2 Testdateien
- **Effort:** medium (vier Kanäle, i18n, Längengrenze SMS, Mail-Validator)

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `alert_gate.radar_overtakes_cooldown` / `last_nowcast_precip_mm` | function | liefern Vergleichsbasis (Y) und Durchbruch-Entscheidung (#2065); **unverändert** |
| `alert_gate.check_event_identity_gate` | function | findet den früheren Alarm DESSELBEN Ereignisses; wird um ein Ergebnisfeld erweitert, Entscheidung selbst unverändert |
| `trip_alert.py::_mengen_ueberholt`, `_menge_mm` (= `result.window_precip_mm`) | locals | Basis Y = `_basis_mm`, aktuelle Menge X = `_menge_mm`; beide stehen an der Stelle des Durchbruchs bereits zur Verfügung |
| `RadarAlertRequest` → `OnsetEvent`/`AlertMessage` | DTO | Transportweg bis in die Renderer (Muster `addendum_reference`, #2018) |
| `render.py::render_sms` | function | reservierte Präfix-Länge (Muster `_ADDENDUM_SMS_PREFIX`), Längengarantie aus der bestehenden Kürzungslogik |
| `i18n` Katalog `alarm.json` (de/en) | catalog | Nutzertext nur über Katalog (`docs/reference/i18n_konventionen.md`) |
| `tests/helpers/alarm_pruefstrecke.py::AlarmPruefstrecke` | test helper | Mehrlauf-Nachbau gegen echten Code (`docs/specs/modules/alarm_pruefstrecke.md`) |
| `fix_2065_verschaerfung_ueberholt_sperre.md`, `feat_2050_s4c_ein_ereignis_ein_alarm.md`, `fix_2009_nowcast_vorlauf.md` | Specs | Vorgänger; Durchbruch-Logik darf nicht verändert werden |

## Implementation Details

```
1. Gate (alert_gate.py)
   GateResult bekommt ein additives Feld (Default False), z. B. `ist_mengen_verschaerfung`.
   check_event_identity_gate setzt es im Eskalationszweig (der zuerst geprueft wird) auf True,
   wenn
        quantitative_escalation == True
    UND ein Registereintrag desselben Ereignisses gefunden wurde (match != None)
    UND match["source"] == "nowcast"   (frueherer Alarm war ein Radar-Alarm)
    UND NICHT addendum_direction       (Nachtrags-Zweig #2018/#2050 S4c bleibt unveraendert).
   Entscheidung `allowed` und alle Rueckgabewege bleiben unveraendert; nur Zusatzinformation.
   Grund: ohne gefundenen Vorgaenger (anderes Ereignis, Register leer) waere "dasselbe Ereignis"
   eine falsche Behauptung, obwohl die Sperrzeit ueberholt wurde.

2. Trip-Pfad (trip_alert.py, nach check_event_identity_gate, vor send_radar_alert)
   Ist `_identity_gate.ist_mengen_verschaerfung`, wird das Wertepaar
   (Y = _basis_mm, X = _menge_mm) in den RadarAlertRequest geschrieben
   (neue optionale Felder, Default None; Muster addendum_reference).
   Nur wenn beide Zahlen vorliegen und X > Y; sonst kein Hinweis (fail-soft: lieber kein Hinweis
   als ein falscher). Entscheidung "senden oder nicht" wird NICHT beruehrt.

3. Transport (notification_service.py)
   RadarAlertRequest -> OnsetEvent/AlertMessage: Wertepaar unveraendert durchreichen.
   _dispatch_alert_message rendert wie bisher je Kanal aus derselben AlertMessage;
   sms_body geht an SMS, Premium-SMS UND Telegram-Kurzform (ein Text, kein zweiter Renderer).

4. Renderer (render.py) - nur bei gesetztem Kennzeichen, sonst byte-identisch
   - E-Mail: eigene Hinweis-Box (wie Cooldown-/Nachtrags-Box, gleiche Zeile-fuer-Zeile-
     Reihenfolge-Regeln), Text aus Katalog: DE "Dasselbe Ereignis, jetzt staerker: 7,3 statt
     3,1 mm" / EN "Same event, now stronger: 7.3 instead of 3.1 mm"; Plaintext-Teil traegt
     dieselbe Zeile. Zahlenformat der Nutzersprache (DE Komma, EN Punkt), eine Nachkommastelle.
   - Telegram-Langform: eigene Zeile zwischen Kopf und Detailzeile (wie addendum_reference).
   - SMS / Premium-SMS / Telegram-Kurzform: Kurzform-Token, nie uebersetzt (ADR-0104),
     ASCII/GSM-7: `UP 3.1>7.3 ` direkt nach dem Ortskopf vor dem Radar-Token; Zeichen reserviert
     vom Limit wie `_ADDENDUM_SMS_PREFIX` (Limit - Praefixlaenge), damit die Gesamtlaenge
     garantiert <= Limit (160) bleibt und zuerst die vorhandenen Zusatz-Token (Zonen, Marker)
     weichen, nie Kopf/Radar-Token. Das Token ist in docs/reference/sms_format.md und
     premium_sms_format.md zu dokumentieren.
   - Keine Handlungsempfehlung im Text: nur Daten (Produktregel).
   - Zahlen X und Y sind genau die beiden Werte, die den Durchbruch ausgeloest haben
     (`window_precip_mm` des Laufs vs. zuletzt gemeldete Menge). Sie koennen vom
     `R<mm>`-Token der SMS (Stunde ab Beginn) abweichen; das ist gewollt, weil nur diese
     beiden Zahlen den Durchbruch erklaeren (siehe Known Limitations).

5. Alarmlog (alert_log.append_entry)
   Optional, additiv, nur bei gesetztem Kennzeichen: `escalation_from_mm`, `escalation_to_mm`
   (Muster is_addendum: Absenz = Normalfall, Alt-Eintraege schema-identisch). Zweck: der
   Durchbruch ist im Log ohne Journal-Archaeologie nachvollziehbar (am 24.08. fehlte
   `precip_mm` im Eintrag). Read-Modify-Write bleibt gewahrt, da append_entry nur anhaengt.
```

## Expected Behavior

- **Input:** Trip-Radar-Lauf, bei dem `radar_overtakes_cooldown` (Faktor >= 2 UND >= 2 mm gegen die
  zuletzt gemeldete Menge) die Sperrzeit/Entdopplung überholt UND der Vorgänger im Ereignis-Register
  ein Radar-Alarm desselben Ereignisses ist.
- **Output:** Derselbe Alarm wie heute, in allen konfigurierten Kanälen ergänzt um genau einen
  Hinweis „Dasselbe Ereignis, jetzt stärker: X statt Y mm" (Kurzform in SMS/Premium-SMS).
- **Side effects:** Zwei additive Zahlenfelder im Alarmlog-Eintrag dieses Alarms. Keine Änderung an
  Sperrzeit, Basis-Buchung (`record_nowcast_sent`), Register-Buchung, Tagesbudget oder
  Zustellentscheidung.

## Acceptance Criteria

- **AC-1:** Durchbruch-Verhalten unverändert, Nachbau 24.08. Given ein Trip mit Radar-Alarm im
  Kanalprofil und die Prüfstrecke fährt vier Läufe nacheinander mit gleichem Regenbeginn und
  Mengen 1,0 → 3,1 → 5,2 → 7,3 mm im Abstand von 15 Minuten / When alle vier Läufe durchlaufen /
  Then werden genau drei Alarme zugestellt (Lauf 1, 2 und 4) und der Lauf mit 5,2 mm bleibt still —
  dieselbe Zahl und Reihenfolge wie vor dieser Änderung; die Vergleichsbasis nach Lauf 2 ist 3,1 mm.
  - Test: Mehrlauf-Nachbau gegen den echten Code in der `AlarmPruefstrecke`; belegt, dass kein Deckel
    und keine verschärfte Entdopplung eingeführt wurde (Fehlerrichtung „Alarm bleibt aus" verboten).
    Muss auf dem Stand VOR der Änderung ebenfalls grün sein (Wächter), danach weiter grün.

- **AC-2:** Kennzeichnung in allen vier Kanälen. Given der Nachbau aus AC-1 mit E-Mail, Telegram,
  SMS und Premium-SMS als Kanälen / When Lauf 2 (1,0 → 3,1 mm) und Lauf 4 (3,1 → 7,3 mm)
  zugestellt werden / Then trägt jeder dieser beiden Alarme in jedem der vier Kanäle die Aussage
  „dasselbe Ereignis, jetzt stärker" mit den beiden Zahlen (Lauf 2: 3,1 statt 1,0; Lauf 4: 7,3 statt
  3,1) — in E-Mail und Telegram als Satz, in SMS und Premium-SMS in der Kurzform `UP 1.0>3.1` bzw.
  `UP 3.1>7.3`.
  - Test: Alle vier Kanäle werden über die Prüfstrecke an lokalen Stubs abgegriffen (kein echter
    Versand); der Text wird je Kanal auf Aussage UND beide Zahlen geprüft, nicht auf Dateiinhalt.

- **AC-3:** erster Alarm bleibt unverändert. Given derselbe Nachbau / When Lauf 1 (erster Alarm
  des Ereignisses, keine Vorgängermeldung) zugestellt wird / Then enthält er in keinem Kanal einen
  Verschärfungs-Hinweis, und sein Text ist byte-identisch zum Text vor dieser Änderung.
  - Test: Vergleich des gerenderten Alarms von Lauf 1 mit einem Alarm ohne Kennzeichen (gleicher
    Aufbau) in allen vier Kanälen.

- **AC-4:** nur echte Verschärfung desselben Ereignisses. Given zwei Konstellationen, in denen die
  Sperrzeit mengenmäßig überholt wird, aber (a) kein früherer Radar-Alarm desselben Ereignisses im
  Register steht (z. B. anderes Ereignis zu anderer Beginnzeit) bzw. (b) der Vorgänger eine amtliche
  Warnung oder ein Abweichungsalarm war / When der Alarm zugestellt wird / Then erscheint kein
  „dasselbe Ereignis, jetzt stärker"-Hinweis (bei (b) bleibt der bestehende Nachtragstext
  „Ergänzung zu …" unverändert).
  - Test: Zwei Prüfstrecken-Szenarien mit Positivkontrolle (derselbe Aufbau mit gefundenem
    Radar-Vorgänger trägt den Hinweis), damit das Ausbleiben nicht an einer Nebenbedingung hängt.

- **AC-5:** SMS und Premium-SMS innerhalb der Grenze. Given ein Verschärfungs-Alarm mit langem
  Ortsnamen, Ende-Angabe und Regenzonen-Kürzeln / When die SMS gerendert wird / Then ist sie höchstens
  160 Zeichen lang, enthält das Token `UP <Y>><X>`, den Ortskopf und das Radar-Token, und verliert
  bei Platzmangel zuerst Zusatz-Token (Zonen, Marker), nie den Hinweis; Premium-SMS trägt denselben
  Text und hält ihre eigene Grenze ebenfalls ein.
  - Test: Rendern mit Extrem-Eingaben (lange Namen, zweistellige mm-Werte), Längenprüfung gegen 160
    und gegen die Premium-SMS-Grenze (`docs/reference/premium_sms_format.md`), GSM-7-Zeichensatz.

- **AC-6:** zweisprachig. Given ein Nutzer mit Sprache Englisch und ein Nutzer mit Sprache Deutsch /
  When beide denselben Verschärfungs-Alarm (3,1 → 7,3 mm) erhalten / Then lautet der Hinweis in der
  E-Mail und in der Telegram-Langform für den englischen Nutzer „Same event, now stronger: 7.3
  instead of 3.1 mm" (englische Zahlenform), für den deutschen „Dasselbe Ereignis, jetzt stärker:
  7,3 statt 3,1 mm"; das SMS-Token `UP 3.1>7.3` ist für beide identisch (Kurzform wird nie übersetzt).
  - Test: Rendern mit `lang="de"` und `lang="en"`; zusätzlich Katalog-Paritätstest
    (neue Schlüssel in beiden Sprachen vorhanden), kein deutscher Text im englischen Alarm.

- **AC-7:** Radar-Mail besteht weiter den Validator. Given eine auf Staging zugestellte
  Verschärfungs-Mail im Test-Postfach / When `uv run python3 .claude/hooks/radar_alert_mail_validator.py`
  läuft / Then endet er mit Exit 0 (Segment-Label, Onset-Zeit, Intensität und Cooldown-Hinweis
  weiter vorhanden, Hinweis steht zusätzlich).
  - Test: Live-E2E über echte Staging-Zustellung (Stalwart-Test-Postfach), nur Exit 0 gilt als bestanden.

- **AC-8:** Ortsvergleich unverändert. Given ein Ortsvergleich mit Radar-Alarm, dessen Menge sich
  zwischen zwei Läufen verdoppelt / When der Radar-Alarm des Ortsvergleichs zugestellt wird / Then
  trägt er in keinem Kanal einen Verschärfungs-Hinweis, und sein Text ist byte-identisch zum Text
  vor der Änderung (#2065 wirkt dort bewusst nicht).
  - Test: Ortsvergleich-Radar-Alarm gerendert/zugestellt über die vorhandene Test-Strecke und
    Byte-Vergleich mit dem Alarm vor der Änderung; zusätzlich Aufrufer-Test: der Ortsvergleichs-Pfad
    kennt das Kennzeichen nicht.

- **AC-9:** Mandantentrennung. Given zwei Nutzer mit je einem eigenen Trip und eigener
  Vorgängermeldung (Nutzer A: 3,1 mm, Nutzer B: 9,0 mm) / When für beide derselbe Lauf mit 7,3 mm
  durchläuft / Then bekommt nur A einen Verschärfungs-Alarm „7,3 statt 3,1 mm" (B: 7,3 gegen 9,0 ist
  keine Verschärfung, kein Durchbruch, kein Hinweis), und kein Zahlenpaar stammt aus den Daten des
  anderen Nutzers.
  - Test: zwei verschiedene `user_id`, getrennte Datenverzeichnisse, Prüfung von Alarmtext und
    Alarmlog beider Nutzer.

- **AC-10:** Alarmlog nachvollziehbar. Given ein Verschärfungs-Alarm wurde zugestellt / When der
  Alarmlog des Nutzers gelesen wird / Then trägt genau dieser Eintrag die zusätzlichen Felder
  `escalation_from_mm` und `escalation_to_mm` mit den Werten aus dem Alarm; alle anderen Einträge
  (auch Radar-Erstalarme und Altbestand) tragen die Felder nicht und bleiben unverändert erhalten.
  - Test: Log nach dem Nachbau lesen; vorhandene Alt-Einträge vor/nach dem Anhängen unverändert
    (Read-Modify-Write mit Merge, kein Replace).

## Test Plan

Kern-Schicht (deterministisch, ohne Netz, **kein** `Mock()`/`patch()`/`MagicMock`):

- `tests/tdd/test_radar_verschaerfung_kennzeichnung_mehrlauf.py` (neu): AC-1 bis AC-4, AC-8, AC-9,
  AC-10 über `AlarmPruefstrecke` (echte `RadarNowcastService`-Unterklasse als DI-Naht, wie
  `test_alarm_szenario_ein_ereignis_ein_alarm.py`), Loopback-Stubs für alle vier Kanäle.
  AC-1 wird zuerst als Wächter gegen den unveränderten Code grün nachgewiesen; die Kennzeichnungs-ACs
  sind RED vor der Implementierung (Nutzersicht: Alarm von 7,3 mm sieht aus wie der erste).
- `tests/tdd/test_radar_verschaerfung_kennzeichnung_renderer.py` (neu): AC-5 (Längen, GSM-7) und AC-6
  (DE/EN, Katalog-Parität) direkt gegen die echten Renderer mit echten `AlertMessage`-Objekten.
- Mutations-Gegenprobe (Adversary): z. B. Hinweis auch beim Erstalarm setzen, Y/X vertauschen,
  Bedingung `match["source"] == "nowcast"` entfernen, SMS-Reservierung entfernen — jede Verfälschung
  muss mindestens einen Test rot färben.

Live-E2E (nur in `/e2e-verify`, nach dem Push gegen Staging): echte Zustellung auf Staging im
Stalwart-Test-Postfach; E-Mail-Prüfung mit `radar_alert_mail_validator.py` (AC-7), Telegram und SMS
über die Staging-Test-Kanäle bzw. Prüfstrecken-Abgriff. Hinweis: Staging-Mailweg ist laut Memory
(#2774) derzeit gestört; ist er es zum Prüfzeitpunkt noch, ehrlich als „lokaler Nachweis, nicht
Staging" benennen.

## Definition of Done

- AC-1 bis AC-10 erfüllt; AC-1 vor der Änderung grün (Wächter), Kennzeichnungs-ACs vorher rot und
  nachher grün belegt.
- Mutations-Gegenprobe des Adversary: jede genannte Verfälschung färbt mindestens einen Test rot.
- `radar_alert_mail_validator.py` Exit 0 gegen echt zugestellte Staging-Mail (oder ehrlich als lokaler
  Nachweis benannt, falls #2774 den Staging-Mailweg noch blockiert).
- SMS-Token in `docs/reference/sms_format.md` und `premium_sms_format.md` dokumentiert.
- Alle 6 CI-Checks am PR grün, Prod-Deploy mit Selftest Exit 0; #2848 danach geschlossen.

## Known Limitations

- **Kein Deckel je Ereignis.** Jede erneute Verdopplung (Faktor >= 2 und >= 2 mm gegen die zuletzt
  gemeldete Menge) bricht weiter durch; im Beispiel also bis zu drei Alarme für ein Ereignis, jetzt
  aber erkennbar als Verschärfung. Option C (Deckel) wurde vom PO verworfen, weil sie die
  Fehlerrichtung „Alarm bleibt aus" berührt. Eine spätere Änderung wäre eine eigene Spec.
- **Ortsvergleich nicht betroffen:** Der Mengen-Durchbruch (#2065) ist dort PO-zurückgestellt, daher
  gibt es dort nichts zu kennzeichnen. Wird #2065 später auf den Ortsvergleich ausgedehnt, muss die
  Kennzeichnung im selben Zug dort mitverdrahtet werden (Renderer sind bereits geteilt).
- **Reine Stufen-Eskalation ohne Mengen-Durchbruch** (z. B. Stufenwechsel LOW → HIGH, Faktor < 2)
  wird nicht gekennzeichnet; das Kennzeichen hängt am Mengen-Durchbruch, wie vom PO entschieden.
- **Zahlen im Hinweis vs. `R<mm>`-Token:** X/Y sind die Vergleichsmengen des Durchbruchs
  (`window_precip_mm`), das SMS-Radar-Token nennt die Menge der Stunde ab Beginn; beide können
  unterschiedlich sein. Die Spec legt bewusst die Vergleichsmengen fest, weil nur sie den Durchbruch
  erklären.
- **Fehlende Vergleichsbasis:** Ohne gespeicherte Basis gibt es keinen Durchbruch (#2065) und damit
  auch keinen Hinweis; das ist unverändert.
- **Wortwahl:** „Ereignis" statt „Regenereignis" gewählt, da dieselbe Zeile auch bei Gewitter-Radar
  steht; PO-Formulierung war „sinngemäß".
- **Keine Handlungsempfehlungen** im Text (Produktregel: nur Daten).
- **Telegram-Langform mit `addendum_reference`:** Ist `addendum_reference` gesetzt, entfällt der
  Verschärfungs-Satz (`_render_telegram_onset` kennt nur eine der beiden Zusatzzeilen). In der
  Praxis schließen sich beide aus, weil der Nachtrags-Zweig im Gate vor dem Radar-Zweig liegt
  und `ist_mengen_verschaerfung` bei `addendum_direction` nie gesetzt wird.
- **Umfang der Umsetzung (2026-11-08):** Der Fix berührt 8 Produktiv-/Katalogdateien (86 LoC)
  statt der im Workflow üblichen 5, weil Vier-Kanal-Parität (ADR-0095), i18n (de/en) und
  Alarmlog dies erzwingen. Die Schätzung „7 Dateien" in Estimated Scope war ein Zählfehler
  (tatsächlich: `alert_gate.py`, `trip_alert.py`, `notification_service.py`, `alert/model.py`,
  `alert/render.py`, `alert_log.py`, `de/alarm.json`, `en/alarm.json`).

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine neue; berührt ADR-0095 (Kanal-Parität), ADR-0104 (i18n, Kurzform nicht
  übersetzt), ADR-0021 (geteilter Alarm-Code Trip/Ortsvergleich).
- **Rationale:** reine Darstellungs-Ergänzung ohne Änderung einer Entscheidungsfläche; das bestehende
  Verhalten aus #2065 / #2050 S4c bleibt, es wird nicht rückgängig gemacht.

## Changelog

- 2026-11-08: Initial spec created (Issue #2848, PO-Entscheid Option B)
- 2026-11-08: Implementiert (status implemented): `GateResult.ist_mengen_verschaerfung`, `RadarAlertRequest.verschaerfung` → `AlertMessage.verschaerfung`, Hinweis in E-Mail/Telegram-Langform (Katalog `alarm.verschaerfung`, de/en), SMS-Token `UP <Y>><X>` (SMS, Premium-SMS, Telegram-Kurzform), Alarmlog `escalation_from_mm`/`escalation_to_mm`. Tests: `tests/tdd/test_radar_verschaerfung_kennzeichnung_{mehrlauf,renderer}.py`, Fixture `tests/fixtures/alarm_kette/ortsvergleich_radar_verdopplung_vor_2848.json`. Known Limitations ergänzt. Doku: `sms_format.md` §3.4g, `premium_sms_format.md`, `architecture.md`.
