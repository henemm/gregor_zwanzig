---
entity_id: fix_1727_s5g_restkandidaten_und_kategorien
type: refactor
created: 2026-08-20
updated: 2026-08-20
status: draft
workflow: fix-1727-s5g-alarmkandidaten
tags: [timezone, adr-0051, output-timezone-guard, alert-anchor, compare, radar-alert]
---

# Fix #1727 S5g — Restkandidaten (8) + Kategorie-Mechanik für `KNOWN_VIOLATIONS`

## Approval

- [ ] Approved

## Purpose

Zwei getrennte, aber zusammengehörige Maßnahmen an `tests/test_output_timezone_guard.py`:

**Teil A** stellt die letzten 8 echten `raw_astimezone`-Kandidaten in
`KNOWN_VIOLATIONS` (`alert_briefing_anchor.py`, `compare_location_weather_source.py` x2,
`compare_official_alert.py`, `scheduler_dispatch_service.py`, `stage_weather.py`,
`trip_alert.py` x2) auf die zentralen Helfer `to_utc()`/`local_dt()`/`local_fmt()` um. Reine
Formbereinigung, kein Bugfix — die Analyse hat für alle 8 Stellen bestätigt, dass sie schon heute
korrekt rechnen. `KNOWN_VIOLATIONS` schrumpft dadurch von 34 auf 26.

**Teil B** macht den Unterschied zwischen „noch nicht behoben" und „bewusst so dauerhaft" bei den
verbleibenden 26 Einträgen maschinell prüfbar statt reiner Prosa. Heute beginnen die 4
bewusst-UTC-Einträge mit `"raw_astimezone (:130) — …"` — also mit der Fundart des Scanners, nicht
mit einer Kategorie — und sehen dadurch identisch aus wie ein echter, noch offener Kandidat. Ein
Eintrag beschreibt sich dabei nachweislich falsch: `run_compare_presets_daily` behauptet „Fälligkeit
in der Ortszone des Presets", ist tatsächlich ein manueller `?hour=`-Debug-Trigger, den der
Produktivbetrieb nie erreicht (die echte Preset-Ortszonen-Logik sitzt seit #1726 in
`compare_slot_scheduler.py::presets_due_for_hour`). Issue #1727 fordert wörtlich, dieser Unterschied
müsse am Ende „zitierbar" sein. Teil B löst das über eine Pflicht-Kategorie je Eintrag
(`DAUERHAFT` / `AUFRUFSEITE(#1402)` / `BEWUSST-UTC(#1345)`) mit erzwungener Mindestbegründung,
statt einer neuen ungeprüften Konvention.

## Source

- **File A:** `src/services/alert_briefing_anchor.py`
- **Identifier A:** `record_briefing_sent` (`:205`)
- **File B:** `src/services/compare_location_weather_source.py`
- **Identifier B:** `_window_bound` (`:43`), `fetch` (`:118`)
- **File C:** `src/services/compare_official_alert.py`
- **Identifier C:** `_day_window_end` (`:397`)
- **File D:** `src/services/scheduler_dispatch_service.py`
- **Identifier D:** `run_compare_presets_daily` (`:210`)
- **File E:** `src/services/stage_weather.py`
- **Identifier E:** `_to_utc_date` (`:62`)
- **File F:** `src/services/trip_alert.py`
- **Identifier F:** `_briefing_precip_for_onset` (`:1028`), `check_radar_alerts` (`:1274`)
- **File G (Wächter):** `tests/test_output_timezone_guard.py`
- **Identifier G:** `KNOWN_VIOLATIONS` (`:526-645`), Gate-Tests `test_no_unlisted_output_timezone_violations` (`:669`), `test_known_violations_only_shrink` (`:685`), neuer Kategorie-Test

> **Schicht-Hinweis:** Alle sechs Kandidaten-Dateien liegen in `src/services/` (Python-Core), der
> Wächter in `tests/`. Keine Frontend-, Go- oder API-Router-Beteiligung.

