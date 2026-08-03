---
entity_id: fix_1470_drilldown_ortszeit
type: feature
created: 2026-08-03
updated: 2026-08-03
status: draft
version: "1.0"
tags: [timezone, drilldown, telegram, issue-1470, issue-1465]
workflow: fix-1470-drilldown-ortszeit
---

# Fix #1470 — „heute" und „morgen" im Drilldown folgen der Ortszeit

## Approval

- [x] Approved — **PO Henning, 2026-08-03, wörtlich: „Ja, Ortszeit."** Vorgelegt beim
  Abschluss von #1465 als ausdrückliche Produktfrage („welche 24 Stunden sind *morgen*"),
  nicht als Fehlerbehebung.

## Purpose

Im Telegram-Drilldown beginnt „morgen" heute um Mitternacht **Weltzeit**. Auf Korsika
(UTC+2) zeigt das Fenster 02:00–02:00 Ortszeit: Die ersten zwei Stunden des Tages fehlen,
die letzten zwei des Vortages sind dabei. Bei einer Tour in Neuseeland wären es zwölf
Stunden — „morgen" zeigte dann überwiegend heute.

**Auch „heute" ist betroffen** (im Ticket zunächst nicht benannt, beim Messen gefunden):
`day_date = received_at.date()` ist das UTC-Datum. Kurz nach Ortsmitternacht meldet der
Drilldown den Vortag.

Nebenbefund aus #1465 — solange die Funktion abstürzte, kam niemand bis hierher.

## Source

- **File:** `src/services/trip_command_processor.py` — **Identifier:** `_handle_drilldown`
  (`:565-578`), `_handle_hours_drilldown` (`:625-638`); beide Blöcke wortgleich.
- **Zonen-Auflösung (unverändert nutzen):** `_display_tz(trip, day_date)` aus #1465,
  dahinter `tz_for_coords` über den Wegpunkt.
- **Haus-Helfer:** `src/utils/timezone.py` — `local_dt`, `UTC`.

## Estimated Scope

- **LoC:** ~40–70 Produktivcode + ~120 Testcode + ~40 Doku.
- **Files:** 1 Produktivdatei, 1 neue Testdatei.
- **Effort:** low — die Rechnung ist klein, der Aufwand liegt in der Reihenfolge (AC-4).

## Acceptance Criteria

- **AC-1:** Given ein Nutzer fragt im Drilldown „morgen" ab, während seine Tour in einer
  anderen Zeitzone liegt als der Server / When das Tagesfenster gebildet wird / Then
  beginnt es an der **Ortsmitternacht** der Tour und umfasst 24 Stunden dieses Ortstages —
  nicht die Weltzeit-Mitternacht.
  - Test: Tour auf Korsika, erste Zeile der Stundentabelle ist `00:00` Ortszeit.

- **AC-2:** Given ein Nutzer fragt „heute" ab, nachdem am Ort bereits Mitternacht war,
  aber vor Mitternacht Weltzeit / When die Antwort erzeugt wird / Then trägt sie das
  **Ortsdatum**, nicht das Weltzeit-Datum.
  - Test: `received_at` 22:30 UTC (= 00:30 Ortszeit), Kopfzeile nennt den Folgetag.

- **AC-3:** Given „heute" und „morgen" werden nacheinander abgefragt / When beide
  antworten / Then folgen sie **demselben Kalender** — „morgen" ist der Tag nach „heute",
  gemessen an derselben Ortszeit.
  - Test: eigener Fall, der beide Antworten gegeneinander hält.

- **AC-4:** Given die Fenstergrenze und die Beschriftung der Stundenzeilen werden
  bestimmt / When beides erzeugt wird / Then stammen sie aus **derselben**
  Zonen-Auflösung — sie können konstruktiv nicht auseinanderlaufen.
  - Test: keiner automatisierbar; im Bericht zu belegen, dass `tz` durchgereicht und nicht
    zweimal geholt wird.

- **AC-5:** Given eine Tour hat keine Etappe mit Wegpunkten / When die Zone aufgelöst wird
  / Then fällt sie auf die **importierte UTC-Konstante** zurück, nicht auf ein
  hartverdrahtetes `ZoneInfo("UTC")` — dieselbe Regel, die der Zeitzonen-Wächter
  durchsetzt.

- **AC-6:** Given der Umbau ist abgeschlossen / When die bestehenden Drilldown-Tests
  laufen / Then bleiben sie grün — insbesondere die sechs aus
  `test_telegram_drilldown_local_time_boundary.py` und die 13 aus #1465.

