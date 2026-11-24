---
entity_id: rework_3317_wartezeiten_tempo_s1
type: refactor
created: 2026-11-24
updated: 2026-11-24
status: draft
version: "1.0"
workflow: rework-3317-wartezeiten
tags: [testsuite, performance, wartezeiten, epic-1196]
---

# Testsuite: echte Wartezeiten und Sammel-Subprozesse beschleunigen, Scheibe A

## Approval

- [ ] Approved

## Purpose

Vier Testdateien warten real (Sammel-Läufe der ganzen Suite, ein 30-s-Hänger, ein 10-s-Timeout, nacheinander gestartete Prozesse je Uhrzeit) und gehören damit zu den langsamsten der Suite. Diese Scheibe verkürzt die Wartezeit, ohne eine Zusicherung zu schwächen. Issue #3317 (Scheibe 3 zu #3279, Teil von Epic #1196); dies ist Scheibe A, die Mail-Validatoren (Scheibe B) laufen als eigenes Folge-Issue.

## Source

- **File:** `tests/tdd/test_pytest_collection_and_timeout_safety.py`, `tests/refactor/test_epic_129a_3_ui_removed.py`, `tests/tdd/test_dwd_thunder_parallel_fetch.py`, `tests/tdd/test_radar_nowcast_segment_wanduhr_unabhaengig.py`, `tests/helpers/wanduhr_matrix.py`
- **Identifier:** `default_collect`/`email_collect`/`staging_collect`/`live_collect` (Fixtures), `test_friendly_format_footgun_not_collected_by_default`, `test_timeout_ini_default_kills_hanging_test`, `test_ac7_collection_clean`, `test_ac3_haenger_mit_unveraendertem_default_timeout_endet_nach_etwa_10s`, `test_radar_segment_tests_liefern_zu_jeder_wanduhrzeit_dasselbe_ergebnis`, `lauf_bei_uhrzeit`, `matrix_differenz`

> **Schicht-Hinweis:** Reine Testinfrastruktur (`tests/`, Doku-Artefakte). Keine Produktdatei (`src/`, `.claude/hooks/`, Go, Frontend), keine neue Abhängigkeit (pytest, pytest-timeout, pytest-xdist, httpx, freezegun sind vorhanden). Querschnitts-Prüfpunkte entfallen: Kanäle, Mandantentrennung und Trip/Ortsvergleich-Teilung sind nicht berührt, Nutzerdaten werden nicht bewegt (der mtime-Nachweis liest nur Zeitstempel, kein Schreibzugriff).

## Estimated Scope

- **LoC:** ca. +150/-110 (Grenze ±250)
- **Files:** 5 (vier Testdateien, ein Testhelfer), dazu Nachweise unter `docs/artifacts/rework-3317-wartezeiten/`
- **Effort:** medium (Risiko: still geschwächte Zusicherung; Schutz ist die Mutations-Gegenprobe je umgebautem Test)

### Affected Files

