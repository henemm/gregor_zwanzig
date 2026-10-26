---
entity_id: feat_2327_gps_etappenfortschritt
type: feature
created: 2026-10-26
updated: 2026-10-26
status: draft
workflow: feat-2327-gps-etappenfortschritt
version: "1.0"
tags: [premium-sms, inbound, gps, position, planposition, etappe, adr-0102]
---

# GPS-Etappenfortschritt aus eingehender Premium-SMS (Issue #2327, Epic #2506)

## Approval

- [ ] Approved

## Purpose

Enthaelt eine eingehende Garmin-inReach-Nachricht Koordinaten, wird daraus der tatsaechliche
Etappenfortschritt des Nutzers abgeleitet -- aber nur, wenn der Punkt hoechstens 100 m von der
geplanten Route der Heute-Etappe entfernt liegt. Die Positionsquelle (`trip_segments`) liefert
dann diesen Fix statt der Planposition, sodass Briefing, Alarme, Radar und Befehlsantworten in
allen vier Kanaelen (E-Mail, Telegram, SMS, Premium-SMS) von der echten Position ausgehen. Das ist
eine bewusste, PO-bestaetigte Abweichung vom bisherigen Grundsatz "Planposition ist die legitime
Positionsquelle" und wird in ADR-0102 festgehalten.

## Source

