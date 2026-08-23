---
entity_id: feat_2051_s4_strecke_kommando
type: feature
created: 2026-08-23
updated: 2026-08-23
status: draft
version: "1.3"
tags: [alarm, nowcast, radar, ausdehnung, zone, kommando, inbound]
---

# Inbound-Kommando `/strecke` — #2051 Scheibe S4

## Approval

- [ ] Approved

## Purpose

Alle bestehenden Kommandos (`/jetzt`, `/heute`, `/morgen`, `/gewitter`,
`/timeline_heute`, `/glance`) liefern **Ortswetter an einem Punkt**. S4 fuegt
ein neues, abrufbares Kommando `/strecke` hinzu, das die **Regen-
Ereignisflaechen entlang der Reststrecke der aktiven Etappe** ausgibt — die
Datenbausteine dafuer (`RainZone`, `derive_rain_zones()`,
`points_along_remaining_route()`) liegen seit S2a/S2b live im Alarm-Pfad,
S4 verdrahtet sie erstmals in einen **vom Nutzer selbst ausloesbaren** Pfad.

Grundprinzip aus dem Ticket (unveraendert bindend): **nur Daten ueber das
Wetter, keine Handlungsempfehlung und keine Rechnung ueber den Nutzer.**
Verboten sind Ankunftszeiten, Begegnungspunkte, "bei Planzeit bist du um
15:40 bei km 9". Erlaubt ist "Nass km 8-12, 15:00-16:30, mäßig, INCA".

## Source

- **File:** `src/services/trip_command_processor.py` (neuer Handler
  `_show_strecke` + zwei neue Renderer-Helfer), `src/services/trip_segments.py`
  (neue Punktbildung ab genanntem km), `src/services/rain_extent.py`
  (additive Felder auf `RainZone`), `src/services/inbound_telegram_reader.py`
  (Slash-Kurzform)
- **Identifier:** `_show_strecke()` (neu, `trip_command_processor.py`),
  `points_from_km()` (neu, `trip_segments.py`), `RainZone.intensity_label` /
  `RainZone.source` (neu, additiv, `rain_extent.py`)

> **Schicht-Hinweis:** Alle Aenderungen liegen ausschliesslich im
> Python-Core (`src/services/`) — kein Go-API-, kein Frontend-Anteil.

## Estimated Scope

- **LoC:** ~210-270 produktiv (neue Punktbildung ~40, additive Felder +
  Aggregation in `rain_extent.py` ~30, `_show_strecke` inkl. Argument-
  Validierung und Spannenbildung (E7) ~100, zwei Renderer-Helfer ~60,
  Wiring an drei Registrierungsstellen ~15), ~270-340 Tests — **über dem
  250-LoC-Workflow-Limit**, `workflow.py set-field loc_limit_override 500`
  vor `/40-tdd-red` einplanen (Muster wie S2a/S2b/S3).
- **Files:** `trip_command_processor.py`, `trip_segments.py`,
  `rain_extent.py`, `inbound_telegram_reader.py` + 3-4 neue Testdateien.
- **Effort:** medium-high — kein neuer Rechenkern (Punktbildung/Zonenbildung
  liegen seit S2a fertig vor), aber zwei neue Renderer, eine neue
  Argument-Validierung mit mehreren Randfällen, und Verdrahtung an zwei
  unabhängigen Eingangskanälen.

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `points_along_remaining_route()` | function (`trip_segments.py:683-715`, S2a) | Muster für die neue `points_from_km()` — dieselbe Deckelung (`RADAR_ZONE_MAX_POINTS`, `RADAR_ZONE_POINT_SPACING_KM`), nur mit anderem Startpunkt. |
| `derive_rain_zones()` / `RainZone` | function/dataclass (`rain_extent.py:26-91`, S2a) | Zonenbildung unverändert — S4 erweitert nur die Datenklasse additiv und liest die neuen Felder. |
| `ForecastBudgetGate` | class (`forecast_budget.py:36-74`) | `allow("user_briefing")` immer `True`, `allow("polling")` ab 80% `False` — trägt E1 ohne eigenes neues Gate. |
| `backfill_stage_distances()` | function (`track_resolution.py:264-344`) | Fail-soft-Nachrüstung der Kilometrierung — S4 ruft sie **selbst** auf, nach dem Muster des Alarm-Pfads (`trip_alert.py:1432-1436`), bevor das Segment aufgelöst wird. |
| `resolve_current_segment()` / `position_at_time()` | functions (`trip_segments.py:455,561`) | Unverändert — Planpositions-Einstieg ohne km-Argument (Muster `_show_now`). |
| `RadarNowcastService.source_label()` | method (`radar_service.py:555-561`) | Roh-Quellenschlüssel → Klartext, von den neuen Renderern zur Render-Zeit aufgerufen — `rain_extent.py` bleibt dadurch eine reine Auswertung ohne Kopplung an `radar_service.py`. |
| `_BARE_KEYWORD_MAP` / `_VALID_COMMANDS` | dict/set (`trip_command_processor.py:83,87-102`) | Zweistufige Registrierung — bare Keyword macht das Kommando automatisch auch über E-Mail-Inbound erreichbar (E4). |
| `_SHORTCUT_MAP` | dict (`inbound_telegram_reader.py:37-57`) | Slash-Variante `/strecke` für den Telegram-Bot-Menü-Tap — eigener Eintrag nötig, `_BARE_KEYWORD_MAP` allein deckt nur die Freitext-Eingabe ohne führenden Slash ab (siehe Korrektur unten). |
| `_show_now` | method (`trip_command_processor.py:1513-1588`) | Vorbild-Handler: Segmentauflösung, `elevation_m`-Normalisierung, Fehlerbranch bei fehlender heutiger Etappe — dessen Wortlaut wird für denselben Fall **wiederverwendet** (AC-18). |

## Korrektur gegenüber dem Kontextdokument

Das Kontextdokument benennt `inbound_telegram_reader._VALID_COMMANDS:33-35`
als zweite Slash-Registrierungsstelle. Nachgemessen (`inbound_telegram_
reader.py:449-484`) hat dieses Set dort **keine** Wirkung auf die Slash-Form:
`_parse_command()` prüft zuerst `_SHORTCUT_MAP` (explizite `/xyz`-Einträge,
z. B. `/heute`, `/now`, `/jetzt`), danach das geteilte `_BARE_KEYWORD_MAP`
(Freitext ohne Slash), und `_VALID_COMMANDS` greift nur als **Fallback für
Kommandos, die nicht in `_BARE_KEYWORD_MAP` stehen** (aktuell nur
`startdatum`/`report`). Da `strecke` in `_BARE_KEYWORD_MAP` landet (Schritt
2 löst es bereits auf), ist eine Ergänzung von `_VALID_COMMANDS` an dieser
Stelle **nicht** funktional notwendig — die tatsächliche Registrierungsstelle
für die Slash-Form ist `_SHORTCUT_MAP` (neuer Eintrag `"/strecke": "strecke"`,
Muster der bestehenden `/heute`/`/morgen`/`/now`-Einträge). Kein AC prüft
daher die Mitgliedschaft in `_VALID_COMMANDS` — das wäre eine Formprüfung
ohne beobachtbare Wirkung; AC-1 prüft stattdessen das tatsächliche
Dispatch-Ergebnis beider Eingabeformen.

