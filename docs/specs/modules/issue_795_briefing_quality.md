---
entity_id: issue_795_briefing_quality
type: module
created: 2026-06-13
updated: 2026-06-13
status: complete
version: "2.0"
tags: [email, renderer, briefing, quality, pills, tests]
---

# Briefing-Mail-Qualität + Pill-Inhalt analog SMS (#795)

## Approval

- [x] Approved (PO 2026-06-13 — Pill-Inhalt analog SMS vereinheitlichen [ausgeschrieben, NICHT kryptisch], Optik bleibt Vollfarb-Kapsel #664; + Tests/Qualitäts-Fixes)

## Purpose

Die Metrik-Pills im „Metriken-Überblick" hatten nie eine konsistente **inhaltliche**
Spezifikation — die Uhrzeit-, Schwellen- und Formatlogik ist pro Metrik ad-hoc gewachsen
und widerspricht sich. Die **SMS** dagegen hat eine durchdachte, einheitliche Regel
(`docs/reference/sms_format.md`). PO-Entscheidung: Die Pills übernehmen die **Inhaltslogik
der SMS** (welche Metriken, gleiche Schwellen, Schwellen-Zeitpunkt + Spitzen-Zeitpunkt),
aber **ausgeschrieben/lesbar** — KEINE kryptischen SMS-Tokens (`W10@11(15@17)`). Die
**Optik** bleibt die PO-freigegebene Vollfarb-Kapsel (#664); der WCAG-AA-Konflikt wird
INNERHALB der Kapselform gelöst (dunklere Vollfarben + weißer Text). Zusätzlich die
Qualitäts-Fixes aus dem Review (Plain-tone-Marker, HTML↔Plain-Hierarchie, Vortag-Prominenz)
und die Test-Härtung (Tests prüfen Qualität, nicht nur Anwesenheit).

## Source

- **File:** `src/output/renderers/email/helpers.py` (`_pill_for_metric`, `build_metrics_summary_pills`, `pill_html`, `tone_symbol`, `_PILL_TONES`)
- **File:** `src/output/renderers/email/plain.py`, `html.py` (Hierarchie, Vortag-Zeile)
- **File:** `tests/tdd/test_issue_795_briefing_quality.py` (neu), `tests/tdd/test_issue_257_trip_briefing_polish.py` (Hex-Pinning → Kontrast-Assertion)

## Dependencies

| Entity | Type | Reason |
|--------|------|--------|
| `#759` (ampel_dot / display_thresholds) | feature | EIN Ampel-System: Pill-Stufe + Schwellen identisch zur Stundentabelle (AC-9) |
| `#664` (Metriken-Überblick / pill_html) | feature | Vollfarb-Kapsel-Design der Pills (#664-Handoff) |
| `src/output/tokens/builder.py` (SMS DEFAULTS) | module | Erwähnungsschwellen + Peak-Logik (SSoT, AC-3/AC-5) |
| `#790` (Briefing-Mail vereinfacht) | feature | Basis: Pills sind seit #790 der eine Metrik-Block |

## Pill-Inhalts-Spezifikation (analog SMS, ausgeschrieben)

Zwei Metrik-Klassen, EINE Regel je Klasse. Schwellen + Peak-Logik aus der SMS
(`render_threshold_peak_value`: erste Stunde ≥ Schwelle = „ab", Tagesspitze = „Spitze";
kollabiert wenn identisch).

### Klasse 1 — Ereignis-Metriken (mit Uhrzeit)
`wind, gust, precipitation, rain_probability, thunder, visibility, humidity`

- **Über Erwähnungsschwelle:** `<Label> ab HH:00 · Spitze <max> <Einheit> um HH:00`.
  Wenn Schwellen-Stunde == Spitzen-Stunde (und Wert gleich): `<Label> ab HH:00 · <wert> <Einheit>`.
- **Unter Schwelle:** ruhige Klartext-Form: `kein Regen`, `kein Gewitter`, `Wind ruhig`,
  `Böen ruhig`, `Regenrisiko geringe`, `gute Sicht`, `Luft trocken`.
- **Erwähnungsschwellen — IDENTISCH zur SMS** (`builder.py DEFAULTS`):
  Regen > 0 mm · Regenwahrsch. ≥ 20 % · Wind ≥ 10 km/h · Böen ≥ 20 km/h · Gewitter ≥ Level L.
  Sicht: Unterschreitung der display-Schwelle (Default 2 km). Luftfeuchte ≥ 90 %.
- **Spezialfälle Wortlaut:**
  - precipitation: `Regen ab HH:00 · <summe> mm gesamt, Spitze HH:00`
  - thunder: `Gewitter ab HH:00 · stärkste HH:00` (Level-Eskalation); ohne: `kein Gewitter`
  - visibility (Unterschreitung): `Sicht ab HH:00 unter <X> km · min <Y> km`
- **Einheitlich `HH:00`** überall (behebt den Regenwahrsch.-`:00`-Bug).

### Klasse 2 — Bereichs-/Kontext-Metriken (OHNE Uhrzeit)
`temperature, wind_chill, cloud_total, cloud_low, freezing_level, dewpoint, uv_index, sunshine`

- Format: `<Label> <min>–<max> <Einheit>`; bei min==max **Einzelwert** `<Label> <wert> <Einheit>`.
- Beispiele: `Temperatur 7–18 °C`, `0°-Grenze 1800–2400 m`, `Bewölkung 12–87 %`,
  `Taupunkt 4–9 °C`, `UV bis 7`, `Sonne 120 min`.
- KEINE Uhrzeit (analog SMS-Temperatur — Tageskontext, kein kritischer Zeitpunkt).

### Farbe — EIN Ampel-System für die ganze Mail (Konsistenz mit #759-Stundentabelle)
- **Klasse 1 (Ereignis):** Die Pill-Stufe wird über **dieselbe 4-stufige Ampel** wie die
  Stundentabelle bestimmt: `ampel_dot`-Logik + `MetricDefinition.display_thresholds`
  (SSoT — Wind 30/50/70, Böen 50/65/80, Regen 1/5/10, Regenwahrsch. 30/60/80, …), angewandt
  auf den **Spitzenwert**. **NICHT** nach der Erwähnungsschwelle. **Garantie:** derselbe Wert
  ergibt dieselbe Stufe (🟢🟡🟠🔴) in Tabelle UND Pill. Ruhige Form (unter Erwähnungsschwelle) = grün.
- **Klasse 2 (Bereich):** neutral (kein Schweregrad).
- **Vollfarb-Kapsel + WCAG-AA:** Die 4 Pill-Vollfarben sind die **WCAG-AA-gedunkelten
  Entsprechungen** der 4 Ampelstufen 🟢🟡🟠🔴 (weißer Text ≥ 4.5:1; Form bleibt Vollfarb-Kapsel
  `border-radius:99px`). Grün/Orange/Rot lassen sich passend dunkeln; **Gelb** wird zwangsläufig
  ein dunkles Gold/Ocker (helles Gelb + weißer Text ist nie AA) — Stufe/Schwelle identisch zur
  Tabelle, Farbe „ansatzweise" angenähert. EINE SSoT-Farbtabelle (4 Stufen) für HTML.
- **Plain (full, utf-8):** `tone_symbol` nutzt **dieselben 4 Emojis** 🟢🟡🟠🔴 wie die Stundentabelle
  (nicht ein abweichendes 3er-Set), Klasse 2 ohne Symbol.
- **Compact (Nur-Text, 7bit/ASCII):** keine Emojis möglich → Schwere als **dezentes ASCII-Zeichen**
  abgeleitet aus DERSELBEN Ampelstufe: grün → kein Präfix, gelb → `!`, orange → `!!`, rot → `!!!`
  (Klasse 2 / neutral → kein Präfix). **KEINE** rohen `[AMPEL_*]`/`[TONE]`-Marker. Der compact nutzt
  ansonsten denselben ausgeschriebenen Pill-Text wie die ausführliche Mail (SMS-Schwellen, min==max
  gefixt) und bleibt single `text/plain`, 7bit/ASCII, < 2 KB.

## Implementation Details

```
RC0 (NEU, Kern) — Pill-Inhalt vereinheitlichen analog SMS (helpers._pill_for_metric):
  _pill_for_metric komplett nach obiger Klasse-1/Klasse-2-Regel neu aufbauen.
  Schwellen + Peak-Ermittlung aus der SMS wiederverwenden wo sinnvoll (DRY):
  render_threshold_peak_value-Muster bzw. eine gemeinsame Hilfsfunktion. Erwähnungsschwellen
  aus EINER Quelle mit der SMS teilen (builder.DEFAULTS bzw. zentrale Konstante). Farbe via
  display_thresholds (ampel). Ausgeschrieben, keine @-Tokens.

RC1 — Plain tone-Marker (plain.py): tone_symbol(tone) (good→🟢 warn→🟡 bad→🔴 info→neutral),
  KEINE [TONE]-Marker. (bereits in v1 umgesetzt — beibehalten.)

RC2 — Hierarchie HTML==Plain: Metriken-Überblick VOR Segment-Tabellen in beiden.
  (bereits in v1 — beibehalten.)

RC3 — min==max: durch Klasse-2-Regel abgedeckt (Einzelwert).

RC4 — Vortag-Zeile-Prominenz: eigene abgesetzte Einheit, ≥14px, WCAG-AA, nicht graue Fußnote.
  (bereits in v1 — beibehalten.)

RC5 — EIN Ampel-System (Konsistenz mit #759): Pill-Stufe via ampel_dot+display_thresholds
  (SSoT mit der Stundentabelle), 4 Stufen. Vollfarb-Kapsel behalten; die 4 Stufenfarben sind die
  WCAG-AA-gedunkelten Entsprechungen von 🟢🟡🟠🔴 (weißer Text ≥4.5:1; Gelb→dunkles Gold). tone_symbol
  (Plain) = dieselben 4 Emojis wie die Tabelle. EINE SSoT-Farb-/Stufentabelle. KEIN heller-Chip-Umbau.

RC6 (F001-Fix) — test_issue_257_trip_briefing_polish.py pinnt exakte Hex-Werte → bricht bei
  Farbänderung. Auf Kontrast-/Tone-Assertion umstellen (prüft Bedeutung, nicht exakten Hex).
```

## Acceptance Criteria

- **AC-1:** Given dieselben Daten / When HTML und Plain gerendert werden / Then steht der Metriken-Überblick in **beiden** vor den Segment-Tabellen.
  - Test: Positions-Index „Metriken" < erste Segment-Tabelle, in HTML UND Plain.

- **AC-2:** Given eine Plain-Mail mit Pills / When gerendert / Then **keine** rohen `[INFO]/[WARN]/[GOOD]/[BAD]`; Ereignis-Pills tragen die **gleichen 4 Ampel-Emojis** 🟢🟡🟠🔴 wie die Stundentabelle (Bereichs-Pills ohne Symbol).
  - Test: kein `[TONE]` im Plain; je nach Stufe erscheint 🟢/🟡/🟠/🔴.

- **AC-3 (Pill-Inhalt Klasse 1 — Ereignis):** Given eine Ereignis-Metrik über Erwähnungsschwelle / When der Pill gerendert wird / Then erscheint **ausgeschrieben** „… ab HH:00 · Spitze … um HH:00" (kein `@`-Token), mit der **SMS-identischen** Schwelle. Unter Schwelle erscheint die ruhige Klartext-Form.
  - Test: Wind mit Verlauf (Schwelle 10) → „Wind ab HH:00 · Spitze X km/h um HH:00"; Wind durchweg < 10 → „Wind ruhig". Schwellenwert == SMS-DEFAULT.

- **AC-4 (Pill-Inhalt Klasse 2 — Bereich):** Given eine Bereichs-Metrik / When der Pill gerendert wird / Then erscheint „<Label> min–max <Einheit>" **ohne Uhrzeit**; bei min==max ein Einzelwert.
  - Test: Temperatur 7..18 → „Temperatur 7–18 °C" (kein „Max HH:00"); konstant 12 → „Temperatur 12 °C".

- **AC-5 (einheitliches Uhrzeitformat):** Given irgendein Ereignis-Pill mit Uhrzeit / When gerendert / Then immer `HH:00` (zweistellig, mit `:00`) — keine Variante ohne `:00`.
  - Test: rain_probability über Schwelle → enthält `HH:00`, nicht `ab 14` ohne `:00`.

- **AC-6 (Vortag-Prominenz):** Given Vortag-Vergleich / When gerendert / Then ist die Einordnungszeile eigene abgesetzte Einheit (HTML: ≥14px, eigene Box, nicht 13px/#5c5a52; Plain: abgesetzt) und genau EINE Zeile.
  - Test: HTML-Vortag-Box trägt nicht die schwache Signatur; Plain genau eine Vortag-Zeile.

- **AC-7 (Kontrast WCAG-AA, Vollfarb, 4 Stufen):** Given die 4 Ampelstufen-Pillfarben / When gerendert / Then ist jede Vollfarbe + weißer Text ≥ 4.5:1, und die Form bleibt Vollfarb-Kapsel (`border-radius:99px`, vollflächiger Hintergrund).
  - Test: Kontrastverhältnis je der 4 Stufenfarben ≥ 4.5; pill_html nutzt vollflächigen bg + weißen fg.

- **AC-8 (kein Hex-Pinning):** Given die Farbtests / When Farben justiert werden / Then prüfen sie Bedeutung/Kontrast statt exakter Hex-Werte; `test_issue_257` bricht nicht mehr bei WCAG-Anpassung.
  - Test: test_issue_257-Pill-Tests grün nach Farbänderung (Kontrast-/tone-basiert).

- **AC-9 (Ampel-Konsistenz Pill ↔ Stundentabelle):** Given ein Ereignis-Metrik-Wert / When er sowohl in der Stundentabelle als auch als Pill erscheint / Then ergibt er **dieselbe Ampelstufe** — gleiche `display_thresholds`, gleiche `ampel_dot`-Logik (derselbe Spitzenwert → dieselbe Stufe/Farbe in beiden).
  - Test: für Grenzwerte je Metrik (z.B. Wind 29/30/50/70) liefert die Pill-Stufenbestimmung dieselbe Stufe wie `ampel_dot(wert, display_thresholds)`.

- **AC-10 (Compact ASCII-Schwerezeichen):** Given eine compact-Briefing-Mail mit Ereignis-Metriken / When sie gerendert wird / Then trägt jede Ereignis-Pill ein **ASCII-Schwerezeichen** abgeleitet aus der Ampelstufe (grün→kein, gelb→`!`, orange→`!!`, rot→`!!!`), **kein** rohes `[AMPEL_*]`/`[TONE]`-Marker; die Mail bleibt single `text/plain`, 7bit/ASCII (`isascii()`), < 2 KB.
  - Test: compact rendern → kein `[AMPEL_`/`[WARN]`/`[INFO]` im Body; eine Pill über Gefahrenschwelle trägt das erwartete `!`-Präfix; `body.isascii()` True; Bytegröße < 2048.

## Known Limitations
- Kontrast-Test prüft die definierten Farbkonstanten, nicht gerenderte Pixel.
- compact-Pfad: bleibt single text/plain, 7bit/ASCII, < 2 KB — übernimmt aber den neuen Pill-Text
  + ASCII-Schwerezeichen (AC-10).
- `°C`→`CC`-ASCII-Transliteration im compact ist ein **pre-existing** Defekt (auch im Prod-Stand),
  separat als Issue erfasst — NICHT Teil von #795.

## Changelog
- 2026-06-13: v1 — Qualitäts-Fixes (tone-Marker, Hierarchie, min==max, Vortag, Kontrast).
- 2026-06-13: v2 — Pill-Inhalt analog SMS vereinheitlicht (ausgeschrieben), Vollfarb-Kapsel + WCAG, F001-Fix. PO-Entscheidung.
- 2026-06-13: v3 — Pill-Farbe = EIN Ampel-System mit der #759-Stundentabelle (gleiche 4 Stufen + display_thresholds + ampel_dot-Logik; Vollfarben = WCAG-gedunkelte 🟢🟡🟠🔴; Plain = dieselben Emojis). Neuer AC-9 (Ampel-Konsistenz Pill↔Tabelle). PO-Entscheidung.
- 2026-06-13: v4 — Compact (Nur-Text/ASCII) übernimmt den neuen Pill-Text + ASCII-Schwerezeichen (grün→kein, gelb→`!`, orange→`!!`, rot→`!!!`) statt roher `[AMPEL_*]`-Marker. Neuer AC-10. PO-Entscheidung. `°C`→`CC`-Transliteration als pre-existing Nebenbefund vermerkt.
- 2026-06-13: **IMPLEMENTED** — alle ACs erfüllt, alle Dateien aktualisiert.
