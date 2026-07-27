# Context: fix-1378-compare-zeitbasis

Issue: #1378 (S3 Scheibe C von Epic #1372, Dach #1374)
Erhoben: 2026-07-27, Basis-Stand `9aabba19` (= `origin/main`, = Staging)

## Request Summary

Die Ortsvergleichs-Mail beschriftet die Stundenzeilen mit der Rohzeit des
Datenpunkts statt mit der Ortszeit. Sie soll denselben Weg gehen wie
Trip-Briefing und Ausblick: eine Zeitbasis, ein Auflöser.

## Nachweis an echter Staging-Mail (Vorbedingung erfüllt)

**Ein** Versand über den Einzelversand-Endpoint (`POST
127.0.0.1:8001/api/scheduler/compare-presets/cp-21e198c1b74020dd/send?user_id=default`),
Preset „Validator-1025 Compare" (Innsbruck/Stubai/Zillertal, alle
`Europe/Vienna` = UTC+2; Server läuft `Etc/UTC`). Mail zugestellt an
`gregor-test@henemm.com`, `X-GZ-Mail-Type: compare`, Date
`Mon, 27 Jul 2026 04:58:44 +0000`. Ausgewertet per IMAP (BODY.PEEK).

Preset-Tagesfenster: `day_window_start_hour=9`, `day_window_end_hour=16`.

**Beide Mail-Teile zeigen die Zeilen `09:00` … `16:00`.** Gegenprobe der
Temperaturwerte gegen `api.open-meteo.com` für Innsbruck mit
`timezone=Europe/Vienna`:

| Mail-Zeile | Mail-Wert | Ortszeit 09–16 | Ortszeit 11–18 |
|---|---|---|---|
| 09:00 | 23° | 21.3 | **22.9** |
| 10:00 | 23° | 21.6 | **23.0** |
| 11:00 | 24° | 22.9 | **23.9** |
| 12:00 | 24° | 23.0 | **23.8** |
| 13:00 | 24° | 23.9 | **23.5** |
| 14:00 | 23° | 23.8 | **23.4** |
| 15:00 | 24° | 23.5 | **23.7** |
| 16:00 | 24° | 23.4 | **23.8** |

Gerundet stimmt die Mail über alle acht Stunden **ziffernweise** mit der
Ortszeit-Reihe **11–18 Uhr** überein, mit der Reihe 09–16 nicht. Der UV-Verlauf
stützt das (Mail endet bei UV 2 → 1, typisch für 17/18 Uhr Ortszeit).

**Abweichung: +2 Stunden (UTC → Europe/Vienna, Sommerzeit).** Nutzersichtbare
Folge: Wer „9 bis 16 Uhr" einstellt, bekommt die Werte von 11 bis 18 Uhr
Ortszeit — falsch beschriftet als 9 bis 16.

## Ursache: zwei Stellen, ein Defekt

`dp.ts` ist per Hausnorm **naive UTC** (`models.py:146-157`, #1345 — aware
Zeitstempel werden an der Provider-Grenze auf naiv/UTC gestrippt).

| # | Stelle | Code | Wirkung |
|---|---|---|---|
| 1 | **Auswahl** | `services/comparison_engine.py:53,59-60` — `start_hour <= dp.ts.hour <= end_hour` | Tagesfenster greift auf UTC-Stunden; es werden die falschen Datenpunkte geholt |
| 2a | **Beschriftung HTML** | `email/compare_html.py:644` — `dp.ts.strftime("%H")` | UTC-Stunde als Zeilenbeschriftung |
| 2b | **Beschriftung Klartext** | `renderers/comparison.py:229` — `dp.ts.strftime("%H:%M")` | dito, zweiter Mail-Teil |

Wichtig: Ein reiner Beschriftungs-Fix wäre **falsch** — er würde die Mail
korrekt auf „11–18" umbeschriften, dem Nutzer aber weiterhin nicht sein
eingestelltes Fenster liefern. Auswahl und Beschriftung müssen gemeinsam auf
Ortszeit.

## Existierende Muster (Trip = Vorbild)

- `output/renderers/day_window.py:148-184` — Trip filtert das Tagesfenster über
  `local_hour(dp.ts, tz)`, nicht über `dp.ts.hour`.
- `email/helpers.py:93,142` — Trip beschriftet über `local_hour(dp.ts, tz)`.
- `utils/timezone.py:26` — `tz_for_coords(lat, lon)` (TimezoneFinder,
  Fallback UTC) ist der **etablierte** Auflöser: Alarm-Renderer
  (`alert/project.py:147`), `notification_service.py` (6 Stellen),
  `trip_alert.py`.
- `utils/timezone.py` Kopf: „Internal pipeline stays 100% UTC — conversion
  happens only at render time." Genau das verletzen die drei Stellen oben.

## Zweiter Auflöser — Befund gegen die Ticket-Annahme

Das Ticket nennt den 3-Tages-Ausblick als korrekt rechnende Referenz
(`compare_html.py:746-753`). Der Ausblick nutzt aber einen **anderen** Weg als
der Trip: das gespeicherte Feld `Location.timezone` (`app/user.py:64`),
Fallback `UTC`.

