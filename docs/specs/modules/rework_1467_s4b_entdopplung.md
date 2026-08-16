---
entity_id: rework_1467_s4b_entdopplung
type: refactor
created: 2026-08-16
updated: 2026-08-16
status: draft
version: "1.0"
tags: [alerts, trip, epic-1458, issue-1467, issue-1744, s4b, s4b-1, entdopplung]
---

# Quellenübergreifende Alarm-Entdopplung nach Ereignis-Identität — Trip-Fläche (Issue #1467 Scheibe S4b-1, = #1744 Scheibe B, Epic #1458 Teil 4b)

## Approval

- [x] Approved — PO-Freigabe 2026-08-16 (inkl. Entscheid: EINE Gefahrenklasse `wet` statt zwei; `loc_limit_override` bewilligt)

## Purpose

Ein und dasselbe Gewitter löst heute zwei unabhängige Alarme aus: einen
Radar-Nowcast und — Minuten später — eine amtliche Warnung. Beide werden
zugestellt, weil ihre Sperrzeiten in getrennten Töpfen je **Quelle** liegen
und einander konstruktionsbedingt nicht sehen können. Gemessen am
Produktivprotokoll (13 Tage, 2026-08-03 bis 2026-08-16): der auslösende
Vorfall (`5f534011`, 2026-08-11 14:22 UTC, Nowcast `thunder` gefolgt von
amtlich `thunderstorm` nach +8,2 Min) ist real wiedergefunden, und
quellenübergreifende Doppelungen dieser Art treten im Schnitt alle 1,5 Tage
auf (6 Fälle in 13 Tagen).

Diese Scheibe führt einen geteilten Baustein `check_event_identity_gate()`
ein, der **nach Ereignis-Identität** — gleiche Gefahrenklasse + gleicher
Ortsbezug + überlappendes Zeitfenster — entdoppelt, bevor eine zweite
Meldung für dasselbe Ereignis rausgeht. Sie ist die letzte von drei
Teilscheiben aus #1744 Scheibe B und **schließt Issue #1467**.

**Scope dieser Teilscheibe (S4b-1):** ausschließlich die **Trip-Fläche**,
**beide Richtungen** — `check_radar_alerts()` (Nowcast) und
`check_official_alert_triggers()`/`_send_official_alert_only()` (amtlich)
in `src/services/trip_alert.py`. Der Baustein wird von Anfang an
**entitätsparametrisiert** gebaut (Trip/Compare-Teilungsregel), damit die
Ortsvergleich-Verdrahtung (S4b-2, eigenes Folge-Issue) reine Zusatz-Aufrufe
ohne neue Logik ist.

**Leitsatz, unverändert aus S1–S4a übernommen:** Der gefährlichste Fehler
ist der ausbleibende Alarm. Jede Unsicherheit in dieser Scheibe — fehlender
Zeitbezug, fehlende Ortskennung, unbekannte Gefahrenart — entscheidet sich
**immer** Richtung Zustellung, nie Richtung Unterdrückung.

## Source

- **File:** `src/services/alert_gate.py`
- **Identifier:** neue Funktionen `check_event_identity_gate`,
  `resolve_hazard_class`, `record_event_identity`

Betroffene Schicht: ausschließlich **Python-Core** (`src/services/`,
`src/output/renderers/alert/`). Kein Go-Code, kein Frontend-Code.

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `rework_1467_s4a_amtlich` | module | Vorgänger-Scheibe (live) — liefert `check_official_alert_gate`, `GateResult`-Muster, Aufrufstellen-Positionen in `_send_official_alert_only`; diese Scheibe fügt eine **weitere**, letzte Stufe an dieselben Aufrufstellen an |
| `rework_1467_s3_nowcast` | module | liefert `check_nowcast_gate`, `record_nowcast_sent`, das Protokoll-Muster `append_suppressed_entry` (bisher Nowcast-only) |
| `rework_1467_s1_alarm_kennung` | module | `entity_id`/`entity_type` ∈ {trip, compare} — Ereignis-Identität setzt auf dieser Kennung auf |
| `fix_1744_alarm_format_angleichen` | module | liefert `format_segment_reference`, `normalize_segment_id` (`output/renderers/alert/segments.py`) — die Ortsbezug-Normalisierung dieser Scheibe verwendet dieselbe Funktion, keine zweite |
| `services.alert_urgency` | module | geteilte Dringlichkeits-Skala `"LOW"`/`"MODERATE"`/`"HIGH"` — die Eskalations-Prüfung (V2) vergleicht auf dieser bestehenden Skala, keine neue Rangfolge |
| `services.alert_state.AlertStateService` | module | Melde-Gedächtnis-Ablage; das neue Ereignis-Identität-Register liegt in derselben Datei wie das amtliche Melde-Gedächtnis, eigener Schlüssel-Präfix |
| `services.radar_service.NOWCAST_HORIZON_MIN` | module | bestehende Konstante (60 Min) — Puffer für Punkt-gegen-Intervall-Überlappung UND Schwelle für „wesentlich darüber hinaus" (V1); keine neue Konstante |
| `output.renderers.alert.official_alerts.dedupe_official_alerts` / `official_alert_revision_verdict` | module | bleiben unverändert zuständig für amtlich-gegen-amtlich (gleiche und verschiedene Quellen) — außerhalb des Scopes dieser Scheibe |
| `trip_alert.py` Doppel-Alert-Guard (`:1081-1099`) | module | bleibt unverändert bestehen (T7-Entscheidung, s. Implementation Details) — deckt Nowcast-gegen-Änderungsalarm ab, eine andere Paarung als diese Scheibe |
| `alert_log` | module | neue Konstante `REASON_EVENT_DUPLICATE`; `append_suppressed_entry` wird erstmals auch vom amtlichen Pfad aufgerufen |
| `alert_channel_threshold.split_by_threshold` | module | bleibt unverändert NACH dem neuen Gate — Kanal-Schwelle entscheidet WIE, das Gate entscheidet OB (ADR-0046, V3) |

## Estimated Scope

- **LoC produktiv:** ~180–230 (`alert_gate.py` neue Funktionen ~90–120,
  `alert_urgency.py` +1 Vergleichs-Helfer ~8–12, `alert_log.py` +1 Konstante,
  `alert_state.py` reiner Docstring-Zusatz (keine Logikänderung, s.
  Implementation Details), `trip_alert.py`-Verdrahtung an zwei Stellen
  inkl. Batch-Filterung im amtlichen Pfad ~60–90).
- **LoC Tests:** ~350–500 — **sprengt das 250er-Budget deutlich**,
  `loc_limit_override` erforderlich (analog S4a, dort auf 1000
  angehoben; hier schlanker, weil nur EIN Baustein + zwei Aufrufstellen
  statt zwei vollständige Pfad-Umbauten). Begründung: kritischer
  Alarmpfad, zwei Richtungen, Mutations-Gegenprobe zu V1 UND V2 PFLICHT,
  Mandantentrennungs-Nachweis, Batch-Teilunterdrückung.
