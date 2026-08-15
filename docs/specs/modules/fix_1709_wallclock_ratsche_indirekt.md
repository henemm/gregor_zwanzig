---
entity_id: fix_1709_wallclock_ratsche_indirekt
type: bugfix
created: 2026-08-15
updated: 2026-08-15
status: draft
workflow: fix-1709-wallclock-ratsche-indirekt
version: "1.0"
tags: [issue-1709, tests, fixtures, ratsche, wanduhr, ci-ampel, freezegun]
---

# Indirekte Wanduhr-Abhängigkeit: messbar machen und dauerhaft bewachen

## Approval

- [x] Approved — PO „freigabe" 2026-08-15

## Purpose

Die bestehende Ratsche `tests/tdd/test_fixture_wallclock_ratchet.py` meldet einen Fund nur,
wenn eine Fixture **beides** tut: das Etappendatum aus der Wanduhr bilden **und** eine
ungeklemmte Ankunftszeit aus `(now ± timedelta).strftime("%H:%M")` setzen. Die Variante, die
am 2026-08-10 drei Sitzungen einen Abend gekostet hat, ist das **logische Gegenteil**: sie
setzt gar keine Ankunftszeiten, wodurch der Prüfling eine Tageszeit-Grenze selbst berechnet.
Diese Variante kann der bestehende Scanner strukturell nicht sehen.

Diese Spec liefert zwei Dinge, die zusammengehören: ein **versioniertes Messwerkzeug**, mit
dem sich indirekte Zeitabhängigkeit überhaupt erst beweisen lässt, und eine **zweite,
eigenständige Fundregel** in der Ratsche, die neue Fixtures dieser Bauart beim Commit stoppt.

> **Schicht-Hinweis:** Ausschließlich Testinfrastruktur (`tests/`). **Kein** Eingriff in
> `src/`, `api/`, `internal/`, `frontend/`, `cmd/` — s. AC-7.

## Source

- **Issue:** #1709
- **Files:** `tests/tdd/test_fixture_wallclock_ratchet.py` (Erweiterung),
  `tests/fixtures/ratchet_cases/` (Attrappen), neues Messwerkzeug unter `tests/helpers/`
- **Nicht Gegenstand:** #1871 (der konkrete rote Testfall) — PO-Entscheidung 2026-08-15,
  getrennt zu halten, damit beide Teile einzeln nachweisbar sind

### Die Fehlerklasse, am Code nachgemessen

Zeilenangaben im Ticket sind veraltet; hier der Stand bei `b6674c94`, selbst nachgemessen:

1. `src/app/day_window.py:16-17` — `DAY_WINDOW_START_HOUR = 4`, `DAY_WINDOW_END_HOUR = 19`.
2. `src/services/trip_segments.py:265-278` — das Ziel-Segment endet bei
   `combine(arrival_local_date, time(end_hour))` in der **Ortszone des Ziels**.
3. `src/services/trip_alert.py:1244-1245` und `:1411` — beide filtern
   `segment.end_time < now_utc` als „bereits absolviert" weg.

Bei den im Bestand dominierenden Fixture-Koordinaten `47.0 / 11.0` (Europe/Vienna, sommers
UTC+2) ist 19:00 Ortszeit **exakt 17:00 UTC**. Der Test sieht harmlos aus; die
Zeitabhängigkeit entsteht erst im Prüfling.

**Korrektur zum Ticket:** Die dort als Ursache genannte 23:59-Klemme in `src/core/naismith.py`
**existiert nicht mehr** — seit #1667 S2 rechnet `_format_hhmm()` (Z. 54-73) mit
`total_min % (24*60)`.

### Die Bestandsmenge ist gemessen, nicht geschätzt

