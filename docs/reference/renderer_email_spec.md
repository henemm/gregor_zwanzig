# Renderer Specification – E-Mail Reports

This document defines how E-Mail reports are generated in Gregor Zwanzig.

**Last Updated:** 2026-06-26 (Issue #884 — HTML-Mail vollständige Fidelity: 8-Sektion-Layout mit Header-Stats-Grid, Ziel-Sektion, Ausblick mit Risk-Dot, Kommandos-Sektion, zweigeteilt Footer)

**Acceptance Validators (seit Issue #733):**
- **Trip-Briefing-Mail** (beide Formate: `full` HTML / `compact` Nur-Text): `.claude/hooks/briefing_mail_validator.py` (dispatcht auf `X-GZ-Mail-Type` + `X-GZ-Format` Header)
- **Orts-Vergleich-Mail**: `.claude/hooks/email_spec_validator.py` (fest auf Vergleichstabelle/Winner-Box verdrahtet)

Siehe CLAUDE.md für Scope-Details und Pflicht-Gate-Dokumentation.

---

## Principles
- E-Mail reports are **long-form**, human-friendly, but must remain concise and structured.
- They always include the **compact token line** (identical to the SMS).
- They may add **human-readable summaries** and **tables per stage/etappen points**.
- Debug information is appended at the end in plain text, identical to console output.
- Outgoing mails carry marker headers (`X-GZ-Mail-Type`, `X-GZ-Format`) for deterministic routing to acceptance validators.

---

## Layout (seit Issue #884 – HTML-Mail Fidelity)

### Sektionen im HTML-Briefing (8 gesamt, 7 implementiert)

**Neu seit Issue #884 (2026-06-26):** Die HTML-Briefing-Mail folgt einer vollständigen, designgeleiteten Struktur mit 8 Abschnitten (7 implementiert; Stirnlampe entfällt nach PO-Entscheidung):

| Nr. | Sektion | Status | Beschreibung |
|---|---|---|---|
| 1 | **Header** (zweispaltig + Stats-Grid) | LIVE | Kopfzeile mit Etappen-Code + Titel + Datum (links) und Tripname + Etappennummer (rechts); darunter 5-er Stats-Grid (Distanz, Aufstieg, Abstieg, Max-Höhe, Segmente) |
| 2 | **Quick-Take + Tags** | LIVE | Kompakte Zusammenfassung des Briefing-Inhalts; farbige Tags (tone=warn/ok/info/risk) für Kontexte |
| 3 | **Stirnlampe** | ENTFÄLLT | (PO-Entscheidung aus Issue #790 — nicht mehr in neuem Cloud-Design) |
| 4 | **Segmente** (Stundentabellen) | LIVE | Pro Etappensegment: Segment-Header + zwei-stufige Desktop-Tabelle (Gruppen-Row TEMP/WIND/NIEDERSCHLAG + Einheiten-Row) + Mobile-Variante (`EmailHourList` zwei-Zeilen-Format) |
| 5 | **Wetter am Ziel** (abgesetzte Sektion) | LIVE | Eigene abgesetzte Sektion mit accent-Eyebrow, Zielname, Ankunftszeiten-Range, identische Tabelle wie Segmente |
| 6 | **Ausblick** (Folge-Etappen) | LIVE | Nächste 4 Tage als kompakte Zeilen-Tabelle; jede Etappe mit Wochentag + Code + Name + Temp-Range + Risk-Dot (Farbindikator); Gewitter-Badge falls vorhanden |
| 7 | **Antwort-Kommandos** | LIVE | Dedizierte Sektion mit 3×2-Grid der Befehle (PAUSE 2d, SKIP, STOP, STATUS, CONFIG, HELP) + Hinweistext |
| 8 | **Footer** (zweigeteilt) | LIVE | Obere Zeile: Brand + Briefing-Typ; untere Zeile: Links (Trip-Übersicht, Zeitplan, Abmelden) |

Detaillierte Sektionsspezifikationen: siehe `docs/specs/modules/issue_884_mail_fidelity.md` (AC-1..AC-10).

### HTML-Rendering-Details (Issue #884)

#### Header (Sektion 1)
- **Struktur:** `<table>` mit zwei `<td>` (Desktop: Zweisspaltenlayout; Mobile: volle Breite)
- **Hintergrund:** `#fbfaf6` (G_HEADER_BG, neues Design-Token), `border-bottom:1px solid #e6e1d3`
- **Linke Spalte:** Eyebrow `"MORGEN-BRIEFING · {STAGE_CODE}"` (mono 10px, `#c45a2a`), Titel (22px desktop / 18px mobile), Datum (mono 13px desktop / 12px mobile)
- **Rechte Spalte:** `"GREGOR ZWANZIG"` (mono 10px, `#9a978d`), Trip-Kurzname (14px), Etappennummer (mono 12px)
- **Stats-Grid:** 5-Spalten-`<table>` (desktop) / 3 Spalten in 2 Zeilen (mobile); mit `border-right:1px solid #e6e1d3` als Trennlinie
  - Labels: Distanz · Aufstieg · Abstieg · Max-Höhe · Segmente

#### Segmente (Sektion 4)
- **Desktop-Tabelle:** zwei Ebenen
  - Gruppen-Row: Hintergrund `#fbfaf6`, Spaltenkopfgruppen (TEMP, WIND, NIEDERSCHLAG, SICHT/UV, HÖHE) mit Colspan
  - Einheiten-Row: Spalten-Labels mit Einheiten
  - Datenzellen: kritische Werte **fett + Farbe** (`#c2410c` bei Wind >20 km/h, `#0e6fb8` bei Regen >1 mm, `#b91c1c` bei Gewitter >0)
- **Mobile-Tabelle:** `EmailHourList` zwei-Zeilen-Format (neu ab Issue #884; ersetzt `_render_mobile_compact_rows`)
  - Hauptzeile: Zeit (mono bold, 26px breit) · Wetter-Glyph · Temp · gefühlte Temp · Risk-Dot
  - Detailzeile: Wind/Regen/Sicht/UV/Höhe komprimiert
  - Hintergrund: transparent oder leicht warn-getönt bei kritischen Werten

#### Wetter am Ziel (Sektion 5)
- **Sektion:** eigener Block, `bg #fbfaf6`, `border-top:1px solid #e6e1d3`
- **Kopfzeile:** Zweispaltig space-between; Links accent-Eyebrow `"ANKUNFT · WETTER AM ZIEL"` (`#c45a2a`) + Zielname; Rechts Zeitraum-String
- **Tabelle:** identischer Stil wie Segment-Tabellen (Desktop + Mobile)

#### Ausblick (Sektion 6)
- **Struktur:** `<table>` mit einer `<tr>` pro Folge-Etappe
- **Desktop:** 5 Spalten – Wochentag · Code · Name+Note+ggf. Gewitter-Badge · Temp-Range · Risk-Dot
- **Mobile:** 3 Spalten – Wochentag · (Name+Code+Note gestapelt) · (Temp+Risk-Dot übereinander)
- **Risk-Dot:** `border-radius:50%`, 10×10px, Farbe aus `format_trend_tokens()`:
  - ok: `#15803d` + `rgba(21,128,61,0.18)`
  - watch: `#c2410c` + `rgba(194,65,12,0.20)`
  - risk: `#b91c1c` + `rgba(185,28,28,0.22)`
  - Fallback: `#c8c4b8`
- **Gewitter-Badge:** `⚡ Gewitter {zeitangabe}` in `#b91c1c` mit light-red Hintergrund und Border

#### Antwort-Kommandos (Sektion 7 – NEU)
- **Grid:** 3×2 (desktop) / 2×3 (mobile) via `<table>`
- **6 Einträge:** PAUSE 2d, SKIP, STOP, STATUS, CONFIG, HELP
- **Stil:** CMD mono 11px bold + Beschreibung mono 10px `#9a978d`
- **Hinweistext:** mono 10px, color `#b8b4a8`: "Antworte auf diese E-Mail mit einem Schlüsselwort."

#### Footer (Sektion 8)
- **Gesamter Footer:** `bg #1d1c1a`, `color #9a978d`, mono 11px
- **Obere Zeile:** Links `"GREGOR ZWANZIG"` (`#fff`, bold, letterSpacing 0.06em) + " · " (`#5a5750`) + Briefing-Typ; Rechts (desktop-only) Datum + Provider + Icon
- **Untere Zeile:** Nach `border-top:1px solid #3a3835`, Link-Zeile: "Trip-Übersicht öffnen →" (`#c45a2a`) · "Briefing-Zeitplan" · "Abmelden" (alle plain text, keine `href`)

### Legacy: Token Line & Debug Block

#### 2) Token Line
- First block of the body.
- Exact 1:1 copy of the SMS token line.
- **Format-Definition:** siehe [`docs/reference/sms_format.md`](sms_format.md) (v2.0) — Single Source of Truth.
- Beispiel (mit Vigilance-Block und Fire-Block für Korsika):
  ```
  Paliri: N8 D24 R0.2@6(1.4@16) PR20%@11(100%@17) W10@11(15@17) G20@11(30@17) TH:M@16(H@18) TH+:M@14(H@17) HR:M@17TH:H@17 Z:HIGH208 M:24
  ```
- Beispiel (ohne Vigilance/Fire, internationaler Trip):
  ```
  Monte: N15 D25 R- PR20%@14 W22@14(28@16) G35@14(48@17) TH:M@14 TH+:- DBG[MET MED]
  ```

#### 3) Human-Friendly Summary (Quick-Take)
- Short list (dl) of the same values in words, e.g.:
  - Temperatur: Nacht-Min 15°C · Tages-Max 25°C
  - Regen: Menge –, Wahrscheinlichkeit 20% @14 Uhr
  - Wind: 22 km/h @14 Uhr, Böen 35 km/h @14 Uhr (Peak 48 km/h @19 Uhr)
  - Gewitter: Level M @14 Uhr

#### 4a) Klartext-Hinweis bei niedriger Konfidenz (Issue #121, ab Issue #715 einziger Confidence-Output in Tabelle)

Im E-Mail-Body wird ein Klartext-Hinweis ausgegeben, wenn an mindestens einer Stunde in T+0..72h `confidence_pct < 60` liegt. Dies ist der **einzige visuelle Confidence-Hinweis in der E-Mail-Tabelle** (Spalte wurde mit Issue #715 entfernt; Verlässlichkeit erscheint nur noch als Textblock und SMS-Token). Andernfalls erscheint **kein** Hinweis (Visual-Noise-Vermeidung).

- Format: `"Ab {Wochentag} nimmt die Unsicherheit zu (Temperatur-Spreizung {N} °C)."`
- Wochentag: erster betroffener Tag in T+0..72h (Deutsch: Montag–Sonntag).
- Spread: `max(spread_t2m_k)` über alle unsicheren Stunden dieses Tages, gerundet auf ganze Kelvin/°C.
- HTML: `<p class="confidence-hint">…</p>` in einem gelb hinterlegten Block, positioniert zwischen `summary` und `changes`.
- Plain: eigene Zeile mit Leerzeile davor/dahinter, gleicher Position.

#### Debug Block
- Always appended at the end, in `<pre>` formatted text.
- Content identical to console output.
- Must include:
  - `cfg.path`
  - `report` (morning/evening/update)
  - `channel` (console/email/sms)
  - `debug` flag
  - `dry_run` flag
  - `source.decision`
  - `source.chosen`
  - `source.confidence`
  - `source.coords`
  - `source.meta` (provider, run, model)
  - token line used
- Example:
  ```
  DBG[MET MED]
  source.decision: MOSMIX rejected (dist=20.0km, delta_h=220m, land_sea_match=false)
  source.chosen: MET
  source.confidence: MED (62)
  source.coords: 54.29N,10.90E
  source.meta: run=2025-08-28T19:12Z, model=ECMWF
  tokens: Monte: N15 D25 R- PR20%@14 W22@14(28@16) G35@14(48@17) TH:M@14 DBG[MET MED]
  ```

---

## Rules
- **Token line** is the single source of truth → all other representations must derive from it.
- **Debug block** must be identical between console and email.
- **Tables** may extend beyond 160 chars (no SMS limit).
- **Times** in tables use **leading zeros** for clarity.
- All numbers are integers unless explicitly defined as float (e.g. rainfall `R`).

---

## Marker Headers and Validation Routing (seit Issue #733)

`build_mime_message()` in `src/output/channels/email.py` setzt optionale Marker-Header zur deterministischen Klassifikation:

### Header-Format

```
X-GZ-Mail-Type: trip-briefing | compare
X-GZ-Format:    full | compact
```

### Routing

| Mail-Typ | Format | Quelle | Validator |
|----------|--------|--------|-----------|
| `trip-briefing` | `full` | `trip_report_scheduler.py` (Briefing-Versand) | `.claude/hooks/briefing_mail_validator.py` (AC-1/4) |
| `trip-briefing` | `compact` | `trip_report_scheduler.py` (compact-Renderer seit #722) | `.claude/hooks/briefing_mail_validator.py` (AC-2/6) |
| `compare` | `full` | `src/app/cli.py` (Compare-Wizard Versand) | `.claude/hooks/email_spec_validator.py` (AC-3) |

### Validierungslogik

- **`briefing_mail_validator.py`** prüft Trip-Briefing-Mails format-spezifisch:
  - `trip-briefing/full`: multipart/alternative, HTML + Plain Parts, ≥1 sequenzielle Stundentabelle, Werte selbst-konsistent
  - `trip-briefing/compact`: single text/plain, 7bit, isascii, < 2 KB, Kopf + Metriken + Ausblick + Footer (keine Stundentabelle)
  - `compare`-getaggte Mails: sauberes No-Op (Exit 0, falscher Validator)

- **`email_spec_validator.py`** prüft Orts-Vergleich-Mails (Vergleichstabelle, Winner-Box, min-locations). Für andere Mail-Typen nicht zuständig.

**Acceptance Gating:** Nur Exit 0 der entsprechenden Validator erlaubt „E2E Test bestanden".

---

## Metric Display Contract (seit Issue #814)

### Einfach (use_friendly_format=True) vs. Roh (use_friendly_format=False)

Der vollständige Vertrag aller Wetter-Metriken in der Briefing-Mail wird hier **einmalig** festgelegt.
Die **alleinige Quelle** der Anzeige-Entscheidung ist `use_friendly_format` in `MetricConfig`.

**Single Source of Truth: Metrik-spezifische Anzeige-Regeln**

| Kategorie | Metriken | Einfach (HTML) | Einfach (Plain) | Roh (HTML) | Roh (Plain) | Notiz |
|---|---|---|---|---|---|---|
| **Severity-Ampel** 🟢🟡🟠🔴 | wind, gust, precip, pop, cape | Ampelpunkt nach `display_thresholds` | Zahl + Einheit | Zahl + Einheit, **keine Markierung** | Zahl + Einheit | Nur HTML hat Ampel; Plain & Roh immer numerisch |
| **Wetterbild-Piktogramm** | cloud_total, cloud_low, cloud_mid, cloud_high, sunshine | Emoji (☀️🌤️⛅🌥️☁️) | Emoji (gleich) | Zahl | Zahl | Emoji in Einfach (HTML+Plain), Zahl in Roh — unverändert seit #435 |
| **Gewitter-Symbol** | thunder | ⚡ (MED=„⚡ mögl.", HIGH=„⚡⚡", NONE=„–") | ⚡ (gleiche Symbole) | deutsches Wort (kein / mögl. / hoch) | deutsches Wort (kein / mögl. / hoch) | ⚡-Symbol in Einfach (HTML+Plain); Roh immer deutsches Wort |
| **Zahl (kein Modus-Unterschied)** | visibility, temperature, wind_chill, dewpoint, humidity, pressure, uv_index, freezing_level, snowfall_limit, snow_depth, fresh_snow, precip_type | Zahl + Einheit | Zahl + Einheit | Zahl + Einheit | Zahl + Einheit | Unverändert in beiden Modi |

### Best-Practice-Schwellen (Ampelpunkte für Severity-Metriken)

| Metrik | 🟡 (Gelb) | 🟠 (Orange) | 🔴 (Rot) | Basis |
|---|---|---|---|---|
| wind (km/h) | 30 | 50 | 70 | Beaufort 5/7/8–9 |
| gust (km/h) | 50 | 65 | 80 | Böenklassifikation |
| precip (mm/h) | 1 | 5 | 10 | Regenintensität leicht/mäßig/stark |
| pop (%) | 30 | 60 | 80 | Niederschlagswahrscheinlichkeit |
| cape (J/kg) | 1000 | 2500 | 3500 | Standard-Konvektionsskala (ersetzt seit #814 fest verdrahtete Leiter 300/1000/2000) |

### Visibility wird bewusst NICHT ampeliert

Echte Wetterdaten zeigen: Median 16–54 km, ≥10 km in 90–100 % aller Stunden, <1 km (Nebel) ~0 %.
Eine Ampel wäre dauergrün und wertlos. Die nackte km-Zahl trägt mehr Information.
Ein echter Nebel-/Diesigkeits-Wächter gehört in die Alarm-Ebene (Folge-Issue nach #814).

### Implementierungs-Hinweis: „Roh ist Roh"

Im Roh-Modus gibt es **bei keiner Metrik** inline-Farb- oder Hintergrund-Markierungen
(insbesondere nicht Gelb-Highlight bei CAPE oder Orange-Highlight bei Sicht).
Alle Roh-Ausgaben sind numerisch/textlich ohne Styling.

---

## Viewport-spezifisches Rendering (ab Issue #831)

Die HTML-Briefing-Mail enthält zwei Stundentabellen-Varianten, die per CSS-Mediaqueries
geschaltet werden:

| Viewport | CSS-Klasse | Rendering | Display |
|----------|-----------|-----------|---------|
| Desktop (≥601px) | `.desktop-only` | `_render_html_table()` mit `html=True` | HTML-Tabelle mit Ampel-Emojis im Einfach-Modus |
| Mobile (≤600px) | `.mobile-compact` | `_render_mobile_compact_rows()` mit `indicator_keys` (seit #831) | Einfach-Modus: HTML-Tabelle (identisch Desktop); Roh-Modus: Monospace-`<pre>`-Block |

**Issue #831 — Mobile Einfach-Modus:** Der Mobile-Renderer (`_render_mobile_compact_rows`) respektiert
jetzt den Einfach-Modus: wenn `indicator_keys` gesetzt ist (d.h. die Metriken sind mit `use_friendly_format=true`
konfiguriert), delegiert er an `_render_html_table` und zeigt Ampel-Emojis (🟢🟡🟠🔴) — identisch zur Desktop-Ansicht.
Im Roh-Modus (leere `indicator_keys`) verbleibt die Ausgabe im klassischen Monospace-`<pre>`-Block (Issue #636).

**Resultat:** Kein Modus-Mismatch mehr zwischen Desktop- und Mobile-Ansicht derselben Nachricht.