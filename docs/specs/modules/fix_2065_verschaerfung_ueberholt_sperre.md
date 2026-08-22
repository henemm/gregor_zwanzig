---
entity_id: fix_2065_verschaerfung_ueberholt_sperre
type: module
created: 2026-08-22
updated: 2026-08-22
status: draft
workflow: fix-2065-verschaerfung-durchbricht-sperrzeit
version: "1.0"
tags: [alarm, nowcast, sperrzeit, entdopplung]
---

# Verschärfung überholt die Radar-Sperrzeit (Issue #2065)

## Approval

- [ ] Approved

## Purpose

Eine sich deutlich verschärfende Regenlage erreicht den Nutzer heute nicht, wenn ein
vorangegangener Radar-Alarm noch eine laufende Sperrzeit hält — gemessen: 11 mm/h (~10 mm)
lösen aus und buchen 120 Minuten Sperre, 90 Minuten später schweigt eine auf 30 mm/h
(~27,5 mm) verdreifachte Lage mit Protokollgrund `cooldown`. Das verletzt Anforderung **A-3**
aus #2050 ("Eine Verschärfung überholt jede Sperre", dort Szenario 4). Diese Spec führt eine
eigenständige, quantitative Überholungsprüfung ein, die an **beiden** Stellen wirkt, an denen
der gemessene Fall heute scheitert: der Sperrzeit selbst und der dahinterliegenden
Entdopplung.

## Source

- **File:** `src/services/alert_gate.py` (neuer Vergleichs-Helfer, Erweiterung
  `record_nowcast_sent`, optionaler Parameter `check_event_identity_gate`)
- **File:** `src/services/trip_alert.py` (`TripAlertService.check_radar_alerts`,
  Kontrollfluss im Sperrzeit-Fall)
- **File:** `src/services/throttle_store.py` (`ThrottleStore`, Schema-Erweiterung)
- **Identifier:** `check_nowcast_gate` (unverändert), neuer Helfer (Arbeitstitel
  `_radar_overtakes_cooldown` bzw. äquivalent), `check_event_identity_gate`

Schicht: ausschließlich Python-Core (`src/services/`). Kein Go-, kein Frontend-Anteil.

## Estimated Scope

- **LoC:** ~+140 / −20 (Produktivcode) — eng am 250-LoC-Standardlimit des Workflows;
  Doku (ADR-Nachtrag, Spec-Nachtrag) zählt dort nicht mit. Ggf. `loc_limit_override` nötig.
- **Files:** 4 Produktivdateien (`alert_gate.py`, `trip_alert.py`, `throttle_store.py`,
  ggf. eine Konstanten-Stelle)
- **Effort:** high
- **Risiko:** HIGH — kritischer Alarmpfad, geteilter Baustein (Trip + Ortsvergleich),
  Schema-Änderung an Bestandsdaten

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `src/services/alert_gate.py::check_nowcast_gate` | function | Bleibt in Signatur UND Verhalten unverändert — der neue Helfer taucht dort nicht im Aufrufgraphen auf |
| `src/services/alert_gate.py::record_nowcast_sent` | function | Bekommt einen optionalen Mengen-Parameter, gebucht weiterhin nur nach erfolgreicher Zustellung (F001-Symmetrie) |
| `src/services/alert_gate.py::check_event_identity_gate` | function | Bekommt einen optionalen Eskalations-Parameter, der in den bestehenden ersten Eskalationszweig (`:669`, `exceeds(...)`) einspeist |
| `src/services/throttle_store.py::ThrottleStore` | class | Eintragsformat erweitert sich um die zuletzt gemeldete Menge, alter Reinstring bleibt lesbar |
| `src/services/radar_service.py::NowcastResult.window_precip_mm` | attribute | Die quantitative Vergleichsgröße (60-Min-Vergleichsfenster ab `now`), dieselbe Größe wie bei der Briefing-Überholung |
| `src/services/alert_daily_limit.py::is_allowed`/`increment` | function | Erneute Tageslimit-Prüfung im Override-Pfad (AC-7) — Lesen vor dem Abruf, Buchen nur nach Zustellung |
| `src/services/alert_urgency.py::exceeds` | function | Bestehende Eskalationsprüfung, mit der der neue Parameter ODER-verknüpft wird |
| `src/services/compare_radar_alert.py` | module | Zweiter Aufrufer von `check_nowcast_gate` — bleibt unberührt (Ortsvergleich zurückgestellt) |
| `docs/adr/0021-shared-deviation-alert-engine.md` | doc | Trägt die feste Reihenfolge Ruhezeit→Sperrzeit→Tages-Obergrenze fest — die Ausnahme braucht einen datierten Nachtrag |
| `docs/specs/modules/rework_1467_s3_nowcast.md` | doc | Spec der geteilten Gate-Kette — muss den neuen Zweig mitführen |
| `tests/helpers/alarm_pruefstrecke.py::AlarmPruefstrecke` | test helper | Zeitreihen-Harness, auf dem der Kernfall (AC-1) reproduziert wird |