- **Eingang:** `src/services/inbound_sms_reader.py` -- `split_link_code` (eine Zerlegungsstelle,
  D9 #2154), `_poll_journal`, `_verarbeite_befehl` (`user_id` nur aus der Go-Antwort, AC-9 #1676)
- **Positionsquelle:** `src/services/trip_segments.py` -- `position_at_time`,
  `points_with_passage_times`, `points_along_remaining_route`; Vorbild `points_from_km`
- **Neu:** `src/services/position_fix.py` -- Plausibilitaet, Snapping, Persistenz, Gueltigkeit
- **Neu in** `src/utils/geo.py` -- Punkt-zu-Strecke-Abstand

> **Schicht-Hinweis:** ausschliesslich Python-Core (`src/services/`, `src/utils/`). Kein Go, kein
> Frontend, kein neuer Endpoint. Die `user_id` kommt unveraendert aus der bestehenden Go-Antwort
> (`/api/internal/premium-sms-learn`).

> **Querschnitts-Pruefpunkte:**
> - Trip/Ortsvergleich-Teilung: nicht betroffen (kein Editor-/UI-Baustein; Ortsvergleich hat keine
>   Etappen und keine Positionsquelle). Die Wirkung sitzt in der geteilten Positionsquelle, nicht
>   in Trip- oder Compare-Code.
> - Mandantentrennung: Fix je Nutzer, Test mit zwei Nutzern (AC-9).
> - Kanaele: alle vier benannt, gleiche Wirkung, keine Kanal-Sonderlogik (AC-8).

## Belegtes Koordinatenformat

Echte Nachrichten des PO vom 26.10.2026 (Fixture-Vorgabe, woertlich):

- `Heute inreachlink.com/gS5ySf-2sYCWmJQksXnjeHw  (46.6370, 12.7678)`
- `so morgen  inreachlink.com/gGF87yQgGC0h_fnW_2_ngUA  (46.6124, 12.8676)`

Aufbau: Befehlstext, Link `inreachlink.com/<Code>`, zwei Leerzeichen, dann `(lat, lon)` mit
Dezimalpunkt und vier Nachkommastellen. Der Parser ist tolerant: variable Leerzeichen, auch
negative Werte und andere Nachkommastellenzahl; ohne Koordinaten bleibt das Verhalten
unveraendert; eine Klammer mit Unsinn oder ungueltigem Bereich (|lat| > 90, |lon| > 180) wird
ignoriert, der Befehl laeuft normal weiter. Die Koordinaten stehen HINTER dem Link-Marker, an dem
`split_link_code` heute den Befehlstext abschneidet -- der Befehlstext vor dem Link darf durch die
Koordinaten nicht veraendert werden.

## Estimated Scope

- **LoC:** +250..350 produktiv (Tests, Docs und ADR zaehlen nicht) -- `loc_limit_override` noetig
  (`workflow.py set-field loc_limit_override 500`)
- **Files:** 4 Code (1 neu) + 1 Laufzeitdatei, 3 Docs/ADR (1 neu), 3 Testdateien + Fixtures
- **Effort:** high. Risk MITTEL-HOCH: zentrale Positionsquelle mit fuenf Konsumenten; ein
  Fehlsnapping verfaelscht Alarme und Regenradar.

### Affected Files

| File | Change Type | Description |
|------|-------------|-------------|
| `src/services/inbound_sms_reader.py` | MODIFY | `extract_position(text)` neben `split_link_code`; Aufruf in `_verarbeite_befehl`/`_poll_journal` erst NACH `user_id` aus der Go-Antwort; reine Positions-SMS: Fix aufnehmen, keine bezahlte Antwort |
| `src/utils/geo.py` | MODIFY | Punkt-zu-Strecke-Abstand mit lokaler Equirectangular-Projektion, liefert Abstand und Streckenanteil |
| `src/services/position_fix.py` | CREATE | `record_position_fix`, Heute-Etappen-Suche ueber alle Trips des Nutzers, Plausibilitaet (<= 100 m), Fortschritts-km, Gueltigkeit, Persistenz |
| `src/services/trip_segments.py` | MODIFY | `position_at_time` / `points_with_passage_times` bevorzugen gueltigen Fix, sonst Planposition (Vorbild `points_from_km`); Docstring "Planposition ist die legitime Positionsquelle" anpassen |
| `data/users/<user_id>/position_fix.json` | CREATE (Laufzeitdatei) | eigene Datei je Nutzer, nicht im Trip-JSON |
| `docs/adr/0102-gps-fix-uebersteuert-planposition.md` | CREATE | Entscheidung dokumentieren |
| `docs/adr/README.md` | MODIFY | Index-Eintrag 0102 (`tests/test_adr_index_drift.py`) |
| `docs/reference/premium_sms_format.md` | MODIFY | §4 "Befehlseingang" um Koordinaten ergaenzen |
| `tests/unit/test_position_fix_parser.py` | CREATE | Parser gegen die zwei echten Texte |
| `tests/unit/test_position_fix_snapping.py` | CREATE | Snapping, 99/101 m, Ablauf, Mehrdeutigkeit, Rueckwaerts-Fix, Zwei-Nutzer |
| `tests/tdd/test_position_fix_inbound_e2e.py` | CREATE | Ende-zu-Ende ueber `_poll_journal` mit Journal-Fixture |
| `tests/fixtures/position_fix/seven_journal_*.json` | CREATE | aufgezeichnete Journal-Eintraege mit den zwei echten Texten |

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `split_link_code` (#2154 D9) | function | einzige Befehlstext-Zerlegung; Koordinaten-Parser steht daneben, dupliziert sie nicht |
| `_verarbeite_befehl` / `/api/internal/premium-sms-learn` | function / endpoint | liefert die `user_id` (AC-9 #1676); ohne sie wird kein Fix gespeichert |
| `fix_2323_premium_sms_gate_generisch.md` | spec | Gate ist `to == SERVICE_NUMBER`, nicht der Link-Marker; Koordinaten sind optional |
| `trip_segments.position_at_time`, `points_with_passage_times`, `points_from_km`, `resolve_current_segment` | function | Wirkstelle und Vorbild |
| `track_resolution.resolve_stage_track_km` / `_match_track` | function | Trackpunkte der Heute-Etappe aus dem Nutzer-`gpx_dir` |
| `loader.get_data_dir(user_id)` | function | Ablageort je Nutzer |
| ADR-0101 | adr | Read-Modify-Write mit Merge fuer die Fix-Datei |
| ADR-0049, 0088, 0093, 0095 | adr | Premium-SMS-Kanal, Webhook-Kick, Alarm-Kanaele; ADR-0102 ist mit ihnen verwandt |
| Konsumenten: `trip_alert.py` (~2201-2240, :2705), `trip_report_scheduler.py` (:2364-2385), `trip_command_processor.py` (:3088-3094, :3184-3261), `radar_service.py` (:157), `alert/project.py` (:384) | module | wirken automatisch ueber die zentrale Positionsquelle |

## Entscheidungen

Der PO hat die Detailfragen nicht einzeln beantwortet; die folgenden Festlegungen trifft der Tech
Lead begruendet und legt sie hiermit zur Freigabe vor.

1. **Fix-Gueltigkeit: bis Ende der Heute-Etappe bzw. Tageswechsel (Etappen-Datum), danach Rueckfall
   auf die Planposition.** Begruendung: Die Bedeutung eines Fixes haengt an der Etappe, nicht an
   der Uhr. Eine feste Stundenzahl waere zu kurz fuer lange Etappen mit Rast und zu lang ueber
   Mitternacht; "Heute" ist ohnehin der Bezugsrahmen der Plausibilitaet.
2. **Reine Positions-SMS ohne Befehl: Fix wird aufgenommen, es wird KEINE bezahlte Antwort
   gesendet.** Begruendung: Der Nutzer hat nichts gefragt; eine Antwort kostet eine Premium-SMS
   und liefert keine Information. Die Wirkung zeigt sich im naechsten Briefing/Alarm.
3. **Neuester plausibler Fix gewinnt (Zeitstempel des Journal-Eintrags), auch wenn er
   rueckwaerts liegt.** Begruendung: Der Nutzer kann umkehren oder einen Abstecher machen; der
   juengste Messwert ist der beste Beleg. Ein aelterer Journal-Eintrag (Nachlieferung) ueberschreibt
   keinen juengeren.
4. **Mehrere Trips des Nutzers mit Heute-Etappe: alle pruefen.** Liegt der Punkt nur auf EINER
   Etappe innerhalb 100 m, gilt dieser Trip. Liegt er auf mehreren, wird verworfen und geloggt.
   Begruendung: Ein falsch zugeordneter Fix waere schlimmer als keiner; der Rueckfall ist die
   bekannte Planposition.
5. **Plausibilitaet: Abstand zur Route der Heute-Etappe <= 100 m (Grenze inklusive; Tests bei
   99 m und 101 m).** Gemessen wird der Abstand zur Strecke (Punkt-zu-Strecke-Projektion mit
   lokaler Equirectangular-Projektion), nicht haversine zu Trackpunkten -- Trackpunkte liegen
   weit auseinander, ein Punkt mitten auf einem langen Segment haette sonst Kilometer Abstand.
   Die Einschraenkung auf die Heute-Etappe entschaerft Selbstkreuzungen und Rueckwege.
6. **Wirkung zentral in der Positionsquelle** (`position_at_time` / `points_with_passage_times`,
   Vorbild `points_from_km`), damit alle vier Kanaele und alle Konsumenten gleich wirken. Keine
   Kanal-Sonderlogik, keine Aenderung in den fuenf Konsumenten selbst.
7. **Persistenz: eigene Datei je Nutzer unter `data/users/<user_id>/`, Read-Modify-Write mit Merge
   (ADR-0101), nicht im Trip-JSON** (Go roundtrippt das Trip-JSON und kennt das Feld nicht).
   `user_id` ausschliesslich aus der Go-Antwort, nie `"default"`.
8. **ADR-0102 gehoert zum Scope:** "Plausibler GPS-Fix uebersteuert Planposition" (verwandt mit
   0049, 0093, 0095, 0088, 0101). `docs/adr/README.md` bekommt den Index-Eintrag;
   `docs/reference/premium_sms_format.md` §4 nennt die Koordinaten; der Docstring in
   `trip_segments.points_with_passage_times` wird angepasst.
9. **Tests:** kein Mock-Theater. Parser gegen die zwei echten Texte als Fixture; Snapping;
   Ablauf; Mehrdeutigkeit; Zwei-Nutzer; Ende-zu-Ende ueber den echten Eingang (`_poll_journal` mit
   Journal-Fixture), nicht nur Einzelfunktionen.

## Implementation Details

**Parser (`extract_position`).** Eine Funktion neben `split_link_code`, die aus dem Gesamttext
das Paar `(lat, lon)` oder `None` liefert. Sie sucht die letzte Klammer `(<Zahl>, <Zahl>)` mit
Dezimalpunkt, prueft den Wertebereich und liefert sonst `None`. `split_link_code` bleibt in
seinem Ergebnis unveraendert (Befehlstext vor dem Link-Marker).

**Aufnahme.** In `_verarbeite_befehl` wird nach erfolgreicher Zuordnung (`user_id` aus der
Go-Antwort) `record_position_fix(user_id, lat, lon, zeitstempel)` aufgerufen. Fehlt die
Zuordnung, wird kein Fix gespeichert. Ist der Befehlstext leer, endet der Lauf nach der Aufnahme
ohne Antwort (Entscheidung 2); bei vorhandenem Befehl laeuft die Antwort wie heute.

**Plausibilitaet und Snapping (`position_fix.py`).** Fuer jeden Trip des Nutzers wird die
Heute-Etappe bestimmt (`resolve_current_segment`), ihr Track aus dem Nutzer-`gpx_dir` geladen und
der Punkt auf die Strecke projiziert. Ergebnis: Abstand in Metern und stage-kumulative Position in
km. Treffer nur bei Abstand <= 100 m und genau einem Trip (Entscheidung 4). Zu `lat`/`lon`,
Fortschritts-km, Trip-ID, Etappen-Datum und Zeitstempel wird eine Zeile je Nutzer geschrieben;
ein juengerer gespeicherter Fix wird von einem aelteren nicht ersetzt (Entscheidung 3).

**Wirkung.** `position_at_time` und `points_with_passage_times` pruefen zuerst, ob fuer diesen
Trip und dieses Etappen-Datum ein gueltiger Fix vorliegt (Entscheidung 1); dann ist der erste Punkt
der gesnappte Fix, die Folgepunkte laufen wie bei `points_from_km` ab Fortschritts-km entlang der
Reststrecke. Ohne Fix ist das Ergebnis bit-identisch zum Stand vor dieser Scheibe.

## Expected Behavior

- **Input:** Journal-Eintrag mit Befehlstext, Link und Koordinaten (oder nur Koordinaten); danach
  ein beliebiger Abruf der Positionsquelle (Briefing, Alarm, Radar, Befehl).
- **Output:** Liegt der Punkt innerhalb 100 m der Heute-Etappe, rechnen alle Ausgaben ab dem
  gesnappten Punkt; sonst unveraendert ab Planposition.
- **Side effects:** Schreiben/Aktualisieren von `data/users/<user_id>/position_fix.json` (Merge);
  Log-Eintrag bei verworfenem Fix (zu weit entfernt, mehrdeutig, ungueltig).

## Acceptance Criteria

- **AC-1:** Given die zwei echten Nachrichtentexte vom 26.10.2026 (`Heute inreachlink.com/gS5ySf-2sYCWmJQksXnjeHw  (46.6370, 12.7678)` und `so morgen  inreachlink.com/gGF87yQgGC0h_fnW_2_ngUA  (46.6124, 12.8676)`) / When der Parser sie zerlegt / Then liefert er die Koordinaten (46.6370, 12.7678) bzw. (46.6124, 12.8676) und der Befehlstext bleibt "Heute" bzw. "so morgen" -- identisch zum Ergebnis ohne Koordinaten.
  - Test: `test_position_fix_parser.py` mit beiden Texten als Fixture; Befehlstext-Gleichheit gegen `split_link_code` desselben Textes ohne Klammer.

- **AC-2:** Given Texte ohne Klammer, mit variablen Leerzeichen, mit Unsinn in der Klammer oder mit ungueltigem Bereich (lat 91, lon 181) / When der Parser laeuft / Then entsteht bei Leerzeichenvarianten dasselbe Paar, bei allen anderen kein Fix, und der Befehl wird wie bisher beantwortet.
  - Test: Parametrisierter Parser-Test; ein Eingangstest zeigt, dass ein Befehl mit Unsinn-Klammer weiterhin die normale Antwort erhaelt.

- **AC-3:** Given eine Heute-Etappe mit langem Streckenabschnitt zwischen zwei Trackpunkten / When ein Punkt 99 m neben dem Abschnitt gemeldet wird und ein zweiter Punkt 101 m daneben / Then wird der 99-m-Punkt als Fortschritt uebernommen und der 101-m-Punkt verworfen (und geloggt); der Abstand wird zur Strecke gemessen, nicht zum naechsten Trackpunkt.
  - Test: `test_position_fix_snapping.py` mit synthetischem Track und Punkten bei 99 m / 101 m; ein dritter Punkt mitten auf dem Abschnitt, weit von beiden Trackpunkten, wird akzeptiert.

- **AC-4:** Given ein gueltiger Fix fuer die Heute-Etappe / When Briefing, Alarm-Messpunkt, Radar und Befehl die Position abrufen / Then liegt der erste Messpunkt am gesnappten Fix und die Folgepunkte laufen von dort entlang der Reststrecke, nicht ab der Planposition.
  - Test: Echter Trip, gestellte Uhr, Planposition und Fix liegen deutlich auseinander; geprueft werden die Koordinaten, die `position_at_time` und `points_with_passage_times` liefern, sowie die Argumente des Nowcast-Abrufs im echten `check_radar_alerts()`.

- **AC-5:** Given ein Fix vom Etappentag / When die Etappe endet oder der Tag wechselt / Then faellt die Positionsquelle auf die Planposition zurueck, ohne dass der alte Fix die naechste Etappe beeinflusst.
  - Test: Uhr hinter Etappenende bzw. am Folgetag gestellt; Ergebnis bit-identisch zum Lauf ohne Fix.

- **AC-6:** Given ein gespeicherter Fix und danach ein neuerer plausibler Fix, der weiter hinten auf der Strecke liegt / When die Positionsquelle abgefragt wird / Then gilt der neuere Fix (auch rueckwaerts); ein Journal-Eintrag mit aelterem Zeitstempel ueberschreibt einen juengeren nicht.
  - Test: Zwei Fixes in beiden Reihenfolgen eingespielt; Endzustand der Datei und Positionsquelle geprueft.

- **AC-7:** Given zwei Trips desselben Nutzers mit Heute-Etappe / When ein Punkt gemeldet wird, der nur auf der Route eines Trips innerhalb 100 m liegt / Then wirkt der Fix nur auf diesen Trip; liegt er innerhalb 100 m auf beiden Routen, wird er verworfen, geloggt und beide Trips bleiben auf der Planposition.
  - Test: Zwei Trips mit eindeutiger und mit ueberlappender Strecke; Positionsquelle beider Trips nach dem Eingang.

- **AC-8:** Given ein gueltiger Fix / When Briefing und Alarm in E-Mail, Telegram, SMS und Premium-SMS erzeugt werden / Then gehen alle vier Kanaele von derselben gesnappten Position aus, ohne kanalspezifische Positionslogik.
  - Test: Positionsquelle einmal abgefragt; die vier Renderer-Pfade nutzen sie unveraendert. Mutationsgegenprobe: wird der Fix-Zweig in `position_at_time` entfernt, wird der Test aus AC-4 rot.

- **AC-9:** Given zwei verschiedene Nutzer A und B, jeder mit eigener Heute-Etappe / When eine Nachricht mit Koordinaten Nutzer A zugeordnet wird / Then aendert sich die Positionsquelle von Nutzer B nicht, die Fix-Datei liegt unter dem Verzeichnis von A, und bei fehlender Zuordnung durch die Go-Antwort wird kein Fix gespeichert (nie unter `default`).
  - Test: Zwei-Nutzer-Test mit eigenen Datenverzeichnissen; Dateien beider Nutzer und deren Positionsquelle geprueft; Fall "Go kennt die Nummer nicht" schreibt keine Datei.

- **AC-10:** Given eine Positions-SMS ohne Befehlstext (nur Link und Koordinaten) / When sie ueber `_poll_journal` eingeht / Then wird der Fix aufgenommen und es wird keine Premium-SMS-Antwort gesendet.
  - Test: Ende-zu-Ende mit Journal-Fixture ueber `_poll_journal`; Versandkanal registriert null Sendungen, Fix-Datei vorhanden.

- **AC-11:** Given ein echter Journal-Eintrag mit "Heute" plus Koordinaten auf der Route / When `_poll_journal` ihn verarbeitet / Then wird die Heute-Antwort wie bisher gesendet und zugleich der Fix gespeichert; ein Eintrag mit Koordinaten ausserhalb der 100 m wird beantwortet, aber nicht gespeichert.
  - Test: Ende-zu-Ende ueber `_poll_journal` mit aufgezeichneter Journal-Fixture (Formen wie `tests/fixtures/befehl_antwortzeit/seven_journal_*.json`), kein Mock der Zielfunktionen.

- **AC-12:** Given die Dokumentation / When die Scheibe geliefert ist / Then existiert ADR-0102 mit Index-Eintrag, `premium_sms_format.md` §4 nennt das Koordinatenformat und die Fix-Wirkung, und der Docstring von `points_with_passage_times` behauptet nicht mehr, es gebe kein GPS.
  - Test: `tests/test_adr_index_drift.py` gruen; Doku-Abnahme durch den Adversary (`# doc-compliance-test`-Ausnahme, kein Verhaltenstest).

## Known Limitations

- Die 100-m-Grenze ist eine feste Konstante; GPS-Ungenauigkeit im Gelaende wird nicht modelliert.
- Wer die Route verlaesst (Abstecher > 100 m), bleibt bis zum naechsten plausiblen Fix auf der letzten Position bzw. der Planposition.
- Etappen ohne Nutzer-GPX (nur Wegpunkte) haben keinen Track zum Snappen; dort wird kein Fix uebernommen.

## Nicht Ziel

- Keine Kanal-Sonderlogik, keine neue Anzeige "Position vom Fix" in den Ausgaben.
- Keine Handlungsempfehlung aus dem Fix, nur geaenderte Datengrundlage.
- Keine Aenderung am Go-Code und am Trip-JSON-Schema.

## Offene Punkte

- Das Zeitstempel-Feld des Journal-Eintrags ist in der Umsetzung gegen die aufgezeichneten Journal-Fixtures zu verifizieren; fehlt es, gilt der Eingangszeitpunkt der Verarbeitung.
- Verhalten bei Etappen ohne Track (nur Wegpunkte) ist als Known Limitation geregelt, nicht erweitert.
- Der Zeitpunkt der Ablaufpruefung (Lesezeitpunkt in der Positionsquelle, nicht Aufraeum-Job) ist als Lesezeit-Pruefung vorgesehen; ein Aufraeum-Job ist nicht Teil des Scopes.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** ADR-0102 (neu, Teil dieses Scopes)
- **Rationale:** Der Grundsatz "Planposition ist die legitime Positionsquelle" wird fuer plausible GPS-Fixes bewusst abgeloest. Eine dokumentierte Entscheidung wird nie still rueckgaengig gemacht; Verwandtschaft mit ADR-0049, 0088, 0093, 0095 und 0101.

## Changelog

- 2026-10-26: Initial spec created (Issue #2327, aus `docs/context/feat-2327-gps-etappenfortschritt.md`; Koordinatenformat durch zwei echte Nachrichten belegt; Detailentscheidungen als Tech-Lead-Festlegung).