## Estimated Scope

- **LoC:** ~20-30 Produktivcode, ~26 Zeilen Registerumschrift, ~25 Zeilen Kategorie-Test (Teil B),
  ~25 Zeilen neuer Ortszonen-Test für AC-7 — zusammen rund 100, innerhalb des LoC-Limits 250
- **Files:** 6 Produktivdateien + 2 Testdateien (`tests/test_output_timezone_guard.py`,
  `tests/tdd/test_compare_alert_day_window.py`)
- **Effort:** medium (Formumbau selbst niedrig, aber 3 der 8 Stellen rechnen in die Ortszone statt
  nach UTC — falsche Helferwahl würde einen Zeitzonenfehler einführen, wo heute keiner ist; Teil B
  ist neue Testmechanik nach erprobtem Vorbild)

### Affected Files

| File | Change Type | Description |
|------|-------------|--------------|
| `src/services/alert_briefing_anchor.py` | MODIFY | `record_briefing_sent`: `(at or now).astimezone(timezone.utc)` → `to_utc(at or now)` |
| `src/services/compare_location_weather_source.py` | MODIFY | `_window_bound`: `...astimezone(timezone.utc)` → `to_utc(...)`; `fetch`: `now.astimezone(tz).date()` → `local_dt(now, tz).date()` |
| `src/services/compare_official_alert.py` | MODIFY | `_day_window_end`: `now.astimezone(tz)` → `local_dt(now, tz)` |
| `src/services/scheduler_dispatch_service.py` | MODIFY | `run_compare_presets_daily`: `...astimezone(timezone.utc)` → `to_utc(...)` |
| `src/services/stage_weather.py` | MODIFY | `_to_utc_date`: `ts.astimezone(timezone.utc).date()` → `to_utc(ts).date()` |
| `src/services/trip_alert.py` | MODIFY | `_briefing_precip_for_onset`: `onset_dt.astimezone(timezone.utc).replace(...)` → `to_utc(onset_dt).replace(...)`; `check_radar_alerts`: `(...).astimezone(tz).strftime("%H:%M")` → `local_fmt(dt, tz)` |
| `tests/test_output_timezone_guard.py` | MODIFY | 8 Einträge aus `KNOWN_VIOLATIONS` entfernt (34→26); alle 26 verbleibenden Werte auf Kategorie-Präfix umgeschrieben; neuer Test für Kategorie + Mindestbegründung |

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `utils.timezone.to_utc` | function | zentraler Helfer aus S5f, für 5 der 8 Kandidaten (1, 2, 5, 6, 7) |
| `utils.timezone.local_dt` | function | bereits bestehender Helfer, für 2 der 8 Kandidaten (3, 4) — rechnet in die Ortszone, kein UTC |
| `utils.timezone.local_fmt` | function | bereits bestehender Helfer, für Kandidat 8 — Default-Format `"%H:%M"`, deckungsgleich mit dem Ist-Ausdruck |
| `tests/tdd/test_repo_path_hardcoding_ratchet.py::_MARKER`/`_UNWORT`/`_MIN_BEGRUENDUNG` | Muster | Vorbild für die Mindestbegründungs-Prüfung in Teil B (`:346-352`) |
| `test_issue_818_radar_briefing_integration.py` (AC-1/AC-2) | Test | echtes Werte-Netz für Kandidat 7, muss unverändert grün bleiben |
| `test_bundle_791_847_844_alerts.py::test_ac1_radar_alert_onset_in_local_time` | Test | echtes Werte-Netz für Kandidat 8, muss unverändert grün bleiben |
| `test_compare_alert_day_window.py::test_ac4_fenster_wird_in_der_ortszeit_am_ort_aufgeloest` | Test | echtes Werte-Netz für Kandidaten 2+3, muss unverändert grün bleiben |
| `test_official_alert_time_window.py::_daytime_location` | Test-Helfer | nicht-deterministisch bei Kandidat 4 (Wien an erster Stelle der Kandidatenliste) — Pflicht-Prüfpunkt für die Mutations-Gegenprobe, kein AC |
| `docs/context/fix-1727-s5g-alarmkandidaten.md` | Analyse | Quelle aller Messungen dieser Spec |
| `docs/specs/modules/fix_1727_s5f_raw_astimezone_formbereinigung.md` | Spec | direkte Formvorlage der Vorgängerscheibe |

