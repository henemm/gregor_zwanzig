---
entity_id: fix_2020_alarm_ausloesung
type: module
created: 2026-08-21
updated: 2026-08-21
status: draft
version: "1.0"
tags: [alarm, nowcast, radar, briefing-sperre]
---

# Auslösung des Regen-Alarms — Nowcast-Sperre bricht bei Überholung (#2020, Scheibe 1)

## Approval

- [ ] Approved

## Purpose

Der Radar-Nowcast-Alarm eines Trips bleibt heute stumm, sobald das Morgen-Briefing für die
Onset-Stunde irgendeinen Regenwert ≥ 0,5 mm genannt hat — unabhängig davon, wie stark die
aktuelle Vorhersage diesen Wert inzwischen übersteigt. Am 2026-08-20 waren für den KHW-Trip
403 7,4 mm angekündigt, tatsächlich fielen 33,1 mm (Tagessumme); die Sperre hat den
Nowcast-Alarm bis 15:30 zurückgehalten, obwohl der erste schwere Guss bereits um 13:00 fiel.
Diese Spec ersetzt die binäre Sperre („wurde überhaupt etwas angekündigt?") durch eine
Überholungs-Prüfung („übersteigt die aktuelle Vorhersage die Ankündigung deutlich genug, um
eine neue Warnung wert zu sein?") und macht jede verbleibende Unterdrückung an dieser Stelle
erstmals im Alarm-Protokoll sichtbar.

## Source

- **File:** `src/services/trip_alert.py`
- **Identifier:** `TripAlertService.check_radar_alerts()`, Bezeichner `_briefing_announced` /
  `_briefing_precip_for_onset()` (Zeilennummern verschoben, nicht als Anker verwenden)
- **Nebenschauplatz:** `src/services/radar_service.py` — `NowcastResult`, `_derive_result()`,
  `intensity_to_text()`

> Schicht-Hinweis geprüft: Alle betroffenen Symbole liegen in `src/services/` (Python-Core,
> Domain-Backend). Keine Go-API-, Frontend- oder CLI-Berührung.

## Estimated Scope

- **LoC:** ~140 (nach Review-Korrektur; Mengen-Akkumulation statt reinem Raten-Vergleich
  braucht zusätzliche ~20 Zeilen in `_derive_result()`) — weiterhin deutlich unter dem
  250er-Limit
- **Files:** 4
- **Effort:** medium

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `radar_service.NowcastResult` | Datenklasse | trägt künftig zwei neue Felder: `window_precip_mm` (akkumulierte Menge in der ersten Stunde ab jetzt — der Wert für den Faktor-Vergleich gegen `_briefing_precip`) und `max_rate_mm_h` (Spitzenrate **im selben 60-Min-Vergleichsfenster wie `window_precip_mm`**, korrigiert nach Fix-Loop-Fund F001 — nur noch die Untergrenze „ist das überhaupt Starkregen") (siehe Vorbedingungs-Prüfung unten, revidiert) |
| `radar_service.HEAVY_RAIN_THRESHOLD_MM_H` (neu, extrahierte Konstante) | Schwelle | Relevanzfilter (Untergrenze auf `max_rate_mm_h`) der Überholungsregel; dieselbe Zahl, die `intensity_to_text()` bereits für „Starker Regen" nutzt — keine zweite, unabhängige Zahl |
| `alert_log.append_suppressed_entry()` | Funktion (bereits vorhanden, unverändert) | dritter Aufruf im Nowcast-Pfad; Signatur und Verhalten bleiben wie für die beiden bestehenden Aufrufe in `check_radar_alerts()` |
| `alert_log.REASON_NOWCAST` | Konstante (bereits vorhanden) | `reason`-Wert für den neuen Protokoll-Eintrag |

## 🔴 Vorbedingungs-Prüfung (im Code verifiziert, nicht angenommen)

**Revidiert nach Review (Team-Lead-Fund 2026-08-21):** Punkt 1/2 der Erstfassung hatten
einen Designfehler — Spitzenrate (mm/h) gegen Stundenmenge (mm) zu vergleichen kann in
beide Richtungen falsch liegen: ein kurzer, kräftiger Schauer (hohe Spitzenrate, wenig
Gesamtmenge) hätte fälschlich die Sperre gebrochen; ein langer, mäßiger Landregen (niedrige
Spitzenrate, viel Gesamtmenge) hätte sie fälschlich gehalten. Durchgerechnet: Briefing
kündigt 2,0 mm an, ein 10-Minuten-Schauer mit 4,5 mm/h Spitze bringt real nur ≈ 0,75 mm —
die alte Regel (`max_rate_mm_h >= 2× UND >= 4,0`) hätte trotzdem ausgelöst, obwohl die
Wirklichkeit die Ankündigung UNTERSCHREITET. Korrigiert unten: Menge gegen Menge, Rate
bleibt nur noch die Relevanz-Untergrenze.

1. **Es gibt heute KEINEN direkten Zahlenwert im `result`-Objekt, um die aktuelle
   Regenmenge mit `_briefing_precip` zu vergleichen.** `NowcastResult` (Rückgabetyp von
   `get_nowcast()`) trägt nur `intensity_label` (String) und `frames` (Liste ungefilterter
   `RadarFrame`, je mit `precip_mm_h` und `timestamp`). Weder eine akkumulierte Menge noch
   der Spitzenwert (`max_rate`, in `_derive_result()` bereits berechnet, aber verworfen)
   landen im Ergebnis. **Kein Blocker**, additive Erweiterung: `NowcastResult` bekommt zwei
   neue Felder, `max_rate_mm_h: float = 0.0` (Untergrenzen-Check) und
   `window_precip_mm: float = 0.0` (Mengen-Check, neu berechnet — siehe Implementation
   Details). Kein Verhaltensrisiko für bestehende Aufrufer (alle Konstruktions-Stellen in
   Produktions- und Testcode nutzen Keyword-Argumente; neue Felder mit Default brechen
   nichts).

   **Korrektur einer eigenen Fehleinschätzung:** Das Nowcast-**Fenster**, aus dem
   `max_rate`/`onset_minutes`/`intensity_label` abgeleitet werden, ist **180 Minuten**
   (`_NOWCAST_HORIZON_MIN = 180`, `radar_service.py`), nicht ~55–60 Minuten wie in der
   Erstfassung behauptet — das war eine Verwechslung mit `RADAR_ONSET_THRESHOLD_MIN = 55`,
   einer andersartigen Schwelle (gate für „ist der Onset noch nah genug dran", nur in
   `radar_alert_due()` verwendet). Für die Überholungsregel wird deshalb ein **eigenes,
   auf eine Stunde begrenztes Vergleichsfenster** eingeführt (siehe Implementation Details)
   statt des 180-Minuten-Fensters — sonst würde ein Drei-Stunden-Wert gegen einen
   Ein-Stunden-Wert aus dem Briefing verglichen.

   **Frame-Raster geprüft, nicht angenommen.** Es ist **nicht einheitlich**: RADOLAN
   (`providers/brightsky.py`, Feld `precipitation_5`) liefert 5-Minuten-Schritte; alle
   anderen Produktivquellen (INCA, AROME-FR, ICON-D2, ARPAE, der globale `minutely_15`-
   Fallback) laufen über `_fetch_openmeteo_15()` mit 15-Minuten-Schritten. `RadarFrame`
   selbst trägt keine Dauer, nur `timestamp` und `precip_mm_h`. Die Mengen-Berechnung MUSS
   die Dauer je Frame aus den tatsächlichen aufeinanderfolgenden Zeitstempeln ableiten,
   nicht als feste Kadenz annehmen — sonst wäre die Menge für RADOLAN-Gebiete (u. a. Teile
   Deutschlands) strukturell falsch (3× zu hoch, würde man 15 Minuten annehmen).

2. **Einheiten-Falle — jetzt durch Mengen-Vergleich statt Raten-Vergleich aufgelöst.**
   `_briefing_precip_for_onset()` liefert `precip_1h_mm` — eine Modell-**Akkumulation**
   für die Onset-Stunde. Das neue `window_precip_mm` ist ebenfalls eine Akkumulation
   (Summe aus `precip_mm_h × Dauer_h` je Frame im Ein-Stunden-Vergleichsfenster) — gleiche
   physikalische Größe, gleiche Zeitbasis-Länge. **Bleibt eine Näherung, aber eine
   konservative:** Das Vergleichsfenster beginnt bei „jetzt", nicht notwendig exakt an der
   Uhrstunden-Grenze, die das Briefing für `precip_1h_mm` nutzt, und es wird nie über
   fehlende Frames hinaus hochgerechnet — eine unvollständige Datenlage macht die Regel
   eher zurückhaltender, nie alarmfreudiger (bewusste Richtung, siehe Known Limitations).
   `max_rate_mm_h` bleibt bestehen, dient aber nur noch als Relevanz-Untergrenze („ist das
   überhaupt Starkregen"), nicht mehr für den Faktor-Vergleich. **Fix-Loop-Korrektur (Fund
   F001, 2026-08-21):** `max_rate_mm_h` wird — wie `window_precip_mm` — aus dem 60-Min-
   Vergleichsfenster gebildet, nicht aus dem 180-Min-Nowcast-Fenster. Ein Spitzenwert aus
   dem größeren Fenster hätte einen späten, unabhängigen Starkregen-Ausbruch (z. B. bei
   +150 Min) als Untergrenzen-Beleg für ganz anderen, schwachen Nahregen zugelassen —
   genau das Gegenteil der hier beschriebenen Absicht, dass Rate und Menge dasselbe
   Ereignis beschreiben. Der lokale `max_rate` aus dem 180-Min-Fenster bleibt unverändert
   für `intensity_label` (reine Anzeige) erhalten.

3. **`#883` (konvektiver Sicherheits-Override) ist KEIN ADR.** `grep -rl "883"
   docs/adr/` liefert keinen Treffer. Die Entscheidung ist ausschließlich als
   Issue/Epic-Slice dokumentiert (`docs/features/issue-816-alert-deviation-core.md`:
   „Slice 4: Konvektiver Sicherheits-Override (#883)"). Diese Spec **erweitert** die
   Bedingung, die die Sperre durchbricht, um eine zweite, unabhängige Bedingung
   (Überholung) — sie ersetzt und widerruft die konvektive Bedingung nicht (AC-5 sichert
   das als Regressionsschutz ab). Kein ADR nötig; Begründung im ADR-Abschnitt unten.

**Kein Blocker gefunden.** Die Implementierung kann wie unten beschrieben umgesetzt werden.

## Implementation Details

```
# src/services/radar_service.py — Konstante extrahieren (Wiederverwendung statt neuer Zahl)
HEAVY_RAIN_THRESHOLD_MM_H = 4.0   # war Inline-Literal in intensity_to_text()

def intensity_to_text(...):
    ...
    if mm_per_h < HEAVY_RAIN_THRESHOLD_MM_H:
        return INTENSITY_MODERATE
    return INTENSITY_HEAVY

# NowcastResult: zwei neue Felder, Default = 0.0, additiv
@dataclass
class NowcastResult:
    ...
    data_unavailable: bool = False
    max_rate_mm_h: float = 0.0      # NEU (#2020): Spitzenrate im 180-Min-Fenster —
                                     # nur noch Relevanz-Untergrenze, kein Faktor-Vergleich
    window_precip_mm: float = 0.0   # NEU (#2020): akkumulierte Menge in der ERSTEN STUNDE
                                     # ab jetzt — vergleichbar mit precip_1h_mm im Briefing

# _derive_result(): max_rate wie bisher, ZUSAETZLICH ein eigenes 60-Min-Fenster fuer
# die Mengen-Akkumulation (NICHT das 180-Min-Fenster oben — das waere ein 3h-Wert
# gegen einen 1h-Briefingwert).
compare_horizon = now + timedelta(minutes=60)
compare_window = sorted(
    (f for f in frames if f.timestamp >= now and f.timestamp < compare_horizon),
    key=lambda f: f.timestamp,
)
window_precip_mm = 0.0
for i, frame in enumerate(compare_window):
    # Dauer JE FRAME-PAAR aus echten Zeitstempeln -- nicht als feste Kadenz
    # angenommen (RADOLAN 5 Min, alle anderen Quellen 15 Min, s. o.).
    next_ts = (
        compare_window[i + 1].timestamp if i + 1 < len(compare_window)
        else compare_horizon
    )
    duration_h = max(0.0, (next_ts - frame.timestamp).total_seconds() / 3600.0)
    window_precip_mm += frame.precip_mm_h * duration_h

return NowcastResult(
    ...,
    data_unavailable=data_unavailable,
    max_rate_mm_h=max_rate,
    window_precip_mm=window_precip_mm,
)
```

**Als implementiert (weicht vom vereinfachten Pseudocode oben ab, Fix-Loop-Funde F001–F002
(Runde 1) und F006–F007 (Runde 2), 2026-08-21):**

- `max_rate_mm_h` im `NowcastResult` stammt aus `compare_window` (60 Min), nicht aus dem
  180-Min-`window` oben — Begründung siehe Vorbedingungs-Prüfung Punkt 2 (Fix-Loop-
  Korrektur F001). Der lokale `max_rate` bleibt für `intensity_label` unverändert.
- Die Dauer je Frame wird **nicht** aus einer global über die volle Frame-Liste
  abgeleiteten Kadenz bestimmt (weder Minimum noch Median — beide Ansätze wurden
  implementiert und beide vom Adversary gebrochen, siehe Fix-Loop-Historie unten), sondern
  ausschließlich aus der **unmittelbaren Nachbarschaft** des jeweiligen Frames in der
  vollständigen, zeitlich sortierten Frame-Liste, zusätzlich gedeckelt durch eine feste
  Modul-Konstante:
  ```
  _MAX_FRAME_COVERAGE = timedelta(minutes=15)   # groebstes Produktivraster (INCA,
                                                 # AROME-FR, ICON-D2, ARPAE, minutely_15);
                                                 # RADOLAN liefert 5 Minuten.
  frame_end = min(
      naechster_frame_zeitstempel_in_der_vollstaendigen_liste,
      frame.timestamp + _MAX_FRAME_COVERAGE,
      compare_horizon,
  )
  ```
  Kein Wert außerhalb der unmittelbaren Nachbarschaft eines Frames kann dessen Deckung
  noch beeinflussen — weder ein ferner Ausreißer-Abstand (F002/F003, Runde 1) noch eine
  Mehrheit ferner, trockener Frames, die eine globale Kennzahl nach oben ziehen (F006,
  Runde 2). `_infer_frame_cadence()` (Median-Ansatz, Runde 1) entfällt ersatzlos, ebenso
  ihr ungetesteter 5-Minuten-Rückfallwert bei weniger als zwei unterscheidbaren
  Zeitstempeln (F007, Runde 2) — der ist mit der Funktion gegenstandslos, weil die feste
  Obergrenze `_MAX_FRAME_COVERAGE` diesen Fall jetzt strukturell mitabdeckt (ein isolierter
  Einzel-Frame wird auf höchstens 15 Minuten Deckung begrenzt, nie auf das Fensterende
  hochgerechnet).

```
# src/services/trip_alert.py — check_radar_alerts(), Ersatz der binaeren Sperre
# Modul-Konstante (analog RADAR_ONSET_THRESHOLD_MIN-Muster, #2009/ADR-0021):
_BRIEFING_OVERTAKE_FACTOR = 2.0

_briefing_announced = (_briefing_precip is not None and _briefing_precip >= 0.5)

# #2020 A3: Ueberholungs-Pruefung statt binaerer Sperre. Menge gegen Menge
# (window_precip_mm vs. _briefing_precip), Rate nur als Relevanz-Untergrenze
# (max_rate_mm_h). UND-Verknuepfung (nicht ODER) haelt die Regel fuer festen
# _briefing_precip monoton in beiden Groessen (AC-3).
_overtaking = (
    _briefing_announced
    and result.window_precip_mm >= _briefing_precip * _BRIEFING_OVERTAKE_FACTOR
    and result.max_rate_mm_h >= radar_service_mod.HEAVY_RAIN_THRESHOLD_MM_H
)
if _briefing_announced and not result.is_convective and not _overtaking:
    logger.debug(f"Radar alert suppressed: briefing had {_briefing_precip} mm for {trip.id}")
    try:
        alert_log.append_suppressed_entry(
            self._user_id, entity_id=trip.id, entity_type="trip",
            reason=alert_log.REASON_NOWCAST,
            gate_reason=f"briefing_announced:{_briefing_precip}mm",
            effective_channels=effective_channels,
        )
    except Exception as e:
        logger.error(
            "Radar alert: Unterdrueckungs-Protokoll (Briefing-Ankuendigung) fuer "
            "Trip %s fehlgeschlagen (%s) — der Alarm blieb aus, nur der "
            "Protokoll-Eintrag fehlt.", trip.id, e,
        )
    continue
```

Die bestehende Konvektions-Bedingung (`_briefing_announced and not result.is_convective`)
bleibt als Fallback unverändert erhalten — sie wird nur um `and not _overtaking` ergänzt,
nicht ersetzt. `_briefing_context`-Textzuordnung (Zeilen darunter) bleibt unverändert; siehe
Known Limitations zur Wortlaut-Grenze dieser Scheibe.

## Expected Behavior

- **Input:** Briefing-Ankündigung `_briefing_precip` (mm, Onset-Stunde) und aktueller
  Nowcast `result.window_precip_mm` (mm, akkumuliert in der ersten Stunde ab jetzt) sowie
  `result.max_rate_mm_h` (mm/h, Spitzenwert) für dasselbe Segment.
- **Output:** Die Briefing-Sperre bricht (Alarm wird ausgewertet und ggf. versendet), wenn
  `window_precip_mm >= 2 × _briefing_precip` UND `max_rate_mm_h >= HEAVY_RAIN_THRESHOLD_MM_H`
  (4,0 mm/h) — zusätzlich zur bestehenden konvektiven Bedingung. Bleibt die Sperre bestehen,
  entsteht ein `alert_log`-Suppressed-Eintrag mit `reason=REASON_NOWCAST`.
- **Side effects:** Erhöhtes Alarmaufkommen im Nowcast-Pfad (Betrag vorab nicht messbar,
  siehe Analyse-Dokument `docs/context/fix-2020-alarm-ausloesung.md`, Abschnitt
  „Summenwirkung"). Erstmals sichtbare Protokoll-Spur für diese konkrete Unterdrückung.

## Acceptance Criteria

- **AC-1:** Given das Morgen-Briefing hat für die Onset-Stunde eines Segments 1,0 mm
  angekündigt (illustrativer Stundenwert — der reale Stundenwert vom 2026-08-20 ist laut
  Analyse nicht rekonstruierbar, siehe `docs/context/fix-2020-alarm-ausloesung.md`,
  Abschnitt „Datengrenzen"; NICHT die Tagessumme von 7,4 mm verwenden) und der aktuelle
  Radar-Nowcast sagt für dasselbe Segment durchgehend 12 mm/h für die kommende Stunde
  voraus (akkumuliert ≈ 12 mm, Spitzenrate 12 mm/h) / When der 15-Minuten-Prüfzyklus
  (`check_radar_alerts()`) läuft / Then durchbricht der Nowcast die Sperre (12 mm ≥ 2 × 1,0
  mm UND 12 mm/h ≥ 4,0 mm/h) und der Wanderer bekommt einen Alarm, obwohl bereits etwas
  angekündigt war.
  - Test: `check_radar_alerts()` mit injiziertem Nowcast-Ergebnis (DI-Seam
    `frame_source`, mehrere Frames über die volle Stunde) und geladenem
    Briefing-Schnappschuss ausführen; prüfen, dass ein Alarm tatsächlich versendet wird
    (nicht nur, dass die Sperre-Variable stimmt).

- **AC-2 (Menge entscheidet, nicht allein die Rate):** Given dasselbe Briefing (1,0 mm
  angekündigt), der Nowcast erreicht kurzzeitig eine Spitzenrate von 6,0 mm/h (über der
  4,0-mm/h-Untergrenze), fällt aber im restlichen Stundenfenster ab, sodass insgesamt nur
  1,8 mm akkumulieren (unter 2 × 1,0 mm = 2,0 mm) / When derselbe Prüfzyklus läuft / Then
  bleibt die Sperre bestehen (kein Alarm) — die Untergrenze allein reicht nicht, die
  akkumulierte Menge muss den Faktor ebenfalls erfüllen.
  - Test: Gleicher Aufbau wie AC-1 mit abklingender Frame-Serie (hohe Einzelrate, geringe
    Gesamtmenge); prüfen, dass `continue` greift und kein Versand stattfindet.

- **AC-3 (Monotonie):** Given eine Kombination aus `window_precip_mm` und `max_rate_mm_h`,
  die die Sperre für einen festen angekündigten Wert bereits durchbricht (Faktor UND
  Untergrenze erfüllt) / When ein zweiter Nowcast-Lauf für denselben angekündigten Wert
  geprüft wird, bei dem sowohl `window_precip_mm` als auch `max_rate_mm_h` mindestens so
  hoch sind wie im ersten Lauf / Then durchbricht auch der zweite Lauf die Sperre — ein
  mindestens gleich starker oder stärkerer Nowcast führt nie zu einer schwächeren Meldung
  als ein schwächerer.
  - Test: Zwei Läufe mit identischem `_briefing_precip`, Lauf 2 mit
    `window_precip_mm_2 >= window_precip_mm_1` und `max_rate_mm_h_2 >= max_rate_mm_h_1`,
    wobei Lauf 1 bereits auslöst; assert, dass Lauf 2 ebenfalls auslöst (nicht nur die
    Boolesche Zwischenvariable, sondern der tatsächliche Alarm-Versand).

- **AC-4 (Fehlalarm-Wächter — Spitzenrate allein darf NIE auslösen):** Given das
  Morgen-Briefing hat 2,0 mm für die Onset-Stunde angekündigt und der Nowcast zeigt einen
  kurzen, 10-minütigen Schauer mit einer Spitzenrate von 4,5 mm/h (über der 4,0-mm/h-
  Untergrenze), danach bleibt das Stundenfenster trocken, sodass real nur ≈ 0,75 mm
  akkumulieren (weit unter 2 × 2,0 mm = 4,0 mm) / When der Prüfzyklus läuft / Then bleibt
  die Sperre bestehen und es geht KEIN Alarm raus — die tatsächliche Regenmenge unterschreitet
  sogar die Ankündigung, ein Alarm wäre hier objektiv falsch. Dieser Fall MUSS rot werden,
  falls die Implementierung je wieder auf einen reinen Raten-Vergleich zurückgebaut wird.
  - Test: `check_radar_alerts()` mit einem einzelnen kurzen Hochrate-Frame (10 Min, 4,5
    mm/h) gefolgt von trockenen Frames für den Rest der Stunde; assert, dass `continue`
    greift und explizit KEIN Versand stattfindet, obwohl `max_rate_mm_h` allein die
    Untergrenze erfüllt hätte.

- **AC-5 (Konvektiv-Override bleibt unangetastet):** Given eine Situation mit
  `is_convective=True` und einer Briefing-Ankündigung, bei der die Überholungsbedingung
  NICHT erfüllt ist (z. B. Nowcast-Rate unter der 2×-Schwelle) / When der Prüfzyklus läuft
  / Then durchbricht der Alarm die Sperre trotzdem, weil die bestehende konvektive
  Bedingung unverändert als eigenständige Bedingung gilt (#883 bleibt erhalten, wird nicht
  ersetzt).
  - Test: Regressionstest mit `is_convective=True` und niedrigem Überholungsfaktor;
    prüfen, dass der Alarm trotzdem versendet wird.

- **AC-6 (Sichtbarkeit):** Given die Sperre bleibt bestehen (weder Überholung noch
  Konvektion) / When `check_radar_alerts()` durchläuft / Then entsteht ein
  `alert_log`-Eintrag über `append_suppressed_entry()` mit `reason=REASON_NOWCAST` und
  einem `gate_reason`, der die Briefing-Ankündigung als Ursache benennt — die
  Unterdrückung ist danach im Protokoll nachvollziehbar statt nur in `logger.debug`.
  - Test: Nach einem unterdrückten Lauf das Alarm-Protokoll des Nutzers lesen und
    prüfen, dass ein `not_delivered`-Eintrag mit dem erwarteten `reason`/`gate_reason`
    existiert — kein Dateiinhalt-Check, sondern Lesen über die Protokoll-Leseschnittstelle.

- **AC-7 (kein Briefing-Wert):** Given `_briefing_precip_for_onset()` liefert `None` (kein
  Schnappschuss oder keine Daten für die Onset-Stunde) / When der Prüfzyklus läuft / Then
  bleibt das Verhalten unverändert gegenüber heute — `_briefing_announced` ist von
  vornherein `False`, die neue Überholungsprüfung wird gar nicht erst ausgewertet, kein
  neuer Protokoll-Eintrag durch diese Regel.
  - Test: Bestehenden Pfad ohne Schnappschuss durchlaufen lassen; prüfen, dass der Alarm
    wie vor dieser Änderung ausgelöst wird und kein `REASON_NOWCAST`-Suppressed-Eintrag
    für diese Ursache entsteht.

## Known Limitations

- **Wortlaut bleibt Scheibe 2.** `_briefing_context` liefert im Überholungsfall weiterhin
  nur „bereits angekündigt" (nicht „bereits angekündigt — jetzt deutlich mehr" o. Ä.). Die
  Formulierung von Zeitangaben/Kontext-Texten ist ausdrücklich zurückgestellt
  (`docs/specs/modules/fix_2020_alarm_zeitangaben.md`, freigegeben, aber nicht Teil dieser
  Scheibe).
- **Einheiten-Näherung, bewusst konservativ.** `window_precip_mm` akkumuliert ab „jetzt"
  über eine Stunde, `precip_1h_mm` bezieht sich auf die feste Uhrstunde des Briefings —
  beide Fenster überlappen typischerweise stark, sind aber nicht deckungsgleich (siehe
  Vorbedingungs-Prüfung Punkt 2). Die Regel extrapoliert nie über tatsächlich vorhandene
  Frames hinaus: Fehlen Frames am Fensterende (Datenausfall, Drosselung), wird
  `window_precip_mm` eher zu klein als zu groß — die Regel bleibt im Zweifel
  zurückhaltend, nie alarmfreudig. Für den Zweck „ist die reale Menge deutlich größer als
  angekündigt?" ausreichend; keine exakte physikalische Gleichsetzung.
- **Nur der Trip-Radar-Pfad.** `src/services/compare_radar_alert.py` hat keine
  analoge `_briefing_announced`-Sperre (geprüft: kein Treffer für das Muster) — diese
  Scheibe berührt den Ortsvergleich nicht, weil dort kein paralleler Bug besteht.
- **O3 bleibt eine Teil-Lücke.** Nur diese eine Unterdrückungsstelle bekommt einen
  `alert_log`-Eintrag. `deviation_alert_engine.py` und die übrigen ~zehn
  Unterdrückungsstufen bleiben unprotokolliert (volle O3-Lücke, nicht Teil dieser Scheibe).
- **Alarmaufkommen steigt**, Betrag vorab nicht messbar (Basislinie unbeobachtbar, siehe
  Analyse). Zwei Tage vor Tourstart bewusst in Kauf genommen (PO-Entscheid 2026-08-21).
- **Absolute Regeln und Empfindlichkeitsstufen bleiben unangetastet** — beide durch die
  Analyse als wirkungslos bzw. architektonisch gesperrt identifiziert (W1/W2), nicht Teil
  dieser Scheibe.
- **Prognose-Zwischenstände** (wann genau sprang die Vorhersage von 7,4 auf 29,4 mm)
  bleiben unaufgezeichnet — eigenes Ticket #2030.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** `#883` (konvektiver Sicherheits-Override) ist selbst kein ADR, sondern
  eine Issue/Epic-Slice-Entscheidung (`docs/features/issue-816-alert-deviation-core.md`).
  Diese Spec fügt eine zweite, unabhängige Durchbruchsbedingung (Überholung) hinzu, ohne
  die konvektive Bedingung zu verändern oder zurückzunehmen (AC-5 sichert das als
  Regressionsschutz ab) — additiv, keine Rücknahme einer dokumentierten Entscheidung. Der
  Vergleich bleibt in beiden Bedingungen ein Vergleich gegen den zuletzt versendeten
  Briefing-Stand, nie gegen einen absoluten Systemwert — das bestätigt ADR-0009 und
  ADR-0043, statt sie zu berühren. Absolute Alarmregeln (`include_absolute`) werden
  ausdrücklich nicht angefasst (ADR-0009/0013/0040/0043 bleiben in Kraft).

## Changelog

- 2026-08-21: Initial spec created (#2020 Scheibe 1, Umschnitt auf die Auslösung)
- 2026-08-21: Review-Korrektur (Team-Lead-Fund): Faktor-Vergleich lief fälschlich über die
  Spitzenrate (`max_rate_mm_h`) statt über eine Menge — ein kurzer, kräftiger Schauer hätte
  fälschlich ausgelöst, obwohl die reale Regenmenge die Ankündigung sogar unterschritten
  hätte. Ersetzt durch `window_precip_mm` (Mengen-Akkumulation aus echten
  Frame-Zeitstempeln, eigenes 60-Min-Vergleichsfenster statt des 180-Min-Nowcast-Fensters);
  `max_rate_mm_h` bleibt nur noch als Relevanz-Untergrenze. AC-1/AC-2 korrigiert
  (illustrativer Stundenwert statt Tagessumme), AC-3 angepasst, AC-4 (Fehlalarm-Wächter)
  neu eingefügt — die bisherigen AC-4/AC-5/AC-6 (Konvektiv-Override/Sichtbarkeit/kein
  Briefing-Wert) rücken dadurch zu AC-5/AC-6/AC-7 auf.
- 2026-08-21: Fix-Loop nach Adversary-Verdict BROKEN (Commit `559d4b5b`). Zwei CRITICAL
  Funde behoben: **F001** — `max_rate_mm_h` stammte aus dem 180-Min-Nowcast-Fenster statt
  aus demselben 60-Min-Vergleichsfenster wie `window_precip_mm`; ein später, unabhängiger
  Starkregen-Ausbruch außerhalb des Vergleichsfensters konnte dadurch die Überholung für
  ganz anderen, schwachen Nahregen legitimieren — jetzt beide Werte aus `compare_window`.
  **F002** — `_infer_frame_cadence()` nahm das Minimum aller Frame-Abstände über den
  gesamten, ungefilterten Frame-Satz; ein einzelner Ausreißer-Abstand irgendwo im
  180-Min-Horizont (z. B. Providerwiederholung) drückte die Kadenz auf wenige Minuten und
  unterzählte dadurch `window_precip_mm` im gesamten Vergleichsfenster (beobachtet:
  13,75-fache Unterzählung) — jetzt Median statt Minimum. ACs inhaltlich unverändert,
  Details siehe `docs/artifacts/fix-2020-alarm-zeitangaben/adversary-dialog.md`.
- 2026-08-21: Fix-Loop 2 nach Adversary-Verdict BROKEN (Commit `f8a564c5`, Runde 2). Der
  Median-Ansatz aus Fix-Loop 1 war selbst wieder brechbar: **F006** (CRITICAL) — eine
  Mehrheit ferner, TROCKENER Frames außerhalb des Vergleichsfensters zog die global
  abgeleitete Median-Kadenz auf 60 Minuten und rechnete den letzten Nahregen-Frame bis
  dorthin hoch, wodurch `window_precip_mm` sich verdoppelte (3,0 → 6,0 mm) und ein
  Alarm-Versand ausgelöst wurde, obwohl die Störframes selbst keinen Regen enthielten.
  **F007** (CRITICAL) — der Kadenz-Rückfallwert bei weniger als zwei unterscheidbaren
  Zeitstempeln (5 Min) war durch keinen Test bewacht; ein isolierter Einzel-Frame wäre bei
  falschem Rückfallwert bis zu 11,6-fach überzählt worden. Da JEDER weitere globale
  Schätzer (Minimum, Median, künftig denkbare Alternativen) dieselbe Angriffsfläche hätte,
  wurde `_infer_frame_cadence()` **ersatzlos entfernt** und durch eine
  nachbarschaftsbasierte Regel mit fester Obergrenze (`_MAX_FRAME_COVERAGE = 15 Min`)
  ersetzt — kein Wert außerhalb der unmittelbaren Nachbarschaft eines Frames kann dessen
  Deckung mehr beeinflussen. **F008** (HIGH) identifiziert, aber nicht Teil dieses
  Fix-Loops — PO-Entscheid: anhaltender Regen, der die Untergrenze erst knapp nach dem
  60-Min-Schnitt erreicht, soll warnen; Behebung folgt in einem eigenen Schritt direkt im
  Anschluss (eigene AC-Freigabe nötig). ACs dieses Fix-Loops inhaltlich unverändert.
  Details: `docs/artifacts/fix-2020-alarm-zeitangaben/adversary-dialog.md`, Abschnitt
  „Runde 2".
