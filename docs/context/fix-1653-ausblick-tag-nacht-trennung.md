# Context: fix-1653-ausblick-tag-nacht-trennung

## Request Summary

Issue #1653: Die Gewitter-Zelle des Mehrtages-Ausblicks (Abend-Mail-Tabelle,
Abend-Mail-Klartext, Telegram-„Ausblick"-Bubble) verrührt zwei verschiedene
Zeiträume zu einer Aussage und zeigt nie beide — Tag- und Nachtgewitter
derselben Etappe schließen sich gegenseitig aus. Ziel: die Zelle trägt zwei
getrennte Aussagen (Tag + ggf. Nacht), jede aus ihrem eigenen Zeitfenster,
in beiden Kanälen.

## Root Cause (gemessen, drei Fehler in derselben Zelle)

Eine Ausblick-Zeile (`row`, gebaut von `build_outlook_row()`) trägt zwei
unabhängige Datenquellen für dieselbe fachliche Aussage „Gewitter":

1. **`row["thunder"]`** — `summary.thunder_level_max.name`
   (`outlook.py:371-372`). `summary` = `aggregate_stage(seg_weather)`
   (`trip_report_scheduler.py:1629`), aggregiert über `seg_weather`, das
   `_convert_trip_to_segments()` für die **Gehzeit-Segmente** der Etappe
   liefert (z.B. 08–17 Uhr) → **Gehzeit-geklemmt**.
2. **`row["hourly_thunder"]`** — abgeleitet aus `points`
   (`outlook.py:381-395`), das `_flat_points` ist: **alle** `dp` aus
   `sw.timeseries.data` über alle Segmente hinweg
   (`trip_report_scheduler.py:1649-1652`), **ohne** Zeitfenster-Filter →
   **ungefiltert über den ganzen von den Segmenten abgedeckten Zeitraum**
   (inkl. Nachtstunden, wenn die zugrundeliegende Zeitreihe sie enthält).

Aus (2) berechnet `format_trend_tokens()` (`email/helpers.py:970-989`) über
`render_threshold_peak_value()` (`tokens/metrics.py:29-67`) das
`thunder_token` — **immer nur der eine stärkste Wert (`peak = max(samples)`)
über die gesamte Reihe**, mit dessen Stunde. Es gibt keine Trennung nach
Tag/Nacht, keine zweite (Tag+Nacht getrennte) Berechnung.

**Drei konkrete Fehler, die daraus entstehen:**

| # | Fehler | Fundort |
|---|---|---|
| 1 | Wort (`thunder_word`, aus (1) Gehzeit-geklemmt) und Uhrzeit (aus `thunder_token`, aus (2) ungefiltert) werden kombiniert, obwohl sie aus verschiedenen Fenstern stammen | `outlook.py:199-211` (`render_outlook_table`, HTML): `gew_str = _THUNDER_LEVEL_LABEL[thunder_level]` (Quelle 1) `+= f" @{_at.group(1)}"` aus `t_tok` (Quelle 2, Regex auf `thunder_token`) |
| 2 | Nur der 24h-Peak wird gezeigt — ist die Nacht stärker, verschwindet das Tagesgewitter (und umgekehrt); **beide gleichzeitig werden nie gezeigt** | `tokens/metrics.py:49` (`peak = max(samples, ...)`) — strukturell, keine Tag/Nacht-Trennung in `render_threshold_peak_value()` |
| 3 | Rohe Programmnamen `MED`/`HIGH` statt `mittel`/`hoch` in der **Klartext**-Mail (`thunder_plain` aus `_THUNDER_MAP`, `email/helpers.py`) | **Out of Scope — eigenes Ticket #1654** |

**Telegram** (`narrow.py:571-586`, `_outlook_lines`) liest **ausschließlich**
`thunder_token` (Fehler 2 direkt, kein Fehler 1 da kein Wort+Uhrzeit-Mix,
sondern reines Token `⚡{Stufe}@{Stunde}` mit `_TREND_THUNDER_LABELS`
deutschen Wörtern). Betroffen von Fehler 2 identisch zur Mail.

**Plain-Text-Mail** (`render_outlook_plain`, `outlook.py:264-323`) zeigt
`tok['thunder_plain']` — rein wortbasiert (Quelle 1, Gehzeit-geklemmt),
zeigt daher **nie** eine Uhrzeit und **nie** die Nacht überhaupt (weder
Fehler 1 noch 2 sichtbar, aber Nachtgewitter komplett unsichtbar — das ist
der eigentliche Auftrag dieses Issues: Nachtangabe fehlt hier ganz).

## Warum es nie auffiel

