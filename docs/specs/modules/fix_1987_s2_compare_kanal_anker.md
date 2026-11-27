---
entity_id: fix_1987_s2_compare_kanal_anker
type: feature
created: 2026-11-27
updated: 2026-11-27
status: draft
workflow: fix-1987-compare-kanal-anker
issue: 1987
version: "1.0"
tags: [alerts, compare, channels, anchor, issue-1987, notification]
---

# Ortsvergleich: kanalscharfer, rollierender Alarm-Anker (Issue #1987, Scheibe S2)

## Approval

- [ ] Approved

## Purpose

Der Abweichungsalarm eines Ortsvergleichs vergleicht die aktuelle Vorhersage je Ort
gegen einen gespeicherten Referenzstand ("Anker"). Heute schiebt diesen Anker nur das
Briefing, kanallos; ein zugestellter Alarm lässt ihn stehen. Nach PO-Entscheid
2026-08-19 ist die Vergleichsbasis eines Empfängers der Stand, den er **auf diesem
Kanal zuletzt tatsächlich zugestellt bekommen hat**, Briefing oder Alarm. Diese Scheibe
überträgt das von Trips (S1, `fix_1987_kanal_anker.md`) auf den Ortsvergleich und fügt
dort zusätzlich den rollierenden Anker hinzu, den es bisher gar nicht gibt. Der
Alarm ist kanalübergreifend relevant: betroffen sind alle vier Kanäle
(E-Mail, Telegram, SMS, Premium-SMS), gleicher Inhalt, kanalgerechte Form.

Herleitung, Ist-Zustand, Risiken: `docs/context/fix-1987-compare-kanal-anker.md`.

## Source

- **File:** `src/services/compare_alert.py`
- **Identifier:** `CompareAlertService._vorbereite_ort` (Basis-Auflösung, Zeile ~689),
  Versandschleife in `_check_one_preset` (nach `send_multi_location_deviation_alert`,
  Zeile ~477-497, neuer Schreibpunkt)
- Nebendateien: `src/services/compare_weather_snapshot.py`
  (`CompareWeatherSnapshotService`), `src/services/alert_preview_hours.py`
  (`compare_preview_point`, Zeile ~88-120)

> **Schicht-Hinweis:** ausschließlich Python-Core (`src/services/`). Kein Frontend,
> keine Go-API-Änderung. Der Go-Cleanup beim Preset-Löschen
> (`internal/store/compare_preset.go:331-357`, Präfix `<id>__`) trifft die neuen
> Dateien über den Dateinamen-Präfix ohne Änderung.
>
> **Trip/Ortsvergleich-Teilung:** Pendant ist die Trip-Auflösung in
> `trip_alert.py` (S1). Neutral teilbar ist nur die reine Auswahl-Hilfsfunktion
> (`alarm_anchor_basis.py`); die Basis-Regel selbst weicht bewusst ab (s. Design),
> daher bleibt der Trip-Code unangetastet. Mandantentrennung: alle Pfade laufen über
> `user_id` des Dienstes (`get_data_dir(user_id)`), nie `"default"`.

## Scope

- **LoC:** ca. 200 Produktivcode (Limit 250, kein Split)
- **Files:** 3 bis 4 Produktivdateien + ADR-Amendment + neue Tests
- **Effort:** medium. Alarmpfad Ortsvergleich + Vorschau; Bestandsdaten bleiben.

### Affected Files

