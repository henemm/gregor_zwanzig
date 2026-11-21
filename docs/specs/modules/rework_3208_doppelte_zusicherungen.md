---
entity_id: rework_3208_doppelte_zusicherungen
type: refactor
created: 2026-11-21
updated: 2026-11-21
status: draft
version: "1.0"
issue: 3208
epic: 1196
workflow: rework-3208-doppelte-tests
tags: [tests, aufraeumen, doppelte-zusicherungen]
---

# Doppelte Zusicherungen in Issue-Testdateien zusammenlegen, erste Scheibe (#3208)

## Approval

- [ ] Approved

## Purpose

Dieselbe Regel soll an genau einer Stelle geprueft werden. Die erste Scheibe legt die belegt doppelten Zusicherungen der Gehzeit-Berechnung (Naismith/DAV) und des SMS-/Premium-SMS-Resolvers in die fachlich benannte Testdatei zusammen, ohne dass eine Zusicherung verloren geht. Ehrlicher Befund vorab: Die Ausbeute ist klein. Unter 368 Issue-Testdateien gibt es nur 45 woertlich gleiche Assert-Texte; in den Gruppen Kanal-Layout und Kanal-Resolver liegt fast keine echte Dopplung vor. #3208 liefert deshalb vor allem die Methode (Entfernen nur bei Identitaet oder echter Teilmenge, Beleg per Mutation) und eine erste, abgeschlossene Scheibe, keinen Grossumbau.

## Source

