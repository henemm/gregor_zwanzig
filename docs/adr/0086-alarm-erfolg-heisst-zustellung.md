# ADR-0086: Alarm-Erfolg heißt Zustellung — Totalausfall wird begrenzt wiederholt statt als Erfolg gebucht

- **Status:** Akzeptiert
- **Datum:** 2026-10-09
- **Bezug:** GitHub-Issue #1405 Scheibe 1 (Epic #2505), Spec
  `docs/specs/modules/fix_1405_s1_alarm_zustellung.md`; löst #684 AC-3 ab; präzisiert #1459 D4
  (v1.4) und #1701 D7; setzt ADR-0021 (Zeilen 314/337: "Buchung nur nach erfolgreicher
  Zustellung") um

## Kontext

`NotificationResult.sent` bedeutet heute "mindestens ein Kanal wurde betreten". Scheitern alle
Transporte, bleibt `sent=True`; alle sechs Alarm-Aufrufer (Trip und Ortsvergleich) buchen den Alarm
dann als erledigt (Zustand, Sperrzeit, Tageskontingent, Ereignis-Identität) und wiederholen ihn
nie. Ein komplett gescheiterter Alarm geht still verloren. Das widerspricht ADR-0021 und dem
PO-Auftrag #1405 ("Erfolg heißt Wirkung").

Die heutige Semantik ist jedoch dreifach dokumentiert:

1. **#684 AC-3:** ein transienter Sendefehler lässt das Recording stehen (Begründung: sonst
   Alarm-Spam alle 30 Minuten; Lehre "Alert-Recording nie an Live-SMTP-Erfolg koppeln").
2. **#1459 D4 (v1.4):** `reachable_channels` wurde eingeführt, damit die Cockpit-Zahl unverändert
   bleibt ("AC-11 gewinnt").
3. **#1701 D7:** "die Buchung hinter den `try` ziehen ist FALSCH" — weil sie die Unterscheidung
   zwischen "betreten" und "zugestellt" zerstört hätte.

Es gibt keinen Mechanismus, der Alarme nach Totalausfall nachliefert (der Nachlieferweg aus #1662
gilt nur für Briefings, ein Zähler wurde dort bewusst abgelehnt). Die Empfangslage unterwegs ist
unvorhersehbar; jeder Alarm, der verloren geht, ist ein verlorener Warnhinweis.

## Entscheidung

