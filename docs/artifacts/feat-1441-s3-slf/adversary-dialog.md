# Adversary Dialog — feat-1441-s3-slf
Spec: docs/specs/modules/feat_1441_s3_slf.md
Datum: 2026-10-17 06:53

## Checkliste
- [x] **Input:** Koordinate eines Trip-Segments bzw. Ortsvergleich-Orts in der Schweiz; das aktuelle SLF-Bulletin (CAAML6).
- [x] **Output:** Null oder eine `OfficialAlert` der Gefahrenart `avalanche_bulletin` je Punkt (Stufe 1–5 mit Wortlaut, Höhe, Probleme, Tageszeit, Feinstufe), in den vier Kanälen und im Ortsvergleich wie der S1-Bericht; Quellenzeile mit Name, Link und Maßgeblichkeitshinweis in Mail und Telegram-Langform.
- [x] **Side effects:** Ein HTTP-Abruf je Cache-Zeitraum für die ganze Schweiz; Pro-Quelle-Journal (#1422) und Melde-Gedächtnis wie bei jeder amtlichen Quelle.
- [x] **AC-1:** [Grundfall] Given das Bulletin `at_2026-03-01T08:00:00Z.json` und ein Punkt in der Mikroregion `CH-7231` (Rating erheblich/minus, Problem Altschnee ab 2000 m) / When die Warnungen für diesen Punkt abgerufen werden / Then liefert die Quelle genau eine Warnung der Gefahrenart `avalanche_bulletin` mit `source="slf_bulletin:CH-7231"`, `dedup_id="avalanche_bulletin:CH-7231"`, `scale="eaws"`, `native_level=3`, `level=3`, Höhe „oberhalb 2000", dem Problem `persistent_weak_layers` und der konstanten SLF-Link-URL.
- [x] **AC-2:** [Höhe aus dem Problem, eindeutig] Given das Bulletin `at_2026-03-01T17:30:00Z.json`, Region `CH-7231` (Rating erheblich; Problem Altschnee ab 2000 m = erheblich, Problem Nassschnee bis 2200 m = mäßig) und das Bulletin `at_2026-01-15T08:00:00Z.json`, Region `CH-1311` (zwei erhebliche Probleme, beide ab 2000 m) / When die Warnungen abgerufen werden / Then steht in beiden Fällen „oberhalb 2000 m"; das mäßige Nassschnee-Problem mit abweichender Grenze zählt im ersten Fall nicht mit, weil es das Träger-Rating nicht trägt.
- [x] **AC-3:** [Höhe nur nach unten] Given das Bulletin `at_2026-04-10T08:00:00Z.json`, Region `CH-1246` (Rating erheblich; Nassschnee-Problem bis 2400 m; das mäßige/geringe Zweitproblem ab 2000 m trägt das Rating nicht) / When abgerufen wird / Then lautet die Höhe „unterhalb 2400 m", im gerenderten Text „… unterhalb 2400 m …".
- [x] **AC-4:** [Mehrdeutig ⇒ keine Höhe] Given das Bulletin `at_2026-03-01T17:30:00Z.json`, Region `CH-5112` (Rating mäßig; Altschnee ab 2000 m **und** Nassschnee bis 2200 m, beide mäßig) / When abgerufen wird / Then wird die Stufe 2 ohne jede Höhenangabe geliefert (weder „oberhalb 2000" noch „unterhalb 2200"); im gerenderten Text steht keine Höhe.
- [x] **AC-5:** [Keine Grenze vorhanden] Given (a) das Bulletin `at_2026-03-01T08:00:00Z.json`, Region `CH-8112` (Stufe 1, Gleitschnee mit `lowerBound 0`) und (b) das Bulletin `at_2026-04-10T08:00:00Z.json`, Region `CH-1311` (Träger-Rating erheblich „nachmittags", das tragende Nassschnee-Problem hat keine `elevation`) / When abgerufen wird / Then trägt keine der beiden Warnungen eine Höhe, und (b) trägt die Tageszeit „nachmittags".
- [x] **AC-6:** [Feinstufe im Modell] Given Ratings mit `subdivision` minus (`CH-7231`, 2026-03-01 Morgen), plus (`CH-5112`, 2026-01-15), neutral (`CH-1246`, 2026-03-01 Morgen) und ohne Feinstufe (Stufe 1, `CH-8112`) / When abgerufen wird / Then ist `level_modifier` „-", „+", `None`, `None` und die Ziffer (`native_level`) bleibt 3, 3, 2, 1.
- [x] **AC-7:** [S1 unverändert] Given die Auslösung der CAAML-Funktionen nach `caaml.py` / When die S1-Tests der Quelle avalanche.report laufen / Then bleiben sie unverändert grün — insbesondere liefert ein Rating mit eigener `elevation` weiter diese Höhe (die Höhe-aus-Problem-Regel greift nur ohne Rating-`elevation`), und `avalanche_report.py` enthält keine eigene Kopie der verschobenen Funktionen.
- [x] **AC-8:** [Gültigkeit, Abend- und Morgen-Ausgabe] Given die Abend-Ausgabe (`at_2026-03-02T06:00:00Z.json`, gültig bis 2026-03-02T16:00Z) / When um 2026-03-02T06:00Z abgerufen wird / Then gilt sie und liefert die Warnung; um 2026-03-02T17:00Z mit derselben (nun abgelaufenen) Antwort / Then ist das Ergebnis leer **ohne** Ausfallhinweis; und das Morgen-Update `at_2026-03-02T08:00:00Z.json` liefert um 08:00Z seine eigene Gültigkeit (07:00Z–16:00Z).
- [x] **AC-9:** [Leere Saison] Given die aufgezeichnete Antwort `leer.json` (HTTP 200, `{"bulletins":[]}`) / When ein Punkt in Graubünden abgefragt wird / Then ist das Ergebnis leer, `unavailable=False` (kein Ausfallhinweis), im Pro-Quelle-Journal steht die Quelle als erfolgreich beantwortet, und die leere Antwort wird höchstens 1800 s gecacht — 1801 s später löst der nächste Abruf eine neue Anfrage aus (ein neues Bulletin bleibt nicht 24 h unsichtbar).
- [x] **AC-10:** [Abruffehler] Given ein Netzfehler, HTTP 503, kaputtes JSON bzw. ein 200 ohne `bulletins`-Liste / When ein Punkt in Graubünden abgefragt wird / Then gilt die Quelle als nicht abrufbar (`unavailable=True`, da keine zweite Quelle zuständig ist), und der Ausfallhinweis erscheint im Trip-Briefing.
- [x] **AC-11:** [Ein Abruf für ganz CH] Given drei Punkte in verschiedenen Mikroregionen (Graubünden, Wallis, Berner Oberland) / When sie innerhalb des Cache-Zeitraums nacheinander abgefragt werden / Then entsteht genau ein HTTP-Abruf an `aws.slf.ch`, und jeder Punkt erhält die Warnung seiner Mikroregion.
- [x] **AC-12:** [Zuständigkeit per Polygon] Given Innsbruck (47.27 / 11.39), Bregenz/Vorarlberg (47.50 / 9.75), Aosta (45.74 / 7.32), Feldberg/Schwarzwald (47.87 / 8.00) sowie ein Punkt in `CH-7231` / When `covers()` bzw. die Registry befragt wird / Then ist SLF nur für den Schweizer Punkt zuständig; für die vier anderen Punkte findet kein Abruf statt und es entsteht kein Ausfallhinweis. Die Bestandstests `test_avalanche_report_ausfall_sichtbarkeit.py` (Tirol, Zell am See) bleiben grün, obwohl `slf_bulletin` in der Registry steht.
- [x] **AC-13:** [Mittelland, keine Ausschlussliste] Given ein Punkt in `CH-9211` (Zürich, 47.37 / 8.54), der im Bulletin `at_2026-03-01T08:00:00Z.json` nicht vorkommt / When abgefragt wird / Then ist das Ergebnis leer ohne Ausfallhinweis (Region nicht im Bulletin ⇒ „nicht zuständig", `mark_not_covered`). Given eine Mikroregion, die in `at_2026-02-10T08:00:00Z.json` bewertet ist und in `at_2025-12-20T08:00:00Z.json` nicht (der Test bestimmt sie aus den Fixtures) / Then liefert dieselbe Quelle sie im einen Bulletin und im anderen nicht — im Code steht keine feste Liste ausgeschlossener Regionen.
- [x] **AC-14:** [SLF-Ausfall im Mittelland] Given der SLF-Abruf schlägt fehl und der Punkt liegt in `CH-9211` (Zürich) / When die Warnungen mit Status abgefragt werden / Then ist das Verhalten dasselbe wie in Graubünden (AC-10): `unavailable=True` und der generische Ausfallhinweis erscheint, weil kein Kompensationspartner zuständig ist (Kompensationsregel `base.py` ab :199 greift erst ab zwei zuständigen Quellen). Der Test hält das als bekannte, ausdrücklich beschriebene Eigenschaft fest, damit sie nicht unbemerkt kippt.
- [x] **AC-15:** [Egress] Given der neue Host / When das Egress-Inventar in Python und Go geprüft wird / Then führen beide `aws.slf.ch` mit derselben Klassifikation wie `avalanche.report` (`BLOCKED`), kein weiterer neuer Host, und der Drift-Test ist grün; ein echter Abruf aus der Test-Umgebung wird blockiert.
- [x] **AC-16:** [Registry-Reihenfolge] Given die echte Standard-Registry / When die Quellen aufgelistet werden / Then heißt die Quelle `slf_bulletin`, steht unmittelbar nach `avalanche_report`, und beide liegen nach allen übrigen Quellen.
- [x] **AC-17:** [Abschaltbar mit einer Zeile] Given die Registry ohne die SLF-Registrierung (Zeile entfernt bzw. im Test entfernt) / When ein Punkt in Graubünden und ein Punkt in Tirol abgefragt werden und die Bestandssuite der Lawinenquellen läuft / Then entsteht keine SLF-Warnung, kein Abruf an `aws.slf.ch` und kein Ausfallhinweis, und kein anderer Test und keine andere Quelle ändert ihr Verhalten.
- [x] **AC-18:** [Quellenangabe, Link, Maßgeblichkeit] Given eine SLF-Warnung (`CH-7231`, 2026-03-01 Morgen) / When Trip-Briefing-Mail, Ortsvergleichs-Mail, eigenständige Warnungs-Mail und Telegram-Langform gerendert werden / Then enthält jeder dieser Texte „WSL-Institut für Schnee- und Lawinenforschung SLF", den Link `https://www.slf.ch/de/lawinenbulletin-und-schneesituation/` und den Satz „Maßgeblich ist der Originalbericht des SLF."; SMS, Premium-SMS und Telegram-Kurzform tragen keines der drei Elemente.
- [x] **AC-19:** [Feinstufe in der Mail] Given eine SLF-Warnung Stufe 3 mit Feinstufe minus, Höhe oberhalb 2000 m und Problem Altschnee / When Trip-Briefing-Mail, Ortsvergleichs-Mail und eigenständige Warnungs-Mail gerendert werden / Then lautet die Stufenzeile in allen drei „Lawinenstufe 3- (erheblich) oberhalb 2000 m · Altschnee" (Problemname wie im Namensverzeichnis des Renderers); bei Feinstufe neutral „Lawinenstufe 3 (erheblich)", bei plus „Lawinenstufe 3+ (erheblich)".
- [x] **AC-20:** [Feinstufe in Telegram] Given dieselbe Warnung / When die Telegram-Langform gerendert wird / Then steht dort „Lawinenstufe 3- (erheblich)" (Zeile und Kopfzeile „Lawinenstufe 3-"); die Telegram-Kurzform ist identisch zum SMS-Text (`AV3`, ohne Feinstufe).
- [x] **AC-21:** [SMS und Premium-SMS ohne Feinstufe] Given dieselbe Warnung (Stufe 3, Feinstufe minus) / When Briefing-SMS, Alarm-SMS und Premium-SMS gerendert werden / Then enthalten sie `AV3` (im Briefing-SMS-Block `!AV3`), niemals `AV3-`, „3-" oder einen Quellennamen, und genau ein `AV`-Token.
- [x] **AC-22:** [Alarm: vier Kanäle × zwei Flächen] Given eine Eskalation auf Stufe 4 in der Schweiz (abgeleitet aus `at_2026-03-01T08:00:00Z.json`, `CH-7231`) / When der Alarm im Trip-Alarm und im Ortsvergleich-Alarm versendet wird / Then kommt er in beiden Flächen über E-Mail, Telegram, SMS und Premium-SMS an — Premium-SMS ausdrücklich auch im Ortsvergleich — jeweils mit demselben Inhalt (Stufe, Region bzw. Ort, Höhe) in kanalgerechter Form; Stufe 5 würde dieselben Wege nehmen (`level=4` bleibt abgeleitet).
- [x] **AC-23:** [Ortsvergleich-Quellenfilter] Given ein Ortsvergleich mit einem Ort in Graubünden / When die Warnungen ohne `sources`-Filter, mit `sources=["slf_bulletin"]` und mit `sources=["meteoalarm"]` abgefragt werden / Then erscheint die SLF-Warnung im ersten und zweiten Fall und fehlt im dritten (Quellenname = Teil vor dem ersten „:").
- [x] **AC-24:** [Eskalation und Folgeausgabe] Given zuletzt gemeldete Stufe 3 und neue Stufe 4 (abgeleitet), dann Stufe 4 → 5 (abgeleitet), und die Abend-Ausgabe 2026-03-01 gefolgt vom Morgen-Update 2026-03-02 mit gleicher Stufe / When der Alarm-Lauf jeweils läuft / Then eskalieren 3 → 4 und 4 → 5 (Vergleich über `native_level`), und die Folgeausgabe mit gleicher Stufe in derselben Mikroregion löst **keinen** neuen Alarm aus (Identität = Mikroregion, nicht die wechselnde Bulletin-ID).
- [x] **AC-25:** [Zwei Nutzer] Given Nutzer A mit einem Trip in Graubünden (Winter-Fixture) und Nutzer B mit einem Trip in München / When für beide Trip-Briefing-Mail und -SMS erzeugt werden / Then enthält nur die von A den SLF-Bericht; die von B bleibt unverändert ohne Lagebericht und ohne Hinweis, und das Melde-Gedächtnis von A enthält keinen Eintrag von B und umgekehrt.
- [x] **AC-26:** [Absenkung ⇒ Entwarnung über vier Kanäle] Given im Melde-Gedächtnis steht die SLF-Warnung Stufe 4 (`source="slf_bulletin"`) und der aktuelle Lauf liefert bei gesunder Quelle Stufe 2 für dieselbe Mikroregion (abgeleitet aus `at_2026-03-01T08:00:00Z.json`) / When der Alarm-Lauf läuft / Then erhält der Nutzer genau eine Entwarnung „Stufe 4 → 2" (SMS `+AV4>2`) über E-Mail, Telegram, SMS und Premium-SMS (Dringlichkeit des alten Werts), die Mail nennt als Quelle das SLF, und das Gedächtnis steht danach auf 2.
- [x] **AC-27:** [Feinstufenwechsel ist keine Entwarnung] Given gemeldete Stufe 3 mit Feinstufe plus und ein Folgelauf mit Stufe 3 und Feinstufe minus (und umgekehrt) / When der Alarm-Lauf läuft / Then entsteht weder eine Entwarnung noch ein neuer Alarm, und das Gedächtnis bleibt bei Stufe 3.
- [x] **AC-28:** [Quellenwechsel AT↔CH ist keine Entwarnung] Given im Melde-Gedächtnis steht eine Warnung der Quelle `avalanche_report` (AT) für einen Ort-Schlüssel und der Lauf liefert für denselben Schlüssel (Koordinate jetzt in der Schweiz) eine Warnung der Quelle `slf_bulletin` / When der Alarm-Lauf läuft / Then wird die frühere AT-Warnung nicht als „gesenkt" oder „beendet" gemeldet (die AT-Quelle antwortet dort „nicht zuständig", nicht gesund), und die SLF-Warnung wird nach den gewöhnlichen Regeln für neue Warnungen behandelt.
- [x] **AC-29:** [Ausfall, leere Saison und verschwundene Region sind keine Entwarnung] Given gemeldete SLF-Stufe 3 / When der nächste Lauf (a) einen SLF-Abruffehler hat, (b) die leere Saison-Antwort `{"bulletins":[]}` erhält, (c) die Region im Bulletin nicht mehr findet, jeweils zwei Läufe hintereinander / Then entsteht in keinem der drei Fälle eine Entwarnung („gesenkt" oder „beendet"), und das Gedächtnis bleibt unverändert.
- [x] **AC-30:** [Mail-Validator kennt Feinstufe und SLF] Given eine SLF-Warnungs-Mail mit „Lawinenstufe 3- (erheblich)" und Quelle SLF / When `official_alert_mail_validator.py` sie prüft / Then wird sie als Lawinenmail erkannt und besteht (Exit 0); „Lawinenstufe 3- (mäßig)" bleibt ein Fehler (Ziffer und EAWS-Wort müssen zusammenpassen), und eine Mail ohne Quelle bleibt ein Fehler.
- [x] **AC-31:** [Doku] Given die Umsetzung / When sie abgeschlossen ist / Then enthalten `docs/specs/data_sources.md` den Antrag #7 samt Auflagen und Version 1.4, `docs/adr/` das ADR-0091 mit Index-Eintrag (ADR-0089 verweist darauf), `docs/specs/modules/avalanche_report_bulletin.md` den Verweis auf diese Spec statt „Slice 2", und `docs/artifacts/feat-1441-s3-slf/anfrage_slf_entwurf.md` den Entwurf der Anfrage.

## Dialog

### Runde 1
**Adversary:**
Testlauf (-v -rA, Artefakt docs/artifacts/feat-1441-s3-slf/adversary-test-output.txt): 147 passed. Bestand (adversary-test-output-bestand.txt): 304 passed. Go-Test des Egress-Pakets: ok. Alle 31 ACs und die drei Expected-Behavior-Punkte gegen den Code gelesen (Confirmations unten) und rund 40 Mutationen per String-Ersetzung gefahren (externe Sicherung ausserhalb des Repos; nach jeder Mutation Wiederherstellung per Dateivergleich; am Ende Arbeitsbaum-Status und Diff-Statistik identisch zum Anfangsstand).

Confirmation: AC-1, AC-2, AC-3, AC-4, AC-5
  Code reference: src/services/official_alerts/caaml.py:64
  Evidence: `elevation_from_problems` nimmt nur Probleme mit `dangerRatingValue == Traeger-Stufe` und passender Tageszeit; `len(bounds) != 1` (caaml.py:75) liefert bei mehrdeutigen/fehlenden Grenzen keine Hoehe; `lowerBound 0` wird in `_problem_bound` verworfen. Mutation 2 (`< 1` statt `!= 1`) und 3 (`lowerBound 0` zaehlt) wurden von AC-2/AC-4/AC-5a-Tests rot gezogen.
  Status: CONFIRMED

Confirmation: AC-1, AC-6, AC-7
  Code reference: src/services/official_alerts/caaml.py:181
  Evidence: `level_modifier=_level_modifier(rating)` am Traeger-Rating; `native_level` bleibt die Ziffer. src/services/official_alerts/avalanche_report.py:31 importiert nur noch aus caaml.py (keine Kopie); S1-Bestand 304 passed. Mutation Vorzeichen vertauscht (minus/plus) -> AC-6-Tests rot.
  Status: CONFIRMED

Confirmation: AC-8, AC-9, AC-10, AC-11, AC-13, AC-14
  Code reference: src/services/official_alerts/slf.py:88
  Evidence: `_candidates` holt EIN Dokument (`cache_key="CH"`), filtert `valid_to >= now`, ruft bei leerer Antwort/unbewerteter Region `mark_not_covered()`. Mutation 6 (leere Saison als fetch_incomplete) -> AC-9 rot; Mutation 7 (24-h-TTL) -> `test_ac9_leere_antwort_bleibt_hoechstens_1800_sekunden_im_cache` rot; Gueltigkeitsfilter entfernt -> AC-8 rot; `mark_not_covered` entfernt -> AC-9/13/29 rot; Cache-Key je Punkt -> AC-11 rot; `bulletins`-Pruefung entfernt -> AC-10 `ohne-bulletins` rot.
  Status: CONFIRMED

Confirmation: AC-12, AC-17
  Code reference: src/services/official_alerts/slf.py:72
  Evidence: `covers()` = Polygon ueber `RegionMapper.regions_at`. Mutation 1 (BBox 45.8-47.9 / 5.9-10.6) -> `test_ac12_covers_ist_nur_fuer_den_schweizer_punkt_wahr` rot. Registrierungszeile entfernt: Bestand (22 Dateien) gruen, nur die SLF-Tests (AC-12/16/17) werden rot -> die Quelle ist mit einer Zeile abschaltbar, ohne Fremdwirkung.
  Status: CONFIRMED

Confirmation: AC-15
  Code reference: internal/egress/inventory.go:45
  Evidence: `"aws.slf.ch": Blocked` und src/app/egress_guard.py:57 `IsolationKind.BLOCKED`. Python-Eintrag entfernt, Go-Eintrag entfernt, Python auf TEST_ACCESS -> jeweils `test_egress_inventory_drift.py::test_inventories_are_identical` rot (Go-Seite nur dort, das genuegt: Gleichheit beider Listen).
  Status: CONFIRMED

Confirmation: AC-16
  Code reference: src/services/official_alerts/__init__.py:61
  Evidence: Registrierung direkt nach `AvalancheReportSource()`. Reihenfolge getauscht -> `test_ac16_slf_steht_unmittelbar_nach_avalanche_report_am_ende_der_registry` rot; SLF vor Dpc einsortiert -> beide AC-16-Tests rot.
  Status: CONFIRMED

Confirmation: AC-18, AC-19, AC-20, AC-21
  Code reference: src/output/renderers/alert/official_alerts.py:174
  Evidence: Feinstufe nur in `avalanche_bulletin_text` (Mail, Telegram-Zeile) und Telegram-Kopf (official_alerts.py:2043); Quellenlabel-Praefixaufloesung official_alerts.py:202, Massgeblichkeitssatz official_alerts.py:214. Mutationen: Feinstufe aus Mail entfernt (5) -> ueber 40 Tests rot (AC-19/20/22); Feinstufe im Briefing-SMS-Token (4) -> AC-21-Briefing + AC-25 rot; Feinstufe im Alarm-SMS/Premium-Token (4b, official_alerts.py:2238) -> `test_ac21_alarm_sms_und_premium_sms_...` + AC-20-Kurzform rot (zwei getrennte Token-Pfade, beide bewacht); Massgeblichkeit aus Telegram (11) -> AC-18 rot; nur HTML bzw. nur Klartext der Mail (20, 21) -> AC-18 rot; Telegram-Kopf ohne Feinstufe -> AC-20 rot; Praefix-Label entfernt -> AC-18/25/30 rot.
  Status: CONFIRMED

Confirmation: AC-22, AC-23, AC-24, AC-25
  Code reference: src/output/renderers/alert/official_alerts.py:637
  Evidence: Eskalation `_rank(alert) > kandidat_level` -> `comparable_level` -> `native_level` (src/services/official_alerts/models.py:63). Mutation 9 (`return alert.level`) und 9b (nur im Renderer-Verdict) -> AC-24 (4 auf 5) und AC-22 Stufe 5 rot. Quellenfilter exakt statt Praefix (src/services/compare_official_alert.py:444) -> AC-23 rot.
  Status: CONFIRMED

Confirmation: AC-26, AC-27, AC-28, AC-29
  Code reference: src/services/official_alert_allclear.py:154
  Evidence: Absenkung nur ueber `comparable_level`. Mutation 10 (minus-Feinstufe = Absenkung) -> AC-27[3plus-zu-3minus] + AC-28 rot; 10d (plus = Absenkung) -> AC-27[3minus-zu-3plus] rot; 10c' (Feinstufe als Eskalation, official_alerts.py:637) -> AC-27[3minus-zu-3plus] rot. (Ein erster Versuch 10c am toten `_exact_match_verdict` blieb gruen -- falscher Mutationsort, kein Befund.)
  Status: CONFIRMED

Confirmation: AC-30
  Code reference: .claude/hooks/official_alert_mail_validator.py:68
  Evidence: Regex `([1-5])[-+]?`; Regex ohne `[-+]?` -> AC-30 (gueltig + falsches Wort) rot; `is_avalanche` fest False (Zeile 260) -> AC-30 gueltig rot; Markentupel auf `("avalanche.report",)` -> AC-30 gueltig rot. Abweichung 2 (Validator, 3 Zeilen) ist inhaltlich korrekt und eng.
  Status: CONFIRMED

Confirmation: AC-31
  Code reference: src/services/official_alerts/data/README.md:1
  Evidence: `tests/test_slf_bulletin_docs.py` im Lauf gruen (# doc-compliance-test, Dokukonformitaet, kein Verhaltensnachweis); `tests/test_adr_index_drift.py` gruen im Bestand.
  Status: CONFIRMED

Confirmation: Input / Output / Side effects
  Code reference: src/services/official_alerts/models.py:60
  Evidence: Ein Dokument je Cache-Zeitraum (AC-11), genau ein Alert je Punkt (slf.py:120), Journal ueber `collect_source_queries` (AC-9), Feld `level_modifier` mit Default None; Vergleiche nutzen nur `native_level`.
  Status: CONFIRMED

Bewertung bekannte Abweichung 1 (Diff gegen HEAD in tests/): Die 7 geaenderten Zeilen in tests/test_slf_bulletin_kanaele.py ergaenzen nur die Feinstufe, die die Fixtures wirklich tragen (CH-5112 Abend 2026-03-01: `subdivision: plus`, per Skript nachgemessen; CH-7231 minus; abgeleitete Varianten 4/5 erben minus, weil `derive` die Feinstufe nicht aendert). Die Erwartung wird schaerfer (Substring "2+ (mäßig)" statt "2 (mäßig)"), nicht schwaecher; sie entspricht Spec Abschnitt 6. Kein verwaessernder Eingriff. Mutation 5 und 26 zeigen, dass diese Literale tatsaechlich wirken. Bewertung: korrekt.
Bewertung bekannte Abweichung 2 (Validator): Regex `[-+]?` und Marken-Tupel sind das Minimum fuer AC-30. Mutation: Regex ohne `[-+]?` rot; Tupel auf nur avalanche.report rot. Zwei Restluecken siehe F004.

Findings:
Finding F001
  ID: F001
  Severity: MEDIUM
  Category: edge_case
  Code reference: src/services/official_alerts/caaml.py:181
  Description: `level_modifier=_level_modifier(rating)` liest die Feinstufe vom Traeger-Rating. Mutation 27 (`rated[0][1]`, erstes Rating statt Traeger) laesst alle 147 Tests gruen. Das ist kein theoretischer Fall: in at_2026-04-10T08:00:00Z.json, Region CH-4242, hat das erste Rating Feinstufe "-", das Traeger-Rating "neutral" (per Skript ueber 61 Fixture-Bulletins gemessen: 1 Abweichung).
  Spec requirement: AC-6 / Implementation Details 6 — Feinstufe des Traeger-Ratings.
  Conflict: Die Zusicherung "Feinstufe stammt vom Traeger" ist an keiner Stelle geprueft; eine Verfaelschung wuerde im Briefing "Stufe 3-" statt "Stufe 3" ausgeben (Haftung: Stufenwortlaut).
  Remediation: Parser-Test mit dem Aprilbulletin CH-4242: `level_modifier is None` (Traeger neutral).

Finding F002
  ID: F002
  Severity: LOW
  Category: anti_pattern
  Code reference: src/services/official_alerts/slf.py:112
  Description: fail-soft in `SlfSource.fetch` (try/except -> `mark_fetch_incomplete`, `[]`). Mutation "except: raise" bleibt gruen. Ein Bulletin mit kaputter Struktur (z. B. `elevation` als String) liefert real `[]` (per Skript belegt), aber kein Test erzwingt, dass das ueber diesen Pfad als Ausfall endet.
  Spec requirement: Implementation Details 2 — nicht abrufbar = fetch_failed; Docstring "Wirft nie".
  Conflict: Die Mutationsfamilie "fail-soft -> werfen" wird nicht gefangen.
  Remediation: Test mit abgeleiteter Variante (Rating `elevation: "kaputt"`), Erwartung `unavailable=True`, kein Raise.

Finding F003
  ID: F003
  Severity: LOW
  Category: edge_case
  Code reference: src/services/official_alerts/slf.py:120
  Description: Auswahl "hoechste Stufe, Gleichstand kleinste ID". Mutation auf "niedrigste Stufe" bleibt gruen. Ein Punkt liegt nur auf Polygongrenzen in mehreren Regionen (alle 135 Innenpunkte: genau eine Region), daher praktisch nur dort relevant.
  Spec requirement: Purpose — genau ein Alert je Punkt, Stufe woertlich.
  Conflict: Ein Randpunkt zweier Regionen koennte die niedrigere Stufe melden, ohne dass ein Test rot wird (identische Logik wie S1 avalanche_report.py:161).
  Remediation: Test mit abgeleitetem Doppeltreffer oder Sammel-Eintrag #1199.

Finding F004
  ID: F004
  Severity: LOW
  Category: anti_pattern
  Code reference: .claude/hooks/official_alert_mail_validator.py:71
  Description: Marker-Tupel `_AVALANCHE_SOURCE_MARKS`. Einzelner SLF-Marker entfernt (Label oder `slf.ch`) und Tupel um `""` erweitert (jede Mail waere "Lawinenmail") bleiben gruen. Ersteres ist Redundanz (Mail traegt beide), zweiteres heisst: keine Gegenprobe "Lawinenstufe-Text ohne jede Quelle faellt an S-2" (Luecke schon aus S1).
  Spec requirement: AC-30 — Mail ohne Quelle bleibt Fehler.
  Conflict: Fehler wird nur ueber S-1b/P-4 gefangen, nicht ueber die Erkennung; zu lockere Erkennung unbewacht.
  Remediation: Sammel-Eintrag #1199 (Validator-Test: Lawinenstufe-Text ohne Marker und ohne Leiter faellt an S-2).

Finding F005
  ID: F005
  Severity: LOW
  Category: spec_violation
  Code reference: src/output/renderers/email/compare_html.py:892
  Description: Die Ortsvergleichs-Kopfzeile `count_line = f"Lawinenstufe {stufe} · Ort"` nennt die Ziffer ohne Feinstufe, die Stufenzeile im Detail zeigt "3-". Kein Test prueft die Kopfzeile mit Feinstufe.
  Spec requirement: AC-19 — "Stufenzeile in allen drei"; die Spec nennt die Uebersichtszeile nicht.
  Conflict: Uneinheitliche Darstellung in derselben Mail (Kopf "3", Detail "3-"); ob gewollt, ist aus der Spec nicht entscheidbar.
  Remediation: PO-/Spec-Entscheid; sonst Sammel-Eintrag #1199.

**Implementierer:**
F001 behoben: neuer Test `test_ac6_feinstufe_kommt_vom_traeger_rating_nicht_vom_ersten_rating` (CH-4242, 2026-04-10, level_modifier None, native_level 3). F002-F005 gehen als Sammel-Eintraege an den Aufrufer.

### Runde 2
**Adversary:**
Zweite Runde, gezielte Nachfassung statt Wiederholung: (a) Falsche Mutationsorte ausgeschlossen -- Mutation 10c am `_exact_match_verdict` blieb gruen, weil der Pfad bei vorhandenem Zeitraum nie erreicht wird (official_alerts.py:577); Wiederholung am lebenden Pfad (official_alerts.py:637) wurde von AC-27[3minus-zu-3plus] gefangen. (b) Alle 12 Pflicht-Mutationen der Spec liegen rot: 1 (AC-12), 2 (AC-4), 3 (AC-5), 4 (AC-21), 5 (AC-19), 6 (AC-9), 7 (AC-9), 8 (AC-16), 9 (AC-24), 10 (AC-27), 11 (AC-18), 12 (AC-13; fuer die Ausschlussliste ist der Quelltext-Scan der einzige Waechter, da Zuerich funktional ohnehin leer ist -- Tupel und Konstante beide gefangen). (c) Zusaetzlich gefangen: Quellenfilter-Praefix (AC-23), Cache-Key (AC-11), problem_elevation aus (AC-1..3), Egress-Inventar Python/Go/Kind (AC-15), Registrierung entfernt (Bestand gruen, nur SLF-Tests rot). (d) Nicht gefangen: Mutation 27 (F001), fail-soft zu raise (F002), niedrigste Stufe (F003), Marker-Lockerung (F004); `problem_elevation` Default True fuer S1 bleibt gruen, weil S1-Fixtures ein Rating-`elevation` tragen (Regel dort wirkungslos; Hinweis, kein Befund). (e) Wirkort-Frage: Briefing-SMS und Alarm-/Premium-SMS laufen ueber zwei getrennte Token-Pfade (official_alerts.py:464 und :2238); beide einzeln mutiert und gefangen. Der Quellenfilter wirkt im echten Pfad (compare_official_alert.py:444), die Registrierung wurde am echten Registry-Aufruf geprueft. Kein Test ist nur wegen eines Fehlers gruen: die geaenderten Erwartungsliterale (Abweichung 1) sind strenger als zuvor.
**Implementierer:**
(keine Rueckfrage offen; Entscheid ueber F001-F005 beim Aufrufer)

## Herkunft der Vorbedingungen

kein Sprachprofil konfiguriert (`precondition_origins.default_lang`)

## Verdict

**Nachpruefung F001 (Adversary):** BEHOBEN.
  Code reference: tests/test_slf_bulletin_parser.py:184
  Evidence: Mutation 27 (`level_modifier=_level_modifier(rated[0][1])` in src/services/official_alerts/caaml.py:181) wird jetzt von `test_ac6_feinstufe_kommt_vom_traeger_rating_nicht_vom_ersten_rating` rot gezogen (einziger roter Test); nach Wiederherstellung per Dateivergleich identisch. Neuer Lauf der sechs Testdateien: 148 passed.

VERDICT: HOLDS (Tri-State-Wort: VERIFIED)
Tests: 148 passed (neue Suiten), 304 passed (Bestand), Go egress ok, 0 failed.
Pflicht-Mutationen 1-12: alle von mindestens einem Test gefangen. Mutation 27 nach Nachbesserung ebenfalls. Offen: F002-F004 (LOW, nicht gefangene Mutationen) und Beobachtung F005 (LOW).
Regressions: keine gefunden. Checklist: 34/34 Punkte (3 Expected Behavior + 31 ACs) bewiesen.
Empfehlung: F001 geschlossen; F002-F005 als Sammel-Eintraege (#1199).

## Geprüfte Dateien

- sha256:46228d6ea85da9f367919e68b0f4d091934b5cf55efbc0d25d996d3220203e86  .claude/hooks/official_alert_mail_validator.py
- sha256:6c8d0219cde1aa6d08d83004b7bf9caf891e9b63e396b80274530872f8778fba  internal/egress/inventory.go
- sha256:9adc393f825f7ceec36cc2f82422e7b089366396332b6df4aa2ee7cb36aa1933  src/output/renderers/alert/official_alerts.py
- sha256:9a90fac4c5878bf77f636297c123e4ee75eeeeb7ec17752820dafcb5538a7661  src/output/renderers/email/compare_html.py
- sha256:c5feb54c642c7799f37ffe9ff4b3d3f971d0826d779490535650b53498c00fdd  src/services/official_alert_allclear.py
- sha256:eeab9414f6a41d8593dbe03ef7f0680402b8bca7e899858d2f69760b53de3ced  src/services/official_alerts/__init__.py
- sha256:775c5f00ef0c99f0eeca8a836d8b4f049fea4731fd10c748fd58acd5839116df  src/services/official_alerts/caaml.py
- sha256:63127118d2370338d8d3b7569ac58386136b674b63c2572bf9326a2f3b8c0697  src/services/official_alerts/data/README.md
- sha256:f129323b96482e7754ec8adeadbaa7b117ec3c497df54cee377d55394494d783  src/services/official_alerts/models.py
- sha256:e9aa4485fc2c86b32bf8c698f96ed2b97131c4177970fe143abcb49081b2d6b4  src/services/official_alerts/slf.py
- sha256:e1ea57fee56ee2fd2c91a455cacedd05e298702573181d7d5af301c8911ffb19  tests/test_slf_bulletin_parser.py

## Prüfbasis

- base: 6fafebf3e690349232bb35d9d0d1ebb819198cec
- blob:acf8205ff034074767ca1955d2bab305a1d90958  .claude/hooks/official_alert_mail_validator.py
- blob:7afb7acf55c951d126ecf146d96c820aeac2141c  internal/egress/inventory.go
- blob:c71274ac89f6891cd7b47de8268b44f49a6988cf  src/output/renderers/alert/official_alerts.py
- blob:1f159d5bd69ffb17a23b8bd1f7ee603c8caba109  src/output/renderers/email/compare_html.py
- blob:a97a9137951fc838f63a2a8e68018221e5bf8947  src/services/official_alert_allclear.py
- blob:9ea537a76e47ee9d8a095efcdefd255e66cc3291  src/services/official_alerts/__init__.py
- blob:b2b731f4ae78ec5414ef1a389fb860f6d4f0adb8  src/services/official_alerts/caaml.py
- blob:ca8751070b7a3ac3c8112c06617057334ad05bca  src/services/official_alerts/data/README.md
- blob:fb2cea2e9c26b22527ca12eeecc33fb14d262746  src/services/official_alerts/models.py
- blob:c4eec3a8b332842d95c684972ac2bcf4f8d874c1  src/services/official_alerts/slf.py
- blob:e6cc6e2c8c98cbc2dd91dfd14945e6003419bd49  tests/test_slf_bulletin_parser.py