## Implementation Details

Reihenfolge, analog S5f — Teil A vor Teil B, damit die neuen Kategorie-Werte nicht doppelt
angefasst werden:

1. **5 × `to_utc()`-Umstellung** (Kandidaten 1, 2, 5, 6, 7): rohen `.astimezone(timezone.utc)`-
   Ausdruck durch den bestehenden Helfer aus `src/utils/timezone.py` ersetzen. Bei Kandidat 7
   bleibt die anschließende `.replace(...)`-Kette unverändert (`to_utc(onset_dt).replace(...)`),
   analog zum Muster aus S5f bei `segment_weather.py`.
2. **2 × `local_dt()`-Umstellung** (Kandidaten 3, 4): `now.astimezone(tz)` → `local_dt(now, tz)`
   bzw. mit angehängtem `.date()`. **Diese beiden Stellen bewusst NICHT auf `to_utc()` ziehen** —
   sie rechnen den lokalen Tag/die lokale Uhrzeit am jeweiligen Vergleichsort, nicht den UTC-Wert.
   Ein `to_utc()`-Umbau würde hier einen Zeitzonenfehler *einführen*, wo heute keiner ist (dieselbe
   Falle, die S5f bei `trip_segments.py`s Ankunftstag am Ziel bewusst vermieden hat).
3. **1 × `local_fmt()`-Umstellung** (Kandidat 8): `(...).astimezone(tz).strftime("%H:%M")` →
   `local_fmt(dt, tz)`. `local_fmt`s Default-Format ist bereits `"%H:%M"` — deckungsgleich, kein
   Format-Parameter nötig. Auch hier: Ortszone, nicht UTC.
4. **Register:** die 8 zugehörigen Einträge aus `KNOWN_VIOLATIONS` entfernen — über den
   funktionsbezogenen Schlüssel (`Datei::Funktion::Ordinal`), NICHT über die im Register
   vermerkte Zeilennummer. Sieben der acht Registereinträge nennen eine veraltete Zeile (teils
   >150 Zeilen daneben, s. Known Limitations).
5. **Unbenutzte Imports prüfen:** je geänderter Datei kontrollieren, ob `from datetime import
   timezone` (oder Äquivalent) nach dem Umbau noch gebraucht wird — S5f musste das in
   `trip_segments.py` entfernen, hier ist es je Datei neu zu prüfen (mehrere der sechs Dateien
   nutzen `timezone` an anderer Stelle weiter, z. B. für `datetime.now(timezone.utc)`).
6. **Teil B — Kategorie-Präfix:** alle 26 verbleibenden Werte in `KNOWN_VIOLATIONS` auf ein
   Präfix aus `{"DAUERHAFT", "AUFRUFSEITE(#1402)", "BEWUSST-UTC(#1345)"}` umschreiben, gefolgt von
   einer substanziellen Begründung. Die 2 DAUERHAFT- und 20 AUFRUFSEITE-Einträge tragen bereits
   textlich diese Kategorie (nur das Präfix-Format muss vereinheitlicht werden); die 4
   BEWUSST-UTC-Einträge (`forecast_budget.py::_today_utc`, `meteoalarm_budget.py::_now_ts`,
   `meteoalarm_budget.py::_today_utc`, `weather_extractor.py::_to_naive_utc`) wechseln von
   `"raw_astimezone (:N) — …"` auf `"BEWUSST-UTC(#1345) — …"`. Bei `run_compare_presets_daily`
   entfällt der Eintrag ohnehin durch Teil A — die falsche Beschreibung muss dort nicht mehr
   korrigiert werden.