## Getroffene Entscheidungen (E1–E7 aus dem Briefing + eigene Festlegungen)

**E1 — Abrufpriorität.** Der erste Messpunkt fährt `priority="user_briefing"`
(nie gedrosselt — eine Antwort kommt immer). Die Folgepunkte (bis zu 5
weitere) fahren `priority="polling"` und entfallen bei knapper Budgetlage.
Fällt ein einzelner Folgepunkt aus (Budget oder Fehler), läuft das Kommando
fail-soft mit den übrigen Punkten weiter (Muster `trip_alert.py:1748-1770`,
E4 aus S2a). Fallen **alle** Folgepunkte aus, während mehr als ein Punkt
geplant war, gibt die Antwort **keine** km-Zonen-Angabe aus — sie sagt
ehrlich, dass die Ausdehnung nicht ermittelt werden konnte (AC-7). Ist genau
1 Punkt geplant (Reststrecke unter der 2-km-Spacing-Schwelle, S2a-Regime),
ist dieser Punkt der volle, gültige Messumfang — sein Ergebnis ist eine
normale Antwort, kein Ausfall (AC-6, Positivkontrolle zu AC-7).

**E2 — `RainZone` additiv um `intensity_label`/`source` erweitert.**
Beide Felder tragen einen Default (`""`), bestehende S2a/S2b-Konstruktionen
(alle mit Keyword-Argumenten) bleiben unverändert lauffähig. Aggregation je
Zone:
- `intensity_label` = der **stärkste** Wert unter den Punkten der Zone,
  Rangfolge `INTENSITY_CONVECTIVE > INTENSITY_HEAVY > INTENSITY_MODERATE >
  INTENSITY_LIGHT` (Konstanten aus `radar_service.py:137-140`; `DRY` kommt
  in einer Zone strukturell nicht vor, da nur nasse Punkte — `onset_minutes
  is not None` — überhaupt in die Zonenbildung eingehen).
- `source` = der **rohe** Quellenschlüssel (z. B. `"INCA"`, `"radar"`) des
  Punkts, der die Zone trägt. Bei uneinheitlichen Quellen gewinnt der
  **erste** Punkt der Zone (kleinster km-Wert) — kein Mehrheitsentscheid,
  keine Kombination mehrerer Quellen in einem String. Die Klartext-
  Übersetzung (`RadarNowcastService.source_label()`) passiert **erst beim
  Rendern**, nicht in `rain_extent.py` — das Modul bleibt dadurch, wie im
  eigenen Docstring festgehalten, eine reine Auswertung ohne Kopplung an
  `radar_service.py`.

**E3 — Zwei neue Renderer, kein Antasten der bestehenden Suffix-Helfer.**
`_onset_extent_suffix()`/`_sms_onset_extent_suffix()` (`render.py`, S2a/S2b,
live) bleiben unverändert — sie hängen eine Ausdehnungs-**Angabe** an einen
Alarm-Satz. `/strecke` braucht etwas anderes: eine **mehrzeilige** Auflistung
aller Zonen als eigenständige Antwort. Die beiden neuen Helfer leben in
`trip_command_processor.py` (Muster der dortigen privaten Formatierer
`_fmt_glance`/`_fmt_timeline`/`_fmt_gewitter`), nicht in `render.py` — sie
teilen sich keinen Code mit den Alarm-Renderern, weil die Darstellungsform
(Tabelle/Liste vs. angehängter Halbsatz) grundverschieden ist. Beide
Renderer bekommen den **Abrufzeitpunkt als expliziten Parameter**
durchgereicht (Nachtrag, s. Implementation Details) — kein `datetime.now()`
im Renderer selbst.

**E4 — Zwei Eingangskanäle, eine Registrierungsstelle mit Wirkung auf beide,
plus eine kanalspezifische Ergänzung.** `strecke` kommt in
`_BARE_KEYWORD_MAP` (`trip_command_processor.py`) — das macht es automatisch
sowohl über Telegram-Freitext als auch über E-Mail-Inbound erreichbar (beide
rufen `TripCommandProcessor().process()` auf dieselbe Weise). Zusätzlich
nötig: der Slash-Eintrag in `_SHORTCUT_MAP` (`inbound_telegram_reader.py`,
siehe Korrektur oben) für den Telegram-Bot-Menü-Tap, sowie ein Eintrag in
`_show_help()`. SMS/Premium-SMS sind **keine** Registrierungsstelle — dort
gibt es keinen Inbound-Kommando-Pfad (Premium-SMS ist reiner Sendekanal,
siehe CLAUDE.md).

**E5 — Optionales km-Argument, bezogen auf die STAGE-kumulative
Kilometrierung des AKTUELL AKTIVEN Segments (eigene Festlegung).**
`points_along_remaining_route()` operiert auf `active: TripSegment` — dem
aktuell laufenden ~2h-Wegabschnitt, nicht der ganzen Tagesetappe. Die
ausgegebenen Zonen-km-Werte (`RainZone.km_from/km_to`, aus
`GPXPoint.distance_from_start_km`) sind aber **tageskumulativ** (S2a-Docstring:
"NICHT die Segment-Grenzen"). Damit das km-Argument dieselbe Einheit trägt
wie die Ausgabe, ist sein gültiger Bereich `[active.start_point.
distance_from_start_km, active.end_point.distance_from_start_km]` — die
kumulative Spanne des aktuell aktiven Segments, nicht `[0, aktive
Segmentlänge]` und nicht die ganze Tagesetappe. Eine Anfrage über mehrere
Segmente hinweg (z. B. "zeig mir ab km 2, obwohl ich gerade bei km 9 bin")
ist damit bewusst **außerhalb des Scopes** dieser Scheibe (Known Limitation)
— sie würde eine mehrsegmentige Traversierung erfordern, die
`points_along_remaining_route()` heute nicht kann.

Voraussetzung für ein gültiges Argument: `active.distance_measured is True`
(nach dem Backfill-Versuch, s. E6) — auf einem unvermessenen Segment hat
"km 5" keine verlässliche Bedeutung, egal ob der Nutzer sie selbst nennt.

**Ungültige Eingaben** (nicht-numerisch, negativ *relativ zum Segmentstart*
— konkret: unterhalb `active.start_point`-km oder oberhalb `active.
end_point`-km, oder syntaktisch kein Zahl): alle drei Fälle werden
**abgelehnt**, nicht stillschweigend geklemmt — ein geklemmter Wert würde
eine andere Frage beantworten als die gestellte (AC-15). **Dezimalwerte sind
erlaubt** (`float()`-Parsing, Punkt als Dezimaltrennzeichen) — die
Zonen-km-Werte selbst sind bereits `float`, eine künstliche Beschränkung auf
Ganzzahlen hätte keinen Gegenwert (AC-16). Der obere Rand des gültigen
Bereichs ist **eingeschlossen** — km gleich `end_point`-km ergibt eine
gültige, wenn auch entartete Anfrage mit Reststrecke 0 (AC-14, Konsistenz
mit dem bestehenden "Reststrecke < Spacing → 1 Punkt"-Verhalten aus S2a).

