---
entity_id: feat_2050_s4b_messluecken_protokoll
type: feature
created: 2026-08-23
updated: 2026-08-23
status: draft
workflow: feat-2050-s4b-messluecken-protokoll
version: "1.0"
tags: [alarm, nowcast, radar, protokoll, messluecken]
---

# Messlücken der Radar-Ausdehnung landen im Alarmprotokoll (Issue #2050, Scheibe S4b)

## Approval

- [ ] Approved

## Purpose

Ein Radar-Alarm nennt seit #2051 S2a die räumliche Ausdehnung des Regenereignisses
(„km 2–6"). Fällt einer der bis zu sechs Messpunkte entlang der Reststrecke aus, verschwindet
er in `derive_rain_zones` kommentarlos — eine Ausdehnung, die aus vier von sechs Punkten
stammt, ist nachträglich nicht von einer vollständig vermessenen zu unterscheiden. Diese
Scheibe erfüllt Anforderung **E-1** (Nachvollziehbarkeit: Messpunkt und Vergleichsbasis gehören
ins Protokoll) für die Ausdehnungs-Messpunkte, indem sie die bereits geschriebenen, aber nie
gebauten **AC-12/AC-13 der S4a-Spec** baut: Zahl und km-Lage ausgefallener Messpunkte werden im
Alarmprotokoll festgehalten.

## Herkunft

Aus `docs/specs/modules/feat_2050_s4a_radar_teilausfall.md`, Abschnitt „Acceptance Criteria"
(dort geschrieben, nie gebaut):

> **AC-12:** Given ein ausgelöster Radar-Alarm, dessen räumliche Ausdehnung aus Messpunkten
> bestimmt wurde, von denen mindestens einer ausgefallen ist (`derive_rain_zones` überspringt
> ihn heute kommentarlos, `rain_extent.py:77-78`), When der Alarm protokolliert wird, Then hält
> der Protokolleintrag fest, dass und an welcher Stelle Messpunkte fehlten — eine Ausdehnung,
> die aus vier von sechs Punkten stammt, ist nachträglich als solche erkennbar und nicht von
> einer vollständig vermessenen zu unterscheiden (Anforderung E-1: Messpunkt und
> Vergleichsbasis gehören ins Protokoll).
>
> **AC-13:** Given der auslösende erste Messpunkt meldet Regen, während **alle** Folgepunkte
> ausfallen, When der Alarm protokolliert wird, Then weist der Eintrag sämtliche Folgepunkte
> als fehlend aus — die Ausdehnungsaussage schrumpft in diesem Fall still auf den einen
> gemessenen Punkt zusammen (`km X-X`), und genau dieser Extremfall muss im Protokoll vom
> echten Befund „Regen nur auf einem Kilometer" unterscheidbar sein.

## Source

- **File:** `src/services/trip_alert.py` — `_radar_e1_fields()` (Suchbegriff
  `def _radar_e1_fields(`, ~`:180`), Aufrufstelle `_e1 = _radar_e1_fields(` (~`:1899`),
  Mehrpunkt-Abfrage zwischen der Zuweisung `_zonen_ergebnisse: list = [_zonen_messwert(result)]`
  (~`:1698`) und der Verdichtung `derive_rain_zones(_punkte, _zonen_ergebnisse)` (~`:1722`)
- **File:** `src/services/alert_log.py` — `append_entry()` (Suchbegriff `def append_entry(`,
  ~`:384`), `append_suppressed_entry()` (Suchbegriff `def append_suppressed_entry(`, ~`:525`),
  geteilter Schreib-Helfer `_apply_e1_fields()` (Suchbegriff `def _apply_e1_fields(`, ~`:341`)
  samt `_E1_FIELD_TYPES` (~`:331`)
- **Identifier:** `_radar_e1_fields`, `append_entry`, `append_suppressed_entry`,
  `_apply_e1_fields`

Schicht: ausschließlich Python-Core (`src/services/`). Kein Go-, kein Frontend-Anteil —
`internal/store/log.go` liest weiterhin nur die bestehenden Felder aus `entries`, das neue
Feld bleibt dort unsichtbar, wie schon die bestehenden E-1-Größen aus #2050 S6.

## Zuschnitt-Entscheid: `rain_extent.py` bleibt unangetastet

Der naheliegende Vorschlag — „eine Lücke schließt die laufende Zone ab, dann stimmt der Text
überall automatisch" — wurde geprüft und **verworfen**. Beide denkbaren Zonenbildungen
(Zusammenwachsen über die Lücke hinweg *oder* Trennen an der Lücke) behaupten etwas
Ungemessenes: Zusammenwachsen behauptet durchgehende Nässe, Trennen behauptet Trockenheit.
Ehrlich ist nur eine **Kennzeichnung** der Lücke — und die ist Wortarbeit, kein Zonen-Umbau.

Zwei Tests aus #2051 S2a schreiben das heutige Nicht-Trennen ausdrücklich fest, beide mit
Positivkontrolle:

- `tests/tdd/test_regen_ausdehnung_zonenbildung.py::test_ac11_datenloser_punkt_faellt_aus_der_zonenbildung_heraus`
  (~`:148`) — Ergebnis **mit** Lücke ist identisch zu „Punkt komplett entfernt".
- `tests/tdd/test_regen_ausdehnung_textstellen.py::test_e4_punkt_ohne_frames_trennt_die_nasszone_nicht`
  (~`:503`) — `throttled` **und** `data_unavailable` je einzeln: genau **eine** Zone.

Diese Scheibe **erhält** die Lückeninformation und protokolliert sie zusätzlich (E-1). Die
Zonenbildung selbst bleibt byte-gleich, beide S2a-Wächter bleiben grün. Die Textaussage beider
Verzerrungsrichtungen (Zonen wachsen zu groß bzw. zu klein zusammen) ist bewusst **nicht** Teil
dieser Scheibe — siehe „Nicht Ziel".

## Estimated Scope

- **LoC:** ~30–40 Produktivcode (ohne Tests); mit den zwölf ACs zugehörigen Tests kommen
  voraussichtlich weitere ~80–140 Zeilen dazu
- **Files:** 3 — 2 Produktivdateien, 1 neue Testdatei
- **Effort:** low
- **Risiko:** LOW — additiv, fail-soft, keine Verhaltensänderung an einer bestehenden,
  freigegebenen Zusicherung (Zonenbildung bleibt unangetastet)

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `src/services/trip_alert.py::_zonen_messwert` | function | Bestehender Filter (#2051 S2a, E4), liefert `None` für alle drei Lückenwege — unverändert, nur ausgewertet |
| `src/services/trip_alert.py::_punkte` | local list | Positionsgleich zu `_zonen_ergebnisse`; `_punkte[i].distance_from_start_km` liefert die km-Lage einer Lücke |
| `src/services/alert_log.py::_apply_e1_fields` | function | Geteilter Schreib-Helfer beider `append_*`-Funktionen — bekommt den neuen Parameter, EINE Stelle für beide Aufrufer |
| `src/services/alert_log.py::_E1_FIELD_TYPES` | module data | Typtabelle für die additiv-defensive Serialisierung — bekommt einen neuen Eintrag (`dict`) |
| `tests/tdd/test_regen_ausdehnung_textstellen.py::_ZonenRadar` | test helper | Echte `RadarNowcastService`-Unterklasse am DI-Seam von `TripAlertService` (~`:383`), steuerbar über `trocken_index`/`trocken_felder`/`ausnahme_index`/`weitere_trockene` — Muster für die neue Testdatei |
| `tests/tdd/test_regen_ausdehnung_zonenbildung.py`, `tests/tdd/test_regen_ausdehnung_textstellen.py` | test | Regressions-Wächter, müssen unverändert grün bleiben (AC-12 dieser Spec) |

## Betroffene Dateien

| Datei | Änderungstyp | Beschreibung |
|---|---|---|
| `src/services/trip_alert.py` | MODIFY | `_radar_e1_fields()` um die Lücken-Ableitung erweitern (**innerhalb** des bestehenden `try`), Aufrufstelle `_e1 = _radar_e1_fields(...)` um die zwei nötigen Argumente ergänzen (`_punkte`, `_zonen_ergebnisse`) |
| `src/services/alert_log.py` | MODIFY | `append_entry()` und `append_suppressed_entry()` je um `measurement_gaps: Optional[dict] = None`; geteilter Helfer `_apply_e1_fields()` und `_E1_FIELD_TYPES` um denselben Schlüssel erweitert (EINE Ableitung für beide Aufrufer, Muster #2050 S6) |
| `tests/tdd/test_radar_messluecken_protokoll.py` | CREATE | AC-1 bis AC-12, benannt nach Verhalten, nicht nach Issue-Nummer |

**`src/services/rain_extent.py`: NICHT betroffen.** Ausdrücklich — siehe „Zuschnitt-Entscheid".

## Implementation Details

### Technischer Ansatz: Ableitung im Aufrufer, nicht in `derive_rain_zones`

Drei Wege wurden gegeneinander bewertet:

| Weg | Idee | Urteil |
|---|---|---|
| A | additives Feld an `RainZone` | ❌ semantisch unmöglich — eine Lücke liegt *zwischen* Zonen, keine Zone könnte sie tragen |
| B | `derive_rain_zones` gibt Lücken zusätzlich zurück | ❌ Rückgabetyp-Änderung ⇒ Referenzfeger über fremde Testdateien, und Doppelarbeit, weil der Aufrufer die Rohinformation längst hat |
| **C** | **Lücken im Aufrufer ableiten, `rain_extent.py` gar nicht anfassen** | ✅ gewählt |

In `check_radar_alerts` liegt zwischen der Zuweisung `_zonen_ergebnisse: list = [...]`
(~`:1698`) und der Verdichtung `derive_rain_zones(_punkte, _zonen_ergebnisse)` (~`:1722`)
bereits index-genauer Zugriff auf `_punkte[i].distance_from_start_km` **und**
`_zonen_ergebnisse[i] is None` — exakt die Rohinformation, die AC-12 verlangt.
`derive_rain_zones` bekommt nur den verdichteten Rest und bleibt unverändert.

### Datenform

Neues optionales Feld `measurement_gaps`, abgeleitet in `_radar_e1_fields()` (~`:180`) —
Suchbegriff `def _radar_e1_fields(` — dem bestehenden Muster „**eine** Ableitung für alle
Protokollstellen eines Zweigs" folgend (#2050 S6). Die Funktion wird genau einmal gerufen
(Suchbegriff `_e1 = _radar_e1_fields(`, ~`:1899`) und ihr Ergebnis per `**_e1` an
`append_entry()` gespreadet.

```python
"measurement_gaps": {
    "points_total": <Zahl der Messpunkte>,
    "points_measured": <Zahl mit verwertbarem Ergebnis>,
    "gap_km": [<km-Lage jedes ausgefallenen Punkts, auf eine Nachkommastelle gerundet>],
}
```

Das Feld wird **immer** gesetzt, sobald die Mehrpunkt-Abfrage lief — auch bei leerer
`gap_km`-Liste. Ein *fehlendes* Feld hätte sonst drei Bedeutungen zugleich: „alles gemessen",
„Alteintrag von vor dem Deploy" und „Ableitung fail-soft gescheitert". Genau diese
Ununterscheidbarkeit ist der Mangel, den die Scheibe beheben soll — sie darf nicht auf einer
Ebene höher neu entstehen (AC-4).

- **AC-2 erfüllt:** `points_total`/`points_measured`/`gap_km` nennen Zahl *und* Lage.
- **AC-3 erfüllt:** der Extremfall (`points_total=6, points_measured=1`) ist strukturell vom
  echten Befund „Regen nur auf einem Kilometer" (`points_total == points_measured`)
  unterscheidbar — an Zahlen, nicht am Text.

Die km-Rundung folgt derselben Nachkommastelle wie die gemessene km-Spanne
(`segments.format_alert_location`) und das Zonen-Rendering aus #2051 S2a.

### Geteilter Schreib-Helfer: `_apply_e1_fields` und `_E1_FIELD_TYPES` mitziehen

`append_entry()` und `append_suppressed_entry()` schreiben ihre E-1-Größen beide über
`_apply_e1_fields()` (~`:341`), gesteuert durch die Typtabelle `_E1_FIELD_TYPES` (~`:331`).
Ein neues Feld an nur einer der beiden `append_*`-Funktionen vorbeizuschreiben würde diese
zentrale, additiv-defensive Serialisierung (Typprüfung, `None` → Absenz, fail-soft mit
`logger.warning`) umgehen. Die Erweiterung um `measurement_gaps: dict` bleibt innerhalb von
`src/services/alert_log.py` — kein zusätzliches Produktivfile, kein Bruch der
Zwei-Dateien-Vorgabe.

### Fail-soft (AC-9)

Die neue Ableitung liegt **innerhalb** des bestehenden `try`-Blocks von `_radar_e1_fields()`
(Muster `_radar_e1_fields` `:207-229`): scheitert sie, entsteht der Alarm trotzdem, nur ohne
`measurement_gaps` — dieselbe Absicherung wie bei den fünf bestehenden E-1-Größen.

### Risiko R3 aufgelöst: Index 0 kann bei einem ausgelösten Alarm nie eine Lücke sein

Drei Wege, wie der erste Messpunkt ausfällt — keiner erreicht eine Protokollzeile mit
Ausdehnung:

| Fall am ersten Punkt | Warum kein Alarm |
|---|---|
| Abruf wirft | `except` `continue`t, bevor `_zonen_ergebnisse` überhaupt existiert |
| `data_unavailable=True` | die Zonenbildung läuft zwar, aber der auslösende Zweig `continue`t vorher mit `REASON_DATA_UNAVAILABLE` (S4a) |
| `throttled=True` | impliziert `not frames` ⇒ `onset_minutes=None`; `radar_alert_due()` verlangt `onset is not None` oder `already_running` — beides falsch ⇒ stiller `continue` |

Folge: AC-13 der S4a-Spec („alle Folgepunkte fallen aus") ist wie geschrieben korrekt —
gemeint sind zwangsläufig Index 1..N-1. Diese Tatsache braucht eine eigene Positivkontrolle
(AC-8): sonst prüft niemand, dass ein Ausfall an Index 0 gar nicht bis zur Protokollzeile
kommt und die Prüfung des Extremfalls (AC-2) damit überhaupt etwas misst.

## Expected Behavior

- **Input:** ein ausgelöster Radar-Alarm, dessen Mehrpunkt-Abfrage für mindestens einen der
  Folgepunkte kein verwertbares Ergebnis liefert (geworfene Ausnahme, `throttled` oder
  `data_unavailable`).
- **Output:** der zugehörige `append_entry()`-Aufruf trägt ein `measurement_gaps`-Feld mit
  `points_total`, `points_measured` und `gap_km` — unabhängig davon, welcher der drei Wege die
  Lücke verursacht hat.
- **Side effects:** keine — die Zonenbildung, die versendete Alarmnachricht und die
  Auslöseentscheidung bleiben unverändert. Betroffen ist ausschließlich das Alarmprotokoll.

## Acceptance Criteria

- **AC-1:** Given ein Radar-Prüflauf mit drei Zonenpunkten nass–Lücke–nass (mittlerer Punkt
  ausgefallen), When der Alarm protokolliert wird, Then hält der Eintrag `measurement_gaps`
  mit der Zahl und der km-Lage genau des mittleren, ausgefallenen Punkts fest.

- **AC-2:** Given der auslösende erste Messpunkt meldet Regen, während alle Folgepunkte
  ausfallen (`points_total=6`), When der Alarm protokolliert wird, Then weist
  `measurement_gaps` `points_measured=1` und alle fünf Folgepunkte als `gap_km` aus.

- **AC-3:** Given ein echter Befund „Regen nur auf einem Kilometer" bei vollständig
  vermessener Strecke (alle sechs Punkte liefern ein Ergebnis, nur einer davon ist nass), When
  der Alarm protokolliert wird, Then zeigt `measurement_gaps` `points_total == points_measured`
  und eine leere `gap_km`-Liste — strukturell unterscheidbar vom Extremfall aus AC-2, obwohl
  beide dieselbe Ausdehnungsangabe „km X–X" im Text erzeugen könnten.

- **AC-4:** Given ein Radar-Prüflauf, dessen Mehrpunkt-Abfrage lief und für alle Punkte ein
  verwertbares Ergebnis lieferte, When der Alarm protokolliert wird, Then ist
  `measurement_gaps` trotzdem im Eintrag vorhanden, mit leerer `gap_km`-Liste und
  `points_total == points_measured` — ein fehlendes Feld darf nicht zugleich „alles gemessen"
  und „Ableitung gescheitert" bedeuten können.

- **AC-5:** Given der Abruf für einen Folgepunkt wirft eine Ausnahme, When der Alarm
  protokolliert wird, Then erscheint dieser Punkt in `gap_km` des Protokolleintrags —
  unabhängig und getrennt von den beiden anderen Lückenwegen geprüft.

- **AC-6:** Given der Abruf für einen Folgepunkt liefert `throttled=True`, When der Alarm
  protokolliert wird, Then erscheint dieser Punkt in `gap_km` des Protokolleintrags —
  unabhängig und getrennt von AC-5 und AC-7 geprüft.

- **AC-7:** Given der Abruf für einen Folgepunkt liefert `data_unavailable=True`, When der
  Alarm protokolliert wird, Then erscheint dieser Punkt in `gap_km` des Protokolleintrags —
  unabhängig und getrennt von AC-5 und AC-6 geprüft.

- **AC-8:** Given der Ausfall trifft den ersten, auslösenden Messpunkt (Ausnahme oder
  `data_unavailable=True`), When der Prüflauf durchläuft, Then entsteht dazu **keine**
  Protokollzeile mit einer Ausdehnungsangabe — der Lauf steigt vorher aus (Positivkontrolle:
  ohne diesen Nachweis würde niemand belegen, dass AC-2 tatsächlich einen Index-1..N-1-Fall
  misst).

- **AC-9:** Given die Ableitung von `measurement_gaps` scheitert (z. B. eine unerwartete
  Datenform), When der Radar-Alarmpfad geprüft wird, Then wird der Alarm trotzdem versendet und
  protokolliert — nur ohne das Feld `measurement_gaps`, kein Ausbleiben des gesamten Eintrags.

- **AC-10:** Given zwei verschiedene Nutzer erleiden im selben Prüfzyklus je eine Messlücke bei
  einem ausgelösten Radar-Alarm, When beide Alarmpfade geprüft werden, Then landet jeder
  `measurement_gaps`-Eintrag ausschließlich im Alarmprotokoll des jeweils betroffenen Nutzers.

- **AC-11:** Given ein Alarmprotokoll enthält Alteinträge ohne das Feld `measurement_gaps`
  (vor dieser Scheibe geschrieben), When das Protokoll nach dieser Scheibe erneut gelesen oder
  um einen neuen Eintrag ergänzt wird, Then bleiben die Alteinträge unverändert lesbar und
  werden nicht umgeschrieben (Read-Modify-Write).

- **AC-12:** Given die beiden bestehenden Regressions-Wächter aus #2051 S2a
  (`test_ac11_datenloser_punkt_faellt_aus_der_zonenbildung_heraus`,
  `test_e4_punkt_ohne_frames_trennt_die_nasszone_nicht`), When diese Scheibe implementiert ist,
  Then bleiben beide Tests unverändert grün und die gerenderte Ausdehnungs-Aussage (Zonenbildung
  und Text) ändert sich an keiner Stelle.

## Nicht Ziel

- **Die Zonenbildung selbst** (`rain_extent.py::derive_rain_zones`) wird nicht geändert — siehe
  „Zuschnitt-Entscheid". Beide denkbaren Änderungen (Zusammenwachsen über die Lücke hinweg
  verhindern oder an der Lücke trennen) behaupten etwas Ungemessenes; ehrlich ist nur eine
  Kennzeichnung, und die ist Wortarbeit, nicht Zonen-Umbau.
- **Die Textaussage der Alarmnachricht selbst** — die Kennzeichnung beider
  Verzerrungsrichtungen (Zonen wachsen zu groß bzw. zu klein zusammen) in `render.py` über alle
  vier Kanäle samt SMS-Kurzform. Das ist Wortarbeit über das Renderer-Commit-Gate und gehört in
  die Folge-Scheibe **S4b-2**, nach dem Merge von #2051 S2b.
- **Keine neue Alarmart und keine Änderung an der Auslöseentscheidung.** Diese Scheibe ist
  reine Buchführung — ob und wann ein Alarm auslöst, bleibt unverändert.
- **Kein neuer Alarm für den amtlichen Zweig.** `check_official_alert_triggers` kennt seinen
  Ausfall-Status im Alarmpfad weiterhin nicht — eigenständiger Nebenbefund, nicht Gegenstand
  dieser Scheibe.
- **Regel-Budget:** Diese Scheibe führt **keine** neue Pflicht-Regel und **kein** neues Gate
  ein — additive, fail-soft Erweiterung eines bestehenden Protokollierungs-Musters.

## Test Plan

### Automated Tests (TDD RED)

Neue Testdatei `tests/tdd/test_radar_messluecken_protokoll.py`, benannt nach Verhalten. Jeder
Test fährt über die **echte** Auslöseentscheidung (`check_radar_alerts`), nicht über einen Mock
der geprüften Funktion — Vorbild `tests/tdd/test_regen_ausdehnung_textstellen.py`. Das
Test-Werkzeug `_ZonenRadar` (~`:383` dort) ist eine echte `RadarNowcastService`-Unterklasse am
DI-Seam von `TripAlertService` — kein Mock, liefert die Produktiv-Dataclass, steuerbar per
Index über `trocken_index`, `trocken_felder` (z. B. `{"data_unavailable": True}`,
`{"throttled": True}`), `ausnahme_index`, `weitere_trockene`. Für AC-2 (alle Folgepunkte
ausgefallen) muss das Muster ggf. um mehrere gleichzeitige Lückenindizes erweitert werden
(Implementierungsentscheidung der RED-Phase) — kein neuer Helfer, sondern dieselbe
Steuerungsidee mit mehr Indizes.

- **AC-1:** `_ZonenRadar` mit einem `trocken_felder`-Lauf (z. B. `data_unavailable`) auf dem
  mittleren von drei Zonenpunkten; Nachweis über `alert_log.read_undelivered()` bzw. das
  geschriebene `entries`-Feld `measurement_gaps` — Zahl 1, km-Lage exakt der mittlere Punkt.
- **AC-2:** alle Folgepunkte auf einen Lückenweg gestellt; `measurement_gaps.points_total=6`,
  `points_measured=1`, `gap_km` mit fünf Einträgen.
- **AC-3 (Gegenprobe zu AC-2):** derselbe Aufbau, aber alle sechs Punkte liefern ein Ergebnis,
  nur einer ist real trocken/nass unterschiedlich — `points_total == points_measured`, leere
  `gap_km`.
- **AC-4:** Kontroll-Lauf ganz ohne Ausfall — `measurement_gaps` ist trotzdem vorhanden, mit
  leerer `gap_km`.
- **AC-5/AC-6/AC-7:** drei getrennte Testfunktionen, je ein Lückenweg (Ausnahme via
  `ausnahme_index`, `throttled` via `trocken_felder`, `data_unavailable` via `trocken_felder`)
  an genau einem Folgepunkt.
- **AC-8 (Positivkontrolle):** Ausfall am ersten Messpunkt (Ausnahme bzw.
  `data_unavailable=True`) — Nachweis, dass **keine** Ausdehnungs-Protokollzeile entsteht
  (kein `measurement_point`/`measurement_gaps`-Eintrag zu diesem Lauf).
- **AC-9 (Fail-soft):** eine gezielt fehlerhafte Eingabe an die neue Ableitung (z. B. über
  `monkeypatch` auf die Ableitungsfunktion selbst, nicht auf `_radar_e1_fields` als Ganzes) —
  der Alarm wird trotzdem versendet und protokolliert, nur ohne `measurement_gaps`.
- **AC-10:** zwei Nutzer, je ein Lückenlauf im selben Testprozess — `read_undelivered()`/
  `entries` je Nutzer geprüft, keine Vermischung.
- **AC-11:** ein vorbereiteter Alteintrag ohne `measurement_gaps` in `alert_log.json`, danach
  ein neuer Lauf für denselben Nutzer — der Alteintrag bleibt byte-identisch erhalten.
- **AC-12:** die beiden bestehenden Dateien `tests/tdd/test_regen_ausdehnung_zonenbildung.py`
  und `tests/tdd/test_regen_ausdehnung_textstellen.py` werden im selben Testlauf mitgeführt und
  bleiben grün — kein neuer Test nötig, reiner Regressionsnachweis über den vollen Testlauf der
  Scheibe.

### AC-Test-Mapping

| AC | Testfunktion (geplant) |
|---|---|
| AC-1 | `test_luecke_in_der_mitte_haelt_zahl_und_km_lage_fest` |
| AC-2 | `test_alle_folgepunkte_ausgefallen_ist_der_extremfall` |
| AC-3 | `test_echter_befund_ein_kilometer_ist_vom_extremfall_unterscheidbar` |
| AC-4 | `test_luecken_feld_ist_auch_ohne_luecke_vorhanden` |
| AC-5 | `test_geworfene_ausnahme_erscheint_als_luecke` |
| AC-6 | `test_throttled_erscheint_als_luecke` |
| AC-7 | `test_data_unavailable_erscheint_als_luecke` |
| AC-8 | `test_ausfall_am_ersten_punkt_erzeugt_keine_ausdehnungszeile` |
| AC-9 | `test_scheiternde_luecken_ableitung_kostet_den_alarm_nicht` |
| AC-10 | `test_zwei_nutzer_teilen_sich_keinen_luecken_eintrag` |
| AC-11 | `test_alteintrag_ohne_messluecken_feld_bleibt_unveraendert` |
| AC-12 | Regressionslauf der beiden #2051-S2a-Dateien im selben Testdurchgang |

## Known Limitations

- **Die Textaussage beider Verzerrungsrichtungen bleibt offen.** Weder das Zu-groß- noch das
  Zu-klein-Zusammenwachsen der Zonen über eine Lücke hinweg wird durch diese Scheibe im
  gerenderten Text kenntlich gemacht — Folge-Scheibe **S4b-2**, nach dem Merge von #2051 S2b.
- **Nur der Trip-Radarzweig.** Der Ortsvergleich-Radarpfad (`compare_radar_alert.py`) hat keine
  eigene Mehrpunkt-Ausdehnungsmessung und ist von dieser Scheibe nicht betroffen.
- **Der amtliche Zweig kennt seinen Ausfall im Alarmpfad weiterhin nicht.**
  `check_official_alert_triggers` verschluckt einen Fehlschlag von
  `get_official_alerts_for_location` unverändert mit `logger.warning` — eigenständiger
  Nebenbefund, nicht Gegenstand dieser Scheibe.

## Risiken

- **R4 — Protokollieren darf den Alarm nie kosten.** Die neue Ableitung liegt innerhalb des
  bestehenden `try`-Blocks von `_radar_e1_fields()` — dasselbe Fail-soft-Muster wie die fünf
  bestehenden E-1-Größen (AC-9).
- **R5 — Bestandsdaten.** Alarmprotokoll-Einträge ohne `measurement_gaps` müssen lesbar bleiben
  und dürfen nicht umgeschrieben werden — Read-Modify-Write, Muster AC-14 aus #2050 S3b (AC-11).
- **R6 — AC-12/AC-13 der S4a-Spec waren bis zu dieser Scheibe vollständig ungetestet.** Kein
  bestehender Test griff auf `measurement_gaps` oder eine Lücken-/Messpunktzahl im Protokoll
  zu — alle roten Tests dieser Scheibe entstehen komplett neu, mit Positivkontrolle für jeden
  einzelnen (Muster #2050 S2b).
- **R1/R2 — entfallen.** Beide Risiken der S4a-Spec (frozen `RainZone` braucht Default,
  Signaturänderung an `derive_rain_zones` erfordert einen Referenzfeger über fremde
  Testdateien) betrafen ausschließlich Weg A/B. Mit dem gewählten Weg C bleibt
  `rain_extent.py` unangetastet — beide Risiken sind gegenstandslos, nicht nur gemindert.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** additive Erweiterung eines bereits etablierten, dokumentierten
  Protokollierungs-Musters (E-1-Größen, #2050 S6/S4a) um ein weiteres optionales Feld. Keine
  neue Entscheidungsfläche (Kanäle, Provider, Datenmodell-Grundform, Auth, Editor-Paradigma,
  Test-/Deploy-Strategie) berührt.

## Changelog

- 2026-08-23: Initial spec created (aus `docs/context/feat-2050-s4b-messluecken-protokoll.md`).