| File | Change Type | Scheibe | Description |
|------|-------------|---------|-------------|
| `tests/refactor/test_epic_129a_3_ui_removed.py` | MODIFY | A | `test_ac7_collection_clean` (Z. 146-177, Voll-Sammlung per `uv run`) entfällt nur unter AC-4 |
| `tests/tdd/test_dwd_thunder_parallel_fetch.py` | MODIFY | A | Der 10-s-Test (Z. 633-658) wird zu Konstante plus Spion; `_Server` ohne `getfqdn` |
| `tests/tdd/test_pytest_collection_and_timeout_safety.py` | MODIFY | A | eine echte Sammlung mit Mitschreib-Plugin, Beleg-Läufe `-m`, Hänger-Test aus zwei Teilen |
| `tests/tdd/test_radar_nowcast_segment_wanduhr_unabhaengig.py` | MODIFY | A | Referenzmessung wiederverwenden |
| `tests/helpers/wanduhr_matrix.py` | MODIFY | A | Messpunkte nur bei nachgewiesenem Gewinn gleichzeitig; Aufrufer-Schnittstelle bleibt |
| `tests/tdd/test_einstellung_gleich_mail_validatoren.py`, `tests/helpers/mail_lang_fixture.py` | (nicht angefasst) | B | Folge-Issue, siehe Known Limitations |

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| pytest, `pytest-timeout`, `pytest-xdist` (`--dist loadgroup`), `freezegun`, `httpx` | bestehend | Sammlung, Timeout-Belege, Worker-Gruppen, gestellte Uhr, Spion an `httpx.Client.send` |
| `src/providers/dwd.py` (`THUNDER_REQUEST_TIMEOUT` Z. 162, Verdrahtung Z. 627-629 über `capped_timeout_or_raise`) | bestehend, unverändert | Prüfling des DWD-Umbaus |
| `tests/conftest.py` (`xdist_group`-Gruppen, `echtdaten`) | bestehend | Worker-Gruppe der Sammlungs-Datei |
| `tests/helpers/wanduhr_matrix.py` | bestehend | weitere Nutzer: `test_wanduhr_matrix`, `test_prozesszonen_schalter`, `test_radar_onset_threshold_variance`, `test_fixture_wallclock_ratchet`, `tests/tdd/conftest.py`; müssen grün bleiben |
| `docs/specs/modules/rework_3279_scanner_ratschen_tempo_s1.md` | Vorbild | Muster: Worker-Gruppe, Mutations-Gegenprobe, Messnachweis |
| `docs/artifacts/rework-3279-testsuite-tempo/messung_vorher.py` | bestehend | Messwerkzeug für Vorher/Nachher |

## Implementation Details

Reihenfolge der Umsetzung: (1) ac7, (2) DWD, (3) Sammlung und Hänger, (4) Radar; je Schritt zuerst Vorher-Messung, dann Umbau, dann Mutations-Gegenprobe und Nachher-Messung. Alle Schritte laufen ohne menschliche Freigabe (kein Override). Maßgeblich ist der Abschnitt „Gegenprüfung" in `docs/context/rework-3317-wartezeiten.md`.

**1. ac7 (`test_epic_129a_3_ui_removed.py`).** Der Test prüft dasselbe wie `test_full_suite_collection_still_exits_zero` (Exit 0, keine Sammelfehler); Unterschied ist nur `uv run` und der Pfad `tests/`. Er entfällt nur, wenn die Mutation „kaputter Import" (eine Testdatei importiert ein nicht existierendes Modul) im verbleibenden Test rot wird, geprüft gegen den Stand vor UND nach dem Umbau aus Schritt 3. Beachten: der verbleibende Test sucht `ERROR` in der Ausgabe, ac7 den Text „error during collection" (kleingeschrieben) plus Exit-Code; wird die Mutation nicht rot, bleibt ac7 unverändert stehen. Schritt 1 misst nur den Vorher-Stand; die endgültige Entscheidung und das Entfernen fallen erst nach Schritt 3.

**2. DWD (`test_dwd_thunder_parallel_fetch.py`).** Der 10-s-Test wartet den unveränderten Default real ab. Ersatz: (a) `dwd.THUNDER_REQUEST_TIMEOUT == 10.0` bleibt geprüft; (b) ein durchreichender Spion an `httpx.Client.send` schreibt den an den echten Gewitter-Requests wirksamen Lese-Timeout mit und schlägt ohne gesehenen Request fehl (kein Patch am Produktcode, der Request läuft echt gegen den lokalen Testserver, der sofort antwortet; das Budget liegt weit entfernt, damit `capped_timeout_or_raise` den Wert nicht deckelt); (c) das Verhalten (Abbruch am Timeout, URL genau einmal angefragt, kein Retry, Zelle `None`) bleibt im bestehenden 2-s-Test (`test_ac3_haengender_download_kostet_hoechstens_den_timeout_und_wird_nicht_wiederholt`, Z. 351). Der Testserver `_Server` bekommt ein `server_bind` ohne `socket.getfqdn` (nur in der Testdatei; der Produktcode bleibt unberührt). Befund: lokal kostet `getfqdn("127.0.0.1")` gemessen 35 s; das trifft den ersten Serverstart der Datei und damit `test_ac1_...` (lokal rot am 40-s-Timeout). Warum der 2-s-Test 10,5 s dauert, ist UNGEKLÄRT: sein Serverstart liegt innerhalb der Messung (`t0` vor `_dwd_server`), die Zusicherung `dauer <= 5 s` besteht aber, der Rest fällt also außerhalb an (Vermutung: Raster-Vorab-Erzeugung, ungemessen). Er ist vor dem Umbau zu messen. Nach dem Umbau gilt ac1 lokal NICHT als repariert (zusätzlich schlief `sleep(0.2)` gemessen 0,395 s, nur 8-9 von 12 Zeitpunkten, gefordert ≥ 10; Ursache ungeklärt), und die Schwelle wird NICHT gesenkt.

