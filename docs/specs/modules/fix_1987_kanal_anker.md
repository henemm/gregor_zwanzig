---
entity_id: fix_1987_kanal_anker
type: bugfix
created: 2026-08-19
updated: 2026-08-19
status: approved
workflow: fix-1987-kanal-anker
version: "1.1"
tags: [alerts, trip, channels, anchor, issue-1987, notification]
---

# Alarm-Vergleichsbasis wird je Kanal geführt — nur bei tatsächlicher Zustellung (Issue #1987, Scheibe S1)

## Approval

- [x] Approved — PO (Henning) am 2026-08-19, Freigabe der 11 Akzeptanzkriterien mit „go"

## Purpose

Der Abweichungs-Alarm eines Trips vergleicht die aktuelle Vorhersage gegen
einen gespeicherten Referenz-Wert ("Anker"). Heute gibt es genau **einen**
rollierenden Alarm-Anker je Trip, kanallos — er wird auch dann
fortgeschrieben, wenn ein Kanal den Alarm nie erreicht hat. Fachlich richtig
ist: die Vergleichsbasis eines Empfängers ist das, was dieser Empfänger auf
**diesem konkreten Kanal zuletzt tatsächlich zugestellt bekommen hat**
(PO-Entscheid 2026-08-19). Diese Scheibe fächert den rollierenden Alarm-Anker
über die vier Kanäle `("email", "telegram", "sms", "premium_sms")`
(`alert_log.py:70`) auf und bindet ihn an tatsächliche Zustellung —
ausschließlich für **Trips**, nicht für den Ortsvergleich (Scheibe S2,
zurückgestellt).

Vollständige Herleitung, Ist-Zustand, Risiken und PO-Entscheidungen E1/E2:
`docs/context/fix-1987-kanal-anker.md`. Diese Spec wiederholt die Analyse
nicht, sondern zieht Scope und Acceptance Criteria daraus.

## Source

