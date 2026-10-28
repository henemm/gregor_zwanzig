# ADR-0103: Semaphorenzahlen des parallelen Abruf-Bausteins (Startwert Open-Meteo 3)

- **Status:** Akzeptiert
- **Datum:** 2026-10-28
- **Bezug:** Issue #1539 (Epic #2138), Scheibe S3, Spec
  `docs/specs/modules/feat_1539_s3_trip_alarm_parallel.md`; Baustein-Spec
  `docs/specs/modules/feat_1539_s1b_s2_abruf_baustein.md`; verwandt mit ADR-0038 (harte
  Laufzeitgrenze je Lauf), ADR-0100 (Regel-Budget: Prüfdatum +90 Tage)
- **Prüfdatum:** 2027-01-26

## Kontext

Der Trip-Alarm rief das Wetter der fälligen Etappen strikt nacheinander ab. Vorher-Messung im
Prod-Journal: Laufdauer im p95 37 s je Lauf, Spitze 215 s, Abbrüche an der 180-s-Grenze
(ADR-0038). Mit S3 nutzt der Trip-Alarm als erster echter Nutzer den gemeinsamen Baustein
`services.parallel_fetch.fetch_ordered`. Der Baustein begrenzt die Last je Provider über eine
Semaphore (Slots); jeder Slot umspannt die ganze Aufgabe inklusive der Wiederholungsversuche
(Open-Meteo: 5 Versuche bei 502/503/504). Die Slotzahlen waren bisher eine nicht gemessene
Annahme im Code — zu viele Slots riskieren 503/429 von Open-Meteo, zu wenige verschenken den
Zeitgewinn.

## Entscheidung

1. **Startwert der Slots je Provider:** Open-Meteo = **3** Slots; MeteoAlarm = 1 und
   Météo-France = 4 bleiben unverändert. Unbekannte Provider erhalten 3.
2. **Stellschraube:** Die Slotzahl ist ohne Code-Änderung per Umgebungsvariable
   `GZ_PARALLEL_FETCH_SLOTS_OPEN_METEO` (allgemein `GZ_PARALLEL_FETCH_SLOTS_<PROVIDER>`)
   nachstellbar; der Executor per `GZ_PARALLEL_FETCH_WORKERS` (Default 8).
3. **Messmethode:** Gemessen werden im Prod-Journal vor und nach der Umstellung, bei Slotzahl 3:
   - der Anteil der Open-Meteo-Antworten mit Status **503** bzw. **429** an allen Abrufen,
   - die Etappen-Abrufdauer (Zeile „Etappe X: Abruf in N s") als **p50** und **p95**,
   - ergänzend die Laufdauer je Trip-Alarmlauf und die Zahl der Abbrüche an der 180-s-Grenze.
4. **Messquelle:** Prod-Journal, gelesen per `sudo -n -u claude-gregor journalctl` (für `hem`
   ohne diesen Weg nicht lesbar). Auf Staging ist echte Nebenläufigkeit nicht messbar
   (`NOT_MEASURABLE_ON_STAGING`); die Nachmessung ist ein eigener Schritt nach dem Deploy.
5. **Frist bleibt hart (ADR-0038):** der Baustein erhält immer eine endliche Frist — im
   Alarmlauf die Lauf-Grenze (`run_started_at + 180 s`), sonst etwa 60 s ab Aufruf.
6. **Prüfdatum 2027-01-26** (+90 Tage, Regel-Budget ADR-0100): Am Prüfdatum wird die Slotzahl
   gegen die Messwerte bestätigt oder korrigiert. Steigt der 503/429-Anteil gegenüber der
   Vorher-Messung spürbar, wird die Zahl gesenkt; bleibt er gleich und hängt p95 an der
   Slotgrenze, darf sie steigen.

## Verworfene Alternativen

- **Keine Semaphore, nur der Executor begrenzt (8):** verworfen — mehrere Nutzer und Trips
  würden Open-Meteo gleichzeitig mit bis zu 8 Abrufen samt Wiederholungen belasten.
- **Slotzahl 1 (seriell wie bisher):** verworfen — kein Zeitgewinn, die Abbrüche an der
  180-s-Grenze blieben.
- **Messroutine im Code (eigene Zähler/Endpunkt):** verworfen — das Prod-Journal enthält
  Status und Dauer bereits; ein zusätzlicher Zähler wäre eine weitere Pflichtfläche.

## Konsequenzen

- **Positiv:** Kürzere Wartezeit je Trip bei mehreren fälligen Etappen; die Last auf Open-Meteo
  bleibt begrenzt und ist ohne Deploy nachstellbar.
- **Negativ / Preis:** Laufende Threads sind nicht abbrechbar; eine zu späte Etappe wird
  verworfen (`timeout`), ihr Thread hält den Slot bis zum Ende.
- **Folgepflichten:** Nachmessung nach dem Deploy und erneut am Prüfdatum; S4 bis S6 (Radar,
  Briefing, Ortsvergleich) nutzen dieselben Slots und gehen in dieselbe Messung ein.