Kein Golden-Snapshot (`tests/golden/`) enthält ein Gewitter der Stufe
`MED`/`HIGH` (`grep` → 0 Treffer). Fälle B/C (aus der Issue-Messtabelle)
wurden nie gerendert und nie getestet.

## Related Files

| File | Relevance |
|------|-----------|
| `src/output/renderers/email/outlook.py` | `build_outlook_row()` (Row-Bau, Quelle 1+2 fließen hier zusammen), `render_outlook_table()` (HTML-Zelle, Fehler 1), `render_outlook_plain()` (Klartext-Zelle) |
| `src/output/renderers/email/helpers.py` | `format_trend_tokens()` — zentrale SSoT für alle Trend-Tokens (HTML/Klartext/Telegram/SMS), Fehler-2-Ursprung (`thunder_token`) |
| `src/output/tokens/metrics.py` | `render_threshold_peak_value()` — generischer Peak-Only-Mechanismus, betrifft auch R/W/G-Token (nicht nur Gewitter), Änderung hier hat Streuwirkung |
| `src/output/renderers/narrow.py` | `_outlook_lines()` (Telegram-Ausblick-Bubble), liest `thunder_token` direkt |
| `src/services/weather_metrics.py` | `aggregate_stage()` — Quelle 1 (Gehzeit-Klemmung), Level-2-Aggregation |
| `src/services/trip_report_scheduler.py` | `_build_stage_trend()` (Z. 1552-1670+) — baut `agg` (Quelle 1) und `_flat_points` (Quelle 2, ungefiltert) und ruft `build_outlook_row()` |
| `src/app/day_window.py` | Bereits vorhandene Fenster-Logik (`resolve_configured_window()`, `hour_in_window()`) — dieselbe Quelle, auf der die Gehzeit-Klemmung beruht; enthält seit #1651 `night_addendum()`-Muster (Vorbild, nicht identisch) |
| `src/output/metric_format.py` | `THUNDER_LABEL_DE` — geteilte deutsche Wortquelle (`leicht`/`mittel`/`hoch`), bereits von der HTML-Tabelle genutzt, NICHT von der Klartext-Zelle (→ #1654) |

## Existing Patterns

- **#1651 (morgendliche „Gewitter-Vorschau", geschlossen 2026-08-09)** löst
  ein verwandtes, aber **anderes** Problem: dort geht es um den **Fließtext-
  Satz** außerhalb der Ausblick-Tabelle, und um Nachtstunden, die außerhalb
  eines *Tagesfensters* (04-19 Uhr) liegen, mit einer **separaten**
  Nachtwetter-Zeitreihe (`night_weather`, aus `fetch_night_weather()`) als
  maßgeblicher Quelle für die Autoritäts-Stunden 00:00-06:00.
  Die Ausblick-**Tabelle** ist strukturell anders: hier gibt es **keine**
  zweite Nachtwetter-Quelle — Tag- und Nachtwerte stecken bereits **beide**
  in derselben `hourly_thunder`-Reihe (ungefiltert, aus `_flat_points`).
  Das Problem hier ist nicht „fehlende Nachtquelle", sondern „eine
  gemeinsame Reihe wird nicht nach Tag/Nacht **getrennt** ausgewertet,
  sondern nur der Peak über alles genommen".
- Die Spec `docs/specs/modules/fix_1651_vorschau_zeitfenster.md` §„Integration
  Ausblick-Tabelle (Abend-Default) — VERSCHOBEN NACH #1653" (Abschnitt 4,
  Zeilen 196-220) enthält einen **veralteten** Entwurf für die Abend-Zelle
  (`night_thunder`-Zusatzfeld analog zum Morgen-Text). Die Spec selbst
  markiert ihn ausdrücklich als überholt: „die dort gemessenen Altfehler der
  Zelle ändern den Entwurf" — er geht davon aus, dass Tag und Nacht bereits
  sauber getrennt vorliegen, was laut #1653-Messung nicht der Fall ist
  (Fehler 1+2 bestehen unabhängig von jeder Nacht-nach-Tagesfenster-Frage).
  **Nicht 1:1 übernehmbar, aber als Präzedenz für „additive Zell-Erweiterung
  statt Ersetzung" relevant.**
- `render_threshold_peak_value()` ist die **geteilte** Quelle für alle
  `@`-Zeit-Tokens (Niederschlag R, Wind W, Böe G, Gewitter TH) — eine
  Tag/Nacht-Trennung dort betrifft **nur** Gewitter, wenn sie gewitter-
  spezifisch eingebaut wird (z.B. neuer Parameter oder neue Hilfsfunktion),
  nicht generisch für alle vier Symbole.

## Dependencies

