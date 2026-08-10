---
entity_id: fix_1653_ausblick_tag_nacht_trennung
type: bugfix
created: 2026-08-09
updated: 2026-08-10
status: implemented
version: "1.0"
tags: [gewitter, ausblick, tag-nacht, issue-1653]
---

# #1653 — Mehrtages-Ausblick: Gewitter-Zelle trennt Tag und Nacht

## Approval

- [x] Approved

## Purpose

Die Gewitter-Zelle des Mehrtages-Ausblicks (Abend-Mail-Tabelle,
Abend-Mail-Klartext, Telegram-„Ausblick"-Bubble) trägt heute zwei
unabhängige Datenquellen für dieselbe Zeile und verrührt sie zu einer
einzigen, oft widersprüchlichen Aussage. Drei gemessene Fehler (Issue
#1653, Stand `bcc4aeaf`):

1. **Wort und Uhrzeit stammen aus verschiedenen Zeiträumen.** Das Wort
   (`thunder_word`) kommt aus dem auf die Gehzeit geklemmten Aggregat, die
   angehängte Uhrzeit aus der ungefilterten 24-Stunden-Reihe. Fall B der
   Messung: Tag „mittel" 14 Uhr, Nacht „hoch" 0 Uhr → Zelle zeigt „MED @0"
   — ein Tageswort mit einer Nachtstunde kombiniert.
2. **Tag und Nacht fallen zusammen, eines verschwindet.** Nur der stärkste
   Wert über 24 Stunden wird gezeigt. Ist die Nacht stärker, verschwindet
   das Tagesgewitter (Fall B); ist der Tag stärker, verschwindet das
   Nachtgewitter (Fall C). **Beide werden nie gleichzeitig gezeigt** — in
   HTML-Tabelle, Klartext-Mail und Telegram gleichermaßen.
3. Rohe Programmnamen `MED`/`HIGH` statt `mittel`/`hoch` in der
   Klartext-Mail — **eigenes Ticket #1654, nicht Teil dieser Spec.**

Der eigentliche fachliche Auftrag dieser Scheibe: die **Klartext-Mail**
(`render_outlook_plain()`) zeigt aktuell **nur** das Tageswort ohne jede
Uhrzeit — ein Nachtgewitter erscheint dort **nie**, auch nicht in Fall A
(kein Tagesgewitter, Nacht hoch 0 Uhr). Ziel: die Ausblick-Zeile trägt
künftig zwei getrennte Aussagen — eine Tages-Aussage (Wort **und** Uhrzeit
aus demselben Tagesfenster) und, falls vorhanden, eine Nacht-Aussage —
konsistent in allen drei Kanälen.

**Verhältnis zu #1651:** #1651 (bereits live) behandelt die morgendliche
„Gewitter-Vorschau" (Fließtext-Satz) mit einer **separaten**
Nachtwetter-Zeitreihe als Autorität. Diese Scheibe ist strukturell anders:
Tag- und Nachtwerte stecken hier bereits **beide** in derselben
`hourly_thunder`-Reihe (`row["hourly_thunder"]`, ungefiltert über alle
Segmentstunden) — es gibt keine zweite Quelle, die Reihe muss nur nach
Tag/Nacht **getrennt ausgewertet** statt nur auf den Peak reduziert werden.
Der veraltete Entwurf in `docs/specs/modules/fix_1651_vorschau_zeitfenster.md`
Abschnitt 4 (Zeilen 196–220) ist explizit überholt und wird **nicht**
übernommen.

## Source

- **File:** `src/output/renderers/email/helpers.py` —
  `format_trend_tokens()` (zentrale SSoT für alle Trend-Tokens)
- **File:** `src/output/renderers/email/outlook.py` — `build_outlook_row()`,
  `render_outlook_table()`, `render_outlook_plain()`
- **File:** `src/output/renderers/narrow.py` — `_outlook_lines()`
- **File:** `src/services/trip_report_scheduler.py` — `_build_stage_trend()`

Schicht: **Python-Core** (`src/output/renderers/`, `src/services/`). Kein
Go-, kein Frontend-Code betroffen.

## Estimated Scope

- **LoC:** ~70 Produktivcode + ~200 Tests (Kern-Suite, neuer Golden-Snapshot,
  Compare-Paritäts-Ergänzung) → **voraussichtlich über dem 250-Zeilen-
  Workflow-Limit**; `workflow.py set-field loc_limit_override 500` bei
  Bedarf in `/50-implement` einholen.
- **Files:** 4 Produktivdateien (MODIFY), 1 neue Testdatei (CREATE), 1–2
  bestehende Testdateien (MODIFY, Compare-Parität)
- **Effort:** medium

## Dependencies

| Entity | Type | Purpose |
|---|---|---|
| `app.day_window.hour_in_window()` | vorhanden | Wrap-aware Stunden-Zugehörigkeit zum konfigurierten Tagesfenster — Grundlage der Tag/Nacht-Trennung dieser Scheibe |
| `app.day_window.resolve_configured_window()` | vorhanden | Löst `trip.report_config.day_window_start_hour/end_hour` auf feste Grenzen auf (Default 4/19) — bereits identisch genutzt in `_build_thunder_forecast_from_trend_or_fetch()`, `trip_report_scheduler.py:1743` |
| `app.day_window.DAY_WINDOW_START_HOUR` / `DAY_WINDOW_END_HOUR` | vorhanden | Default-Fenstergrenzen (4/19) für Aufrufer, die kein Fenster durchreichen (z.B. Compare, ältere Tests) |
| `output.tokens.metrics.render_threshold_peak_value()` | vorhanden, **unverändert** | Wird für Gewitter jetzt **zweimal** aufgerufen (Tag-Samples, Nacht-Samples) statt einmal über die volle Reihe — die Funktion selbst bekommt keinen neuen Parameter, bleibt für R/W/G byte-identisch |
| `output.renderers.email.helpers.format_trend_tokens()` | MODIFY | Zentrale Stelle der neuen Tag/Nacht-Berechnung — einzige SSoT für HTML, Klartext und Telegram |
| `output.renderers.email.outlook.build_outlook_row()` | MODIFY | Nimmt Fenstergrenzen entgegen und reicht sie additiv ins Row-Dict durch |
| `services.trip_report_scheduler.TripReportSchedulerService._build_stage_trend()` | MODIFY | Löst das Fenster auf und übergibt es an `build_outlook_row()` |

## Implementation Details

### 1. Tag/Nacht-Split in `format_trend_tokens()` (neue SSoT-Logik)

`stage["hourly_thunder"]` (Tupel von `HourlyValue(hour, value)`, `value` =
`thunder_label_value()`-Ordinal) wird über `hour_in_window()` in zwei
Teilmengen zerlegt:

```python
from app.day_window import (
    hour_in_window, DAY_WINDOW_START_HOUR, DAY_WINDOW_END_HOUR,
)

win_start = stage.get("day_window_start_hour", DAY_WINDOW_START_HOUR)
win_end = stage.get("day_window_end_hour", DAY_WINDOW_END_HOUR)

hourly_thunder = stage.get("hourly_thunder") or ()
_day_samples = tuple(s for s in hourly_thunder
                      if hour_in_window(s.hour, win_start, win_end))
_night_samples = tuple(s for s in hourly_thunder
                        if not hour_in_window(s.hour, win_start, win_end))

thunder_day_token = render_threshold_peak_value(
    "TH", _day_samples, threshold=thunder_thr, is_level=True,
    level_labels=_TREND_THUNDER_LABELS,
)
thunder_night_token = render_threshold_peak_value(
    "TH", _night_samples, threshold=thunder_thr, is_level=True,
    level_labels=_TREND_THUNDER_LABELS,
)
```

`thunder_thr` und `_TREND_THUNDER_LABELS` sind die bereits vorhandenen
Variablen der Funktion (unverändert). Beide neuen Tokens werden dem
Rückgabe-Dict **additiv** hinzugefügt: `thunder_day_token`,
`thunder_night_token`.

**Das bestehende `thunder_token` (24h-Peak über die volle Reihe) bleibt
unverändert** — byte-identisch berechnet wie heute. Grund: mehrere
bestehende Tests (`tests/tdd/test_issue_640_trend_threshold_times.py`,
`tests/tdd/test_thunder_mention_threshold_shared.py`) prüfen exakt diesen
Wert; ein Umbau auf den Tages-Wert würde sie fälschlich rot machen, obwohl
sie ein anderes, weiterhin gültiges Verhalten (voller 24h-Peak als
eigenständige Größe) bewachen. Die drei Ziel-Renderer lesen künftig
`thunder_day_token`/`thunder_night_token` statt `thunder_token`.

Fensterbestimmung als neue, additive Stage-Dict-Schlüssel
(`day_window_start_hour`/`day_window_end_hour`) statt Pflichtparameter:
fehlen sie (ältere Aufrufer, Compare, Bestandstests), gilt der Default 4/19
— identisch zum heutigen impliziten Verhalten der Gehzeit-Klemmung.

### 2. `build_outlook_row()` reicht das Fenster durch

Zwei neue optionale Keyword-Parameter:

```python
def build_outlook_row(
    summary, points, weekday, tz, *,
    sms_thresholds: Optional[dict] = None,
    metrics: Optional[list] = None,
    day_window_start_hour: Optional[int] = None,
    day_window_end_hour: Optional[int] = None,
) -> dict:
    ...
    optional = {
        ...  # bestehende Einträge unverändert
        "day_window_start_hour": day_window_start_hour,
        "day_window_end_hour": day_window_end_hour,
    }
```

Werden sie nicht übergeben (`None`), filtert der bestehende
`{k: v for k, v in optional.items() if v is not None}`-Mechanismus sie aus
dem Row-Dict — `format_trend_tokens()` greift dann auf den Default 4/19
zurück. Das ist reine Additivität: kein bestehender Aufrufer, der die neuen
Parameter nicht kennt, ändert sein Verhalten (Parität zu
`tests/tdd/test_trip_outlook_parity.py`).

### 3. `_build_stage_trend()` löst das konfigurierte Fenster auf

Direkt vor dem bestehenden `build_outlook_row(...)`-Aufruf
(`trip_report_scheduler.py:1663`):

```python
from app.day_window import resolve_configured_window
_rc = getattr(trip, "report_config", None)
_win_start, _win_end = resolve_configured_window(
    getattr(_rc, "day_window_start_hour", None),
    getattr(_rc, "day_window_end_hour", None),
)
row = build_outlook_row(
    agg, _flat_points, WEEKDAYS_DE[stage.date.weekday()], _tz,
    sms_thresholds=_sms_thr,
    day_window_start_hour=_win_start, day_window_end_hour=_win_end,
)
```

Identischer Aufruf-Musters wie bereits in
`_build_thunder_forecast_from_trend_or_fetch()` (Zeile ~1743) — keine neue
Logik, nur eine zweite Verwendungsstelle derselben, bereits vorhandenen
Funktion. Kein neuer Netzabruf.

### 4. HTML-Zelle (`render_outlook_table`) — Fehler 1 + 2 behoben

**Vorschlag, PO-Freigabe für das exakte Zellformat bei Spec-Approval
eingeholt (bestätigt 2026-08-09):**

```python
day_part = None
if thunder_level in ("LOW", "MED", "HIGH"):
    day_part = _THUNDER_LEVEL_LABEL[thunder_level]
    d_tok = tokens.get("thunder_day_token", "-")
    _at = _re.search(r"@(\d+)", d_tok) if d_tok != "-" else None
    if _at:
        day_part += f" @{_at.group(1)}"

night_part = None
n_tok = tokens.get("thunder_night_token", "-")
if n_tok != "-":
    _m = _re.match(r"^([a-zA-Zäöü]+)@(\d+)", n_tok)
    if _m:
        night_part = f"nachts {_m.group(1)} @{_m.group(2)}"

if day_part and night_part:
    gew_str = f"{day_part} · {night_part}"
elif day_part:
    gew_str = day_part
elif night_part:
    gew_str = night_part
else:
    gew_str = "–"

if gew_str != "–":
    _hail_note = _format_hail_note(stage.get("hail"))
    if _hail_note:
        gew_str += f" · {_hail_note}"
```

Fehler 1 behoben: die Uhrzeit im Tagesteil kommt jetzt aus
`thunder_day_token` (dasselbe Fenster wie das Wort), nicht mehr aus dem
ungefilterten `thunder_token`. Fehler 2 behoben: Nachtangabe erscheint
zusätzlich zur Tagesangabe, nicht nur wenn sie der stärkere Wert ist —
auch dann, wenn der Tag „–" ist (Fall A), ersetzt der Nacht-Teil das reine
„–" statt es zu verschlucken. Der Hagel-Zusatz hängt neu an jeder
nicht-leeren Zelle (bisher nur bei Tagesgewitter).

**Known Limitation / bewusster Non-Goal dieser Scheibe:** die
Hintergrundfarbe der Zelle (`_THUNDER_LEVEL_BG`) bleibt ausschließlich vom
Tageswert abgeleitet — ein reines Nachtgewitter färbt die Zelle nicht.
Kann bei Bedarf als eigene, kleine Folge-Änderung entschieden werden.

### 5. Klartext-Zeile (`render_outlook_plain`) — Kernauftrag des Issues

`tok['thunder_plain']` bleibt als Tages-Wort-Baustein unverändert (Quelle
1, kein Zeitanteil). Neu: derselbe Nacht-Zusatz wie in der HTML-Zelle wird
angehängt, wenn `thunder_night_token != "-"`:

```python
line = (
    f"{weekday:<3} {name_field}{tok['temp_str']:<8} "
    f"{precip_str:<5} {tok['wind_str']:<5} {tok['thunder_plain']}"
)
n_tok = tok.get("thunder_night_token", "-")
if n_tok != "-":
    _m = _re.match(r"^([a-zA-Zäöü]+)@(\d+)", n_tok)
    if _m:
        line += f" · nachts {_m.group(1)} @{_m.group(2)}"
```

Damit zeigt die Klartext-Mail **erstmals** eine Nachtangabe mit Uhrzeit —
das war die eigentliche, im Issue benannte Lücke.

### 6. Telegram (`narrow._outlook_lines`) — von zufällig zu strukturell korrekt

```python
dt = tok.get("thunder_day_token", "-")
nt = tok.get("thunder_night_token", "-")
if dt != "-" or nt != "-":
    day_txt = f"⚡{dt}" if dt != "-" else tok["thunder_plain"]
    if nt != "-":
        day_txt += f" · nachts {nt}"
    thunder_part = day_txt
else:
    thunder_part = tok["thunder_plain"]
```

Ersetzt `tok["thunder_token"]` (24h-Peak) durch die Tag/Nacht-getrennte
Fassung. Fall C (Tag hoch 14, Nacht mittel 22) zeigte bisher zufällig
richtig `⚡hoch@14`, weil der Tag der stärkere Wert war — künftig ist das
Ergebnis strukturell garantiert, nicht zufällig, und Fall B zeigt neu
`⚡mittel@14 · nachts hoch@0` statt nur `⚡hoch@0` (das Tagesgewitter kam
bisher nie durch).

## Expected Behavior

- **Input:** `stage`-Dict mit `hourly_thunder` (ungefilterte Stunden-
  Zeitreihe der Etappe) und optional `day_window_start_hour`/
  `day_window_end_hour`.
- **Output:** HTML-Zelle, Klartext-Zeile und Telegram-Zeile zeigen Tages-
  und Nachtgewitter getrennt, jeweils mit Wort und Uhrzeit aus demselben
  Zeitfenster; kein Gewitter → unverändert „–"/„⚡–"/„kein".
- **Side effects:** keine — reine Rendering-Funktionen, kein Netz-, kein
  DB-Zugriff, kein neuer Fetch.

## Acceptance Criteria

- **AC-1:** Given eine Etappe mit Tagesgewitter „mittel" um 14 Uhr innerhalb
  des konfigurierten Tagesfensters / When die Ausblick-Tabelle gerendert
  wird / Then zeigt die Gewitter-Zelle „mittel @14" mit einer Uhrzeit, die
  nachweislich aus demselben Tagesfenster stammt wie das Wort (nicht mehr
  aus der ungefilterten 24-Stunden-Reihe).
  - Test: echter Pfad `build_outlook_row()` → `format_trend_tokens()` →
    `render_outlook_table()` mit Fixture-Zeitreihe, deren Nachtstunde ein
    anderes Level trägt als 14 Uhr — Zelle darf NICHT die Nachtstunde als
    Tages-Uhrzeit zeigen.

- **AC-2:** Given eine Etappe mit Tagesgewitter „mittel" 14 Uhr UND
  Nachtgewitter „hoch" 0 Uhr (Fall B der Issue-Messung) / When Ausblick-
  Tabelle UND Telegram-Ausblick gerendert werden / Then zeigen beide sowohl
  die Tages- als auch die Nachtangabe gleichzeitig, nicht nur das stärkere
  Ereignis.
  - Test: gerenderter HTML- und Telegram-Text enthält nachweisbar sowohl
    „mittel"/„14" als auch „hoch"/„0" — kein Verschwinden des schwächeren
    Ereignisses.

- **AC-3:** Given dieselbe Fall-B-Konstellation / When die Klartext-
  Ausblick-Zeile gerendert wird / Then enthält sie erstmals eine
  Nachtangabe mit Uhrzeit (bisher zeigte sie ausschließlich das Tageswort
  ohne jede Zeit- oder Nachtinformation).
  - Test: `render_outlook_plain()`-Ausgabe vor und nach dem Fix vergleichen
    — vorher keine Uhrzeit/Nacht-Erwähnung, nachher beides vorhanden.

- **AC-4:** Given eine Etappe ohne Tagesgewitter aber mit Nachtgewitter
  „hoch" 0 Uhr (Fall A) / When alle drei Kanäle gerendert werden / Then
  zeigen HTML-Zelle, Klartext-Zeile und Telegram-Zeile die Nachtangabe
  sichtbar, statt sie durch ein reines „–"/„⚡–" zu verschlucken.
  - Test: alle drei Renderer-Ausgaben enthalten „hoch"/„0", keine zeigt nur
    den bloßen Leerwert.

- **AC-5:** Given eine Etappe ganz ohne Gewitter (Tag und Nacht `NONE`) /
  When alle drei Kanäle gerendert werden / Then bleiben die Zellen
  unverändert „–"/„⚡–"/„kein" — byte-identisch zum Stand vor dieser
  Änderung.
  - Test: Nullfall-Fixture, Ausgabe-Vergleich mit dem heutigen (Vor-Fix)
    Rendering-Ergebnis.

- **AC-6:** Given der Compare-Ausblick (`metrics is not None`-Zweig in
  `build_outlook_row()`/`render_outlook_plain()`) / When eine Compare-Mail
  mit denselben Gewitterdaten gerendert wird / Then bleibt die Compare-
  Ausgabe byte-identisch zum Stand vor dieser Änderung.
  - Test: bestehender Compare-Paritätstest (`test_trip_outlook_parity.py`
    bzw. `test_compare_outlook*.py`) bleibt grün, ergänzt um einen Lauf mit
    Tag+Nacht-Gewitterdaten, der zeigt, dass `cells`/`format_outlook_value`
    unverändert bleiben.

- **AC-7:** Given Niederschlag-, Wind- und Böen-Tokens, weiterhin über
  genau einen unveränderten Aufruf von `render_threshold_peak_value()`
  berechnet / When die bestehenden Tests für `precip_token`/`wind_token`/
  `gust_token` laufen / Then bleiben sie unverändert grün — die
  Tag/Nacht-Trennung ist ausschließlich gewitterspezifisch neu
  (`thunder_day_token`/`thunder_night_token`), `render_threshold_peak_value()`
  selbst bekommt keinen neuen Parameter.
  - Test: `tests/tdd/test_issue_640_trend_threshold_times.py` läuft
    unverändert grün (Regressionsnachweis per bestehender Suite).

- **AC-8:** Given kein bisheriger Golden-Snapshot mit Gewitter der Stufe
  „mittel"/„hoch" existiert (`grep` über `tests/golden/` → 0 Treffer) /
  When die Test-Suite um einen neuen Snapshot-Testfall ergänzt wird / Then
  existiert mindestens ein versionierter Snapshot, der Tag- **und**
  Nachtgewitter ab Stufe „mittel" in derselben Mail zeigt, sodass diese
  Fehlerklasse künftig automatisch auffällt.
  - Test: neuer Eintrag unter `tests/golden/email/` (oder Erweiterung der
    bestehenden Golden-Suite), der beim Rückfall auf altes Verhalten rot
    wird.

## Known Limitations

- Hintergrundfarbe der HTML-Zelle bleibt tagesbasiert (s. Implementation
  Details §4) — ein reines Nachtgewitter färbt die Zelle nicht ein.
- `hour_in_window()` kennt nur Ortszeit-Stunden (0–23), kein Kalenderdatum
  — bei Etappen, deren `_flat_points` mehr als 24 Stunden abdecken, ist die
  Tag/Nacht-Zuordnung wie im Bestand rein stundenbasiert (vorbestehende
  Einschränkung, nicht neu eingeführt durch diese Scheibe).
- Rohe Programmnamen `MED`/`HIGH` in der Klartext-Mail bleiben bestehen —
  eigenes Ticket #1654.
- Exaktes Zellformat (Trennzeichen „·", Reihenfolge Tag-vor-Nacht,
  Wortwahl „nachts {stufe} @{h}") ist ein **Vorschlag** dieser Spec, PO hat
  ihn am 2026-08-09 bestätigt.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine neue — betrifft ADR-0025 (Gewitter-Stufen-Domäne),
  keine Änderung der dortigen Entscheidung, nur konsistentere Anwendung.
- **Rationale:** Die Trennung von Tag- und Nachtwerten ist eine reine
  Rendering-/Aggregations-Korrektur (dieselbe Quelle wird korrekt
  ausgewertet statt eine neue Datenquelle einzuführen) — keine neue
  Grundsatzentscheidung nötig.

## Changelog

- 2026-08-09: Initial spec created
- 2026-08-09: PO-Freigabe ('approved') erhalten, Zellformat bestätigt
- 2026-08-10: Implementiert und über vier Adversary-Runden gehärtet, Verdict
  VERIFIED (130/130 Tests grün, 8/8 ACs bestätigt). Gefundene und behobene
  Lücken: **F001** (CRITICAL, R1→R2) Tagesgewitter verschwand hinter dem
  Nachtwert; **F002** (HIGH, R1→R2) Wort und Uhrzeit der HTML-Zelle aus
  verschiedenen Zeitfenstern; **F003** (CRITICAL, R1→R2) Compare-Klartext-
  Zweig unbeabsichtigt mitverändert; **F004** (HIGH, R2→R3) Klartext-
  Tageswort blieb am Gehzeit-geklemmten Aggregat statt am Tagesfenster;
  **Telegram-Falsch-Positiv** (R2→R3) Aggregat zeigte HIGH, obwohl die
  Stundenreihe das nur nachts erreichte; **F005** (R3→R4) HTML/Klartext
  verwarfen den Spitzenwert bei Eskalation innerhalb desselben Tag-/
  Nachtfensters, Telegram zeigte ihn korrekt (Drei-Wege-Uneinigkeit) — Fix:
  neuer Helfer `_thunder_token_parts()` (`email/outlook.py:38-59`), von
  allen vier Fundstellen genutzt. Status auf `implemented` gesetzt.