- **File:** `src/services/trip_alert.py`
- **Identifier:** `TripAlertService._get_cached_weather` (Anker-Priori\
tätskette, Zeile 608-763), `TripAlertService._write_rolling_alarm_anchor`
  (Zeile 796-806), einzige verbleibende Schreib-Aufrufstelle Zeile 429-434
  (Zustellungs-Trigger). Der bisherige Ceiling-Schreib-Trigger Zeile 334-344
  (`_effective_anchor_age`-Aufruf Zeile 340 + Refresh-Write bei
  Ceiling-Überschreitung) entfällt für den kanalscharfen Tier-2-Merker
  ersatzlos (s. Implementation Details, „Schreibpfad — EIN Trigger")
- Nebendatei: `src/services/weather_snapshot.py` — `WeatherSnapshotService
  .save_alarm_anchor` (Zeile 190-219), `.load_alarm_anchor` (Zeile 221-251),
  `.alarm_anchor_target_date` (Zeile 253-263)

> **Schicht-Hinweis:** ausschließlich Python-Core (`src/services/`) —
> Persistenz-Schema des rollierenden Alarm-Ankers und die Lese-/Schreiblogik
> im Trip-Alarm-Pfad. Kein Frontend-Code, keine Go-API-Änderung.

## Estimated Scope

- **LoC:** ~100-160 Produktivcode (Kernänderung in `weather_snapshot.py` und
  `trip_alert.py`), Tests zusätzlich. Workflow-Limit 250 (Standard, keine
  Anhebung beantragt).
- **Files:** 2 Produktivdateien, 5 bestehende Testdateien (Dateiname/JSON-\
  Zugriff direkt), mindestens 3 neue Testdateien.
- **Effort:** medium — etabliertes Muster (`weather_snapshot.py` führt
  bereits drei Rollen als drei separate Dateien), additive Erweiterung ohne
  neuen Merge-Mechanismus.

### Affected Files

| Datei | Änderungstyp | Beschreibung |
|---|---|---|
| `src/services/weather_snapshot.py` | MODIFY | `save_alarm_anchor`, `load_alarm_anchor`, `alarm_anchor_target_date` bekommen einen Pflicht-Parameter `channel: str`. Dateinamensschema wechselt von `{trip_id}_alarm_anchor.json` auf `{trip_id}_alarm_anchor_{channel}.json`. `load_alarm_anchor`/`alarm_anchor_target_date` fallen auf die kanallose Altdatei zurück, wenn die kanalspezifische Datei fehlt (AC-5) |
| `src/services/trip_alert.py` | MODIFY | `_write_rolling_alarm_anchor` iteriert über `notif_result.delivered_channels` und schreibt je Kanal einen eigenen Merker (AC-1, AC-2) — einziger verbleibender Schreib-Trigger; der bisherige Ceiling-Schreib-Trigger (Zeile 334-344) entfällt ersatzlos. Neue Kandidaten-Auflösung je Kanal in `_get_cached_weather` (AC-4/AC-7/AC-8); `_effective_anchor_age` wird durch eine reine Lese-Alterungsprüfung je Kanal-Kandidat ersetzt (kein Schreibeffekt mehr). Neue Aggregation über `effective_channels`: der EINE gemeinsame Auswertungslauf vergleicht gegen den ÄLTESTEN gültigen Kandidaten (AC-11) |
| `tests/tdd/test_alert_rolling_anchor.py` | MODIFY | Dateiname-/API-Zugriffe bekommen den neuen `channel`-Parameter |
| `tests/tdd/test_alert_anchor_day_guard.py` | MODIFY | dito |
| `tests/tdd/test_onset_anchor_fresh_window_symmetry.py` | MODIFY | dito |
| `tests/tdd/test_onset_shift_alert.py` | MODIFY | dito |
| `tests/tdd/test_compare_alert_anchor_unaffected.py` | MODIFY | dito — beweist zusätzlich, dass der Ortsvergleichs-Anker (eigene Datei, eigener Code) von der Kanal-Auffächerung unberührt bleibt |
| `tests/tdd/test_alert_channel_anchor_delivery.py` | CREATE | AC-1, AC-2, AC-5, AC-6 (Teilzustellung, keine Zustellung, Bestandsdaten-Rückfall, Schwellenfilter) |
| `tests/tdd/test_alert_channel_anchor_ceiling_fallback.py` | CREATE | AC-4, AC-7, AC-8 (Alterungsgrenze je Kandidat, fehlender Merker, Tagesgrenze) |
| `tests/tdd/test_alert_channel_anchor_shared_comparison.py` | CREATE | AC-11 (Auswahl des ältesten Kandidaten für den EINEN gemeinsamen Auswertungslauf) |

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `NotificationResult.delivered_channels` (`notification_service.py:142-144`) | property | Quelle der Wahrheit für „zugestellt" — `[c for c in sent_channels if c not in failed_channels]`. NICHT `sent` (aggregiertes Bool), NICHT `effective_channels` (nur konfiguriert, nicht zugestellt) |
| `alert_log._ALL_CHANNELS` (`alert_log.py:70`) | const | verbindliche Kanal-Bezeichner `("email", "telegram", "sms", "premium_sms")`, projektweit einheitlich ohne Enum |
| `alert_channel_threshold.split_by_threshold` (`trip_alert.py:1508-1511`) | function | filtert Kanäle unterhalb der Dringlichkeitsschwelle VOR dem Versand — ein so entfernter Kanal erscheint nie in `sent_channels`/`delivered_channels` und bekommt dadurch von selbst keinen frischen Merker (AC-6); die verbleibenden Kanäle bilden zugleich die Menge, aus der AC-11 den ältesten Kandidaten wählt |
| `WeatherSnapshotService.save`/`save_dated` (Tier 1, Briefing-Anker) | function | unverändert weiterverwendet — bleibt unbedingt und kanalagnostisch (E1) |
| `write_anchor_and_reset_memory`/`_anchor_and_reset()` (`trip_report_scheduler.py:1514-1525`, `:1543`, `:1651`) | function | unverändert — trägt die #1629-Garantie, wird von dieser Scheibe nicht angefasst |
| `DeviationAlertEngine.evaluate()` (ADR-0021) | function | unverändert — bleibt EIN gemeinsamer Auswertungslauf (E2), keine Signaturänderung; bekommt weiterhin genau einen `cached`-Wert, jetzt aus der AC-11-Aggregation |
| `alert_state` (Melde-Gedächtnis, ADR-0056 AC-12) | store | schützt bereits gegen Wiederholungs-Alarme für Kanäle, die schon einen aktuelleren Stand kennen — Grundlage der AC-11-Begründung, warum „ältester Kandidat" keine Doppel-Alarme erzeugt |
| `docs/adr/ADR-0056` | doc | führte den rollierenden Alarm-Anker ein (Hybrid-Trigger a/b) — diese Scheibe erweitert den Mechanismus additiv und löst Trigger (b) für den kanalscharfen Merker ab (Amendment, kein neues ADR) |
| `docs/specs/modules/fix_1661_anker_vom_falschen_tag.md` | doc | Tagesgrenzen-Guard (#823/#1916 AC-10) — gilt weiterhin je Kanal (AC-8) |

## Nicht in dieser Scheibe

- **Scheibe S2 (Ortsvergleich).** Der Compare-Δ-Anker (`compare_alert.py`,
  `compare_weather_snapshot.py`) bleibt vollständig unverändert. PO-\
  zurückgestellt.
- **Getrennte Auswertung je Kanal.** Die Auslöse-Entscheidung
  (`DeviationAlertEngine.evaluate`) bleibt EIN gemeinsamer Lauf (E2) — ob ein
  Alarm ausgelöst wird, hängt weiterhin nicht vom Kanal ab. Kanalscharf sind
  ausschließlich (1) welcher Kanal seinen Merker fortschreibt und (2) welcher
  Kandidat in die AC-11-Aggregation eingeht.
- **Kanalgenaue Ausweisung des Vergleichsstands im Alarmtext.** `reference_at`
  (`trip_alert.py:359-371`, an `_send_alert` übergeben `:373-378`) bleibt EIN
  gemeinsamer Wert für den gesamten Alarm — der Stand, gegen den tatsächlich
  verglichen wurde (AC-11, der gewählte älteste Kandidat). Eine je-Kanal
  getrennte Ausweisung im Text bräuchte einen Umbau der Versandschnittstelle
  und gehört, falls gewünscht, zu #1948 S6 (Telegram-Parität), wo die
  kanalweise Ausweisung ohnehin behandelt wird.
- **Kanal-Dimension am Briefing-Anker (Tier 1).** `save()`/`save_dated()`
  bleiben unbedingt und kanalagnostisch (E1) — s. Abschnitt „Bewusste Abkehr
  von Alt-Verhalten" unten.
- **Migrationsskript für Bestandsdaten.** Die kanallose Altdatei bleibt
  liegen und dient als Rückfall (AC-5); kein aktives Umschreiben.
- **Neue Kalibrierung von `_ALARM_ANCHOR_CEILING` (4h) oder
  `_MAX_UNDATED_ANCHOR_AGE` (26h).** Beide Werte bleiben unverändert.

## Implementation Details

### Kanal-Dimension am rollierenden Anker (Tier 2)

Umsetzungsvariante: **eine Datei je Kanal**,
`{trip_id}_alarm_anchor_{channel}.json`, statt verschachteltem JSON.
Begründung: `weather_snapshot.py` führt seine drei bestehenden Rollen bereits
als drei separate Dateien (`:104`, `:131`, `:215`), jede Schreibmethode
überschreibt vollständig — es existiert **kein** Merge-Pfad im Modul.
Verschachteltes JSON bräuchte einen neuen Read-Modify-Write-Mechanismus, weil
die vier Kanäle nie gleichzeitig geschrieben werden (unterschiedliche
Zustellbilanzen je Lauf). Der vervielfachte Platzbedarf (der Anker hält
vollständige Stundenreihen aller Etappen) ist bewusst nicht vermeidbar:
divergierende Zustellung bedeutet fachlich verschiedene Wetterstände je
Kanal — genau der Zweck dieses Tickets.

`save_alarm_anchor(trip_id, target_date, segments, channel)`,
`load_alarm_anchor(trip_id, channel)`, `alarm_anchor_target_date(trip_id,
channel)` (alle `weather_snapshot.py`) bekommen `channel` als Pflicht-\
Parameter ohne Default — dasselbe Muster wie der bereits pflichtige
`tagesgleicher_anker_noetig`-Parameter aus #1661: ein vergessenes Argument
mit stillschweigendem Default würde eine Kanal-Verwechslung erzeugen, die
kein Test fängt, solange nur ein Kanal konfiguriert ist.

### Schreibpfad: nur zugestellte Kanäle rücken vor — EIN Trigger

`_write_rolling_alarm_anchor` (`trip_alert.py:796-806`) iteriert über eine
Liste von Kanälen statt einen einzelnen Schreibvorgang auszuführen:

```
def _write_rolling_alarm_anchor(
    self, trip_id: str, target_date: date,
    weather: List[SegmentWeatherData], channels: Iterable[str],
) -> None:
    svc = WeatherSnapshotService(user_id=self._user_id)
    for channel in channels:
        svc.save_alarm_anchor(trip_id, target_date, weather, channel)
```

Es bleibt genau EINE Aufrufstelle: der **Zustellungs-Trigger**
(`trip_alert.py:429-434`, nach `notif_result = self._send_alert(...)`):
`channels=notif_result.delivered_channels`. Ein Kanal, der nicht in
`delivered_channels` steht — sei es, weil er fehlgeschlagen ist, blockiert
wurde, oder von `split_by_threshold()` vorab entfernt wurde — bekommt
**keinen** frischen Merker (AC-1, AC-2, AC-6). Bewusst `delivered_channels`,
NICHT `effective_channels` (konfiguriert, aber nicht notwendig zugestellt)
und NICHT `sent_channels` (nur „betreten", enthält auch fehlgeschlagene
Transporte, Anti-Pattern #656).

**Der bisherige Ceiling-Schreib-Trigger entfällt für den kanalscharfen
Tier-2-Merker ersatzlos.** Der Block `trip_alert.py:334-344` (Kommentar +
`_effective_anchor_age`-Aufruf Zeile 340 + Refresh-Write bei
Ceiling-Überschreitung Zeile 341-344) lief bislang im Zweig „kein Alarm
gefeuert" (`eval_result.triggered == False`) — dort wurde NICHTS versendet,
es gibt keine `delivered_channels`. Ein dort geschriebener Merker wäre exakt
das, was diese Scheibe verbietet: ein Stand, den kein Empfänger je
zugestellt bekam. Die Schutzwirkung gegen eine veraltete Vergleichsbasis
geht dadurch nicht verloren — sie wandert vom Schreib- in den Lesepfad (s.
u. „Alterungs-Obergrenze je Kanal"): ein gealterter Kanal-Merker wird beim
Lesen einfach nicht mehr als Kandidat herangezogen, die Kette fällt für
diesen Kanal auf Tier 1 zurück, statt ihn beim Schreiben künstlich
aufzufrischen. Dies ist eine bewusste Ablösung von ADR-0056 Trigger (b) für
den kanalscharfen Merker — s. „Bewusste Abkehr von Alt-Verhalten" und das
ADR-Amendment.

### Lesepfad: kanalscharfe Kandidaten, EIN gemeinsamer Vergleich

Die bestehende Kette in `_get_cached_weather` (`trip_alert.py:671-763`)
bleibt strukturell erhalten (`load_dated` → rollierender Anker →
undatierter Rückfall). Sie wird um eine **Kandidaten-Auflösung je Kanal**
erweitert: für jeden Kanal aus `effective_channels` (nach Schwellenfilter,
s. AC-6) wird sein eigener Kandidaten-Merker bestimmt —
`load_alarm_anchor(trip.id, channel)`, mit Tagesgrenzen-Prüfung (AC-8) und
Alterungsgrenze (AC-4); fehlt er ganz (weder kanalspezifisch noch kanallose
Altdatei), fällt der Kandidat direkt auf den taggleichen Tier-1-\
Briefing-Anker zurück (AC-7). `load_alarm_anchor` selbst fällt zusätzlich
auf die kanallose Altdatei `{trip_id}_alarm_anchor.json` zurück, wenn nur
die kanalspezifische Datei fehlt (AC-5).

Da die Auslöse-Entscheidung (`DeviationAlertEngine.evaluate`) EIN
gemeinsamer Lauf bleibt (E2, ADR-0021 unangetastet), braucht sie GENAU EINEN
`cached`-Stand. Dieser wird aus den Kanal-Kandidaten wie folgt gewählt
(AC-11): **der ÄLTESTE gültige Kandidat unter den effektiven Kanälen.**
Begründung: nur so geht keinem Kanal eine Änderung verloren — ein Kanal, der
auf einem älteren Stand steht, muss die Änderungen sehen, die er noch nicht
kennt; ein bereits aktueller Kanal bekommt dadurch höchstens eine
Wiederholung im Vergleich, wovor bereits das Melde-Gedächtnis (`alert_state`,
ADR-0056 AC-12) schützt.

Ausdrücklich verworfen:

- **der JÜNGSTE Kandidat** — würde für schlechter versorgte Kanäle
  Änderungen unterschlagen, die diese Kanäle noch gar nicht gesehen haben:
  ein stiller Ausfall anderer Bauart, genau das, was diese Scheibe beheben
  soll.
- **ein fester Kanal-Vorrang** (z. B. immer E-Mail zuerst) — willkürlich,
  ohne fachliche Rechtfertigung, und würde bei abgeschaltetem
  Vorrangs-Kanal überraschend versagen.

Der im Alarmtext ausgewiesene `reference_at` (`trip_alert.py:359-371`,
`:373-378`) bleibt dabei EIN gemeinsamer Wert für den gesamten Alarm — der
Stand, gegen den tatsächlich verglichen wurde (also der gewählte älteste
Kandidat). Eine kanalgenaue Ausweisung im Text ist NICHT Teil dieser Scheibe
(s. „Nicht in dieser Scheibe").

### Alterungs-Obergrenze je Kanal (AC-4) — nur beim Lesen wirksam

Überschreitet der Tier-2-Merker EINES Kanals `_ALARM_ANCHOR_CEILING` (4h,
`trip_alert.py:80`), wird er als Kandidat für diesen Kanal NICHT
herangezogen — der Kandidat dieses Kanals ist dann der taggleiche Tier-1-\
Briefing-Anker, nicht der veraltete Kanal-Merker und ausdrücklich NICHT der
(möglicherweise frischere) Merker eines anderen Kanals (Kontaminationsverbot,
s. Kontext-Dokument, Bewertungstabelle „AC-3 frischester verfügbarer Stand",
Option (c) gewählt, Option (a) verworfen). Diese Prüfung ersetzt die frühere
`_effective_anchor_age`-Methode (Zeile 808-826), die bislang „das jüngere
von Briefing- und rollierendem Anker" für einen Schreib-Trigger berechnete —
mit dem Entfall des Ceiling-Schreib-Triggers (s. o.) wird sie durch eine
reine Lese-Alterungsprüfung je Kanal-Kandidat ersetzt, ohne eigenen
Schreibeffekt.

## Expected Behavior

- **Input:** ein Alarm-Lauf für einen Trip mit mehreren konfigurierten
  Kanälen, dessen Zustellbilanz je Kanal unterschiedlich ausfällt
  (z. B. E-Mail zugestellt, SMS gescheitert), und deren Tier-2-Merker
  unterschiedlich alt sind.
- **Output:** nur die tatsächlich zugestellten Kanäle bekommen einen
  frischen rollierenden Anker-Merker; nicht zugestellte, blockierte oder
  schwellengefilterte Kanäle behalten ihren alten Stand (oder den
  kanallosen Alt-Rückfall) unverändert. Der EINE gemeinsame Auswertungslauf
  vergleicht gegen den ältesten gültigen Kandidaten unter den effektiven
  Kanälen (AC-11). Die Auslöse-Entscheidung selbst (ob überhaupt ein Alarm
  gefeuert wird) ändert sich nicht.
- **Side effects:** bis zu vier Anker-Dateien je Trip statt einer
  (`{trip_id}_alarm_anchor_{channel}.json`), die alte kanallose Datei bleibt
  als Rückfall bestehen und wird nicht mehr aktiv fortgeschrieben, sobald
  mindestens ein Kanal seine eigene Datei besitzt. Kein neuer HTTP-Endpunkt,
  kein Schema-Bruch am Briefing-Anker. Kein opportunistischer
  Ceiling-Refresh-Write mehr (entfällt ersatzlos für Tier 2).

## Acceptance Criteria

- **AC-1:** Given ein Trip mit den Alarmkanälen E-Mail und SMS, bei dem ein
  Alarm nur per E-Mail zugestellt wird (SMS scheitert am Transport), When
  der Alarm-Versand abgeschlossen ist und `_write_rolling_alarm_anchor`
  läuft, Then wird ausschließlich der E-Mail-Anker (`{trip_id}_alarm_anchor
  _email.json`) auf den neuen Stand geschrieben, während der SMS-Anker
  (`{trip_id}_alarm_anchor_sms.json`) unverändert stehen bleibt.
  - Test: Kern. `notification_service` so präparieren, dass
    `delivered_channels == ["email"]` (SMS in `failed_channels`); vor und
    nach dem Lauf `load_alarm_anchor(trip_id, "sms")` vergleichen
    (identisch) und `load_alarm_anchor(trip_id, "email")` prüfen (neuer
    `fetched_at`-Zeitstempel).

- **AC-2:** Given ein Alarm wird auf keinem einzigen konfigurierten Kanal
  zugestellt (alle scheitern oder sind blockiert), When
  `_write_rolling_alarm_anchor` für diesen Lauf aufgerufen wird, Then
  entsteht für KEINEN Kanal ein frischer rollierender Merker.
  - Test: Kern. `delivered_channels == []` präparieren, alle vier
    Kanal-Dateien vor/nach dem Lauf vergleichen — keine wird neu
    geschrieben (Zeitstempel-Vergleich, kein Dateiinhalt-String-Check).

- **AC-3 (Regressionsschutz #1629, Gegenprobe):** Given ein
  Briefing-Lauf, bei dem auf keinem Kanal etwas zugestellt wird (z. B. der
  Versandaufruf wirft eine Ausnahme, `trip_report_scheduler.py:1543`,
  oder `result.sent == False` im regulären Pfad, `:1651`), When der
  Briefing-Lauf abgeschlossen ist, Then wird der Tier-1-Briefing-Anker
  (`save()` + `save_dated()`) TROTZDEM geschrieben, UND ein anschließender
  Abweichungs-Alarm-Check für denselben Trip findet über den Rückfall (AC-4)
  eine gültige Vergleichsbasis statt `None`.
  - Test: Kern. `send_trip_report` einen Fehler werfen lassen bzw.
    `result.sent = False` zurückgeben, `_anchor_and_reset()` durchlaufen
    lassen (bestehendes #1629-Muster), danach `_get_cached_weather()` für
    einen beliebigen Kanal aufrufen — Rückgabe ist NICHT `None`.
  - Mutations-Gegenprobe: koppelt eine Verfälschung den Tier-1-Write
    fälschlich an eine Zustellbedingung, MUSS dieser Test rot werden.

- **AC-4:** Given der rollierende Tier-2-Merker eines Kanals existiert,
  ist aber älter als `_ALARM_ANCHOR_CEILING` (4h, `trip_alert.py:80`),
  While ein taggleicher Tier-1-Briefing-Anker vorhanden ist, When der
  Kandidaten-Merker dieses Kanals aufgelöst wird, Then wird gegen den
  Tier-1-Briefing-Anker verglichen — NICHT gegen den veralteten
  Kanal-Merker und NICHT gegen den (ggf. frischeren) Merker eines anderen
  Kanals.
  - Test: Kern. Kanal-Anker `email` mit `fetched_at` = jetzt minus 5h
    anlegen, Kanal-Anker `telegram` frisch anlegen (jetzt), Tier-1-\
    Briefing-Anker für heute anlegen. Kandidaten-Auflösung für Kanal
    `email` aufrufen — Assert: Kandidat ist der Tier-1-Anker, NICHT der
    frische `telegram`-Anker und NICHT der eigene, zu alte `email`-Anker.
  - Mutations-Gegenprobe: griffe der Ceiling-Rückfall versehentlich auf
    den Merker eines anderen Kanals zu, MUSS dieser Test rot werden.

- **AC-5:** Given ein Trip besitzt ausschließlich die kanallose Altdatei
  `{trip_id}_alarm_anchor.json` (Bestand vor dieser Scheibe), When nach dem
  Deploy der erste Alarm-Lesevorgang für einen beliebigen Kanal (z. B.
  `premium_sms`) läuft, Then liefert `load_alarm_anchor(trip_id,
  "premium_sms")` den Inhalt der Altdatei als Vergleichsbasis — kein
  Datenverlust, kein Migrationsskript nötig.
  - Test: Kern. Altdatei manuell anlegen (Dateiname ohne Kanal-Suffix),
    `load_alarm_anchor()` für zwei verschiedene Kanäle aufrufen — beide
    liefern denselben Inhalt.

- **AC-6:** Given ein Kanal wird von `split_by_threshold()`
  (`trip_alert.py:1508-1511`) vor dem Versand unterhalb der
  Dringlichkeitsschwelle entfernt (er landet weder in `sent_channels` noch
  in `failed_channels`), When `_write_rolling_alarm_anchor` läuft, Then
  bekommt dieser Kanal KEINEN frischen Merker — er hat nichts empfangen.
  - Test: Kern. `notif_result.sent_channels` ohne den schwellengefilterten
    Kanal präparieren (er taucht in keiner der beiden Listen auf), Anker-\
    Datei dieses Kanals vor/nach dem Lauf vergleichen (unverändert).
  - Mutations-Gegenprobe: iteriert der Schreibpfad versehentlich über
    `effective_channels` (konfiguriert) statt `delivered_channels`
    (zugestellt), MUSS dieser Test rot werden — genau der Fehler, der die
    Zusicherung still bricht.

- **AC-7:** Given ein Kanal hat noch nie einen eigenen Tier-2-Merker
  geschrieben bekommen UND keine kanallose Altdatei existiert, When sein
  Kandidaten-Merker aufgelöst wird, Then fällt er auf den
  Tier-1-Briefing-Anker zurück und bekommt weiterhin Alarme — dies ist die
  dokumentierte Präzisionsgrenze von S1 (gröbere, aber gültige
  Vergleichsbasis), kein Fehler.
  - Test: Kern. Weder kanalspezifische noch kanallose Alarm-Anker-Datei
    anlegen, nur einen Tier-1-Briefing-Anker — Assert: Kandidat ist NICHT
    `None`, sondern der Tier-1-Anker.

- **AC-8:** Given ein rollierender Kanal-Anker trägt ein `target_date`
  ungleich heute (falscher Tag, #823/#1916 AC-10), When sein
  Kandidaten-Merker aufgelöst wird, Then wird er verworfen (analog zur
  bestehenden Tagesgrenzen-Prüfung für den kanallosen Anker) und die Kette
  fällt für diesen Kanal weiter auf den nächsten gültigen Stand zurück —
  die Tagesgrenze gilt weiterhin je Kanal, nicht global.
  - Test: Kern. Kanal-Anker mit `target_date` = gestern anlegen,
    `alarm_anchor_target_date(trip_id, channel)` prüfen — Rückgabe ≠ heute,
    Anker wird als Kandidat verworfen.

- **AC-9:** Given ein Trip-Alarm wird ausgelöst und mindestens ein Kanal
  zugestellt (Regelfall wie vor dieser Scheibe), When
  `DeviationAlertEngine.evaluate()` innerhalb desselben Alarm-Laufs
  aufgerufen wird, Then feuert derselbe Alarm bei gleicher Wetterlage wie
  vor dem Umbau — die Kanal-Trennung wirkt ausschließlich auf Merker und
  Kandidaten-Auswahl (AC-11), NICHT auf die Auslöse-Entscheidung.
  - Test: Kern. Bestehendes Szenario aus `test_alert_rolling_anchor.py`
    (Signale, die vor der Scheibe einen Alarm auslösen) nach der Migration
    unverändert grün laufen lassen — keine neue Assertion nötig, reiner
    Regressionsnachweis.

- **AC-10:** Given Radar-Unterdrückung basiert auf der eingefrorenen,
  datierten Briefing-Datei (ADR-0056 AC-11), When ein kanalscharfer
  Schreibvorgang des rollierenden Alarm-Ankers läuft (egal für welchen
  Kanal), Then bleibt die datierte Briefing-Datei (`{trip_id}_{YYYY-MM-\
  DD}.json`) davon vollständig unberührt.
  - Test: Kern. Bestehender `tests/tdd/test_alert_anchor_radar_isolation
    .py` unverändert grün nach der Migration der Kanal-Dimension.

- **AC-11:** Given zwei Alarmkanäle mit unterschiedlich alten gültigen
  Kandidaten-Merkern (E-Mail-Merker von 09:00, SMS-Merker von 06:00), When
  der EINE gemeinsame Auswertungslauf die Vergleichsbasis für diesen Alarm
  auflöst, Then wird gegen den SMS-Merker von 06:00 verglichen (der ältere
  der beiden Kandidaten) — damit auch die Änderung zwischen 06:00 und 09:00
  gemeldet wird, die der SMS-Kanal noch nicht kennt.
  - Test: Kern. Zwei Kanal-Merker mit unterschiedlichen `fetched_at`-\
    Zeitstempeln anlegen, `effective_channels = {"email", "sms"}`, den
    gemeinsamen Auswertungslauf aufrufen — Assert: der an
    `DeviationAlertEngine.evaluate()` übergebene `cached`-Stand entspricht
    dem SMS-Merker (06:00), nicht dem E-Mail-Merker (09:00).
  - Mutations-Gegenprobe: greift die Auflösung auf den JÜNGSTEN statt den
    ÄLTESTEN Kandidaten zu, MUSS dieser Test rot werden — genau der
    Fehler, der Änderungen für schlechter versorgte Kanäle stillschweigend
    unterschlägt.

## Bewusste Abkehr von Alt-Verhalten

**Erste bewusste Abkehr — der unbedingte Tier-1-Write bleibt bestehen.**
Der Kommentar `trip_report_scheduler.py:1527-1531` beschreibt den
unbedingten Anker-Write als bewusstes #1629-Verhalten: „Ein bloß nicht
zustellbares Briefing schreibt ihn seit jeher; hier wird nur
Gleichbehandlung hergestellt." Diese Scheibe hält fest: dieses Verhalten
bleibt für Tier 1 (Briefing-Anker, `save()`/`save_dated()`) **unverändert
bestehen** (E1, AC-3) — die Zustellungsbindung dieser Spec betrifft
ausschließlich Tier 2 (rollierender Alarm-Anker). Wer künftig den
unbedingten Tier-1-Write als Widerspruch zu #1987 liest, irrt: beide
Regeln gelten gleichzeitig, auf verschiedenen Ebenen der Anker-\
Prioritätskette.

**Zweite bewusste Abkehr — Ceiling-Schreib-Trigger (ADR-0056 Trigger b)
entfällt für den kanalscharfen Merker.** ADR-0056 führte zwei Schreib-\
Trigger ein: (a) tatsächlicher Alarmversand, (b) opportunistische
Auffrischung bei Überschreiten der 4h-Ceiling, unabhängig von einem
ausgelösten Alarm. Trigger (b) ist mit der Zustellungsbindung dieser
Scheibe für den kanalscharfen Tier-2-Merker begrifflich unmöglich
geworden: er lief im Zweig „kein Alarm gefeuert", also ohne jede
`delivered_channels`-Information — ein dort geschriebener Merker wäre eine
Zustellung, die nie stattgefunden hat. Die Schutzwirkung gegen eine
veraltete Vergleichsbasis bleibt erhalten, wandert aber vom Schreib- in den
Lesepfad: ein gealterter Kanal-Merker wird beim Lesen als Kandidat
ausgeschlossen (AC-4) und die Kette fällt für diesen Kanal auf den
taggleichen Tier-1-Anker zurück, statt ihn beim Schreiben künstlich
aufzufrischen.

## Testplan

Alle Tests laufen in der **Kern-Schicht** (deterministisch, kein Netz, kein
Live-Versand) — kein AC dieser Scheibe braucht Staging.

| AC | Testdatei | Ansatz |
|---|---|---|
| AC-1, AC-2, AC-6 | `test_alert_channel_anchor_delivery.py` (CREATE) | echte `WeatherSnapshotService`-Fixtures in isoliertem `get_data_dir()`, präparierte `NotificationResult` (Teilzustellung/Nullzustellung/Schwellenfilter) über den echten `_write_rolling_alarm_anchor`-Aufruf |
| AC-3 | `test_alert_channel_anchor_delivery.py` (CREATE) | echter `_anchor_and_reset()`-Pfad mit fehlgeschlagenem Versand (Muster #1629), anschließender `_get_cached_weather()`-Aufruf |
| AC-4, AC-7, AC-8 | `test_alert_channel_anchor_ceiling_fallback.py` (CREATE) | Fixture-Anker mit präparierten `fetched_at`/`target_date`-Werten je Kanal, Tier-1-Anker als Referenz |
| AC-5 | `test_alert_channel_anchor_delivery.py` (CREATE) | kanallose Altdatei manuell anlegen, zwei Kanäle lesen |
| AC-9 | `test_alert_rolling_anchor.py` (MODIFY) | bestehendes Auslöse-Szenario, Regressionsnachweis nach API-Anpassung |
| AC-10 | `test_alert_anchor_radar_isolation.py` (unverändert, muss grün bleiben) | Bestandstest, keine inhaltliche Änderung nötig |
| AC-11 | `test_alert_channel_anchor_shared_comparison.py` (CREATE) | zwei Kanal-Kandidaten unterschiedlichen Alters, geteilter Auswertungslauf, Spionage auf den an `DeviationAlertEngine.evaluate()` übergebenen `cached`-Wert |

Kein Mock-Theater: alle Tests laufen über echte Dateien und den echten
Trip-Alarm-Pfad (keine `Mock()`/`patch()`/`MagicMock`, die nur die eigene
Annahme zurückspiegeln), keine Dateiinhalt-String-Checks als
Verhaltensnachweis.

## Mutations-Gegenprobe

Mindestens diese vier Verfälschungen MUSS je ein Test fangen (Pflicht, nicht
Kür — eine grüne Testsuite beweist nur, dass sie durchläuft, nicht dass sie
etwas bewacht):

1. **Schreibpfad iteriert über `effective_channels` statt
   `delivered_channels`.** Bricht die Zusicherung still — ein
   schwellengefilterter oder fehlgeschlagener Kanal bekäme trotzdem einen
   frischen Merker. Muss AC-6 (und AC-1) rot machen.
2. **Tier-1-Write wird an die Zustellung gekoppelt.** Bringt die #1629-\
   Regression zurück — ein Briefing ohne jede Zustellung schriebe dann
   keinen Briefing-Anker mehr, die Abweichungs-Wache würde erneut
   strukturell blind. Muss AC-3 rot machen.
3. **Ceiling-Rückfall greift auf den Merker eines anderen Kanals zu**
   statt auf den Tier-1-Briefing-Anker. Kontaminiert die Vergleichsbasis
   eines Kanals mit einem Stand, den dieser Empfänger nie erhalten hat.
   Muss AC-4 rot machen.
4. **Die AC-11-Aggregation wählt den JÜNGSTEN statt den ÄLTESTEN
   Kandidaten.** Unterschlägt Änderungen für schlechter versorgte Kanäle —
   ein stiller Ausfall anderer Bauart als der ursprüngliche Bug. Muss
   AC-11 rot machen.

## Known Limitations

- **Kein Migrationsskript, aktives Auslaufen der Altdatei.** Die kanallose
  `{trip_id}_alarm_anchor.json` wird nach dem Deploy nicht mehr aktiv
  fortgeschrieben (jeder Schreibvorgang trägt jetzt einen Kanal-Suffix),
  bleibt aber als Rückfall bestehen, solange ein Kanal noch keine eigene
  Datei besitzt (AC-5, AC-7).
- **Ein Kanal ohne eigenen Merker vergleicht gegen den gröberen
  Tier-1-Stand** (AC-7) — bewusste Präzisionsgrenze von S1, kein Fehler.
  Eine Auflösung, die stattdessen den Merker eines anderen Kanals nutzt,
  wurde als Kontamination verworfen (s. Kontext-Dokument).
- **Vervierfachter Speicherbedarf für den rollierenden Alarm-Anker** je
  Trip (bis zu vier vollständige Segment-Schnappschüsse statt einem) —
  fachlich notwendig, nicht optimierbar ohne den Ticket-Zweck zu
  unterlaufen.
- **Kein opportunistischer Ceiling-Refresh mehr für Tier 2** — ein Kanal,
  dessen Merker altert, ohne dass ein neuer Alarm zugestellt wird, bleibt
  auf dem alten Merker sitzen, bis entweder ein neuer Alarm zugestellt wird
  oder die Kette beim Lesen auf Tier 1 zurückfällt (AC-4). Bewusst in Kauf
  genommen — s. „Bewusste Abkehr von Alt-Verhalten".
- **Scheibe S2 (Ortsvergleich) bleibt vollständig unangetastet** — der
  Compare-Δ-Anker hat weiterhin genau eine Vergleichsbasis je Preset/Ort,
  unabhängig vom Zustellkanal.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine neue — Amendment zu ADR-0056.
- **Rationale:** ADR-0056 führte den rollierenden Alarm-Anker mit
  Hybrid-Trigger (a) Alarmversand / (b) 4h-Ceiling ein, aber kanallos.
  Diese Scheibe erweitert denselben Mechanismus additiv um eine
  Kanal-Dimension und löst dabei Trigger (b) für den kanalscharfen
  Tier-2-Merker ab: die Alterungsprüfung wandert vom Schreib- in den
  Lesepfad (s. Implementation Details, „Schreibpfad — EIN Trigger"), weil
  ein zustellungsfreier Schreibvorgang unter der neuen Zustellungsbindung
  begrifflich unmöglich ist. Trigger (a) und die Tagesgrenzen-Prüfung
  (#823/#1916 AC-10) sowie die Radar-Isolation (AC-11 des ADR, nicht zu
  verwechseln mit AC-11 dieser Spec) bleiben unverändert — kein neues ADR
  nötig, ein Amendment-Absatz in `docs/adr/ADR-0056` genügt zur
  Dokumentation. ADR-0021 (geteilte `DeviationAlertEngine`) bleibt
  unangetastet: die Auslöse-Entscheidung ist weiterhin EIN gemeinsamer Lauf
  (E2), der genau einen `cached`-Wert erhält (jetzt aus der
  AC-11-Aggregation).

## Changelog

- 2026-08-19: Initiale Spec. Scope aus
  `docs/context/fix-1987-kanal-anker.md` (PO-Entscheidungen E1/E2, gewählte
  Umsetzungsvariante „eine Datei je Kanal") übernommen, ohne Abweichung.
- 2026-08-19 (Nachschärfung, Team-Lead-Review): (A) Ceiling-Schreib-\
  Trigger entfällt für den kanalscharfen Tier-2-Merker ersatzlos — Widerspruch
  zwischen Schreibpfad-Beschreibung und AC-4 aufgelöst, Alterungsprüfung
  wandert vom Schreib- in den Lesepfad. (B) Neues AC-11: der EINE gemeinsame
  Auswertungslauf vergleicht gegen den ÄLTESTEN gültigen Kandidaten unter den
  effektiven Kanälen, nicht „Implementierungsdetail der GREEN-Phase". (C)
  `reference_at` bleibt EIN gemeinsamer Wert (Korrektur einer früheren
  Fehlvorgabe); kanalgenaue Ausweisung nach „Nicht in dieser Scheibe"
  verschoben, Verweis auf #1948 S6. AC-4/AC-7 entdoppelt (AC-4 nur
  Alterungsfall, AC-7 nur „nie geschrieben"-Fall).
