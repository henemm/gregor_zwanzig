# Context: #2050 S4b — Messlücken im Alarmprotokoll

## Request Summary

Ein Radar-Alarm nennt seit #2051 S2a die räumliche Ausdehnung des Regenereignisses („km 2–6").
Fällt einer der bis zu sechs Messpunkte aus, verschwindet er in `derive_rain_zones` kommentarlos
— aus dem Ergebnis ist nachträglich **nicht** erkennbar, dass die Ausdehnung nur aus vier von
sechs Punkten stammt. Diese Scheibe baut die bereits geschriebenen, aber nie gebauten
**AC-12/AC-13 der S4a-Spec**: Zahl und Lage der Lücken gehören ins Alarmprotokoll
(Anforderung **E-1**, Nachvollziehbarkeit).

**Die Textaussage selbst ist ausdrücklich NICHT Teil dieser Scheibe** — siehe „Zuschnitt-Entscheid".

## Ausgangslage — am Code belegt

### Wo eine Lücke entsteht (drei Wege)

Alle in `trip_alert.py::check_radar_alerts`, in der Mehrpunkt-Abfrage (`:1698–1722`):

| Weg | Stelle | Erkennungsmerkmal |
|---|---|---|
| Abruf wirft | `except Exception` `:1713`, hängt `None` an `:1720` | `logger.warning`, sonst stumm |
| Abruf liefert, aber ohne verwertbare Frames | `_zonen_messwert()` `trip_alert.py:164-177` | `result.throttled` **oder** `result.data_unavailable` |
| Ergebnis ist `None` | ebenda | `result is None` |

