---
entity_id: fix_2314_ci_zeitzonen_riss
type: bugfix
created: 2026-09-14
updated: 2026-09-14
status: draft
version: "1.0"
tags: [tests, ci, zeitzone, issue-2314]
---

<!-- Issue #2314 — CI-Job `test` ist taeglich 22:00-02:30 UTC strukturell rot
     (144 Fehler / 38 Dateien), unabhaengig vom PR-Inhalt. -->

# Fix #2314 — CI-Zeitzonen-Riss: Test-Fixtures datieren nach Ortstag statt Prozesstag

## Approval

- [ ] Approved

## Purpose

Der CI-Job `test` blockiert taeglich zwischen 22:00 und 02:30 UTC jeden PR, unabhaengig von
dessen Inhalt (144 Fehler in 38 Dateien). Ursache ist **kein Produktivcode-Defekt**: 38
Testdateien datieren Trip-Etappen mit `date.today()` — dem Kalendertag der **Prozesszone**
`America/St_Johns` (Root-`conftest.py`, Wächter #1402) — platzieren die Trips aber auf
Koordinaten in anderen Zonen (ueberwiegend Tirol/UTC+2). Das Produkt rechnet den Kalendertag
absichtlich und korrekt in der **Ortszone der Trip-Koordinaten** (`trip_local_today`, ADR-0044).
Springt der Ortstag vor Mitternacht Prozesszone, vergleichen die Tests gegen den falschen Tag.
Diese Lieferung stellt die Fixtures auf den Ortstag um und macht die Suite damit uhrzeitunabhaengig
— ohne die Prozesszonen-Fixierung (#1402) oder Produktivcode anzutasten.

## Source

- **File:** `tests/helpers/ortstag.py` (NEU)
- **Identifier:** `ortstag(lat: float, lon: float, *, now_utc: datetime | None = None) -> date`
  — delegiert an `src/utils/timezone.py::tz_for_coords()` (keine eigene Zonenarithmetik).
  Wo bereits ein `Trip`-Objekt existiert, ist `src/services/trip_day.py::anchor_tz(trip, now_utc)`
  gleichwertig zulaessig (bestehendes Muster, siehe `tests/helpers/briefing_zeiten.py:57-69`).

> **Schicht-Hinweis:** reines Test-Infrastruktur-Artefakt (`tests/`). Produktivcode
> (`src/`, `api/`, `internal/`, `frontend/`) wird ausschliesslich gelesen (als Wahrheitsquelle
> fuer die Zonenberechnung), nicht veraendert.

## Estimated Scope

- **LoC:** ca. +220/-150 (viele 1-3-Zeilen-Diffs in Testdateien) — `loc_limit_override 500`
  vor `/40-tdd-red` setzen.
- **Files:** ~40 (1 neu: `tests/helpers/ortstag.py`; ~39 MODIFY, davon 3 Fixture-Helfer mit
  vielen Importeuren + ~35 rote Testdateien direkt)
- **Effort:** medium

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `src/utils/timezone.py::tz_for_coords(lat, lon)` | Wahrheitsquelle | liefert die `ZoneInfo` zu Koordinaten; der neue Helfer delegiert vollstaendig dorthin, keine eigene Zonenlogik |
| `src/services/trip_day.py::anchor_tz(trip, now_utc)` | gleichwertige Alternative | wo schon ein `Trip` existiert (Muster bereits in `tests/helpers/briefing_zeiten.py:57-69`) |
| Root-`conftest.py:1-24` (#1402) | unveraendert | Prozesszonen-Fixierung `America/St_Johns` bleibt bestehen — sie deckt den Fehler auf, ist nicht die Ursache |
| `tests/conftest.py:579-627` + `tests/helpers/wanduhr.py` (`GZ_TEST_WALL_CLOCK_UTC`, #2096) | Nachweiswerkzeug | stellt die Wanduhr fuer den gesamten Lauf auf eine feste UTC-Uhrzeit, ohne Systemzeit anzufassen |
| `tests/helpers/wanduhr_matrix.py::lauf_bei_uhrzeit()` (#1709) | Nachweiswerkzeug | fuehrt eine Testdatei je Uhrzeit in einem frischen Subprozess aus und liefert das Ergebnis je Test zurueck — Grundlage fuer den Vorher/Nachher-Nachweis |
| `tests/tdd/test_fixture_wallclock_ratchet.py` (#1667) | bestehende Ratsche, spaeter erweiterbar | AST-Scanner gegen ein verwandtes Wanduhr-Anti-Muster in Fixtures — Erweiterung um „`date.today()` als Etappendatum" ist **nicht** Teil dieser Lieferung (Regel-Budget), sondern Checkbox in Sammel-Issue #1196 |
| `docs/adr/0044-…md` (Kalendertag = Ortszeit) | inhaltliche Grundlage | traegt die Entscheidung, gegen die die Fixtures bisher falsch liefen |

## Implementation Details

### Neuer Helfer

```python
# tests/helpers/ortstag.py
def ortstag(lat: float, lon: float, *, now_utc: datetime | None = None) -> date:
    """Der Kalendertag am Ort (lat, lon), gemessen an now_utc (Default: jetzt).

    lat/lon sind PFLICHT ohne Default — ein stiller Rueckfall auf Prozess-
    oder Test-Standardkoordinaten wuerde genau den Fehler reproduzieren,
    den diese Lieferung behebt. Reine Delegation an das produktive
    tz_for_coords(); keine eigene Zonenarithmetik.
    """
```

Aufruf ohne `lat`/`lon` ist ein `TypeError` (Python-Pflichtparameter, kein Default) — kein
zusaetzlicher Code noetig, das ist die Signatur selbst.

### Umzustellende Fixture-Helfer (viele Importeure — zuerst)

- `tests/helpers/alert_log_fixtures.py:133` — `gust_alert_trip()`: `Stage(date=date.today())`
  → `Stage(date=ortstag(LAT, LON))` (46 Importeure profitieren automatisch)
- `tests/helpers/trip_outlook_channels.py:111` — `heute = date.today()` → `ortstag(LAT, LON)`
- `tests/helpers/nowcast_gate_fixtures.py::make_trip()` — Default fuer `stage_date`
  (Reykjavik-Koordinaten `TRIP_LAT`/`TRIP_LON`) → `ortstag(TRIP_LAT, TRIP_LON)` statt
  `date.today()`-Fallback

### Direkt betroffene Testdateien (~35, siehe vollstaendige Liste in
`docs/context/fix-2314-ci-zeitzonen-riss.md`, Abschnitt „Related Files"/„Messbefunde")

Lokale `date.today()`-Datierungen von Trips/Ankern/`load_dated`/`save_dated` werden durch
`ortstag(lat, lon)` mit den tatsaechlichen Trip-Koordinaten ersetzt — oder, wo bereits ein
`Trip` vorliegt, durch `anchor_tz(trip, now_utc)` (gleichwertig). Betroffen u. a.:
`tests/tdd/test_alert_undelivered_hint.py:237`, `tests/tdd/test_alert_anchor_day_guard.py:155,
229-567`, `tests/.../test_issue_1088_official_alert_triggers.py:157,557`,
`tests/.../test_alert_state_briefing_reset.py:103,112,608`.

### Sonderfall: Klemm-Test

`tests/tdd/test_trip_report_test_send_past_stage_clamp.py` (~Z.121): der Provider-Double lehnt
Anfragen ab, wenn `start.date() != date.today()`. Das Produkt (`trip_report_scheduler.py:1320-
1323`) klemmt aber auf `trip_local_today`. Fix: Double-Vergleich auf `ortstag(<Trip-Koordinaten>)`
umstellen.

### Explizit NICHT umgestellt (Tautologie-Verbot — Zusicherung wuerde sich selbst pruefen)

Tests, die die **Tagesberechnung selbst** pruefen, duerfen ihren Soll-Tag NICHT aus dem Helfer
(oder einer anderen Produktfunktion) ableiten. Sie werden auf **gestellte Uhr + hart
hingeschriebenen Soll-Tag** umgebaut: Die Uhr wird auf einen festen Zeitpunkt gestellt
(`freeze_time`), der Soll-Tag steht als Literal im Test (Beispiel: bei `2026-09-14T23:00Z` ist
der Ortstag in Tirol `2026-09-15`). Mindestens ein Zeitpunkt liegt dort, wo UTC-Tag und Ortstag
auseinanderfallen — sonst unterscheidet der Test richtig nicht von falsch.

Abgeleitet aus den **143 tatsaechlich roten Test-IDs** (nicht aus der Zeilen-Voruntersuchung) ist
das in der roten Menge nur: `tests/unit/test_gpx_import_in_trip_dialog.py::TestGpxToStageDataCustomDate::
test_default_date_is_today` (Default-Tag von `gpx_to_stage_data`, ADR-0044).
Die roten Tests in `tests/e2e/test_e2e_story3_reports.py` (`TestSchedulerIntegration::
test_scheduler_finds_active_trip`) und `tests/unit/test_alarm_zeitfenster_ziel.py`
(`test_gegenprobe_vorlaufsperre_wird_durch_fix_neutralisiert`) pruefen eine **Folgewirkung** — dort
ist der Helfer mit den tatsaechlichen Trip-Koordinaten zulaessig. Nicht rote Stellen
(Betreff-Zusicherung `:274`, Radar-Fixture `:366-417`) bleiben unberuehrt. Grenzfall
`tests/tdd/test_alert_etappen_praefix_kurzform.py` wird im Einzelfall entschieden; die Begruendung
gehoert in den Implementierungsbericht.

### Sonderfall: Modulweites `NOW`

`tests/tdd/test_official_alert_time_window.py:59` setzt `NOW = datetime.now(timezone.utc)` beim
**Laden der Datei** — also bevor die gestellte Uhr (`GZ_TEST_WALL_CLOCK_UTC`) greift. Unter gestellter
Uhr laufen dann zwei Uhren gegeneinander (gemessen: Uhr 07:40 bei Echtzeit 07:35 → 4/4 gruen; Uhr
15:00 → `ac26`/`ac28`/`ac30` rot; der echte CI-Lauf um 14:25 UTC war gruen ⇒ keine Stunden-
Abhaengigkeit, sondern Zwei-Uhren-Artefakt). `NOW` wird deshalb **zur Testlaufzeit** bestimmt
(Funktion/Fixture statt Modulkonstante); die Zusicherungen der Tests bleiben unveraendert.

### Unveraendert

Root-`conftest.py` (#1402-Wächter bleibt exakt so bestehen), alles unter `src/`, `api/`,
`internal/`, `frontend/`.

## Expected Behavior

- **Input:** dieselben 38 Testdateien, derselbe Testinhalt — nur die Datumsquelle der
  Test-Fixtures aendert sich von `date.today()` (Prozesstag) auf `ortstag(lat, lon)`
  (Ortstag der jeweiligen Trip-Koordinaten).
- **Output:** `pytest`-Ergebnis der 38 Dateien ist zu jeder gestellten Uhrzeit (23:00, 01:00,
  04:00, 12:00, 15:00 UTC) identisch gruen — vorher zeitfensterabhaengig rot (Messgrenze s. AC-1).
- **Side effects:** keine. Kein Produktivcode-Pfad wird veraendert; die Prozesszonen-Fixierung
  aus #1402 bleibt unangetastet und erfuellt weiterhin ihren Zweck (Zonenfehler im Produkt
  sichtbar machen).

## Acceptance Criteria

- **AC-1:** Given die 38 betroffenen Testdateien und der Fix ist eingespielt / When sie mit
  gestellter Uhr (`GZ_TEST_WALL_CLOCK_UTC`) zu 23:00, 01:00, 04:00, 12:00 und 15:00 UTC laufen /
  Then ist jeder der fuenf Laeufe fuer alle 38 Dateien gruen. Messgrenze, ausdruecklich: Unter der
  gestellten Uhr liefert `date.today()` den **UTC-Tag**, nicht den Neufundland-Tag (gemessen: bei
  `01:00Z` → `2026-09-14`, echte Ortszeit St. John's `2026-09-13 21:30`). Nur **23:00** stellt den
  echten Nachtfehler nach (143 rote IDs, mengengleich mit dem CI-Nachtlauf); 01:00/04:00 sind
  Regressionskontrollen, 12:00/15:00 fangen das Zwei-Uhren-Artefakt (modulweites `NOW`). Das echte
  Fenster 00:00–02:30 UTC und das Kalifornien-Fenster decken AC-8 und AC-9 ab.
  - Test: `GZ_TEST_WALL_CLOCK_UTC=<Uhrzeit> uv run pytest <Dateiliste> -v -rA` fuenfmal nacheinander.

- **AC-2:** Given derselbe Dateisatz VOR dem Fix (Ausgangszustand, zur Dokumentation im
  Implementierungsbericht) / When dieselbe Testsuite zu mindestens einer Nachtuhrzeit (23:00
  oder 01:00 UTC) laeuft / Then schlagen die Tests fehl — das ist der Bug-Nachweis aus
  Nutzersicht (die Merge-Ampel blockiert einen inhaltlich unveraenderten PR).
  - Test: Referenz auf den bereits vorliegenden Messbefund (Job `103636609514`, 144 Fehler /
    38 Dateien, dokumentiert in `docs/context/fix-2314-ci-zeitzonen-riss.md`) plus mindestens
    ein frischer Reproduktionslauf vor der Umstellung.

- **AC-3:** Given die Umstellung aller 38 Dateien und der drei Fixture-Helfer / When die
  Testanzahl je Datei vor und nach der Aenderung verglichen wird (`pytest --collect-only`) /
  Then ist die Anzahl der gesammelten Tests je Datei unveraendert — kein Test wurde geloescht,
  uebersprungen (`skip`) oder als erwarteter Fehlschlag (`xfail`) markiert.
  - Test: `uv run pytest <Dateiliste> --collect-only -q` vor und nach der Aenderung, Zeilenzahl
    je Datei diffen.

- **AC-4:** Given die Root-`conftest.py`-Prozesszonen-Fixierung `America/St_Johns` (#1402) sowie
  der gesamte Produktivcode unter `src/`, `api/`, `internal/`, `frontend/` / When der Fix
  eingespielt ist / Then ist `git diff` fuer diese Bereiche leer — nur Testcode und der neue
  Helfer unter `tests/helpers/` aendern sich.
  - Test: `git diff --stat main... -- conftest.py src/ api/ internal/ frontend/` liefert keine
    Zeilen.

- **AC-5:** Given der neue Helfer `ortstag(lat, lon, *, now_utc=None)` mit Koordinaten in drei
  unterschiedlichen Zonen (z. B. Tirol/UTC+2, Reykjavik/UTC+0, Kalifornien/UTC-7 bis UTC-8) zu
  derselben gestellten Uhrzeit / When der Helfer aufgerufen wird / Then liefert er fuer jede
  Zone den jeweils richtigen Ortstag, UND ein Aufruf ohne `lat`/`lon` scheitert (Pflichtangabe,
  kein stiller Rueckfall auf eine Standardkoordinate).
  - Test: `tests/tdd/test_ortstag_helfer.py` (NEU) — Selbsttest des Helfers mit drei
    Zonen-Fixtures zu einer Uhrzeit nahe der Tagesgrenze plus ein Test, der den Aufruf ohne
    Koordinaten als `TypeError` erwartet.

- **AC-6:** Given einer der Tests, die die Tagesberechnung selbst pruefen (z. B.
  `tests/e2e/test_e2e_story3_reports.py:274` oder `tests/unit/test_alarm_zeitfenster_ziel.py`)
  UND eine gezielte Verfaelschung des Produkts, die `trip_local_today` wieder auf den
  Prozesstag statt den Ortstag zurueckfallen laesst / When diese Tests zu einer Uhrzeit laufen,
  in der Prozesstag und Ortstag auseinanderfallen (23:00 UTC) / Then wird
  mindestens einer dieser Tests rot — der Umbau auf `ortstag()` in den ANDEREN 38 Dateien
  darf diese Faehigkeit, einen echten Produktfehler zu erkennen, nicht wegnehmen.
  - Test: Mutations-Gegenprobe per String-Ersetzung mit externer Sicherungskopie (Repo-Konvention,
    kein `git checkout/stash/reset`) in `src/services/trip_day.py::trip_local_today` bzw.
    `anchor_tz`, danach betroffene Datei(en) laufen lassen, danach Sicherungskopie zurueckspielen.

- **AC-7:** Given `tests/tdd/test_trip_report_test_send_past_stage_clamp.py` (Provider-Double
  vergleicht bisher `start.date()` gegen `date.today()`) / When der Double-Vergleich auf den
  Ortstag der Trip-Koordinaten umgestellt ist und die Testsuite zu einer Nachtuhrzeit
  (23:00 UTC) laeuft / Then ist die Datei gruen, und die Zusicherung des Tests bleibt dieselbe
  (eine vergangene Etappe wird auf den heutigen Ortstag geklemmt und tatsaechlich versendet —
  Ergebnis `"sent"`).
  - Test: `GZ_TEST_WALL_CLOCK_UTC=23:00 uv run pytest tests/tdd/test_trip_report_test_send_
    past_stage_clamp.py -v`.

- **AC-8:** Given die 38 Dateien und die drei Fixture-Helfer nach dem Fix / When alle verbliebenen
  Vorkommen von `date.today()` (sowie `datetime.today()`/`date_type.today()`) darin aufgelistet
  werden / Then dient keines davon mehr als Datum einer Etappe, eines Ankers oder eines
  Wetter-Schnappschusses eines Trips — Beweis per Konstruktion, unabhaengig von jeder Uhrzeit
  (deckt das lokal nicht messbare Fenster 00:00–02:30 UTC und das Kalifornien-Fenster ab).
  - Test: `grep -n "date.today()\|datetime.today()\|date_type.today()"` ueber die Dateiliste; jede
    verbliebene Fundstelle ist im Implementierungsbericht mit Begruendung aufgefuehrt und vom
    Adversary gegengelesen.

- **AC-9:** Given der Fix ist in `main` gemergt / When der CI-Job `test` auf `main` einmal mit
  **echter Uhr** innerhalb des Fensters 00:00–02:30 UTC laeuft / Then ist er gruen — der einzige
  Nachweis unter echter Neufundland-Prozesszone, ohne gestellte Uhr. Das Issue wird erst danach
  geschlossen.
  - Test: GitHub-Actions-Lauf des Jobs `test` auf dem Merge-Stand, Startzeit und Ergebnis im
    Issue dokumentiert.

## Out of Scope

- Erweiterung der Wanduhr-Ratsche #1667 um das Muster „`date.today()` als Trip-Etappendatum" —
  gebucht als Checkbox in Sammel-Issue #1196 (Regel-Budget: kein neues Gate in dieser Lieferung).
- Die im Ticket urspruenglich benannte Stelle `src/services/gpx_processing.py:219` — liegt
  nachweislich nicht auf dem fehlschlagenden Pfad (nur `POST /api/gpx/parse` und
  Mehrdatei-Import, nie der Scheduler) und wird nicht angefasst.
- Alle `date.today()`-Vorkommen ausserhalb der 38 roten Dateien (von 170 Fundstellen im Repo
  betrifft nur eine Teilmenge tatsaechlich den Fehler — Trip-Ort in Prozesszone bleibt
  unproblematisch).
- Inhaltliche Aenderung der Zusicherungen der Berechnungs-Tests unter „Tautologie-Verbot" — sie
  pruefen weiterhin dasselbe; geaendert wird nur, WOHER Uhr und Soll-Tag kommen (gestellte Uhr +
  Literal statt Wanduhr + `date.today()`).

## Risiken

- **Falsches Gruen durch Tautologie:** wird der Helfer versehentlich auch in einem
  Berechnungs-Test eingesetzt, der genau die Ortstag-Logik prueft, misst der Test nur noch sich
  selbst. Gegenmassnahme: die Ausschlussliste im Abschnitt „Explizit NICHT umgestellt" ist
  verbindlich, AC-6 ist die Gegenprobe.
- **Falsches Gruen durch Default-Koordinaten:** ein Helfer mit `lat`/`lon`-Default wuerde den
  urspruenglichen Fehler (Trip-Ort ignoriert) reproduzieren. Gegenmassnahme: Pflichtparameter
  ohne Default, AC-5 zweiter Teil.
- **Falsches Gruen durch Einzeluhrzeit-Nachweis:** ein Nachweis nur um 23:00 UTC deckt das
  Reykjavik-Fenster (00:00-02:30 UTC) und das Los-Angeles-Fenster (02:30-07:00 UTC) nicht ab.
  Gegenmassnahme: AC-1 verlangt alle vier Kontrolluhrzeiten.

## Test-Plan

| AC | Testdatei/Befehl |
|----|-------------------|
| AC-1 | fuenfmaliger Lauf mit `GZ_TEST_WALL_CLOCK_UTC` (23:00, 01:00, 04:00, 12:00, 15:00) ueber alle 38 Dateien |
| AC-2 | Referenzmessung (bereits vorliegend) + ein frischer Vorher-Lauf zu einer Nachtuhrzeit |
| AC-3 | `pytest --collect-only -q` vor/nach, je Datei diffen |
| AC-4 | `git diff --stat main... -- conftest.py src/ api/ internal/ frontend/` |
| AC-5 | `tests/tdd/test_ortstag_helfer.py` (NEU, Verhaltensname, kein Issue-Bezug im Dateinamen) |
| AC-6 | Mutations-Gegenprobe (String-Ersetzung + Sicherungskopie) gegen `trip_local_today`/`anchor_tz`, betroffene Tests laufen lassen |
| AC-7 | `GZ_TEST_WALL_CLOCK_UTC=23:00 uv run pytest tests/tdd/test_trip_report_test_send_past_stage_clamp.py -v` |
| AC-8 | grep-Auflistung verbliebener `date.today()`-Fundstellen in Dateiliste + 3 Helfern, begruendet im Bericht |
| AC-9 | echter CI-Lauf `test` auf `main` im Fenster 00:00–02:30 UTC |

## Known Limitations

1. Der Grenzfall `tests/tdd/test_alert_etappen_praefix_kurzform.py:302/319,535/539` wird erst
   bei der Implementierung final entschieden (Tautologie-Nachbarschaft); die Entscheidung
   gehoert in den Implementierungsbericht.
2. Die Ratsche gegen ein Wiederauftreten (#1667-Erweiterung) ist ausdruecklich nicht Teil dieser
   Lieferung — ohne sie kann das `date.today()`-Muster mit einem neuen Test zurueckkehren
   (170 Fundstellen im Gesamtrepo, nicht alle betroffen).
3. **Messgrenze der gestellten Uhr:** `freezegun` liefert fuer `date.today()` den UTC-Tag und
   ignoriert die Prozesszone. Das Nachtfenster ist lokal nur 22:00–24:00 UTC nachstellbar;
   00:00–02:30 UTC und das Kalifornien-Fenster (02:30–07:00 UTC) sind lokal nicht messbar
   (`libfaketime`/`time-machine` nicht installiert; eine neue Abhaengigkeit nur fuer diesen Nachweis
   ist unverhaeltnismaessig). Ersatz: AC-8 (Konstruktion) + AC-9 (echter CI-Lauf nach dem Merge).
4. Die Zaehlung 144 (CI-Zusammenfassung) vs. 143 (extrahierte IDs) entsteht durch parametrisierte
   IDs mit Leerzeichen (`[quiet_hours-Stille …]`), die beim Extrahieren zusammenfallen — keine
   inhaltliche Abweichung.
5. Nur die 38 gemessenen Dateien sind Gegenstand; weitere `date.today()`-Vorkommen, die
   zufaellig in der Prozesszone liegende Koordinaten verwenden, bleiben unberuehrt, weil sie den
   Fehler nicht ausloesen.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** reine Testinfrastruktur-Korrektur ohne Verhaltensaenderung an Produktivcode —
  keine neue Entscheidungsflaeche im Sinne der ADR-Kriterien. Inhaltlich getragen von ADR-0044
  (Kalendertage folgen der Ortszeit) und ADR-0051 (Zone kommt aus den Daten); beide bleiben
  unveraendert in Kraft, diese Lieferung bringt lediglich die Test-Fixtures auf denselben Stand
  wie der bereits akzeptierte Produktivcode.

## Changelog

- 2026-09-14: Initial spec erstellt — Issue #2314.
- 2026-09-14: Berechnungs-Tests werden ebenfalls umgebaut (gestellte Uhr + Literal-Soll-Tag),
  da sie selbst in der roten Liste stehen; AC-6 Mutationsprobe zu 23:00 UTC; AC-7 Zusicherung
  korrigiert (`"sent"`).
- 2026-09-14 (nach Freigabe, aus RED-Messung): AC-1 auf fuenf Uhrzeiten mit ausdruecklicher
  Messgrenze (gestellte Uhr = UTC-Tag); neu AC-8 (Beweis per Konstruktion) und AC-9 (echter
  CI-Nachtlauf vor Issue-Close); Sonderfall modulweites `NOW` in
  `test_official_alert_time_window.py`; Tautologie-Ausschlussliste aus den 143 echten roten IDs
  neu abgeleitet (nur `test_gpx_import_in_trip_dialog.py` ist Berechnungs-Test).
- 2026-09-14 (Umsetzung, Adversary F001): bewusste Abweichung von „Nicht rote Stellen bleiben
  unberuehrt" — `tests/e2e/test_e2e_story3_reports.py:274` (Betreff) und
  `tests/unit/test_alarm_zeitfenster_ziel.py:405-419` (Radar-Fixture) wurden mit umgestellt.
  Grund: die Segment-Fixture datiert jetzt auf den Ortstag, der Betreff traegt dieses Datum
  (sonst `test_email_subject_format` neu rot); der Radar-Pfad sucht die Etappe ueber
  `trip_local_today` (`src/services/trip_alert.py:1610`), im echten Fenster 00:00–02:30 UTC haette
  die Fixture sonst den falschen Tag getragen. Adversary: legitim, nicht tautologisch (Mutation
  M1 `trip_local_today`→Prozesstag macht 25 Tests rot, Fix-Umkehr im Helfer 64).