- **`sent` heißt "mindestens ein Kanal hat zugestellt".** `sent_channels` wird erst nach
  erfolgreichem Send gefüllt (Muster `send_trip_report`). Das neue Feld `attempted_channels`
  ("betreten", nach dem Versuch eingetragen) übernimmt die bisherige Rolle von `sent_channels`
  für `reachable_channels` des Alarm-Protokolls. Damit bleibt die von #1459 D4 und #1701 D7
  geforderte Unterscheidung "betreten" vs. "zugestellt" erhalten — sie wandert nur auf ein
  ehrlich benanntes Feld. Die Cockpit-Zahl (#1459 AC-11) und "konfiguriert, aber nichts
  zugestellt" (AC-15) bleiben unverändert.
- **Drei Ausgänge statt eines Booleans.** Die abgeleitete Property `delivery_outcome` kennt
  `delivered`, `blocked_only`, `transport_failed` (plus `no_channel` für den unveränderten Fall
  "kein Kanal konfigurierbar"). Ein einzelnes `not sent` wäre als Wiederholungssignal falsch,
  weil ein Alarm mit ausschließlich bewusst gesperrten Kanälen (SMS-Tageslimit) sonst alle
  30 Minuten gegen dieselbe Sperre liefe.
  - `delivered` (auch Teilerfolg): buchen wie bisher, nicht wiederholen — sonst Dubletten auf den
    funktionierenden Kanälen.
  - `blocked_only`: terminal, buchen, nicht wiederholen.
  - `transport_failed`: nicht buchen, Fehlversuchs-Backoff.
  - **Mischfall** (gesperrt + Transportfehler, nichts zugestellt) = `transport_failed`: der
    gescheiterte Kanal soll erneut versucht werden; der gesperrte bleibt durch seine Sperre
    ohnehin gesperrt. Unterscheidung Sperre/Fehler: Sperre = Key in `blocked_reason_codes`;
    Premium-SMS-Transportfehler (in `blocked_channels` ohne Code) ist ein Transportfehler.
- **Backoff statt Sofort-Wiederholung und statt Zähler.** Bei `transport_failed` wird im
  bestehenden `ThrottleStore` ein Backoff mit eigenem Scope (`<scope>:retry`, 30 Minuten) je
  **Ereignis** gesetzt (nicht je Trip: ein neues, anderes Ereignis wird nicht blockiert). Während
  des Backoffs gibt es weder Versand noch Protokolleintrag. Das löst die Spam-Sorge aus #684:
  höchstens ein Versuch und ein Protokolleintrag je 30 Minuten je Ereignis.
- **Kein Versuchsdeckel.** Ein Zähler wurde bei #1662 abgelehnt; die Wiederholung endet, wenn
  das Ereignis entfällt oder ein Kanal zustellt.
- **Parität:** dieselbe Regel in allen drei Versandpfaden (`send_official_alert`,
  `_dispatch_alert_message`, `send_multi_location_official_alert`) und in allen sechs Aufrufern
  (Trip- und Ortsvergleich-Änderungs-, Radar- und Amtlich-Alarm). Der Sammelpfad meldete eine
  Tageslimit-Sperre bisher als `sent=True`; das wird angeglichen.
- **Ablösung:** #684 AC-3 (transienter Fehler ⇒ `True`) gilt nicht mehr. #1459 D4 und #1701 D7
  bleiben in ihrer Absicht gültig; die Formulierung "`sent_channels` = versucht" wird durch
  `attempted_channels` ersetzt. #1701 D7 ("Buchung nicht hinter den `try` ziehen") bezog sich auf
  den Erhalt der Unterscheidung — diese bleibt erhalten, der Zug ist jetzt richtig, weil das
  Versuchs-Feld separat existiert. Die Ratsche im Wächter (`test_success_status_guard.py`)
  sinkt dadurch (B14a/B14c entfallen) statt zu steigen.

## Verworfene Alternativen

- **Status quo (Recording nicht an Zustellung koppeln, #684 AC-3):** verliert Alarme still bei
  Totalausfall, widerspricht ADR-0021 und #1405.
- **`sent` unverändert lassen und ein zweites Feld `delivered` einführen:** alle Aufrufer lesen
  `sent`; ein Feld, das niemand liest, ändert nichts. `sent` ist der falsche Name für "betreten".
- **Zwei Ausgänge (`not sent` ⇒ Retry):** wiederholt Alarme mit reiner Sperre alle 30 Minuten.
- **Versuchsdeckel/Zähler je Ereignis:** bei #1662 abgelehnt (zusätzlicher Zustand, eigener
  Aufräumbedarf); der Backoff begrenzt Last und Dubletten ausreichend.
- **Backoff je Trip:** würde ein neues, dringenderes Ereignis hinter dem Fehlschlag eines alten
  verstecken.
- **Sofort-Wiederholung im selben Lauf:** hilft nicht bei Dauerausfall und verdoppelt Dubletten
  bei mehrdeutigen Fehlschlägen.

## Konsequenzen

- **Positiv:** Ein komplett gescheiterter Alarm geht nicht mehr still verloren; Zustand,
  Sperrzeit und Tageskontingent buchen nur belegte Zustellung. Das Wort "gesendet" stimmt. Die
  Wächter-Einträge B14a/B14c/B1/B15/B16 entfallen; das Kommando "report" meldet dem Nutzer das
  echte Ergebnis.
- **Negativ / Preis:** (1) **Dauerausfall:** ohne Deckel bis zu 48 Versuche je Ereignis und Tag.
  (2) **Mehrdeutige Fehlschläge** (Timeout nach Annahme durch den Anbieter) können bis zu 48
  Dubletten je Tag und Ereignis erzeugen; beim SMS-Timeout wird das Tageskontingent zusätzlich
  unterzählt. Bewusst in Kauf genommen: ein verlorener Warnhinweis wiegt schwerer als eine
  Dublette. (3) Ein nach Totalausfall wiederholter Radar-Alarm kommt frühestens nach 30 Minuten.
  (4) Im Trip-Pfad wird eine reine Sperre jetzt terminal gebucht statt jeden Lauf neu geprüft.
- **Folgepflichten:** `attempted_channels` wird nach dem `try` eingetragen (der Wächter
  Klasse 1c meldet jedes nackte `append` vor einem riskanten `try`); neue Alarmarten oder
  Kanäle lesen `delivery_outcome` statt `sent`; Backoff-Schlüssel ist immer ein
  Ereignis-Fingerabdruck. Jede Änderung der 30-Minuten-Frist oder ein Versuchsdeckel braucht
  ein neues ADR.