`_zonen_messwert` gibt in allen drei Fällen `None` zurück — bewusst **kein** „trocken", weil ein
als trocken gewerteter Ausfall eine Nass-Zone trennen und damit eine ungemessene trockene
Strecke erfinden würde (#2051 S2a, E4).

### Wo die Information verworfen wird

`services/rain_extent.py::derive_rain_zones` (`:77-78`):

```python
for punkt, ergebnis in zip(points, results):
    if ergebnis is None:
        continue  # E4: echte Luecke — weder nass noch trocken
```

Das `continue` ist die einzige Stelle, an der die Lückeninformation existiert und verlorengeht.
`RainZone` (`@dataclass(frozen=True)`, `:26-43`, vier Felder `km_from`/`km_to`/`onset_minutes`/
`event_end_minutes`) trägt kein Kennzeichen.

### Wo sie NICHT mehr abgreifbar ist

`RadarAlertRequest` (`notification_service.py:176-267`) trägt `rain_zones` (bereits **verdichtet**)
und `km_measured` (nur das Flag „km stammt aus echter GPX-Wegstrecke") — **weder Messpunkt- noch
Lückenzahl**. Am Code bestätigt. Die Zahl muss also **vor** der Verdichtung aus `_punkte` /
`_zonen_ergebnisse` abgegriffen werden.

### Wie ein zugestellter Radar-Alarm heute protokolliert wird

`alert_log.append_entry()` (`alert_log.py:384-507`), gerufen in `check_radar_alerts` (`:2193`),
bekommt über `**_e1` die fünf E-1-Größen aus `_radar_e1_fields()` (`trip_alert.py:180-229`).
Deren `measurement_point` ist die **Segment-Spanne der Etappe**:

```python
"measurement_point": {
    "segment_id": ..., "km_from": active.start_point..., "km_to": active.end_point...,
}
```

— nicht die einzelnen Messpunkte der Mehrpunkt-Abfrage. Nichts im Protokoll spricht heute über
Messpunkte, Zonen oder Lücken. `_radar_e1_fields()` ist fail-soft (`{}` + Warnung bei Fehler,
`:223-229`); der Alarm läuft dann trotzdem.

### 🔴 `NameError`-Risiko: entwarnt

Die S4a-Spec markierte als „vor dem Bauen zu prüfen", ob ein Verzweigungspfad die Lesestelle
`:1722` ohne gesetztes `_zonen_ergebnisse` erreicht. **Er existiert nicht:** die Zuweisung
`:1698` ist unbedingt, die Lesestelle `:1722` folgt auf derselben Einrückungsebene; dazwischen
liegt nur die `for`-Schleife, deren `try/except` ausschließlich `append`t und nie neu bindet —
kein `continue`, kein `return`, kein `if`. Die drei `continue`-Stellen davor (`:1589` Gate,
`:1634-1652` Positionsbestimmung, `:1665-1686` erster Abruf) überspringen die Lesestelle
zwangsläufig mit. Unabhängig von zwei Seiten belegt (eigene Lesung + Explore-Agent).

## 🔴 Zuschnitt-Entscheid: warum die Zonenbildung UNVERÄNDERT bleibt

Der naheliegende Vorschlag — „eine Lücke schließt die laufende Zone ab, dann stimmt der Text
überall automatisch" — wurde geprüft und **verworfen**.

**Grund 1: Er tauscht eine Unwahrheit gegen eine andere.** Beide Darstellungen behaupten
Ungemessenes. Zusammenwachsen (`km 2–6` über die Lücke hinweg) behauptet durchgehende Nässe;
Trennen (`km 2–3, km 5–6`) behauptet Trockenheit dazwischen. Ehrlich ist nur eine
**Kennzeichnung** — und die ist Wortarbeit.

**Grund 2: Er kippt eine freigegebene, gut gebaute Zusicherung.** Zwei Tests aus #2051 S2a
schreiben das Nicht-Trennen ausdrücklich fest, beide mit Positivkontrolle:

| Test | Zusicherung |
|---|---|
| `tests/tdd/test_regen_ausdehnung_zonenbildung.py::test_ac11_datenloser_punkt_faellt_aus_der_zonenbildung_heraus` (`:148-175`) | Ergebnis **mit** Lücke ist identisch zu „Punkt komplett entfernt"; Positivkontrolle erzwingt 2 Zonen |
| `tests/tdd/test_regen_ausdehnung_textstellen.py::test_e4_punkt_ohne_frames_trennt_die_nasszone_nicht` (`:503`) | `throttled` **und** `data_unavailable` je einzeln: genau **eine** Zone; Positivkontrolle: ein *echt* trockener Punkt trennt sehr wohl |

Die Begründung steht im Test selbst: ein als trennend gewerteter Ausfall „erfindet eine trockene
Strecke, die niemand gemessen hat".

**Folge:** Diese Scheibe **erhält** die Lückeninformation und protokolliert sie (E-1). Die
Zonenbildung selbst bleibt byte-gleich, beide S2a-Tests bleiben grün. Die Textaussage beider
Verzerrungsrichtungen wandert nach **S4b-2**, zusammen mit der Gewitter-Beschriftung — beides in
`render.py`, beides nach dem #2051-S2b-Merge.

## Related Files

| Datei | Relevanz |
|---|---|
| `src/services/rain_extent.py` | `derive_rain_zones` verwirft die Lücke (`:77-78`); `RainZone` `frozen=True`, `:26-43` — neues Feld braucht **Default** (Zusage an die S2b-Session) |
| `src/services/trip_alert.py` | `check_radar_alerts`: Abgriff zwischen `:1698` und `:1722`; `_zonen_messwert` `:164-177`; `_radar_e1_fields` `:180-229`; `append_entry`-Aufruf `:2193` |
| `src/services/alert_log.py` | `append_entry()` `:384-507` — Zielort der neuen Protokollfelder |
| `docs/specs/modules/feat_2050_s4a_radar_teilausfall.md` | AC-12/AC-13 bereits **geschrieben**, nie gebaut — Wortlaut übernehmen |
| `docs/specs/modules/feat_2051_s2a_raeumliche_ausdehnung.md` | Known Limitation `:421ff` beschreibt beide Verzerrungsrichtungen; E4/AC-11 ist die Zusicherung, die nicht gekippt werden darf |
| `tests/tdd/test_regen_ausdehnung_zonenbildung.py` | Muss grün bleiben (AC-11) |
| `tests/tdd/test_regen_ausdehnung_textstellen.py` | Muss grün bleiben (E4) |

## Existing Patterns

- **Additives, optionales Feld mit Default** — das Muster der gesamten S4a-Scheibe
  (`convective_checked: bool = True`, `UndeliveredIncident.convective_check_failed: bool = False`).
  Altbestand bleibt lesbar, kein Schema-Bruch.
- **Ausfall bekommt einen eigenen, ehrlichen Grund statt still unterzugehen** —
  `REASON_DATA_UNAVAILABLE` / „Wetterdaten nicht verfügbar" (S4a), `get_official_alerts_with_status()`
  (#1348, PO-Entscheid 2026-07-23 „streng": eine ausgefallene abdeckende Quelle genügt).
- **Eine Ableitung für alle Protokollstellen eines Zweigs** — `_radar_e1_fields()` (#2050 S6),
  damit derselbe Vorfall nicht je nach Ausgang verschieden im Protokoll steht.
- **Fail-soft beim Protokollieren** — eine gescheiterte Protokollableitung darf den Alarm nie
  kosten (`_radar_e1_fields` `:223-229`).

## Dependencies

- **Upstream:** `points_along_remaining_route()` (`trip_segments.py:683-716`, Deckel
  `RADAR_ZONE_MAX_POINTS = 6`) erzeugt die Messpunkte; `radar_svc.get_nowcast()` liefert je Punkt.
- **Downstream:** `derive_rain_zones` hat **genau einen** produktiven Aufrufer
  (`trip_alert.py:1722`). `alert_log`-Einträge werden von `read_undelivered()` und der
  Briefing-Leseseite konsumiert.

## Parallele Sessions — abgestimmt, kollisionsfrei

| Session | Scheibe | Dateien | Abstimmung |
|---|---|---|---|
| `2050 S4c` | #2050 S4c (ein Ereignis, ein Alarm) | `alert_gate.py`, `trip_alert.py` (`:310–657`, Löschung `:1835–1861`, `check_radar_alerts` `~:1990–2060`), `undelivered_hint.py` | Kein Überlapp; beidseitig gegengeprüft. Mein Hunk endet `:1722`, ~113 Zeilen Abstand zur Löschung. **Meine Änderung liegt VOR ihrer** und verschiebt deren Zeilen, nicht umgekehrt. |
| `gregor-zwanzig-37` | #2051 S2b (Ausdehnung auf alle Kanäle) | `render.py` (`_render_subject_onset`, `_render_telegram_onset`, `_render_email_onset_multi`, `_render_sms_onset`), `validator_render_service.py` | Fasst `rain_extent.py` **nicht** an; konsumiert nur `OnsetEvent.rain_zones`. Ihre AC-Fixtures sind lückenfrei. Zusage von dort: brechende Wächter zieht sie selbst zurecht. |

**Reihenfolge:** S2b merged zuerst, S4b-2 setzt danach auf ihrem Stand auf. Diese Scheibe (S4b)
ist von der Reihenfolge unabhängig, weil sie `render.py` nicht berührt.

## Risks & Considerations

- **R1 — `RainZone` ist `frozen=True` und wird in Nachbarscheiben positional konstruiert.** Ein
  neues Feld **muss** einen Default tragen, sonst brechen fremde Testaufbauten (S2b legt davon
  „eine ganze Reihe" an). Ausdrückliche Zusage an die S2b-Session.
- **R2 — Signaturänderung an `derive_rain_zones` ⇒ Referenzfeger.** Ändert sich Rückgabetyp oder
  Signatur, `grep -rln "derive_rain_zones\|RainZone" tests/` — Signatur-Wächter liegen in
  **fremden** Testdateien. Beide bekannten Dateien sind oben gelistet.
- **R3 — Der erste Messpunkt ist ein Sonderfall.** `_zonen_ergebnisse[0]` stammt aus dem
  auslösenden Abruf (`_zonen_messwert(result)`). Ein `data_unavailable` würde dort seit S4a schon
  vorher aussteigen — `throttled` aber **nicht** zwingend. Zu prüfen: kann Index 0 eine Lücke sein,
  und was heißt AC-13 („alle Folgepunkte fallen aus") dann genau?
- **R4 — Protokollieren darf den Alarm nie kosten.** Neue Ableitung fail-soft halten, Muster
  `_radar_e1_fields`.
- **R5 — Bestandsdaten.** Alarmprotokoll-Einträge ohne die neuen Felder müssen lesbar bleiben und
  dürfen nicht umgeschrieben werden (Read-Modify-Write, AC-19-Muster aus S3b).
- **R6 — AC-12/AC-13 sind heute vollständig ungetestet.** Kein bestehender Test greift auf
  `alert_log` / `measurement_point` / eine Lücken- oder Messpunktzahl zu. Die roten Tests entstehen
  komplett neu — Positivkontrolle für jeden davon (Muster #2050 S2b).

## Analysis

### Type

**Feature** — eine geschriebene, nie gebaute Zusicherung (AC-12/AC-13 der S4a-Spec) wird gebaut.
Kein Bug: das heutige Verhalten ist spec-konform (#2051 S2a, E4), nur unvollständig
nachvollziehbar.

### 🔴 Technischer Ansatz: `derive_rain_zones` bleibt UNANGETASTET

Drei Wege wurden gegeneinander bewertet; **Weg C** gewinnt mit Abstand:

| Weg | Idee | Urteil |
|---|---|---|
| A | additives Feld an `RainZone` | ❌ **semantisch unmöglich** — eine Lücke liegt *zwischen* Zonen. Eine Lücke bei km 4 zwischen den Zonen km 0–2 und km 6–8 hat keine Zone, an die sie sich hängen ließe |
| B | `derive_rain_zones` gibt Lücken zusätzlich zurück | ❌ Rückgabetyp-Änderung ⇒ Referenzfeger über fremde Testdateien; **und Doppelarbeit**, weil der Aufrufer die Rohinformation längst hat |
| **C** | **Lücken im Aufrufer ableiten, `rain_extent.py` gar nicht anfassen** | ✅ **Empfohlen** |

**Begründung für C:** In `trip_alert.py::check_radar_alerts` liegt zwischen der Zuweisung
(`_zonen_ergebnisse: list = [_zonen_messwert(result)]`) und der Verdichtung
(`derive_rain_zones(_punkte, _zonen_ergebnisse)`) bereits **index-genauer** Zugriff auf
`_punkte[i].distance_from_start_km` **und** `_zonen_ergebnisse[i] is None` — also exakt die
Rohinformation, die AC-12 („dass und an welcher Stelle") verlangt. `derive_rain_zones` bekäme
nur den verdichteten Rest.

**Folgen:** `rain_extent.py` wird nicht angefasst → R1 (frozen dataclass, Default-Pflicht) und
R2 (Referenzfeger) entfallen **vollständig**. Die zwei S2a-Wächter können gar nicht rot werden.
Die Zusage an die #2051-S2b-Session ist damit übererfüllt.

### Datenform des Protokollfelds

Neues optionales Feld `measurement_gaps`, abgeleitet in `_radar_e1_fields()` (Suchbegriff
`def _radar_e1_fields(`, ~`:180`) — dem bestehenden Muster „**eine** Ableitung für alle
Protokollstellen eines Zweigs" (#2050 S6) folgend. Die Funktion wird genau **einmal** gerufen
(Suchbegriff `_e1 = _radar_e1_fields(`, ~`:1899`) und ihr Ergebnis per `**_e1` an alle
Protokollstellen des Radarzweigs gespreadet — eine Änderung wirkt überall konsistent.

```python
"measurement_gaps": {
    "points_total": <Zahl der Messpunkte>,
    "points_measured": <Zahl mit verwertbarem Ergebnis>,
    "gap_km": [<km-Lage jedes ausgefallenen Punkts>],
}
```

**🔴 Verfeinerung gegenüber dem Agentenvorschlag:** Das Feld wird **immer** gesetzt, sobald die
Mehrpunkt-Abfrage lief — auch bei leerer `gap_km`-Liste. Der Vorschlag „Feld weglassen, wenn
keine Lücke" wäre schlanker, aber ein *fehlendes* Feld hätte dann **drei** Bedeutungen: „alles
gemessen", „Alteintrag von vor dem Deploy" und „Ableitung fail-soft gescheitert". Genau diese
Ununterscheidbarkeit ist der Mangel, den die Scheibe beheben soll — sie darf nicht auf einer
Ebene höher neu entstehen.

- **AC-12 erfüllt:** `gap_km` nennt Zahl *und* Lage.
- **AC-13 erfüllt:** der Extremfall (`points_total=6, points_measured=1`) ist strukturell vom
  echten Befund „Regen nur auf einem Kilometer" (`points_total == points_measured`)
  unterscheidbar — an Zahlen, nicht am Text.

### 🔴 Risiko R3 aufgelöst: Index 0 kann bei einem ausgelösten Alarm nie eine Lücke sein

Unabhängig von zwei Seiten belegt. Drei Wege, wie der erste Punkt ausfällt — **keiner** erreicht
eine Protokollzeile mit Ausdehnung:

| Fall am ersten Punkt | Warum kein Alarm |
|---|---|
| Abruf wirft | `except` `continue`t, bevor `_zonen_ergebnisse` überhaupt existiert |
| `data_unavailable=True` | Zonenbildung läuft zwar, aber `if result.data_unavailable:` `continue`t mit `REASON_DATA_UNAVAILABLE` (S4a) |
| `throttled=True` | impliziert `not frames` ⇒ `onset_minutes=None`; `radar_alert_due()` verlangt `onset is not None` **oder** `already_running` — beides falsch ⇒ stiller `continue` |

**Folge:** AC-13 („alle Folgepunkte fallen aus") ist wie geschrieben korrekt — gemeint sind
zwangsläufig Index 1..N-1. **Keine Spec-Korrektur nötig.** Aber diese Tatsache braucht eine
eigene Positivkontrolle: sonst prüft niemand, dass ein Ausfall an Index 0 gar nicht bis zur
Protokollzeile kommt.

### Affected Files

| Datei | Änderung | Beschreibung |
|---|---|---|
| `src/services/trip_alert.py` | MODIFY | `_radar_e1_fields()` um die Lücken-Ableitung erweitern (fail-soft, **innerhalb** des bestehenden `try`), Aufrufstelle um die zwei Argumente ergänzen |
| `src/services/alert_log.py` | MODIFY | `append_entry()` (`:384`) **und** `append_suppressed_entry()` (`:525`) je um `measurement_gaps: Optional[dict] = None` — **zwei** Stellen mit festen Signaturen, keine `**kwargs` |
| `tests/tdd/test_radar_messluecken_protokoll.py` | CREATE | AC-12/AC-13 + Positivkontrollen |

**`src/services/rain_extent.py`: NICHT betroffen.** Ausdrücklich.

### Scope Assessment

- Produktivdateien: **2** · Produktivcode ~30–40 LoC · Tests ~80–140 LoC
- LoC-Limit 250: **eingehalten**
- Risiko: **LOW** — additiv, fail-soft, keine Verhaltensänderung an einer bestehenden Zusicherung

### Offene Punkte — beide geklärt

- [x] **Test-Werkzeug: bereits vorhanden, keine Helfer-Erweiterung nötig.** `_ZonenRadar`
      (`tests/tdd/test_regen_ausdehnung_textstellen.py:383`) ist eine echte
      `RadarNowcastService`-Unterklasse am DI-Seam von `TripAlertService` — **kein Mock**, sie
      liefert die Produktiv-Dataclass mit echten Feldern und steuert nur, *welches* Ergebnis ein
      Punkt bekommt. Steuerbar per Index über `trocken_index`, `trocken_felder`
      (z. B. `{"data_unavailable": True}`), `ausnahme_index`, `weitere_trockene` — deckt alle drei
      Lückenwege ab. Muster wiederverwenden statt neu bauen.
- [x] **Rundung `gap_km`: eine Nachkommastelle**, konsistent mit der gemessenen km-Spanne
      (`segments.format_alert_location`) und dem Zonen-Rendering aus #2051 S2a. Entschieden, keine
      PO-Frage.

## Nebenbefunde (nicht in dieser Scheibe)

- **Amtlicher Zweig:** `check_official_alert_triggers` ruft `get_official_alerts_for_location` —
  den Alt-Wrapper **ohne** Ausfall-Status — und verschluckt den Fehlschlag mit `logger.warning`.
  Derselbe B-4-Verstoß, andere Quelle. Aus dem S4a-Kontext übernommen, weiterhin offen.
- **`convective_checked` erreicht den Renderer nicht.** Die Kette bricht beim Bau von
  `RadarAlertRequest` (`trip_alert.py:2060ff`): `is_convective=result.is_convective` wird
  mitgenommen, `result.convective_checked` nicht — das DTO hat kein solches Feld. Die fünf
  Beschriftungsstellen (`render.py:480` `_render_subject_onset`, `:653` `_render_email_onset_multi`,
  `:727` `_render_email_onset`, `:805` `_render_telegram_onset`, `:946` `_render_sms_onset`) lesen
  daher nur `is_convective`. **Vorarbeit für S4b-2, hier bewusst liegengelassen.**
- **Vorbild für S4b-2 (Kennzeichnung von Unsicherheit):** #2051 S3 hat das Paar bereits gebaut —
  Langform `_onset_sharpness_suffix()` (`render.py:599`, no-op wenn leer) und Kurzform
  `_sms_onset_sharpness_marker()` (`:907`), die ein `"?"` ans **fertige** Zeit-Token hängt.
  Bewusst `?` statt `~`, weil `~` GSM-7-Extension ist und vom Transport zu `-` gefaltet würde.
  Belegtes Kurzform-Inventar, mit dem ein neues Zeichen nicht kollidieren darf: `R`, `TH`, `now`,
  `?`, `Rest{mm}`, `!{code}`, sowie app-weit reserviert `X` (UNAVAILABLE_SYMBOL,
  `tokens/builder.py:84-86`).
- **Platzzusage der #2051-S2b-Session für S4b-2** (von dort mitgeteilt): ihr neuer Kurzform-Helfer
  heißt `_sms_onset_extent_marker()` und liegt **hinter** `_sms_onset_sharpness_marker()`. Die
  Tokenreihenfolge wird `{Zeitgruppe}{Ende}{Güte-Marker ?} {Zonen-Kürzel km8-12}`. Empfehlung von
  dort: eine Lücken-Kennzeichnung gehört **hinter** das Zonen-Kürzel, weil die Lücke eine Aussage
  über die *Strecke* ist, nicht über die Zeit.
- **⚠️ Kein Prioritäts-Kürzen im Alarm-SMS-Pfad.** Der harte Schnitt `body[:limit]` ist eine
  Reißleine, die laut Bestandstest `tests/tdd/test_onset_ende_sms_budget.py:107-137` **nie**
  greifen darf — das 140-Zeichen-Budget wird durch Konstruktion gehalten. S2b führt mit ihrer AC-8
  die erste explizite Abwahl ein (Kürzel entfällt ganz statt abgeschnitten). Ein weiteres Zeichen
  in S4b-2 braucht dieselbe Disziplin, sonst kippt der Bestandstest.