- **Files:** 0 neu, 5 produktiv geändert (`alert_gate.py`,
  `alert_urgency.py`, `alert_log.py`, `alert_state.py` [Docstring],
  `trip_alert.py`), 1 ADR-Nachtrag, ~4–5 Testdateien geändert/neu.
- **Effort:** high.
- **Risiko:** HOCH — kritischer Alarmpfad, quellenübergreifende Logik ohne
  Präzedenz, Fehlerrichtung „Alarm bleibt aus" ist per Definition am
  schwersten zu bemerken (die Meldung fehlt einfach).

## Implementation Details

### Gefahrenart-Kanon (T2) — EINE Klasse, PO-Entscheid 2026-08-16

Die real vorkommenden `OfficialAlert.hazard`-Werte wurden im Code
nachgeprüft (`grep hazard=` über `src/services/official_alerts/*.py`):

`wind_gust`, `rain`, `snow`, `black_ice`, `thunderstorm`, `extreme_heat`,
`extreme_cold`, `wildfire_risk`, `flood`, `access_ban` — zehn Werte aus
sechs Quellen (`geosphere_warn.py`, `vigilance.py`, `meteoalarm.py`,
`meteo_forets.py`, `massif_closure.py`, `dpc.py`).

**Kanon:**

| Klasse | Nowcast-Signal | amtliche Hazards |
|---|---|---|
| `"wet"` (Niederschlag/Gewitter) | `is_convective` — **beide** Werte | `"thunderstorm"`, `"flood"`, `"rain"` |

Alle anderen amtlichen Hazards (`wind_gust`, `snow`, `black_ice`,
`extreme_heat`, `extreme_cold`, `wildfire_risk`, `access_ban`) fallen in
**keine** Klasse und werden nie entdoppelt (AC-4).

**Warum EINE Klasse und nicht zwei (konvektiv vs. Niederschlag):** Der
ursprüngliche Zuschnitt trennte nach `is_convective`. Die Messung am
Produktivprotokoll widerlegt das als Identitätskriterium — es ist eine
Momentaufnahme der Radarzelle, nicht die Ereignis-Identität. Am 2026-08-11
erzeugte **eine** Gewitterlage auf Trip `5f534011` sechs Alarme für dieselbe
Etappe: 14:22 Radar/konvektiv, 14:30 amtlich `thunderstorm`, 15:07
Radar/nicht-konvektiv, 15:45 amtlich, 17:45 amtlich, 17:52
Radar/nicht-konvektiv. Dieselbe Zelle wurde also mal als Gewitter, mal als
Regen eingestuft (`alert_log.register_pairs_for_nowcast()` bildet
`is_convective` genau darauf ab, `alert_log.py:95-105`). Mit zwei getrennten
Klassen liefen drei der vier gemessenen quellenübergreifenden Paare
aneinander vorbei — die Scheibe hätte von sechs Meldungen etwa vier übrig
gelassen statt zwei.

Die Trennschärfe kommt stattdessen aus den übrigen drei Bedingungen:
dieselbe Etappe, überlappendes Zeitfenster, und die beiden Ausnahmen (V1
Abdeckungs-Vorbehalt, V2 Eskalation). **`rain` ist mit dieser Entscheidung
Teil des Kanons** — damit entfällt die zuvor benannte `rain`-vs-`flood`-Lücke.

**Preis, der benannt gehört:** Ein rein stratiformer Landregen-Nowcast kann
unterdrückt werden, wenn für dieselbe Etappe eine überlappende amtliche
Gewitterwarnung bereits gemeldet wurde. Fachlich vertretbar — der Nutzer
wurde für diesen Ort und Zeitraum bereits vor Niederschlag gewarnt, nur
unter dem Wort „Gewitter". Umgekehrt gilt dasselbe.

```python
# src/services/alert_gate.py
HAZARD_CLASS_WET = "wet"
_WET_HAZARDS = frozenset({"thunderstorm", "flood", "rain"})


def resolve_hazard_class(
    *, is_convective: Optional[bool] = None, hazard: Optional[str] = None,
) -> Optional[str]:
    """T2-Kanon. Genau EIN Identifikationsweg pro Aufrufer: Nowcast liefert
    `is_convective`, amtlich liefert `hazard`. Unbekannter/anderer Hazard
    -> None (keine Klasse, nie entdoppelt).

    Ein Nowcast ist IMMER Niederschlag — `is_convective` unterscheidet nur
    die Erscheinungsform derselben Zelle, nicht das Ereignis (PO-Entscheid
    2026-08-16, Messung s.o.)."""
    if is_convective is not None:
        return HAZARD_CLASS_WET
    if hazard in _WET_HAZARDS:
        return HAZARD_CLASS_WET
    return None
```

### Ortsbezug (T3) — kein neues Datenmodell nötig

Alle drei Trip-Alarmarten führen bereits dieselbe Segment-Kennung:
Nowcast `normalize_segment_id(active.segment_id)` (`trip_alert.py:1149`),
amtlich `str(segment.segment_id)` je Koordinaten-Cluster
(`trip_alert.py:1423/1432`). `normalize_segment_id()`
(`output/renderers/alert/segments.py:17-29`) ist reines
`str(value).strip() or None` — roh und normalisiert sind wertgleich.
Ortsbezug-Match = nicht-leere Schnittmenge der Segment-ID-Mengen.
`region_label` wird **nicht** verwendet (Freitext einer fremden Quelle,
keine Geografie-Gleichsetzung mit Segment-IDs).

**Bruchstelle (AC-5):** eine leere/fehlende Kennung erzeugt **nie** ein
Match — sonst würde „kein Ort bekannt" auf „jeden Ort" passen und ein
Ereignis ohne Ortsangabe könnte fälschlich ein völlig anderswo laufendes
Ereignis unterdrücken.

### Zeitfenster (T4) — drei Vergleichsfälle, nur einer end-to-end verdrahtet

Punkt (Nowcast-Onset) und Intervall (`valid_from`/`valid_to`) sind
unterschiedliche Repräsentationen; die Vergleichsfunktion behandelt alle
drei Kombinationen, aber nur **Punkt-gegen-Intervall** ist über die beiden
Aufrufstellen dieser Scheibe erreichbar (der gemessene Kernfall):

- **Punkt gegen Intervall:** Überlappung mit Puffer
  `NOWCAST_HORIZON_MIN` (60) — `punkt ∈ [valid_from − 60min, valid_to + 60min]`.
- **Punkt gegen Punkt:** Differenz ≤ `cooldown_minutes` (bereits vorhandener
  Trip-Parameter, s. `trip_alert.py:998-1002`). Über die beiden
  verdrahteten Aufrufstellen dieser Scheibe nicht erreichbar (ein zweiter
  Nowcast innerhalb des Cooldowns wird bereits von `check_nowcast_gate`s
  Sperrzeit-Stufe abgefangen, bevor die neue Stufe erreicht wird) — bleibt
  in der Matching-Funktion als Vollständigkeits-/Vorbereitungsfall für
  S4b-2/S4b-3, isoliert getestet, nicht Teil des End-to-End-Nachweises.
