# Adversary Dialog — fix-2744-uhrzeitabhaengige-tests
Spec: docs/specs/modules/fix_2744_uhrzeitunabhaengige_tests.md
Datum: 2026-11-06 15:57

## Checkliste
- [x] **Input:** Testlauf zu beliebiger Tageszeit, auch mit `GZ_TEST_WALL_CLOCK_UTC` zwischen 23:30 und 24:00 UTC.
  Beweis: die 7 betroffenen Dateien (106 Tests) liefen im Normallauf und mit GZ_TEST_WALL_CLOCK_UTC=2026-11-05T23:58:00+00:00 vollständig grün.
- [x] **Output:** dieselben Tests sind grün, mit demselben fachlichen Inhalt.
  Beweis: beide Läufe ohne Fehlschlag; Zusicherungen der f002-Tests im Wortlaut unverändert, nur die Uhr fest.
- [x] **Side effects:** keine; Produktivcode unverändert.
  Beweis: `git diff --stat` zeigt nur Dateien unter tests/; nichts unter src/, internal/, api/.
- [x] **AC-1:** Given die beiden f002-Tests (`..._ruhezeit_folgt_der_heutigen_etappe_nicht_der_ersten`, `..._tageszaehler_folgt_der_heutigen_etappe_nicht_der_ersten`) und die gestellte Wanduhr `GZ_TEST_WALL_CLOCK_UTC=2026-11-05T23:40:00+00:00` / When sie laufen / Then sind beide grün (vorher rot), und bei 12:00 UTC bleiben sie grün.
  Beweis: grün unter 23:58/23:40/12:00 UTC und im Normallauf; Mutation 2e (freeze_time entfernt) wird unter 23:40 UTC rot, die feste Uhr wirkt.
- [x] **AC-2:** Given die Verfälschung `anchor_tz(trip, now)` → `trip_tz(trip)` im Prüfling `trip_alert` / When die f002-Tests unter der festen Uhr laufen / Then werden beide rot (Mutations-Gegenprobe, die Zusicherung wirkt dort, wo sie gilt).
  Beweis: Mutation 2a in src/services/trip_alert.py (14 Stellen) macht beide f002-Tests rot, auch bei 12:00 UTC.
- [x] **AC-3:** Given die Gestern-Zone-Tests (`test_ac2_gestern_zone_liefert_prozesstag_gleich_utc_tag_minus_eins`, `test_utc_tag_unter_gestern_zone_weicht_vom_prozesstag_ab`) / When sie zu einer echten Startzeit zwischen 23:30 und 24:00 UTC laufen / Then wählen sie eine tragende Zone und sind grün; die Zonenwahl steht an EINER Stelle für beide Dateien.
  Beweis: beide Dateien nutzen tests/helpers/gestern_zone.py (`GESTERN_ZONE`); Mutation 2c (`<-2330>+23:30`) macht test_ac3_gestern_zone_traegt_den_ganzen_utc_tag[23-45-0] und [23-59-59] rot.
- [x] **AC-4:** Given der Test `test_ac1_deutsch_ohne_lang_gleich_lang_de` / When die beiden Renderläufe über einen Minutenwechsel laufen würden / Then bleiben die Ergebnisse gleich, weil die Uhr um beide Läufe fest steht; der Test bleibt grün.
  Beweis: Mutation 2d (freeze_time in render_paar_bei_fester_uhr entfernt) macht test_ac4_paar_ist_gleich_obwohl_die_uhr_ueber_die_minute_laufen_wuerde rot.
- [x] **AC-5:** Given der SMS-Test des Ortsvergleich-Radar-Alarms (`Zermatt: R@\d{1,2}:\d{2}`) / When er bei 23:55 UTC läuft / Then ist er grün (vorher `R@Mo0:03`-Fehlschlag).
  Beweis: grün bei 23:55 und 23:58 UTC; ohne freeze_time bei 22:55 UTC (Wien 23:55) rot ("Zermatt: R@Fr0:03").
