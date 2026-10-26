# ADR-0102: Plausibler GPS-Fix aus Premium-SMS übersteuert die Planposition

- **Status:** Akzeptiert
- **Datum:** 2026-10-26
- **Bezug:** Issue #2327 (Epic #2506), Spec `docs/specs/modules/feat_2327_gps_etappenfortschritt.md`;
  verwandt mit ADR-0049 (Premium-SMS als vierter Kanal), ADR-0088 (Push weckt, Poll bleibt
  Wahrheit), ADR-0093, ADR-0095 (Kanal-Parität), ADR-0101 (Read-Modify-Write mit Merge)

## Kontext

Bisher galt: „Planposition ist die legitime Positionsquelle — es gibt kein GPS“
(`trip_segments.points_with_passage_times`). Wo der Wanderer steht, wurde allein aus dem
Zeitplan der Etappe interpoliert. Garmin inReach hängt an jede Nachricht an die Dienstnummer aber
die echte Position an (`… inreachlink.com/<Code>  (46.6370, 12.7678)`, belegt durch zwei echte
Nachrichten des PO vom 26.10.2026). Wer schneller oder langsamer als geplant läuft, bekommt
Briefing, Alarme, Radar und Befehlsantworten sonst für den falschen Ort.

## Entscheidung

1. **Ein plausibler GPS-Fix übersteuert die Planposition.** Plausibel heißt: höchstens 100 m
   (inklusive) neben der **Strecke** der Heute-Etappe — gemessen als Punkt-zu-Strecke-Abstand mit
   lokaler Equirectangular-Projektion, nicht als Abstand zum nächsten Trackpunkt. Der Fix friert
   die Position nicht ein: ab dem Meldezeitpunkt schreibt die Positionsquelle sie nach Plan-Tempo
   (Segmentzeiten) entlang der Strecke fort, begrenzt auf das Etappenende; bei Abfrage zum oder
   vor dem Meldezeitpunkt gilt der Fix selbst.
2. **Eindeutigkeit vor Wirkung:** liegt der Punkt auf der Heute-Etappe mehrerer Trips desselben
   Nutzers, wird er verworfen und geloggt — ein falsch zugeordneter Fix ist schlimmer als keiner.
3. **Gültigkeit an der Etappe, nicht an der Uhr:** der Fix gilt für denselben Trip und dasselbe
   Etappen-Datum, auch in einer geplanten Rast; nach Ankunft oder am Folgetag fällt die
   Quelle auf die Planposition zurück (Prüfung zur Lesezeit).
4. **Neuester Fix gewinnt** (Journal-Zeitstempel), auch rückwärts auf der Strecke; ein älterer
   Eintrag ersetzt nie einen jüngeren.
5. **Wirkung zentral in der Positionsquelle** (`position_at_time`, `points_with_passage_times`,
   Keyword `user_id`): alle Konsumenten und alle vier Kanäle gehen von derselben Position aus,
   keine Kanal-Sonderlogik. Ohne `user_id` ist das Ergebnis bit-identisch zum Stand davor — es
   wird nie über Nutzergrenzen hinweg nach einem Fix gesucht.
6. **Persistenz je Nutzer** in `data/users/<user_id>/position_fix.json`, nicht im Trip-JSON;
   Read-Modify-Write mit Merge (ADR-0101). Die `user_id` stammt ausschließlich aus der Go-Antwort
   des Lern-Endpunkts, nie `default`.
7. **Reine Positions-SMS** (kein Befehlstext) nimmt den Fix auf und löst keine bezahlte Antwort aus.

## Verworfene Alternativen

- **Fix ungeprüft übernehmen:** verworfen — ein Abstecher, ein Hüttenbesuch abseits oder ein
  Fehlfix würde Alarme und Radar an einen Ort ohne Bezug zur Route verschieben.
- **Abstand zum nächsten Trackpunkt:** verworfen — Trackpunkte liegen teils kilometerweit
  auseinander; ein Punkt mitten auf einem langen Abschnitt würde fälschlich verworfen.
- **Feste Gültigkeitsdauer in Stunden:** verworfen — zu kurz für lange Etappen mit Rast, zu lang
  über Mitternacht.
- **Fix im Trip-JSON:** verworfen — Go roundtrippt das Trip-JSON und kennt das Feld nicht.

## Folgen

- Etappen ohne passenden Nutzer-GPX (nur Wegpunkte) haben keinen Track zum Snappen; dort wird kein
  Fix übernommen (Known Limitation der Spec).
- Die 100-m-Grenze ist eine feste Konstante (`position_fix.FIX_RADIUS_M`); GPS-Ungenauigkeit wird
  nicht modelliert.