**3. Sammlung und Hänger (`test_pytest_collection_and_timeout_safety.py`).** Heute: vier Modul-Fixtures (`default_/email_/staging_/live_collect`) = je eine Voll-Sammlung, drei Teil-Sammlungen mit `-o addopts=`, eine zweite Voll-Sammlung im mtime-Test (Z. 390), ein echter 30-s-Hänger (Z. 640). Neu:

- EINE echte Voll-Sammlung in EINEM Subprozess pro Datei-Lauf, mit Mitschreib-Plugin per `-p` (nie im Testprozess: dort gälten die CI-Optionen wie `--ignore`, die Zahlen wichen ab). Das Plugin schreibt mit: `pytest_itemcollected` = Gesamt (inkl. später abgewählter Items), `session.items` bei `pytest_collection_finish` = gewählt, je Item die Marker. Exit 0 und „kein ERROR" dieses Laufs bleiben zugesichert. Gesamt, gewählt, `email`/`live`/`staging` und die drei Teil-Sammlungen werden daraus abgeleitet.
- Ableitung ersetzt nicht den Beleg, dass pytest `-m` richtig auswertet: je ein echter kurzer Lauf mit `-m email`, `-m live` und `-m staging` auf je einer Datei (Kommandozeile ersetzt die addopts-Auswahl) bleibt Pflicht. Kein `conftest.py` wertet die Marker-Auswahl aus (`tests/conftest.py` Z. 907 setzt nur `xdist_group`).
- mtime-Nachweis (Echtdaten `data/users/default/trips/*.json` unberührt): Zeitstempel werden vor und nach genau dieser einen Sammlung gelesen; der zweite Voll-Lauf entfällt.
- Worker-Gruppe (Entscheidungsregel): CI läuft `-n 4 --dist loadgroup`, Modul-Fixtures entstehen je Worker neu. Ist die Datei nach dem Umbau kurz (Richtwert 20 s, unter `-n 4` gemessen), kommt die ganze Datei in die Gruppe `echtdaten` (genau eine Sammlung samt mtime-Nachweis). Sonst eigene `xdist_group` (Name ohne `@`, nicht `echtdaten`) und eine eigene Sammlung für den mtime-Test.
- Hänger: heutiger Test belegt nur `returncode != 0` (jeder Abbruch unter 60 s bestünde). Ersatz in zwei Teilen: (a) im Kindprozess wird aus der echten Konfiguration (`-c pyproject.toml`) der wirksame Wert 30 belegt (Hook `pytest_timeout_set_timer` oder gleichwertig), (b) ein echter Hänger mit kurzem Limit (wenige Sekunden) wird nachweislich abgebrochen, belegt durch die Timeout-Meldung in der Ausgabe und eine Laufzeit deutlich unter der Hängerdauer, nicht nur durch den Exit-Code. Beide Teile sind nötig.