7. **Teil B — Kategorie- und Begründungs-Test:** neuer Test in `tests/test_output_timezone_guard.py`
   nach dem Muster von `test_repo_path_hardcoding_ratchet.py:346-352` (`_MARKER`/`_UNWORT`/
   `_MIN_BEGRUENDUNG`). Zwei Zusicherungen:
   - (a) jeder Wert in `KNOWN_VIOLATIONS` beginnt mit genau einer der drei gültigen Kategorien;
   - (b) nach dem Kategorie-Präfix folgt eine Begründung, die nach Entfernen aller Nicht-Wort-Zeichen
     (`_UNWORT`-Muster) mindestens `_MIN_BEGRUENDUNG = 15` Buchstaben/Ziffern übrig lässt — hält
     Alibi-Texte wie `": x"` oder ein einzelnes Emoji draußen.

## Expected Behavior

- **Input (Teil A):** dieselben Eingaben wie heute (Sendezeitpunkte, Compare-Fenstergrenzen,
  Etappendaten, Onset-Zeitpunkte, Radar-Alarmzeiten).
- **Output (Teil A):** identische Werte wie vor dem Umbau. Einzige beobachtbare Änderung ist das
  Schrumpfen von `KNOWN_VIOLATIONS` um genau 8 Einträge (34 → 26).
- **Output (Teil B):** jeder verbleibende `KNOWN_VIOLATIONS`-Wert ist über sein Präfix maschinell
  einer von drei Kategorien zuordenbar; ein Eintrag mit ungültigem Präfix oder einer zu kurzen
  Begründung lässt den neuen Test rot werden.
- **Side effects:** keine.

## Test Plan

### Automated Tests (TDD RED)

- [ ] Test 1: GIVEN die 5 `to_utc()`-Kandidaten (1, 2, 5, 6, 7) WHEN der Umbau abgeschlossen ist
  THEN liefern sie identische Werte wie vor dem Umbau (No-Op-Charakter, da alle Eingaben bereits
  aware sind).
- [ ] Test 2: GIVEN die 3 Ortszeit-Kandidaten (3, 4, 8) WHEN der Umbau abgeschlossen ist THEN
  rechnen sie weiterhin in die Ortszone des jeweiligen Ortes/Startpunkts, nicht nach UTC — ein
  Ersetzen von `local_dt`/`local_fmt` durch `to_utc` würde diesen Test rot färben.
- [ ] Test 3: GIVEN die 8 in `KNOWN_VIOLATIONS` gelisteten Fundstellen WHEN der Umbau abgeschlossen
  ist THEN sind genau diese 8 Einträge entfernt (34→26), `test_known_violations_only_shrink` und
  `test_no_unlisted_output_timezone_violations` laufen grün.
- [ ] Test 4: GIVEN die bestehenden Werte-Netz-Tests für Kandidat 7 und 8
  (`test_issue_818_radar_briefing_integration.py`, `test_bundle_791_847_844_alerts.py::
  test_ac1_radar_alert_onset_in_local_time`) und für Kandidaten 2+3
  (`test_compare_alert_day_window.py::test_ac4_fenster_wird_in_der_ortszeit_am_ort_aufgeloest`)
  WHEN der Umbau abgeschlossen ist THEN laufen alle unverändert grün, ohne Assert-Anpassung.
- [ ] Test 5: GIVEN die 26 verbleibenden `KNOWN_VIOLATIONS`-Werte nach Teil A WHEN der neue
  Kategorie-Test läuft THEN trägt jeder Wert eines der drei gültigen Präfixe und eine Begründung
  ≥15 Zeichen (nach Unwort-Bereinigung).
