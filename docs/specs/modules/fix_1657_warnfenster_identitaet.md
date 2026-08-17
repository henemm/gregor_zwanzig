---
entity_id: fix_1657_warnfenster_identitaet
type: bugfix
created: 2026-08-17
updated: 2026-08-17
status: draft
version: "1.0"
workflow: fix-1657-warnung-identitaet
---

# Fix #1657: Berührende und ineinander verschachtelte Warnfenster gelten als dieselbe amtliche Warnung

## Approval

- [ ] Approved

## Purpose

Dieselbe amtliche Gefahr wird mehrfach gemeldet, wenn die Quelle sie zunächst in
stundenfeinen Teilfenstern und später als ein zusammenfassendes, breiteres Fenster
ausstellt (Kirchbach 2026-08-16: drei Meldungen für eine durchgehende Gewitterwarnung;
Obertilliach 2026-08-11: dasselbe Muster). `official_alert_revision_verdict()`
(#1685) erkennt Überlappung heute strikt und wertet ein umschließendes Breitfenster
fälschlich als „Vorverlegung des Beginns" statt als reine Granularitäts-Änderung. Diese
Spec schließt beide bestätigten Mechanismen — PO-Entscheidung 2026-08-17, Kontext-Doc
`docs/context/fix-1657-warnung-identitaet.md` Abschnitt „PO-Entscheidungen".

## Source

- **File:** `src/output/renderers/alert/official_alerts.py`
- **Identifier:** `official_alert_revision_verdict` (Zeile 428-520) — einzige zu
  ändernde Funktion. `official_alert_state_key` (383-399) und
  `_identity_hazard_prefix` (402-425) bleiben unverändert.
- **Aufrufstellen (unverändert, nur Nachweispflicht):** `src/services/trip_alert.py:1487-1511`
  (`check_official_alert_triggers`), `src/services/compare_official_alert.py:255-284`
  (`_detect`) — beide teilen sich die geänderte Funktion, keine eigene Anpassung nötig.

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `output.renderers.alert.official_alerts.official_alert_state_key` | function | Kanonische Schlüsselbildung, unverändert |
| `output.renderers.alert.official_alerts._identity_hazard_prefix` | function | Kandidatensuche ohne Zeitraum-Parsing, unverändert |
| `output.renderers.alert.official_alerts.dedupe_official_alerts` | function | Anzeige-Ebene, bewusst NICHT verändert — zwei Perioden bleiben dort weiterhin zwei Einträge |
| `services.alert_state.AlertStateService` | class | Melde-Gedächtnis; `reset()` (`alert_state.py:47-121`) behält `official_alert:`-Einträge über den Briefing-Reset hinweg (#1614) — Grund für den Zeitnähe-Guard dieser Spec |
| `services.trip_alert.TripAlertService.check_official_alert_triggers` | method | Trip-Lesepfad, ruft die geänderte Funktion unverändert auf (Zeile 1499) |
| `services.compare_official_alert.CompareOfficialAlertService._detect` | method | Ortsvergleich-Lesepfad, ruft die geänderte Funktion unverändert auf (Zeile 268) |
| `docs/specs/modules/fix_1685_warnfenster_revision.md` | spec | Direkter Vorgänger — führte Überlappungs-/Eskalations-/Vorverlegungs-Prüfung ein; diese Spec präzisiert genau zwei Teilregeln daraus, hebt sie nicht auf |
| #1245 AC-4 | decision | Ursprung der Zeitraum-in-Identität-Regel; bleibt unverändert für echte, nicht berührende/nicht umschließende Perioden |
| ADR-0040 | decision | „Eine gerissene Grenze wird einmal gemeldet, erneut erst bei Verschärfung" — bestätigt die Richtung dieser Spec |

## Estimated Scope

- **LoC:** ~35 (Produktivcode +20/-5, Tests +90/-10)
- **Files:** 3 (1 Produktivdatei, 2 Testdateien)
- **Effort:** medium

### Affected Files

| File | Change Type | Description |
|------|-------------|--------------|
| `src/output/renderers/alert/official_alerts.py` | MODIFY | `official_alert_revision_verdict`: (1) Überlappungsprüfung Zeile 485 von `<` auf `<=` (Berührung zählt), (2) neue Containment-Prüfung vor der Vorverlegungs-Ausnahme (Zeile 498) mit 6h-Zeitnähe-Guard auf `kandidat.reported_at` |
| `tests/tdd/test_official_alert_revision_dedup.py` | MODIFY | Revision des Touching-Teilfalls von `ac6-kein-zeit-ueberlapp-meldet`, neue Fälle: Containment, Zeitnähe-Guard, Kirchbach-Regression, Obertilliach-Regression, Ortsvergleich-Parität, Stufenerhöhung-unter-Containment |
| `tests/tdd/test_official_alert_dedup_timespan.py` | MODIFY (falls nötig) | Explizite Gegenprobe „echte Lücke bleibt eigene Warnung" bleibt grün |

### Estimated Changes

- Files: 1 Produktivdatei, 2 Testdateien
- LoC: +20/-5 Produktivcode; +90/-10 Tests

## Implementation Details

### 1. Berührung zählt als Überlappung

Zeile 485 heute:

```python
if alert_vf < cand_vt and cand_vf < alert_vt:
```

Künftig `<=` auf beiden Seiten:

```python
if alert_vf <= cand_vt and cand_vf <= alert_vt:
```

Ein Fenster, das exakt dort beginnt, wo das andere endet (`14:00–15:00Z` nach
`13:00–14:00Z`), zählt jetzt als überlappender Kandidat. Eine echte Lücke — und sei sie
nur eine Sekunde — bleibt außerhalb des `<=`-Bereichs und fällt weiter auf
`_exact_match_verdict` zurück (meldet).

### 2. Containment vor der Vorverlegungs-Prüfung, mit Zeitnähe-Guard

Nach der Kandidaten-Auswahl (Tie-Break, Zeile 493-497) wird vor der bestehenden
Eskalations-/Vorverlegungs-Prüfung (Zeile 498) geprüft, ob das neue Fenster den
gewählten Kandidaten vollständig umschließt:

```python
is_containment = alert_vf <= kandidat_vf and alert_vt >= kandidat_vt
```

Ist das der Fall UND ist der Kandidat frisch (`reported_at` höchstens 6h alt), dann **entfällt die
≥2h-Vorverlegungs-Ausnahme** — der Fall gilt als reiner Granularitätswechsel und wird
still fortgeschrieben, es sei denn, die Stufe ist gestiegen. Die bestehende
Eskalations-Bedingung (`alert.level > kandidat_level`) bleibt unter Containment
unverändert wirksam — nur der Zeit-Vorverlegungs-Teil der Oder-Bedingung wird
unterdrückt:

```python
escalated = alert.level > kandidat_level
containment_greift = is_containment and kandidat_frisch   # reported_at <= 6h vor `now`
vorverlegung = (not containment_greift) and (kandidat_vf - alert_vf) >= timedelta(hours=2)
if escalated or vorverlegung:
    return True, None, None
# sonst: stille Revision wie bisher (merged_entry, stale_key)
```

> **Korrektur 2026-08-17 (in der GREEN-Phase gefunden).** Eine frühere Fassung dieses
> Blocks trug den Frische-Guard als eigenen Nachsatz:
> `if is_containment and not _kandidat_is_fresh(...): return _exact_match_verdict()`.
> Das ist **falsch** und macht den freigegebenen, unveränderten Fall
> `ac2-nur-verlaengert-still` (#1685 AC-2) rot: „nur verlängert" (gleicher Beginn,
> späteres Ende) **ist** formal Containment, und wenn dessen `reported_at` älter als 6h
> ist, hätte der Nachsatz einen bislang stillen Fall in eine Meldung gedreht — obwohl
> Containment dort gar nichts entscheidet (Vorverlegung = 0h, der Fall wäre ohnehin
> still). Der Guard darf **ausschliesslich** die Containment-Ausnahme unterdrücken und
> keine Fälle umdrehen, die auch ohne Containment still wären. Die oben stehende Fassung
> leistet genau das und ist die implementierte.

Ist der Kandidat NICHT frisch (älter als 6h), greift Containment nicht — der Fall
fällt auf `_exact_match_verdict` zurück und meldet. Das verhindert, dass ein
Wochen alter, nie bereinigter State-Eintrag (`AlertStateService.reset()` behält
`official_alert:`-Einträge über den Briefing-Reset hinweg, #1614) eine völlig neue,
unabhängige Warnung derselben Region+Gefahr fälschlich verschluckt.

### Nachgerechnet: Kirchbach 2026-08-16 (drei Fenster, alle Stufe 2.0)

1. `13:00–14:00Z` (13:15:14) — kein Kandidat im leeren State → meldet. State: Eintrag mit `reported_at=13:15:14`.
2. `14:00–15:00Z` (13:45:02) — Berührung mit Kandidat 1 (`14:00 <= 14:00`) zählt jetzt als Überlappung. Kein Containment (`14:00 <= 13:00` ist falsch). Keine Eskalation, keine Vorverlegung (`13:00 − 14:00` negativ) → still fortgeschrieben, `reported_at` bleibt `13:15:14` (übernommen vom Kandidaten, unverändertes #1685-Verhalten).
3. `11:00–20:00Z` (16:30:02) — überlappt den einzigen verbliebenen State-Eintrag (`14:00–15:00Z`). Containment: `11:00 <= 14:00` und `20:00 >= 15:00` → ja. Guard: `16:30:02 − 13:15:14 = 3h15m`, innerhalb 6h → Containment greift. Keine Eskalation → still.

**Ergebnis: genau eine Meldung** (Schritt 1).

### Nachgerechnet: Obertilliach 2026-08-11 (drei Fenster, alle Stufe 2.0)

1. `15:00–16:00Z` (14:30:14) — kein Kandidat → meldet.
2. `17:00–18:00Z` (15:45:22) — geprüft gegen Kandidat 1 (`15:00–16:00Z`): `alert_vf=17:00 <= cand_vt=16:00`? **Nein** — echte Lücke von einer Stunde zwischen `16:00Z` und `17:00Z`. Kein Kandidat gefunden → `_exact_match_verdict` → **meldet als eigenständige, neue Warnung**.
3. `13:00–19:00Z` (17:45:09) — überlappt/umschließt BEIDE bisherigen State-Einträge (Fenster 1 bleibt als verwaister Eintrag stehen, #1685 Known Limitation). Tie-Break wählt den mit höherem `reported_at` bei gleicher Stufe: Kandidat 2 (`17:00–18:00Z`, `reported_at=15:45:22`). Containment: `13:00 <= 17:00` und `19:00 >= 18:00` → ja. Guard: `17:45:09 − 15:45:22 = 2h`, innerhalb 6h → Containment greift. Keine Eskalation → still.

**Ergebnis: GENAU ZWEI Meldungen** (Schritt 1 und Schritt 2) — nicht eine. Die zweite
Meldung ist nach der neuen Regel weiterhin berechtigt, weil zwischen Fenster 1 und
Fenster 2 eine echte, einstündige Lücke liegt (`16:00Z` bis `17:00Z`); erst das dritte,
umschließende Fenster wird korrekt als stille Revision erkannt. Dieses Ergebnis ist
absichtlich nicht auf „eine Meldung" geschönt — es ist die tatsächliche Konsequenz der
PO-Regel „echte Lücke bleibt eigene Warnung".

## Zu revidierende Zusicherung

`tests/tdd/test_official_alert_revision_dedup.py`, Parametrisierung um Zeile 198-207,
Fall `ac6-kein-zeit-ueberlapp-meldet`: deckt heute pauschal „kein Zeit-Überlapp ⇒
meldet" ab, inklusive des Teilfalls „exakt aneinandergrenzend" (`alert_vf == cand_vt`).
**Dieser Teilfall wird durch diese Spec revidiert** (PO-Entscheid 2026-08-17,
Kontext-Doc Abschnitt „PO-Entscheidungen"): exakt aneinandergrenzende Fenster gelten
künftig als dieselbe Warnung und bleiben still. Der andere Teilfall — eine echte Lücke,
und sei sie nur eine Sekunde — bleibt unverändert bestehen und meldet weiterhin
(nachgewiesen an Obertilliach Schritt 2 oben). Der Testfall wird in zwei getrennte
Parametrisierungen aufgeteilt: `ac6-echte-luecke-meldet` (bleibt `expect_report=True`)
und `ac6b-beruehrung-still` (neu, `expect_report=False`).

### Nachtrag 2026-08-17 (in der RED-Phase gefunden): eine ZWEITE Fundstelle

Die obige Angabe war unvollständig — dieselbe Zusicherung steht ein zweites Mal an
anderer Stelle, gefunden beim Schreiben der Tests:

`test_ac1_ac3_ac10_ac11_trip_checker_real_entry`, Teilfall `ac11` (vormals um Zeile
539-541), prüft denselben Sachverhalt über den **echten Einstieg**
`check_official_alert_triggers` statt über die reine Funktion:

```python
adjacent = _run_trip_chain("ac11", [(0, 0, 2), (8, 8, 2)])
assert len(adjacent[1]) == 1, "AC-11: angrenzend/nicht-ueberlappend muss neu gemeldet werden"
```

Wegen `base_to == base_from + 8h` startet das zweite Fenster **exakt** bei `base_to` —
das ist der Berührungsfall aus AC-1. #1685 AC-11 (Herkunft: #1245 AC-4) und #1657 AC-1
können nicht beide gelten.

**Entscheidung:** Die freigegebene Regel gilt an **beiden** Fundstellen — der PO hat am
2026-08-17 die Regel freigegeben („berührende Fenster sind dieselbe Warnung"), nicht eine
einzelne Codezeile. Die Assertion wird auf „meldet nicht erneut" umgestellt. Nutzen
obendrein: AC-1 ist damit nicht nur an der reinen Funktion abgesichert, sondern auch am
echten Trip-Einstieg — also dort, wo die Zusicherung tatsächlich wirkt.

**Lehre für die Spec-Arbeit:** Die zuerst genannte Fundstelle war eine Stichprobe, keine
Vollzählung. Bei „diese Zusicherung wird revidiert" ist die Klasse auszuzählen, nicht das
zuerst gefundene Exemplar zu benennen.

## Expected Behavior

- **Input:** `official_alert_revision_verdict(alert, state, now=None)` — eine zu prüfende
  `OfficialAlert` (mit `valid_from`/`valid_to`, `level`, Identitätsfeldern), das
  Melde-Gedächtnis `state` (Schlüssel → Eintrag mit `last_reported_value`, `reported_at`,
  `valid_from`, `valid_to`) und optional eine Referenzzeit für den 6h-Frische-Guard.
- **Output:** unverändertes Tripel `(should_report, stale_key, merged_entry)`.
  - `(True, None, None)` — melden: exakter Neuzugang, Stufenerhöhung, echte Lücke, echte
    nicht umschließende Vorverlegung ≥2h, oder Containment mit veraltetem (>6h) Kandidaten.
  - `(False, stale_key, merged_entry)` — stille Revision: Berührung, echte Überlappung ohne
    Eskalation, oder Containment mit frischem Kandidaten. Der Aufrufer entfernt `stale_key`
    aus dem State, legt `merged_entry` unter dem neuen Schlüssel ab und persistiert sofort.
- **Side effects:** keine innerhalb der Funktion — sie ist rein und schreibt weder State noch
  Dateien. Die Persistenz bleibt Sache der beiden Aufrufstellen (`trip_alert.py:1502-1508`,
  `compare_official_alert.py:274-279`), deren Verhalten unverändert bleibt.

## Test Plan

### Test-Schicht

Kern-Schicht (deterministisch): `official_alert_revision_verdict` ist eine reine
Funktion über `dict`/`OfficialAlert`, kein Netz, kein Mock-Theater.

**Zeit wird injiziert, nicht gemessen.** Jeder Test, der den 6h-Frische-Guard berührt
(Test 4 und 5), reicht `now` explizit herein und setzt `reported_at` als festen Wert
relativ dazu. Damit ist die 6h-Grenze exakt prüfbar; kein Test hängt an der Laufzeituhr.
Das ist Pflicht, keine Stilfrage: Der Guard ist die einzige Sicherung dagegen, dass eine
echte neue Warnung verschluckt wird — ein an der Grenze sporadisch rot werdender Test
würde irgendwann als „flaky" abgetan und die Sicherung fiele still aus.

### Automated Tests (TDD RED)

- [ ] **Test 1** (Berührung, still): GIVEN im Melde-Gedächtnis steht eine Warnung mit
  Fenster `13:00–14:00Z` GELB, WHEN dieselbe Identität+Gefahr mit exakt anschließendem
  Fenster `14:00–15:00Z` GELB geprüft wird, THEN meldet der Checker sie NICHT erneut.
- [ ] **Test 2** (echte Lücke, meldet): GIVEN dieselbe Ausgangslage wie Test 1, WHEN
  das neue Fenster `14:00:01–15:00Z` geprüft wird (eine Sekunde Lücke), THEN meldet der
  Checker die Warnung als eigenständige, neue Warnung.
- [ ] **Test 3** (Containment, frisch, still): GIVEN im Melde-Gedächtnis stehen zwei
  frische Schmaleinträge (`13:00–14:00Z`, `14:00–15:00Z`, `reported_at` vor wenigen
  Minuten), WHEN ein breites Fenster `11:00–20:00Z` derselben Identität+Gefahr geprüft
  wird, THEN meldet der Checker es NICHT erneut, obwohl der Beginn 3h früher liegt.
- [ ] **Test 4** (Zeitnähe-Guard, meldet): GIVEN derselbe Containment-Fall wie Test 3,
  aber der Bestandskandidat wurde vor mehr als 6h gemeldet (`reported_at` vor 7h), WHEN
  das breite Fenster geprüft wird, THEN meldet der Checker es erneut als eigenständige
  Warnung.
- [ ] **Test 5** (Zeitnähe-Guard, Grenzfall still): GIVEN derselbe Containment-Fall wie
  Test 3, aber der Bestandskandidat wurde vor genau 5h59min gemeldet, WHEN das breite
  Fenster geprüft wird, THEN bleibt der Checker still (Guard-Grenze liegt bei >6h, nicht
  ≥6h).
- [ ] **Test 6** (Stufenerhöhung überlebt Containment): GIVEN derselbe Containment-Fall
  wie Test 3, aber das breite Fenster trägt Stufe ORANGE statt GELB, WHEN es geprüft
  wird, THEN meldet der Checker es trotz Containment erneut als Alarm.
- [ ] **Test 7** (Vorverlegung ohne Containment meldet weiterhin): GIVEN im
  Melde-Gedächtnis steht ein Fenster `14:00–22:00Z` GELB, WHEN ein NICHT umschließendes
  Fenster `12:00–20:00Z` GELB geprüft wird (2h früherer Beginn, aber kein Containment
  des Bestandskandidaten, da `12:00 <= 14:00` und `20:00 >= 22:00` NICHT beide gelten),
  THEN meldet der Checker die Warnung erneut wie vor dieser Spec (#1685 AC-3
  unverändert).
- [ ] **Test 8** (Kirchbach-Regression): GIVEN die drei realen Fenster
  `13:00–14:00Z`/13:15:14, `14:00–15:00Z`/13:45:02, `11:00–20:00Z`/16:30:02, alle Stufe
  2.0, WHEN sie nacheinander geprüft werden, THEN meldet der Checker genau einmal
  (beim ersten Fenster), die beiden folgenden bleiben still.
- [ ] **Test 9** (Obertilliach-Regression, ZWEI Meldungen): GIVEN die drei realen
  Fenster `15:00–16:00Z`/14:30:14, `17:00–18:00Z`/15:45:22, `13:00–19:00Z`/17:45:09,
  alle Stufe 2.0, WHEN sie nacheinander geprüft werden, THEN meldet der Checker GENAU
  ZWEI Mal (erstes und zweites Fenster, echte Lücke dazwischen), das dritte, umschließende
  Fenster bleibt still.
- [ ] **Test 10** (Ortsvergleich-Parität): GIVEN dieselbe Containment-Ausgangslage wie
  Test 3, aber im Melde-Gedächtnis eines Ortsvergleichs-Orts
  (`CompareOfficialAlertService._detect`), WHEN das breite Fenster für diesen Ort
  geprüft wird, THEN verhält sich der Ortsvergleichs-Pfad identisch zum Trip-Pfad
  (still).
- [ ] **Test 11** (Stufenerhöhung bei reiner Überlappung, Regression #1685 AC-5): GIVEN
  ein überlappendes, NICHT umschließendes Fenster derselben Identität+Gefahr mit
  gestiegener Stufe, WHEN es geprüft wird, THEN meldet der Checker es weiterhin — wie
  vor dieser Spec.
- [ ] **Test 12** (Fail-soft unverändert, Regression): GIVEN eine Warnung ohne
  `valid_from`/`valid_to` steht mit unverändertem Level im Melde-Gedächtnis, WHEN
  dieselbe zeitlose Warnung erneut geprüft wird, THEN entscheidet weiterhin
  ausschließlich der exakte Schlüsseltreffer, keine Containment- oder
  Berührungsprüfung greift.

## Acceptance Criteria

- **AC-1:** Given im Melde-Gedächtnis steht eine amtliche Warnung mit Fenster `13:00–14:00Z` GELB, When dieselbe Identität+Gefahr mit exakt anschließendem Fenster `14:00–15:00Z` GELB geprüft wird, Then meldet der Checker sie NICHT erneut (Berührung zählt als Überlappung).
  - Test: Test 1.

- **AC-2:** Given dieselbe Ausgangslage wie AC-1, When das neue Fenster eine Sekunde später beginnt (`14:00:01–15:00Z`, echte Lücke), Then meldet der Checker die Warnung als eigenständige, neue Warnung — das ist die ausdrückliche Grenze der Revision.
  - Test: Test 2.

- **AC-3:** Given im Melde-Gedächtnis stehen zwei frische Schmalfenster derselben Identität+Gefahr (`reported_at` vor wenigen Minuten), When ein breites, beide vollständig umschließendes Fenster geprüft wird, Then meldet der Checker es NICHT erneut, obwohl sein Beginn früher liegt als der jüngste Kandidat.
  - Test: Test 3.

- **AC-4:** Given derselbe Containment-Fall wie AC-3, aber der Bestandskandidat wurde vor mehr als 6 Stunden gemeldet, When das breite Fenster geprüft wird, Then meldet der Checker es erneut als eigenständige Warnung (Zeitnähe-Guard verhindert das Verschlucken einer echten neuen Warnung durch einen veralteten State-Eintrag).
  - Test: Test 4.

- **AC-5:** Given derselbe Containment-Fall wie AC-3, aber die neue Warnung trägt eine höhere Stufe als der umschlossene Kandidat, When sie geprüft wird, Then meldet der Checker sie trotz Containment als Alarm — die Eskalations-Zusicherung aus #1685 bleibt unter Containment unverändert wirksam.
  - Test: Test 6.

- **AC-6:** Given im Melde-Gedächtnis steht ein Fenster mit spätem Beginn, When ein neues, NICHT umschließendes Fenster mit mindestens 2 Stunden früherem Beginn geprüft wird, Then meldet der Checker die Warnung erneut — die Vorverlegungs-Ausnahme aus #1685 bleibt für echte, nicht umschließende Vorverlegungen unverändert bestehen.
  - Test: Test 7.

- **AC-7 (Kirchbach-Regression):** Given die drei realen Kirchbach-Fenster vom 2026-08-16 (`13:00–14:00Z`, `14:00–15:00Z`, `11:00–20:00Z`, alle Stufe 2.0, in dieser Reihenfolge), When sie nacheinander geprüft werden, Then meldet der Checker genau EINMAL (beim ersten Fenster), die beiden folgenden Fenster bleiben still fortgeschrieben.
  - Test: Test 8.

- **AC-8 (Obertilliach-Regression, nachgerechnet):** Given die drei realen Obertilliach-Fenster vom 2026-08-11 (`15:00–16:00Z`, `17:00–18:00Z`, `13:00–19:00Z`, alle Stufe 2.0, in dieser Reihenfolge, mit einer echten einstündigen Lücke zwischen Fenster 1 und Fenster 2), When sie nacheinander geprüft werden, Then meldet der Checker GENAU ZWEIMAL (erstes und zweites Fenster), nur das dritte, umschließende Fenster bleibt still — nicht „genau einmal".
  - Test: Test 9.

- **AC-9 (Ortsvergleich-Parität):** Given dieselbe Containment-Ausgangslage wie AC-3, aber im Melde-Gedächtnis eines Ortsvergleichs-Orts statt eines Trips, When der Ortsvergleichs-Checker (`_detect`) das breite Fenster prüft, Then verhält er sich identisch zum Trip-Pfad — still, wie in AC-3.
  - Test: Test 10.

- **AC-10 (Regression, Fail-soft unverändert):** Given eine Warnung ohne `valid_from`/`valid_to` steht mit unverändertem Level im Melde-Gedächtnis, When dieselbe zeitlose Warnung erneut geprüft wird, Then entscheidet weiterhin ausschließlich der exakte Schlüsseltreffer — keine Berührungs- oder Containment-Prüfung greift bei fehlenden Zeitfeldern.
  - Test: Test 12.

## Non-Regression

| Quelle | Zusicherung | Auswirkung dieser Spec |
|---|---|---|
| `test_official_alert_revision_dedup.py:205` (`ac5-stufe-gestiegen-meldet`) | Stufenerhöhung meldet trotz Überlappung | Unverändert, zusätzlich explizit unter Containment geprüft (AC-5) |
| `test_official_alert_revision_dedup.py:198-207` (`ac6-kein-zeit-ueberlapp-meldet`) | **PRÄZISIERT (siehe „Zu revidierende Zusicherung")**: nur der Teilfall „echte Lücke" bleibt bestehen (AC-2), der Teilfall „Berührung" wird revidiert (AC-1) |
| `test_official_alert_revision_dedup.py:544, 615` | Mandantentrennung und Orts-Isolation im Ortsvergleich | Unverändert — beide Prüfungen laufen weiter auf getrennten `AlertStateService`-Instanzen je Nutzer/Ort |
| #1685 AC-3/AC-4 (Vorverlegung, kein Containment) | Echte Vorverlegung ≥2h ohne Containment meldet | Unverändert, AC-6 dieser Spec sichert das explizit ab (Test 7) |
| `official_alerts.py:468-469` (Fail-soft) | Fehlende `valid_from`/`valid_to` ⇒ exakter Schlüsseltreffer entscheidet | Unverändert (AC-10) |
| #1245 AC-1 / `dedupe_official_alerts` | Anzeige zeigt überlappende/berührende Perioden weiterhin getrennt | Unverändert — nur das Melde-Gedächtnis wird angefasst, nicht die Anzeige-Ebene |
| ADR-0040 | „Eine gerissene Grenze wird einmal gemeldet, erneut erst bei Verschärfung" | Bestätigt und für Berührung/Containment präzisiert |

## Nicht in dieser Scheibe

- **Aspekt (c) — identischer Anzeigetext bei stundenfeinen Teilfenstern** (Kontext-Doc,
  Abschnitt „Zwei bestätigte Mechanismen, ein widerlegter"): mechanisch widerlegt als
  Bündelungs-Effekt, ungeklärt bleibt, ob der PO-Befund „beide Meldungen trugen `So13-22`"
  auf einer anderen Ursache beruht. Braucht rohe GeoSphere-Payload-Evidenz zur Klärung —
  eigenes Issue, PO-Entscheid 2026-08-17.
- Aspekt (c) ist damit ausdrücklich NICHT durch diese Spec geschlossen, auch wenn die
  Mechanik (a)/(b) behoben ist.

## Known Limitations

- **Verwaiste State-Einträge bleiben bestehen** (unverändert aus #1685): wird ein
  Kandidat durch Tie-Break nicht ausgewählt (z.B. Fenster 1 im Obertilliach-Fall), bleibt
  sein Schlüssel unverändert im Melde-Gedächtnis stehen. Harmlos für die Melde-Logik
  (spätere Prüfungen wählen wieder per Tie-Break), aber ohne separate Bereinigung wächst
  das Melde-Gedächtnis pro Identität+Gefahr unbegrenzt.
- **Der 6h-Zeitnähe-Guard schützt nur den Containment-Zweig**, nicht die
  Berührungs-Prüfung (Änderung 1) und nicht den bestehenden Überlappungs-/
  Vorverlegungs-Zweig aus #1685. Ein Wochen alter, exakt berührender oder echt
  überlappender State-Eintrag wird weiterhin als Kandidat gefunden — das ist
  unverändertes #1685-Verhalten, nicht Teil dieser Scheibe.
- **Der 6h-Guard braucht eine Referenzzeit — sie wird injizierbar geführt.** Die
  Funktion erhält einen **optionalen** Parameter `now: datetime | None = None`; ist er
  `None`, gilt `datetime.now(timezone.utc)`. Beide Aufrufstellen (`trip_alert.py:1499`,
  `compare_official_alert.py:268`) bleiben dadurch **unverändert** — der Default greift.
  Tests reichen `now` explizit herein und prüfen die 6h-Grenze damit exakt statt relativ
  zur Laufzeituhr.

  **Begründung (PO-Punkt 2026-08-17):** Ein Guard, dessen Testbarkeit an der Wanduhr
  hängt, wird ausgerechnet an der Grenze unzuverlässig — und dieser Guard ist die
  einzige Sicherung dagegen, dass eine echte neue Warnung verschluckt wird. Ein
  sporadisch rot werdender Test an genau dieser Stelle wird erfahrungsgemäß irgendwann
  als „flaky" abgetan, und damit fällt die Sicherung still aus. Der optionale Parameter
  kostet nichts und macht AC-4 deterministisch prüfbar.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Chirurgische Präzisierung zweier Teilregeln innerhalb der bestehenden
  #1685-Architektur (dieselbe Funktion, dieselbe Signatur, keine neue Grundsatz-
  entscheidung zu Kanälen, Provider, Datenmodell, Auth oder Editor-Paradigma).
  ADR-0040 deckt die Grundrichtung bereits ab.

## Changelog

- 2026-08-17: Initial spec created (Issue #1657, PO-Entscheidung 2026-08-17 aus dem Analyse-Dialog übernommen; Obertilliach-Regression eigenständig nachgerechnet, Ergebnis „zwei Meldungen" statt geschönter „eine Meldung").