- **File:** `docs/context/rework-3208-doppelte-tests.md` (Abschnitt "Analysis": Befund je Gruppe, Technical Approach)
- **Identifier:** Testdateien unter `tests/` (siehe Scope); Vorbild fuer Aufbau und Regel: `docs/specs/modules/tote_tests_inventur.md` (#3207)

Schicht: reine Testsuite-Sanierung. Kein Produktcode in `src/`, `api/`, `internal/` oder `frontend/src/` wird veraendert; keine Nutzerdaten bewegt; kein Briefing-/Alarm-Inhalt veraendert (alle vier Kanaele bleiben durch ihre bleibenden Tests bewacht). Kein Trip/Vergleich-Pendant betroffen.

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| #3207 / `tote_tests_inventur` | spec | Vorgaenger; Regel "Tests im selben Umbau mitentfernen", Collect-Baseline, Wirkweise der Wächter |
| `core.naismith` (`compute_stage_arrivals`, `speeds_for_tempo`, `dav_hours`) | module | geprueftes Verhalten der Gehzeit-Gruppe (Mutationsziel G1a-G1d) |
| `services.trip_segments.stage_measured_distances` | module | kanonische Regel "Etappe vermessen" (#2082) |
| `services.channel_list_resolver.resolve_channel_lists`, `output.renderers.sms_trip` | module | geprueftes Verhalten der Resolver-Gruppe (Mutationsziel G3) |
| `tests/tdd/test_einstellung_gleich_mail_fallliste.py` | test | Waechter ueber Testverweise der beiden Falllisten-JSONs |
| `tests/fixtures/einstellung_gleich_mail/fallliste_sms.json`, `fallliste_premium_sms.json` | fixture | verweisen heute auf den zu entfernenden 3099-Test |
| `tests/test_stillgelegte_testdateien.py`, Doku-Waechter #316 | test | greifen bei Loeschungen und Doku-Verweisen |
| `tests/tdd/test_3100_premium_sms_fallliste.py` | test | bleibender, breiterer Ersatz fuer 3099 AC-6; importiert `_orte_sms` aus 3099 (bleibt) |
| ADR-0094, ADR-0095 | decision | Test-Schichten; Kanal-Paritaet (kein Kanal verliert Abdeckung) |

## Scope

### Affected Files

| File | Change Type | Description |
|------|-------------|-------------|
| `tests/tdd/test_gehzeit_etappenregel.py` | MODIFY | nimmt aus der Wegstrecken-Datei zwei Faelle auf (Luecke am Etappenende, Go-Paritaetswert 10:30); #2042-Bezug als Kommentar |
| `tests/tdd/test_gehzeit_folgt_wegstrecke.py` | DELETE | fuenf Faelle: drei aufgegangen (identisch/Teilmenge), zwei uebernommen |
| `tests/tdd/test_issue_802_fahrrad_segment_zeit.py` | MODIFY | `test_ac4_wanderer_default_naismith_sum` entfernen; Parametrisierung `test_ac3_...` ohne `"A"`; ac1 liest Wertekontrakt A |
| `tests/tdd/test_3099_sms_resolver.py` | MODIFY | `test_ac6_premium_gleich_sms_trotz_abweichender_premium_ebene` entfernen; Festwert-Test fuer die SMS-Folge Niederschlag/Boe/Bewoelkung ergaenzen |
| `tests/fixtures/einstellung_gleich_mail/fallliste_sms.json` | MODIFY | Fall `sms-premium-gleich-sms-text`: Testverweis auf Ersatztest |
| `tests/fixtures/einstellung_gleich_mail/fallliste_premium_sms.json` | MODIFY | Fall `psms-trip-versand-abweichend`: Testverweis auf Ersatztest |
| `docs/context/rework-3208-doppelte-tests.md` | MODIFY | Mutationsprotokoll vorher/nachher, Begruendung G2 |

Nicht geaendert (geprueft, bleiben unveraendert): `tests/test_3196_trip_tempo_dav.py`, `tests/test_3197_tempo_je_etappe.py` (siehe Einzelentscheidung 2).

### Estimated Changes

- Files: 7 (1 DELETE, 6 MODIFY), nur Tests, Fixtures, Doku
- LoC: ca. +45 / -190
- Effort: low
- Collect-Only: Testanzahl sinkt netto um 5 (3 aus der Wegstrecken-Datei, 2 aus 802); 3099 bleibt netto gleich (ein Fall raus, ein Festwert-Fall rein)

## Implementation Details

### Kriterium

Entfernt wird nur, was identisch ist (gleiche Funktion, gleiche Eingaben, gleiche Erwartung) oder eine echte Teilmenge einer bleibenden Zusicherung. "Aehnlich" (andere Schicht, andere Werte, andere Luecke) bleibt. Kein Parametrisieren aus Optik. Jede entfernte Zusicherung hat in der Tabelle unten einen benannten Ziel-Test.

### Einzelentscheidungen (nach Lesen der Testdateien)

**1. Gehzeit, `test_gehzeit_folgt_wegstrecke.py` geht in `test_gehzeit_etappenregel.py` auf.**

| Entfallener Fall | Entscheidung | Ziel-Test (bleibt/neu) | Begruendung |
|---|---|---|---|
| ac1 `vermessene_etappe_rechnet_mit_der_wegstrecke` | identisch, entfaellt | `etappenregel::test_ac4_vermessene_plausible_etappe_rechnet_gemessen` | gleiche Stage (0 und 2x Luftlinie), gleiche beiden Asserts (gemessen, groesser als Luftlinie plus 1 min) |
| ac2 `unvermessene_etappe_bleibt_unveraendert` | identisch, entfaellt | `etappenregel::test_ac7_etappe_ohne_messwerte_bleibt_unveraendert` | beide Wegpunkte ohne Messwert, Erwartung Luftlinie, identische Rechnung |
| ac4 `negative_differenz_faellt_auf_luftlinie_zurueck` (km 12 -> 4) | Teilmenge, entfaellt | `etappenregel::test_ac2_nicht_strikt_steigend_faellt_zurueck[kleiner]` (km 5 -> 4) | gleiche Aequivalenzklasse "nicht strikt steigend"; die Zusatz-Zusicherung "Gehzeit > 0" ist durch die Erwartung `approx(Luftlinienminuten, abs=1)` mit rund 34 Minuten (Luftlinie ca. 2,3 km bei 4 km/h) mit abgedeckt, geht also nicht verloren |
| ac3 `rueckfall_gilt_je_etappe_nicht_je_abschnitt` (Luecke am Etappenende, geprueft wird der vermessene Abschnitt davor) | NICHT aufgehen lassen, uebernommen | neu `etappenregel::test_ac3b_luecke_am_etappenende_entwertet_die_etappe` | etappenregel ac3 hat die Luecke in der Mitte und prueft den letzten Wegpunkt; eine Mutation "Pruefung ignoriert den letzten Wegpunkt" wuerde dort rot, aber nicht zwingend die Luecke am Ende erfassen. Andere Lage der Luecke ist keine Teilmenge |
| ac5 `paritaet_erwartungswerte_fuer_die_go_seite` (08:00 und 10:30) | einzigartig, uebernommen | neu `etappenregel::test_ac8_paritaet_erwartungswerte_fuer_die_go_seite` (Name an den dort freien Zaehler anpassen) | einziger Python-Festwert, den der Go-Test `internal/model/naismith_gemessene_strecke_test.go` spiegelt; Docstring-Hinweis auf die Go-Datei bleibt |

Der Modul-Kopf von `test_gehzeit_etappenregel.py` erhaelt einen Kommentar "#2042 (Gehzeit folgt der gemessenen Wegstrecke, Spec fix_2042_gehzeit_wegstrecke): ehemals `test_gehzeit_folgt_wegstrecke.py`, hier aufgegangen (#3208)"; ac4 und ac7 behalten ihren Hinweis "Regressionswaechter fuer #2042 AC-1/AC-2".

**2. `test_3196_trip_tempo_dav.py` vs. `test_3197_tempo_je_etappe.py`: keine Entfernung (Abweichung von der Analyse).** Beim Lesen zeigt sich: `test_save_trip_schreibt_tempo_und_rechnet_dav` (3196) traegt eine Trip-`activity="fahrrad_20"` mit gespeichertem Tempo "fuss 4" und belegt, dass das Tempo Vorrang hat und `activity` auf der Platte stehen bleibt (ohne Vorrang kaeme 09:06/09:48 wie im Nachbartest). `test_bestand_ohne_ueberschreibung_unveraendert` (3197) hat keine `activity`, prueft zusaetzlich `stage_speeds == tempo_speeds` und S2. Nur der Zahlenwert 08:00/10:30/12:12 ist gleich, die Zusicherungen sind weder identisch noch Teilmenge. Beide Dateien bleiben unveraendert; die Pruefung steht im Context-Dokument als "geprueft, keine echte Dopplung". Der Wert 12:12 ist aus derselben DAV-Rechnung bewusst an zwei Schichten gebunden (Loader vs. `stage_speeds`).

**3. `test_issue_802_fahrrad_segment_zeit.py`.**
- ac3 `[W]` und `test_ac4_wanderer_default_naismith_sum` rufen dieselbe Funktion mit derselben Stage (`_CONTRACT["W"]`) und demselben Assert auf: identisch. `test_ac4_...` entfaellt, der Docstring von `test_ac3_...` nennt "deckt auch AC-4 (Wanderer-Default unveraendert)".
- ac3 `[A]` ist echte Teilmenge von `test_ac1_save_trip_populates_arrival_calculated` (gleiche Hoehen `[500,1100,1100,500]`, gleiche Tempoart `fahrrad_20`, gleiche Erwartung `["08:00","09:00","09:00","09:36"]`; `save_trip` ruft dieselbe Funktion, ac1 prueft zusaetzlich Persistenz und "alle befuellt"). `"A"` wird aus der Parametrisierung genommen; damit der Wertekontrakt (den Go spiegelt) nicht doppelt gepflegt wird, liest `test_ac1_...` Hoehen und Erwartung aus `_CONTRACT["A"]` statt aus Literalen.
- ac3 `[B]`, `[C]` (Rundung, Mitternachts-Wrap) bleiben, ebenso `test_issue_296_be_arrival.py` (andere Werte, anderer Pfad).

**4. `test_3099_sms_resolver.py` / `test_3100_premium_sms_fallliste.py`.**
- `test_ac6_premium_gleich_sms_trotz_abweichender_premium_ebene` ist Teilmenge von `test_3100::test_ac1_trip_eingang_premium_gleich_sms` (3100: drei Premium-Ebenen "abweichend/leer/nie" mal zwei Befehle ueber den echten Garmin-Eingang, Premium-Text gleich SMS-Text, Grenze 153; ac6: eine abweichende Ebene, zwei Nutzer ueber Versand). Mutationsfeinheit bleibt: "Premium liest die Premium-Liste statt der SMS-Liste" faengt 3100 ac1 (siehe G3a).
- Den Festwert `"E1 R2.0@4 G45@4 CT:SCT@4"` (SMS-Liste Niederschlag, Boe, Bewoelkung in dieser Folge) traegt in 3099 sonst kein Test (`test_ac2` hat eine andere Liste, `test_ac9` die Folge Boe, Niederschlag, Bewoelkung). Er wandert in einen neuen Test `test_ac2_sms_folge_niederschlag_boe_bewoelkung` in 3099 (Abschnitt AC-2, Aufbau mit den vorhandenen Helfern `_sms(_trip(_trip_dict(_liste([...]))))`, Bericht "evening" als Standard), Kommentar "Festwert aus ehemals AC-6 (#3099), #3208".
- Falllisten: Fall `sms-premium-gleich-sms-text` (`fallliste_sms.json`) und Fall `psms-trip-versand-abweichend` (`fallliste_premium_sms.json`) zeigen kuenftig auf `tests/tdd/test_3100_premium_sms_fallliste.py::test_ac1_trip_eingang_premium_gleich_sms`. Feld `ac` auf `AC-1`, `befund` nennt "ersetzt #3099 AC-6 (#3208)". IDs und `merkmale` bleiben unveraendert, damit Hinweis-Liste (`VERSTREUT` in 3100) und Achsen-Pruefungen weiter greifen; falls der Waechter bei `weg: versand` keine andere Belegung findet, wird in `psms-trip-versand-abweichend` `weg` auf `eingang+versand` gesetzt (der Ersatztest geht ueber den Eingang und den echten Versandweg).

### Mutationsnachweis je Gruppe (vorher UND nachher)

Jede Mutation per String-Ersetzung im Produktcode mit externer Sicherungskopie (Scratchpad), danach Wiederherstellung aus der Sicherung, nie `git checkout/stash/reset`. Es laufen nur benannte Testdateien. Protokoll (Mutation, rot vorher, rot nachher, wiederhergestellt gruen) im Context-Dokument.

| Mutation | Ziel | Erwartung nachher |
|---|---|---|
| G1a | `compute_stage_arrivals`: gemessene Strecke ignorieren (immer Luftlinie) | rot in `etappenregel::test_ac4` und `test_ac8_paritaet...` |
| G1b | Rueckfallregel kippen: fehlende/fallende Strecke wird nicht auf Luftlinie zurueckgesetzt (jeweils Variante: Wert fehlt am Ende, Wert faellt) | rot in `etappenregel::test_ac2`, `test_ac3`, `test_ac3b`, `test_ac7` |
| G1c | Grundtempo (`speeds_for_tempo`) bzw. Steigungsgewicht (`dav_hours`) aendern | rot in 3196, 3197 und 802 (`ac3[W]`, `ac1`) |
| G1d | Aufstiegsrate aendern | rot in `etappenregel::test_ac8_paritaet...` (10:30) |
| G3a | Premium-Zweig liest die Premium-Liste statt der SMS-Liste | rot in `test_3100::test_ac1_...` |
| G3b | SMS-Kuerzel/Token der Niederschlagsmetrik aendern | rot im neuen Festwert-Test in 3099 |

"Vorher": dieselbe Mutation macht mindestens einen der heutigen Tests (inkl. der zu entfernenden) rot. "Nachher": dieselbe Mutation macht nach dem Umbau mindestens einen bleibenden Test rot, und zwar den in der Spalte genannten. Ist eine Mutation nachher gruen, ist das ein Befund, der Umbau wird nicht ausgeliefert.

### Nicht im Umfang / Abgespalten

- **G2 Kanal-Layout** (`test_issue_429_channel_layouts.py`, `test_issue_434_per_report_layouts.py`, `test_reports_pro_typ.py`, `test_3057_channel_list_resolver.py`): geprueft, keine Dopplung. 429, 434 und `test_reports_pro_typ` pruefen aehnliche Muster auf verschiedenen Ebenen (Kanal vs. Bericht) mit anderen Fixtures; `test_3057` ac1 ist ein Orakel ueber alle Kombinationen. Kein Umbau, nur im Context-Dokument begruendet. Veraltete "RED, noch nicht existierende API"-Docstrings in 429/434 sind ein Nebenbefund und nicht Gegenstand.
- **G3 Helfer-Konsolidierung und Parametrisierung 3098/3099:** nicht Gegenstand (`_mc`, `_orte_liste`, `_trip_dict`, `_AbweichendesModell` sind nur aehnlich; die Soll-Strings sind je Kanal verschieden, also Refactor und nicht Dopplung). Die Dateien 3096, 3098, 3099, 3100, 3196, 3197 und 802 werden nicht umbenannt (Waechter, Spec- und Frontend-Verweise, z. B. `naismith_stage_tempo_3197.test.ts`).
- **Bereits angelegte Folge-Issues im Epic #1196:** #3263 (Fix-Runden 2795), #3264 (Nowcast/Radar), #3265 (Provider-Fallback), #3266 (Fixloop-Dateien), #3267 (Sprachkatalog).
- Unberuehrt bleiben `tests/unit/test_segment_builder.py` (einzige Abdeckung von `compute_hiking_time`), `test_naismith_hhmm_wrap_parity.py`, `test_naismith_midnight_wrap_segments.py`, `test_issue_296_be_arrival.py`.

## Expected Behavior

- **Input:** Testbestand mit den fuenf belegten Dopplungen der ersten Scheibe.
- **Output:** gleiche geprueften Zusicherungen, an je einer Stelle; Wegstrecken-Datei entfaellt; Falllisten-Verweise zeigen auf den Ersatztest; Kern-Schicht weiter 100 % gruen.
- **Side effects:** keine Auswirkung auf Produktverhalten oder Deploy-Inhalt; Testanzahl sinkt netto um 5.

## Test Plan

Es entsteht kein neuer Produktionscode. Es gibt keinen klassischen RED-Test: der RED-Schritt ist der Mutationsnachweis "vorher" (Schutz ist vor dem Umbau nachweisbar), der Nachweis "nachher" der GREEN-Beleg. Keine Mock-Tests, keine Dateiinhalt-Checks als Verhaltensnachweis. Ein zusaetzlicher Doku-/Strukturtest ist nicht noetig, weil der bestehende Falllisten-Waechter die Testverweise maschinell prueft.

### Automated Tests (TDD RED)

- [ ] Test 1: GIVEN der Stand vor dem Umbau WHEN jede Mutation G1a-G1d, G3a, G3b angewendet wird THEN ist mindestens ein Test der betroffenen Dateien rot (Ausgangsprotokoll im Context-Dokument).
- [ ] Test 2: GIVEN der Stand nach dem Umbau WHEN dieselben Mutationen angewendet werden THEN ist der in der Mutationstabelle genannte bleibende Test rot und nach Wiederherstellung wieder gruen.
- [ ] Test 3: GIVEN die geaenderten Falllisten WHEN `tests/tdd/test_einstellung_gleich_mail_fallliste.py`, `test_3099_sms_resolver.py` und `test_3100_premium_sms_fallliste.py` laufen THEN sind alle gruen (Testverweise gefunden, Achsen belegt).
- [ ] Test 4: GIVEN die berührten Testdateien WHEN `pytest --collect-only -q` vorher und nachher laeuft THEN fehlen genau die geplanten Faelle und es gibt keine Collect-Fehler.
- [ ] Test 5: GIVEN alle berührten Dateien WHEN sie namentlich laufen THEN sind sie gruen (`uv run pytest` nie ohne benannte Dateien, #1477).

## Definition of Done

- [ ] Jede entfernte Zusicherung mit Ziel-Test und Begründung (identisch oder echte Teilmenge) im Context-Dokument (AC-1)
- [ ] Mutationsprotokoll G1a–G1d, G3a, G3b vorher und nachher rot, nach Wiederherstellung grün (AC-2)
- [ ] Issue-Bezüge als Kommentar an den Ziel-Tests (AC-3)
- [ ] Keine verwaisten Verweise, Falllisten-Wächter und Doku-Wächter grün, Falllisten zeigen auf den Ersatztest (AC-4, AC-8)
- [ ] Collect-Only netto genau minus 5, keine Collect-Fehler (AC-5)
- [ ] Berührte Dateien namentlich grün, alle 6 CI-Checks grün, Kern-Schicht 100 % grün, Adversary-Verdict VERIFIED (AC-6)
- [ ] Diff nur unter tests/ und docs/, Produktionscode unverändert (AC-7)

## Acceptance Criteria

- **AC-1:** Given ein Testfall wird im Zuge der ersten Scheibe entfernt / When der Umbau fertig ist / Then ist jede entfernte Zusicherung identisch oder echte Teilmenge einer bleibenden und in der Spec je Fall mit Ziel-Test belegt (Wegstrecke ac1 -> etappenregel ac4, ac2 -> ac7, ac4 -> ac2[kleiner]; ac3 und ac5 als neue Faelle uebernommen; 802 ac4 -> ac3[W], 802 ac3[A] -> ac1; 3099 ac6 -> 3100 ac1 plus Festwert-Test), und ein nur aehnlicher Fall (3196 gegen 3197) bleibt unveraendert.
  - Test: Pruefung der Fall-Tabelle gegen die Dateien; jeder Ziel-Test existiert und laeuft gruen; fuer die uebernommenen Faelle `test_ac3b_...`, `test_ac8_paritaet...` und den Festwert-Test liefert `pytest --collect-only` je einen Treffer.

- **AC-2:** Given die sechs Mutationen G1a-G1d, G3a, G3b / When sie vor dem Umbau und nach dem Umbau je per String-Ersetzung mit externer Sicherungskopie angewendet werden (nie `git checkout/stash/reset`) / Then wird jede Mutation vorher und nachher von mindestens einem Test der benannten Dateien rot gefangen, und nach Wiederherstellung aus der Sicherung sind diese Tests wieder gruen.
  - Test: Mutationsprotokoll (Mutation, vorher rot, nachher rot, wiederhergestellt gruen) im Context-Dokument; bei einer nachher gruenen Mutation wird nicht ausgeliefert.

- **AC-3:** Given Testfaelle tragen Issue-Bezuege (#2042, #2082, #3196, #3099 AC-6, #802) / When die Faelle zusammengelegt werden / Then bleibt der Issue-Bezug als Kommentar oder Docstring am bleibenden bzw. uebernommenen Test erhalten, insbesondere #2042 im Kopf von `test_gehzeit_etappenregel.py` und #3099 AC-6 am Festwert-Test.
  - Test: Der Bezug steht beim Ziel-Test (Sichtpruefung im Review); kein Verhaltensnachweis ueber Dateiinhalt, die Zusicherungen selbst laufen als Tests.

- **AC-4:** Given die Datei `tests/tdd/test_gehzeit_folgt_wegstrecke.py` und die entfernten Testnamen (`test_ac4_wanderer_default_naismith_sum`, `test_ac6_premium_gleich_sms_trotz_abweichender_premium_ebene`) sind geloescht / When ueber `tests/`, `docs/`, `internal/`, `frontend/` und `.claude/` (inkl. versteckter Ordner) nach den Namen gesucht wird / Then gibt es ausserhalb des Context-Dokuments keine verwaisten Verweise, und der Falllisten-Waechter `test_einstellung_gleich_mail_fallliste.py` sowie `test_stillgelegte_testdateien.py` und der Doku-Waechter #316 sind gruen.
  - Test: grep mit 0 Treffern ausser dem Context-Dokument; Waechter-Testdateien namentlich gruen.

- **AC-5:** Given die Collect-Liste der berührten Testdateien vor dem Umbau / When nach dem Umbau `pytest --collect-only -q` auf dieselben Dateien laeuft / Then ist die Testanzahl netto um genau 5 gesunken (3 aus der Wegstrecken-Datei, 2 aus 802, 3099 netto gleich), es verschwinden nur die geplanten Faelle und es gibt keine Collect-Fehler.
  - Test: Vorher-Nachher-Vergleich der Testlisten mit Differenz exakt nach Plan.

- **AC-6:** Given alle berührten Testdateien (`test_gehzeit_etappenregel.py`, `test_issue_802_fahrrad_segment_zeit.py`, `test_3099_sms_resolver.py`, `test_3100_premium_sms_fallliste.py`, `test_3196_trip_tempo_dav.py`, `test_3197_tempo_je_etappe.py`, `test_einstellung_gleich_mail_fallliste.py`) / When sie namentlich ausgefuehrt werden (nie `uv run pytest` ohne Dateien) / Then sind alle gruen, und die Kern-Schicht ist zu 100 % gruen, alle 6 CI-Checks des PR sind gruen.
  - Test: lokaler Lauf der benannten Dateien; CI-Lauf des PR mit allen 6 Checks gruen.

- **AC-7:** Given der Umbau betrifft nur Testsammlung und Dokumentation / When der Diff gegen `origin/main` geprueft wird / Then liegen alle geaenderten Dateien unter `tests/` oder `docs/`, und Produktionscode (`src/`, `api/`, `internal/`, `frontend/src/`, `cmd/`) ist unveraendert.
  - Test: `git diff --name-only origin/main` enthaelt keinen Pfad ausserhalb von `tests/` und `docs/`.

- **AC-8:** Given die Falllisten `fallliste_sms.json` und `fallliste_premium_sms.json` verwiesen auf den entfernten 3099-Test / When die zwei Eintraege `sms-premium-gleich-sms-text` und `psms-trip-versand-abweichend` auf `test_3100_premium_sms_fallliste.py::test_ac1_trip_eingang_premium_gleich_sms` umgestellt sind / Then findet der Waechter beide Testverweise, die IDs und Achsen-Belegung bleiben vollstaendig, und die Hinweis-Liste in 3100 ist weiter gueltig.
  - Test: `test_einstellung_gleich_mail_fallliste.py`, `test_3099_sms_resolver.py::test_ac11_*` und `test_3100_premium_sms_fallliste.py::test_ac5_*`/`test_ac6_*` laufen gruen.

## Known Limitations

- Die Ausbeute ist bewusst klein; die uebrigen Gruppen (Fix-Runden, Nowcast/Radar, Provider-Fallback, Fixloop, Sprachkatalog) sind als eigene Issues #3263 bis #3267 im Epic #1196 abgespalten.
- Die Methode erfasst nur Dopplung per Funktion, Eingabe und Erwartung; rein semantische Aehnlichkeit mit anderen Fixtures wird nicht zusammengelegt.
- Mutationen werden von Hand gesetzt (String-Ersetzung); ein automatischer Mutationslauf ist nicht Teil dieses Umbaus.
- Teilmutation G1b-monotonie (nur Monotonie-Pruefung aus) war schon vor dem Umbau gruen, weil die Plausibilitaetspruefung sie in allen Testfaellen maskiert; G1b als Ganzes (Variante "Rueckfall aus") ist vorher und nachher rot, der Umbau verliert also keinen Schutz. Die bestehende Luecke (identische Koordinaten, leicht fallender km-Wert) schliesst Folge-Issue #3271 im Epic #1196.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Aufraeumen nach bestehender Test-Politik (ADR-0094) und der in #3207 verankerten Regel; keine neue Architekturentscheidung, kein neues Gate, keine Aenderung an wirksamer Gate-Konfiguration.

## Changelog

- 2026-11-21: Initial spec created