- **Intervall gegen Intervall:** echte Überlappung
  (`alert_vf < cand_vt and cand_vf < alert_vt`, analog
  `official_alert_revision_verdict`). Ebenfalls nicht end-to-end
  erreichbar in S4b-1 (amtlich-gegen-amtlich bleibt vollständig bei
  `dedupe_official_alerts`/`official_alert_revision_verdict`, s.
  Nicht-Ziele) — isoliert getestet.

**Fehlender/unvergleichbarer Zeitbezug ⇒ kein Match ⇒ senden** (AC-7,
fail-soft, gleiche Richtung wie `official_alert_revision_verdict` bei
fehlendem `valid_from`/`valid_to`).

### Die Kernregel (V1) und ihre Ausnahme

„Wer zuerst meldet, gewinnt" — die zweite Meldung wird unterdrückt, **außer**
ihr Zeitfenster reicht wesentlich über das der ersten hinaus. „Wesentlich" =
mehr als `NOWCAST_HORIZON_MIN` (60 Min) über das bereits abgedeckte Ende
hinaus — dieselbe Konstante wie der Überlappungs-Puffer, keine neue Zahl.
Begründung (PO, 2026-08-16): eine amtliche Warnung gilt oft bis in den
Abend, ein Nowcast deckt nur 60 Minuten. Fiele die amtliche Warnung nach
einem vorangegangenen Nowcast ersatzlos weg, wüsste der Wanderer nicht,
dass die Lage stundenlang kritisch bleibt — und sie käme auch nicht
nachträglich, weil `official_alert_revision_verdict()` sie beim nächsten
Lauf als bereits gesehen führt (eigener State-Raum, von dieser Scheibe
unberührt).

„Abgedecktes Ende" einer registrierten Meldung:

```python
def _covered_until(point_at, window_end) -> Optional[datetime]:
    if point_at is not None:
        return point_at + timedelta(minutes=NOWCAST_HORIZON_MIN)
    return window_end
```

### Eskalation durchbricht immer (V2) — struktureller erster Zweig