| Menge | Uhrzeiten (UTC) | Differenz |
|---|---|---|
| 69 Dateien: Etappe + Wanduhr + Alarmpfad, ohne Ankunftszeiten, ohne Härtungs-Helfer | 06/10/18/22:30 | **0** |
| 100 Dateien: Etappe + Wanduhr + Alarmpfad, ohne `briefing_zeiten`-Helfer | 06/12 | **1** |

🔴 **Die im Ticket befürchtete Massensanierung entfällt.** Die obere Schranke von 107
Kandidaten enthält genau **einen** zeitabhängigen Testfall (→ #1871). Die übrigen wurden von
#1667 S1, #1697, #1851 und #1858 bereits gehärtet. Das ist gemessen, nicht gelesen.

### Das Härtungs-Kit existiert bereits

| Kippkante | Baustein | Wirkung |
|---|---|---|
| Tagesfenster | `tests/helpers/arrival_window_fixtures.py::active_window_offsets` | Ankunft im aktiven Fenster, monoton, auf dem Etappentag |
| Ortstag ≠ Serverdatum | dieselbe Datei, `stage_date(lat, lon)` | Etappendatum = Ortstag, dieselbe Formel wie der Prüfling |
| Briefing-Vorlaufsperre | `tests/helpers/briefing_zeiten.py::briefing_zeiten_fuer_trip` | Briefingzeiten relativ zur echten Uhr, außerhalb des Vorlaufs |
| alle | Koordinate `64.13 / -21.90` (`Atlantic/Reykjavik`, UTC+0 ohne Sommerzeit) | Ortstag ≡ UTC-Tag |

Zielform vollständig: `tests/tdd/test_briefing_anchor_survives_dispatch_failure.py:178-205`.
**Die Aufgabe ist deshalb nicht „eine Härtung erfinden", sondern „die vorhandene erzwingen".**

## Scope

### Gewählte Lösung

**1. Messwerkzeug (`tests/helpers/wanduhr_matrix.py`, neu).** Eine Funktion, die eine oder
mehrere Testdateien zu mehreren gestellten Uhrzeiten laufen lässt und die **Differenz** der
Fehlermengen zurückgibt.

Drei Eigenschaften sind zwingend, alle drei sind bei der Analyse teuer gelernt worden:

- **Ein frischer Prozess je Datenpunkt.** Mehrere `pytest.main()`-Aufrufe im selben Prozess
  ergaben eine Matrix (rot 02–04 UTC), die sich bei frischen Prozessen nicht reproduzieren
  ließ (rot 04–06 UTC). Zustand sickert zwischen Läufen durch.
- **Nur die Differenz ist auswertbar, nie eine absolute Fehlerzahl.** Sitzungsweites
  `freezegun` zerstört pydantic-v1-Importe (`TypeError: metaclass conflict`,
  `pydantic/v1/types.py:1180`) und erzeugt so 9 Falsch-Positive.
  `extend_ignore_list=['pydantic']` behebt das nicht.
- **Uhrzeiten in der Ortszone der Fixture wählen, nicht in UTC.** Wer die Grenzen in UTC
  notiert, sucht bei fremder Zone an der falschen Stelle.

**2. Zweite Fundregel in der Ratsche.** Sie macht an der **Fixture-Bauart** fest, nicht am
Prüfling. Fund, wenn **alle** Merkmale zugleich zutreffen:

- die Funktion baut eine Etappe mit **mindestens zwei** Wegpunkten, **und**
- das Etappendatum stammt aus der Wanduhr (dieselbe Erkennung wie die bestehende Regel,
  `_ist_wanduhr_datum`), **und**
- **kein** Wegpunkt trägt `arrival_calculated` **oder** `arrival_override`, **und**
- `stage.start_time` ist nicht gesetzt, **und**
- die Datei nutzt **weder** `arrival_window_fixtures` **noch** `briefing_zeiten`, **und**
- die Datei importiert einen zeitgrenzen-auswertenden Pfad (`trip_alert`, `compare_alert`,
  `trip_report_scheduler`, `compare_slot_scheduler`, `alert_gate`, `deviation_alert`,
  `alert_daily_limit`, `official_alert`).

Die ersten vier Merkmale sind **am Prüfling abgelesen**, nicht geraten
(`src/services/trip_segments.py`, HEAD `b6674c94`):

| Merkmal | Belegstelle | Warum es die Immunität entscheidet |
|---|---|---|
| ≥ 2 Wegpunkte | `:121-123` — `if len(stage.waypoints) < 2: return []` | Eine Ein-Wegpunkt-Etappe erzeugt **gar kein Segment**; es gibt nichts, das „vorbei" sein könnte |
| kein `arrival_calculated` | `:125-127` — Self-Heal-Auslöser ist `all(wp.arrival_calculated is None …)` | Nur dann rechnet Naismith überhaupt und setzt den 08:00-Standardstart |
| kein `arrival_override` | `:36-52` `_known_time_for_index`, Kette `arrival_override > stage.start_time (idx 0) > arrival_calculated` | 🔴 `arrival_override` **gewinnt**, auch wenn der Self-Heal gelaufen ist — eine Fixture mit durchgängigem `arrival_override` ist immun, obwohl sie den Auslöser erfüllt |
| kein `stage.start_time` | `:132` — `default_start = stage.start_time if stage.start_time else time(8, 0)` | Ein gesetzter Etappenstart ersetzt den 08:00-Standard |

Das letzte Merkmal (Alarmpfad-Import) ist die Näherung an die nicht entscheidbare Frage
„wertet der Prüfling eine Tageszeit aus?". Sie ist bewusst **grob**: sie schaut auf Importe der
Datei, nicht auf Aufrufketten.

**Verworfen:** eine Fundregel, die den Prüfling analysiert. Bei acht gemessenen
Kippkanten-Familien in verschiedenen Modulen führte das zu einer Regel, die entweder alles
oder nichts meldet. Das Ticket erlaubt den begründeten Ansatzwechsel ausdrücklich.

### Affected Files

| Datei | Change | Beschreibung |
|---|---|---|
| `tests/helpers/wanduhr_matrix.py` | CREATE | Messwerkzeug: Differenz-Messung über Uhrzeiten, ein Prozess je Punkt |
| `tests/tdd/test_wanduhr_matrix.py` | CREATE | Selbsttests des Messwerkzeugs inkl. Gegenprobe (AC-3) |
| `tests/tdd/test_fixture_wallclock_ratchet.py` | MODIFY | Zweite Fundregel `scan_indirekte_wanduhr_fixtures()` + Selbsttests |
| `tests/fixtures/ratchet_cases/indirekte_wanduhr_faelle.py.txt` | CREATE | Attrappen außerhalb der Scanfläche |
| Produktivcode | — | **unverändert** (AC-7) |

### Estimated Changes

- Dateien: 4
- LoC: Produktiv +0 / −0, Test ca. +260 / −5

## Acceptance Criteria

- **AC-1 (die neue Fundregel meldet das Anti-Muster):** Given eine Attrappen-Datei, die eine
  Etappe mit Wanduhr-Datum **ohne** Ankunftszeiten baut, keinen Härtungs-Helfer nutzt und
  `trip_alert` importiert / When `scan_indirekte_wanduhr_fixtures(tmp_path)` darüber läuft /
  Then meldet es genau diese Funktion mit Datei, Funktionsname und Zeile.
  - Test: `test_scanner_meldet_die_indirekte_variante` gegen eine echte Datei auf `tmp_path`.

- **AC-2 (Gegenprobe — der Scanner schweigt bei jeder immunen Bauart, wichtigster AC):**
  Given sieben Attrappen, die je **eines** der Fund-Merkmale nicht erfüllen — (a) nur **ein**
  Wegpunkt, (b) `arrival_calculated` gesetzt, (c) **`arrival_override`** gesetzt (bei
  `arrival_calculated = None`), (d) `stage.start_time` gesetzt, (e) `arrival_window_fixtures`
  genutzt, (f) `briefing_zeiten` genutzt, (g) kein Alarmpfad-Import / When der Scanner darüber
  läuft / Then meldet er **keine** davon.
  - Test: sieben benannte Testfunktionen, je `assert not funde`. Ohne diesen AC wäre eine Regel
    zulässig, die einfach alles meldet — genau das Übel, das #1709 als „fälschlich
    blockierendes Gate" anprangert. **Fall (c) ist der heikelste:** diese Fixture erfüllt den
    Self-Heal-Auslöser (`arrival_calculated is None`) und ist trotzdem immun, weil
    `arrival_override` in `_known_time_for_index` gewinnt. Eine Regel, die nur auf
    `arrival_calculated` schaut — wie der erste Entwurf dieser Spec —, meldet sie fälschlich.

- **AC-3 (das Messwerkzeug erkennt eine bekannte Zeitabhängigkeit — Wirksamkeitsbeleg):**
  Given eine Attrappe, deren Testfall bei gestellter Uhr vor einer festgelegten Stunde grün und
  danach rot ist / When das Messwerkzeug sie zu beiden Uhrzeiten misst / Then meldet es genau
  diesen Testfall als Differenz, und bei zwei Uhrzeiten **derselben** Seite der Grenze meldet
  es eine leere Differenz.
  - Test: `test_matrix_findet_die_kante` + `test_matrix_meldet_nichts_ohne_kante`. Ein Werkzeug,
    das nie etwas findet, ist von einem sauberen Bestand nicht unterscheidbar — dieser AC ist
    der Unterschied zwischen „nichts gefunden" und „nichts da".

- **AC-4 (frischer Prozess je Datenpunkt ist erzwungen, nicht empfohlen):** Given das
  Messwerkzeug / When es zwei Uhrzeiten misst / Then läuft jeder Datenpunkt in einem eigenen
  Betriebssystem-Prozess.
  - Test: ein Testfall lässt das Werkzeug zweimal dieselbe Attrappe messen und prüft, dass die
    beobachteten Prozesskennungen (`os.getpid()`, von der Attrappe in eine Datei geschrieben)
    paarweise verschieden und vom Messprozess verschieden sind. Ein Kommentar „bitte frischen
    Prozess nehmen" wäre keine Zusicherung, sondern eine Bitte.

- **AC-5 (der echte Testbaum erzeugt keinen Fehlalarm):** Given der Scanner läuft über den
  echten Baum `tests/` / When die Fundmenge gebildet wird / Then ist sie leer oder vollständig
  durch `KNOWN_VIOLATIONS` gedeckt, **und** die Zahl der geprüften Kandidatenfunktionen ist
  ≥ 20.
  - Test: `test_echter_testbaum_ohne_fehlalarm`. Die Untergrenze verhindert, dass ein leerer
    Scan durch eine kaputte Kandidatensuche vorgetäuscht wird — ohne sie wäre der AC durch
    „finde gar nichts" trivial erfüllbar.

- **AC-6 (Ausnahmeliste kann nur schrumpfen):** Given `KNOWN_VIOLATIONS` der neuen Regel /
  When der Scanner über den echten Baum läuft / Then enthält die Liste keinen Eintrag, den der
  Scanner nicht mehr findet.
  - Test: `test_known_violations_der_neuen_regel_ohne_veraltete_eintraege`, Muster der
    bestehenden Regel (Z. 544-553). **Bewusste Grenze, wie beim Vorbild:** gegen *neue*
    unbegründete Einträge kann sich eine Ausnahmeliste strukturell nicht selbst schützen —
    das bleibt review-pflichtig und wird hier nicht als gelöst behauptet.

- **AC-7 (Nicht-Wirkung, Produktivcode unangetastet):** Given der vollständige Diff dieser
  Scheibe / When `git diff --stat origin/main...HEAD -- src/ api/ internal/ frontend/ cmd/`
  läuft / Then ist die Ausgabe leer.
  - Test: struktureller Nachweis im PR, kein eigener Pytest-Test.

- **AC-8 (Regel-Budget maschinell auffindbar):** Given die neue Regel / When die Datei nach dem
  Prüfdatum durchsucht wird / Then steht `2026-11-10` als Text in der Datei und als Konstante.
  - Test: `test_regel_budget_pruefdatum_der_neuen_regel_steht_als_text`, Muster der bestehenden
    Regel (Z. 663-672).

- **AC-9 (die Ratsche läuft in der CI-Ampel):** Given `.github/ci_tdd_excludes.txt` nach dieser
  Scheibe / When darin nach `test_fixture_wallclock_ratchet` und `test_wanduhr_matrix` gesucht
  wird / Then kommt keiner der beiden Namen vor.
  - Test: `test_neue_waechter_sind_nicht_von_der_ci_ausgenommen` — ein Wächter, der nicht läuft,
    ist kein Wächter.

## Test Plan

### Automated Tests (TDD RED)

- [ ] AC-1: `test_scanner_meldet_die_indirekte_variante`
- [ ] AC-2: sieben Gegenproben-Testfunktionen (1 Wegpunkt / `arrival_calculated` / `arrival_override` / `stage.start_time` / beide Helfer / kein Alarmpfad)
- [ ] AC-3: `test_matrix_findet_die_kante`, `test_matrix_meldet_nichts_ohne_kante`
- [ ] AC-4: `test_matrix_nutzt_je_datenpunkt_einen_eigenen_prozess`
- [ ] AC-5: `test_echter_testbaum_ohne_fehlalarm` (inkl. Kandidaten-Untergrenze)
- [ ] AC-6: `test_known_violations_der_neuen_regel_ohne_veraltete_eintraege`
- [ ] AC-8: `test_regel_budget_pruefdatum_der_neuen_regel_steht_als_text`
- [ ] AC-9: `test_neue_waechter_sind_nicht_von_der_ci_ausgenommen`

### Mutations-Gegenprobe (Pflicht)

Mindestens diese Verfälschungen müssen einen Test rot machen:

1. Jedes einzelne Fund-Merkmal aus der `UND`-Kette entfernen (sieben Mutationen) → jeweils muss
   der zugehörige AC-2-Fall rot werden. Bleibt einer grün, ist dieses Merkmal unbewacht.
2. Die Kandidaten-Untergrenze in AC-5 entfernen → eine kaputte Kandidatensuche muss auffallen.
3. Im Messwerkzeug den frischen Prozess durch einen Aufruf im selben Prozess ersetzen → AC-4
   muss rot werden.
4. `KNOWN_VIOLATIONS` um einen erfundenen Eintrag ergänzen → AC-6 muss rot werden.

## Known Limitations

- **Der Wächter bewacht Tests, nicht das Produkt.** Wie bei #1667 S1 gilt: aus „die Ratsche ist
  grün" folgt nichts über die Zuverlässigkeit der Alarme.
- **Das letzte Fund-Merkmal ist eine Näherung.** Geprüft werden Importe der Datei, nicht
  Aufrufketten. Eine Fixture, die den Alarmpfad über einen Umweg erreicht, wird nicht erkannt.
  Die Gegenrichtung — eine Datei importiert den Alarmpfad für einen anderen Testfall — führt zu
  einem Fund, der über `KNOWN_VIOLATIONS` oder Härtung aufzulösen ist.
- **Nur Python.** Go-seitige Zeitfenster (`internal/scheduler/`, `internal/store/`) sind nicht
  Gegenstand.
- **Latente Fixtures werden bewusst nicht gemeldet.** Es gibt Dateien, die das Anti-Muster
  strukturell bauen, deren Testpfad den Alarmpfad aber nie erreicht (geprüft:
  `test_bug_775_email_trip_lookup.py`, `test_inbound_telegram_reader.py`,
  `test_inbound_gate_errors.py` — reine Inbound-/Zuordnungstests). Sie sind heute immun und
  bleiben unauffällig; kommt später ein Alarmpfad-Import dazu, meldet die Regel sie ab dann.
  Das ist gewollt: eine Regel, die auch latente Fälle meldet, wäre die zu weite Variante aus R1.
- **Vier Kippkanten-Familien bleiben unbewacht:** Ruhezeit (nutzergesetzt, Default aus),
  Tageszähler-Reset an Ortsmitternacht, Nowcast-Horizont und die Go-Seite. Sie sind im
  Kontext-Dokument vermessen, aber keine dieser Familien hat bislang einen Fang belegt.
- **Der konkrete rote Testfall wird hier NICHT behoben** (#1871, Ursache offen). Diese Scheibe
  liefert das Werkzeug, mit dem er gefunden wurde, und den Wächter gegen Neuzugänge.
- **Aufrufer/Geschwister-Split bewusst nicht geschlossen (Adversary-Finding F-ADV2, Runde 2).**
  Wird das Wanduhr-Datum im **Aufrufer** berechnet und als Parameter an eine **Geschwister**-
  Funktion übergeben, die ihrerseits `Stage(...)` baut, sieht keine der beiden Funktionen für
  sich beide Merkmale zugleich — die zweite Fundregel prüft ausschließlich innerhalb einer
  Funktion, Rückgabewerte/Parameter über Funktionsgrenzen hinweg werden nicht verfolgt (teuer,
  s. Grenzen-Abschnitt im Docstring von `test_fixture_wallclock_ratchet.py`). Diese Struktur ist
  im Bestand bereits **etabliert**: `tests/tdd/test_issue_760_stage_number.py:31` (Helferfunktion
  `_stage(..., d: date)`, die das Datum als Parameter entgegennimmt und `Stage(date=d, ...)`
  baut) ist heute nur deshalb ungefährlich, weil dort ausschließlich mit **einem** Wegpunkt
  gebaut wird — eine Erweiterung dieser Helferfunktion auf **zwei** Wegpunkte würde dort bereits
  genügen, um die Ratsche zu umgehen. #1709 erlaubt der Regel ausdrücklich, eine Näherung zu
  bleiben; diese Grenze ist damit bewusst offen, nicht gelöst.

## Nachtrag 2026-08-15: Härtung von zehn Bestandsdateien kam hinzu (PO-Entscheidung)

Die ursprüngliche Fassung schrieb „keine Sanierung von Bestandsdateien (gemessen: nicht nötig)".
Das war für die **Wirkung** richtig und für die **Bauart** falsch — ein Unterschied, der beim
Schreiben der Spec nicht gesehen wurde.

Der fertige Scanner meldete elf Bestandsstellen. Alle zehn betroffenen Dateien wurden mit dem
in dieser Scheibe entstandenen Werkzeug zu vier Uhrzeiten (05/12/18/23 UTC) nachgemessen:
**keine einzige ist zeitabhängig**. Sie bauen das Anti-Muster, ihre Prüfaussagen hängen aber
nicht daran — latent, nicht defekt.

Der erste Implementierungsversuch trug die elf Stellen in `KNOWN_VIOLATIONS_INDIREKT` ein, um
den Wächter grün zu bekommen. **Das ist zurückgenommen.** Die Regel neben der bestehenden Liste
verbietet es wörtlich („darf NICHT gefuellt werden, um den Waechter gruen zu bekommen";
„Umstellen waere aufwendig" ist kein Grund), und ein Wächter mit elf Ausnahmen bewacht nur noch
Neuzugänge — weniger, als freigegeben wurde.

**PO-Entscheidung 2026-08-15:** die zehn Fixturen werden auf das vorhandene Härtungs-Kit
umgestellt, `KNOWN_VIOLATIONS_INDIREKT` bleibt **leer**. Bedingungen: keine `assert`-Zeile wird
angefasst (geändert wird die Vorbedingung, nicht die Zusicherung), jede Datei bleibt einzeln
grün, und jede wird vor und nach der Härtung mit `matrix_differenz` gegengemessen.

Betroffen: `test_alert_state_briefing_reset.py`, `test_alert_undelivered_hint.py`,
`test_import_und_fremdquellen_folgen_ortstag.py`, `test_issue_1069_tier_channel_gating.py`
(zwei Funktionen), `test_official_alert_channel_threshold.py`,
`test_official_alert_sms_marker.py`, `test_trip_alert_channel_precedence.py`,
`test_trip_briefing_anchor_unchanged.py`, `test_trip_outlook_dispatch_mail.py`,
`tests/unit/test_premium_sms_versand.py`.

**Zusätzliches Kriterium aus diesem Nachtrag:**

- **AC-10 (die Ausnahmeliste der neuen Regel bleibt leer):** Given
  `KNOWN_VIOLATIONS_INDIREKT` nach dieser Scheibe / When der Scanner über den echten Baum
  `tests/` läuft / Then ist die Liste leer **und** die Fundmenge leer — der Wächter ist ohne
  jede Ausnahme grün.
  - Test: `test_known_violations_der_neuen_regel_ist_leer`; Assert
    `KNOWN_VIOLATIONS_INDIREKT == frozenset()` und `scan_indirekte_wanduhr_fixtures(TESTS_ROOT) == []`.

**LoC-Budget:** zunächst auf 1000 Testzeilen angehoben (PO-Erlaubnis 2026-08-15), nach der
Fix-Schleife auf **1300** (zweite PO-Erlaubnis am selben Tag). Der größte Block sind die
Attrappen und inzwischen elf Gegenproben — also genau die Nachweise, die den Wächter davor
bewahren, alles zu melden. Kürzen hätte die Zusicherung geschwächt.

🔴 **Das LoC-Gate hat die erste Überschreitung nicht bemerkt** (Anzeige `+0/1000`, tatsächlich
1252 Testzeilen). Es misst hier den falschen Stand — dieselbe Schwäche, die als
Phantom-Delta bekannt ist. Die Überschreitung wurde deshalb von Hand gemeldet und freigegeben,
nicht vom Gate erzwungen. Wer sich hier auf die Anzeige verlässt, hat kein Budget.

## Nicht in dieser Scheibe

- Keine Sanierung über die zehn oben genannten Dateien hinaus.
- Kein Eingriff in `src/`, `api/`, `internal/`, `frontend/`, `cmd/`.
- Keine Änderung an der bestehenden ersten Fundregel oder ihrer `KNOWN_VIOLATIONS`.
- Keine Bewertung des 1440-Minuten-Wächters `test_radar_fixture_ist_zu_jeder_tageszeit_…`
  (gehört zu #1871).

## Regel-Budget

**Prüfdatum: 2026-11-10** (aus dem Ticket übernommen).

Fang-Beleg bei Einführung: Das Messwerkzeug hat #1871 gefunden — einen Testfall, der auf
`main` täglich drei Stunden lang rot ist und den fünf grüne CI-Läufe zuvor nicht auffällig
gemacht hatten. Am Prüfdatum: hat die **Fundregel** (nicht das Werkzeug) mindestens eine neue
Fixture dieser Bauart gestoppt? Kein Fang → Rückbau der Regel, Werkzeug bleibt.

## Changelog

- 2026-08-15: Initial spec created
- 2026-08-15: Nachtrag — Härtung von zehn Bestandsdateien aufgenommen, AC-10 ergänzt,
  LoC-Budget auf 1000 Testzeilen angehoben (beides PO-Entscheidung nach der Messung)