- **Upstream:** `aggregate_stage()` (Gehzeit-Aggregat), `_flat_points`
  (ungefilterte Rohreihe je Etappe) — beide bereits vorhanden, keine neuen
  Netzabrufe nötig (im Unterschied zu #1651, das eine zusätzliche
  `night_weather`-Quelle brauchte).
- **Downstream:** `render_outlook_table()` (HTML-Mail), `render_outlook_plain()`
  (Klartext-Mail), `narrow._outlook_lines()` (Telegram) — alle drei müssen
  konsistent dieselbe neue Tag/Nacht-getrennte Struktur lesen (SSoT-Prinzip,
  `format_trend_tokens()` bleibt die zentrale Stelle).
- **Nicht betroffen:** SMS (zeigt Ausblick-Zelle nicht), Compare-Ausblick
  (`metrics is not None`-Zweig in `build_outlook_row()`/`render_outlook_plain()`
  — eigener Spaltenformat-Pfad, Trip/Compare-Teilungs-Invariante gilt, aber
  Compare hat keine Gewitter-Zelle in diesem Format).

## Existing Specs

- `docs/specs/modules/multi_day_trend.md` (v5.0, status `implementing`) —
  Entity-Spec für die Ausblick-Tabelle selbst, muss um die Tag/Nacht-
  Trennung der Gewitter-Zelle ergänzt werden.
- `docs/specs/modules/fix_1651_vorschau_zeitfenster.md` (v2.0) — verwandt,
  s.o. „Existing Patterns"; AC-2/AC-10 dort sind explizit „verschoben nach
  #1653" und in dieser Form **nicht** mehr gültig (die Annahmen hinter ihnen
  sind durch die #1653-Messung widerlegt).
- ADR-0025 (laut Issue „berührt") — referenziert Vorschau/Ausblick-Vergleich,
  vor Umsetzung gegenlesen falls Vergleichslogik (`_thunder_entry_from_trend_row`
  o.ä.) mit angefasst wird.

## Risks & Considerations

- **`render_threshold_peak_value()` ist geteilter Code** (R/W/G/TH) — jede
  Änderung dort für „mehrere Peaks" muss gewitter-spezifisch bleiben (z.B.
  neuer Parameter oder eigene Funktion für Tag/Nacht-Split), sonst brechen
  Niederschlag/Wind/Böe-Tokens, die diese Trennung nicht brauchen.
- **Kein Golden-Snapshot mit `MED`/`HIGH`** — muss in dieser Scheibe entstehen,
  sonst bleibt genau diese Fehlerklasse weiter unsichtbar (PO-Kommentar im
  Issue nennt das explizit als Lücke).
- **Test-Fallstricke aus dem Issue-Kommentar (Vorarbeit aus #1651-TDD-RED):**
  - `TripReportSchedulerService._build_stage_trend()` läuft offline über
    `GZ_TEST_FIXTURE_DIR` (72-Stundenpunkte-Fixtures, Go-Format, #263) — echter
    Pfad statt handgebauter Zeile.
  - 🔴 **`reset_shared_weather_cache_for_tests()` zwingend zwischen
    Szenarien** — sonst liest der zweite Test die Reihe des ersten aus dem
    geteilten Roh-Cache und wird grün aus falschem Grund (im #1651-RED-Lauf
    tatsächlich passiert, nur durch Zufalls-Reihenfolge entdeckt).
  - Nachtquelle und Folgeetappe auf **verschiedene** Fixture-Orte legen,
    damit eine geprüfte Angabe nachweisbar nur aus der Nacht-Zeitreihe
    stammen kann.
  - Alle drei Kanäle im Testlauf abschalten (`no_channels`), kein echter
    Versand.
- **Zielformat ist im Issue nur ein Vorschlag, nicht spezifiziert** — die
  Spec-Phase muss die exakte Darstellung für HTML-Zelle, Klartext-Zeile und
  Telegram-Zeile PO-seitig festlegen (Trennzeichen, Reihenfolge Tag/Nacht,
  Verhalten wenn nur eines von beiden vorliegt — analog zum bereits
  PO-entschiedenen Fließtext-Muster aus #1651: „Starkes Gewitter erwartet ab
  14:00, nachts mittleres Gewitter ab 22:00"). **Erledigt:** PO hat das
  Zellformat aus der Spec bei der Freigabe 2026-08-09 bestätigt.
- **Trip/Compare-Teilungs-Invariante (CLAUDE.md):** `build_outlook_row()` und
  `format_trend_tokens()` sind geteilter Code zwischen Trip und Compare —
  Änderungen müssen für den Compare-`metrics`-Zweig neutral bleiben (additiv,
  wie bereits bei Hagel/#1475 gehandhabt).