Nach dem Auffinden eines passenden Registereintrags (gleiche Klasse,
überlappender Ort, überlappende Zeit) ist die Eskalationsprüfung der
**erste** Zweig mit eigenem `return` — noch vor der V1-Ausnahme
(Zeitfenster-Erweiterung) und vor der eigentlichen Unterdrückung. Vorbild:
`official_alert_revision_verdict()`
(`output/renderers/alert/official_alerts.py:428-520`), die dasselbe Muster
für amtlich-gegen-amtlich bereits umsetzt. Vergleichen wird auf der
bestehenden Dringlichkeits-Skala `services.alert_urgency`
(`"LOW"`/`"MODERATE"`/`"HIGH"`), die beide Quellen bereits an den
Aufrufstellen berechnen (`_radar_urgency` in `check_radar_alerts`,
`_official_urgency` in `_send_official_alert_only`) — kein neuer
Wertebereich. `alert_urgency.py` bekommt dafür einen kleinen öffentlichen
Vergleichs-Helfer (wiederverwendet die bestehende `_RANK`-Tabelle, keine
zweite Rangfolge — Wiederholungsklasse #1481):

```python
# src/services/alert_urgency.py
def exceeds(a: str, b: str) -> bool:
    """Echtes Groesser-als auf der bestehenden LOW/MODERATE/HIGH-Skala."""
    return _RANK.get(a, 0) > _RANK.get(b, 0)
```

```python
# src/services/alert_gate.py — Kernablauf (vereinfacht)
def check_event_identity_gate(*, ..., severity, ...) -> GateResult:
    if hazard_class is None:
        return _ALLOWED  # T2: keine Klasse, kein Match möglich
    match = _find_matching_entry(state, hazard_class, segment_ids,
                                  point_at, window_start, window_end,
                                  cooldown_minutes)
    if match is None:
        return _ALLOWED  # kein Vorgänger, oder kein Zeit-/Ortsbezug
    if alert_urgency.exceeds(severity, match["severity"]):
        return _ALLOWED  # V2 — ERSTER Zweig, bricht IMMER durch
    if _covers_materially_more(match, point_at, window_start, window_end):
        return _ALLOWED  # V1-Ausnahme
    return GateResult(False, alert_log.REASON_EVENT_DUPLICATE)
```

### Kanalübergreifend, nicht je Kanal (V3)

Der neue Gate-Aufruf steht **vor** `alert_channel_threshold.split_by_threshold()`
(`trip_alert.py:1167`/`:1519`) an beiden Aufrufstellen — ein Ergebnis für
die ganze Entität, danach entscheidet die Kanal-Schwelle nur noch, auf
welchem Weg eine bereits freigegebene Meldung geht (ADR-0046: die Schwelle
regelt WIE, nie OB).

### Aufrufstellen — letzte Stufe vor dem Versand

| Pfad | Position | Bestehende Stufen davor |
|---|---|---|
| `check_radar_alerts()` (Nowcast) | unmittelbar vor `self._notification_service.send_radar_alert(...)` (`:1172`), nach `_radar_urgency` (`:1163`) | `check_nowcast_gate` (`:1008`) → Briefing-Vergleich (`:1075`) → Doppel-Alert-Guard (`:1081-1099`, **bleibt unverändert**, s. T7 unten) |
| `_send_official_alert_only()` (amtlich) | unmittelbar vor `self._notification_service.send_official_alert(...)` (`:1522`), nach `_official_urgency` (`:1515`) — **pro Alert**, s. Batch-Filterung | `check_official_alert_gate` (`:1496`) → `_is_briefing_imminent` (`:1507`) |

Die Ereignis-Identität steht bewusst zuletzt: sie ist die teuerste Prüfung
(Register-Scan + Zeit-/Ortsvergleich), ein durch billigere Stufen ohnehin
gesperrter Alarm soll sie nicht mehr durchlaufen.

### Batch-Filterung im amtlichen Pfad (Bruchstelle, eigenes AC)

`_send_official_alert_only()` verschickt heute **alle** `official_notices`
eines Laufs in **einer** Nachricht; `_official_urgency` ist die höchste
Dringlichkeit über die ganze Liste. Ein blindes Gate über die ganze Liste
wäre falsch in **beide** Richtungen:

- alles durchlassen, weil ein Teil neu ist → die Nowcast-Dublette bleibt
  bestehen (Zweck verfehlt);
- alles sperren, weil ein Teil ein Duplikat ist → eine zweite, echte
  Warnung im selben Lauf (z. B. `extreme_heat` neben duplikat
  `thunderstorm`) würde mit verschluckt — genau die Fehlerrichtung „Alarm
  bleibt aus", die diese Scheibe nicht erzeugen darf.

Deshalb wird **pro Alert** geprüft und gefiltert, `_official_urgency` **nach**
dem Filtern aus der verbleibenden Liste neu berechnet; bleibt die Liste
leer, wird nichts verschickt und nichts gebucht (AC-17).

### Register — Ablage im bestehenden `AlertStateService`

Neuer Schlüssel-Präfix `EVENT_IDENTITY_KEY_PREFIX = "event_identity:"` in
`alert_state.py` (analog `OFFICIAL_ALERT_KEY_PREFIX`). Ein Eintrag je
erfolgreich zugestellter Meldung (Nowcast **oder** amtlich — dasselbe
Register für beide Richtungen, das ist, was „quellenübergreifend"
technisch bedeutet: wer zuerst zustellt, schreibt; wer zweiter ist, liest
denselben Eintrag):

```json
"event_identity:wet:3,4:2026-08-11T14:22:00+00:00": {
  "hazard_class": "wet",
  "segment_ids": ["3", "4"],
  "severity": "HIGH",
  "point_at": "2026-08-11T14:22:00+00:00",
  "window_start": null,
  "window_end": null,
  "reported_at": "2026-08-11T14:22:03+00:00"
}
```

Matching scannt per `startswith("event_identity:<hazard_class>:")` (analog
`_identity_hazard_prefix()` in `official_alerts.py:402-425`) und prüft je
Kandidat Segment-Schnittmenge + Zeitüberlappung. `record_event_identity()`
wird **ausschließlich nach erfolgreicher Zustellung** aufgerufen (F001-
Symmetrie zu `record_nowcast_sent`).

**Reset-Verhalten (T5, kein Logik-Eingriff nötig):**
`AlertStateService.reset()` (`alert_state.py:73-100`) behält **nur**
Schlüssel mit Präfix `official_alert:` und verwirft alles andere. Ein
neuer Präfix `event_identity:` profitiert davon **automatisch** — er wird
beim Briefing-Reset mitgelöscht, **ohne Code-Änderung** an `reset()`
selbst. Das ist beabsichtigt (T5: „nach einem Briefing ist der
Informationsstand neu gesetzt, ein alter Nowcast-Eintrag darf eine
spätere amtliche Warnung nicht mehr unterdrücken"). Die einzige Änderung
an `alert_state.py` ist ein **Docstring-Zusatz** bei `reset()`, der diese
Wechselwirkung ausdrücklich festhält — sonst könnte ein künftiger Umbau,
der einen zweiten Präfix „aus Symmetrie" schont, dieses Verhalten
versehentlich umdrehen. AC-14 sichert das explizit mit einem eigenen Test
ab, nicht nur mit dem Docstring.

### Beobachtbarkeit (T6) — bewusste Erweiterung ggü. S4a E3

`append_suppressed_entry()` (`alert_log.py:253-326`) ist heute laut
Docstring „ausschließlich die beiden Nowcast-Pfade". Diese Scheibe
erweitert das **gezielt** um die Ereignis-Identität-Unterdrückung im
amtlichen Pfad — aber **nur** dafür, nicht für Ruhezeit/Tageslimit. Das
bleibt exakt die S4a-E3-Invariante: der bestehende Wächter
`test_ac9_amtlicher_alarm_bekommt_keinen_unterdrueckungs_grund` bleibt
für Ruhezeit/Tageslimit unverändert grün (AC-16 grenzt das ausdrücklich
ab). Neuer Aufruf im amtlichen Pfad:

```python
alert_log.append_suppressed_entry(
    self._user_id, entity_id=trip.id, entity_type="trip",
    reason=alert_log.REASON_OFFICIAL_ALERT,
    gate_reason=alert_log.REASON_EVENT_DUPLICATE,
    effective_channels=effective_channels,
)
```

Begründung (T6): hier fallen bewusst Meldungen weg — ohne Protokoll-Spur
kann niemand nachweisen, dass die Entdopplung korrekt statt fehlerhaft
arbeitet, und ein Fehler in genau dieser Funktion ist per Definition
unsichtbar („Alarm bleibt aus" hinterlässt sonst keine Spur).

### T7 — Der bestehende Doppel-Alert-Guard bleibt unverändert bestehen

`trip_alert.py:1081-1099` (aus #818 AC-4) prüft Nowcast gegen den
Δ-Zustand desselben Trips (`precip:<segment_id>`,
`thunder_level_max:<segment_id>` — vom **Änderungsalarm** geschrieben).
Das ist eine **andere Paarung** als diese Scheibe: S4b-1 verdoppelt
ausschließlich Nowcast↔amtlich; der Änderungsalarm-Pfad
(`check_and_send_alerts()`, `:171`) wird von dieser Scheibe nicht
angefasst (Δ als dritte Richtung ist S4b-3, optional, s. Nicht-Ziele).
Der Doppel-Alert-Guard ist also weiterhin der **einzige** Schutz gegen
Nowcast↔Δ-Dubletten und bleibt deshalb unverändert bestehen — zwei
Mechanismen nebeneinander sind hier richtig, weil sie unterschiedliche
Paarungen abdecken, nicht dieselbe zweimal (AC-13 sichert das als
Regression ab, damit ein künftiges Aufräumen ihn nicht versehentlich für
„redundant" hält und entfernt).

## Invarianten

- **Der gefährlichste Fehler ist der ausbleibende Alarm.** Jede
  Unsicherheit (fehlender Zeitbezug, fehlende Ortskennung, unbekannte
  Gefahrenart, unbekanntes/altes Registerformat) entscheidet fail-soft
  Richtung Zustellung.
- **Die Eskalationsprüfung (V2) ist strukturell der erste Zweig** nach dem
  Auffinden eines Kandidaten — vor der V1-Ausnahme, vor der Unterdrückung.
- **Kanalübergreifend (V3):** der Gate-Aufruf steht vor
  `split_by_threshold()`, nicht danach und nicht je Kanal.
- **Ereignis-Identität ist die letzte Stufe** an beiden Aufrufstellen —
  nach allen bestehenden billigeren Prüfungen.
- **Die amtliche Eskalation bleibt cooldown-frei** (S4a AC-3): der neue
  Gate-Aufruf fügt eine Prüfung NACH `check_official_alert_gate` hinzu,
  ändert aber nicht dessen Signatur — kein Cooldown-Parameter wandert
  durch die Hintertür zurück.
- **Register-Schreiben ausschließlich nach erfolgreicher Zustellung**
  (F001-Symmetrie, wie `record_nowcast_sent`).
- **Der Doppel-Alert-Guard (`trip_alert.py:1081-1099`) bleibt unverändert**
  — andere Paarung (Nowcast↔Δ statt Nowcast↔amtlich).
- **`append_suppressed_entry` wird im amtlichen Pfad NUR für
  `REASON_EVENT_DUPLICATE` aufgerufen**, nicht für Ruhezeit/Tageslimit
  (S4a E3 bleibt für diese beiden Gründe unverändert gültig).
- Mandantentrennung: jeder Teil mit ZWEI verschiedenen Nutzern verifiziert,
  `user_id` nie auf `"default"` zurückfallen lassen.
- Bestandsdaten: Read-Modify-Write mit Merge, nie Replace; ein Register-
  Eintrag in unbekanntem/altem Format führt nie zu einer Unterdrückung.
- Datenbeschaffung wird NICHT fusioniert — Nowcast und amtliche Quellen
  bleiben technisch eigenständige Abrufe.
- Testpolitik: kein Mock-Theater, keine Dateiinhalt-Checks als
  Verhaltensnachweis.
- Testdateien nach VERHALTEN benennen, nie nach Issue-Nummer.

## Nicht-Ziele (ausdrücklich)

- **Ortsvergleich-Parität (S4b-2, eigenes Folge-Issue).** Der Baustein
  wird entitätsparametrisiert gebaut, aber `compare_radar_alert.py` und
  `compare_official_alert.py` werden von dieser Scheibe **nicht**
  angefasst.
- **Änderungsalarm als dritte Prüfrichtung (S4b-3, optional).** Der
  bestehende Doppel-Alert-Guard bleibt die einzige Absicherung für
  Nowcast↔Δ; eine echte Ereignis-Identität-Integration des
  Änderungsalarms ist eine eigene Scheibe.
- **Weitere Gefahrenarten über den `wet`-Kanon hinaus** (S4b-3, optional) —
  Wind, Hitze, Kälte, Schnee, Glatteis, Waldbrand, Zugangssperre.
- **Amtlich-gegen-amtlich bleibt vollständig bei
  `dedupe_official_alerts`/`official_alert_revision_verdict`.** Diese
  Scheibe fügt dort keine zweite Dedup-Ebene ein.
- **Datenbeschaffung wird nicht fusioniert.**
- **`region_label` wird nicht als Ortsbezug verwendet** — Freitext einer
  fremden Geografie, keine Gleichsetzung mit Segment-IDs.
- Kein neuer Go-Endpunkt, kein neuer Cron-Job, kein Frontend-Code.

## Reihenfolge der Arbeit

1. `resolve_hazard_class`, `alert_urgency.exceeds`, `_covered_until`,
   `_find_matching_entry` als reine Funktionen zuerst, isoliert getestet
   (alle drei Zeitvergleichsfälle, auch die zwei nicht end-to-end
   erreichbaren).
2. `check_event_identity_gate` + `record_event_identity` zusammenbauen,
   Register-Schema fixieren.
3. **Nowcast-Pfad zuerst** verdrahten (Regressionstest: Kernfall
   Nowcast→amtlich, 8,2 Min Abstand, amtlich wird unterdrückt).
4. **Amtlicher Pfad** verdrahten inkl. Batch-Filterung (Regressionstest:
   umgekehrte Reihenfolge amtlich→Nowcast, PLUS der Teilunterdrückung-Fall
   mit zwei Hazards im selben Lauf).
5. V1-Ausnahme (Zeitfenster-Erweiterung) und V2 (Eskalation) je mit
   eigenem Mutations-Gegenprobe-Test.
6. Reset-Regressionstest (AC-14), Mandantentrennung (AC-18), Doppel-
   Alert-Guard-Regression (AC-13) zuletzt, wenn das Verhalten feststeht.
7. ADR-Nachtrag zuletzt.

## Risiken

| | Risiko (aus Nutzersicht) | Gegenmittel |
|---|---|---|
| **R-A** | Batch-Filterung falsch verdrahtet: ein echter zweiter Alarm im selben Lauf wird mit der Dublette zusammen verschluckt. | Eigener AC-17-Test mit ZWEI verschiedenen Hazards im selben Lauf, einer davon Duplikat. |
| **R-B** | Eskalationsprüfung fällt bei einem Refactor an den falschen Platz (nach statt vor der V1-Ausnahme) und eine echte Verschärfung bleibt aus. | Mutations-Gegenprobe PFLICHT (AC-10, Gegenprobe-Unterpunkt). |
| **R-C** | Ein künftiger Umbau von `alert_state.reset()` schont den neuen Präfix „aus Symmetrie zu `official_alert:`" und die Entdopplung wirkt über Briefings hinweg fälschlich fort. | AC-14 mit explizitem Vorher/Nachher-Test, Docstring-Verweis in `reset()`. |
| **R-D** | Zwei Mechanismen (Doppel-Alert-Guard + neues Gate) laufen künftig versehentlich gegeneinander oder einer wird für redundant gehalten und entfernt, wodurch Nowcast↔Δ ungeschützt bleibt. | AC-13 als explizite Regression, T7-Begründung in der Spec. |
| **R-E** | Ein leeres/unbekanntes Registerformat (Altdaten, korrupte Datei) wird als Match interpretiert und unterdrückt fälschlich. | AC-19 fail-soft-Test mit kaputtem/fremdem Registereintrag. |

## Wächter, die mitziehen müssen

| Test | Warum |
|---|---|
| `tests/tdd/test_nowcast_suppression_logging.py::test_ac9_amtlicher_alarm_bekommt_keinen_unterdrueckungs_grund` | bleibt für Ruhezeit/Tageslimit unverändert grün (S4a E3) — NICHT anfassen, AC-16 grenzt die Erweiterung sauber ab |
| `tests/tdd/test_alert_gate.py` | bekommt `check_event_identity_gate`-Fälle dazu; bestehende `check_nowcast_gate`/`check_official_alert_gate`-Fälle bleiben unverändert grün |
| `tests/tdd/test_issue_1088_official_alert_triggers.py` | Trip-Amtlich-Auslöser, plus der neue Kernfall-Regressionstest |
| Nowcast-Regressionstests (bestehende Radar-Alert-Suiten) | Doppel-Alert-Guard-Verhalten (T7) muss identisch bleiben |

## Test-Plan

Kern-Schicht (deterministisch, kein Netz), sofern nicht anders vermerkt.

| AC | Datei | Schicht |
|---|---|---|
| AC-1 bis AC-3 (Baustein-Struktur, Register) | `tests/tdd/test_alert_gate.py` (neu, `check_event_identity_gate`) | Kern |
| AC-4 (Gefahrenart-Kanon, Nicht-Kanon-Hazards) | `tests/tdd/test_alert_gate.py` (neu, `resolve_hazard_class`) | Kern |
| AC-4b inkl. Gegenprobe (eine Klasse `wet`, Kreuzprobe konvektiv/nicht-konvektiv) | `tests/tdd/test_alert_gate.py` | Kern |
| AC-5 (Ortsbezug, Bruchstelle) | `tests/tdd/test_alert_gate.py` | Kern |
| AC-6, AC-7 (Zeitfenster Punkt-Intervall, fail-soft) | `tests/tdd/test_alert_gate.py` | Kern |
| AC-8, AC-9 inkl. Gegenprobe (V1 Kernregel + Ausnahme) | `tests/tdd/test_alert_gate.py` | Kern |
| AC-10 inkl. Gegenprobe (V2 Eskalation) | `tests/tdd/test_alert_gate.py` | Kern |
| AC-11 (kanalübergreifend, V3) | `tests/tdd/test_issue_1088_official_alert_triggers.py` (neuer Fall, Aufruf-Reihenfolge) | Kern |
| AC-12 (letzte Stufe, Aufrufreihenfolge) | `tests/tdd/test_issue_1088_official_alert_triggers.py`, Nowcast-Äquivalent | Kern |
| AC-13 (Doppel-Alert-Guard-Regression, T7) | bestehende Radar-Doppel-Alert-Guard-Tests, unverändert + 1 neuer Fall | Kern |
| AC-14 (Reset erfasst neuen Präfix) | `tests/tdd/test_alert_state_reset.py` (Bestand, ergänzt) | Kern |
| AC-15 (Beobachtbarkeit Nowcast) | bestehende Nowcast-Suppression-Log-Tests, ergänzt | Kern |
| AC-16 (Beobachtbarkeit amtlich, Abgrenzung zu S4a E3) | `tests/tdd/test_nowcast_suppression_logging.py` (ergänzt) | Kern |
| AC-17 (Batch-Filterung, Teilunterdrückung) | `tests/tdd/test_issue_1088_official_alert_triggers.py` (neuer Fall) | Kern |
| AC-18 (Mandantentrennung) | `tests/tdd/test_alert_gate.py` (zwei Nutzer-Kontexte) | Kern |
| AC-19 (fail-soft bei unbekanntem Registerformat) | `tests/tdd/test_alert_gate.py` | Kern |
| AC-20 (amtliche Eskalation bleibt cooldown-frei, Regression zu S4a) | `tests/tdd/test_alert_gate.py` (Signatur-Inspektion `check_official_alert_gate` unverändert) | Kern |
| AC-21 (ADR-Nachtrag) | `# doc-compliance-test` bzw. `tests/test_adr_index_drift.py` | Kern |

Live-E2E: keine eigenen Live-Marker-Tests — echte quellenübergreifende
Doppelungen sind nicht auf Bestellung provozierbar. Staging-Nachweis über
gezielt gesetzte Registereinträge (analog S4a: vorbelegte Zustandsdateien),
nicht über „auf ein echtes Gewitter warten".

## Acceptance Criteria

**Baustein-Struktur**

- **AC-1:** Given die neue Funktion `check_event_identity_gate` in
  `src/services/alert_gate.py`, When sowohl der Nowcast-Trip-Pfad
  (`check_radar_alerts`) als auch der amtliche Trip-Pfad
  (`_send_official_alert_only`) je eine Meldung vor dem Versand prüfen,
  Then rufen beide dieselbe Funktion auf — nicht zwei eigene Prüfungen —
  und ihr Rückgabewert ist eine echte `GateResult`-Instanz, nicht nur ein
  Objekt mit gleichnamigen Attributen.
  - Test: Aufrufzähler (Spion) auf `check_event_identity_gate`, mindestens
    1 Aufruf je Pfad und Lauf mit zutreffender Gefahrenklasse; zusätzlich
    `isinstance(ergebnis, GateResult)` auf dem Rückgabewert.

- **AC-2:** Given eine erfolgreich zugestellte Meldung (Nowcast oder
  amtlich), When der Versand abgeschlossen ist, Then legt
  `record_event_identity` genau EINEN Registereintrag unter dem Präfix
  `event_identity:<hazard_class>:` in `AlertStateService` ab, mit
  Gefahrenklasse, Ortskennungen, Zeitbezug, Dringlichkeit und Zeitpunkt.
  - Test: Zustellung simulieren, `AlertStateService.load(entity_id)` nach
    dem Lauf enthält genau einen neuen `event_identity:`-Schlüssel mit
    allen Pflichtfeldern.

- **AC-3:** Given einen fehlgeschlagenen Zustellversuch (kein Kanal
  erreichbar), When der Lauf beendet ist, Then wurde KEIN Registereintrag
  angelegt — Registrierung ausschließlich nach erfolgreicher Zustellung
  (F001-Symmetrie zu `record_nowcast_sent`).
  - Test: alle Kanäle unerreichbar simulieren, Register-Snapshot vor/nach
    dem Lauf identisch.

**Gefahrenart-Kanon (T2)**

- **AC-4:** Given eine amtliche Warnung mit `hazard` außerhalb der Klasse
  `wet` (`"extreme_heat"`, `"wildfire_risk"`, `"access_ban"`,
  `"wind_gust"`, `"snow"`, `"black_ice"`, `"extreme_cold"`) UND einen
  zeitlich/örtlich überlappenden Nowcast-Registereintrag, When
  `check_event_identity_gate` geprüft wird, Then wird die Warnung NICHT
  unterdrückt — `resolve_hazard_class` liefert `None`, die Prüfung greift
  für diese Gefahrenart nie.
  - Test: für jeden der sieben genannten Hazard-Werte einen Fall mit
    künstlich passendem Nowcast-Registereintrag, Zustellung erfolgt in
    allen sieben Fällen.

- **AC-4b:** Given einen registrierten Nowcast-Eintrag mit
  `is_convective=True` (Klasse `wet`), When eine amtliche Warnung mit
  `hazard="rain"` ODER `hazard="flood"` desselben Orts und überlappenden
  Zeitfensters eintrifft, Then wird sie unterdrückt — und ebenso im
  umgekehrten Fall (Nowcast mit `is_convective=False` gegen amtliches
  `thunderstorm`). Die Radar-Einstufung konvektiv/nicht-konvektiv trennt
  KEINE Ereignisse (PO-Entscheid 2026-08-16).
  - Test: vier Fälle über Kreuz — `is_convective` ∈ {True, False} ×
    `hazard` ∈ {`"thunderstorm"`, `"rain"`}, alle vier `allowed=False`.
  - Mutations-Gegenprobe (Pflicht): `resolve_hazard_class` wieder auf zwei
    Klassen aufspalten (`"convective"`/`"precipitation"`) MUSS diesen Test
    rot machen.

**Ortsbezug (T3)**

- **AC-5:** Given zwei Meldungen gleicher Gefahrenklasse und
  überlappenden Zeitfensters, aber deren Segment-Kennungen sich NICHT
  überschneiden (disjunkte Mengen) ODER bei denen eine der beiden
  Kennungen leer/`None` ist, When `check_event_identity_gate` geprüft
  wird, Then entsteht KEIN Match — beide Meldungen werden zugestellt.
  Eine leere Kennung erzeugt in keinem Fall ein Match.
  - Test: (a) disjunkte Segment-Mengen, (b) eine Seite ohne Segment-
    Kennung — beide Fälle liefern `allowed=True`.

**Zeitfenster (T4)**

- **AC-6:** Given den Kernfall dieser Scheibe — einen bereits registrierten
  Nowcast-Eintrag (Gefahrenklasse `wet`, Segment `3`, Onset 14:22 UTC), When
  8,2 Minuten später eine amtliche Warnung derselben Klasse und
  desselben Segments eintrifft, deren Gültigkeitsfenster den Onset-Punkt
  (mit 60-Min-Puffer) überlappt, Then wird die amtliche Warnung
  unterdrückt (Reproduktion des gemessenen Falls `5f534011`,
  2026-08-11).
  - Test: Nowcast-Eintrag vorbelegen, amtliche Warnung 8,2 Min später mit
    überlappendem Fenster auslösen, `allowed=False`,
    `reason=REASON_EVENT_DUPLICATE`.

- **AC-7:** Given eine Meldung ohne vergleichbaren Zeitbezug (fehlendes
  `valid_from`/`valid_to` bei amtlich, fehlender Onset bei Nowcast) ODER
  einen Registereintrag mit unparsbarem Zeitfeld, When
  `check_event_identity_gate` geprüft wird, Then entsteht KEIN Match —
  die Meldung wird zugestellt (fail-soft, gleiche Richtung wie
  `official_alert_revision_verdict`).
  - Test: je ein Fall mit fehlendem Zeitbezug auf jeder Seite,
    `allowed=True` in beiden Fällen.

**V1 — zeitliche Priorität mit Abdeckungs-Vorbehalt**

- **AC-8:** Given eine bereits registrierte Meldung, When eine zweite
  Meldung derselben Klasse/desselben Orts eintrifft, deren Zeitfenster
  vollständig innerhalb des bereits abgedeckten Fensters liegt (keine
  Eskalation, keine wesentliche Erweiterung), Then wird sie unterdrückt.
  - Test: zweite Meldung mit identischer/kleinerer Dringlichkeit und
    Zeitfenster ⊆ bereits abgedecktem Fenster, `allowed=False`.

- **AC-9:** Given eine bereits registrierte Nowcast-Meldung (abgedeckt
  bis Onset+60 Min), When eine amtliche Warnung derselben Klasse/desselben
  Orts eintrifft, deren `valid_to` mehr als 60 Minuten über das bereits
  abgedeckte Ende hinausreicht — auch OHNE höhere Dringlichkeit —, Then
  wird sie zugestellt (neue Information, V1-Ausnahme).
  - Test: Nowcast-Eintrag abgedeckt bis T, amtliche Warnung mit
    `valid_to = T + 90min`, gleiche Dringlichkeit, `allowed=True`.
  - Mutations-Gegenprobe (Pflicht): die Schwelle `NOWCAST_HORIZON_MIN`
    durch eine deutlich größere Zahl ersetzen (z. B. `600`) MUSS diesen
    Test rot machen.

**V2 — Verschärfung durchbricht immer**

- **AC-10:** Given eine bereits registrierte Meldung niedrigerer
  Dringlichkeit (`"MODERATE"`), When eine zweite Meldung derselben
  Klasse/desselben Orts mit HÖHERER Dringlichkeit (`"HIGH"`) eintrifft —
  UNABHÄNGIG davon, ob ihr Zeitfenster das bereits abgedeckte wesentlich
  erweitert oder nicht —, Then wird sie zugestellt.
  - Test: zweite Meldung mit höherer Dringlichkeit UND Zeitfenster
    vollständig innerhalb des abgedeckten Fensters (die V1-Ausnahme
    greift hier NICHT, nur die Eskalation), `allowed=True`.
  - Mutations-Gegenprobe (PFLICHT): den Eskalations-Zweig **entfernen**
    MUSS diesen Test rot machen — das ist die Absicherung gegen die
    gefährlichste Fehlerrichtung „Alarm bleibt aus" bei einer echten
    Verschärfung.
  - **Nachtrag 2026-08-16 (Adversary-Befund, Präzisierung):** Die
    ursprüngliche Fassung verlangte zusätzlich, dass ein **Verschieben**
    des Eskalations-Zweigs hinter die V1-Ausnahme den Test rot macht. Das
    ist bei der gebauten Codeform nicht erfüllbar — und zwar, weil sie
    **stärker** ist als gefordert: V2 und V1 sind zwei unabhängige,
    seiteneffektfreie Ausstiege (`return _ALLOWED`,
    `alert_gate.py:605-609`). Ihre Reihenfolge ist verhaltensgleich, V1
    kann V2 gar nicht überstimmen. Eine Reihenfolge-Abhängigkeit, die man
    testen könnte, existiert nicht mehr. Wird der Baustein später so
    umgebaut, dass einer der beiden Zweige einen Seiteneffekt bekommt,
    lebt die Reihenfolge-Anforderung wieder auf und braucht dann einen
    eigenen Test.

**V3 — kanalübergreifend**

- **AC-11:** Given eine durch `check_event_identity_gate` unterdrückte
  amtliche Warnung, When man die Kanal-Aufteilung
  (`alert_channel_threshold.split_by_threshold`) für diesen Lauf
  betrachtet, Then wird sie für KEINEN Kanal aufgerufen — die
  Entdopplung entscheidet VOR der Kanal-Schwelle, nicht je Kanal danach.
  - Test: Aufrufzähler auf `split_by_threshold`, bleibt bei 0, wenn das
    Gate unterdrückt; wird aufgerufen, wenn das Gate freigibt.

**Reihenfolge**

- **AC-12:** Given beide Trip-Aufrufstellen, When man ihre
  Aufrufreihenfolge zur Laufzeit beobachtet, Then läuft
  `check_event_identity_gate` in beiden Pfaden als LETZTE Stufe —
  Nowcast: nach `check_nowcast_gate`, Briefing-Vergleich UND
  Doppel-Alert-Guard; amtlich: nach `check_official_alert_gate` UND
  `_is_briefing_imminent`.
  - Test: Aufruf-Sequenz-Spionage in beiden Pfaden, ein reiner
    Quellcode-Grep genügt nicht — entscheidend ist die Laufzeit-Reihenfolge.

**T7 — Doppel-Alert-Guard bleibt bestehen**

- **AC-13:** Given einen Trip mit zugestelltem Änderungsalarm (Δ) für
  ein Segment, When innerhalb des Cooldowns ein Nowcast-Alarm für
  dasselbe Segment/dieselbe Gefahrenart ansteht, Then bleibt er weiterhin
  durch den bestehenden Doppel-Alert-Guard (`trip_alert.py:1081-1099`)
  unterdrückt — unverändert gegenüber vor dieser Scheibe, unabhängig vom
  neuen `check_event_identity_gate`.
  - Test: bestehende Doppel-Alert-Guard-Fälle unverändert grün ausführen;
    zusätzlich ein Fall, der zeigt, dass das neue Gate hierfür gar nicht
    zuständig ist (kein Registereintrag für Δ-Alarme).

**Register-Reset (T5)**

- **AC-14:** Given einen Trip mit einem `event_identity:`-Registereintrag
  UND einem `official_alert:`-Eintrag, When
  `AlertStateService.reset(entity_id)` beim Briefing-Versand läuft, Then
  ist der `event_identity:`-Eintrag danach verschwunden, der
  `official_alert:`-Eintrag bleibt unverändert erhalten (bestehendes
  Verhalten aus #1460).
  - Test: beide Eintragstypen vorbelegen, `reset()` aufrufen, Datei danach
    enthält nur noch den `official_alert:`-Schlüssel.

**Beobachtbarkeit (T6)**

- **AC-15:** Given eine durch `check_event_identity_gate` unterdrückte
  Nowcast-Meldung, When der Lauf beendet ist, Then enthält
  `alert_log.json` (`not_delivered`) genau einen Eintrag mit
  `reason=REASON_NOWCAST` und `gate_reason=REASON_EVENT_DUPLICATE`.
  - Test: Unterdrückung erzwingen, Protokoll-Eintrag prüfen.

- **AC-16:** Given eine durch `check_event_identity_gate` unterdrückte
  amtliche Warnung, When der Lauf beendet ist, Then enthält
  `alert_log.json` (`not_delivered`) genau einen Eintrag mit
  `reason=REASON_OFFICIAL_ALERT` und `gate_reason=REASON_EVENT_DUPLICATE`
  — UND: eine durch Ruhezeit oder Tageslimit (nicht durch
  Ereignis-Identität) unterdrückte amtliche Warnung erzeugt weiterhin
  KEINEN Protokoll-Eintrag (S4a E3 bleibt für diese beiden Gründe
  unverändert gültig).
  - Test: zwei Fälle im selben Testmodul — (a) Ereignis-Identität-
    Unterdrückung erzeugt einen Eintrag, (b) Ruhezeit-Unterdrückung
    erzeugt keinen; bestehender S4a-Wächter bleibt zusätzlich unverändert
    grün.

**Batch-Filterung (Bruchstelle)**

- **AC-17:** Given einen Lauf mit zwei amtlichen Warnungen für denselben
  Trip — eine davon ein Duplikat eines bereits registrierten
  Nowcast-Ereignisses (`thunderstorm` → Klasse `wet`), die andere eine
  eigenständige Warnung anderer Gefahrenart (`extreme_heat`, keine
  Klasse) —, When `_send_official_alert_only` läuft, Then wird NUR die
  duplizierte Warnung unterdrückt, die andere wird zugestellt — beide in
  getrennter Betrachtung, nicht als Alles-oder-Nichts-Entscheidung über
  den ganzen Lauf.
  - Test: beide Warnungen im selben Lauf auslösen, zugestellte Nachricht
    enthält ausschließlich `extreme_heat`, Protokoll zeigt einen
    `not_delivered`-Eintrag für `thunderstorm`.

**Mandantentrennung**

- **AC-18:** Given zwei verschiedene Nutzer mit je einem Trip gleicher
  Kennung, deren Registereinträge unabhängig geführt werden, When Nutzer
  A einen Nowcast-Eintrag registriert und Nutzer B unabhängig davon eine
  amtliche Warnung derselben Klasse/desselben Segments auslöst, Then
  wirkt A's Registereintrag NICHT auf B — B erhält seine Warnung, ohne
  Rückfall auf `"default"`.
  - Test: zwei Datenverzeichnisse (`user_id` A/B), gleiche Trip-Kennung,
    A registriert, B's amtliche Warnung geht trotzdem durch.

**Bestandsdaten / fail-soft**

- **AC-19:** Given einen Registereintrag mit unbekanntem/kaputtem Format
  (fehlendes `severity`-Feld, unparsbares Zeitfeld, aus einer künftigen
  Schema-Version), When `check_event_identity_gate` diesen Eintrag als
  Kandidat prüft, Then wird er wie „kein Match" behandelt — die neue
  Meldung wird zugestellt, kein Absturz.
  - Test: Registereintrag mit fehlenden/kaputten Feldern vorbelegen,
    neue Meldung auslösen, `allowed=True`, kein Exception-Durchbruch.

**Regression zu S4a**

- **AC-20:** Given die Funktionssignatur von `check_official_alert_gate`
  nach Abschluss dieser Scheibe, When man sie inspiziert, Then ist sie
  UNVERÄNDERT gegenüber S4a — kein Cooldown-/Sperrzeit-Parameter wurde
  nachträglich ergänzt. Die neue Ereignis-Identität-Prüfung ist ein
  EIGENER, nachgelagerter Aufruf, keine Erweiterung des Gates selbst.
  - Test: `inspect.signature(check_official_alert_gate)` unverändert
    gegenüber dem S4a-Stand (Diff der Parameterliste ist leer).

**Dokumentation**

- **AC-21:** Given den ADR-0021-Nachtrag aus S4a (#1467), When diese
  Scheibe abgeschlossen ist, Then trägt ADR-0021 einen weiteren,
  datierten Nachtrag mit Bezug auf „#1467" und „S4b", der festhält, dass
  seit dieser Scheibe eine quellenübergreifende Ereignis-Identität-Prüfung
  als letzte, gemeinsame Stufe für Nowcast und amtliche Trip-Alarme
  existiert — ohne die S4a-Aussage zur Unterdrückungs-Protokollierung zu
  widerrufen (die gilt weiterhin für Ruhezeit/Tageslimit, s. AC-16).
  - Test: `# doc-compliance-test` — ADR-0021 enthält nach Abschluss einen
    Nachtrag-Absatz mit Bezug auf „#1467" und „S4b", datiert nach dem
    2026-08-16.

## Known Limitations

- **Ein stratiformer Landregen-Nowcast kann von einer amtlichen
  Gewitterwarnung unterdrückt werden** (und umgekehrt), weil der Kanon
  beide zur Klasse `wet` zählt. Bewusster PO-Entscheid 2026-08-16: die
  Radar-Einstufung konvektiv/nicht-konvektiv ist eine Momentaufnahme der
  Zelle, kein Ereignis-Unterscheidungsmerkmal (Messung s. Implementation
  Details). Die Trennschärfe liegt bei Ort, Zeitfenster und den beiden
  Ausnahmen V1/V2.
- **Punkt-gegen-Punkt und Intervall-gegen-Intervall bleiben in dieser
  Scheibe isoliert getestet, nicht end-to-end verdrahtet** — über die
  beiden Trip-Aufrufstellen ist nur Punkt-gegen-Intervall real
  erreichbar. S4b-2/S4b-3 könnten das ändern.
- **Ortsvergleich bleibt vollständig außerhalb dieser Scheibe** — der
  Baustein ist entitätsparametrisiert vorbereitet, aber nicht verdrahtet
  (S4b-2).
- **Änderungsalarm (Δ) als dritte Prüfrichtung bleibt offen** (S4b-3,
  optional) — der bestehende, weniger generische Doppel-Alert-Guard
  bleibt die einzige Absicherung für diese Paarung.
- **Ein Rückbau des Bausteins (Baustein → wieder getrennte Prüfungen) ist
  mit Verhaltenstests grundsätzlich nicht vollständig fangbar** — der
  strukturelle Schutz liegt teilweise außerhalb dieser Spec (Code-Review).

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine neue — ADR-0021 (geteilter Auswertungskern) bekommt
  einen weiteren Nachtrag, im Anschluss an den S4a-Nachtrag.
- **Rationale:** Die quellenübergreifende Ereignis-Identität-Prüfung ist
  konsequente Fortsetzung des in ADR-0021 etablierten Musters — ein
  geteilter Baustein statt N eigenständiger Prüfketten je Quelle. Neu
  ggü. S3/S4a ist, dass der Baustein hier erstmals **quellenübergreifend**
  vergleicht (nicht nur je Quelle dieselbe Prüfkette anwendet), und dafür
  ein eigenes, wenn auch kleines, Datenmodell (das Ereignis-Identität-
  Register) einführt — kein neues Architekturprinzip, aber ein neuer
  Baustein-Typ innerhalb des bestehenden Prinzips.

## Changelog

- 2026-08-16: Initiale Spec. V1–V3 (fachlich) und T1–T7 (technisch) nach
  PO-Vorgabe vom 2026-08-16 (`docs/context/rework-1467-s4b-entdopplung.md`)
  zugeschnitten. Gefahrenart-Kanon und Ortsbezug-Aufwand gegen den
  tatsächlichen Code verifiziert (Ortsbezug ist billiger als in der
  ursprünglichen Risiko-Einschätzung angenommen, kein neues Datenmodell
  nötig). Zeilenangaben gegen `origin/main` @ `5ddb46e7`, verifiziert.