- [ ] Test 6: GIVEN ein synthetischer Eintrag mit gültigem Präfix aber Alibi-Begründung (`"x"` oder
  ein Emoji) WHEN der Kategorie-Test läuft THEN wird er als Verstoß erkannt (roter Test bei
  isolierter Prüfung der Testlogik, z. B. per Fixture-Dict analog `_fixture`/`_scan` im Vorbild).
- [ ] Test 7 (**neu zu schreiben**, AC-7): GIVEN einen Vergleichsort in einer Zone, in der Ortstag
  und UTC-Tag zum geprüften Zeitpunkt auseinanderfallen (fest gewählter Ort, fest gesetzter
  Zeitpunkt — keine Laufzeit-Ortswahl) WHEN `_day_window_end` das Fensterende bestimmt THEN folgt es
  dem **Ortstag**; ein Ersetzen von `local_dt(now, tz)` durch `to_utc(now)` oder eine feste Zone
  färbt den Test rot. Schliesst die belegte Lücke, dass die bestehenden Tests dieser Funktion
  ausschliesslich in Wiener Zone rechnen, wo Ortstag und UTC-Tag zusammenfallen.

## Acceptance Criteria

- **AC-1:** Given die 5 Kandidaten `record_briefing_sent`, `_window_bound`,
  `run_compare_presets_daily`, `_to_utc_date`, `_briefing_precip_for_onset`, When ihr roher
  `.astimezone(timezone.utc)`-Aufruf durch `to_utc(...)` aus `src/utils/timezone.py` ersetzt wird,
  Then liefern alle fünf denselben Wert wie vor dem Umbau — geprüft über die bestehenden
  Golden-Master- und Integrationstests der jeweiligen Funktion, kein Assert-Wert wurde angepasst.
  - Test: `uv run pytest tests/tdd/test_briefing_imminent_gate.py
    tests/tdd/test_alert_channel_threshold.py tests/tdd/test_compare_alert_day_window.py
    tests/tdd/test_issue_461_compare_preset_dispatch.py tests/tdd/test_stage_weather_parity.py
    tests/tdd/test_issue_818_radar_briefing_integration.py` — alle grün, Diff der Testdateien
    selbst leer.
    ⚠️ **Testdateien müssen namentlich genannt werden.** `uv run pytest` mit einem blossen
    Verzeichnis (`tests/`) ist projektweit gesperrt (#1477) — der Wächter prüft, ob jedes Argument
    auf `.py` endet, und `tests/` tut das nicht. Ein `-k`-Filter ersetzt die Dateinennung NICHT.

- **AC-2:** Given die Kandidaten `fetch` (`compare_location_weather_source.py`, Kandidat 3) und
  `check_radar_alerts` (`trip_alert.py`, Kandidat 8), When ihr roher `.astimezone(tz)`-Aufruf durch
  `local_dt(now, tz)` bzw. `local_fmt(dt, tz)` ersetzt wird, Then rechnen beide weiterhin in die
  **Ortszone** des jeweiligen Ortes bzw. Startpunkts — nicht nach UTC. Ein versehentlicher Umbau auf
  `to_utc()` an einer dieser Stellen lässt die genannten Tests rot werden.
  - Test: `uv run pytest tests/tdd/test_compare_alert_day_window.py -k
    test_ac4_fenster_wird_in_der_ortszeit_am_ort_aufgeloest` (Kandidat 3, Ort in
    America/Los_Angeles mit ausformulierter Mutations-Erwartung im Docstring) und
    `uv run pytest tests/tdd/test_bundle_791_847_844_alerts.py -k
    test_ac1_radar_alert_onset_in_local_time` (Kandidat 8, Korsika, echter `mail_sink`; prüft die
    lokale Zeit im Body **und** dass die UTC-Zeit dort nicht steht) — beide grün ohne
    Assert-Änderung.

- **AC-3:** Given die 8 in `KNOWN_VIOLATIONS` gelisteten Fundstellen aus Teil A, When der Umbau
  abgeschlossen ist, Then sind genau diese 8 Einträge (funktionsbezogen identifiziert, nicht über
  die veraltete Zeilennummer) aus dem Register entfernt, kein anderer Eintrag hat sich in seinem
  Schlüssel geändert, und `test_known_violations_only_shrink` sowie
  `test_no_unlisted_output_timezone_violations` laufen grün — Registergröße 34 → 26.
  - Test: `uv run pytest tests/test_output_timezone_guard.py -k "known_violations_only_shrink or
    no_unlisted_output_timezone_violations"` — beide grün.

- **AC-4:** Given die 26 nach Teil A verbleibenden Werte in `KNOWN_VIOLATIONS`, When der neue
  Kategorie-Test läuft, Then trägt jeder Wert genau eines der drei Präfixe `DAUERHAFT`,
  `AUFRUFSEITE(#1402)` oder `BEWUSST-UTC(#1345)`, gefolgt von einer Begründung mit mindestens 15
  Buchstaben/Ziffern nach Entfernen aller Nicht-Wort-Zeichen — alle 26 bestehen.
  - Test: `uv run pytest tests/test_output_timezone_guard.py -k
    test_jeder_eintrag_traegt_kategorie_und_begruendung` — grün. (Name festgelegt, nicht als
    Vorschlag: der Test wird in AC-5 erneut referenziert und muss dort denselben Namen tragen.)

- **AC-5:** Given ein synthetischer `KNOWN_VIOLATIONS`-Eintrag mit gültigem Präfix, aber einer
  Begründung, die nach Unwort-Bereinigung unter 15 Zeichen bleibt (z. B. `"DAUERHAFT — x"` oder ein
  einzelnes Emoji), When der Kategorie-Test auf diesen Eintrag angewendet wird, Then meldet der Test
  einen Verstoß — die Prüfung ist nicht bloß eine Präfix-Existenzprüfung.
  - Test: `uv run pytest tests/test_output_timezone_guard.py -k
    test_alibi_begruendung_zaehlt_nicht` (Name festgelegt). Isolierter Testfall, der die
    Prüffunktion direkt gegen ein **Fixture-Dict** mit dem Alibi-Eintrag aufruft — nicht gegen das
    echte `KNOWN_VIOLATIONS`. Muster: `_fixture`/`_scan` in
    `tests/tdd/test_repo_path_hardcoding_ratchet.py`, dort belegt durch
    `test_ac5_marker_ohne_begruendung_bleibt_rot` (`:172`) und
    `test_ac8_alibi_begruendung_zaehlt_nicht` (`:180`). Assertion erwartet einen **gemeldeten
    Verstoss**, kein leeres Ergebnis — die Prüffunktion muss also einen Befund zurückgeben, den der
    Test einsammeln kann, statt selbst zu assertieren.

- **AC-6:** Given die sechs geänderten Produktivdateien, When der Umbau abgeschlossen ist, Then
  enthält keine einen unbenutzten Import — je Datei ist geprüft, ob `timezone` aus `datetime` nach
  dem Umbau noch für andere Zwecke gebraucht wird, und nur dort entfernt, wo das nicht der Fall ist.
  - Test: `uv run ruff check src/services/alert_briefing_anchor.py
    src/services/compare_location_weather_source.py src/services/compare_official_alert.py
    src/services/scheduler_dispatch_service.py src/services/stage_weather.py
    src/services/trip_alert.py` — keine `F401`-Findings, keine neuen Findings gegenüber dem Stand
    vor dieser Scheibe.

- **AC-7:** Given den Kandidaten `_day_window_end` (`compare_official_alert.py`, Kandidat 4) und
  einen Vergleichsort in einer Zone, in der Ortstag und UTC-Tag zum geprüften Zeitpunkt
  **auseinanderfallen** (z. B. `Pacific/Auckland` bei einem UTC-Zeitpunkt am späten Abend), When
  `_day_window_end` das Tagesfenster-Ende bestimmt, Then bezieht es sich auf den **Ortstag** des
  Vergleichsorts, nicht auf den UTC-Tag — der Test wird rot, sobald `local_dt(now, tz)` durch
  `to_utc(now)` oder eine fest verdrahtete Zone ersetzt wird.
  - Test: **neu zu schreiben** in `tests/tdd/test_compare_alert_day_window.py` als
    `test_day_window_end_folgt_dem_ortstag_nicht_dem_utc_tag` (Name festgelegt), mit fest gewähltem
    Ort und fest gesetztem Zeitpunkt (keine Laufzeit-Ortswahl). 🔴 **Der Ort MUSS ausserhalb der
    Wiener Zone liegen und der Zeitpunkt so gewählt sein, dass Ortstag und UTC-Tag
    auseinanderfallen** — sonst prüft der Test dieselbe Blindstelle wie die bestehenden und ist
    wertlos. Begründung, warum ein neuer Test
    nötig ist: die vorhandenen Grenzwert-Tests `test_1599_ac5`/`test_1599_ac6` (`:840`/`:861`)
    prüfen `_day_window_end` ausschließlich mit fest kodierten Zeiten in Wiener Zone (17:45 UTC als
    „19:45 Ortszeit"). Dort fallen Ortstag und UTC-Tag auf **denselben** Kalendertag, und
    `_day_window_end` wertet genau `local_now.date()` aus — eine Verwechslung von `local_dt` mit
    `to_utc` bliebe deshalb grün. Der bestehende Zonen-Test `_daytime_location()`
    (`test_official_alert_time_window.py:497-508`) ist als Nachweis untauglich, weil er den Ort zur
    Laufzeit aus 11 Kandidaten wählt und Wien an erster Stelle steht (s. Known Limitations).

## Known Limitations

- **Kein funktionaler Bug** — wie S5f ist dies reine Formbereinigung. Alle 8 Kandidaten rechnen
  schon heute korrekt; keiner ist ein laufender Zeitzonenfehler.
- **Zeilendrift im Register ist massiv:** 7 von 8 betroffenen Registereinträgen nennen eine
  veraltete Zeile, teils um mehrere hundert Zeilen daneben (`:872`→`:1028`, `:1092`→`:1274`,
  `:271`→`:397`, `:179`→`:210`). Einträge sind ausschließlich über den funktionsbezogenen Schlüssel
  zu identifizieren.
- **Zwei Kandidaten ohne echtes Werte-Netz** (1: `record_briefing_sent`, 6: `_to_utc_date`) — alle
  vorhandenen Tests übergeben bereits UTC-aware Werte bzw. prüfen nur Schlüsselmengen, nie den
  konkreten Zeitwert der Konvertierung. Der Umbau ist dort ausschließlich durch die eigenen Tests
  von `to_utc()` (aus S5f) gedeckt, nicht durch ein dediziertes Regressionsnetz dieser Scheibe.
- **Kandidat 4 (`_day_window_end`) war bis zu dieser Scheibe nicht deterministisch bewacht** —
  deshalb **AC-7**, das den fehlenden Test mitbringt. Der Mangel hat zwei unabhängige Ursachen, die
  beide belegt sind:
  1. `_daytime_location()` (`test_official_alert_time_window.py:497-508`) wählt den Ort zur Laufzeit
     als ersten von 11 Kandidaten mit Ortsstunde 6–16 — **Wien steht an erster Stelle**. Läuft die
     Suite zur passenden Tageszeit, testet sie Wien gegen Wien, und eine Mutation „fest auf Wien
     verdrahtet" bliebe unentdeckt. Ein wanduhr-abhängiger Wächter ist kein Wächter.
  2. Die Grenzwert-Tests `test_1599_ac5`/`test_1599_ac6` (`test_compare_alert_day_window.py:840`/
     `:861`) prüfen `_day_window_end` mit fest kodierten Zeiten in **Wiener Zone** (17:45 UTC als
     „19:45 Ortszeit"). Ortstag und UTC-Tag fallen dort auf denselben Kalendertag; da
     `_day_window_end` genau `local_now.date()` auswertet, bliebe eine Verwechslung von `local_dt`
     mit `to_utc` **grün**. Sie bewachen die Fenster-Formel, nicht die Zone.

  Ohne AC-7 wäre die Zusicherung „rechnet in der Ortszone" für Kandidat 4 unbelegt — genau der
  Fehler, der bei S5e als nicht führbares AC-8 auffiel, nur diesmal vor der Umsetzung erkannt.
- **Kein literaler Count-Assert:** es gibt kein `len(KNOWN_VIOLATIONS) == 26` — wie schon bei S5f
  ist die „genau N"-Zusicherung Diff-Augenschein plus die zwei bidirektionalen Mengentests
  (`test_no_unlisted_output_timezone_violations`, `test_known_violations_only_shrink`).
- **Nicht Scope dieser Scheibe (Nebenbefunde, gehen in die Triage #1199):**
  - `_derive_is_day` vergleicht UTC-Tag gegen Ortstag (`stage_weather.py:74`) — belegt kosmetisch
    und praktisch unerreichbar (einziger Leser ist eine Icon-Auswahl, wo der WMO-Code ohnehin
    Vorrang hat); die Formbereinigung dieser Scheibe löst das nicht.
  - Detektor-Schwäche bei `ZoneInfo(NAME)` statt `ZoneInfo("Literal")` (Konstanten-Indirektion wird
    vom Scanner nicht erkannt).
  - Scan-Scope-Lücke `src/providers/` — dort steht `ZoneInfo("Europe/Vienna")`
    (`geosphere.py:545`), für den Detektor unsichtbar.
  - Der Wien-Default auf der Go-Seite (`internal/config/config.go:20`) — #1727 grenzt Go
    ausdrücklich aus.
  - Toter Code `or timezone.utc` in `compare_official_alert.py:396` (`tz_for_coords` liefert nie
    falsy). Darf beiläufig mit entfernt werden, ist aber kein eigenes AC dieser Scheibe.
- **Ortsvergleich ist Produktthema zurückgestellt:** drei der acht Kandidaten liegen in
  Compare-Dateien (`compare_location_weather_source.py` x2, `compare_official_alert.py`). Diese
  Scheibe ist reine Zeitzonen-Hygiene am Bestand, kein Feature-Ausbau am Ortsvergleich.
- **Regel-Budget (Teil B):** ersetzt die bisher ungeprüfte Prosa-Konvention, ist also kein
  Netto-Zuwachs an Regeln. Prüfdatum dennoch gesetzt: **2026-11-18**. Kriterium: hat der neue Test
  bis dahin mindestens einen Eintrag ohne gültige Kategorie oder ohne ausreichende Begründung
  gefangen? Wenn nein, ersatzlos zurückbauen.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine neue — Umsetzung folgt ADR-0051 Regel 1/2 (Zeitpunkt vs. Kalenderzeit, Zone an
  den Daten) und der Hausnorm #1345 (naiv == UTC). Wie bei S5f zentralisiert diese Scheibe nur eine
  bereits etablierte, korrekte Umrechnung in benannte Helfer.
- **Rationale:** Teil A führt kein neues Muster ein. Teil B führt keinen neuen Architektur-
  Mechanismus ein, sondern übernimmt ein im Repo bereits erprobtes Muster (Marker +
  Mindestbegründung aus `test_repo_path_hardcoding_ratchet.py`) auf eine bestehende Ausnahmeliste —
  konsistent mit dem Wächter-Modell aus ADR-0051 (`KNOWN_VIOLATIONS` darf nur schrumpfen, nie
  wachsen). Ein eigenes ADR wäre für eine Formbereinigung plus Testmechanik-Übertragung ohne neue
  Architekturentscheidung unangemessen.

## Changelog

- 2026-08-20: Initial spec created