| Datei | Änderungstyp | Beschreibung | LoC |
|---|---|---|---|
| `src/services/compare_weather_snapshot.py` | MODIFY | `save_alarm_anchor(preset, loc, point, channel)` und `load_alarm_anchor(preset, loc, channel)`; Datei `{preset}__{loc}__alarm_{channel}.json`; `delete()` bleibt unverändert (Präfix `{preset}__`) | ~50 |
| `src/services/alarm_anchor_basis.py` | CREATE | reine Hilfsfunktionen: "neuester gültiger Stand je Kanal" und "ältester über Kanäle" (Alter, `target_date`-Guard); kein I/O | ~40 |
| `src/services/compare_alert.py` | MODIFY | `_vorbereite_ort` löst Basis je Kanal auf und wählt den ältesten; Schreibpunkt je Gruppe nach dem Versand (fail-soft) | ~90 |
| `src/services/alert_preview_hours.py` | MODIFY | `compare_preview_point` nutzt dieselbe Auflösung, rein lesend | ~20 |
| `docs/adr/0056-rollierender-alarm-anker-statt-briefing-only-snapshot.md` | MODIFY | Amendment (s. ADR-Abschnitt) | Doku |
| `tests/tdd/test_compare_channel_anchor_delivery.py` | CREATE | AC-1, AC-2, AC-3, AC-9, AC-11 | Test |
| `tests/tdd/test_compare_channel_anchor_basis.py` | CREATE | AC-4, AC-5, AC-6, AC-7, AC-8, AC-12 | Test |
| `tests/tdd/test_compare_channel_anchor_preview_cleanup.py` | CREATE | AC-10, AC-11 (Löschen), AC-13 | Test |
| `tests/tdd/test_compare_alert_anchor_unaffected.py` | MODIFY (nur falls nötig) | Dateiname `{preset}__{loc}.json` bleibt gültig; Kanaldateien kommen additiv hinzu | Test |

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `NotificationResult.delivered_channels` (`notification_service.py:169,209-213`) | property | Wahrheit für "zugestellt" (sent minus failed). NICHT `delivered_all`, NICHT `sent_channels`, NICHT `effective_channels` |
| `CompareWeatherSnapshotService.save/load/delete` | service | Briefing-Anker (Tier 1) bleibt unverändert; Format der Kanaldatei identisch |
| `_write_compare_alert_snapshots` / `write_anchor_and_reset_memory` (`scheduler_dispatch_service.py:1178-1254`, `alert_briefing_anchor.py:266`) | function | Briefing-Anker schreibt weiter unbedingt, kanalagnostisch, auch im Exception-Pfad (#1629); nicht angefasst |
| `_MAX_ANCHOR_AGE` (`compare_alert.py:63`, 26 h) | const | die EINE Alterungsgrenze, unverändert |
| `DeviationAlertEngine.evaluate` (ADR-0021) | function | bleibt EIN gemeinsamer Lauf je Ort, Signatur unverändert |
| `AlertStateService` (Melde-Gedächtnis) | service | bleibt kanallos und unberührt |
| `CompareLocationWeatherSource.fetch` (`compare_location_weather_source.py:212-214`) | service | liefert `target_date` am Frischpunkt, wenn ein Tagesbezug übergeben wurde |
| `alert_preview_hours.compare_preview_point` | function | zweiter Leser des Compare-Ankers |
| Go `compare_preset.go:331-357` | function | löscht `compare_weather_snapshots/<id>__*.json` |
| ADR-0056, ADR-0021, #1661, #1629, #1199 F002 | doc | Rahmen |

## Design

### Variante B' (gewählt)

Je Kanal c der rohen `config.channels` gilt:

**basis_c = neuester gültiger Stand aus {Briefing-Anker (bestehende Datei), Alarm-Anker c}.**

Gültig heißt:

1. Alter höchstens 26 h (`_MAX_ANCHOR_AGE`, EINE Grenze für beide Quellen).
2. Der Alarm-Anker zählt nur, wenn sein `target_date` dem `target_date` des
   Briefing-Ankers entspricht (Tagesbezug #1661). Ein neues Abend-Briefing für morgen
   entwertet damit heutige Alarm-Anker. Beide ohne Datum (Altbestand) gelten als gleich.
3. Es wird nie der Alarm-Anker eines anderen Kanals herangezogen (Kontaminationsverbot).

Fehlt die Kanaldatei, ist der Briefing-Anker die Basis aller Kanäle (Bestandsdaten,
Issue-AC-4). Gibt es keinen gültigen Stand, gilt das bestehende `too_old`/`missing`-
Verhalten (Ort übersprungen, Diagnose protokolliert), es wird kein Sprung erfunden.

### Gemeinsamer Lauf

Die Auslöse-Entscheidung bleibt ein Lauf je Ort (ADR-0021). Verglichen wird gegen die
**älteste** basis_c der rohen `config.channels` (vor Schwellen-/Metrikfilter, wie S1:
der Schwellenfilter braucht die Dringlichkeit, die erst nach der Änderungserkennung
feststeht; ein gefilterter Kanal zieht die Basis höchstens nach hinten, nichts geht
verloren, Wiederholungen verhindert `alert_state`). `target_date` und `fetched_at`
dieser Basis speisen Frischabruf, `reference_at` und `anchor_point`.

### Schreiben

Nach `send_multi_location_deviation_alert` je versendeter Gruppe: für jeden Ort der
Gruppe und jeden Kanal in `notif_result.delivered_channels` **dieser Gruppe** wird
`save_alarm_anchor` aufgerufen. Fail-soft, nach dem Versand; Backoff, Finalize,
Protokoll, Throttle und Daily-Limit bleiben unverändert. Kein
`write_anchor_and_reset_memory`, das Melde-Gedächtnis wird nicht geleert.
Blockiert, Ruhezeit, Backoff, Daily-Limit oder Transportfehler bedeuten: nichts
zugestellt, kein Merker.

### Herkunft von `target_date` am geschriebenen Merker (Codeprüfung)

`fresh_point.target_date` ist auf dem Schreibpfad **nicht immer gesetzt**:
`CompareLocationWeatherSource.fetch` (Zeile 212-214) füllt es nur, wenn ein Tagesbezug
übergeben wurde. `_vorbereite_ort` übergibt `target_date` nur, wenn die Basis eines hat
(Zeile 718-727). Regel für den Merker:

- Trägt `fresh_point.target_date` einen Wert, wird er geschrieben.
- Sonst wird das `target_date` der gewählten Basis (der ältesten, gegen die
  ausgewertet wurde) übernommen; ist auch das leer (Altbestand ohne Datum), bleibt das
  Feld leer. Das ist konsistent mit der Gleichheitsregel oben (beide leer = gleich).

Damit trägt ein Merker nie ein erfundenes Datum, und der Guard (AC-6) greift auch für
den ersten Merker nach einem Deploy.

### Begründung der Abweichung von S1

S1 lässt den datierten Briefing-Anker immer gewinnen; der rollierende Merker greift dort
nur ohne Tagesbriefing. Das erfüllt den PO-Entscheid an Briefing-Tagen nicht
(Zustellung nach dem Briefing wird ignoriert). Dieser S1-Defekt wird in **#3481**
behoben und hier bewusst nicht gespiegelt. Ebenso gilt für Compare die **eine** Grenze
26 h: eine 4-h-Grenze wie bei S1 würde einen jüngeren, zugestellten Alarm-Anker
verwerfen und auf einen älteren Briefing-Stand zurückfallen, also einen erfundenen
Sprung erzeugen. Das widerspricht dem PO-Entscheid zur Alterungsgrenze.

### Vorschau

`alert_preview_hours` (Alarm-Vorschau) löst die Basis über dieselbe Funktion auf, rein
lesend, sonst zeigte sie andere Stundenzeilen als der Alarm.

### Briefing-Anker

Bleibt unbedingt und kanalagnostisch, auch im Exception-Pfad des Dispatch (#1629).
Die Zustellungsbindung gilt nur für den neuen Alarm-Merker.

## Datenmodell

- Ablage: `data/users/<user_id>/compare_weather_snapshots/`
- Neue Datei je Ort und Kanal: `{preset}__{loc}__alarm_{channel}.json`, Kanal aus
  `email | telegram | sms | premium_sms`.
- Format identisch zur bestehenden Compare-Snapshot-Datei (`id`, `name`, `lat`, `lon`,
  `fetched_at`, `provider`, `aggregated`, optional `hourly`, optional `target_date`).
  Serialisierung wiederverwendet, kein neues Schema.
- Schreiben per `atomic_write_json`. Bestehende Dateien werden nie umbenannt oder
  überschrieben (Read-Modify-Write-Regel: nur die Kanaldatei wird geschrieben).
- Der Präfix `{preset}__` bleibt erhalten, damit `delete()` und der Go-Cleanup die
  Dateien erfassen. Die Briefing-Datei `{preset}__{loc}.json` kollidiert nie mit dem
  Kanalnamen.

## Expected Behavior

- **Input:** Alarmlauf eines Ortsvergleichs mit mehreren Kanälen und Orten, deren
  Zustellbilanz je Gruppe verschieden ausfällt.
- **Output:** Nur zugestellte Kanäle der jeweiligen Gruppe schieben ihren Merker für
  genau die Orte dieser Gruppe. Die Auswertung vergleicht gegen die älteste
  Kanal-Basis. Auslöse-Entscheidung, Melde-Gedächtnis, Backoff, Protokoll und
  Throttle bleiben unverändert.
- **Side effects:** bis zu vier zusätzliche Dateien je Preset und Ort. Kein neuer
  Endpunkt, keine Migration.

## Acceptance Criteria

- **AC-1:** Given ein Ortsvergleich-Alarm mit den Kanälen E-Mail und SMS, der in einer
  Ortsgruppe nur per E-Mail zugestellt wird (SMS scheitert am Transport) / When der
  Versand abgeschlossen ist / Then liegt für jeden Ort dieser Gruppe ausschließlich
  ein neuer E-Mail-Merker vor, während der SMS-Merker unverändert bleibt und die SMS
  weiter gegen ihre bisherige Basis vergleicht.
  - Test: Kern. Echte Dateien im Test-Datenverzeichnis; `delivered_channels == ["email"]`
    präparieren; SMS-Datei vor/nach identisch, E-Mail-Datei mit neuem `fetched_at`.

- **AC-2:** Given zwei Ortsgruppen mit unterschiedlicher Zustellung, Gruppe A zugestellt
  und Gruppe B gescheitert / When der Versand abgeschlossen ist / Then bekommen nur die
  Orte aus Gruppe A einen Merker (für die in A zugestellten Kanäle), die Orte aus
  Gruppe B behalten ihre bisherige Basis.
  - Test: Kern. Zwei Gruppen mit verschiedener Ortsliste und Kanalmenge erzeugen,
    Merkerdateien je Ort und Kanal prüfen. Mutation: Schreiben über `delivered_all`
    statt je Gruppe muss den Test rot machen.

- **AC-3:** Given ein Alarm, der nirgends zugestellt wird (Versand blockiert, Ruhezeit,
  Backoff, Daily-Limit oder Transportfehler) / When der Lauf endet / Then entsteht für
  keinen Ort und keinen Kanal ein Merker.
  - Test: Kern. `delivered_channels == []` bzw. Backoff aktiv; Verzeichnisinhalt vor/nach
    vergleichen, keine neue `__alarm_*`-Datei.

- **AC-4:** Given ein Kanal mit Briefing-Anker und eigenem Alarm-Merker / When die Basis
  dieses Kanals aufgelöst wird / Then ist sie der jeweils neuere der beiden Stände,
  sodass ein späteres Briefing einen älteren Alarm-Merker ablöst und ein späterer
  Alarm-Merker ein älteres Briefing.
  - Test: Kern. Beide Reihenfolgen mit präparierten `fetched_at` prüfen; die an
    `DeviationAlertEngine.evaluate` übergebene Basis ist jeweils der neuere Stand.

- **AC-5:** Given zwei Kanäle mit unterschiedlich alter Basis (E-Mail 09:00, SMS 06:00)
  / When der gemeinsame Auswertungslauf die Vergleichsbasis eines Ortes bestimmt /
  Then wird gegen die ältere Basis (SMS, 06:00) verglichen, aus der rohen
  `config.channels`-Menge, sodass auch die Änderung zwischen 06:00 und 09:00 gemeldet
  wird.
  - Test: Kern. Zwei Merker mit verschiedenen Zeiten; Spion auf den übergebenen
    `cached`-Wert. Mutation "jüngste statt älteste" muss rot werden.

- **AC-6:** Given ein Alarm-Merker, dessen `target_date` vom `target_date` des
  Briefing-Ankers abweicht / When die Basis aufgelöst wird / Then wird der Merker
  ignoriert und der Briefing-Anker gilt.
  - Test: Kern. Merker mit gestrigem Datum neben heutigem Briefing-Anker; Basis ist der
    Briefing-Anker, auch wenn der Merker jünger ist.

- **AC-7:** Given ein Stand (Briefing-Anker oder Merker), der älter als 26 Stunden ist
  / When die Basis aufgelöst wird / Then wird er ignoriert; gibt es keinen gültigen
  Stand, verhält sich der Ort wie bisher (`too_old` bzw. `missing`, Ort übersprungen,
  Diagnose protokolliert) und es wird kein Vergleich gegen einen erfundenen Stand
  gebildet.
  - Test: Kern. Nur alte Stände: Ort wird übersprungen und die Diagnose geschrieben;
    alter Briefing-Anker plus frischer Merker: Merker gilt.

- **AC-8:** Given ein Ortsvergleich mit Bestandsdaten, also nur dem kanallosen
  Briefing-Anker und keiner Kanaldatei / When der erste Alarmlauf nach dem Deploy
  läuft / Then dient der Briefing-Anker allen vier Kanälen als Ausgangsbasis, und die
  vorhandene Datei bleibt unverändert erhalten (kein Datenverlust, kein
  Migrationsskript).
  - Test: Kern. Nur `{preset}__{loc}.json` anlegen, Basis für alle Kanäle prüfen,
    Dateiinhalt (Zeitstempel) vor/nach gleich; nach Zustellung kommen Kanaldateien
    additiv hinzu.

- **AC-9:** Given ein zugestellter Alarm mit Merker-Schreibung / When der Lauf endet /
  Then bleibt das Melde-Gedächtnis (`alert_state`) unverändert gegenüber dem
  bisherigen Verhalten, und Backoff, Protokolleintrag und Throttle werden durch das
  Schreiben des Merkers weder ausgelöst noch verändert; ein Schreibfehler am Merker
  lässt den Versand als zugestellt stehen.
  - Test: Kern. `alert_state`, Throttle- und Protokolldatei mit und ohne Merker-Pfad
    vergleichen; Schreibfehler simulieren per schreibgeschütztem Zielordner.

- **AC-10:** Given ein Ortsvergleich mit aktivierter Alarm-Vorschau
  (`alert_preview_hours`) / When die Vorschau die Stundenzeilen des Vergleichsstands
  bildet / Then nutzt sie exakt dieselbe Basis wie der Alarm desselben Laufs, und sie
  schreibt nichts.
  - Test: Kern. Gleiche Dateizustände durch Alarm-Auflösung und Vorschau schicken,
    Basis vergleichen; Verzeichnisinhalt nach der Vorschau unverändert.

- **AC-11:** Given ein Ortsvergleich-Preset mit Briefing-Anker und Kanal-Merkern /
  When das Preset gelöscht wird (Python `delete()` und Go-Cleanup mit Präfix
  `{preset}__`) / Then sind auch alle Kanal-Merker dieses Presets entfernt, Dateien
  anderer Presets (z. B. `cp-10__` bei `cp-1`) und anderer Nutzer bleiben bestehen.
  - Test: Kern. Zwei Nutzer, zwei Presets mit Merkern; Löschen; nur das gewählte Preset
    des gewählten Nutzers ist leer. Go-Seite: bestehender Store-Test um eine
    Kanaldatei-Zeile ergänzt.

- **AC-12:** Given ein Kanal ohne eigenen Merker, während ein anderer Kanal einen
  frischeren Merker hat / When die Basis des Kanals ohne Merker aufgelöst wird / Then
  gilt allein der Briefing-Anker, der Merker des anderen Kanals fließt nie ein.
  - Test: Kern. Merker nur für E-Mail; Basis von Telegram, SMS und Premium-SMS ist der
    Briefing-Anker. Mutation "Rückfall auf anderen Kanal" muss rot werden.

- **AC-13:** Given ein Briefing-Lauf, dessen Versand scheitert oder eine Ausnahme wirft
  / When der Dispatch endet / Then wird der Briefing-Anker trotzdem unbedingt und
  kanalagnostisch geschrieben (#1629-Absicherung), und ein folgender Alarmlauf findet
  eine gültige Basis.
  - Test: Kern. Bestehendes Muster aus
    `test_compare_briefing_anchor_survives_dispatch_failure.py` unverändert grün,
    zusätzlich Basis-Auflösung nach dem Fehlerlauf nicht leer.

## Test Plan

### Automated Tests (TDD RED)

Alle Tests in der Kern-Schicht (deterministisch, kein Netz), echte Dateien im
Test-Datenverzeichnis, kein Mock-Theater (kein `Mock()`/`patch()`, das nur die eigene
Annahme spiegelt). Dateien unter `tests/tdd/`:

- [ ] `test_compare_channel_anchor_delivery.py`: AC-1, AC-2, AC-3, AC-9 (Teilzustellung
      je Kanal und Gruppe, Nullzustellung, Gedächtnis/Backoff unberührt)
- [ ] `test_compare_channel_anchor_basis.py`: AC-4 bis AC-8, AC-12 (neuester Stand je
      Kanal, ältester über Kanäle, Datums-Guard, 26 h, Altbestand, Kontamination)
- [ ] `test_compare_channel_anchor_preview_cleanup.py`: AC-10, AC-11, AC-13
- [ ] Mandantentrennung: Delivery- und Cleanup-Tests laufen mit zwei verschiedenen
      Nutzern, ein Merker darf nie im Baum des anderen landen.
- [ ] Bestehende Tests grün: `test_issue_1169_compare_alert_consumer.py`,
      `test_compare_anchor_target_date.py`, `test_compare_alert_anchor_unaffected.py`,
      `test_compare_alert_channel_delivery.py`, `test_compare_anker_ortsmitternacht.py`,
      `test_compare_briefing_anchor_and_memory_reset.py`,
      `test_alert_preview_reihen_quelle.py`, `tests/unit/test_compare_weather_snapshot_delete.py`.

### Mutations-Gegenprobe (Pflicht)

1. Schreiben über `delivered_all` oder `effective_channels` statt je Gruppe
   `delivered_channels` (AC-1, AC-2).
2. Jüngste statt älteste Basis im gemeinsamen Lauf (AC-5).
3. Rückfall auf den Merker eines anderen Kanals (AC-12).
4. Merker ohne `target_date`-Guard akzeptiert (AC-6).
5. Briefing-Anker-Write an Zustellung gekoppelt (AC-13).

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine neue, Amendment zu ADR-0056 (Datei
  `docs/adr/0056-rollierender-alarm-anker-statt-briefing-only-snapshot.md`).
- **Rationale:** Die Zeile "Ortsvergleichs-Δ-Anker bleibt kanalagnostisch (S2,
  zurückgestellt)" (dort Zeile ~112) wird ersetzt: der Ortsvergleich führt jetzt einen
  kanalscharfen, rollierenden Alarm-Anker nach Variante B' (neuester gültiger Stand
  aus Briefing und Kanal-Merker, eine Grenze von 26 h, `target_date`-Guard, ältester
  Kanal-Stand im gemeinsamen Lauf). Die Abweichung vom Trip-Modell (S1) wird dort
  ausdrücklich vermerkt und auf #3481 verwiesen. ADR-0021 bleibt unangetastet.

## Non-goals

- `alert_state` (Melde-Gedächtnis) bleibt kanallos, wie bei Trips.
- `reference_at` bleibt EIN Wert je Alarm; kanalweise Ausweisung gehört zu #1948 S6.
- Korrektur des S1-Trip-Modells (Briefing gewinnt immer, 4 h): #3481.
- Keine Änderung an `compare_radar_alert.py` und `compare_official_alert.py` (nutzen
  keinen Δ-Anker).
- Kein Migrationsskript, kein Go-/Frontend-Change.

## Known Limitations

- Ein Briefing-Anker aus dem Exception-Pfad (#1629-Absicherung) wird auch dann als
  "neuester Stand" gewählt, wenn das Briefing nicht zugestellt wurde. Bewusst in Kauf
  genommen: eine Basis ist besser als keine.
- Ein Kanal ohne eigenen Merker vergleicht gegen den Briefing-Anker (gröbere, aber
  gültige Basis, keine Kontamination durch fremde Kanäle).
- Bis zu vier zusätzliche Snapshot-Dateien je Preset und Ort (fachlich nötig, da
  verschiedene Kanäle verschiedene Stände kennen können).
- Die Basis der gemeinsamen Auswertung berücksichtigt die rohe `config.channels`-Menge,
  nicht den Schwellenfilter (wie S1); ein gefilterter Kanal kann die Basis nur nach
  hinten ziehen.

## Definition of Done

- Alle 13 ACs durch je einen Kern-Test (echte Dateien, ohne Mock-Theater) abgedeckt und grün; vorher RED-Nachweis.
- Mutations-Gegenprobe des Adversary: jede Verfälschung gefangen; Verdict VERIFIED.
- Zwei-Nutzer-Test (Isolation `user_id`) grün; bestehende Compare-Anker-Tests unverändert grün.
- ADR-0056-Amendment geschrieben, ADR-Index konsistent.
- CI 6/6 grün, Staging-Verifikation (`/e2e-verify`) bestanden, Prod-Deploy mit Selftest-Exit 0.
- Issue #1987 nach S2 geschlossen (S1 und S2 ausgeliefert); #3481 bleibt eigenständig offen.

## Changelog

- 2026-11-27: Initiale Spec für Scheibe S2 (Ortsvergleich), Variante B' aus der
  Analyse in `docs/context/fix-1987-compare-kanal-anker.md`; `target_date`-Herkunft des
  Merkers am Code geprüft und festgelegt.
