# Mini-Spec: Verifizieren, ob #1584 den in #1555 gemeldeten Alarm-Ausfall behebt

**Issue #1555.** Ursprünglich mit einer falschen Ursachenkette dokumentiert
(Tier-Lücke → Free-Limit → geteiltes Tagesbudget starvt NowCast). Am
2026-08-07 am laufenden Prod-System widerlegt: das betroffene Konto stand auf
`tier: premium`, es existierte nicht mal eine `alert_daily_count.json` — das
Tageslimit griff nachweislich nicht. Die wirkliche Ursache steckt in **#1584**:
Beide Alarmwege lasen `segment.end_time`, das hart bei `arrival_time + 2h`
endete — die Gefahren-Überwachung fürs Tagesziel war strukturell abgeschaltet,
sobald die Etappe zeitlich absolviert war.

**Diese Scheibe ändert keinen Code.** #1584 hat den Fix bereits geliefert
(`src/services/trip_segments.py:244-290`, PR #1590, live seit 2026-08-08
06:56 UTC; Folge-Scheibe C für den Ortsvergleich-Pfad PR #1598, live seit
10:40 UTC). Aufgabe hier: nachmessen, ob dieser Fix das ursprünglich in #1555
gemeldete Symptom (kein NowCast-Alarm für Trip „KHW 403" trotz Hagelgewitter)
tatsächlich behebt — und danach #1555 mit Beleg schließen oder eine
verbleibende Lücke präzise benennen.

## Ausgangslage (bereits am Code verifiziert, Grundlage dieser Spec)

`trip_segments.py:258` liest jetzt `day_window_end_hour` (Default 4/19,
`src/app/day_window.py:20-35`) statt `arrival_time + timedelta(hours=2)`.
Für den Originalvorfall (2026-08-07, Trip `5f534011`):

| Ereignis | UTC | Ortszeit (UTC+2) | Innerhalb Tagesfenster (bis 19:00 Ortszeit)? |
|---|---|---|---|
| Ankunft Etappe 10 | 11:18 | 13:18 | Start des Ziel-Segments |
| Hagelgewitter 1 | 15:00 | 17:00 | ja — vom alten Code (Ende 15:18) NICHT erfasst, vom neuen Code (Ende 19:00) erfasst |
| Hagelgewitter 2 | 16:00 | 18:00 | ja — dito |
| Hagelgewitter 3 | 20:00 | 22:00 | nein — liegt nach 19:00 Ortszeit, auch vom neuen Segment nicht erfasst |

Für die ersten beiden Ereignisse sollte die Gefahren-Überwachung jetzt greifen.
Für das dritte (nächtliche) Ereignis behauptet eine 42 Tage alte Notiz, es
werde separat über `fetch_night_weather()` (Ankunft → 06:00) abgedeckt — diese
Behauptung ist **nicht** am aktuellen Alarm-Sendepfad nachgemessen und wird
hier erstmals geprüft, nicht wiederholt.

## Was verifiziert wird

- Dass der Ziel-Segment-Zuschnitt am ausgelieferten Code für die
  Originalvorfall-Zeiten tatsächlich bis 19:00 Ortszeit reicht (nicht nur
  laut Diff, sondern am laufenden Verhalten).
- Dass der Alarm-Sendepfad (nicht nur Briefing/Aggregation) für ein Segment
  mit dieser Ausdehnung eine Bewertung durchführt statt `No fresh weather
  data for trip <id>` zu loggen.
- Ob das nächtliche Ereignis (nach 19:00 Ortszeit) über einen separaten Pfad
  am Alarm-Sendepfad abgedeckt ist — gemessen, nicht aus der alten Notiz
  übernommen.
- Ob #1594 (Ruhezeiten-Sammelzustellung) oder #1599
  (Tagesfenster-Obergrenze-Diskrepanz) das konkrete Originalvorfall-Fenster
  (17:00/18:00 Ortszeit) beeinträchtigen — beide sind offen, aber laut ihrer
  eigenen Beschreibung nicht auf dieses Fenster bezogen; das wird hier nicht
  angenommen, sondern kurz gegengelesen.

## Was sich nicht ändern darf

- Kein Eingriff in `trip_segments.py`, `trip_alert.py`,
  `weather_change_detection.py` oder die #1584-Lieferung — diese Scheibe
  liest und misst, ändert nicht.
- Kein lokaler Neustart des Live-Servers (Produktion). Falls ein Nachweis am
  laufenden System nötig ist: Staging-Reproduktion nach dem in #1584 bereits
  benutzten Muster (Wegwerf-Trip, echte Zustellung) oder Log-/Code-Nachweis
  an der Produktion — nie ein Prod-Neustart zu Testzwecken.
- #1555 wird nicht geschlossen, wenn die Messung eine Lücke zeigt — auch
  nicht teilweise oder „im Wesentlichen behoben".

## Acceptance Criteria

- **AC-1:** Given Trip `5f534011`, Etappen-Ankunft 11:18 UTC (13:18 Ortszeit),
  Tagesfenster-Default 4/19 / When das Ziel-Segment am ausgelieferten Code
  (Stand 2026-08-08, PR #1590) für diese Ankunft gebildet wird / Then endet
  es bei 19:00 Ortszeit (17:00 UTC), nicht bei 13:18+2h=15:18 Ortszeit.
  - Test: Direkter Aufruf/Nachvollzug der Segmentbildung mit den
    Originalvorfall-Daten (Code lesen + Ausführen, kein Dateiinhalt-Check).
- **AC-2:** Given ein Ziel-Segment, das bis 19:00 Ortszeit reicht, und ein
  Gewitterereignis um 17:00/18:00 Ortszeit innerhalb dieses Fensters / When
  der Alarm-Sendepfad (`trip_alert.py`, Deviation- und/oder Radar-Check)
  darauf angewendet wird / Then wird das Ereignis bewertet (kein `No fresh
  weather data for trip <id>` für dieses Segment) — reproduziert entweder an
  Produktions-Logs seit 06:56 UTC oder an einer Staging-Nachstellung.
- **AC-3:** Given das dritte Ereignis um 22:00 Ortszeit (nach dem
  Tagesfenster-Ende) / When geprüft wird, ob ein anderer Pfad
  (`fetch_night_weather()` o.ä.) dieses Ereignis am **Alarm-Sendepfad**
  abdeckt / Then wird das Ergebnis konkret berichtet (abgedeckt oder Lücke)
  — nicht aus der bestehenden Memory-Notiz übernommen, sondern selbst
  nachgemessen.
- **AC-4:** Given die Messergebnisse aus AC-1 bis AC-3 zeigen, dass der
  Alarm-Ausfall aus #1555 durch #1584 behoben ist (kein Restbefund) / When
  das Ergebnis dokumentiert wird / Then bekommt #1555 einen Abschluss-
  Kommentar mit Verweis auf #1584 (PR #1590/#1598) und den konkreten
  Messbelegen, und das Issue wird geschlossen.
- **AC-5:** Given die Messung zeigt stattdessen eine verbleibende Lücke
  (z. B. AC-3 negativ, oder #1594/#1599 betreffen das Originalfenster doch)
  / When das Ergebnis dokumentiert wird / Then bleibt #1555 offen, der
  Restbefund wird präzise benannt (Code-Stelle, Zeitfenster, Beleg) und nach
  Nebenbefund-Triage eingeordnet (eigenes Issue nur bei nutzersichtbarem
  Fehlverhalten) — **kein** Schließen mit Vorbehalt.

## Known Limitations

- Der ursprüngliche Vorfall (2026-08-07) liegt in der Vergangenheit; echtes
  Wetter kann nicht erneut abgespielt werden. Nachweis läuft über
  Code-Verhalten mit den Originalvorfall-Zeiten plus, falls nötig, eine
  synthetische Staging-Reproduktion nach dem #1584-Muster.
- Diese Scheibe bewertet nicht, ob #1594/#1599 selbst behoben werden müssen —
  nur, ob sie das hier betrachtete Zeitfenster verfälschen.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Reine Verifikation eines bereits gemäß ADR-0035
  (ein Tagesfenster, wirksam auf Anzeige und Bewertung) ausgelieferten Fixes;
  keine neue Architekturentscheidung.

## Manuelle Test-Schritte

1. Segmentbildung für die Originalvorfall-Ankunft nachvollziehen (AC-1).
2. Alarm-Sendepfad-Verhalten für das 17:00/18:00-Fenster belegen — Prod-Log
   seit 06:56 UTC durchsuchen (`journalctl`/Log-Datei, sudo als
   `claude-gregor` falls Rechte fehlen) oder Staging-Reproduktion (AC-2).
3. Nächtliches Ereignis (22:00 Ortszeit) am Alarm-Sendepfad prüfen (AC-3).
4. #1594/#1599 gegenlesen, ob sie das Originalfenster betreffen.
5. Je nach Ergebnis: Abschluss-Kommentar + Close (AC-4) oder Lücke benennen,
   Issue offen lassen (AC-5).

## Gegenprobe (Mutations-Pflicht)

Entfällt — diese Scheibe ändert keinen Code, es gibt nichts zu verfälschen.
Die Mutations-Pflicht gilt für Implementierungs-Scheiben; hier tritt an ihre
Stelle die Pflicht, jede AC an einem echten Nachweis (Log, Code-Ausführung,
Staging-Reproduktion) festzumachen statt an einer Annahme.
