# Adversary Dialog — rework-3208-doppelte-tests
Spec: docs/specs/modules/rework_3208_doppelte_zusicherungen.md
Datum: 2026-11-21 21:05

## Checkliste
- [x] **Input:** Testbestand mit den fuenf belegten Dopplungen der ersten Scheibe.
- [x] **Output:** gleiche geprueften Zusicherungen, an je einer Stelle; Wegstrecken-Datei entfaellt; Falllisten-Verweise zeigen auf den Ersatztest; Kern-Schicht weiter 100 % gruen.
- [x] **Side effects:** keine Auswirkung auf Produktverhalten oder Deploy-Inhalt; Testanzahl sinkt netto um 5.
- [x] **AC-1:** Given ein Testfall wird im Zuge der ersten Scheibe entfernt / When der Umbau fertig ist / Then ist jede entfernte Zusicherung identisch oder echte Teilmenge einer bleibenden und in der Spec je Fall mit Ziel-Test belegt (Wegstrecke ac1 -> etappenregel ac4, ac2 -> ac7, ac4 -> ac2[kleiner]; ac3 und ac5 als neue Faelle uebernommen; 802 ac4 -> ac3[W], 802 ac3[A] -> ac1; 3099 ac6 -> 3100 ac1 plus Festwert-Test), und ein nur aehnlicher Fall (3196 gegen 3197) bleibt unveraendert.
- [x] **AC-2:** Given die sechs Mutationen G1a-G1d, G3a, G3b / When sie vor dem Umbau und nach dem Umbau je per String-Ersetzung mit externer Sicherungskopie angewendet werden (nie `git checkout/stash/reset`) / Then wird jede Mutation vorher und nachher von mindestens einem Test der benannten Dateien rot gefangen, und nach Wiederherstellung aus der Sicherung sind diese Tests wieder gruen.
- [x] **AC-3:** Given Testfaelle tragen Issue-Bezuege (#2042, #2082, #3196, #3099 AC-6, #802) / When die Faelle zusammengelegt werden / Then bleibt der Issue-Bezug als Kommentar oder Docstring am bleibenden bzw. uebernommenen Test erhalten, insbesondere #2042 im Kopf von `test_gehzeit_etappenregel.py` und #3099 AC-6 am Festwert-Test.
- [x] **AC-4:** Given die Datei `tests/tdd/test_gehzeit_folgt_wegstrecke.py` und die entfernten Testnamen (`test_ac4_wanderer_default_naismith_sum`, `test_ac6_premium_gleich_sms_trotz_abweichender_premium_ebene`) sind geloescht / When ueber `tests/`, `docs/`, `internal/`, `frontend/` und `.claude/` (inkl. versteckter Ordner) nach den Namen gesucht wird / Then gibt es ausserhalb des Context-Dokuments keine verwaisten Verweise, und der Falllisten-Waechter `test_einstellung_gleich_mail_fallliste.py` sowie `test_stillgelegte_testdateien.py` und der Doku-Waechter #316 sind gruen.
- [x] **AC-5:** Given die Collect-Liste der berührten Testdateien vor dem Umbau / When nach dem Umbau `pytest --collect-only -q` auf dieselben Dateien laeuft / Then ist die Testanzahl netto um genau 5 gesunken (3 aus der Wegstrecken-Datei, 2 aus 802, 3099 netto gleich), es verschwinden nur die geplanten Faelle und es gibt keine Collect-Fehler.
- [x] **AC-6:** Given alle berührten Testdateien (`test_gehzeit_etappenregel.py`, `test_issue_802_fahrrad_segment_zeit.py`, `test_3099_sms_resolver.py`, `test_3100_premium_sms_fallliste.py`, `test_3196_trip_tempo_dav.py`, `test_3197_tempo_je_etappe.py`, `test_einstellung_gleich_mail_fallliste.py`) / When sie namentlich ausgefuehrt werden (nie `uv run pytest` ohne Dateien) / Then sind alle gruen, und die Kern-Schicht ist zu 100 % gruen, alle 6 CI-Checks des PR sind gruen.
- [x] **AC-7:** Given der Umbau betrifft nur Testsammlung und Dokumentation / When der Diff gegen `origin/main` geprueft wird / Then liegen alle geaenderten Dateien unter `tests/` oder `docs/`, und Produktionscode (`src/`, `api/`, `internal/`, `frontend/src/`, `cmd/`) ist unveraendert.
- [x] **AC-8:** Given die Falllisten `fallliste_sms.json` und `fallliste_premium_sms.json` verwiesen auf den entfernten 3099-Test / When die zwei Eintraege `sms-premium-gleich-sms-text` und `psms-trip-versand-abweichend` auf `test_3100_premium_sms_fallliste.py::test_ac1_trip_eingang_premium_gleich_sms` umgestellt sind / Then findet der Waechter beide Testverweise, die IDs und Achsen-Belegung bleiben vollstaendig, und die Hinweis-Liste in 3100 ist weiter gueltig.

## Dialog

### Runde 1
**Adversary:** Vergleich der entfernten Faelle mit den Zielen (git show HEAD gegen Arbeitsstand), Tests, Collect, Greps, Diff-Umfang.

Confirmation: AC: AC-1 | Code reference: tests/tdd/test_gehzeit_etappenregel.py:126 (ac3b), :203 (ac8) | Evidence: ac3b nutzt dieselbe Lage (G1 km 0, G2 2x Luftlinie, G3 km None bei _LON_B+0.03 = _LON_C) und denselben Assert wie das entfernte ac3; ac8 hat dieselben Eingaben (8,0 km, 1800 -> 2100 m) und beide Asserts (08:00, 10:30). ac1/ac2 sind identisch zu etappenregel ac4/ac7 (gelesen: gleiche Stage, gleiche Asserts). Entferntes ac4 (km 12 -> 4) ist Teilmenge von ac2[kleiner] (nicht strikt steigend; die Zusatzzusicherung Gehzeit > 0 steckt im approx(Luftlinie ca. 34 min)). Status: CONFIRMED
Confirmation: AC: AC-1 (802) | Code reference: tests/tdd/test_issue_802_fahrrad_segment_zeit.py:51 und :65 | Evidence: Parametrisierung B, C, W bleibt; ac1 liest jetzt _CONTRACT[A] (activity fahrrad_20, Hoehen 500/1100/1100/500, erwartet 08:00/09:00/09:00/09:36) und behaelt Persistenz-Asserts; W-Fall ist mit dem entfernten ac4 identisch (_CONTRACT[W], activity leer). Status: CONFIRMED
Confirmation: AC: AC-1 (3099) | Code reference: tests/tdd/test_3099_sms_resolver.py:213 | Evidence: Festwert E1 R2.0@4 G45@4 CT:SCT@4 unveraendert, Liste precipitation/gust/cloud_total. Entferntes ac6 (Premium = SMS, Versand) steckt im Trip-Eingang-Test test_3100 :156 (3 Ebenen x 2 Befehle). Beide teilen sich den Sendeweg notification_service.py:969 und den Renderer trip_report.py:499; eigene Mutationen E4/E5 werden von 3100 ac1 und ac3 gefangen. Status: CONFIRMED
Confirmation: AC: AC-4 | Evidence: grep ueber tests, docs, internal, frontend, .claude, cmd, src, api: Treffer nur im Herkunftskommentar etappenregel:18, Spec und rework-3208-Context/Artefakten. Status: CONFIRMED
Confirmation: AC: AC-5 | Evidence: pytest --collect-only auf dieselben Dateien: 203 collected (vorher 208, minus 5; Wegstrecke 5 weg, 802 minus 2, 3099 netto 0, etappenregel plus 2: ergibt netto -5). Artefakt adversary-collect.txt. Status: CONFIRMED
Confirmation: AC: AC-6 | Evidence: 9 Dateien (etappenregel, 802, 3099, 3100, 3196, 3197, fallliste, stillgelegte, #316-Docs) namentlich: 217 passed (adversary-test-output.txt). Status: CONFIRMED (CI-Checks nicht Gegenstand des Adversary-Laufs)
Confirmation: AC: AC-7 | Evidence: git diff --cached --name-only HEAD und git diff --name-only HEAD zeigen nur tests/ und docs/; git diff origin/main...HEAD enthaelt keinen Pfad ausserhalb tests/docs; git status --short src api internal cmd frontend/src leer. Status: CONFIRMED
Confirmation: AC: AC-3 | Code reference: tests/tdd/test_gehzeit_etappenregel.py:17-20 (#2042), tests/tdd/test_3099_sms_resolver.py:221 (Festwert aus ehemals AC-6 (#3099)), tests/tdd/test_issue_802_fahrrad_segment_zeit.py:54-58 (AC-4 im ac3-Docstring), etappenregel ac3b nennt #2082, ac8 nennt #3196. Status: CONFIRMED
Confirmation: AC: AC-8 | Code reference: tests/fixtures/einstellung_gleich_mail/fallliste_sms.json:22, tests/fixtures/einstellung_gleich_mail/fallliste_premium_sms.json:12 | Evidence: beide Faelle zeigen auf test_3100 test_ac1_trip_eingang_premium_gleich_sms, IDs und merkmale unveraendert, Waechter test_einstellung_gleich_mail_fallliste gruen. Status: CONFIRMED

**Implementierer:** (nicht beteiligt, Kontext-Isolation)

### Runde 2
**Adversary:** Mutationen gegen die Stelle, an der die Zusicherung wirkt (Details: adversary-mutation-output.txt). E1 Luecke nur am Etappenende ignoriert (trip_segments.py): rot in etappenregel ac3b (und 802 pause-Stage); E2 Rundung half-up -> floor (naismith.py): rot in 802 ac3[B]; E3 Abstiegsrate Fuss 500 -> 600 (naismith.py): rot u.a. 802 ac3[W], 3196, 3197; E4 Premium-Text im Trip-Sendeweg abweichend (notification_service.py): rot in 3100 ac1 (6x), ac3 (2x), ac4; E5 Premium-Text im Renderer abweichend (trip_report.py): rot in 3100 ac1 und ac3. Alle Mutationen per String-Ersetzung mit Sicherung ausserhalb des Repos, nach Wiederherstellung 106 bzw. 97 passed, sha-Pruefung im Skript, git status der Produktionsordner leer. Vorhandenes Protokoll (mutation-nachher.txt): G1a bis G1d, G3a, G3b alle rot, nur G1b-monotonie gruen.

Finding:
  ID: F001
  Severity: LOW
  Category: edge_case
  Code reference: src/services/trip_segments.py:147
  Description: Monotonie-Pruefung span <= 0 wird in den Tests von der Plausibilitaetspruefung (Zeile 154) maskiert, solange die Luftlinie > 0 ist. Mutation G1b-monotonie bleibt gruen (mutation-nachher.txt, vorher ebenfalls gruen laut Protokoll). Kein Umbaufehler, bestehende Luecke: kein Test hat zwei Wegpunkte mit identischer Position und gleichem km-Wert.
  Spec requirement: AC-2 — jede Mutation wird gefangen
  Conflict: eine Mutation bleibt vor und nach dem Umbau ungefangen; der Umbau verschlechtert sie nicht (ac2[gleich] und [kleiner] sind erhalten)
  Remediation: eigener Fall mit identischen Koordinaten und gleichem km in etappenregel (Folge-Issue, nicht in dieser Scheibe); in der Spec als aequivalente Mutation im Testumfang vermerken

Finding:
  ID: F002
  Severity: LOW
  Category: anti_pattern
  Code reference: tests/fixtures/einstellung_gleich_mail/fallliste_premium_sms.json:12
  Description: Fall psms-trip-versand-abweichend behaelt merkmale weg=versand, nutzer=zwei, kuerzung=153, zeigt aber auf test_ac1_trip_eingang_premium_gleich_sms (ein Nutzer, Eingangsweg, nur Obergrenze geprueft). Zwei Nutzer und Kuerzung bewachen ac3 und ac4 derselben Datei, Versand und Eingang nutzen denselben Sendeweg (E4/E5 beweisen die Wirkung). Die Achsen-Etikette ueberzeichnet den einen Test leicht.
  Spec requirement: AC-8 — IDs und Achsen-Belegung bleiben vollstaendig
  Conflict: laut Spec bewusst so entschieden (IDs und merkmale unveraendert); nur Praezision der Etiketten
  Remediation: optional weg auf eingang+versand setzen, so wie die Spec es als Rueckfall vorsah, falls der Waechter es zulaesst

**Implementierer:** (nicht beteiligt)

## Herkunft der Vorbedingungen

kein Sprachprofil konfiguriert (`precondition_origins.default_lang`)

## Verdict

**VERIFIED.** Alle Acht ACs und die drei Expected-Behavior-Punkte sind belegt: jede entfernte Zusicherung ist identisch oder echte Teilmenge einer bleibenden (uebernommene Faelle ac3b, ac8 und der Festwert-Test sind inhaltlich nicht abgeschwaecht), 217 benannte Tests gruen, Collect 208 -> 203, Diff nur tests/ und docs/, keine verwaisten Verweise. Fuenf eigene Mutationen (E1 bis E5) wurden alle gefangen, und zwar an der Stelle, die der Nutzer erreicht (Sendeweg und Renderer der Premium-SMS). Zwei LOW-Anmerkungen (F001 bestehende, aequivalente Mutation; F002 Etikett in der Falllistenzeile) blockieren nichts.

## Geprüfte Dateien

- sha256:0a25a3feeedb8f2c24eb71442d8137ff7226938b997ad784d2d576e5f4b1b19e  src/services/trip_segments.py
- sha256:9525cd85ed5282be989d3d69cb8d74db632cf65f1f22608944012d46468b2f03  tests/fixtures/einstellung_gleich_mail/fallliste_premium_sms.json

## Prüfbasis

- base: ca6b81eddc8005f05c156700d6a955eb8aa00dbd
- blob:3b5bbd798cad4095e3965ac9c6cffa5ebda5a546  src/services/trip_segments.py
- blob:ef4e71c22afe75a946fcc7e538b39b5309586e48  tests/fixtures/einstellung_gleich_mail/fallliste_premium_sms.json
