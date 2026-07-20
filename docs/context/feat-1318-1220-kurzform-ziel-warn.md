# Context: feat-1318-1220-kurzform-ziel-warn

## Request Summary

Bündel-Workflow für die Kurzform-Kanäle (SMS + E-Mail-Kurzzusammenfassung):
- **#1318** (Feature): Amtliche Unwetterwarnungen (`official_alerts`) in SMS **und** E-Mail-Kurzzusammenfassung sichtbar machen — bisher erscheinen sie nur im großen E-Mail-Briefing. War nie eingebaut (kein Regress).
- **#1220** (Verifikation): Ankunftsstunden-Fensterlücke in `compact_summary._collect_hourly_data` — vermutlich bereits durch #1317/#1319 Scheibe A (087f643f) behoben; als Regressionstest absichern.
- **#1317-Abschluss**: **ERLEDIGT, nicht mehr Teil dieses Workflows.** Die parallele Sitzung hat am 2026-07-20 den Deploy-Gate-Defekt #1325 behoben (Commit `3c531179`, Prod-Selftest PASS, Issue 06:00 geschlossen) und danach #1317 deployt und geschlossen (06:14). Prod-Deploys sind damit unblockiert; dieser Workflow liefert nur noch #1318 + #1220.

## Related Files

| File | Relevance |
|------|-----------|
| `src/output/renderers/sms_trip.py` | `SMSTripFormatter.format_sms()` / `_segments_to_normalized_forecast()`. Baut TH:/TH+:-Token rein aus Vorhersage (`build_day_window_points`), konsumiert `official_alerts` **nicht**. Ziel #1318: amtliche Warnung als eigenes Kürzel/Signal. 160-Zeichen-Budget. |
| `src/output/renderers/compact_summary.py` | `CompactSummaryFormatter.format_stage_summary()` (Natursprache) + `_collect_hourly_data` (nutzt jetzt geteiltes `day_window`, Zeile 159). Ziel #1318: amtliche Warnung als eigene Zeile/Pille. Ziel #1220: Verifikation Ankunftsstunde. |
| `src/output/renderers/day_window.py` | `build_day_window_points()` — geteilte Fensterlogik 04-19. Zeile 91/99: `start_h <= h <= end_h` bzw. `arrival_hour <= h <= 19` **inklusiv** → **#1220-Ursache (exklusives `include`) existiert nicht mehr**. |
| `src/output/renderers/alert/official_alerts.py` | **Geteiltes SSOT-Modul** (ADR-0011, kein Copy-Paste): `render_official_alerts_plain`, `render_official_alerts_html`, `dedupe_official_alerts`, `_bundle_by_hazard_level`, `collect_trip_alert_entries`, `official_alert_source_label`, `render_warn_block`. #1318 baut hierauf auf. |
| `src/output/renderers/email/html.py:1314-1350` | Vorbild: HTML-Warn-Kasten im großen Briefing (dedupe + bundle). |
| `src/output/renderers/email/compact.py:163` | Vorbild Text: `render_official_alerts_plain(_alert_entries)` (`== Warnungen ==`). |
| `src/output/renderers/comparison.py:187,401` | Ortsvergleich nutzt dieselben geteilten Alert-Helfer → Konvergenz-Anker. |
| `src/output/renderers/trip_report.py:228,716` | Aufrufstellen: `format_sms(...)` und `format_stage_summary(...)`. Segmente tragen `official_alerts` bereits → Daten an der Aufrufstelle vorhanden, nur nicht durchgereicht/konsumiert. |
| `src/app/models.py:400-412` | `SegmentWeatherData.official_alerts: List[OfficialAlert]` (Feld liegt vor). |
| `src/services/trip_report_scheduler.py:764-775` | Lädt `official_alerts` pro Segment. |

## Existing Patterns