Gemessen an den drei Staging-Orten: `timezone` ist bei allen **`None`**. Der
Ausblick fällt damit ebenfalls auf UTC zurück — er nimmt den richtigen Weg,
bekommt aber keine Daten. Er ist also **kein** verlässliches Vorbild.

Zusätzlich zeigt der Ausblick eine Uhrzeit nur beim Gewitter-@-Token
(`email/outlook.py:281`); in der Nachweis-Mail gab es kein Gewitter, weshalb
die im Ticket beschriebene Diskrepanz *innerhalb* der Mail dort gar nicht
sichtbar wird. Der reale Defekt ist die Abweichung gegen die Ortszeit, nicht
die Abweichung gegen den Ausblick.

Konsequenz für die Umsetzung: **ein** Auflöser für alle vier Stellen (Auswahl,
HTML-Stunden, Klartext-Stunden, Ausblick), aufgebaut auf `tz_for_coords` mit
`Location.timezone` als Vorrang, wenn gesetzt. Kein dritter Weg.

## Related Files

| Datei | Relevanz |
|---|---|
| `src/services/comparison_engine.py:38-62` | Fensterfilter auf `dp.ts.hour` — Auswahlfehler |
| `src/output/renderers/email/compare_html.py:629-660` | `_render_hour_row`, HTML-Beschriftung |
| `src/output/renderers/email/compare_html.py:741-760` | `_build_location_outlook_rows`, zweiter Auflöser |
| `src/output/renderers/comparison.py:209-235` | Klartext-Stundenblock |
| `src/utils/timezone.py` | `tz_for_coords`, `local_hour`, `local_fmt` |
| `src/output/renderers/day_window.py` | geteilter Trip-Fensterauflöser (Vorbild) |
| `src/app/user.py:64,117` | `Location.timezone`, `LocationResult` |
| `src/app/models.py:146-157` | Hausnorm naive UTC (#1345) |
| `src/services/report_config_resolver.py:178-191` | `resolve_compare_time_window` |

## Dependencies

- **Upstream:** `ComparisonEngine.run()` liefert `LocationResult` mit
  `hourly_data`/`outlook_hourly_data`; die Orts-Koordinaten stehen an
  `loc.location.lat/lon`.
- **Downstream:** `render_compare_email()` (HTML + Klartext), Vorschau
  (`compare_preview_service.py`) und Versand
  (`scheduler_dispatch_service.py`) teilen sich Engine und Renderer — ein Fix
  wirkt auf beide. Telegram/SMS-Compare-Renderer (`comparison.py:375ff`)
  sind zu prüfen.

## Existing Specs

- `docs/specs/modules/epic_1372_metrik_zielbild.md` (falls vorhanden) / Epic #1372
- ADR-0035 (Tagesfenster, aus #1361 S1b)
- `docs/reference/mail_validators.md` — Pflicht-Validator liest nur den
  HTML-Teil; der Klartext-Teil ist Prüf-blind (Scheibe-B-Erfahrung, #1366)

## Risks & Considerations

1. **Klartext bleibt Prüf-blind.** `email_spec_validator.py` liest nur HTML.
   Der Nachweis muss den Klartext-Teil eigenständig prüfen (in Scheibe B
   genau daran gescheitert).
2. **Orte in verschiedenen Zeitzonen.** Nach dem Fix zeigen die Stundenblöcke
   je Ort dieselbe Ortsstunde, aber unterschiedliche absolute Zeitpunkte. Das
   ist fachlich richtig (Vor-Ort-Urlauber denkt in Ortszeit), muss aber in der
   Spec stehen — die Übersichtstabelle vergleicht dann Werte, die nicht
   zeitgleich sind.
3. **Tagesgrenze verschiebt sich.** Das Fenster wird auf Ortsstunden
   angewandt; für UTC+2 verschiebt sich der geholte Rohdatenbereich um 2
   Stunden nach vorn. `COMPARE_FORECAST_HOURS` muss weit genug reichen, sonst
   fehlen am Fensterende Datenpunkte.
4. **Zeitzonen-Fallback.** Orte ohne `timezone`-Feld und mit unauflösbaren
   Koordinaten fallen auf UTC — das darf nicht still sein wie bisher.
5. **Kopfzeile.** „Erstellt: 27.07.2026 04:58" ist Serverzeit (UTC), Ortszeit
   wäre 06:58. Verwandt mit #1383 — in der Spec zu entscheiden, ob mit
   drin oder abgegrenzt.
6. **Renderer-Commit-Gate #811** greift (`compare_html.py`, `comparison.py`):
   `test_issue_811_mode_matrix.py` grün + `briefing_mail_validator.py`-Lauf
   nötig, bevor committet werden kann.
7. **open-meteo-Kontingent** (#1329): pro Verifikation genau ein Versand.

## Nebenbefund (nicht Teil dieses Fixes)

Klartext-Kopfzeile zeigt den Wochentag englisch: „Datum: Monday, 27.07.2026"
(`comparison.py:173`, `strftime('%A')` ohne deutsche Locale) — HTML und
Ausblick verwenden deutsche Kürzel. → Sammel-Issue #1199.
