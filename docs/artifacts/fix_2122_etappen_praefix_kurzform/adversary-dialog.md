# Adversary-Dialog — Fix #2122: Etappen-Praefix in der Alarm-Kurzform

Rolle: Adversary Validation Agent. Branch `fix-2122-etappen-praefix-kurzform`,
HEAD `6c8c16a4`. Spec: `docs/specs/modules/fix_2122_etappen_praefix_kurzform.md`
(12 ACs, PO-freigegeben). Waechter: `tests/tdd/test_alert_etappen_praefix_kurzform.py`.

## Runde 1 — Testlauf + Regressionsfeger

`uv run pytest tests/tdd/test_alert_etappen_praefix_kurzform.py -v` -> **11/11 gruen**.

Regressionsfeger (123 Testdateien, alle Aufrufer von `render_sms`, `to_alert_message`,
`to_corridor_events`, `to_multi_point_alert_message`, `build_official_alert_notices`,
`render_official_alert_sms`, `RadarAlertRequest`, `send_deviation_alert`,
`send_radar_alert`, `send_official_alert`) lief mit explizit benannten Dateien.

Ergebnis: **1 FAILED** von ~950 Tests im Feger —
`tests/test_output_timezone_guard.py::test_no_unlisted_output_timezone_violations`.
Dieser Test existierte VOR #2122 unveraendert (kein Diff gegen `origin/main`) und
war dort gruen. Die PR fuegt zwei neue `date.today()`-Aufrufe ein
(`notification_service.py:813`, `:1030`), die der Waechter als `ambient_clock`
(Issue #1402) einstuft. Siehe F001.

## Runde 2 — Mutations-Gegenprobe (AC-12, Pflicht)

Alle Mutationen per String-Ersetzung (Python-Skript), externe Sicherungskopie in
`/tmp/.../scratchpad/backup/*.orig` VOR jeder Mutation, Rueckname und
Byte-Identitaet per Diff NACH jeder Mutation geprueft. Kein `git checkout`/
`stash`/`reset` verwendet.

| # | Mutation | Datei:Zeile | Rote Tests | Bewertung |
|---|---|---|---|---|
| M1 | `_stage_prefix()` gibt IMMER `""` zurueck | render.py:220-249 | AC-1..AC-11, alle 11 | Global bewacht |
| M2 | Praefix NUR im Korridor-Zweig entfernt | render.py:1649 | nur AC-4 (1/11) | Zweigspezifisch bewacht |
| M3 | `_stage_number_for_date()` gibt IMMER `1` zurueck | notification_service.py:390-397 | AC-1,2,3,4,5,6,11 (7/11) | Bildungsstelle bewacht |
| M4 | Radar-Pfad: `request.segment_date` durch `date.today()` ersetzt | notification_service.py:1453 | nur AC-6 (1/11) | Exakt bewacht |
| M5 | Aggregation nennt bei mehreren Etappen nur die erste | render.py:245-249 | AC-7, AC-8 (2/11) | Bewacht |
| M6 | Fehlende Etappe wird uebersprungen statt Praefix zu unterdruecken | render.py:234-241 | nur AC-8 (1/11) | Exakt bewacht |
| M7 | Ortsvergleich-Pfad setzt faelschlich `stage_number=1` | project.py:508-514 | nur AC-9 (1/11) | Exakt bewacht |
| M8 | Reale Aufrufstelle `trip_alert.py` gibt `segment_date` nicht mehr weiter | trip_alert.py:2220-2227 | **0 von 23+ gepruefte Tests** | **UNBEWACHT -> F003** |

Alle Mutationen nach Pruefung zurueckgenommen; `git status --porcelain` /
`git diff --stat origin/main` zeigen danach denselben Stand wie zu Beginn
(nur die zwei projektfremden untracked Testdateien).

## Findings

### F001 — CRITICAL — Regression im Kern-Testlauf (Issue #1402 Waechter)

- Severity: CRITICAL
- Category: regression
- Code reference: `src/services/notification_service.py:813`, `src/services/notification_service.py:1030`
- Description: Beide neuen Zeilen rufen `date.today()` direkt auf (Wanduhr ohne
  Ortsbezug) statt eines `utils.timezone`-Helfers (`local_dt`/`trip_local_today`),
  wie er im selben Modul-Umfeld bereits verwendet wird (`trip_alert.py` nutzt
  `trip_local_today(trip, now_utc)`).
- Spec requirement: CLAUDE.md "Test-Politik" — Kern-Schicht MUSS 100% gruen
  sein. `tests/test_output_timezone_guard.py` ist ein bestehender, ungeaenderter
  Kern-Test (Issue #1402).
- Conflict: `uv run pytest tests/test_output_timezone_guard.py -q` -> Exit 1,
  `test_no_unlisted_output_timezone_violations` FAILED mit
  `[('src/services/notification_service.py::send_deviation_alert::0', 'ambient_clock'), ('src/services/notification_service.py::send_official_alert::0', 'ambient_clock')]`.
  Verifiziert: `git diff origin/main -- tests/test_output_timezone_guard.py` ist
  leer, der Waechter war auf `origin/main` gruen — echter neuer Rueckfall.
- Remediation: `date.today()` durch eine ortsbezogene Ableitung ersetzen
  (z.B. `trip_local_today(trip, now_utc)`) oder bewusst mit Begruendung in
  `KNOWN_VIOLATIONS` eintragen.

### F002 — HIGH — Amtliche Warnung kann die FALSCHE Etappen-Nummer zeigen (veralteter Anker)

- Severity: HIGH
- Category: edge_case
- Code reference: `src/services/notification_service.py:1017-1030`
  (`send_official_alert`), `src/services/weather_snapshot.py:317-328`
  (`alarm_anchor_target_date`, KEINE Alters-/Tagespruefung)
- Description: `send_official_alert` waehlt den `stage_number`-Datumsanker ueber
  `for channel in sorted(effective_channels): anchor_date =
  snap_svc.alarm_anchor_target_date(...); if anchor_date is not None: break` —
  identisch zum bewusst NICHT tagesgebundenen Geometrie-Rueckfall aus
  `trip_alert.py:1071-1079` (dort korrekt, weil nur Routen-Geometrie gebraucht
  wird). #2122 missbraucht denselben Wert jetzt als Datumsquelle fuer die
  Etappen-Nummer, die SEHR WOHL vom Tag abhaengt.
- Spec requirement: AC-5 — Praefix des Tages, dem der TATSAECHLICH verwendete
  Anker entstammt; Purpose-Abschnitt: Praefix soll bei verzoegertem
  Satelliten-Empfang die Zuordnung zur richtigen Etappe ermoeglichen.
- Conflict: Reproduziert per isoliertem Aufruf von `_stage_number_for_date`
  (Trip: heute = 3. von 5 Etappen):
  ```
  stage for today: 3
  stage for anchor 4d old (ausserhalb des Trip-Datumsbereichs): None
  stage for anchor 2d old (= Datum der 1. Etappe): 1
  ```
  Bei einem 2 Tage alten, aber noch gueltigen Anker liefert die Ableitung
  Stage 1 statt der tatsaechlich aktuellen Stage 3 — die amtliche Warnung
  traegt `S1` statt `S3`, obwohl `build_official_alert_notices` die Segmente
  nach `end_time < now_utc` filtert, nicht nach Anker-Datum. Genau dieses
  Szenario (Anker mehrere Tage nicht aktualisiert, aber fuer Geometrie
  weiterverwendet) ist im Docstring von `trip_alert.py:1004-1016` als realer
  Produktivfall dokumentiert ("~16 h blinde Wache" bei ausgefallenem
  Abend-Briefing). AC-5s eigener Test deckt nur den Idealfall ab (Anker fuer
  alle vier Kanaele frisch auf `date.today()`).
- Remediation: Fuer die Etappen-Ableitung entweder denselben Alters-/Tages-
  Filter wie `_kanal_anker_kandidat` anwenden (verwerfen -> `today`-Fallback),
  oder die Etappen-Nummer aus den tatsaechlich betroffenen Segment-IDs der
  Warnung ableiten statt aus dem Anker-Metadatum.

### F003 — HIGH — Reale Aufrufstelle fuer `segment_date` im Radar-Pfad ist UNBEWACHT

- Severity: HIGH
- Category: edge_case (Testabdeckungs-Luecke, Mutations-Gegenprobe AC-12)
- Code reference: `src/services/trip_alert.py:2220-2227` (Stelle, an der
  `RadarAlertRequest(..., segment_date=segment_date, ...)` im ECHTEN
  Ausloesepfad gebaut wird)
- Description: Mutation M8 entfernte genau diese eine Zeile (Weiterreichung
  von `segment_date` an der realen Konstruktionsstelle). Danach blieben ALLE
  gepruefte Tests gruen: die 11 Tests der Spec-Testdatei, plus
  `test_issue_919_radar_alert_canonical.py`, `test_radar_alert_telegram_style.py`
  sowie 7 weitere Onset-/Nowcast-/Compare-Radar-Testdateien (ueber 100
  Einzeltests) — 0 rot.
- Spec requirement: AC-12 — "wird fuer JEDE der fuenf Alarmarten mindestens
  ein Test rot". Team-Lead-Auftrag: "Ist die Zusicherung an der Stelle
  geprueft, an der sie WIRKT — oder nur dort, wo der Code steht?"
- Conflict: AC-2/AC-6 (Radar-Alarm) werden in
  `test_alert_etappen_praefix_kurzform.py` AUSSCHLIESSLICH ueber direkt
  handgebaute `RadarAlertRequest(..., segment_date=...)`-Objekte geprueft, die
  `NotificationService.send_radar_alert()` DIREKT aufrufen. Der reale
  Ausloesepfad (`TripAlertService.check_and_send_alerts` ->
  `_resolve_alert_segment` -> Bau von `RadarAlertRequest` in `trip_alert.py`)
  wird von KEINEM Test durchlaufen, der das Etappen-Praefix im Ergebnis
  prueft. Die Zusicherung ist nur an der KONSUMIERENDEN Stelle
  (`notification_service.py`) bewacht, nicht an der WIRKENDEN Stelle
  (`trip_alert.py`), wo `segment_date` erstmals einen realen Wert erhaelt.
- Remediation: Mindestens ein Test, der den REALEN Radar-Ausloesepfad
  end-to-end durchlaeuft (`TripAlertService`, kein direkt konstruiertes
  `RadarAlertRequest`) und das gerenderte Etappen-Praefix im zugestellten Text
  prueft — analog zu AC-1s Naht-Test fuer den Abweichungs-Alarm, der den
  echten Pfad nutzt und deshalb M3 faengt.

## AC-Abdeckung

| AC | Status | Beleg |
|---|---|---|
| AC-1 | CONFIRMED | M3 (7/11 rot inkl. AC-1), echter Ausloesepfad `send_deviation_alert` |
| AC-2 | CONFIRMED (Rendering) / siehe F003 (Wirkort ungetestet) | M3 faengt AC-2; M8 faengt AC-2 NICHT |
| AC-3 | CONFIRMED | M1 |
| AC-4 | CONFIRMED | M1, M2 (zweigspezifisch) |
| AC-5 | CONFIRMED (Idealfall) / siehe F002 (Staleness-Luecke) | M1; Reproduktionsskript zeigt falschen Wert bei veraltetem Anker |
| AC-6 | CONFIRMED (Rendering) / siehe F003 (Wirkort ungetestet) | M4 faengt AC-6 exakt; M8 faengt es NICHT |
| AC-7 | CONFIRMED | M5 |
| AC-8 | CONFIRMED | M6 |
| AC-9 | CONFIRMED | M7 |
| AC-10 | CONFIRMED | Laengenanalyse `render.py:1780-1794`: `body[:limit]` schneidet nur vom ENDE, Praefix steht am ANFANG von `head` — ueberlebt strukturell jede Kuerzung im Produktivpfad (`limit=140`) |
| AC-11 | CONFIRMED | Test misst SMS/Premium-SMS/Telegram direkt aus einem Aufruf, M1 faengt alle drei |
| AC-12 | TEILWEISE WIDERLEGT | M1-M7 (Rendering/Ableitung) vollstaendig bewacht; M8 (reale Aufrufstelle Radar-Pfad) NICHT bewacht -> F003 |

## Regressions-Invarianz (AC-8/AC-9, "byte-identisch")

`test_ac8_...` und `test_ac9_...` fixieren den gemessenen PRE-FIX-Bestandstext
(`'Seg 1-2: G30->80@11 G30->80@11'` bzw. `'2:+R45 1:+R30'`) und pruefen sowohl
das Ausbleiben des Praefix als auch das Erscheinen bei gesetzter Etappe
(Positivkontrolle im selben Testkoerper) — keine tote Pruefung.

## Verdict

===============================================
**VERDICT: BROKEN**
===============================================

Finding F001: neue `date.today()`-Aufrufe (`notification_service.py:813,1030`)
lassen den bestehenden, unveraenderten Kern-Test
`tests/test_output_timezone_guard.py::test_no_unlisted_output_timezone_violations`
rot werden (Exit 1) — echte Regression, kein "vorbestehend rot".
  Severity: CRITICAL

Finding F002: `send_official_alert` leitet die Etappen-Nummer aus einem
Anker-Datum ab, das bewusst OHNE Alters-/Tagespruefung gewaehlt wird — bei
einem mehrere Tage alten, aber noch gueltigen Anker zeigt die amtliche Warnung
nachweislich die FALSCHE Etappen-Nummer (reproduziert: S1 statt S3).
  Severity: HIGH

Finding F003: die reale Verdrahtungsstelle von `segment_date` im
Radar-Ausloesepfad (`trip_alert.py:2220-2227`) ist durch KEINEN Test bewacht —
Mutations-Gegenprobe M8 entfernte sie ersatzlos, ueber 100 gepruefte Tests
blieben gruen.
  Severity: HIGH

Tests: 11/11 der neuen Spec-Testdatei gruen; 1 von ~950 im Regressionsfeger rot
(F001). Mutationsfamilie: 7 von 8 Mutationen praezise bewacht, 1 unbewacht (F003).

---

# Runde 2 — Gegenpruefung der Fixes (Commit `c5c4986a`)

Auftrag: die drei Befunde F001-F003 aus Runde 1 wurden angeblich behoben.
Nicht die Meldung pruefen, sondern die Fixes selbst — durch Wiederholung der
Mutationen UND Pruefung der neuen Tests auf Scheinsicherheit.

## Diff-Umfang

`git diff --stat 6c8c16a4 -- src/ tests/` zeigt ausschliesslich
`src/services/notification_service.py` (36 Zeilen) und die Spec-Testdatei
(+197 Zeilen, 3 neue Tests `test_f001_...`, `test_f002_...`, `test_f003_...`).
`src/services/trip_alert.py` ist UNVERAENDERT (bestaetigt die Entwickler-
Aussage: F003 war eine reine Testluecke, kein Produktivfehler).

## Mutationswiederholung (String-Ersetzung, externe Sicherungskopie,
Rueckname per Diff verifiziert, kein `git checkout`/`stash`/`reset`)

| # | Mutation | Datei:Zeile | Ergebnis |
|---|---|---|---|
| R2-A | `trip_local_today(trip, now_utc)` zurueck auf `date.today()` in `send_deviation_alert` | notification_service.py:818 | `test_f001_...` ROT + `tests/test_output_timezone_guard.py::test_no_unlisted_output_timezone_violations` ROT (dieselbe Meldung wie Runde 1, jetzt nur noch fuer `send_deviation_alert` — `send_official_alert` bleibt sauber) |
| R2-B | Staleness-Gate in `send_official_alert` zurueck auf `_stage_number_for_date(trip, anchor_date or local_today)` | notification_service.py:1045 | `test_f002_...` ROT — Fehlertext zeigt EXAKT den urspruenglichen Fehlwert: `'S1 Seg 1: !TH:L 17:27-20:27'` (S1 statt S3) |
| R2-C | `segment_date=segment_date` an der realen Aufrufstelle entfernt (= Runde-1-Mutation M8 wiederholt) | trip_alert.py:2227 | `test_f003_...` ROT — 13 andere Tests der Spec-Datei bleiben gruen (praezise, kein Kollateralschaden) |

Alle drei Mutationen einzeln zurueckgenommen, `diff` gegen Sicherungskopie
nach jeder Ruecknahme leer.

## Pruefung auf Scheinsicherheit

**F001 — misst der Test wirklich Ortszeit-Abhaengigkeit?**
`trip_two_zones()`/`_anker()` sind bestehende, mehrfach wiederverwendete
Fixtures (`tests/tdd/conftest.py`, Herkunft #1795/#1727 S5a — dieselbe
Bauart wie in `test_befehlspfade_folgen_ortszone.py`). `_anker()` erzwingt
STRUKTURELL zwei Zusicherungen VOR dem eigentlichen Test: (a) der Ortstag der
gewaehlten Zone entspricht dem erwarteten Wert, UND (b) `ortstag !=
now_utc.date()` — d.h. der Testaufbau kann gar nicht bestehen, wenn Orts- und
Weltzeit-Tag zufaellig zusammenfallen (genau die Klasse Fehler aus #2004,
im Docstring dokumentiert). Die Reduktion auf eine Zone ist also gar nicht
moeglich, ohne dass `_anker()` selbst bereits am Setup scheitert — die
Diskriminierung ist erzwungen, nicht zufaellig. Die Mutationsprobe (R2-A)
bestaetigt das empirisch: der Test faellt exakt dann, wenn die Ortstag-
Ableitung entfernt wird. **Kein Scheinbeweis.**

**F002 — ist die Gegenprobe echt?**
Ja, siehe Mutation R2-B: OHNE den Fix erscheint an GENAU der gepruef­ten
Stelle wieder das reproduzierte Fehlbild `S1` (statt der korrekten `S3`) —
identisch zum Runde-1-Befund. Die Positivkontrolle im selben Testkoerper
(frischer Anker -> `S3` erscheint weiterhin) wurde separat durch den
Grundlauf (14/14 gruen ohne Mutation) bestaetigt. **Kein Scheinbeweis.**

**F003 — durchlaeuft der Test wirklich den echten Ausloesepfad?**
`TripAlertService.check_radar_alerts()` ist die reale Scheduler-Einstiegs­-
stelle (`trip_report_scheduler.py:1789`, alle ~15 min in Produktion
aufgerufen) — kein Testdouble dieser Methode selbst. Injiziert wird nur die
Radar-Datenquelle ueber die bestehende DI-Naht `radar_service=` (echter
`RadarNowcastService`, `CountingFrameSource` liefert echte `RadarFrame`-
Objekte statt eines Netzabrufs — dieselbe Bauart wie in weiteren
Nowcast-Tests, `tests/helpers/nowcast_gate_fixtures.py`). `write_user_tier(uid,
"standard")` schreibt eine echte `user.json` mit einem echten Tier-Attribut;
das ist KEINE Verschleierung, sondern notwendige Vorbedingung, weil
`_effective_alert_channels()` den SMS-Kanal sonst ueber die (unabhaengige)
Tier-Sperre herausfiltern wuerde, BEVOR die Etappen-Frage ueberhaupt
entsteht — ohne diese Zeile wuerde der Test an einer VOR­gelagerten Stelle
scheitern (0 statt 1 SMS), nicht an der gepruef­ten Naht. Mutation R2-C
bestaetigt: der Test faellt praezise, wenn NUR die `segment_date`-
Weiterreichung entfernt wird — sonst nichts. **Kein Scheinbeweis, `write_user_tier`
verdeckt nichts.**

## Neue Angriffsflaeche durch den Fix (Team-Lead-Punkt 3)

**Kann die F002-Staleness-Sperre eine vorher korrekte Ausgabe veraendern?**
Nein — im Gegenteil, sie kann die Ausgabe nur von "falscher Praefix" auf
"kein Praefix" aendern, nie von "korrekter Praefix" auf "kein Praefix": die
Kanalauswahl (`for channel in sorted(effective_channels): ... break` beim
ersten LESBAREN Anker, unabhaengig vom Alter) ist UNVERAENDERT aus Runde 1
uebernommen. Bleibt dabei ein Randfall bestehen — gemischte Kanal-Freshness
(z.B. `email`-Anker 2 Tage alt, `sms`-Anker taggleich, `email` sortiert
zuerst): der jetzige Code waehlt weiterhin den ERSTEN lesbaren Anker
(`email`, veraltet) und unterdrueckt dann das Praefix komplett, OBWOHL ein
taggleicher `sms`-Anker verfuegbar waere. Das ist kein neuer Fehler (dieselbe
Kanal-Selektionsregel bestand schon in Runde 1 und stammt aus
`trip_alert.py`s bewusst alterslosem Geometrie-Rueckfall) und bleibt
SICHER (nie ein falscher Wert, hoechstens ein fehlender) — daher kein
Finding, sondern eine dokumentierte Beobachtung fuer die Known-Limitations-
Liste. Severity, falls spaeter aufgegriffen: LOW.
- Code reference: `src/services/notification_service.py:1040-1045`

**Verhaelt sich `trip_local_today` bei einem Trip ohne Wegpunkte definiert?**
Ja. `trip_tz()` (`src/services/trip_day.py:29-42`) faellt OHNE jeden
Wegpunkt auf die importierte `UTC`-Konstante zurueck ("Hausnorm #1345") und
wirft nie. `trip_local_today`/`trip_local_now` sind duenne, bereits
etablierte Sichten darauf (#1470/#1697/#1724) — kein neues Risiko durch
diesen Fix, da die Funktion selbst nicht Teil des Diffs ist, nur ein neuer
Aufrufer.

## Verdict Runde 2

===============================================
**VERDICT: VERIFIED**
===============================================

Alle drei Befunde aus Runde 1 sind durch eigene Mutationswiederholung
bestaetigt behoben:
- F001: `trip_local_today()` ersetzt `date.today()` an beiden betroffenen
  Stellen; Ruecknahme laesst sowohl den neuen Naht-Test als auch den
  Kern-Waechter `test_output_timezone_guard.py` wieder rot werden.
- F002: Staleness-Gate verhindert nachweislich das reproduzierte Fehlbild
  (S1 statt S3); Ruecknahme bringt exakt dieses Fehlbild zurueck.
- F003: neuer Test durchlaeuft den echten Produktions-Ausloesepfad
  (`TripAlertService.check_radar_alerts()`); Ruecknahme der Wirkort-
  Verdrahtung laesst ihn praezise (und nur ihn) rot werden.

Alle drei neuen Tests wurden auf Scheinsicherheit geprueft (Setup-Zwang bei
F001, Fehlbild-Identitaet bei F002, echter Scheduler-Pfad + notwendige statt
verschleiernde Tier-Vorbedingung bei F003) und bestehen die Pruefung.

Keine neue Regression gefunden: `tests/test_output_timezone_guard.py`
(18 Tests) und ein erneuter Lauf der Spec-Testdatei (14/14) sowie
angrenzender Radar-/Official-Alert-Testdateien bleiben gruen.

Eine nicht-blockierende Beobachtung (Kanal-Selektionsreihenfolge kann bei
gemischter Anker-Freshness ein an sich verfuegbares, korrektes Praefix
unterdruecken statt es zu zeigen) ist sicher (kein Fehlwert) und wird als
LOW/Known-Limitation vermerkt, nicht als Finding gezaehlt.

Tests: 14/14 Spec-Testdatei gruen, 18/18 Timezone-Guard gruen, 3/3
Mutationswiederholungen praezise gefangen, 0 Kollateralschaeden in den
mitgeprueften Radar-/Official-Alert-Regressionstests.