**E6 — Drei ehrliche Zweige, geprüft VOR jedem Nowcast-Aufruf.** `/strecke`
ruft zuerst `backfill_stage_distances(trip, user_id, today, persist=True)`
auf (Muster `trip_alert.py:1432-1436`) und löst danach das aktive Segment
auf.
1. **Keine aktive Etappe/kein auflösbares Segment** — derselbe Text wie
   `_show_now` in derselben Situation (AC-18), keine neue Formulierung für
   denselben Fall.
2. **Segment bleibt unvermessen** (auch nach dem Backfill-Versuch) — die
   Antwort kann keine einzige km-Zahl nennen, also auch keine Zonen-Liste;
   das ist kein Suffix-Wegfall wie in S2a/S2b (dort trägt der Restsatz noch
   Information), sondern der gesamte Kern der Antwort entfällt. Geprüft
   **vor** jedem `get_nowcast`-Aufruf — kein Budget wird für eine Antwort
   verbraucht, die ohnehin nicht kommen kann (AC-17).
3. **Kein Regen erkannt** (alle geplanten Punkte liefern Daten, alle
   trocken) — eigener, von den beiden anderen Zweigen wortlich
   unterscheidbarer Hinweis (AC-19).

**E7 — Die geprüfte Streckenspanne ist selbst ein Datum (Nachtrag,
Adversary-Befund team-lead).** `_remaining_km()`
(`trip_segments.py:665-681`) und die neue `points_from_km()` rechnen
ausschließlich innerhalb von `active` — dem aktuell laufenden ~2h-Segment,
nicht der vollen Resttagesetappe. Segmente entstehen wegpunktweise
(`convert_trip_to_segments`) und sind oft deutlich kürzer als die
theoretische 6×2-km-Reichweite der Punktbildung. Eine Antwort, die nur
"Kein Regen entlang der Reststrecke erkannt" sagt, behauptet damit mehr, als
gemessen wurde — der Nutzer liest daraus Trockenheit bis zum Etappenziel,
geprüft wurde aber nur ein Ausschnitt. Das ist keine Handlungsempfehlung,
sondern eine unbelegte Datenaussage — und widerspricht damit demselben
Grundprinzip, das Handlungsempfehlungen verbietet: nur sagen, was gemessen
wurde.

Direkte Analogie zu S3 (`· Radar reicht bis HH:MM` macht sichtbar, wo eine
Aussage endet, ohne sie zu bewerten): **jede Antwort, die überhaupt
gemessen hat, nennt zusätzlich die tatsächlich geprüfte km-Spanne** — vom
kleinsten bis zum größten km-Wert unter den **erfolgreich** abgefragten
Punkten (nicht den geplanten). Format, angehängt als eigene Zeile am Ende
der Antwort, in beiden Kanälen gleich: `Geprüft: km {von}-{bis}.`
(ganzzahlig gerundet wie die Zonen-km-Werte, ASCII-Bindestrich wie
`_sms_onset_extent_suffix`). Bei nur einem erfolgreichen Punkt entartet die
Spanne zu `von == bis` (z. B. `Geprüft: km 8-8.`) — genau dieselbe
Schreibweise wie ein einzelner degenerierter `RainZone`-Eintrag (S2a-AC-5).