## Die Reihenfolge-Falle (Umsetzungshinweis)

`_display_tz(trip, day_date)` braucht ein `day_date`, das sich erst aus der Zone ergibt.
Auflösung in zwei Schritten:

1. **Welcher Kalendertag?** entscheidet die Zone der Etappe des **Weltzeit-Tages**
   (`_anchor_tz` → `_display_tz(trip, local_dt(received_at, UTC).date())`). Der
   Weltzeit-Tag liegt höchstens einen Tag daneben — damit findet man praktisch immer die
   Etappe, auf welcher der Nutzer gerade steht. Keine zweite Auflösung: es ist derselbe
   `_display_tz`-Aufruf, nur mit einem Tag, der noch nicht von der Zone abhängt.
2. **Fensterbeginn und Beschriftung** nehmen dann `_display_tz(trip, day_date)`, die
   etappengenaue Zone dieses Tages, und **reichen sie durch**.

**Verbleibender Randfall:** Wechselt der Wanderer **an genau diesem Tag** die Zeitzone,
kann die Etappe des Weltzeit-Tages eine andere Zone tragen als die des Ortstages. Der
Fehler ist dann die Zonendifferenz **zweier benachbarter Etappen** — in aller Regel null,
sonst eine Stunde. Rückfall unverändert: keine Etappe für den Tag ⇒ erste Etappe mit
Wegpunkten ⇒ importierte UTC-Konstante.

**Entwicklung dieser Entscheidung (2026-08-03).** Die erste Fassung ankerte an der
**ersten Etappe der Tour** und beschrieb den Randfall als „Sekunden bis Stunden um
Mitternacht". Beides war falsch:

- Der Adversary (F003) hat mit einer Tour Neuseeland → Korsika **zehn Stunden** Abweichung
  vorgeführt — die Spanne entspricht der Zonendifferenz zwischen *erster* und *aktueller*
  Etappe, nicht einem Mitternachtsfenster.
- Der Entwickler hat daraufhin den besseren Anker vorgeschlagen und beziffert
  (`_display_tz(trip, received_at.date())` statt `_trip_tz`): vier Messpunkte, davon zwei
  vorher falsch, alle vier danach richtig.

Damit schrumpft der Fehler von „Zonenspanne der ganzen Tour" (bis 24 Stunden) auf
„Zonenwechsel an genau diesem Tag" — eine Zeile Code für eine Größenordnung.

## Nachweisführung

Kein Mailversand, keine Staging-Mail nötig. **Glücksfall des Zuschnitts:** Der heutige
Zustand **ist** die Mutation — „zurück auf `received_at.tzinfo`" ist wörtlich der Code,
der vor dieser Lieferung dort steht. Der rote Lauf gegen `5bfe06b5` ist damit bereits die
halbe Gegenprobe; die zweite Hälfte (grün nach dem Fix, erneut rot nach Rückmutation) ist
nachzuliefern.

Die Testsuite ist per `conftest.py` auf eine Halbstunden-Zone verankert (#1402). Ein Test
muss das **ausnutzen**: drei Kalender sind an der Uhrzeit unterscheidbar — Weltzeit `02:00`,
Prozess-Zone `04:30`, Ortszeit `00:00`. Eine versehentliche Umstellung auf die
Prozess-Zone fiele am Halbstunden-Rest sofort auf.

## Known Limitations

Nicht Teil dieser Lieferung, beim Messen gefunden und **gemeldet statt angefasst** — alle
in derselben Datei, alle dieselbe Verwechslung:

| Ort | Wirkung |
|---|---|
| `:449-450` `_handle_query` | Auslöser für `/heute`, `/morgen`, `/glance` — dieselbe UTC-Datums-Verwechslung, aber sie **löst einen Versand aus** statt nur eine Anzeige. Eigene Abwägung. |
| `:379` `command_date` | Bezugstag für `### ruhetag` — kurz nach Ortsmitternacht ggf. der Vortag |
| `:974` `_show_status`, `:1125` `_show_now` | `date.today()` = **Prozess**-Zeitzone; auf dem UTC-Server zufällig richtig, in der Testsuite bereits nicht mehr |

Gehören in ein Folge-Ticket. Außerhalb dieser Datei fand sich nichts.

## Changelog

- 2026-08-03 — angelegt nach PO-Entscheid; „heute" beim Messen als ebenfalls betroffen
  erkannt (im Ticket zunächst nur „morgen" benannt).