## Implementation Details

**Eine geteilte Vergleichsfunktion, zwei Wirkorte** — die Definition von "deutlich
schlimmer" (Anforderung C-3) existiert genau einmal und wird an beiden blockierenden
Stellen benutzt, die den gemessenen Fall verursachen (Kernbefund 1 + Befund A der
Analyse, `docs/context/fix-2065-verschaerfung-durchbricht-sperrzeit.md`).

**1. Neuer Vergleichs-Helfer in `alert_gate.py`**, in Nachbarschaft von `record_nowcast_sent`
(`alert_gate.py:386`). Vergleicht die aktuelle Menge (`window_precip_mm`) gegen die
gespeicherte Vergleichsbasis (Baustein 4). UND-verknüpft, Muster identisch zur
PO-freigegebenen Briefing-Überholung (`trip_alert.py:1410-1414`, F008/#2020), aber mit
**eigenen benannten Konstanten** — andere Vergleichsbasis (letzte gemeldete Menge statt
Briefing-Ankündigung), daher eigenständig nachziehbar:

```
Faktor: 2,0            (Arbeitsname: _COOLDOWN_OVERTAKE_FACTOR)
Absolute Untergrenze: 2,0 mm  (Arbeitsname: _COOLDOWN_OVERTAKE_MIN_ABSOLUTE_MM)
```

Fehlt die Vergleichsbasis (kein gespeicherter Wert — Befund C, s. u.), liefert der Helfer
`False` (kein Durchbruch, konservativ).

Der gemessene #2065-Fall rechnet damit durch: `27,5 mm >= 10,08 mm × 2,0` (✓) und
`27,5 mm >= 2,0 mm` (✓) → Durchbruch. Diese beiden Zahlen sind der Regler, den der PO bei
der Freigabe verstellen kann.

**2. `trip_alert.py::check_radar_alerts` — Kontrollfluss im Sperrzeit-Fall.** Bei
`gate.reason == alert_log.REASON_COOLDOWN` kein sofortiges `continue` mehr
(bisher `trip_alert.py:1281-1303`): stattdessen in den Nowcast-Abruf laufen (derselbe
Abruf wie im freien Fall, keine zweite `get_nowcast`-Anfrage — die Invariante "genau EIN
Abruf je Trip", `trip_alert.py:1305`, #1329, bleibt gewahrt), dann den Helfer aus Baustein 1
befragen. Kein Treffer → unverändert unterdrücken, Protokollgrund bleibt `cooldown`.
Treffer → weiterlaufen wie im ungesperrten Fall, inklusive erneuter Tageslimit-Prüfung
(Baustein 5) und der bestehenden Briefing-Überholungsprüfung (`:1410-1414`, unverändert).

**3. `check_event_identity_gate` — optionaler Eskalations-Parameter.** Die quantitative
Verschärfung speist in den bestehenden ERSTEN Eskalationszweig
(`alert_gate.py:669`, `if alert_urgency.exceeds(severity, match["severity"])`) ein, ODER-
verknüpft mit der bestehenden Prüfung. Struktur "Eskalation zuerst, dann V1-Ausnahme, dann
Unterdrückung" (`:641-692`) bleibt unangetastet. Notwendig, weil die dreistufige
Schwere-Skala (`LOW`/`MODERATE`/`HIGH`) bei 4 mm/h sättigt
(`HEAVY_RAIN_THRESHOLD_MM_H`, `radar_service.py:78`) und `exceeds("HIGH","HIGH")` für
11 mm/h gegen 30 mm/h `False` liefert — gemessen belegt (Befund A der Analyse): ohne diesen
Baustein bleibt der rote Kerntest rot, der Protokollgrund wechselt nur von `cooldown` auf
`event_duplicate`.

**4. `ThrottleStore` — Schema-Erweiterung.** Eintrag von reinem ISO-String
(`{scope: {key: iso_timestamp}}`) auf `{scope: {key: {"at": iso_timestamp,
"precip_mm": float|null}}}`. Alter Reinstring bleibt gültig lesbar — neue Lesemethode
(Arbeitstitel `last_sent_with_precip`) statt Überladung von `last_sent()` (15+ Aufrufer,
`throttle_store.py:67`). `_parse()` (`:160-170`) unterscheidet beim Lesen zwischen
altem String-Format und neuem Objekt-Format; `record()` (`:84`) schreibt ausschließlich
das neue Format. Read-Modify-Write bleibt erhalten (`_update()`, `:117-158`), kein Replace.

**5. `record_nowcast_sent` — optionaler Mengen-Parameter**, durchgereicht an
`.record()` des `ThrottleStore`. Buchung weiterhin ausschließlich NACH erfolgreicher
Zustellung (F001-Symmetrie, unverändert aus `alert_gate.py:395`).

**`check_nowcast_gate` bleibt in Signatur UND Verhalten unverändert.** Der neue Helfer
taucht in seinem Aufrufgraphen nicht auf — damit bleiben die drei Ordnungstests
(`test_alert_gate.py:88/129/163`) und der Ortsvergleich (`compare_radar_alert.py`)
unberührt. Das ist die sauberste Erfüllung der PO-Rückstellung des Ortsvergleichs: keine
Signatur-Passagiere, kein toter Default.

**Verworfen** (aus der Analyse übernommen, nicht erneut zu prüfen):
- *Gates umsortieren* — behebt den gemessenen Fall nicht (die Entdopplung dahinter kennt
  dieselbe sättigende Skala, Befund A).
- *Vergleich in `check_nowcast_gate` selbst* — zöge den Speicherzugriff in den geteilten
  Baustein und beträfe Ortsvergleich und Ordnungstests am falschen Ort.
- *Die bestehende `LOW/MODERATE/HIGH`-Leiter um eine vierte Stufe erweitern* — ändert die
  Bedeutung einer an vielen Stellen gelesenen Größe (Kanal-Schwellen ADR-0046, amtliche
  Warnstufen) für einen lokalen Zweck.

**Was NICHT dazugehört:**
- Tageslimit-Durchbruch (Szenario 7 / Anforderung D-3, eigene Scheibe #2050 S3) — bei
  `tier=premium` gilt ohnehin kein Limit (`user_tier.py:45`), für den akuten Fall wirkungslos.
- Ruhezeit-Ausnahme — bewusst NICHT: Ruhezeit bleibt unbrechbar (#1955, PO-Ablehnung).
- Szenario 1 "Regen läuft schon" (#2050 S2b, kollidiert mit #2020 S2, eigene Scheibe).
- Ortsvergleich — bleibt in Verhalten UND Signatur unverändert (s. o.).

**A-3 wird durch diese Spec nur TEILWEISE erfüllt** (zwei von drei Sperren: Sperrzeit und
Entdopplung — nicht das Tageslimit). Das ist keine vollständige Erfüllung von A-3 und darf
nicht als solche verbucht werden.

## Expected Behavior

- **Input:** laufende Radar-Sperrzeit (`ThrottleStore`, Scope `radar`, Schlüssel `trip.id`)
  mit gespeicherter Vergleichsmenge; aktueller Nowcast-Abruf für denselben Trip.
- **Output:** bei ausreichender Verschärfung (Faktor UND absolute Untergrenze erfüllt,
  Tageslimit noch nicht erschöpft) ein zugestellter Alarm über alle konfigurierten Kanäle;
  sonst unverändert Stille mit Protokollgrund `cooldown`.
- **Side effects:** ein zusätzlicher `get_nowcast`-Abruf während laufender Sperrzeit (bisher
  fand dort gar kein Abruf statt); bei Durchbruch Fortschreibung der Vergleichsbasis auf die
  neue, höhere Menge (Selbstbremsung); bei gescheiterter Zustellung KEINE Fortschreibung
  (F001-Symmetrie, AC-10).

## Acceptance Criteria

- **AC-1:** Given eine laufende Sperrzeit aus einem vorangegangenen Alarm über ~10 mm
  (11 mm/h), When 90 Minuten später eine Lage mit ~27,5 mm (30 mm/h) im selben Sperrfenster
  geprüft wird, Then geht ein Alarm über alle konfigurierten Kanäle raus.
  - Test: Zeitreihe auf `AlarmPruefstrecke` (Lauf 1: 11 mm/h auslösend, Lauf 3 nach
    90 Minuten: 30 mm/h) — `triggered_count >= 1`, alle vier Kanal-Listen nicht leer.

- **AC-2:** Given eine laufende Sperrzeit, When die Lage im Vergleich zur letzten
  Meldung unverändert bleibt, Then bleibt die Unterdrückung bestehen und das Protokoll
  weist als Grund `cooldown` aus.
  - Test: zweiter Lauf mit identischer Eingangslage innerhalb des Sperrfensters —
    `triggered_count == 0`, `alert_log.read_undelivered()` liefert einen Eintrag mit
    `gate_reason == alert_log.REASON_COOLDOWN`.

- **AC-3:** Given eine Verschärfung, die den Faktor erreicht, aber deren Gesamtmenge unter
  der absoluten Untergrenze bleibt, When der Vergleich läuft, Then bricht die Sperre NICHT
  durch.
  - Test: Vergleichsbasis so niedrig gewählt, dass Faktor 2,0 rechnerisch erfüllt ist
    (z. B. 0,5 mm × 2,0 = 1,0 mm erreicht), die tatsächliche Menge aber unter 2,0 mm bleibt
    (z. B. 1,8 mm) — `triggered_count == 0`.

- **AC-4:** Given eine Menge über der absoluten Untergrenze, aber ohne den geforderten
  Faktor gegenüber der Vergleichsbasis, When der Vergleich läuft, Then bricht die Sperre
  NICHT durch.
  - Test: Vergleichsbasis so gewählt, dass die neue Menge über 2,0 mm liegt, aber unter dem
    2,0-fachen der Vergleichsbasis (z. B. Basis 10 mm, neue Menge 15 mm) —
    `triggered_count == 0`.

- **AC-5:** Given die Verschärfung erfüllt Faktor und absolute Untergrenze, When der Alarm
  geprüft wird, Then wirkt der Durchbruch AUCH an der Entdopplung — der protokollierte
  Grund ist NICHT `event_duplicate`, der Alarm kommt tatsächlich an.
  - Test: derselbe Lauf wie AC-1, zusätzlich geprüft, dass der zugestellte Alarm nicht mit
    `alert_log.REASON_EVENT_DUPLICATE` unterdrückt wurde (Begründung: Befund A der
    Analyse — ohne diesen Baustein wechselt nur der Protokollgrund, der Alarm bliebe aus).

- **AC-6:** Given die Ruhezeit ist aktiv, When selbst eine extreme Verschärfung geprüft
  wird, Then bleibt der Alarm aus und das Protokoll weist `quiet_hours` als Grund aus.
  - Test: Lauf mit `now` innerhalb der konfigurierten Ruhezeit und einer Verschärfung weit
    über Faktor und Untergrenze — `triggered_count == 0`, Protokollgrund
    `alert_log.REASON_QUIET_HOURS` (PO-Ablehnung #1955, unbrechbar).

- **AC-7:** Given ein Nutzer mit endlichem Tagesbudget, dessen Budget bereits erschöpft
  ist, When eine Verschärfung vorliegt, die Faktor und Untergrenze erfüllt, Then bleibt der
  Alarm aus und das Protokoll weist `daily_limit` als Grund aus.
  - Test: Nutzer-Tier mit endlichem Limit, Tageszähler auf das Limit gesetzt, Verschärfung
    wie in AC-1 — `triggered_count == 0`, Protokollgrund `alert_log.REASON_DAILY_LIMIT`.
    Begründung: die Kette schließt heute bei Sperrzeit kurz, das Tageslimit wurde für den
    Überholungsfall also nie geprüft; der Durchbruch darf es nicht stillschweigend
    mit-überspringen.

- **AC-8:** Given die Sperre wurde von einem zweiten Schreiber ohne Mengenangabe gebucht
  (Kurzfristhinweis im Briefing, `trip_report_scheduler.py:1574`), sodass keine
  Vergleichsbasis existiert, When eine beliebig starke Lage geprüft wird, Then bricht die
  Sperre NICHT durch und das Protokoll weist `cooldown` als Grund aus.
  - Test: Sperre über den Pfad ohne Mengenangabe gebucht, anschließend Lauf mit einer
    Lage, die Faktor und Untergrenze gegen eine hypothetische Basis deutlich überschritte —
    `triggered_count == 0`, Protokollgrund `cooldown` (konservative Fehlerrichtung:
    Alarmflut zu vermeiden wiegt schwerer als Durchlässigkeit ohne Nachweis).

- **AC-9:** Given ein Alarm ist im selben Sperrfenster bereits einmal durchgebrochen und
  hat die Vergleichsbasis auf die höhere Menge fortgeschrieben, When dieselbe (nicht weiter
  verschärfte) Menge erneut geprüft wird, Then bricht der Alarm NICHT ein zweites Mal durch.
  - Test: Lauf 1 (auslösend) → Lauf 2 (Durchbruch, z. B. 27,5 mm) → Lauf 3 mit
    unveränderten 27,5 mm im selben Sperrfenster — `triggered_count == 0` bei Lauf 3
    (Selbstbremsung, Schutz gegen Wiederholungs-Kettenreaktion).

- **AC-10:** Given ein Durchbruchsfall, bei dem die Zustellung scheitert (kein
  erreichbarer Kanal / Zustellfehler), When der Lauf abgeschlossen ist, Then wird die
  Vergleichsbasis NICHT fortgeschrieben.
  - Test: Durchbruchslage wie AC-1, aber ohne zustellbaren Kanal — anschließend gelesene
    Vergleichsbasis unverändert gegenüber dem Stand vor dem Lauf (F001-Symmetrie).

- **AC-11:** Given ein `throttle_state.json` im alten Format (Eintrag = reiner
  ISO-Zeitstempel ohne Mengenangabe), When ein Lauf gegen diese Datei prüft, Then bleibt
  die Sperrzeit unverändert wirksam, die Datei bleibt lesbar und es geht kein Bestandsdatum
  verloren.
  - Test: Roundtrip mit vorbereiteter Alt-Datei (reiner String-Eintrag) — `is_throttled()`
    liefert weiterhin korrekt `True`/`False`, ein anschließendes `record()` überschreibt
    nur den geänderten Schlüssel, alle anderen Bestandseinträge bleiben unangetastet
    (Read-Modify-Write, nie Replace).

- **AC-12:** Given der Ortsvergleich-Radarpfad (`compare_radar_alert.py`), When diese
  Änderung ausgeliefert ist, Then verhält er sich unverändert — weder Signatur- noch
  Verhaltensänderung an seinem Aufrufgraphen über `check_nowcast_gate`.
  - Test: bestehende Ortsvergleich-Nowcast-Tests laufen unverändert grün; zusätzlich ein
    Signatur-Wächter, der belegt, dass `check_nowcast_gate` keine neuen Parameter ohne
    Default entgegennimmt.

- **AC-13:** Given ein Lauf mit laufender Sperrzeit, When die Überholungsentscheidung
  getroffen wird (Durchbruch ODER Unterdrückung), Then protokolliert der Lauf sowohl die
  gelesene Vergleichsbasis als auch die aktuell gemessene Menge.
  - Test: Protokolleintrag (Durchbruchsfall wie AC-1 und Unterdrückungsfall wie AC-2) auf
    Vorhandensein beider Werte prüfen — nachvollziehbar, gegen welche Basis entschieden
    wurde.

- **AC-14:** Given diese Änderung ist umgesetzt, When `docs/adr/0021-shared-deviation-alert-engine.md`
  gelesen wird, Then trägt es einen datierten Nachtrag, der die Ausnahme beschreibt UND
  begründet, warum der Ortsvergleich sie nicht bekommt; zusätzlich trägt
  `docs/specs/modules/rework_1467_s3_nowcast.md` einen entsprechenden Nachtrag.
  - Test: `# doc-compliance-test`, analog `test_ac21_adr_0021_traegt_einen_datierten_s4b_nachtrag`
    (`tests/tdd/test_alert_gate.py:1067`) — Nachtrag mit Bezug auf `#2065` in beiden Dateien,
    nach dem letzten bestehenden Nachtrag (#2018, 2026-08-21) einsortiert.

## Known Limitations

- **Budget-Mehrkosten:** bis zu 7 zusätzliche Nowcast-Abrufe je Sperrfenster und Tour
  (Prüftakt 15 Min, Sperrzeit-Vorgabe 2 h, Radar-Cache-TTL 300 s), gegen ein Tagesbudget von
  9000 (`forecast_budget.py:40`). Unkritisch in der Größenordnung, aber real und im PR zu
  nennen.
- **Fehlende Vergleichsbasis beim zweiten Schreiber:** `trip_report_scheduler.py:1574`
  bucht dieselbe `radar`-Sperre ohne Mengenangabe (Kurzfristhinweis im Briefing) — in
  diesem Fall bleibt der Durchbruch strukturell unmöglich (AC-8), auch bei real starker
  Verschärfung.
- **A-3 aus #2050 wird nur TEILWEISE erfüllt** — zwei von drei Sperren (Sperrzeit,
  Entdopplung), NICHT das Tageslimit (eigene Scheibe #2050 S3 / Anforderung D-3).

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** ADR-0021 (Nachtrag)
- **Rationale:** ADR-0021 schreibt die feste Reihenfolge Ruhezeit → Sperrzeit →
  Tages-Obergrenze als geteilten Baustein für Trip UND Ortsvergleich fest. Diese Spec führt
  eine Ausnahme in dieser Kette ein (quantitative Verschärfung überholt die Sperrzeit) —
  das ist eine Änderung an einer dokumentierten Entscheidung und braucht deshalb einen
  datierten ADR-Nachtrag (Präzedenz: der S4b-Nachtrag zu #1467), der zusätzlich begründet,
  warum der Ortsvergleich diese Ausnahme NICHT bekommt (PO-Rückstellung, s. `docs/context/
  fix-2065-verschaerfung-durchbricht-sperrzeit.md`, Abschnitt „Dependencies").

## Changelog

- 2026-08-22: Initial spec created (aus `docs/context/fix-2065-verschaerfung-durchbricht-sperrzeit.md`,
  Analyse-Phase 2026-08-22).
