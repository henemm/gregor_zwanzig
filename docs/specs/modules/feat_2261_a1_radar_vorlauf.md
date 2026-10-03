---
entity_id: feat_2261_a1_radar_vorlauf
type: feature
created: 2026-10-03
updated: 2026-10-03
status: draft
workflow: feat-2261-a1-radar-vorlauf
version: "1.0"
tags: [alarm, radar, nowcast, vorlauf, schwelle, messort, vergleichbare-menge, trip, ortsvergleich]
---

# Radar-Alarm meldet so früh wie möglich (#2261 Teil A, A-1)

## Approval

- [ ] Approved — Product Owner (offen; Freigabe der ACs auf Deutsch durch Henning steht aus)

Produktentscheid bereits getroffen (PO, 2026-08-21, #2050 A-1): Der Radar-Alarm meldet **so früh
wie möglich** — keine künstliche Untergrenze, einzige Grenze ist die Reichweite der Quelle
(180 Minuten). Die Folge-Regeln dieser Spec (Messort zur Ereigniszeit, vergleichbare Menge,
Ein-Ereignis-ein-Alarm über Segmentwechsel, Uhrzeit statt Restminuten) sind technische
Konsequenzen dieses Entscheids, keine neuen Produktfragen. „Späte Erinnerung kurz vor Eintreffen"
ist durch C-2 / Szenario 5 aus #2050 bereits entschieden (nein).

## Purpose

Der Radar-Alarm löst heute nur aus, wenn der Regen in höchstens 55 Minuten beginnt
(`RADAR_ONSET_THRESHOLD_MIN = 55`), obwohl die Quelle 180 Minuten weit reicht. Die 55 stammen aus
`fix_2009_nowcast_vorlauf` (PO-Freigabe 2026-08-20) mit der Begründung „jenseits ~60 Minuten sinkt
die Ortsschärfe" und der Prämisse „Satelliten-Nutzer auf der Hütte"; beides ist überholt: der
PO-Entscheid A-1 ist einen Tag jünger, die Prämisse hat der PO am 2026-09-05 korrigiert, und die
Ortsschärfe wird seit #2051 S3 über die Gütekennzeichnung (`LOCATION_SHARPNESS_LIMIT_MIN = 60`)
ausgewiesen statt durch Schweigen behandelt.

Diese Spec setzt die Schwelle auf den Quell-Horizont und liefert **in derselben Änderung** die
Vorbereitungen, ohne die ein Wert von 180 Doppel- und Artefakt-Alarme erzeugt: entkoppelter
Messpunkt-Offset, Messort zur Ereigniszeit (B-3), vergleichbare Menge (A-3/C-1), ein Alarm je
Ereignis über Segmentwechsel (C-2), lesbare Zeitangabe statt „in 170 Min" (B-2). Trip und
Ortsvergleich erben die Schwelle gemeinsam (ADR-0021). Alle vier Kanäle (E-Mail, Telegram, SMS,
Premium-SMS) sind gleichrangig.

## Source

- **File:** `src/services/radar_service.py` — Schwelle und Konstanten `:73-140`
  (`NOWCAST_HORIZON_MIN` `:80`, `RADAR_ONSET_THRESHOLD_MIN` `:129`,
  `LOCATION_SHARPNESS_LIMIT_MIN` `:140`); Mengen `window_precip_mm` `:1179`,
  `onset_precip_mm` `:1187-1192`
- **File:** `src/services/trip_alert.py` — `radar_alert_due` `:182`,
  `waehle_massgeblichen_punkt` `:196`, Messpunkt-Zeit `:1855`, Auswahl `:1961-1976`,
  Sperrzeit-Überholung `:2027-2047`, Briefing-Abgleich `:2154-2200`, Identitäts-Gate
  `:2389-2401` (Segmentliste `:2392`)
- **File:** `src/services/trip_segments.py` — `_remaining_km` `:666`,
  `points_along_remaining_route` `:683`, `select_active_segment` `:437`
- **File:** `src/services/alert_gate.py` — `radar_overtakes_cooldown` `:433-458`
- **File:** `src/output/renderers/alert/render.py` — `_onset_wann_kopf` `:630`,
  `_sms_onset_time` `:989`, `_sms_onset_menge` `:1025`, `_sms_onset_sharpness_marker` `:1074`,
  SMS-Zeitgruppe `:1188-1201`
- **File:** `src/services/compare_radar_alert.py` — Docstring `:6`, Auslöseprüfung `:506`
- **Schicht:** Python-Core. Kein Go, kein Frontend, kein neuer Endpoint.

## Estimated Scope

- **Files:** 6 produktiv (`radar_service.py`, `trip_alert.py`, `trip_segments.py`,
  `alert_gate.py`, `render.py`, `compare_radar_alert.py`); `trip_report_scheduler.py` unverändert
- **LoC:** ca. +180/−30 produktiv. Das Limit von 250 wird voraussichtlich nicht erreicht; reicht
  es nicht, `workflow.py set-field loc_limit_override 500`. Tests und Doku zählen nicht.
- **Effort:** high
- **Risk:** MEDIUM-HIGH — eine Zahl, die auf Auslösung, Entdopplung, Sperrzeit-Überholung,
  Briefing-Abgleich, Messort und Texte in allen vier Kanälen wirkt, für Trip und Ortsvergleich.

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `NOWCAST_HORIZON_MIN` (`radar_service.py:80`) | const | Quell-Horizont 180 Min; neue Schwelle wird davon abgeleitet |
| `LOCATION_SHARPNESS_LIMIT_MIN` (`radar_service.py:140`) | const | Gütegrenze 60; zugleich Grenze „vergleichbare Menge" und Grenze „Uhrzeit statt Restminuten" |
| `radar_alert_due` / `waehle_massgeblichen_punkt` (`trip_alert.py`) | function | Auslöseregel je Punkt, Auswahl des maßgeblichen Punkts (#2480) — bleibt, bekommt Fälligkeitsfenster |
| `points_along_remaining_route` / `_remaining_km` (`trip_segments.py`) | function | Messpunkte der Reststrecke; Durchgangszeit je Punkt wird ergänzt |
| `position_at_time`, `select_active_segment`, `convert_trip_to_segments` | function | Planposition als legitime Positionsquelle (kein GPS); Segment zur Ereigniszeit |
| `radar_overtakes_cooldown` (`alert_gate.py`) | function | Menge-gegen-Menge-Vergleich der Sperrzeit; Semantik unverändert |
| `check_event_identity_gate` / `record_event_identity` (`alert_gate.py`) | function | Identitäts-Gate (#1467); **Semantik unverändert** (sonst neues ADR) |
| `alert_daily_limit`, `user_tier` | service | Tagesbudget 2/4/unbegrenzt; Verschärfung bricht durch (D-3, Szenario 7) |
| `_sms_onset_time`, `_onset_wann_kopf` (`render.py`) | function | vorhandener Zeitbaustein mit Tagesbezug (B-2); kein neues Format |
| `compare_radar_alert._detect_triggered_locations` | function | Ortsvergleich erbt die Schwelle über Modulreferenz |
| `tests/helpers/alarm_pruefstrecke.py`, `tests/helpers/strecke_fixtures.py` | test helper | Szenario-Harness, Fake-Radar je Punktindex |

## Implementation Details

### 1. Schwelle abgeleitet (R1)

`RADAR_ONSET_THRESHOLD_MIN = NOWCAST_HORIZON_MIN` — keine zweite Zahl. Der Name bleibt, weil der
Drift-Schutz aus #2009 AC-1 an ihm hängt: Leser holen die Schwelle ausschließlich über die
Modulreferenz `radar_service_mod.RADAR_ONSET_THRESHOLD_MIN`, nie per `from … import`. Der
Begründungskommentar `radar_service.py:113-129` wird auf A-1 umgeschrieben (PO-Entscheid
2026-08-21; Grenze = Reichweite der Quelle; Ortsschärfe über Gütekennzeichnung, nicht über
Schweigen). Trip (`trip_alert.py`) und Ortsvergleich (`compare_radar_alert.py:506`) erben
gemeinsam; es gibt keinen zweiten Pfad mit eigener Zahl.

### 2. Messpunkt-Offset entkoppelt (R2)

Neue Konstante `RADAR_MEASURE_OFFSET_MIN = 27` (der heutige Wert, `55 // 2`) in
`radar_service.py`, gelesen über die Modulreferenz. Sie ersetzt `RADAR_ONSET_THRESHOLD_MIN // 2`
in `trip_alert.py:1855`. Der erste Messpunkt bleibt bit-identisch. Ohne Entkopplung würde der
Messpunkt auf +90 wandern und mit dem Briefing-Offset `NOWCAST_HORIZON_MIN // 2` (+90,
`trip_report_scheduler.py`) zusammenfallen; der Briefing-Offset bleibt unverändert und verschieden.

### 3. Messort zur Ereigniszeit (R3, B-3)

Bei Schwelle 180 darf Regen an einem Punkt nicht auslösen, den der Nutzer erst lange nach
(oder schon vor) dem Regen passiert. Die Fälligkeit eines Punkts wird deshalb um ein
Aufenthaltsfenster ergänzt.

- **Durchgangszeit p_k:** neue Funktion in `trip_segments.py`, die die Punkte samt Durchgangszeit
  liefert. Annahme wie `_remaining_km` (lineare Zeitinterpolation über den Streckenanteil):
  `t0 = max(at, active.start_time)`, `p_k = t0 + Anteil_k · (active.end_time − t0)`, wobei
  `Anteil_k = (k · Punktabstand) / Reststrecke` (0 für den ersten Punkt). Die bestehende Funktion
  `points_along_remaining_route` bleibt rückwärtskompatibel (gleiche Rückgabe, gleiche Punkte).
- **Aufenthaltsfenster-Ende:** `E_k = p_{k+1} + RADAR_PASSAGE_TOLERANCE_MIN` mit neuer Konstante
  `RADAR_PASSAGE_TOLERANCE_MIN = 30` (`radar_service.py`). Für den **letzten** Punkt und den
  Einzelpunkt-Fall (Reststrecke < Punktabstand) ist das Fenster nach oben **offen**: der Nutzer
  erreicht das Etappenziel und bleibt dort.
- **Fälligkeit:** Ein Punkt k ist nur Kandidat in `waehle_massgeblichen_punkt`, wenn zusätzlich zu
  `radar_alert_due` gilt: `now + onset_k ≤ E_k`; läuft der Regen bereits (`already_running`), ist
  der Punkt fällig. Regen, der an einem Punkt erst **nach** dem Weitergehen des Nutzers beginnt,
  löst nicht aus.
- **Rückwärts-Eigenschaft:** Weil `p_1 ≥ t0 ≥ now + 27`, gilt `E_k ≥ 27 + 30 = 57 > 55`.
  Jeder Alarm, der heute (Schwelle 55) ausgelöst hätte, löst weiterhin aus. Szenario 8
  (`test_alarm_szenario_messpunkt_position.py`) bleibt grün.
- Planposition (Zeitplan) ist die legitime Positionsquelle; es gibt kein GPS.

### 4. Vergleichbare Menge (R4, A-3/C-1)

Die Regel „Menge gegen Menge" (#2020 A3/F008) bleibt. Geändert wird nur, **welche** Menge
vergleichbar ist.

- Mengengröße bleibt `window_precip_mm` (60 Minuten ab jetzt; liegt immer innerhalb der
  180-Minuten-Frames, keine Horizont-Kappung).
- **Vergleichbarkeit:** Eine Menge aus einem Lauf gilt als **nicht vergleichbar**, wenn
  `onset_minutes ≥ radar_service_mod.LOCATION_SHARPNESS_LIMIT_MIN` (60) und der Regen nicht
  bereits läuft: das Mengenfenster liegt vor dem Ereignis, ≈0 ist ein Vorlauf-Artefakt. Kleiner
  reiner Baustein (z. B. `menge_ist_vergleichbar(...)` neben `radar_alert_due`).
- **Sperrzeit-Überholung** (`trip_alert.py:2027-2047`): Wird die Basis aus einem nicht
  vergleichbaren Lauf gespeichert, wird sie als `None` behandelt (beim Schreiben der Basis
  `record_nowcast_sent` bzw. beim Lesen über `last_nowcast_precip_mm`; Entscheid der
  Implementierung, Pflicht: ein Lauf mit nicht vergleichbarer Menge hinterlässt keine Basis, gegen
  die später „überholt" werden könnte). Basis `None` → bestehender konservativer Zweig
  (`radar_overtakes_cooldown` liefert `False`), **kein Durchbruch über Menge**. Ist die Menge des
  aktuellen Laufs selbst nicht vergleichbar, gibt es ebenfalls keinen Mengen-Durchbruch.
  Dringlichkeits-Verschärfung (`severity_override` / `quantitative_escalation` bei vergleichbarer
  Menge) kommt weiter durch.
- **Briefing-Abgleich** (`trip_alert.py:2154-2200`, `_overtaking`): Eine nicht vergleichbare Menge
  überholt ein angekündigtes Briefing **nicht** — früher Alarm zu bereits angekündigtem Regen wird
  unterdrückt (C-1); unangekündigter früher Regen wird gemeldet. Wird das Ereignis später
  vergleichbar (Onset < 60), greift der heutige Abgleich unverändert (Faktor
  `_BRIEFING_OVERTAKE_FACTOR`, Untergrenze `_OVERTAKE_MIN_ABSOLUTE_MM`).
- **Anzeige-Menge `onset_precip_mm`** (60 Minuten ab Beginn): Reicht das Fenster über den
  Quell-Horizont hinaus (`onset + 60 > NOWCAST_HORIZON_MIN`, also Onset > 120), ist die Menge am
  Horizont abgeschnitten und zu klein. Dann wird sie **an der Quelle** (`radar_service.py:1187-1192`)
  auf `None` gesetzt; die Intensität bleibt. Alle Anzeigestellen lesen dasselbe Feld und zeigen die
  Mengenangabe dann nicht: `src/output/renderers/alert/project.py:667` (Projektion),
  `src/services/notification_service.py:231/1635` (Request/Durchreichung),
  `render.py:1201` (`_sms_onset_menge(None)` → keine Mengenangabe), `model.py:127` (Feld),
  `trip_alert.py:2354` (Request-Bau), `validator_render_service.py:135/354`. Keine Kanal-eigene
  Sonderlogik: eine Quelle, vier Kanäle.

### 5. Ein Ereignis, ein Alarm über Segmentwechsel (R5, C-2)

Das Identitäts-Gate (`alert_gate.py`) bleibt **unverändert**: disjunkte Segmentmengen sind nie
dasselbe Ereignis. Der Radar-Alarm registriert deshalb statt `[_radar_request.segment_id]`
(`trip_alert.py:2392`) die Menge {aktives Segment} ∪ {Segment, in dem der Nutzer laut Zeitplan zur
Ereigniszeit `now + onset` ist}. Das Segment zur Ereigniszeit wird aus den Segmenten des
Ereignis-Tags (`convert_trip_to_segments`, Auswahl nach Zeit) bestimmt; findet sich keines (Ereignis
nach der letzten Etappe), bleibt es beim aktiven Segment. Die Menge gilt für Prüfung und
Registrierung (`record_event_identity`). Der spätere Alarm bei Eintreffen in Segment B überlappt
und wird als `event_duplicate` unterdrückt; Verschärfungen kommen weiter über `severity_override` /
`quantitative_escalation` durch. Keine „späte Erinnerung kurz vor Eintreffen".

### 6. Texte (R6, B-2)

Bei `onset_minutes > LOCATION_SHARPNESS_LIMIT_MIN` nennt `_onset_wann_kopf` (Betreff,
E-Mail-H1/-Bündelzeile, Telegram-Kopf) statt „in 170 Min" die Uhrzeit mit Tagesbezug über den
vorhandenen Baustein `_sms_onset_time` (kein neues Format, Wochentagskürzel/Tagesbezug wie in der
SMS). Bis einschließlich 60 bleibt „in N Min"; „läuft bereits" bleibt. Die Texte zeigen nur Daten
(Beginn, Intensität, Ort, ggf. Menge), nie Handlungsempfehlungen.

### 7. Ortsvergleich (R7)

`compare_radar_alert.py:506` liest die Schwelle über dieselbe Modulreferenz — keine
Code-Änderung dort außer dem **Docstring `:6`** („Onset ≤ 20 Min" → Schwelle = Horizont der
Quelle). Der Ortsvergleich hat keine Mengen-Überholung (`compare_radar_alert.py` enthält weder
`radar_overtakes_cooldown` noch `window_precip_mm`; geprüft per Grep) und damit keinen
Basis-0.0-Artefakt-Pfad; die Vergleichbarkeitsregel (R4) hat dort keinen Gegenstand. Sein Schutz vor
Doppelalarmen ist Cooldown 120 (`:52/:157`) plus Identität (`:249-253`).

## Abgelöste Entscheidungen

Der Erledigt-Vermerk ist **Teil der Umsetzung** (Doku-Abnahme, `# doc-compliance-test`). In der
Datei-Liste dieser Spec (Änderungen, die die Implementierung ausführt):

| Datei | Bisherige Festlegung | Änderung |
|---|---|---|
| `docs/specs/modules/fix_2009_nowcast_vorlauf.md` (`:82-88`, Known Limitation `:284-290`) | Schwelle 55 mit Ortsschärfe-Begründung; „späte Erinnerung entfällt" | Vermerk „abgelöst durch feat_2261_a1_radar_vorlauf (PO-Entscheid A-1, 2026-08-21)". Die Ablösung betrifft die 55-Begründung und die Schwellenfestlegung; der Drift-Schutz AC-1 (Modulreferenz) bleibt gültig. |
| `docs/specs/modules/feat_2051_s3_reichweite_und_guete.md` (`:88`) | Verweis auf Schwelle 55 neben Gütegrenze 60 | Verweis aktualisieren: Auslöseschwelle = Horizont (180), Gütegrenze bleibt 60 |
| `src/services/compare_radar_alert.py:6` | Docstring „Onset ≤ 20 Min" | Docstring korrigieren (Produktivdatei, siehe Source) |

Neues ADR ist **nicht** nötig: Kein ADR schreibt die 55 fest (Grep-Befund der Analyse);
ADR-0021 regelt nur geteilten Code und Identitäts-Gate, dessen Semantik hier unverändert bleibt.

## Expected Behavior

- **Input:** Radar-Nowcast je Messpunkt (15-Minuten-Raster, bis now+180 Min), Cron
  `7,22,37,52` (erreichbare Onsets 8/23/38/53/68/…/173), Zeitplan der aktiven Etappe.
- **Output:** Ein Radar-Alarm je Ereignis, sobald der Regen irgendwo im Quell-Horizont beginnt und
  dort liegt, wo der Nutzer zur Ereigniszeit sein wird; Kopf mit Uhrzeit statt Restminuten bei
  Onset > 60; Mengenangabe nur, wenn sie nicht am Horizont abgeschnitten ist.
- **Side effects:** Mehr (und frühere) Alarme by design; Tagesbudget Free/Standard wird früher
  verbraucht. Keine Persistenz-Schemaänderung (`alert_state` unverändert; die Vergleichsbasis wird
  für nicht vergleichbare Läufe als „keine Basis" geführt). Isolation: alle Zustände laufen weiter
  über die `user_id` des Trips.

## Acceptance Criteria

- **AC-1 (Schwelle = Reichweite der Quelle):** Given ein Trip mit Regenbeginn in 170 Minuten laut
  Radar-Quelle / When der Radar-Prüflauf läuft / Then wird ein Radar-Alarm versendet, und
  `radar_service.RADAR_ONSET_THRESHOLD_MIN` ist aus `NOWCAST_HORIZON_MIN` abgeleitet (keine zweite
  Zahl); Trip und Ortsvergleich lesen sie über die Modulreferenz, ein Drift zwischen beiden fällt
  im Test auf.
  - Test: `tests/tdd/test_radar_alarm_vorlauf.py::test_beginn_in_170_min_loest_aus`,
    `::test_schwelle_ist_abgeleitet_und_trip_und_vergleich_lesen_dieselbe` (Laufzeit-Drift-Probe:
    Modulwert patchen ⇒ beide Pfade folgen).

- **AC-2 (Messpunkt-Offset entkoppelt):** Given die Schwelle steht auf 180 / When die Messpunkte
  eines Laufs bestimmt werden / Then liegt der erste Messpunkt unverändert bei `now + 27 Min`
  (`RADAR_MEASURE_OFFSET_MIN`), der Briefing-Offset (`NOWCAST_HORIZON_MIN // 2`, +90) bleibt davon
  verschieden, und die Konstante wird nicht aus der Schwelle berechnet.
  - Test: `test_vorlauf_messpunkt.py::test_erster_messpunkt_bleibt_27_min`; die drei bisherigen
    Positionserwartungen (`test_alert_quiet_hours_robustness.py`,
    `test_jetzt_misst_am_aufenthaltsort.py`, `test_radar_alert_follows_ortstag.py`) zeigen auf die
    neue Konstante.

- **AC-3 (Messort zur Ereigniszeit):** Given eine Etappe mit mehreren Messpunkten und Regen, der
  an Punkt 3 erst beginnt, nachdem der Nutzer laut Zeitplan Punkt 3 längst verlassen hat
  (`now + onset_3 > p_4 + 30 Min`) / When der Prüflauf läuft / Then wird kein Alarm ausgelöst;
  beginnt derselbe Regen innerhalb des Aufenthaltsfensters (`now + onset_3 ≤ p_4 + 30 Min`) oder
  am letzten Punkt (Fenster offen), wird alarmiert, und ein bereits laufender Regen ist an jedem
  Punkt fällig.
  - Test: `test_vorlauf_messort_ereigniszeit.py::test_regen_nach_dem_weitergehen_loest_nicht_aus`,
    `::test_regen_im_aufenthaltsfenster_loest_aus`, `::test_letzter_punkt_fenster_offen`,
    `::test_einzelpunkt_fall_fenster_offen`, `::test_laufender_regen_ist_ueberall_faellig`
    (echter `check_radar_alerts()`-Lauf über `AlarmPruefstrecke`, Fake-Radar je Punktindex; die
    Durchgangszeit-Funktion zusätzlich als reiner Test gegen die lineare Interpolation).

- **AC-4 (nichts geht verloren, was heute auslöste):** Given beliebige Konstellationen, in denen
  der Alarm mit Schwelle 55 ausgelöst hätte (Onset ≤ 55 an einem Punkt) / When der Prüflauf mit der
  neuen Regel läuft / Then löst er ebenfalls aus (`E_k ≥ 57 > 55`), und Szenario 8
  (`test_alarm_szenario_messpunkt_position.py`) bleibt unverändert grün.
  - Test: `test_vorlauf_messort_ereigniszeit.py::test_jeder_alarm_von_heute_loest_weiter_aus`
    (parametrisiert über Onset 8/23/38/53 und Punktindex 0..5, auch kurze Etappen mit kleinem
    `p_1 − p_0`), plus die unveränderten `test_alarm_szenario_*`-Wächter.

- **AC-5 (vergleichbare Menge, Sperrzeit-Überholung):** Given ein Ereignis, das erstmals bei
  Onset 170 gemeldet wurde (Menge im Mengenfenster ≈ 0), die Nutzer-Sperrzeit ist länger als 120
  Minuten, und zwei Läufe später liegt die Menge bei ≥ 2 mm bei nun kleinerem Onset / When der
  Prüflauf läuft / Then gibt es **keinen** Durchbruch als „Verschärfung" (Basis aus nicht
  vergleichbarem Lauf gilt als `None`); steigt dagegen die Dringlichkeit (z. B. Gewitter) oder
  überholt eine **vergleichbare** Menge (Onset < 60, Basis vergleichbar, ≥ Faktor und ≥ 2 mm)
  die Basis, bricht der Alarm weiterhin durch.
  - Test: `test_vorlauf_vergleichbare_menge.py::test_basis_aus_vorlauf_artefakt_ist_kein_durchbruch`,
    `::test_dringlichkeit_bricht_trotzdem_durch`,
    `::test_vergleichbare_menge_ueberholt_weiter_die_sperrzeit`; `radar_overtakes_cooldown`
    selbst bleibt in `test_radar_cooldown_overtake.py` unverändert grün.

- **AC-6 (Briefing-Abgleich, C-1):** Given ein Briefing kündigt Regen an (≥ 0,5 mm) / When ein
  Radar-Lauf den Regen bei Onset ≥ 60 sieht / Then wird der Alarm unterdrückt (nicht
  vergleichbare Menge überholt das Briefing nicht, Protokoll `briefing_announced`); sieht derselbe
  Lauf unangekündigten Regen, wird gemeldet; wird das angekündigte Ereignis später vergleichbar
  (Onset < 60) und überholt die Ankündigung nach dem heutigen Faktor, wird gemeldet; ein
  Gewitter durchbricht die Unterdrückung wie bisher (#883).
  - Test: `test_vorlauf_vergleichbare_menge.py::test_angekuendigter_regen_frueh_wird_unterdrueckt`,
    `::test_unangekuendigter_regen_frueh_wird_gemeldet`,
    `::test_spaeter_vergleichbar_ueberholt_wie_heute`, `::test_gewitter_durchbricht_ankuendigung`.

- **AC-7 (Anzeige-Menge am Horizont):** Given ein Regenbeginn mit `onset + 60 > 180` (Onset > 120)
  / When der Alarm in allen Kanälen gerendert wird / Then enthält keiner der vier Kanäle eine
  Mengenangabe (keine falsch kleine Zahl), die Intensität bleibt; bei Onset ≤ 120 erscheint die
  Menge unverändert, und `window_precip_mm`/`max_rate_mm_h` ändern sich dadurch nicht.
  - Test: `test_vorlauf_anzeige_menge.py::test_menge_entfaellt_bei_abgeschnittenem_fenster`
    (Quelle: `NowcastResult.onset_precip_mm is None` bei Onset 150 mit echten 15-Minuten-Frames;
    Wirkung: gerenderte Texte aller vier Kanäle ohne Mengentoken),
    `::test_menge_bleibt_bei_vollem_fenster`.

- **AC-8 (ein Ereignis = ein Alarm über Segmentwechsel, C-2):** Given Erstsicht bei Onset 170 in
  Segment A, der Nutzer erreicht laut Zeitplan zur Ereigniszeit Segment B / When der nächste Lauf
  in Segment B das Ereignis erneut sieht / Then wird genau ein Alarm versendet (der zweite wird als
  `event_duplicate` unterdrückt, Identitäts-Gate-Semantik unverändert); eine echte Verschärfung
  kommt weiter durch; liegt die Ereigniszeit nach der letzten Etappe, bleibt es beim aktiven
  Segment.
  - Test: `test_vorlauf_ein_ereignis_ein_alarm.py::test_erstsicht_170_dann_segmentwechsel_ein_alarm`,
    `::test_verschaerfung_nach_segmentwechsel_kommt_durch`,
    `::test_ereignis_nach_letzter_etappe_bleibt_aktives_segment`; Szenario-Wächter
    `test_alarm_szenario_ein_ereignis_ein_alarm.py` und `…_laufendes_ereignis.py` bleiben grün.

- **AC-9 (Texte: Uhrzeit statt Restminuten, B-2):** Given ein Alarm mit Onset 170 (und einer mit
  Onset 40, einer mit „läuft bereits") / When Betreff, E-Mail-Kopf und Telegram-Kopf gerendert
  werden / Then nennt der Kopf bei 170 die Uhrzeit mit Tagesbezug in der Form des SMS-Bausteins
  (z. B. „ab 14:10", über Mitternacht mit Tagesbezug), bei 40 weiter „in 40 Min", bei laufendem
  Regen weiter „läuft bereits"; der Text enthält nur Daten, keine Handlungsempfehlung.
  - Test: `test_vorlauf_kopf_uhrzeit.py::test_kopf_nennt_uhrzeit_bei_onset_ueber_60`,
    `::test_kopf_bleibt_restminuten_bis_60`, `::test_kopf_uhrzeit_mit_tagesbezug_ueber_mitternacht`,
    `::test_laeuft_bereits_unveraendert`; die Wächter `test_alert_onset_day_rollover.py` und
    `test_onset_wochentagskuerzel.py` bleiben (mit angepassten Literalen) grün.

- **AC-10 (Kanalparität, alle vier gleichrangig):** Given ein Nutzer mit E-Mail, Telegram, SMS und
  Premium-SMS und ein Alarm mit Onset 170 / When der Alarm versendet wird / Then erhalten alle vier
  Kanäle ihn mit demselben Inhalt (Beginn-Uhrzeit mit Tagesbezug, Intensität, Gütekennzeichnung
  „Ortsangabe ab HH:MM unscharf" bzw. SMS-`?`, keine Mengenangabe wegen AC-7); kein Kanal ersetzt
  einen anderen, und der Alarm erreicht auch den Premium-SMS-Kanal.
  - Test: `test_vorlauf_kanalparitaet.py::test_alarm_bei_onset_170_erreicht_alle_vier_kanaele`
    (Prüfstrecke, Kanalinhalte aller vier Kanäle; Inhaltsprüfung auf Uhrzeit und Güte-Marke, keine
    reine String-Presence). Live: Staging-Lauf über den echten Kanal-Eingang;
    Premium-SMS-Empfang über die zweite seven.io-Nummer.

- **AC-11 (Ortsvergleich erbt die Schwelle):** Given ein Ortsvergleich-Preset mit einem Ort, an dem
  der Regen erstmals bei Onset 170 gesehen wird / When der Ortsvergleich-Radar-Lauf mehrfach über
  die Cooldown-Dauer läuft / Then entsteht genau ein Ortsvergleich-Alarm (Cooldown 120 +
  Identität), und der Docstring `compare_radar_alert.py:6` nennt nicht mehr „≤ 20 Min", sondern die
  geteilte Schwelle; der Ortsvergleich hat keine Mengen-Überholung, die Vergleichbarkeitsregel
  (AC-5) berührt ihn nicht.
  - Test: `test_vorlauf_ortsvergleich.py::test_erstsicht_170_ergibt_genau_einen_alarm`,
    `::test_ortsvergleich_liest_schwelle_ueber_modulreferenz`; Docstring-Korrektur per
    Doku-Abnahme (`# doc-compliance-test`).

- **AC-12 (jenseits des Horizonts / keine Frames kein Alarm):** Given Regenbeginn jenseits der
  180 Minuten (nur Frames bis 180 trocken, nasse Frames ab 195) oder eine Quelle ohne Frames
  (`data_unavailable`) / When der Prüflauf läuft / Then wird kein Alarm versendet, und der Lauf
  wird bei fehlenden Frames weiterhin als Quellenausfall protokolliert, nie als „ruhig". Dies
  ersetzt die zwei Tests „Onset > Schwelle → kein Alarm", die bei Schwelle = Horizont nicht mehr
  konstruierbar sind.
  - Test: `test_vorlauf_horizont.py::test_beginn_jenseits_des_horizonts_kein_alarm`,
    `::test_ohne_frames_kein_alarm_aber_protokoll`; ersetzt
    `test_feature_656_radar_nowcast.py:250` und `test_radar_cooldown_overtake.py:1135`.

- **AC-13 (Erledigt-Vermerke):** Given die Tabelle „Abgelöste Entscheidungen" / When die
  Umsetzung abgeschlossen ist / Then tragen `fix_2009_nowcast_vorlauf.md` und
  `feat_2051_s3_reichweite_und_guete.md` (`:88`) einen Ablösungsvermerk mit Verweis auf diese
  Spec, und der Begründungskommentar `radar_service.py:113-129` nennt A-1 statt der 55-Begründung.
  - Test: Doku-Abnahme (`# doc-compliance-test`, kein Verhaltenstest).

## Test Plan

### Automated Tests (TDD RED)

Neue Testdateien nach Verhalten benannt (`tests/tdd/`): `test_radar_alarm_vorlauf.py`,
`test_vorlauf_messpunkt.py`, `test_vorlauf_messort_ereigniszeit.py`,
`test_vorlauf_vergleichbare_menge.py`, `test_vorlauf_anzeige_menge.py`,
`test_vorlauf_ein_ereignis_ein_alarm.py`, `test_vorlauf_kopf_uhrzeit.py`,
`test_vorlauf_kanalparitaet.py`, `test_vorlauf_ortsvergleich.py`, `test_vorlauf_horizont.py`
(die Implementierung darf nach Verhalten zusammenlegen). Aufbau über
`AlarmPruefstrecke(...).lauf(at=, zweig="radar", trip=, radar_service=)` mit
`recording_radar_service_type(...)`, `nass()`, `trocken()`: ein echter Lauf von
`check_radar_alerts()`, nur die Radar-Quelle ist gestellt; echte aufgezeichnete Frames als
Fixtures erwünscht. Kein `Mock()`/`patch()`, das nur die eigene Annahme zurückspiegelt, keine
Dateiinhalt-Checks. Jeder Test mit Persistenz läuft mit zwei verschiedenen Nutzern
(`user_id` aus dem Trip, kein `"default"`-Rückfall).

- [ ] GIVEN Regenbeginn in 170 Min WHEN Prüflauf THEN Alarm (AC-1)
- [ ] GIVEN erster Messpunkt WHEN Schwelle 180 THEN Messpunkt bei +27 Min, Briefing-Offset verschieden (AC-2)
- [ ] GIVEN Regen beginnt erst nach dem Weitergehen WHEN Prüflauf THEN kein Alarm (AC-3)
- [ ] GIVEN Konstellationen, die mit 55 auslösten WHEN Prüflauf THEN weiter Alarm (AC-4)
- [ ] GIVEN Erstsicht 170 und Sperrzeit > 120 WHEN Menge ≥ 2 mm später THEN kein Durchbruch (AC-5)
- [ ] GIVEN angekündigter Regen WHEN früher Alarm bei Onset ≥ 60 THEN unterdrückt (AC-6)
- [ ] GIVEN Onset > 120 WHEN Rendern THEN keine Mengenangabe in allen Kanälen (AC-7)
- [ ] GIVEN Erstsicht in Segment A WHEN Eintreffen in B THEN genau ein Alarm (AC-8)
- [ ] GIVEN Onset 170 WHEN Kopf rendern THEN Uhrzeit mit Tagesbezug (AC-9)
- [ ] GIVEN vier Kanäle WHEN Alarm Onset 170 THEN alle vier mit gleichem Inhalt (AC-10)
- [ ] GIVEN Ortsvergleich Onset 170 WHEN mehrere Läufe THEN ein Alarm (AC-11)
- [ ] GIVEN Beginn jenseits 180 oder keine Frames WHEN Prüflauf THEN kein Alarm (AC-12)

### Test-Kartierung (bestehende Tests)

- **Anzupassen, Literal 55/53 (veraltetes Verhalten, Schwelle jetzt Horizont):**
  `tests/tdd/test_radar_alarm_folgepunkte.py:78`, `tests/tdd/test_issue_822_radar_nowcast_segment.py:1241`,
  `test_alert_onset_day_rollover.py` (45/193/270/312), `test_onset_wochentagskuerzel.py`
  (106/248/532/668), `test_trip_report_scheduler_starkregen_hint.py:80/200`,
  `test_radar_onset_threshold_variance.py`.
- **Anzupassen, `RADAR_ONSET_THRESHOLD_MIN // 2` als erwarteter Messpunkt → neue Konstante
  `RADAR_MEASURE_OFFSET_MIN`:** `test_alert_quiet_hours_robustness.py:385`,
  `test_jetzt_misst_am_aufenthaltsort.py:186`, `test_radar_alert_follows_ortstag.py:197`.
- **Umzuschreiben (Ersatz siehe AC-12, kein Vakuum-Grün):**
  `test_feature_656_radar_nowcast.py:250`, `test_radar_cooldown_overtake.py:1135`.
- **Bleiben gültig:** `test_onset_reichweite_guete_kanalparitaet.py:97`,
  `test_onset_ende_kanalparitaet.py:91` (Onset 20).
- **Szenario-Wächter müssen grün bleiben:** `test_alarm_szenario_ein_ereignis_ein_alarm.py`,
  `…_laufendes_ereignis.py`, `…_tagesbezug_zeitzone.py`, `…_messpunkt_position.py` (Sz. 8).
- Tests werden nur über benannte Testdateien gefahren (`uv run pytest <Dateien>`), nie ohne.

### Live-Verifikation (Staging, nach Merge)

`/e2e-verify` über den echten Kanal-Eingang mit Trip-Nutzer und Ortsvergleich-Nutzer: Alarm bei
Onset > 60 in allen vier Kanälen; Trip-Briefing-Mail mit `briefing_mail_validator.py` (Wegwerf-Nutzer
`gregor-test+…`); Premium-SMS-Empfang über die zweite seven.io-Nummer prüfen (nie „Garmin
ungetestet"); Scheduler-`last_run` geprüft.

**Mutations-Gegenprobe (Pflicht für den Adversary, per String-Ersetzung mit externer Sicherungskopie):**
(1) Schwelle zurück auf 55 ⇒ AC-1 rot; (2) `RADAR_MEASURE_OFFSET_MIN` wieder `THRESHOLD // 2`
⇒ AC-2 rot; (3) Fälligkeitsfenster entfernt (Punkt immer fällig) ⇒ AC-3 rot; (4) Fenster zu eng
(Toleranz 0) ⇒ AC-4 rot; (5) Basis aus Vorlauf-Lauf nicht auf `None` ⇒ AC-5 rot;
(6) `_overtaking` ohne Vergleichbarkeit ⇒ AC-6 rot; (7) `onset_precip_mm` nicht gekappt ⇒ AC-7 rot;
(8) Segmentmenge wieder nur `[segment_id]` ⇒ AC-8 rot; (9) Kopf immer „in N Min" ⇒ AC-9 rot;
(10) Kanalzweig ohne Premium-SMS ⇒ AC-10 rot; (11) Ortsvergleich mit eigener Literal-Schwelle ⇒
AC-1/AC-11 rot; (12) Horizont-Gegenprobe ohne Frames-Wächter ⇒ AC-12 rot. Ein Mutant, den kein Test
fängt, ist ein Finding; entscheidend ist, WELCHER Test rot wird.

## Known Limitations

1. **Mehr Alarme insgesamt (by design).** Jede nasse Zelle innerhalb von 3 Stunden an bis zu
   sechs Messpunkten kann auslösen; die Gütekennzeichnung „unscharf" ist bei frühen Alarmen der
   Normalfall (Extrapolation > 60 Min nicht ortsscharf). Schutz: Aufenthaltsfenster (AC-3),
   Sperrzeit, Tageslimit, Identitäts-Gate.
2. **Tagesbudget Free (2) / Standard (4)** wird früher am Tag durch ferne Ereignisse verbraucht;
   Premium ist unbegrenzt. Der Schutz ist D-3 (eine Verschärfung kommt durch, Szenario 7).
3. **Premium-SMS-Kosten** steigen mit der Alarmzahl (Premium-Tier unbegrenzt).
4. **Keine späte Erinnerung kurz vor Eintreffen** (C-2 entschieden): Nach der Erstmeldung gibt es
   nur Verschärfungen; Identität unterdrückt den „Eintreffen"-Alarm, auch nach Ruhezeit-Ende.
5. **Planposition statt GPS:** Die Durchgangszeit folgt dem Zeitplan; wer schneller oder
   langsamer geht, verschiebt sich gegen das Aufenthaltsfenster (daher die Toleranz von 30 Min).
6. **Cron-Raster:** erreichbare Onsets sind 8/23/38/53/…/173 Minuten; ein Regen bei Onset 178
   erscheint erst im nächsten Lauf. Der Debug-Trigger `api/routers/debug.py:37` umgeht
   `radar_alert_due` und bleibt unberührt.
7. **Briefing-Hinweis unberührt:** Der Briefing-Starkregen-Hinweis
   (`trip_report_scheduler.py:1975-2005`) hat einen eigenen Horizont-Wächter und Offset +90.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Kein ADR schreibt die 55 fest; ADR-0021 (geteilter Code Trip/Ortsvergleich,
  Identitäts-Gate) wird eingehalten — Gate-Semantik unverändert, Schwelle nur über die gemeinsame
  Modulreferenz. Die Ablösung von `fix_2009` ist als Änderungsvermerk dokumentiert.

## Changelog

- 2026-10-03: Initial spec created (#2261 Teil A, Punkt A-1; PO-Entscheid 2026-08-21)