**4. Radar.** Die Referenzmessung (erste Uhrzeit) wird heute einmal für die Positivkontrolle und ein zweites Mal in `matrix_differenz` gemessen; sie wird wiederverwendet (der Test sichert Reproduzierbarkeit der Referenz nicht eigens zu). Weiterhin ein frischer Prozess je Datenpunkt (Pflicht laut Docstring `wanduhr_matrix`, #1709). Gleichzeitiges Starten der frischen Prozesse nur, wenn die Messung unter `-n 4` einen Gewinn zeigt; sonst bleibt es nacheinander. Die Signaturen `lauf_bei_uhrzeit` und `matrix_differenz` bleiben aufrufkompatibel, die fünf weiteren Nutzer von `wanduhr_matrix` laufen grün.

**Messregeln.** Vorher/Nachher je Datei einzeln, seriell und unter `-n 4 --dist loadgroup`, am selben Rechner im selben Zeitfenster (Last schwankt). Nachweise unter `docs/artifacts/rework-3317-wartezeiten/`. Bekannte Ausgangsmessung (24.11.2026, Mac, seriell, Stand 5a442bd41, Summe der 45 langsamsten Phasen, nur Untergrenze, kein Vollwert): Sammlung 258 s, DWD 73 s, Radar 64 s, ac7 45 s; alle fünf Dateien zusammen 930,6 s mit einem roten Test (DWD ac1). Zahlen nach dem Umbau sind ungemessen; Zeitziele sind nicht vorgegeben.

**Offene Befunde.** (1) DWD ac1 lokal rot, nicht Teil des Umbaus, siehe Schritt 2. (2) `main` ist in CI rot durch `tests/test_3197_kanal_paritaet.py::test_etappe_3_mail_zeigt_die_neuen_wegpunkt_zeiten` (Lauf 45372227336, Vermutung Uhrzeitabhängigkeit ungeprüft): nicht Teil dieser Spec, blockiert aber den Merge und wird vor dem PR geklärt (eigenes Issue oder eigener Fix, nicht in diesem PR).

**Code-Abgleich (Zeilennummern der Analyse am Code geprüft).** Z. 146 (ac7), 373/390 (mtime), 640 (Hänger), 634/351 (DWD), `dwd.py` 162/534 stimmen. Abweichungen: die Verdrahtung `capped_timeout_or_raise(base_timeout=THUNDER_REQUEST_TIMEOUT)` steht in `dwd.py` bei Z. 627-629 (Literal-Zeile ist 629, nicht 628); Z. 534 nutzt dieselbe Konstante nur als `acquire`-Timeout, nicht als HTTP-Timeout.

## Expected Behavior

- **Input:** Lauf der vier Testdateien der Scheibe A lokal oder in CI.
- **Output:** dieselben Zusicherungen wie zuvor (zum Teil strenger), je Datei belegt kürzere oder begründet unveränderte Laufzeit.
- **Side effects:** keine; kein Produktcode, kein angehobenes Timeout, `data/users/` bleibt unberührt.

## Acceptance Criteria

- **AC-1:** Given die Sammlungs-Datei läuft / When sie die Sammlung der ganzen Suite prüft / Then läuft genau eine echte Voll-Sammlung in einem Subprozess pro Datei-Lauf (im Ausweichfall der Worker-Gruppen-Regel höchstens zwei: die eigene Sammlung des mtime-Tests kommt hinzu), deren Exit 0 und das Fehlen von ERROR zugesichert bleiben, Gesamt, gewählt und Marker sind daraus abgeleitet, und der Nachweis, dass Echtdaten unberührt bleiben, liegt um genau diese Sammlung.
  - Test: Zähler der Voll-Sammlungs-Subprozesse = 1 (Ausweichfall: 2), auch unter `-n 4 --dist loadgroup`; Mutation (Exit-Code oder ERROR-Prüfung entfernen, Marker-Ableitung verfälschen, Echtdaten-Datei im Test berühren) macht mindestens einen Test rot.

- **AC-2:** Given die Ableitung aus der einen Sammlung / When je ein echter Lauf mit `-m email`, `-m live` und `-m staging` auf je einer Datei läuft / Then liefert pytest dieselbe Auswahl, wie sie die Ableitung für diese Datei nennt.
  - Test: drei kurze Subprozess-Läufe (nur sammeln, nie ausführen); Vergleich der Test-Kennungen mit der Ableitung; verfälschte Marker-Ableitung wird rot.

- **AC-3:** Given der Hänger-Test / When er läuft / Then ist das wirksame Limit 30 aus der echten Konfiguration belegt UND ein Hänger mit kurzem Limit wird nachweislich abgebrochen (strenger als der heutige Vergleich `Exit-Code != 0`).
  - Test: Kindprozess meldet den wirksamen Wert; zweiter Lauf mit kurzem Limit bricht ab; Mutation (`timeout = 30` in einer Kopie der Konfiguration auf 300 oder Abbruchnachweis entfernt) macht je einen Teil rot.

- **AC-4:** Given der Sammel-Test `test_ac7_collection_clean` / When die Mutation „kaputter Import in einer Testdatei" im verbleibenden Test `test_full_suite_collection_still_exits_zero` rot wird / Then entfällt ac7; wird sie nicht rot, bleibt ac7 stehen.
  - Test: Mutation per Kopie mit einem Import auf ein nicht vorhandenes Modul, Ergebnis im Artefakt; Prüfung vor und nach dem Umbau aus AC-1.

- **AC-5:** Given der DWD-Test für den Standard-Timeout / When er läuft / Then ist die Konstante 10.0 belegt, der am echten Request wirksame Lese-Timeout wird per durchreichendem Spion an `httpx.Client.send` mitgeschrieben, das Verhalten (Abbruch am Timeout, kein Retry, Zelle leer) bleibt im 2-s-Test, und der Testserver baut ohne `getfqdn` auf (nur in der Testdatei).
  - Test: vier Mutationen, jede einzeln rot im jeweils genannten Test: Konstante auf 30 (Konstanten-Prüfung und Spion); Literal 30.0 statt Konstante an der Verdrahtung (Spion); Literal 10.0 statt Konstante (der Spion sieht denselben Wert und fängt das NICHT, erwartet rot: der 2-s-Test, weil er die Konstante auf 2,0 stellt); Retry an (2-s-Test, Haenger-URL mehr als einmal). Der Spion wertet nur Gewitter-Abrufe aus und schlägt fehl, wenn er keinen gesehen hat. Ac1 bleibt lokal als rot dokumentiert, Schwelle unverändert.

- **AC-6:** Given der Radar-Test und `wanduhr_matrix` / When die Messpunkte laufen / Then wird die Referenzmessung wiederverwendet, es läuft weiterhin ein frischer Prozess je Datenpunkt, Parallelisierung gibt es nur bei gemessenem Gewinn unter `-n 4`, und die übrigen Nutzer von `wanduhr_matrix` bleiben grün.
  - Test: Prozessstart-Zähler je Datenpunkt = 1; Mutation (Referenz wird falsch wiederverwendet, z. B. leere Referenz) wird rot; Läufe von `test_wanduhr_matrix`, `test_prozesszonen_schalter`, `test_radar_onset_threshold_variance` und `test_fixture_wallclock_ratchet` grün.

- **AC-7:** Given je ein umgebauter Test (Sammlung, Hänger, DWD, Radar, ac7-Entscheidung) / When eine gezielte Verfälschung eingebaut wird / Then ist mindestens ein Test rot, und die Gegenprobe ist je Test protokolliert.
  - Test: Mutation nur per String-Ersetzung mit externer Sicherungskopie, nie `git checkout`, `git stash` oder `git reset`; Datei zurückgespielt und Hash geprüft; Protokoll im Artefakt-Ordner.

- **AC-8:** Given jede der vier Testdateien der Scheibe A / When sie vorher und nachher am selben Rechner im selben Zeitfenster einzeln gemessen wird, seriell und unter `-n 4 --dist loadgroup` / Then liegt je Datei ein Vorher/Nachher-Wert vor, und ein Umbau gilt nur als Erfolg, wenn die Datei schneller ist; sonst wird er zurückgenommen oder begründet belassen.
  - Test: Messnachweis je Datei im Artefakt-Ordner; kein Laufzeit-Assert als Dauertest (wackelt mit der Last); „kein Timeout angehoben" wird als einmaliger Nachweis (Vergleich vorher/nachher) im Artefakt-Ordner geführt, nicht als Test.

## Test Plan

### Automated Tests (TDD RED)

- [ ] Sammlung: GIVEN ein verfälschter Marker-Ableiter WHEN die Datei läuft THEN rot; Subprozess-Zähler für Voll-Sammlungen wie AC-1.
- [ ] Marker-Belege: GIVEN je eine Datei mit email/live/staging WHEN der echte `-m`-Lauf sammelt THEN deckt sich die Auswahl mit der Ableitung.
- [ ] Hänger: GIVEN die echte Konfiguration WHEN der Kindprozess den Wert meldet THEN 30; GIVEN kurzes Limit WHEN ein Test schläft THEN Abbruch.
- [ ] DWD: GIVEN Konstante 10.0 und Spion WHEN ein echter Request läuft THEN Lese-Timeout 10,0; Verhalten im 2-s-Test.
- [ ] Radar: GIVEN eine Referenz WHEN `matrix_differenz` läuft THEN ein frischer Prozess je Datenpunkt, Referenz einmal gemessen.
- Einmalige Nachweise im Artefakt-Ordner (kein Dauertest): Mutations-Gegenprobe (AC-4, AC-7), Vorher/Nachher-Zeit (AC-8).

## Scope

- **In Scope:** vier Testdateien und ein Helfer (Tabelle oben), Messnachweise.
- **Out of Scope:** Mail-Validatoren (Scheibe B, `test_einstellung_gleich_mail_validatoren.py`, `tests/helpers/mail_lang_fixture.py`), jede Produktänderung (`src/`, `.claude/hooks/`), der rote CI-Test `test_3197_kanal_paritaet`, lokale parallele Form (#3278), Scheibe 1 (#3279) und Scheibe 2 (#3316).

## Definition of Done

- [ ] AC-1 bis AC-8 erfüllt, alle Tests der vier Testdateien grün (DWD ac1 darf ausschließlich lokal auf dem Mac rot sein, dokumentiert; in CI muss er grün sein).
- [ ] Nachweise zu Mutations-Gegenprobe und Vorher/Nachher liegen unter `docs/artifacts/rework-3317-wartezeiten/`.
- [ ] Kein Timeout angehoben, keine Schwelle gesenkt, kein Produktcode berührt.
- [ ] Alle CI-Pflicht-Checks grün; der Merge-Blocker auf `main` (`test_3197_kanal_paritaet`) ist vorher geklärt.

## Known Limitations

- **Bewusste Abweichung vom Issue-Umfang:** Issue #3317 nennt fünf Dateien, diese Spec deckt vier davon plus den Helfer ab. `tests/tdd/test_einstellung_gleich_mail_validatoren.py` (Scheibe B) ist NICHT Teil dieser Spec und dieses PR. Begründung: gemessene Ausgangszeit 455 s (147 grün), der Umbau (vorgewärmter Fork-Server mit echtem Chromium je Validator, Fallen bei `os.environ`, `chdir`, macOS-fork, je Worker ein Server) ist ein eigenes Risiko und würde die LoC-Grenze von 250 sprengen. Die Scheibe wird als eigenes Folge-Issue geführt (Nummer noch nicht vergeben). #3317 bleibt bis dahin offen bzw. der Rest wandert ins Folge-Issue. Das Abschlusskriterium des Issues („Vorher/Nachher je Datei") ist mit dieser Spec daher nur für die Scheibe-A-Dateien erfüllt.
- Alle Einsparungen sind Ansätze, nach dem Umbau ungemessen; ein Umbau ohne messbaren Gewinn wird zurückgenommen oder begründet belassen.
- Absolutzeiten schwanken auf dem Mac mit der Last; Vergleich nur im selben Zeitfenster. Die Top-45-Werte sind Untergrenzen.
- DWD ac1 bleibt lokal rot (`getfqdn` 35 s, Schlafzeit-Befund); der Umbau macht ihn lokal nicht grün.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Reine Testinfrastruktur ohne Änderung an Kanälen, Providern, Datenmodell, Auth oder Test-Politik; die Zusicherungen bleiben, nur der Weg dorthin wird kürzer.

## Changelog

- 2026-11-24: Initial spec created (Workflow rework-3317-wartezeiten, Issue #3317, Scheibe A)