Gilt in allen Zweigen **mit** Messung: Zonen vorhanden (E-Mail- und
Telegram-Fassung), kein Regen erkannt (AC-19), alle Folgepunkte ausgefallen
(AC-7 — dort ist die Spanne der Beleg für den Hinweistext selbst: "nur der
Startpunkt lieferte Daten" wird durch `Geprüft: km X-X` konkret). Gilt
**nicht** in den Zweigen ohne jede Messung: keine aktive Etappe (AC-18),
Kilometrierung fehlt (AC-17), ungültiges km-Argument (AC-15) — dort wurde
nichts abgefragt, eine Spanne wäre erfunden.

E7 behebt **nicht** die zugrundeliegende Segment-Grenze selbst (die
Antwort reicht weiterhin nur bis zum Ende des aktuell aktiven Segments,
nicht bis zum Etappenziel) — das würde `points_along_remaining_route()`/
`_remaining_km()` grundlegend ändern und damit den seit S2a **live**
laufenden Alarm-Pfad kurz vor Tourstart anfassen. E7 macht die bestehende
Grenze für den Nutzer **sichtbar** statt sie zu verschweigen; ihre
Aufhebung ist eine eigene, spätere Arbeit.

**Zeitanker der Renderer (Nachtrag aus der RED-Phase, team-lead-Befund).**
`RainZone.onset_minutes`/`event_end_minutes` sind **relative** Minuten
gegenüber dem Abrufzeitpunkt, AC-11/AC-12 verlangen aber **absolute**
Uhrzeiten. Ein Renderer, der die Uhrzeit selbst aus `datetime.now()`
bildet, liest damit eine ZWEITE, spätere Uhr als die, gegen die
`onset_minutes` gemessen wurde — jede Uhrzeit verschiebt sich systematisch
um die Dauer der bis zu sechs HTTP-Abrufe. Er wäre außerdem ohne
Zeitmanipulation nicht deterministisch prüfbar, die Bildungsstelle der
Uhrzeit bliebe unbewacht. Beide Renderer bekommen daher **denselben
`now_utc`, gegen den `_show_strecke` die Nowcasts abgerufen hat, als
expliziten dritten Parameter** — kein `datetime.now()` im Renderer (AC-23).

## Implementation Details

**Neue Punktbildung** (`trip_segments.py`, additiv, Muster
`points_along_remaining_route`):

```python
def points_from_km(
    trip: "Trip", active: TripSegment, segment_date: date, start_km: float,
) -> List[GPXPoint]:
    """Wie points_along_remaining_route(), aber der Startpunkt ist die vom
    Nutzer genannte, STAGE-kumulative Kilometrierung (Issue #2051 S4, E5) --
    nicht die Planposition. Aufrufer prueft VORHER active.distance_measured
    und die Bereichsgrenzen [active.start_point.distance_from_start_km,
    active.end_point.distance_from_start_km] (E5); diese Funktion nimmt
    start_km innerhalb dieses Bereichs als gegeben an."""
    frac = (
        (start_km - active.start_point.distance_from_start_km)
        / (active.end_point.distance_from_start_km
           - active.start_point.distance_from_start_km)
    ) if active.end_point.distance_from_start_km > active.start_point.distance_from_start_km else 0.0
    start = _lerp_point(active.start_point, active.end_point, frac)
    rest_km = active.end_point.distance_from_start_km - start_km
    if rest_km < RADAR_ZONE_POINT_SPACING_KM:
        return [start]
    anzahl = min(RADAR_ZONE_MAX_POINTS, int(rest_km // RADAR_ZONE_POINT_SPACING_KM) + 1)
    return [start] + [
        _lerp_point(start, active.end_point, (i * RADAR_ZONE_POINT_SPACING_KM) / rest_km)
        for i in range(1, anzahl)
    ]
```

**Additive Felder auf `RainZone`** (`rain_extent.py`):

```python
@dataclass(frozen=True)
class RainZone:
    km_from: float
    km_to: float
    onset_minutes: int
    event_end_minutes: int | None
    intensity_label: str = ""  # Issue #2051 S4 (E2): staerkster Wert der Zone
    source: str = ""           # Issue #2051 S4 (E2): Roh-Quelle des ersten
                                # Punkts bei Uneinheitlichkeit -- Klartext-
                                # Uebersetzung bleibt Sache der Renderer.
```

`_abschliessen()` in `derive_rain_zones()` sammelt zusätzlich Intensität und
Rohquelle je Punkt in `laufend` und berechnet beim Zonenabschluss den
stärksten Intensitätswert (Rang-Lookup, s. E2) sowie die Quelle des ersten
Eintrags.

**Geprüfte Spanne** (`trip_command_processor.py`, E7 — reine Hilfsfunktion,
unabhängig von Zonen/Regen-Zustand):

```python
def _geprueft_spanne(
    punkte: list, ergebnisse: list,
) -> tuple[float, float] | None:
    """km-Spanne der ERFOLGREICH abgefragten Punkte (nicht der geplanten,
    Issue #2051 S4, E7). None, wenn kein einziger Punkt ein Ergebnis lieferte
    (defensiv -- bei priority=user_briefing fuer den ersten Punkt in der
    Praxis nicht erreichbar, s. E1)."""
    kms = [
        p.distance_from_start_km
        for p, e in zip(punkte, ergebnisse) if e is not None
    ]
    if not kms:
        return None
    return (min(kms), max(kms))
```

Aufruf und Anhängung passieren NACH der Fail-soft-Schleife aus E1, in JEDEM
Zweig mit Messung (Zonen vorhanden, kein Regen, alle Folgepunkte aus) —
nicht in den drei Zweigen ohne jede Messung (E6).

**Neuer Kommando-Handler** (`trip_command_processor.py`, Muster `_show_now`):

```python
def _show_strecke(
    self, trip: Trip, value: Optional[str], now_utc: datetime,
    user_id: str, channel: str,
) -> CommandResult:
    """Regen-Ereignisflaechen entlang der Reststrecke (Issue #2051 S4)."""
    from services.track_resolution import backfill_stage_distances
    from services.trip_segments import (
        points_along_remaining_route, points_from_km, resolve_current_segment,
    )
    today = trip_local_today(trip, now_utc)
    trip = backfill_stage_distances(trip, user_id, today, persist=True)
    resolved = resolve_current_segment(trip, now_utc, today)
    if resolved is None:
        return CommandResult(  # AC-18: wortgleich zu _show_now
            success=False, command="strecke",
            confirmation_subject=f"[{trip.name}] Kein heutiger Standort",
            confirmation_body=(
                "Keine heutige Etappe gefunden. "
                "Aktueller Position/Standort unbekannt — "
                "bitte Etappenplan prüfen."
            ),
            trip_name=trip.name,
        )
    active, segment_date = resolved
    if not active.distance_measured:
        # AC-17: vor jedem Nowcast-Aufruf, kein Budget verbraucht
        ...
    if value is not None:
        # E5: Argument parsen und gegen [start_km, end_km] pruefen (AC-15/16)
        ...
        points = points_from_km(trip, active, segment_date, start_km)
    else:
        points = points_along_remaining_route(trip, active, segment_date, now_utc)
    # E1: erster Punkt user_briefing, Folgepunkte polling + fail-soft
    # ...ergebnisse sammeln...
    # E7: spanne = _geprueft_spanne(points, ergebnisse), an jede der drei
    # Messungs-Zweig-Antworten (Zonen/kein Regen/alle Folgepunkte aus) anhaengen
    tz = tz_for_coords(points[0].lat, points[0].lon)
    if channel == "email":
        body = _fmt_strecke_email(zonen, tz, now_utc)  # now_utc = derselbe Anker
    else:
        body = _fmt_strecke_telegram(zonen, tz, now_utc)  # wie die Nowcast-Abrufe
    ...
```

**Zwei neue Renderer** (`trip_command_processor.py`, je ein privater
Formatierer, `now_utc` als expliziter Zeitanker — s. Abschnitt "Zeitanker
der Renderer" oben, AC-23):

```python
def _fmt_strecke_email(
    zonen: tuple["RainZone", ...], tz, now_utc: datetime,
) -> str:
    """Tabellarische Zeile je Zone: km-Spanne, Zeitspanne, Intensitaet,
    Quelle (Issue #2051 S4, E3). `now_utc` ist der Abrufzeitpunkt, gegen den
    die relativen `onset_minutes`/`event_end_minutes` in absolute HH:MM
    umgerechnet werden -- IMMER derselbe Wert, den `_show_strecke` fuer die
    Nowcast-Abrufe verwendet hat, NIE `datetime.now()`."""

def _fmt_strecke_telegram(
    zonen: tuple["RainZone", ...], tz, now_utc: datetime,
) -> str:
    """Verdichtete Fassung: eine Zeile je Zone, km-Spanne, Zeitspanne,
    Intensitaet -- ohne Quelle-Spalte (Platzgrund, Issue #2051 S4). Derselbe
    Zeitanker-Vertrag wie `_fmt_strecke_email`."""
```

**Registrierung** (drei Stellen, E4):

```python
# trip_command_processor.py:83
_VALID_COMMANDS = {..., "strecke"}
# trip_command_processor.py:87-102
_BARE_KEYWORD_MAP = {..., "strecke": "strecke"}
# trip_command_processor.py Dispatch (~line 525)
elif key == "strecke":
    return self._show_strecke(trip, value, msg.received_at, msg.user_id, msg.channel)
# inbound_telegram_reader.py:37-57
_SHORTCUT_MAP = {..., "/strecke": "strecke"}
# trip_command_processor.py:_show_help (~line 1391)
"  STRECKE [km]           – Regen-Ereignisflächen entlang der Reststrecke\n"
```

## Expected Behavior

- **Input:** Trip, aktueller Zeitpunkt (`msg.received_at`, zugleich der
  Abrufzeitpunkt `now_utc` für die Nowcast-Abrufe UND der Zeitanker, den
  beide Renderer explizit als Parameter bekommen — E1/E3), Kanal
  (`msg.channel` — `"email"`/`"telegram"`), optionales km-Argument (String
  oder `None`), `user_id`.
- **Output:**
  - E-Mail-Antwort: eine Zeile je Regen-Ereignisfläche mit km-Spanne,
    Zeitspanne (absolut, gegen den durchgereichten Anker berechnet),
    Intensität und Quelle, plus abschließender
    `Geprüft: km {von}-{bis}.`-Zeile (E7).
  - Telegram-Antwort: eine verdichtete Zeile je Fläche (km-Spanne,
    Zeitspanne, Intensität), plus dieselbe abschließende Geprüft-Zeile.
  - Drei ehrliche Sonderfälle (E6): keine aktive Etappe, Segment unvermessen,
    kein Regen erkannt — jeweils eigener, unterscheidbarer Text; im
    Kein-Regen-Fall zusätzlich die geprüfte Spanne (E7).
  - Ungültiges km-Argument: Ablehnung mit dem gültigen Bereich im Text, kein
    Nowcast-Abruf, keine Spannen-Angabe (nichts wurde gemessen).
  - Fallen alle Folgepunkte aus (E1): ehrlicher Hinweis, belegt durch die
    (degenerierte) geprüfte Spanne `km X-X` (E7).
- **Side effects:** bis zu `RADAR_ZONE_MAX_POINTS` `get_nowcast`-Aufrufe je
  Kommando (gedeckelt, wie S2a), ein `backfill_stage_distances`-Schreibvorgang
  (fail-soft, additiv, unabhängig vom Kommando-Ergebnis). Keine
  Trip-Konfiguration wird verändert.

## Acceptance Criteria

- **AC-1:** Given zwei Telegram-Nachrichten mit identischem Kommando in
  unterschiedlicher Schreibweise — (a) `strecke` (Freitext, kein Slash) und
  (b) `/strecke` (Slash, Bot-Menü-Tap) / When beide durch
  `InboundTelegramReader._parse_command` laufen / Then lösen BEIDE denselben
  internen Schlüssel `("strecke", None)` auf — kein Unterschied zwischen
  Freitext- und Slash-Eingabe.
  - Test: Unit-Test gegen `_parse_command` mit beiden Eingaben, Assert auf
    identisches Ergebnis. Bewacht: `inbound_telegram_reader.py:_SHORTCUT_MAP`
    + `trip_command_processor.py:_BARE_KEYWORD_MAP`.

- **AC-2:** Given eine E-Mail mit Body `STRECKE` als erste Zeile / When
  `TripCommandProcessor().process()` mit `channel="email"` läuft / Then wird
  `_show_strecke` aufgerufen (`result.command == "strecke"`, kein
  "Unbekannter Befehl").
  - Test: Unit-Test gegen `process()` mit `InboundMessage(channel="email",
    body="STRECKE", ...)`, Assert auf `result.command`. Bewacht:
    `trip_command_processor.py:_VALID_COMMANDS`, Dispatch-Zweig.

- **AC-3:** Given den Befehl HILFE / When `_show_help()` läuft / Then
  enthält der Text eine Zeile, die mit `"  STRECKE"` beginnt, mit einer
  Kurzbeschreibung der Regen-Ereignisflächen entlang der Reststrecke.
  - Test: Unit-Test gegen `_show_help`, Substring-Prüfung. Bewacht:
    `trip_command_processor.py:_show_help`.

- **AC-4:** Given ein aktives Segment mit Reststrecke 10 km (mehrere
  geplante Punkte) UND einem simulierten Budgetstand von 85% (`allow
  ("polling")` würde `False` liefern) / When `/strecke` verarbeitet wird /
  Then liefert der ERSTE Abfragepunkt trotzdem ein Ergebnis, UND dessen
  `get_nowcast`-Aufruf trägt `priority="user_briefing"`.
  - Test: Unit-Test mit Budget-Fixture bei 85% Auslastung, Assert auf den
    Prioritätsparameter des ersten Aufrufs. Bewacht:
    `trip_command_processor.py:_show_strecke`.

- **AC-5:** Given 4 geplante Punkte, wobei Punkt 3 (nicht Punkt 1) eine
  Exception wirft / When `/strecke` verarbeitet wird / Then werden Punkt 2
  und Punkt 4 dennoch mit `priority="polling"` abgefragt, UND die Antwort
  enthält die aus den Punkten 1/2/4 gebildeten Zonen — das Kommando bricht
  wegen des Einzelausfalls NICHT ab.
  - Test: Unit-Test mit Fake-Service, der bei Index 3 wirft, Assert auf
    Aufrufzahl UND enthaltene Zonen. Bewacht:
    `trip_command_processor.py:_show_strecke` (Fail-soft-Schleife).

- **AC-6:** Given eine Reststrecke von 1,5 km (unter der 2-km-Schwelle,
  genau 1 geplanter Punkt), dieser liefert eine Nass-Zone / When `/strecke`
  verarbeitet wird / Then meldet die Antwort diese eine Zone als normale
  Streckenangabe, OHNE den Hinweis auf eine nicht ermittelbare Ausdehnung.
  - Test: Unit-Test mit 1-Punkt-Fixture, Assert dass die Zonen-Zeile
    erscheint UND der AC-7-Hinweistext fehlt. Bewacht:
    `trip_command_processor.py:_show_strecke`.

- **AC-7:** Given 6 geplante Punkte bei den km-Werten 0, 2, 4, 6, 8, 10
  (Reststrecke 12 km), von denen NUR der erste (km 0) ein Ergebnis liefert
  (Punkte 2-6 alle `throttled`/Exception) / When `/strecke` verarbeitet
  wird / Then enthält die Antwort exakt `"Ausdehnung entlang der
  Reststrecke konnte nicht ermittelt werden — nur der Startpunkt lieferte
  Daten. Geprüft: km 0-0."` — die degenerierte Spanne (E7) belegt den
  Hinweistext mit einem konkreten Wert — und KEINE km-Zonen-Angabe.
  - Test: Unit-Test mit 6-Punkte-Fixture (Punkte 2-6 liefern `None`),
    Volltextvergleich (inkl. der Geprüft-Zeile) UND Negativ-Prüfung, dass
    kein `RainZone`-Muster (`"Nass km"`) vorkommt. Bewacht:
    `trip_command_processor.py:_show_strecke`.

- **AC-8:** Given 3 zusammenhängende nasse Punkte einer Zone mit den
  Intensitäten "Leichter Regen", "Starker Regen", "Mäßiger Regen" (in
  dieser Reihenfolge entlang der Strecke) / When die Zone gebildet wird /
  Then trägt `RainZone.intensity_label == "Starker Regen"` — der stärkste
  Wert, unabhängig von seiner Position.
  - Test: Unit-Test gegen `derive_rain_zones` mit den drei Intensitäten als
    Fixture-Ergebnisse. Bewacht: `rain_extent.py:derive_rain_zones`.

- **AC-9:** Given zwei Fälle: (a) zwei nasse Punkte einer Zone mit
  identischer Quelle `"radar"`, (b) zwei nasse Punkte einer Zone mit den
  Quellen `"INCA"` (erster/km-kleinster Punkt) und `"radar"` (zweiter
  Punkt) / When beide Zonen gebildet werden / Then trägt Zone (a)
  `RainZone.source == "radar"`, Zone (b) `RainZone.source == "INCA"` — NICHT
  `"radar"`.
  - Test: Unit-Test gegen `derive_rain_zones` mit beiden Fixtures, je
    Fall Assert auf `zone.source`, Negativ-Prüfung für Fall (b). Bewacht:
    `rain_extent.py:derive_rain_zones`.

- **AC-10:** Given die bestehenden S2a/S2b-Testfixtures für
  `derive_rain_zones()` und die sieben gerenderten Alarm-Textstellen
  (`render.py`) / When der Alarm-Pfad mit diesen Fixtures unverändert
  läuft / Then bleiben `RainZone.km_from/km_to/onset_minutes/
  event_end_minutes` UND alle sieben gerenderten Texte byte-identisch zum
  Stand vor dieser Spec — die neuen Felder `intensity_label`/`source`
  werden dort nicht gelesen.
  - Test: Regressionslauf von `test_regen_ausdehnung_zonenbildung.py` und
    `test_regen_ausdehnung_textstellen.py` ohne Fixture-Änderung — müssen
    unverändert grün bleiben. Bewacht: `rain_extent.py`, `render.py`
    (Nicht-Berührung).

- **AC-11:** Given zwei Zonen (km 8-12, "Mäßiger Regen", Quelle "INCA",
  Zeitspanne 15:00-16:30; km 19-21, "Starker Regen", Quelle "radar",
  Zeitspanne 17:10-17:40) / When die E-Mail-Antwort gerendert wird / Then
  enthält der Text für JEDE Zone eine eigene Zeile mit allen vier Werten —
  konkret Zeile 1 mit `km 8-12`, `15:00-16:30`, `Mäßiger Regen`, `INCA`,
  Zeile 2 entsprechend mit den Werten der zweiten Zone.
  - Test: Unit-Test gegen `_fmt_strecke_email` mit der Zwei-Zonen-Fixture,
    Substring-Prüfung beider vollständigen Zeilen, Sollstrings aus den
    Fixture-Werten abgeleitet. Bewacht: `trip_command_processor.py`.

- **AC-12:** Given denselben Zwei-Zonen-Aufbau wie AC-11 / When die
  Telegram-Antwort gerendert wird / Then enthält der Text GENAU zwei
  Zeilen (eine je Fläche), UND alle aus beiden Texten extrahierten km-Zahlen
  UND Uhrzeiten (Regex) stimmen zwischen E-Mail- und Telegram-Fassung exakt
  überein.
  - Test: Paritätstest (Muster `test_onset_menge_kanalparitaet.py`):
    Regex-Extraktion der Zahlenpaare aus beiden Texten, Gleichheitsprüfung.
    Bewacht: `trip_command_processor.py` (beide Renderer gemeinsam).

- **AC-13:** Given ein aktives Segment mit `start_point.distance_from_
  start_km=3.0`, `end_point.distance_from_start_km=8.0`,
  `distance_measured=True` UND dem Kommando `/strecke 5` / When die
  Abfragepunkte gebildet werden / Then liegt der ERSTE Punkt bei
  `distance_from_start_km == 5.0` — NICHT an der über `position_at_time`
  bestimmten Planposition.
  - Test: Unit-Test gegen `points_from_km`, Assert auf den exakten km-Wert
    des ersten erzeugten Punkts. Bewacht: `trip_segments.py:points_from_km`.

- **AC-14:** Given dasselbe Segment wie AC-13, Kommando `/strecke 8`
  (exakt `end_point`-km, oberer Rand des gültigen Bereichs eingeschlossen) /
  When verarbeitet wird / Then entsteht GENAU EIN Punkt bei km 8.0
  (Reststrecke=0 innerhalb des Segments) — gültige, wenn auch entartete
  Anfrage, KEINE Fehlermeldung.
  - Test: Unit-Test mit km=8.0, Assert auf genau 1 erzeugten Punkt UND
    `result.success is True`. Bewacht: `trip_segments.py:points_from_km`,
    `trip_command_processor.py:_show_strecke`.

- **AC-15:** Given dasselbe Segment (gültiger Bereich 3–8 km) mit drei
  Kommandos: `/strecke 8.1` (über der oberen Grenze), `/strecke 2.9` (unter
  der unteren Grenze), `/strecke abc` (nicht-numerisch) / When jedes
  verarbeitet wird / Then liefert JEDES exakt den Text `"Ungültige
  km-Angabe. Gültiger Bereich für die aktuelle Etappe: 3–8 km."` UND in
  KEINEM der drei Fälle erfolgt ein `get_nowcast`-Aufruf.
  - Test: Drei Unit-Tests (oder parametrisiert) gegen `_show_strecke`, je
    Volltextvergleich UND Assert `nowcast_spy.call_count == 0`. Bewacht:
    `trip_command_processor.py:_show_strecke` (Argument-Validierung).

- **AC-16:** Given dasselbe Segment, Kommando `/strecke 5.5` / When
  verarbeitet wird / Then liegt der erste erzeugte Punkt exakt bei km 5.5 —
  Dezimalwerte werden akzeptiert und nicht auf ganze km gerundet.
  - Test: Unit-Test mit km=5.5, Assert auf den exakten Fließkommawert.
    Bewacht: `trip_segments.py:points_from_km`.

- **AC-17:** Given ein aktives Segment, das auch nach dem Backfill-Versuch
  `distance_measured=False` bleibt, in zwei Varianten: (a) `/strecke` ohne
  Argument, (b) `/strecke 5` mit Argument / When beide verarbeitet werden /
  Then liefert (a) exakt `"Kilometrierung für die heutige Etappe nicht
  verfügbar — keine Streckenangabe möglich."`, (b) exakt `"Kilometrierung
  für die heutige Etappe nicht verfügbar — die km-Angabe kann nicht
  ausgewertet werden."` — UND in BEIDEN Fällen erfolgt KEIN
  `get_nowcast`-Aufruf UND KEINE `Geprüft:`-Zeile (nichts wurde gemessen).
  - Test: Zwei Unit-Tests mit `distance_measured=False`-Fixture (simulierter
    Backfill-Fehlschlag), Volltextvergleich je Variante, Assert
    `nowcast_spy.call_count == 0` UND Negativ-Prüfung auf `"Geprüft:"`.
    Bewacht: `trip_command_processor.py:_show_strecke` (Gate vor jedem
    Aufruf).

- **AC-18:** Given keinen auflösbaren Standort für heute
  (`resolve_current_segment` liefert `None`, analog zur `/jetzt`-Situation) /
  When `/strecke` verarbeitet wird / Then ist `result.confirmation_body`
  TEXTIDENTISCH zu dem Text, den `_show_now` in derselben Situation liefert
  (`"Keine heutige Etappe gefunden. Aktueller Position/Standort unbekannt —
  bitte Etappenplan prüfen."`) — insbesondere ohne jede `Geprüft:`-Zeile.
  - Test: Unit-Test mit fehlgeschlagener Segmentauflösung, String-Gleichheit
    gegen den bekannten `_show_now`-Text. Bewacht:
    `trip_command_processor.py:_show_strecke`.

- **AC-19:** Given ein vermessenes aktives Segment mit 4 geplanten Punkten
  bei km 0, 2, 4, 6 (illustrativ — entscheidend ist nicht die konkrete
  km-Lage, sondern dass die Werte aus den ERFOLGREICH abgefragten Punkten
  abgeleitet werden, s. AC-21; km 0 als Startwert gewählt, da der
  argumentlose Pfad den ersten Punkt nur im ERSTEN Segment einer Etappe
  driftfrei exakt am Segmentanfang liefert — spätere Segmente sind über die
  reale Zeit-Segmentwahl nicht mit p=0 erreichbar), bei denen ALLE ein
  Ergebnis liefern und ALLE trocken sind (`onset_minutes is None`, kein
  `data_unavailable`) / When `/strecke` verarbeitet wird / Then enthält die
  Antwort exakt `"Kein Regen entlang des geprüften Abschnitts erkannt.
  Geprüft: km 0-6."` — die Aussage bezieht sich ausdrücklich auf den
  GEPRÜFTEN Abschnitt (E7), nicht pauschal auf "die Reststrecke" bis zum
  Etappenziel, und der Wortlaut unterscheidet sich klar von AC-7
  (Ausdehnung nicht ermittelbar) und AC-17 (Kilometrierung fehlt).
  - Test: Unit-Test mit vollständig trockener 4-Punkte-Fixture (km 0-6),
    Volltextvergleich inkl. der Geprüft-Zeile mit den aus der Fixture
    abgeleiteten Grenzwerten. Bewacht: `trip_command_processor.py:
    _show_strecke`.

- **AC-20:** Given eine beliebige Zonen-Antwort in E-Mail- ODER
  Telegram-Fassung mit gesetzten Zonen / When der Text auf eine Liste
  verbotener Muster geprüft wird (Ankunftszeit-Rechnung,
  Handlungsempfehlung, Begegnungspunkt-Aussage — dieselbe Musterliste wie
  S2a-AC-16/S2b-AC-14) / Then enthält der Text KEINES dieser Muster —
  ausschließlich km-Spannen, Uhrzeiten, Intensität, Quelle und die
  geprüfte Spanne.
  - Test: Unit-Test über beide Renderer-Ausgaben mit gesetzten Zonen,
    Negativ-Prüfung gegen die bestehende Musterliste. Bewacht:
    `trip_command_processor.py` (beide neuen Renderer).

- **AC-21 (E7):** Given 4 geplante Punkte bei km 0, 2, 4, 6 (dieselbe
  illustrative Fixture-Wahl wie AC-19 — km 0 als erster Punkt des ersten
  Segments), von denen der LETZTE (km 6) eine Exception wirft, die übrigen
  drei (km 0, 2, 4) liefern Daten (mindestens einer nass, damit eine
  Zonen-Antwort entsteht) / When `/strecke` verarbeitet wird / Then nennt
  die Antwort exakt `"Geprüft: km 0-4."` — abgeleitet aus dem kleinsten und
  größten km-Wert der ERFOLGREICH abgefragten Punkte (0 und 4), NICHT aus
  dem geplanten Maximum (6).
  - Test: Unit-Test mit 4-Punkte-Fixture, Punkt bei km 6 wirft, Substring-
    Prüfung auf exakt `"Geprüft: km 0-4."` UND Negativ-Prüfung, dass
    `"km 0-6"` nicht vorkommt (die Bildungsstelle wird aus den
    tatsächlichen Ergebnissen gespeist, nicht aus der Planung). Bewacht:
    `trip_command_processor.py:_geprueft_spanne`.

- **AC-22 (E7, Positivkontrolle):** Given zwei Fälle mit identischem
  Trip-/Zeit-Aufbau bis auf einen Unterschied: (a) `distance_measured=False`
  bleibt nach dem Backfill-Versuch (AC-17-Konstellation, kein
  Nowcast-Abruf), (b) derselbe Aufbau, aber `distance_measured=True`
  (mindestens 1 Punkt liefert Daten) / When beide Antworten erzeugt werden
  / Then enthält Antwort (a) KEINE `"Geprüft:"`-Zeile, während Antwort (b)
  — bei sonst identischem Aufbau — eine `"Geprüft: km"`-Zeile mit dem
  erwarteten Wert trägt.
  - Test: Testpaar mit identischem Aufbau bis auf `distance_measured`,
    Negativ-Prüfung für (a), Positiv-Prüfung mit exaktem Wert für (b) im
    selben Test (Muster S2b-AC-6) — belegt, dass das Fehlen in (a) eine
    echte Weiche ist und nicht schlicht ein nirgends implementierter Text.
    Bewacht: `trip_command_processor.py:_show_strecke`.

- **AC-23 (Zeitanker der Renderer, Nachtrag):** Given eine identische
  Zonen-Fixture (eine Zone mit `onset_minutes=30`, `event_end_minutes=90`)
  UND zwei verschiedene Ankerzeitpunkte `now_utc`: (a)
  `2026-08-23T12:00:00Z`, (b) `2026-08-23T12:47:00Z` (47 Minuten später) /
  When derselbe Renderer (`_fmt_strecke_email` bzw. `_fmt_strecke_telegram`)
  einmal mit Anker (a) und einmal mit Anker (b) auf DIESELBE Zonen-Fixture
  angewendet wird / Then unterscheiden sich sowohl die gerenderte
  BEGINN-Uhrzeit ALS AUCH die gerenderte ENDE-Uhrzeit zwischen beiden
  Läufen um EXAKT 47 Minuten — konkret Fall (a) Beginn `12:30`/Ende `13:30`,
  Fall (b) Beginn `13:17`/Ende `14:17` — die Uhrzeit wird aus dem
  ÜBERGEBENEN Anker abgeleitet, nicht aus der Systemuhr; ein Rückfall auf
  `datetime.now()` würde bei zwei im selben Testlauf ausgeführten Aufrufen
  eine Differenz nahe 0 statt exakt 47 Minuten ergeben und beide Prüfungen
  (Beginn UND Ende) rot färben.
  - Test: Zwei Unit-Tests (oder ein Testpaar) gegen `_fmt_strecke_email`
    UND `_fmt_strecke_telegram` mit identischer Zonen-Fixture und den zwei
    Ankerwerten, JE ZWEI Asserts (Beginn-Differenz UND Ende-Differenz
    exakt 47 Minuten) statt eines pauschalen Textvergleichs — eine
    Implementierung, die nur eine der beiden Zeitangaben korrekt aus dem
    Anker ableitet, die andere aber aus einer zweiten Quelle bezieht, wird
    dadurch separat gefangen. Bewacht:
    `trip_command_processor.py:_fmt_strecke_email`/`_fmt_strecke_telegram`
    (Zeitanker-Parameter, s. E3-Nachtrag).

## Known Limitations

- **Die Antwort deckt nur das aktuell aktive Wegpunkt-Segment ab, nicht die
  volle Resttagesetappe** (Bestandseigenschaft aus S2a — der Alarm-Pfad hat
  dieselbe Grenze, `_remaining_km()`/`points_along_remaining_route()`
  rechnen ausschließlich innerhalb von `active`). Diese Scheibe behebt die
  Grenze **nicht** — der live laufende Alarm-Pfad wird kurz vor Tourstart
  bewusst nicht angefasst —, macht sie aber über E7 (`Geprüft: km ...`)
  für den Nutzer **sichtbar** statt sie zu verschweigen. Die Aufhebung
  dieser Grenze (mehrsegmentige Traversierung bis zum Etappenziel) ist
  eine eigene, spätere Arbeit.
- **km-Argument nur innerhalb des aktuell aktiven Segments adressierbar**
  (eigene Festlegung E5), aus demselben Grund — siehe oben.
- **Kein SMS-/Premium-SMS-Kanal für `/strecke`.** Beide sind keine
  Inbound-Kommando-Kanäle in diesem System (Premium-SMS ist reiner
  Sendekanal) — das ist keine Lücke dieser Scheibe, sondern eine
  bestehende Systemgrenze.
- **Messlücken bleiben unmarkiert** (S2a Known Limitation, unverändert) —
  ein Punkt ohne Daten fällt still aus der Zonenbildung heraus. E7 macht
  nur die AUSSENGRENZE der Messung sichtbar (welcher km-Bereich überhaupt
  geprüft wurde), nicht einzelne Lücken innerhalb dieses Bereichs.
- **Kein Wiederholungs-Rate-Limit für das Kommando selbst.** Der
  300-Sekunden-Nowcast-Cache dämpft wiederholte Abfragen teilweise, der
  Telegram-Rate-Limit (18/60s) bremst nur den Versand. Ein Nutzer kann
  `/strecke` beliebig oft hintereinander senden — jedes Mal zählt gegen das
  Tagesbudget (mit `polling`-Priorität für die Folgepunkte, gedeckelt).
- **Ortsvergleich bleibt ohne `/strecke`** — kein Streckenkonzept
  (unverändert seit S2a/S2b).

## Nicht-Ziele

- Handlungsempfehlungen jeder Art.
- Rechnungen über den Nutzer: Ankunftszeiten, Begegnungspunkte,
  Ausweichfenster.
- GPS-Ortung oder Check-in-Pflicht.
- Änderungen an bestehenden Alarm-Textstellen oder an
  `_onset_extent_suffix()`/`_sms_onset_extent_suffix()` (S2a/S2b sind live).
- Änderungen am `/jetzt`-Pfad (`_show_now`) und am Briefing-
  Kurzfristhinweis (`starkregen_hint.py`).
- Änderungen an der Trip-Konfiguration des Product Owners.
- Ortsvergleich: kein Streckenkonzept, `/strecke` gilt nur für Trips.
- SMS/Premium-SMS als Antwortkanal für `/strecke` (kein Inbound-Kanal für
  diese beiden).
- Mehrsegmentige Traversierung über das aktuell aktive Segment hinaus beim
  km-Argument, bzw. eine Erweiterung der Reststrecken-Reichweite auf die
  volle Resttagesetappe (s. Known Limitations) — insbesondere keine
  Änderung an `_remaining_km()`/`points_along_remaining_route()` selbst,
  die den live laufenden Alarm-Pfad beträfe.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Ein neues **Kommando** über zwei bereits bestehende
  Inbound-Kanäle (Telegram, E-Mail) — keine der vier Output-Kanäle
  (ADR-0049) wird verändert oder erweitert, es kommt kein neuer Kanal
  hinzu. Die Datenbausteine (`RainZone`, `derive_rain_zones`,
  `points_along_remaining_route`) sind additiv erweitert, keine bestehende
  Signatur ändert sich. Kein neuer Provider, keine Persistenz-Änderung
  außer der bereits etablierten, fail-soften `backfill_stage_distances`-
  Nachrüstung. Berührt keine der vier Entscheidungsflächen, die ein neues
  ADR verlangen würden.

## Changelog

- 2026-08-23: Initial spec created (#2051 Scheibe S4, Inbound-Kommando
  `/strecke` — zwei Eingangskanäle, Prioritäts-/Budget-Regel E1, additive
  `RainZone`-Felder E2, zwei neue Renderer E3, km-Argument E5, drei ehrliche
  Sonderfälle E6).
- 2026-08-23 (v1.1): E7 nachgetragen (Adversary-Befund team-lead) — die
  geprüfte Streckenspanne wird als eigenes Datum ausgegeben, weil die
  Antwort strukturell nur bis zum Ende des aktuell aktiven Segments reicht,
  nicht bis zum Etappenziel. AC-19 umformuliert (nennt jetzt die geprüfte
  Spanne statt pauschal "die Reststrecke" zu behaupten), AC-7
  entsprechend ergänzt, zwei neue ACs (AC-21 Bildung aus erfolgreich statt
  geplant abgefragten Punkten, AC-22 Positivkontrolle Messung vs. keine
  Messung). AC-Zahl 20 → 22. Known Limitations/Nicht-Ziele um die
  Segment-Grenze ergänzt.
- 2026-08-23 (v1.2): Zeitanker-Korrektur aus der RED-Phase (team-lead-
  Befund) — beide Renderer bekommen `now_utc` als expliziten dritten
  Parameter statt selbst die Systemuhr zu lesen (relative
  `onset_minutes`/`event_end_minutes` müssen gegen denselben Zeitpunkt
  umgerechnet werden, gegen den die Nowcasts abgerufen wurden). Neues
  AC-23 (Zeitanker, zwei verschiedene `now_utc`-Werte ergeben exakt
  verschobene Uhrzeiten). AC-Zahl 22 → 23. Illustrative km-Werte in AC-19/
  AC-21 auf 0/2/4/6 nachgezogen (Testkonstruktion: der argumentlose Pfad
  erreicht den Segmentanfang driftfrei nur im ersten Segment einer
  Etappe) — die geprüfte Zusicherung selbst (Ableitung aus erfolgreich
  abgefragten statt geplanten Punkten) ist davon unberührt.
- 2026-08-23 (v1.3): AC-23 an die tatsächlich in der RED-Phase gebauten
  Tests angeglichen (team-lead-Rückfrage) — Ankerdifferenz von 10 auf 47
  Minuten korrigiert, UND die Zusicherung explizit auf BEIDE Zeitwerte
  (Beginn UND Ende der Zone) statt eines pauschalen Textvergleichs
  ausgeweitet, damit eine Implementierung, die nur einen der beiden Werte
  korrekt aus dem Anker ableitet, ebenfalls auffällt. Keine Änderung an
  Renderer-Signaturen oder sonstigen ACs.