- [x] **AC-6:** Given die Gestern-Zone-Tests und die gestellte Wanduhr / When die Wanduhr gesetzt ist / Then lesen diese Tests weiterhin die echte Zeit per `date -u` (kein stilles Einfrieren der Prüfaussage, #2096).
  Beweis: Mutation 2b (`datetime.now(timezone.utc)` statt `date -u`) macht test_ac6_echte_uhr_wird_per_date_gelesen_nicht_per_datetime_now und test_ac3_selbstschutz_bei_nicht_tragender_zone_scheitert_sichtbar rot.
- [x] **AC-7:** Given die gesamte betroffene Testmenge / When sie mit `GZ_TEST_WALL_CLOCK_UTC` auf 12:00, 23:40 und 23:58 UTC läuft / Then ist das Ergebnis jeweils grün (Zeitunabhängigkeit, wie #2096 AC-10).
  Beweis: Normallauf, 12:00, 23:40, 23:58 und 22:55 UTC je 106 Tests grün.

## Dialog

### Runde 1
**Adversary:** Kein Produktivcode geändert; 6 Mutationen (Sicherung extern, Rückspielen per diff geprüft), alle gefangen: 2a anchor_tz → trip_tz (Code reference: src/services/trip_alert.py:750) beide f002 rot; 2b echte_utc_jetzt auf datetime.now (Code reference: tests/helpers/gestern_zone.py:30) 2 Tests rot; 2c Zone getauscht (Code reference: tests/helpers/gestern_zone.py:17) 2 Tests rot; 2d Fixture-freeze_time entfernt (Code reference: tests/helpers/briefing_html_sprache_fixture.py:118) Minutenfest-Test rot; 2e f002-freeze_time entfernt (Code reference: tests/tdd/test_ruhezeit_und_zaehler_folgen_der_ortszone.py:1603) beide rot unter 23:40; R@-freeze_time entfernt (Code reference: tests/tdd/test_alert_sms_location_positions.py:1045) rot unter 22:55.
Finding: ID F001, Severity LOW, Category anti_pattern, Code reference: tests/tdd/test_ruhezeit_und_zaehler_folgen_der_ortszone.py:79, Description: `ROOT =Path(...)` (fehlendes Leerzeichen), Evidence: git diff, Remediation: Leerzeichen zurücksetzen (inzwischen behoben).
**Implementierer:** F001 behoben. Beide Abweichungen begründet (real_datetime: Vergleichsuhr darf nicht über `date -u` laufen, sonst Zirkelschluss; echte_utc_jetzt im Selbstschutz-Test: Sonde läuft ungefroren und nennt die echte Zeit).

### Runde 2
**Adversary:** Abweichungen geprüft: real_datetime ist unabhängig von der Wanduhr, Zusicherung scharf (2b rot, `assert 2001 >= 2026`); der Selbstschutz-Test wird von 2b gefangen. Alle Dateien nach den Mutationen byte-gleich zur Sicherung. Keine weiteren Findings.
**Implementierer:** Keine offenen Punkte.

## Herkunft der Vorbedingungen

kein Sprachprofil konfiguriert (`precondition_origins.default_lang`)

## Geprüfte Code-Stellen
Code reference: src/services/trip_alert.py:750
Code reference: tests/helpers/gestern_zone.py:17
Code reference: tests/helpers/briefing_html_sprache_fixture.py:118
Code reference: tests/tdd/test_ruhezeit_und_zaehler_folgen_der_ortszone.py:1603
Code reference: tests/tdd/test_alert_sms_location_positions.py:1045
Code reference: tests/tdd/test_gestern_zone_hilfe.py:52
Code reference: tests/tdd/test_prozesszonen_schalter.py:187
Code reference: tests/tdd/test_ortstag_helfer.py:231
Code reference: tests/unit/test_briefing_html_minutenfest.py:20
Code reference: tests/unit/test_briefing_html_sprache.py:138

## Verdict: VERIFIED

## Geprüfte Dateien

- sha256:93dae593d00e1d873ef48fa28b53a6933c374c8e40a104dc08cefcfcba37fea2  src/services/trip_alert.py
- sha256:7507787fb6ac34b36513f32212335a6a14efb534d3d88d052a645235ef1713be  tests/helpers/briefing_html_sprache_fixture.py
- sha256:e2faa4fccb6e835c3d7337f4be6b644f84f781863a2cb927e167cdc453824f3b  tests/helpers/gestern_zone.py
- sha256:f11b3b0ac9a6739e16e195e8f794c47f120f285f96d14805285e575dcd7328a0  tests/tdd/test_alert_sms_location_positions.py
- sha256:5565082fb48c20bc80c64857040b29a6c9d5082426de5591c540c80b1fd525df  tests/tdd/test_gestern_zone_hilfe.py
- sha256:6a14e9f39e58eba30fdbe5dd6e9876f2f979477ff08ad6f28f19eb1bb4c801d0  tests/tdd/test_ortstag_helfer.py
- sha256:a2b11e1b1f5cd37e1448d85158712986ad5652aef2891fcefee5516f01b8a334  tests/tdd/test_prozesszonen_schalter.py
- sha256:3c3d91cf31aa9eb3102471e5dee10e8329cc0f6fc408294c98b0b092fb18706a  tests/tdd/test_ruhezeit_und_zaehler_folgen_der_ortszone.py
- sha256:5045ecc48e447c5883b749da82162f7d42cb85cc35515d73f56188f02ecaef46  tests/unit/test_briefing_html_minutenfest.py
- sha256:13c439b9e1cae1af1ce6fd556b70f51eeaa0770de692401a2f86f1b74cd98c46  tests/unit/test_briefing_html_sprache.py

## Prüfbasis

- base: 2b7f45ba3e536ff268f385d87d31889cb8fd03cf
- blob:0e29203ad3870fd54e6972318f6b43db747717ed  src/services/trip_alert.py
- blob:2dfcde3f9aef45557d2ea835610ced35ef81d5df  tests/helpers/briefing_html_sprache_fixture.py
- blob:9f035105757740d697abc661de9805b582a600b5  tests/helpers/gestern_zone.py
- blob:b9cace223ba742966391a20b1ed899a6c8e2fba9  tests/tdd/test_alert_sms_location_positions.py
- blob:c5027644ccf0ddfb2197e4df01476b1da3b84696  tests/tdd/test_gestern_zone_hilfe.py
- blob:09dba7e314d631dc81be852799e2be801c47bc0c  tests/tdd/test_ortstag_helfer.py
- blob:43545c17132e95bb8fb9834efb56b1dea7c58e04  tests/tdd/test_prozesszonen_schalter.py
- blob:4a0cad0fd9d557ba9ac40a094d5d94ac501d8e51  tests/tdd/test_ruhezeit_und_zaehler_folgen_der_ortszone.py
- blob:f255581481c3c99a77b87611629d88cce142ab47  tests/unit/test_briefing_html_minutenfest.py
- blob:3aab2c659044624195ddb49c98a2d769bd2e4018  tests/unit/test_briefing_html_sprache.py
