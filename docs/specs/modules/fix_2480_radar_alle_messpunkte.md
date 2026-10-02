---
entity_id: fix_2480_radar_alle_messpunkte
type: bugfix
created: 2026-10-02
updated: 2026-10-02
status: draft
workflow: fix-2480-radar-alle-messpunkte
version: "1.0"
tags: [alarm, radar, nowcast, messpunkt, folgepunkte, trip]
---

# Trip-Radar-Alarm löst an allen Messpunkten aus (Issue #2480)

## Approval

- [ ] Approved — Product Owner (offen; Freigabe der ACs auf Deutsch durch Henning steht aus)

Produktentscheide bereits getroffen (2026-10-02, Henning): **(a) JA** — Alarm auch, wenn der
Regen innerhalb der nächsten Stunde erst 2–10 km weiter vorn auf der Strecke beginnt.
**(b) JA** — Alarm auch, wenn der eigene Messpunkt nicht abrufbar ist, weiter vorn aber Regen
belegt ist.

## Purpose

Der Radar-Alarm eines Trips misst heute an bis zu sechs Punkten entlang der Reststrecke (Abstand
2 km, #2051 S2a). Ausgelöst wird er aber **nur vom ersten Punkt** (Position zur Fenstermitte,
#2017). Die übrigen Punkte liefern nur die Nass-Zonen im Text. Regen, der ausschließlich über dem
zweiten bis sechsten Punkt liegt, also 2–10 km weiter auf der Strecke, löst deshalb keinen Alarm
aus — obwohl er auf dem Weg des Wanderers liegt und im Text sogar erscheinen würde, wenn der Alarm
aus anderem Grund käme. Das ist eine nutzersichtbare Alarm-Lücke (Herkunft: #2261 Teil A, Sz.8,
Anforderung B-3 aus #2050).

Diese Spec dehnt die Auslöseregel auf **alle Messpunkte** aus. Aus allen Punkten, an denen die
bestehende Regel „Regenbeginn in höchstens 55 Minuten oder Regen läuft schon"
(`radar_alert_due`) erfüllt ist, wird **ein einziger maßgeblicher Punkt** gewählt. Alle Werte des
Alarms (Menge, Dringlichkeit, Gewitter, Ende, Quelle, Mitschnitt) stammen aus genau diesem einen
Abruf — keine gemischten Werte, die so kein Abruf geliefert hat.

Zusätzlich wird die Fehlerpolitik angepasst (Entscheid b): Fällt der erste Messpunkt aus, ist ein
belegt nasser Folgepunkt trotzdem ein Alarm. Das entspricht Anforderung B-4 („Teilausfall gilt nie
als Entwarnung") konsequenter als der bisherige Abbruch.

## Source

- **File:** `src/services/trip_alert.py::TripAlertService.check_radar_alerts` (Radar-Block
  ca. `:1842-2481`)
  - `:1845` `_pos = _punkte[0]` — erster Punkt (Messpunkt aus #2017)
  - `:1874` Abruf des ersten Punkts (`result`); `:1878-1892` Ausnahme-Fang mit `continue` **vor**
    der Zonenschleife (Folgepunkte werden dann heute nie abgerufen)
  - `:1904-1927` `_zonen_ergebnisse`: positionsgleich die vollen `NowcastResult` aller Punkte
    (`None` bei throttled / data_unavailable / Ausnahme) — Grundlage der neuen Auswahl
  - `:2060-2072` Ausstieg `result.data_unavailable` mit `REASON_DATA_UNAVAILABLE`
  - `:2074` `if not radar_alert_due(result, RADAR_ONSET_THRESHOLD_MIN)` — die heutige Auslöseregel
    nur am ersten Punkt
  - `:2082` `_onset_dt`, danach Briefing-Vergleich, Label/Ende/Reichweite, `RadarAlertRequest`,
    Identitäts-Gate, Versand, Mitschnitt-Capture-ID (`:2414-2416`, `_nowcast_source_key(lat, lon)`
    des ersten Punkts), `record_nowcast_sent` / `record_event_identity`
- **File:** `src/services/trip_alert.py::radar_alert_due` (`:182`), `::_zonen_messwert` (`:196`),
  `::_radar_e1_fields` (`:245`) — Letztere additiv (km des auslösenden Punkts)
- **File (neu oder Erweiterung):** kleiner reiner Baustein „maßgeblichen Eintrag wählen", abgelegt
  neben `radar_alert_due` (`src/services/trip_alert.py`) oder in `src/services/radar_service.py`
  (Entscheid der Implementierung; Pflicht: reine Funktion ohne Seiteneffekte, einzeln testbar)
- **Nur lesend / nicht geändert:** `src/services/compare_radar_alert.py::_detect_triggered_locations`
  (`:449-509`), `src/services/trip_segments.py::points_along_remaining_route` (`:683`),
  `src/services/rain_extent.py::derive_rain_zones`, Renderer
  (`src/output/renderers/alert/render.py`, `segments.py`)
- **Schicht:** Python-Core. Kein Go, kein Frontend, kein neuer Endpoint.

## Estimated Scope

- **Files:** ca. 3 produktiv (`trip_alert.py`, ggf. `radar_service.py`, Auswahl-Baustein) +
  2 Tests (1 angepasst, 1 neu) + Spec-Vermerke in 4 bestehenden Specs
- **LoC:** ca. +80/−20 produktiv (unter dem Limit von 250); Tests und Doku zählen nicht
- **Risk:** MEDIUM — zentrale Alarmentscheidung; „mehr Alarme" ist beabsichtigt. Die Reihenfolge
  der Prüfungen ist heikel: Sperrzeit-Override und Menge/Dringlichkeit werden **vor** dem
  Auslöse-Guard gelesen, die Auswahl muss deshalb direkt nach der Zonenschleife stehen.
- **Effort:** medium

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `RadarNowcastService.get_nowcast` (`src/services/radar_service.py`) | method | Abruf je Punkt; Cache und Abruf-Budget (#1329) bleiben unverändert wirksam |
| `radar_alert_due` / `RADAR_ONSET_THRESHOLD_MIN = 55` | function / const | Auslöseregel je Punkt (unverändert, gilt jetzt je Punkt) |
| `_zonen_ergebnisse` / `derive_rain_zones` | data / function | liefern die vollen Ergebnisse aller Punkte bzw. die Nass-Zonen für den Textsuffix |
| `alert_state` (Sperrzeit, Vergleichsbasis #2065), `alert_daily_limit`, Identitäts-Gate (#1467) | services | laufen unverändert nach der Auswahl |
| `alert_log` (`REASON_DATA_UNAVAILABLE`, E-1-Felder) | service | Protokollierung des Ausfalls und des auslösenden Punkts |
| `alert_input_capture` / `_nowcast_source_key` | service | Mitschnitt-ID muss zur Koordinate des maßgeblichen Punkts gehören |
| `compare_radar_alert._detect_triggered_locations` | function | nur Vorbild (jeder Ort löst einzeln aus, höchste Dringlichkeit); wird nicht geändert |
| `tests/helpers/alarm_pruefstrecke.py` (`AlarmPruefstrecke`), `tests/helpers/strecke_fixtures.py` (`recording_radar_service_type`, `nass()`, `trocken()`) | test helper | Szenario-Harness, Fake-Radar je Punktindex |

## Implementation Details

### Auswahl des maßgeblichen Punkts (kleiner reiner Baustein)

Eingabe: die positionsgleiche Liste der Ergebnisse aller Punkte (Index 0 = erster Messpunkt;
`None` = nicht verwertbar: throttled, data_unavailable, Ausnahme). Ausgabe: Index und Ergebnis des
maßgeblichen Punkts oder „keiner".

1. Kandidaten sind alle verwertbaren Punkte, für die `radar_alert_due(ergebnis, 55)` gilt.
2. Unter den Kandidaten gewinnt der **früheste Regenbeginn** (`already_running` zählt als 0 Minuten).
3. Bei Gleichstand gewinnt die **höhere Dringlichkeit** (gleiche Rangfolge wie im
   Ortsvergleich, `highest_urgency`).
4. Bei weiterem Gleichstand gewinnt der **kleinere Index** (der Punkt, der dem Wanderer am
   nächsten liegt).
5. Ist Punkt 0 selbst auslösend und nicht schlechter als jeder andere Kandidat nach 2.–4., ist er
   maßgeblich — das Verhalten und der Text sind dann **bitgleich** wie vor dieser Änderung.

Ab der Auswahl lesen alle nachgelagerten Stellen den maßgeblichen Punkt statt des ersten
(`result` → `_massgeblich`): Menge (`_menge_mm`), Dringlichkeit, Sperrzeit-Override, Auslöse-Guard,
`_onset_dt`, Briefing-Vergleich, Label/Ende/Reichweite, `RadarAlertRequest`, Identitäts-Gate,
Versand, `record_nowcast_sent`, `record_event_identity`. Die Mitschnitt-Capture-ID wird aus der
Koordinate des maßgeblichen Punkts gebildet, nicht aus der des ersten.

**Warum nicht je Größe aggregieren (max/min)?** Eine Mischung wie „Beginn von Punkt 2, Menge von
Punkt 4, Dringlichkeit von Punkt 3" wäre ein Wert, den kein einziger Abruf geliefert hat. Das
bräche die Vergleichsbasis aus #2065 und den Mitschnitt (der Mitschnitt zeigt auf genau einen
Abruf).

### Geteilter Baustein statt Compare-Umbau (ADR-0021)

Der Ortsvergleich löst bereits an jedem Ort einzeln aus
(`_detect_triggered_locations`, `:449-509`) und bündelt zu einer Nachricht mit der höchsten
Dringlichkeit. Er hat diese Lücke nicht. Der Trip übernimmt dieselbe Grundidee („jeder Punkt wird
einzeln gegen `radar_alert_due` geprüft, Dringlichkeit = höchste der auslösenden"), aber mit einer
anderen Ausgabeform: Der Trip meldet **einen** maßgeblichen Punkt (eine Position auf der Strecke,
ein Beginn), der Vergleich bündelt **mehrere Orte** in einer Nachricht. Ein gemeinsamer Umbau
würde den Compare-Pfad (eigene Bündelung, eigene Vergleichsbasis) ohne Nutzen berühren und das
Risiko in zwei Alarmpfade streuen. Deshalb: Der Auswahl-Baustein ist ein kleiner, reiner Baustein
mit klarer Schnittstelle (Liste von Ergebnissen → maßgeblicher Eintrag), der Trip nutzt ihn jetzt,
der Compare-Pfad kann ihn später übernehmen — **ohne** dass dieser Fix `compare_radar_alert.py`
anfasst. Die Schwelle (55 Minuten) und die Gate-Reihenfolge bleiben in beiden Pfaden identisch.

### Fehlerpolitik (Entscheid b)

| Zustand Punkt 0 | Folgepunkte | Ergebnis |
|---|---|---|
| auslösend | beliebig | wie bisher (Punkt 0 maßgeblich, sofern kein früherer Kandidat) |
| trocken / Beginn > 55 Min | mind. einer auslösend | **Alarm** (neu) |
| `data_unavailable` | mind. einer auslösend | **Alarm** (neu, löst #2050 S4b AC-8 ab) |
| Ausnahme beim Abruf | mind. einer auslösend | **Alarm** (neu); die Folgepunkte werden dafür trotzdem abgerufen (heute `continue` davor) |
| `data_unavailable` / Ausnahme | alle trocken oder ausgefallen | **kein Alarm**, weiter `REASON_DATA_UNAVAILABLE` protokolliert |
| `throttled` | beliebig | **unverändert**: kein Zusatzabruf, kein Alarm (Budget-Druck, #1329) |

Hinweis zum Abrufbudget: Die Aussage „Abrufe unverändert" gilt nur, solange Punkt 0 nicht wirft.
Bei einer Ausnahme an Punkt 0 entstehen künftig echte Zusatzabrufe (bis zu `RADAR_ZONE_MAX_POINTS
− 1`), weiterhin mit `priority="polling"` und innerhalb von Cache und Budget #1329.

### Text und Ort (Entscheid a)

- **Uhrzeit** im Text = Regenbeginn **dort, gerechnet ab jetzt** (nicht die Ankunft des Wanderers —
  es gibt keine Ankunftszeit je Punkt; siehe Out of Scope). Der Text trägt dieselbe „ab HH:MM"-Form
  wie bisher.
- **Ort** = der bestehende Nass-Zonen-Suffix (#2051 S2b: Mail/Telegram „km 2–4", SMS „km8–12"),
  sofern die Etappe vermessen ist. Kein neuer Textbaustein, kein Render-Umbau.
- Zu prüfen (nicht umzubauen): Der Onset-Kopf nennt den Segment-km der Etappe. Er darf bei
  Auslösung durch einen Folgepunkt nicht als Aussage „am Standort regnet es dann" gelesen werden;
  im Zweifel trägt der Zonen-Suffix die Ortsangabe. Findet der Adversary eine tatsächlich falsche
  Aussage, ist das ein Befund, der im selben Ticket behoben wird.
- Alle vier Kanäle (Mail, Telegram, SMS, Premium-SMS) bekommen den Alarm über denselben Pfad
  (`RadarAlertRequest`, geteilte Kanal-Auflösung). Es gibt keinen kanalspezifischen Zweig.

### Alarmprotokoll (E-1)

`_radar_e1_fields` bekommt additiv ein Feld für den km des auslösenden Punkts (entlang der Strecke,
`distance_from_start_km`). Bestehende Felder (`measurement_point` = Segment-km, Vorwarnzeit,
Ereigniszeit, Quelle) bleiben unverändert; Leser ohne das neue Feld funktionieren weiter.

### Bewusst NICHT gebaut: Stickiness

Es wird **nicht** gespeichert, welcher Punkt zuletzt gemeldet wurde, um ihn bei der nächsten Wahl
zu bevorzugen (das wäre eine Persistenzänderung in `alert_state`). Stattdessen gilt ein
Pflicht-Test (AC-9): Wechselt der maßgebliche Punkt zwischen zwei Läufen ohne Verschärfung, kommt
kein zweiter Alarm. Fällt dieser Test rot, ist das ein **Spec-Befund**, und die Stickiness wird in
dieser Spec nachgezogen, nicht stillschweigend eingebaut.

## Abgelöste Festlegungen

Die folgenden früheren Festlegungen werden durch diese Spec bewusst abgelöst. Der Erledigt-Vermerk
ist **Teil der Umsetzung** (Doku-Abnahme, `# doc-compliance-test`):

| Stelle | Bisherige Festlegung | Ablösung |
|---|---|---|
| `docs/specs/modules/feat_2050_s4a_radar_teilausfall.md` Zeilen 63–68 (zwei Fehlerpolitiken: Ausfall am ersten Punkt bricht den Trip ab) | Ausfall des auslösenden ersten Punkts ⇒ Abbruch, `sent == 0` | Abbruch nur noch, wenn auch alle Folgepunkte nicht auslösen; Vermerk „abgelöst durch #2480 (PO-Entscheid b, 2026-10-02)" |
| `docs/specs/modules/feat_2050_s4b_messluecken_protokoll.md` AC-8 (Zeile 255, „Ausfall am ersten, auslösenden Messpunkt ⇒ Lauf steigt vorher aus") | Ausfall an Punkt 0 ⇒ keine Protokollzeile, kein Versand | Vermerk „abgelöst durch #2480 (PO-Entscheid b, 2026-10-02)": Ausstieg nur noch, wenn kein Folgepunkt auslöst |
| Wächter `tests/tdd/test_radar_messluecken_protokoll.py:595-625` (`test_ausfall_am_ersten_punkt_erzeugt_keine_ausdehnungszeile`) | erwartet `sent == 0` bei Ausfall an Punkt 0 mit nassen Folgepunkten | wird **bewusst angepasst** (siehe Tests), nicht gelöscht |
| `docs/specs/modules/feat_2051_s2a_raeumliche_ausdehnung.md` Zeile 268 („keine Änderung an der Auslöseregel") | Auslöseregel nur am ersten Punkt, ohne dokumentierte Begründung | Vermerk: Zeile gilt für S2a; Auslöseregel ab #2480 je Punkt |
| `docs/specs/modules/fix_2017_nowcast_messpunkt.md` Known Limitation 9 („Restrisiko: Auslöseregel nur am ersten Punkt") | als Restrisiko festgehalten, nicht gebaut | Vermerk „erledigt durch #2480"; KL 8 (Fenstermitte statt Onset) bleibt gültig |
| `docs/specs/modules/feat_2261_sz8_messpunkt_position.md` AC-5 (hält #2480 als Restrisiko fest) | Verweis auf offenes Issue #2480 | Vermerk „erledigt durch #2480" am AC; der AC selbst bleibt als Doku-Nachweis bestehen |

Ein neues ADR ist **nicht** nötig: ADR-0021/0046/0052/0056 legen die Punkt-0-Regel nicht fest
(Grep-Befund der Analyse); ADR-0009 (Mail nennt Etappe, Segment-km, Onset-Zeit) bleibt unberührt.

## Acceptance Criteria

- **AC-1 (Regen weiter vorn löst Alarm aus):** Given ein Trip, dessen erster Messpunkt trocken
  ist, während über einem Folgepunkt (z. B. Punkt 2, ca. km +4 auf der Strecke) Regen mit Beginn in
  höchstens 55 Minuten belegt ist, When der Radar-Prüflauf läuft, Then wird ein Radar-Alarm
  versendet; die Uhrzeit im Text ist der Regenbeginn an diesem Folgepunkt (gerechnet ab jetzt) und
  der Ort steht im bestehenden Nass-Zonen-Suffix (z. B. „km 2–4").
  - Test: `test_folgepunkt_nass_loest_alarm_aus`; zusätzlich Gegenprobe gleicher Aufbau mit
    Beginn 60 Minuten ⇒ siehe AC-4.

- **AC-2 (Regressionsschutz Punkt 0):** Given ein Trip, dessen erster Messpunkt selbst die
  Auslöseregel erfüllt (und kein Folgepunkt früher beginnt), When der Prüflauf läuft, Then sind
  Versand, Textinhalt, Dringlichkeit, Vergleichsbasis und Protokolleinträge bitgleich zum Stand vor
  dieser Änderung.
  - Test: `test_punkt0_ausloesend_bleibt_bitgleich` (Vergleich gegen aufgezeichnete Referenz des
    heutigen Stands; die bestehenden Radar-Tests in `test_alarm_szenario_*.py` und
    `test_regen_ausdehnung_textstellen.py` bleiben unverändert grün).

- **AC-3 (ein maßgeblicher Punkt, keine Mischwerte):** Given mehrere Punkte erfüllen die
  Auslöseregel, When die Auswahl getroffen wird, Then ist genau ein Punkt maßgeblich: der mit dem
  frühesten Regenbeginn (laufender Regen = 0 Minuten), bei Gleichstand der mit der höheren
  Dringlichkeit, dann der mit dem kleineren Index; und Menge, Dringlichkeit, Gewitter-Kennzeichen,
  Regenende, Quelle, Label, Vergleichsbasis (#2065) sowie die Mitschnitt-Capture-ID (mit der
  Koordinate dieses Punkts) stammen alle aus diesem einen Abruf.
  - Test: `test_massgeblicher_punkt_fruehester_beginn_dann_dringlichkeit_dann_index` (reiner
    Baustein, drei Gleichstandsstufen) und `test_alle_groessen_stammen_aus_einem_abruf` (Prüfstrecke,
    Folgepunkte mit bewusst unterschiedlichen Mengen/Dringlichkeiten; erwartet die Werte des
    gewählten Punkts, nicht deren Max/Min; Capture-ID hat die Koordinate des gewählten Punkts).

- **AC-4 (nichts in Reichweite, kein Alarm):** Given alle Messpunkte sind trocken, oder der
  früheste Regenbeginn aller Punkte liegt später als 55 Minuten, When der Prüflauf läuft, Then wird
  kein Alarm versendet.
  - Test: `test_alle_trocken_kein_alarm`, `test_beginn_ueber_55_min_an_allen_punkten_kein_alarm`.

- **AC-5 (eigener Messpunkt ausgefallen, vorn Regen — Entscheid b):** Given der erste Messpunkt
  liefert keine Daten (`data_unavailable`) oder der Abruf wirft eine Ausnahme, und ein Folgepunkt
  belegt Regen mit Beginn in höchstens 55 Minuten, When der Prüflauf läuft, Then wird ein Alarm
  versendet; bei einer Ausnahme am ersten Punkt werden die Folgepunkte dafür trotzdem abgerufen.
  - Test: `test_punkt0_ausfall_folgepunkt_nass_loest_alarm_aus`, parametrisiert über Ausnahme und
    `data_unavailable`; ersetzt den Wächter von #2050 S4b AC-8
    (`test_radar_messluecken_protokoll.py:595-625`) in genau diesem Teil. Die Positivkontrolle
    „derselbe Ausfall an Index 1 erzeugt `measurement_gaps`" bleibt erhalten.

- **AC-6 (Ausfall ohne Regen bleibt sichtbar):** Given der erste Messpunkt ist ausgefallen
  (Ausnahme oder `data_unavailable`) und alle Folgepunkte sind trocken oder ebenfalls ausgefallen,
  When der Prüflauf läuft, Then wird kein Alarm versendet und der Lauf wird weiterhin mit dem
  Grund `REASON_DATA_UNAVAILABLE` ins Alarmprotokoll geschrieben (nie als „ruhig" gewertet).
  - Test: `test_punkt0_ausfall_folgepunkte_trocken_kein_alarm_aber_protokoll`, parametrisiert wie AC-5.

- **AC-7 (Budget-Druck unverändert):** Given der erste Messpunkt ist `throttled`, When der
  Prüflauf läuft, Then werden keine zusätzlichen Abrufe für Folgepunkte ausgelöst und kein Alarm
  versendet — wie vor dieser Änderung.
  - Test: `test_punkt0_throttled_kein_zusatzabruf_kein_alarm` (zählt die Abrufe über
    `recording_radar_service_type`).

- **AC-8 (Sperren bleiben wirksam):** Given ein Alarm wurde bereits gesendet, When im nächsten
  Lauf wieder ein Folgepunkt auslöst, Then greifen Sperrzeit, Tageslimit und Identitäts-Gate
  (#1467) unverändert: Es wird kein zweiter Alarm für dasselbe Ereignis versendet; eine echte
  Verschärfung (#2065) durchbricht die Sperrzeit weiterhin, und zwar mit der Menge des
  maßgeblichen Punkts.
  - Test: `test_sperrzeit_tageslimit_identitaet_wirken_mit_folgepunkt`,
    `test_verschaerfung_am_folgepunkt_durchbricht_sperrzeit`.

- **AC-9 (Wechsel des Punkts ohne Verschärfung, Pflicht-Test):** Given der erste Lauf hat wegen
  Punkt 2 alarmiert, When im zweiten Lauf (innerhalb der Sperrzeit, gleiches Ereignis) wegen
  Messwert-Schwankung Punkt 3 statt Punkt 2 maßgeblich wird, ohne dass sich Menge oder
  Dringlichkeit verschärfen, Then wird kein zweiter Alarm versendet.
  - Test: `test_punktwechsel_ohne_verschaerfung_kein_zweiter_alarm`. **Fällt er rot, ist das ein
    Spec-Befund** (Stickiness wird dann in dieser Spec nachgezogen), kein Grund, den Test
    aufzuweichen.

- **AC-10 (Alarmprotokoll nennt den auslösenden Punkt):** Given ein Alarm wurde durch einen
  Folgepunkt ausgelöst, When der Alarmprotokolleintrag geschrieben wird, Then enthält er
  zusätzlich den km dieses Punkts entlang der Strecke; alle bisherigen Felder sind unverändert, und
  ein Eintrag ohne das Feld (Altbestand, Alarm durch Punkt 0 ohne Angabe) bleibt gültig und lesbar.
  - Test: `test_e1_protokoll_nennt_km_des_ausloesenden_punkts`,
    `test_e1_felder_rueckwaertskompatibel` (Altzeile ohne Feld wird gelesen).

- **AC-11 (alle vier Kanäle, derselbe Pfad):** Given ein Alarm wird durch einen Folgepunkt
  ausgelöst und der Nutzer hat Mail, Telegram, SMS und Premium-SMS konfiguriert, When der Alarm
  versendet wird, Then erhalten alle vier Kanäle den Alarm mit derselben Auslöseaussage (Beginn „ab
  HH:MM" des maßgeblichen Punkts, Zonen-Ort), und keiner der Texte liest sich als Aussage über den
  Standort des Wanderers zum Regenbeginn.
  - Test: `test_folgepunkt_alarm_erreicht_alle_vier_kanaele` (Prüfstrecke, Kanalinhalte aller vier
    Kanäle; Inhaltsprüfung auf Beginn-Uhrzeit und Zonen-Suffix, keine reine String-Presence ohne
    Plausibilitätsbezug).

- **AC-12 (Ortsvergleich unberührt):** Given der Ortsvergleich-Radar-Alarm, When diese Änderung
  geliefert ist, Then ist `compare_radar_alert.py` unverändert und seine Tests laufen unverändert
  grün.
  - Test: bestehende Compare-Radar-Tests; `git diff` zeigt keine Änderung an
    `src/services/compare_radar_alert.py`.

- **AC-13 (Erledigt-Vermerke):** Given die in „Abgelöste Festlegungen" genannten Stellen, When
  diese Spec umgesetzt ist, Then tragen die fünf Specs (S4a, S4b, S2a Zeile 268, fix_2017 KL 9,
  Sz.8 AC-5) einen Erledigt-/Ablösungsvermerk mit Verweis auf #2480, und der Wächter in
  `test_radar_messluecken_protokoll.py` ist angepasst statt gelöscht.
  - Test: Doku-Abnahme (`# doc-compliance-test`-Ausnahme: kein Verhaltenstest).

## Geplante Tests

Datei nach Verhalten benannt: `tests/tdd/test_radar_alarm_folgepunkte.py` (neu). Aufbau über
`AlarmPruefstrecke(...).lauf(at=, zweig="radar", trip=, radar_service=)` mit
`recording_radar_service_type(calls, script=idx->result)`, `nass()` und `trocken()` aus
`tests/helpers/strecke_fixtures.py`: ein echter Lauf von `check_radar_alerts()`, nur die
Radar-Quelle ist je Punktindex gestellt. Kein `Mock()`/`patch()`, das nur die eigene Annahme
zurückspiegelt. Zwei verschiedene Nutzer entfallen als Pflichtprüfung nur insoweit, als kein neuer
datenbewegender Endpoint entsteht; die Persistenz (`alert_state`, `alert_log`) läuft weiter über
die `user_id` des Trips.

| AC | Test(s) | Datei |
|---|---|---|
| AC-1 | `test_folgepunkt_nass_loest_alarm_aus` | `test_radar_alarm_folgepunkte.py` |
| AC-2 | `test_punkt0_ausloesend_bleibt_bitgleich` + bestehende Radar-Tests unverändert | `test_radar_alarm_folgepunkte.py` |
| AC-3 | `test_massgeblicher_punkt_…`, `test_alle_groessen_stammen_aus_einem_abruf` | `test_radar_alarm_folgepunkte.py` |
| AC-4 | `test_alle_trocken_kein_alarm`, `test_beginn_ueber_55_min_…` | `test_radar_alarm_folgepunkte.py` |
| AC-5 | `test_punkt0_ausfall_folgepunkt_nass_loest_alarm_aus` | `test_radar_alarm_folgepunkte.py`; Wächter-Anpassung in `test_radar_messluecken_protokoll.py` |
| AC-6 | `test_punkt0_ausfall_folgepunkte_trocken_…` | `test_radar_alarm_folgepunkte.py`, `test_radar_messluecken_protokoll.py` |
| AC-7 | `test_punkt0_throttled_…` | `test_radar_alarm_folgepunkte.py` |
| AC-8 | `test_sperrzeit_tageslimit_identitaet_…`, `test_verschaerfung_am_folgepunkt_…` | `test_radar_alarm_folgepunkte.py` |
| AC-9 | `test_punktwechsel_ohne_verschaerfung_kein_zweiter_alarm` | `test_radar_alarm_folgepunkte.py` |
| AC-10 | `test_e1_protokoll_nennt_km_…`, `test_e1_felder_rueckwaertskompatibel` | `test_radar_alarm_folgepunkte.py` |
| AC-11 | `test_folgepunkt_alarm_erreicht_alle_vier_kanaele` | `test_radar_alarm_folgepunkte.py` |
| AC-12 | bestehende Compare-Radar-Tests, Diff-Prüfung | — |
| AC-13 | Doku-Abnahme | — |

**Anpassung des Wächters** `tests/tdd/test_radar_messluecken_protokoll.py:595-625`
(`test_ausfall_am_ersten_punkt_erzeugt_keine_ausdehnungszeile`): Der Fall „Punkt 0 ausgefallen,
Folgepunkte **ausgefallen/trocken**" behält `sent == 0` und die Abwesenheits-Prüfung. Der Fall
„Punkt 0 ausgefallen, Folgepunkt nass" wandert nach `test_radar_alarm_folgepunkte.py` mit
`sent == 1`. Die Positivkontrolle (Ausfall an Index 1 ⇒ `measurement_gaps`) bleibt.

**Mutations-Gegenprobe (Pflicht für den Adversary):** (1) Auswahl auf „immer Punkt 0" zurückdrehen
⇒ AC-1/AC-5 müssen rot werden; (2) Auswahl „spätester statt frühester Beginn" ⇒ AC-3 rot;
(3) Menge/Dringlichkeit weiter aus Punkt 0 lesen, Rest aus dem gewählten Punkt ⇒ AC-3
(Mischwerte) rot; (4) Capture-ID wieder aus Punkt 0 bilden ⇒ AC-3 rot; (5) Ausnahme an Punkt 0
wieder mit `continue` vor der Zonenschleife ⇒ AC-5 rot; (6) `throttled` an Punkt 0 löst
Zusatzabrufe aus ⇒ AC-7 rot; (7) `radar_alert_due` je Punkt ohne Index-Tie-Break ⇒ AC-3 rot. Ein
Mutant, den kein Test fängt, ist ein Finding.

## Expected Behavior

- **Input:** Ergebnisse aller bis zu sechs Messpunkte der Reststrecke (Abstand 2 km) je
  Prüflauf (Scheduler).
- **Output:** Höchstens ein Radar-Alarm je Lauf, in allen konfigurierten Kanälen, mit Werten des
  einen maßgeblichen Punkts; Alarmprotokoll mit auslösendem km.
- **Side effects:** Bei Ausnahme am ersten Punkt zusätzliche Abrufe der Folgepunkte (gedeckelt,
  `priority="polling"`, Cache/Budget #1329 gelten). Sonst keine neuen Abrufe. Keine
  Persistenzänderung (`alert_state`-Schema unverändert; E-1-Feld additiv).

## Known Limitations

1. **Uhrzeit ist Beginn ab jetzt, nicht Ankunft.** Es gibt keine Zeitangabe je Punkt; ein Regen
   bei km +8 „ab 14:10" heißt: dort beginnt es um 14:10. Wann der Wanderer dort ankommt, steht
   nicht im Text (PO-Entscheid a akzeptiert).
2. **Mehr Alarme by design.** Die Fläche der Auslöser wächst von einem auf bis zu sechs Punkte.
   Sperrzeit, Tageslimit und Identitäts-Gate sind der Schutz; AC-8/AC-9 bewachen das.
3. **Punktwechsel zwischen Läufen** wird nur durch die bestehenden Sperren aufgefangen, nicht
   durch Stickiness (siehe oben).

## Risiken

- **Falsche Standort-Aussage im Onset-Kopf** (Kopf nennt Segment-km). Gegenmaßnahme: AC-11,
  Prüfung durch Adversary und Fresh-Eyes-Blick auf Mail-Text.
- **Gate-Reihenfolge:** Menge/Dringlichkeit werden vor dem Guard gelesen; wird die Auswahl zu
  spät gesetzt, bleiben Sperrzeit-Override und Vergleichsbasis auf Punkt 0. Gegenmaßnahme:
  Mutation (3) und AC-8.
- **Vergleichsbasis #2065 über Läufe:** springt der maßgebliche Punkt, könnte die Menge „schrumpfen"
  und eine Verschärfung vortäuschen oder verdecken. Gegenmaßnahme: AC-9; bei Rot Stickiness
  nachziehen.
- **Zusatzabrufe bei Ausnahme an Punkt 0** gegen Budget #1329. Gegenmaßnahme: unverändert
  `polling`-Priorität, `throttled` bleibt ausgenommen (AC-7).
- **Renderer-Commit-Gate / Mail-Validator:** Ändert sich Mail-Inhalt nicht (Dateien in
  `src/output/renderers/` bleiben unberührt), greift das Gate nicht; bei Änderung gilt
  `briefing_mail_validator.py` für Trip-Mails.

## Out of Scope

- **Stickiness-Persistenz** (zuletzt gemeldeten Punkt bevorzugen) — nur nachziehen, falls AC-9 rot
  wird.
- **Ankunftszeit je Punkt** (Zeitpunkt, zu dem der Wanderer den Punkt erreicht) und deren Anzeige
  im Text.
- **Compare-Pfad** (`compare_radar_alert.py`): unverändert (siehe Abschnitt zum geteilten Baustein).
- **Änderung des Abrufbudgets** (#1329) und der Schwelle `RADAR_ONSET_THRESHOLD_MIN`.
- **Render-Umbau** (neuer Ortsbaustein „bei km X"): der bestehende Zonen-Suffix trägt die Ortsangabe.
- Änderungen an `points_along_remaining_route`, Punktzahl oder Punktabstand.

## Changelog

- 2026-10-02: Spec erstellt (Issue #2480, PO-Entscheide a/b vom 2026-10-02); Ablöse-Verweis auf #2050 S4b AC-8 präzisiert.