- **Ein geteiltes Alert-Renderer-Modul** für alle Kanäle (E-Mail groß, Kompakt-Text, Ortsvergleich) — #1318 erweitert um SMS + Kurzform, **kein neuer Renderer** (sonst Trip/Compare-Teilungs-Verstoß).
- **Dedup + Bündelung nach Gefahr+Stufe** (`dedupe_official_alerts` → `_bundle_by_hazard_level`) vor Anzeige (Lehre #1217/#1218).
- **Kurzform-Aggregation über festes Tagesfenster 04-19** via `build_day_window_points` (#1319 Scheibe A), ortsgenau bis Ankunft, danach am Ziel.
- **SMS: keine erfundenen Uhrzeiten** (#874), höchste Priorität für Gewitter, 160-Zeichen-Budget.

## Dependencies

- **Upstream:** `official_alerts` (amtliche Quelle, MeteoAlarm/DWD) — **andere Quelle** als die Vorhersage-Token. Muss sauber getrennt bleiben.
- **Downstream:** `trip_report.py` (Rendering-Zusammenbau), Versand-Kanäle SMS/E-Mail-Kompakt/Telegram.

## Existing Specs / ADRs

- `docs/adr/0025-eine-gewitter-quelle-fuer-alle-briefing-kanaele.md` — **ADR-0025**: EINE gefensterte Gewitter-**Vorhersage**-Quelle für alle Kanäle, keine Widersprüche zwischen Kanälen. #1318 fügt eine **zweite, klar getrennte** Quelle (amtlich) hinzu — Konsistenz-Invariante: amtliche Warnung darf der Vorhersage nicht widersprechen bzw. muss als eigene Kategorie erkennbar sein.
- `docs/specs/modules/sms_daywindow_aggregation.md` — Scheibe A (Tagesfenster). §Dependencies nennt `night_weather`/`arrival_hour` als verifiziert.
- `docs/reference/sms_briefing_overview.md` §5 Punkt 9 — „Amtliche Warnungen in SMS/Kurzzusammenfassung bleiben ausgelagert → #1318" (dieser Workflow).
- `docs/specs/modules/thunder_night_at_destination_channels.md` — superseded durch #1319.

## Offene Design-Entscheidungen (für Spec/PO, #1318)

1. **SMS-Signal:** eigenes Kürzel für „amtliche Warnung aktiv" vs. Erweiterung `TH:`? Priorisierung im 160-Zeichen-Budget.
2. **Kurzzusammenfassung:** amtliche Warnung als eigene Zeile/Pille im Metriken-Überblick?
3. **Kanal-Konsistenz** zu ADR-0025: amtlich vs. Vorhersage sauber getrennt, keine Widersprüche.

## Analysis

### Type
Feature (#1318) + Verifikation/Regression (#1220). Kein Bug-Intake nötig — #1220-Ursache im Code bereits verschwunden.

### PO-Entscheidungen (2026-07-20, verbindlich)

1. **E-Mail-Kurzzusammenfassung ist NICHT Teil von #1318** — die amtliche Warnung steht dort bereits optimal im großen Warn-Kasten; eine zweite Anzeige in derselben Mail wäre eine Dopplung.
2. **Weg: die ursprüngliche SMS-Token-Zeile weiterentwickeln** (`docs/reference/sms_format.md` §2/§3.3/§3.5) — NICHT den #1216-`render_official_alert_sms` (`AMT GELB1/3:`-Format) ins Briefing einhängen. Begründung PO: die Token-Zeile ist das etablierte Modell der Briefing-SMS.
3. **Kürzel müssen international verständlich sein** und sich in der **Konfigurationsoberfläche wiederfinden**, damit der Nutzer den SMS-Aufbau versteht.
4. **Nur orange + rot** (Stufe 3–4) erscheinen in der Kurznachricht.

### Entschiedenes Modell (PO-Freigabe 2026-07-20)

> **Ein Phänomen — ein Kürzel.** Vorhersage und amtliche Warnung nutzen dasselbe internationale Kürzel; unterschieden werden sie durch einen eigenen Warn-Block, eingeleitet mit `!`. Das entwickelt das bestehende Prinzip aus `sms_format.md` §3.4 (zwei `TH:`-Tokens, per Position unterschieden) konsequent weiter.

**Kürzel (4 von 9 bereits im Format vorhanden, 5 neu nach demselben Bildungsgesetz: englisches Wort, 2 Buchstaben, ASCII/GSM-7):**

| hazard | Kürzel | Status |
|---|---|---|
| `thunderstorm` | `TH` | vorhanden (Thunderstorm) |
| `rain` | `HR` | vorhanden (Heavy Rain, Vigilance) |
| `wind_gust` | `W` | vorhanden (Wind) |
| `snow` | `SN` | vorhanden (Snow) |
| `black_ice` | `IC` | neu (ICe) |
| `extreme_heat` | `HT` | neu (HeaT) |
| `extreme_cold` | `CD` | neu (ColD) |
| `wildfire_risk` | `FR` | neu (FiRe) |
| `access_ban` | `CL` | neu (CLosed) |

**Stufe:** vorhandene `L/M/H`-Skala (`tokens/metrics.py:LEVELS`), abgebildet gelb→`L`, orange→`M`, rot→`H`. Keine neue Stufen-Sprache.
**Warn-Block:** `!` leitet ein (international „Achtung", 1 Zeichen, GSM-7-sicher). Kein Emoji — sonst UCS-2 und Budget-Halbierung auf 70 Zeichen.

**Beispiele:**
```
Nur Vorhersage:   GR20 E5: N9 D24 R0.2@6 W10@11 TH:M@16
Mit Warnung:      GR20 E5: N9 D24 R0.2@6 W10@11 TH:M@16 !TH:H@14 W:M
Brand + Sperrung: GR20 E5: N9 D28 R- W12@11 TH:- !FR:H CL
```

### Affected Files (with changes)
| File | Change Type | Description |
|------|-------------|-------------|
| `docs/reference/sms_format.md` | **MODIFY (SSOT!)** | Warn-Block `!` + 9 Kürzel + L/M/H-Stufenabbildung in §2 Token-Reihenfolge und §3 Token-Definitionen aufnehmen; „Provider TODO" bei HR/TH auflösen. |
| `src/output/tokens/dto.py` | MODIFY | Feld für die amtlichen Warnungen im `NormalizedForecast` (statt nur `vigilance_hr/th_*`), damit alle 9 hazards transportiert werden. |
| `src/output/tokens/builder.py` | MODIFY | `_vigilance()` zum vollständigen Warn-Block ausbauen (`!`-Marker, alle 9 Kürzel, L/M/H), Positions-/Prioritäts-Eintrag in `PRIORITY`/`ORDER`. |
| `src/output/renderers/sms_trip.py` | MODIFY | `segment.official_alerts` → Warn-Feld im `NormalizedForecast` füllen (heute bleibt es leer = Wurzel der Lücke); Filter Stufe ≥ orange. |
| `frontend/.../WeatherMetricsTab.svelte` | MODIFY | SMS-Kürzel je Metrik anzeigen + Legende beim Schalter „Amtliche Warnungen" (`!`-Block, 9 Kürzel, L/M/H = gelb/orange/rot). |
| `src/output/renderers/narrow.py` | MODIFY | Telegram-Bubbles: amtliche Warnung über den vorhandenen `render_official_alert_telegram` einhängen (heute kein Warn-Inhalt). |
| Tests | CREATE | (a) #1318 SMS-Warn-Block je hazard + Budget; (b) #1220 Ankunftsstunde in Kurzform (Regression, vermutlich schon grün). |

### Scope Assessment
- Files: ~6 Code + Doku-SSOT + Tests
- Estimated LoC: +150…+250 (LoC-Limit im Blick behalten)
- Risk Level: MEDIUM-HIGH (sicherheitsrelevanter Kanalinhalt, 160-Zeichen-Budget, Format-Vertrag mit Golden-Tests)

### Technical Approach
Die Daten kommen aus dem **modernen** `official_alerts`-Dienst (alle Provider, 9 hazards) — der alte, nie fertig verdrahtete `get_warning_full()`-Pfad wird NICHT wiederbelebt. Sie werden in den `NormalizedForecast` gefüllt und vom vorhandenen Token-Builder als `!`-Block gerendert. Damit bleibt die Token-Zeile die eine Quelle für den SMS-Aufbau, und die Kürzel stammen aus **einem** Katalog, der auch die Konfig-Oberfläche speist (keine zweite gepflegte Liste).

### Dependencies
`official_alerts` (amtliche Quelle) — bereits pro Segment geladen (`trip_report_scheduler.py:764-775`), am Renderer-Aufruf verfügbar. Keine neue Datenbeschaffung nötig.

## Risks & Considerations

- **Trip/Compare-Teilung (PO-Invariante):** SMS/Kurzform müssen die geteilten Alert-Helfer nutzen; eine neue Kurzform-Alert-Komponente ohne geteilten Baustein = Default-Fehler (#1170-Anti-Pattern).
- **#1220 vermutlich moot:** Bug-Ursache im Code weg (day_window inklusiv). Risiko: Verifikationstest ist grün ohne Fix → dann kein Fix, nur Regressionstest + Issue schließen. Falls doch rot → Mini-Fix in `day_window`/`compact_summary`.
- **Deploy-Kopplung #1317/#1325:** Prod-Deploy dieses Backend-Workflows blockiert, bis parallele #1325-Sitzung das Staging-E2E-Gate repariert. Kein Doppelaufwand an #1325.
- **160-Zeichen-Budget SMS:** neue Warnungs-Info darf bestehende Token nicht verdrängen (Priorisierung nötig).
- **Renderer-Mail-Gate #811:** Änderungen an `compact_summary.py`/`email/*` lösen das Commit-Gate aus → Test-Mails vor Commit gegen echt zugestellte Staging-Mail.
