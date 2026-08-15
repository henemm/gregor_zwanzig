# Context: fix-1709-wallclock-ratsche-indirekt

**Issue:** [#1709](https://github.com/henemm/gregor_zwanzig/issues/1709) — „Eine Nacht darf die CI nie blockieren: Wallclock-Ratsche fängt die indirekte Zeitabhängigkeit nicht"
**Workflow:** `fix-1709-wallclock-ratsche-indirekt` · Track: Full Process
**Erstellt:** 2026-08-15 · HEAD bei der Messung: `b6674c94`

## Request Summary

Die bestehende Wächter-Ratsche `tests/tdd/test_fixture_wallclock_ratchet.py` fängt nur eine
Variante der Wanduhr-Abhängigkeit in Testfixtures. Die Variante, die am 2026-08-10 drei
Sitzungen einen Abend gekostet hat, ist ihr **logisches Gegenteil** und deshalb strukturell
unsichtbar. Gesucht ist ein Wächter, der die Fehlerklasse fängt — nicht ein weiterer Einzelfix.

## Ausgangslage: die Einzelfälle sind zu, die Klasse ist offen

| Issue | Stand | Was es war |
|---|---|---|
| #1667 (S1–S3) | ✅ zu | Mitternachts-Wrap; S1 baute die bestehende Ratsche |
| #1697 (PR #1705) | ✅ zu | Ortstag statt Serverdatum; härtete `stage_date()` |
| #1851 | ✅ zu | Briefing-Vorlaufsperre traf drei Alarm-Tests |
| #1858 | ✅ zu | dieselbe Sperre traf die Wächter von #1584/#1667 |
| **#1709** | **offen** | **die Klasse hinter allen vieren** |

Belegungsprüfung 2026-08-15: kein Branch, kein Worktree, kein Commit zu `1709`; die
Ratschen-Datei ist seit `70faaa62` (#1667 S1) unberührt. `fix_1851_alarm_tests_vorlaufsperre.md`
benennt unter „Known Limitations" ausdrücklich, dass die Wanduhr-Familie #1709 unberührt bleibt.

## Warum die bestehende Ratsche diese Variante nicht sehen KANN

`test_fixture_wallclock_ratchet.py:474` meldet einen Fund nur, wenn **beide** Merkmale
zugleich auftreten (Docstring Z. 36–46):

1. Wanduhr-Etappendatum (`now.date()`, `date.today()`, `stage_date()`), **und**
2. ungeklemmte Ankunftszeit — ein `(now ± timedelta).strftime("%H:%M")`.

Der Fall aus #1709 hat Merkmal 1 und ist **gerade durch das Fehlen von Merkmal 2** gefährlich:
ohne gesetzte Ankunftszeiten greift der Naismith-Standardstart, das Ziel-Segment endet am
Tagesfenster-Ende, und ab einer bestimmten Uhrzeit ist es „vorbei". Das ist kein Sonderfall,
den der Scanner übersieht — es ist die Negation seiner Fundbedingung.

**Konsequenz für die Lösung:** eine Erweiterung der bestehenden Fundbedingung um ein weiteres
UND-Glied genügt nicht. Es braucht eine zweite, eigenständige Fundregel.

## Die Ursachenkette, am Code nachgemessen

Zeilenangaben im Issue-Text stimmen nicht mehr (Code ist gewandert). Hier der Stand bei `b6674c94`,
selbst nachgemessen — nicht aus dem Ticket übernommen:

1. `src/app/day_window.py:16-17` — `DAY_WINDOW_START_HOUR = 4`, `DAY_WINDOW_END_HOUR = 19`.
2. `src/services/trip_segments.py:265-278` — das **Ziel-Segment** endet bei
   `combine(arrival_local_date, time(end_hour))` in der **Ortszone des Ziels**
   (`tz_for_coords(last_wp.lat, last_wp.lon)`), umgerechnet nach UTC.
3. `src/services/trip_alert.py:1244-1245` — `if cached.segment.end_time < now_utc: continue`
   („Bereits absolviert — überspringen").
4. `src/services/trip_alert.py:1411` — zweite Stelle, dieselbe Regel („Etappe vorbei").

Bei den im Bestand dominierenden Fixture-Koordinaten `47.0 / 11.0` (Europe/Vienna, im Sommer
UTC+2) ist `19:00` Ortszeit **exakt 17:00 UTC**. Ab da filtern (3) und (4) jedes Segment weg,
und der Alarmpfad meldet völlig korrekt „No fresh weather data". Die Kippkante aus dem Issue
ist damit bestätigt; nur ihre Fundstellen sind andere.

Ein **zweiter** Filter in derselben Schleife (`trip_alert.py:1246-1247`) vergleicht
`cached.segment.start_time.date() > today_utc` — ein **UTC**-Kalendertagsvergleich, also eine
weitere, unabhängige Kippkante an UTC-Mitternacht.

## Die Kippkanten-Landschaft (Vermessung durch Explore-Agent, Korrekturen eingearbeitet)

| # | Familie | Ort | Schwelle | Zone |
|---|---|---|---|---|
| 1 | Tagesfenster → Ziel-Segment-Ende | `trip_segments.py:265-289` | `end_hour` (19), sonst 1-h-Notfenster | **Ortszeit des Ziels** |
| 2 | Mitternachts-Wrap (Interpolation) | `trip_segments.py:85-98` | `if nxt < base: nxt += 1 Tag` | naiv/Ortszeit |
| 3 | Briefing-Vorlaufsperre **Trip** | `trip_report_scheduler.py:189` | `stunde <= h < stunde+3`, Default 7 / 18 | **Ortszeit des Trips** |
| 3b | Vorlauf-Abtastung | `alert_gate.py:64,74,86` | 60 min Vorlauf, 5-min-Raster, 4 h Rückblick | übergebene Zone |
| 3c | Briefing-Fälligkeit **Compare** | `compare_slot_scheduler.py:142,166-171` | **Stundengleichheit**, Default **6** / 18 | Ortszeit des ersten Orts |
| 4 | Ruhezeit (Quiet Hours) | `deviation_alert_engine.py:106-139` | nutzergesetzt; Default `None` | Ortszeit |
| 5 | Tageszähler-Reset | `alert_daily_limit.py:39-40,64-65` | Ortsmitternacht | Ortszeit |
| 6 | Nowcast-Horizont | `trip_alert.py:~945` | `minutes_until_start > 60` | UTC |

**Zwei Korrekturen an meiner eigenen Vorannahme** (beide am Code belegt, nicht hergeleitet):

- Die 23:59-Klemme in `src/core/naismith.py` **existiert nicht mehr** — seit #1667 S2 rechnet
  `_format_hhmm()` (Z. 54-73) mit `total_min % (24*60)`. Wer sie noch als Ursache nennt,
  beschreibt einen Stand von vor #1667 S2.
- Familie 3 hat **zwei** Ausprägungen mit **verschiedenen Schwellenformen und verschiedenen
  Vorgabezeiten**: Trip = 3-Stunden-Fenster ab 7/18 Uhr, Compare = Stundengleichheit ab
  **6**/18 Uhr. Ein Wächter, der nur den Trip-Fall kennt, sieht die Compare-Variante nicht —
  und zwischen 6:00 und 6:59 Ortszeit greift ausschließlich die Compare-Variante.

## Der entscheidende Befund: das Härtungs-Kit existiert bereits

Das ist die wichtigste Erkenntnis dieser Phase und verschiebt den Zuschnitt der Arbeit.
Für **jede** der drei tragenden Kippkanten liegt bereits ein erprobter Baustein im Repo:

| Kippkante | Baustein | Wirkung |
|---|---|---|
| 1 (Tagesfenster) | `tests/helpers/arrival_window_fixtures.py` → `active_window_offsets(lat, lon, …)` | Ankunftszeiten liegen im aktiven Fenster, monoton, auf dem Etappentag |
| 2 (Ortstag ≠ Serverdatum) | dieselbe Datei → `stage_date(lat, lon)` | Etappendatum = **Ortstag**, dieselbe Formel wie der Prüfling (#1697/ADR-0044) |
| 3 (Vorlaufsperre) | `tests/helpers/briefing_zeiten.py` → `briefing_zeiten_fuer_trip(trip)` | Briefingzeiten relativ zur **echten** Uhr, immer außerhalb des Vorlaufs |
| alle | Koordinaten `64.13 / -21.90` (`Atlantic/Reykjavik`, ganzjährig UTC+0) | Ortstag ≡ UTC-Tag, keine Sommerzeit |

Die vollständig gehärtete Zielform steht in
`tests/tdd/test_briefing_anchor_survives_dispatch_failure.py:178-205` — inklusive eines
Kommentars, der die Fehlerklasse benennt („sonst greift ab ~17:00 UTC der Naismith-Default
08:00 und das Ziel-Segment endet am Tagesfenster-Ende (19:00 Ortszeit) VOR dem Testlauf").

`briefing_zeiten.py` enthält zusätzlich die für diesen Workflow zentrale Regel im Klartext:
die Zone MUSS die sein, in der der **Prüfling** die Fälligkeit auswertet — „eine andere Zone
wäre eine Zusicherung am falschen Ort: die Stunde sähe sicher aus und läge trotzdem im Fenster."

**Damit ist die Aufgabe nicht „eine Härtung erfinden", sondern „die vorhandene Härtung dort
erzwingen, wo sie nötig ist".** Das ist eine deutlich andere — und besser belegbare — Arbeit
als das Ticket vom 2026-08-10 annehmen konnte.

## Bestandsvermessung (selbst ausgezählt, mechanisch)

AST-/Textlauf über `tests/**/*.py` bei `b6674c94`:

| Menge | Anzahl |
|---|---|
| Testdateien, die eine Etappe/Wegpunkte bauen **und** Wanduhr-Bezug haben | **151** |
| davon ohne **beide** Härtungs-Helfer | **128** |
| davon zusätzlich ohne **jede** Ankunftszeit (`arrival_calculated`/`arrival_override`) | **107** |
| Dateien, die `arrival_window_fixtures` nutzen | 15 |
| Dateien, die `briefing_zeiten` nutzen | 15 |
| Dateien mit beiden | 3 |
| Dateien mit UTC+0-Koordinate `64.13` | 3 |
| Dateien mit Alpen-Koordinaten (`47.0/11.0` bzw. `ALPEN_LAT`) | 124 |

🔴 **107 ist eine obere Schranke, keine Fundmenge.** Die Klasse beißt nur, wenn der *Prüfling*
eine Tageszeit-Grenze auswertet. Ein reiner Renderer- oder Telegram-Formatierungstest baut
dieselbe Fixture, läuft aber nie durch `trip_alert.py`. Wer 107 als „betroffen" meldet, wiederholt
denselben Fehler wie die widerlegten Erklärungen in der Ticket-Historie.

## Die Messmethode (der eigentliche Knackpunkt)

Ob eine Datei betroffen ist, lässt sich **nicht durch Lesen** entscheiden — die
Zeitabhängigkeit entsteht erst im Prüfling. Sie lässt sich aber **messen**: dieselbe Datei zu
zwei künstlich verschiedenen Uhrzeiten laufen lassen und die Ergebnisse vergleichen. Nur die
**Differenz je Uhrzeit** ist der Befund; ein einzelner roter Lauf beweist nichts.

- `freezegun` ist bereits Dev-Dependency (`pyproject.toml:89`), 16 Testdateien nutzen es.
- Für einen Massenlauf braucht es ein sitzungsweites Einfrieren per Pytest-Plugin
  (`-p <modul>`), da die Bestandsdateien selbst keine Test-Uhr stellen.
- Uhrzeiten müssen **beide Seiten jeder Kippkante** treffen: mindestens eine vor 17:00 UTC und
  eine danach; für Familie 3 zusätzlich je eine in `[7,10)` und `[18,21)` **Ortszeit der
  Fixture** — nicht UTC. Wer die Uhrzeiten in UTC notiert, sucht bei fremder Zone falsch.

Ein Versuch, dieses Mess-Plugin schon in Phase 1 anzulegen, wurde vom `edit_gate` blockiert
(korrekt: `phase1_context` erlaubt keine Code-Änderungen). Es gehört in die Implementierungsphase.

## Bauart-Vorgaben für die neue Ratsche

Aus der Untersuchung der drei bestehenden AST-Ratschen (`test_fixture_wallclock_ratchet.py`,
`test_repo_path_hardcoding_ratchet.py`, `test_data_root_hardcoding_ratchet.py`):

- **Ablage:** `tests/tdd/`. **Nicht** in `.github/ci_tdd_excludes.txt` eintragen — sonst läuft
  sie nicht auf CI. Beide großen Ratschen laufen heute im `test`-Job mit.
- **Fixture-Vorlagen extern:** `tests/fixtures/ratchet_cases/*.py.txt`, außerhalb der
  Scanfläche `tests/**/*.py` — sonst meldet der Wächter seine eigenen Attrappen.
- **Selbstbeleg:** pro erkanntem Anti-Muster ein Positiv-Test (Scanner meldet) **und** eine
  Gegenprobe (Scanner schweigt beim korrekten Muster), beide gegen echte Dateien auf `tmp_path`.
  Vorbild `test_ac3_echter_testbaum_ohne_fehlalarm` verlangt zusätzlich `len(kandidaten) >= 20`,
  damit ein leerer Scan nicht durch fehlende Kandidaten vorgetäuscht werden kann.
- **Ausnahmen:** zwei etablierte Mechaniken — `KNOWN_VIOLATIONS`-Frozenset mit
  Begründungskommentar und Shrink-Gegentest (wenige, strukturell zwingende Fälle) **oder**
  Inline-Marker `# gz-…: <Begründung>` mit `_MIN_BEGRUENDUNG = 15` sinnvollen Zeichen (viele
  verstreute Fälle). Beide sind Ausnahmen **vom Fund**, keine Erlaubnislisten.
- **Regel-Budget:** `EXPIRY`-Konstante **und** ein Test, der das ISO-Datum als Text in der
  eigenen Datei erzwingt. Prüfdatum laut Ticket: **2026-11-10**.

🔴 Die bestehende Ratsche benennt eine Grenze, die auch für die neue gilt und nicht
wegprogrammierbar ist (Z. 172-177): *„Der Shrink-Wächter fängt nur VERALTETE Einträge, nicht
neue unbegründete: eine Ausnahmeliste kann sich strukturell nicht selbst gegen Zuwachs
schützen."*

## Related Files

| Datei | Relevanz |
|---|---|
| `tests/tdd/test_fixture_wallclock_ratchet.py` | Der zu erweiternde Wächter (672 Z.) |
| `tests/helpers/arrival_window_fixtures.py` | Härtungs-Kit Kippkante 1+2 |
| `tests/helpers/briefing_zeiten.py` | Härtungs-Kit Kippkante 3 |
| `tests/helpers/briefing_imminent_fixtures.py` | Vollständig gehärtete Referenz-Bauart (#1594) |
| `tests/tdd/test_briefing_anchor_survives_dispatch_failure.py:178-205` | Zielform einer Fixture |
| `src/services/trip_segments.py:265-289` | Ziel-Segment-Ende (Kippkante 1) |
| `src/services/trip_alert.py:1244-1247, 1411` | Die beiden „Segment vorbei"-Filter |
| `src/services/trip_report_scheduler.py:189` | Vorlaufsperre Trip |
| `src/services/compare_slot_scheduler.py:142,166-171` | Vorlauf-Fälligkeit Compare (anderer Default!) |
| `tests/fixtures/ratchet_cases/wallclock_arrival_faelle.py.txt` | Attrappen-Vorlagen |
| `.github/ci_tdd_excludes.txt` | Darf **nicht** wachsen |

## Existing Specs

- `docs/specs/modules/fix_1667_s1_fixture_wanduhr.md` — Spec der bestehenden Ratsche
- `docs/specs/modules/fix_1697_ortstag_statt_servertag.md` — Ortstag-Härtung
- `docs/specs/modules/fix_1851_alarm_tests_vorlaufsperre.md` — jüngster Einzelfall
- `docs/specs/modules/fix_1594_alarm_vorlauf_sperre.md` — die Sperre selbst
- ADR-0044 (Ortstag), ADR-0035 (Tagesfenster-Quelle), ADR-0009 (ersetzen statt verschlucken)

## Risks & Considerations

- **R1 — Falsch-positive Ratsche blockiert alles.** Das Ticket ist als „fälschlich
  blockierendes Gate" eingestuft; eine zu weite Fundregel erzeugt genau dasselbe Übel mit
  umgekehrtem Vorzeichen. Die Gegenprobe gegen den echten Testbaum ist deshalb Pflicht-AC,
  nicht Kür.
- **R2 — „Prüfling wertet Tageszeit aus" ist syntaktisch nicht entscheidbar.** Das Ticket
  räumt das ein und erlaubt einen begründeten Ansatzwechsel. Wahrscheinlichster Weg:
  Fundregel an der **Fixture-Bauart** festmachen (baut Etappe + nutzt keinen Härtungs-Baustein
  + Ort nicht UTC+0), nicht am Prüfling.
- **R3 — Zwei Vorlauf-Varianten.** Trip ≠ Compare (3-h-Fenster vs. Stundengleichheit, 7 vs. 6
  Uhr). Ein Wächter, der nur eine kennt, lässt die andere durch.
- **R4 — Der Wächter bewacht Tests, nicht das Produkt.** Dieselbe Warnung wie bei #1667 S1:
  aus „die Ratsche ist grün" folgt nichts über die Zuverlässigkeit der Alarme.
- **R5 — Bestandssanierung sprengt das LoC-Budget.** 107 Kandidatendateien lassen sich nicht in
  einem Workflow umstellen (250 Prod / 500 Test). Zuschnitt in Scheiben ist wahrscheinlich
  nötig; Reihenfolge und Abbruchgrenze gehören in die Spec.
- **R6 — Testpfade sind hart verdrahtet** in `.github/ci_tdd_excludes.txt`, Collection-Meta-Tests
  und den Ratschen. Massen-Umbenennung ist untersagt (Tech-Lead-Entscheid 2026-08-08); Härtung
  darf Dateinamen nicht anfassen.

## Analysis (Phase 2)

### Type

Bug (Label `bug`, `priority:high`, `session:khw`) — Fehlerklasse, nicht Einzelfall.

### Die Bestandsmenge wurde gemessen, nicht geschätzt

Messaufbau: `freezegun` stellt die Uhr, **ein frischer Prozess je Datenpunkt**, Testdateien
namentlich benannt, `--allow-hosts=127.0.0.1,::1`. Befund ist immer nur die **Differenz**
zwischen zwei Uhrzeiten — ein einzelner roter Lauf zählt nicht.

| Menge | Uhrzeiten | Differenz |
|---|---|---|
| 69 Dateien: Etappe + Wanduhr + Alarmpfad, **ohne** Ankunftszeiten, **ohne** Härtungs-Helfer | 06:00 / 10:00 / 18:00 / 22:30 UTC | **0** |
| 100 Dateien: Etappe + Wanduhr + Alarmpfad, **ohne** `briefing_zeiten`-Helfer | 06:00 / 12:00 UTC | **1** |

🔴 **Das Ergebnis widerlegt die Arbeitsannahme des Tickets.** Die obere Schranke von 107
Kandidaten enthält **einen** tatsächlich zeitabhängigen Testfall. Die frühere Vermutung, es
liege ein großer sanierungsbedürftiger Bestand vor, ist damit gemessen und falsch: die
betroffenen Dateien wurden von #1667 S1, #1697, #1851 und #1858 bereits gehärtet. **Eine
Massensanierung ist nicht nötig** — Risiko R5 aus Phase 1 entfällt.

### Der eine verbliebene Fund — reproduzierbar, auf heutigem `main`

`tests/unit/test_alarm_zeitfenster_ziel.py::test_radarpfad_spaetankunft_faellt_nicht_in_alle_segmente_vorbei`

| Uhrzeit (UTC) | 00 | 02 | 03 | **04** | **05** | **06** | 07 | 08 | 10–22 |
|---|---|---|---|---|---|---|---|---|---|
| Ergebnis | grün | grün | grün | **rot** | **rot** | **rot** | grün | grün | grün |

Je zwei Läufe pro Datenpunkt, deterministisch. Fehlerbild: `assert []` — „F003: Bei
Spätankunft muss der Radar-Pfad einen Alarm zustellen." Protokollzeile des Prüflings:
`Ziel-Segment: Ankunft 2026-08-16T02:27:00+00:00 liegt nach dem Tagesfenster-Ende (2:00
Ortszeit) — minimales Fenster von 1 h wird verwendet`.

Der Mechanismus ist **nicht** die Vorlaufsperre aus #1851, sondern die Ortswahl-Kompensation
der Fixture selbst (`_radar_mails_fuer_spaetankunft`, steht als einer von zwei Einträgen in
`KNOWN_VIOLATIONS` der bestehenden Ratsche): sie setzt `day_window_end_hour` auf die
Ankunftsstunde, wodurch das Fensterende vor der Ankunft liegt, der Randfall-Guard greift und das
Ziel-Segment in einem 3-Stunden-Band nicht mehr als aktiv gilt.

**Unabhängige Bestätigung aus der Wirklichkeit:** die Beweistabelle in
`fix_1851_alarm_tests_vorlaufsperre.md` verzeichnet einen echten roten CI-Lauf am
**2026-08-15 um 05:29 UTC** — mitten im hier gemessenen Band. Die Messung stützt sich also nicht
allein auf `freezegun`.

🔴 **Und sie belegt die These des Tickets an einem konkreten Fall:** #1851 hat für diese Datei
AC-1 formuliert („alle 12 Testfälle grün, unabhängig von der realen Wanduhrzeit") und
ausdrücklich begründet, ein einziger Lauf genüge als Nachweis, „es gibt keine Kippkante mehr".
Für elf Fälle stimmt das; für den zwölften ist es messbar falsch. Genau davor warnt #1709:
*„Ein einzelner grüner Lauf um 10:00 UTC beweist hier nichts."*

### Drei Fallen im Messaufbau (selbst hineingelaufen, deshalb dokumentiert)

1. **Ein Prozess für mehrere Messpunkte ist ungültig.** 24 aufeinanderfolgende `pytest.main()`
   im selben Prozess ergaben eine Matrix (rot 02–04 Uhr), die sich bei frischen Prozessen nicht
   reproduzieren ließ (rot 04–06 Uhr). Zustand sickert zwischen Läufen durch. Jeder Datenpunkt
   braucht einen eigenen Prozess.
2. **Sitzungsweites `freezegun` zerstört pydantic-v1-Importe** (`TypeError: metaclass conflict`
   in `pydantic/v1/types.py:1180`). Das erzeugt 9 Falsch-Positive, die wie Zeitabhängigkeit
   aussehen. `extend_ignore_list=['pydantic']` behebt es nicht. Nur die **Differenz** zweier
   Läufe ist deshalb auswertbar, nie eine absolute Fehlerzahl.
3. **Sammelläufe verdecken die Ursache.** Im 100-Dateien-Batch war der Fund um 06:00 rot; einzeln
   gemessen liegt seine Kante bei 04–06 Uhr. Batch-Ergebnisse taugen zum Eingrenzen, nicht zum
   Belegen — die Kante gehört einzeln nachgemessen.

### Technischer Ansatz (Empfehlung)

**Zwei Bestandteile, ein Workflow:**

1. **Der Fund wird behoben** — die Fixture `_radar_mails_fuer_spaetankunft` kommt aus
   `KNOWN_VIOLATIONS` heraus oder wird so umgebaut, dass ihre Zusicherung erhalten bleibt und
   das Band 04–06 UTC verschwindet. Das ist der Fang-Beleg, ohne den die neue Regel nach dem
   Regel-Budget am Prüfdatum zurückgebaut werden müsste.
2. **Die Ratsche bekommt eine zweite, eigenständige Fundregel** an der **Fixture-Bauart**
   festgemacht (statisch entscheidbar), nicht am Prüfling (nicht entscheidbar): baut eine
   Etappe aus einem Wanduhr-Datum **und** nutzt weder ein Härtungs-Helferlein noch eine
   UTC+0-Koordinate **und** liegt in einer Datei, die den Alarmpfad importiert.
3. **Das Messwerkzeug wird versioniert**, nicht weggeworfen — sonst ist der Nachweis „zu zwei
   Uhrzeiten gleich" bei der nächsten Änderung wieder Handarbeit. Es ist zugleich die einzige
   Form, in der die *indirekte* Variante überhaupt beweisbar ist.

**Verworfen:** eine Fundregel, die versucht zu erkennen, ob der Prüfling eine Tageszeit-Grenze
auswertet. Das ist syntaktisch nicht entscheidbar (das Ticket räumt es ein) und würde bei acht
gemessenen Kippkanten-Familien in verschiedenen Modulen zu einer Regel führen, die entweder
alles oder nichts meldet.

### Scope Assessment

- Dateien: ~4 (Ratsche, Attrappen-Vorlage, Messwerkzeug, die eine Fixture)
- Geschätzte LoC: Produktiv +0 / Test ca. +250
- Risiko: **MEDIUM** — kein Produktivcode berührt; Hauptrisiko ist eine zu weite Fundregel (R1)

### Offene Frage für die Spec

Der gemessene Fund liegt in einer Fixture, die **bewusst** in `KNOWN_VIOLATIONS` steht, mit
ausführlicher Begründung und einem eigenen 1440-Minuten-Wächter
(`test_radar_fixture_ist_zu_jeder_tageszeit_kein_mitternachtsfenster`). Dieser Wächter ist grün
und der Test trotzdem in einem 3-Stunden-Band rot — er bewacht also eine andere Eigenschaft als
die, auf die es ankommt. Die Spec muss entscheiden, ob die Fixture umgebaut oder der
1440-Minuten-Wächter auf die richtige Eigenschaft umgestellt wird.
