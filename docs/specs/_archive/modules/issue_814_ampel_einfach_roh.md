---
entity_id: issue_814_ampel_einfach_roh
type: module
created: 2026-06-14
updated: 2026-06-14
status: approved
version: "2.0"
tags: [email, renderer, ampel, format-mode, briefing, frontend, bugfix]
---

# Issue #814 — Einfach/Roh-Darstellung endgültig korrekt (vollständiger Metrik-Vertrag)

## Approval

- [x] Approved (PO, 2026-06-14, im Dialog — vollständiger Vertrag inkl. CAPE/Gewitter/Sicht + Frontend)

## Purpose

Das Einfach/Roh-Anzeigeverhalten **aller** Wetter-Metriken in der Briefing-Mail eindeutig,
vollständig und endgültig festschreiben — `use_friendly_format` wird die **alleinige,
deterministische Quelle** der „Einfach"-Entscheidung. Statt vier Sonderfälle (#759/#810)
zu flicken, definiert dieses Issue den **kompletten Vertrag pro Metrik** (Ampelpunkt vs.
Piktogramm vs. Zahl), beseitigt die letzten Inkonsistenzen (CAPE, Sicht, Gewitter) und
hält das Ganze sowohl mit einem verpflichtenden Beide-Modi-Matrix-Test (#811-Muster) als
auch mit den nötigen **Frontend**-Anpassungen kohärent — Backend-Anzeige und UI-Umschalter
müssen übereinstimmen.

## Der vollständige Vertrag (Single Source of Truth)

| Kategorie | Metriken | Einfach | Roh |
|---|---|---|---|
| **Severity → Ampelpunkt** 🟢🟡🟠🔴 (**nur HTML**; Plain immer Zahl) | wind, gust, precip, pop, **cape** | Ampelpunkt (Schwellen unten) | nackte Zahl, **keine** Markierung |
| **Wetterbild → Piktogramm** | cloud_total/low/mid/high, sunshine | Wetter-Emoji (☀️🌤️⛅🌥️☁️ / Sonne) | Zahl |
| **Gewitter → kategorisch** | thunder | ⚡-Symbol (MED=„⚡ mögl.", HIGH=„⚡⚡") | **deutsches Wort** (kein / mögl. / hoch) |
| **Zahl** (kein Modus-Unterschied) | **visibility (km)**, temperature, wind_chill, dewpoint, humidity, pressure, uv_index, freezing_level, snowfall_limit, snow_depth, fresh_snow, precip_type | Zahl | Zahl |

*(wind_direction bleibt unverändert: Einfach = Kompass N/O/S/W, Roh = Grad°. confidence:
nicht wählbar #710, wird ignoriert.)*

**„Roh ist Roh":** In Roh gibt es bei **keiner** Metrik mehr eine Farb-/Hintergrund-
Markierung — auch CAPE und Sicht zeigen dort nur die nackte Zahl.

### Best-Practice-Schwellen (datenvalidiert an echten Open-Meteo-Daten, 10 Orte)

| Metrik | 🟡 | 🟠 | 🔴 | Basis |
|---|---|---|---|---|
| wind (km/h) | 30 | 50 | 70 | Beaufort 5/7/8–9 — **unverändert** |
| gust (km/h) | 50 | 65 | 80 | **unverändert** |
| precip (mm/h) | 1 | 5 | 10 | Regenintensität leicht/mäßig/stark — **unverändert** |
| pop (%) | 30 | 60 | 80 | **unverändert** |
| **cape (J/kg)** | **1000** | **2500** | **3500** | Standard-Konvektionsskala — **ersetzt** die fest verdrahtete Leiter 300/1000/2000 |

**Sicht bewusst KEINE Ampel:** Echte Daten (Median 16–54 km, ≥10 km in 90–100 % aller
Stunden, <1 km Nebel ~0 % selbst an „schlechten" Orten) → jede Ampel wäre dauergrün und
damit wertlos. Die nackte km-Zahl trägt mehr Information (z. B. Ostsee-Dunst „2,3 km" vs.
„42 km"). Ein echter Nebel-/Diesigkeits-Wächter gehört in die Alarm-Ebene (#807/#808-Folge).

## Root Cause (verifiziert)

`build_format_modes(dc)` kollabiert für wind/gust/precip/pop sowohl „Einfach" als auch
„Roh" auf denselben Mode `"raw"` (Katalog-`default_format_mode="raw"`; `use_friendly_format=True`
überschreibt ihn nicht). Der #810-Check `if html and mode != "raw"` (helpers.py:447,462,503)
kann die Modi deshalb **prinzipiell nicht** trennen → Default „Einfach" zeigt live Zahlen
statt Ampel.

## Source

- **Backend (Änderung):** `src/output/renderers/email/helpers.py` (`fmt_val` Ampel-Kopplung
  an `use_friendly_format`, CAPE/Gewitter/Sicht-Zweige, „Roh ist Roh"; neuer per-Spalte-
  Indikator-Builder), `src/output/renderers/email/__init__.py` / `html.py` / `plain.py`
  (Indikator-Set durchreichen), `src/app/metric_catalog.py` (CAPE-`display_thresholds`,
  visibility `has_friendly_format=False`, thunder `raw`-Mode).
- **Frontend (Änderung):** `frontend/src/lib/components/trip-detail/metricsEditor.ts`
  (`INDICATOR_MAP`: `visibility` entfernen, `precipitation` ergänzen).
- **Tests (Änderung):** `tests/tdd/test_issue_811_mode_matrix.py` (metrik-spezifisch,
  `_XFAIL_810` raus), `tests/tdd/test_issue_759_email_ampel.py` (neue Quelle).

## Estimated Scope

- **LoC:** ~300 (Backend ~70, Frontend ~15, Tests ~215) → **loc_limit_override 450**
- **Files:** 0 neu, ~8 geändert
- **Schicht:** **Full-stack** (Python-Renderer + Katalog + Svelte-Editor) → E2E full-stack.

## Acceptance Criteria

**AC-1:** Einfach (use_friendly_format=True) → HTML-Ampelpunkt für wind/gust/precip/pop.
Given Briefing-Mail mit `use_friendly_format=True` für wind/gust/precip/pop
When die echte Mail über `render_email(email_format="full")` gerendert wird
Then ist die HTML-Stundenzelle **jeder** dieser vier ein Ampelpunkt 🟢🟡🟠🔴 in der zur
`display_thresholds`-Schwelle passenden Stufe, **ohne** nackte Zahl.

**AC-2:** Roh (use_friendly_format=False) → HTML-Zahl für die vier, ohne Ampel/Markierung.
Given dieselbe Mail mit `use_friendly_format=False`
When sie als `full`-HTML gerendert wird
Then ist die Zelle jeder der vier eine Zahl (+ Einheit), **kein** Ampel-Emoji und **keine**
Farb-/Hintergrund-Markierung.

**AC-3:** Plain-Teil bleibt in beiden Modi numerisch für die vier Metriken.
Given Einfach **oder** Roh
When der `text/plain`-Teil gerendert wird
Then sind wind/gust/precip/pop dort in beiden Modi numerisch, ohne Ampel-Emoji.

**AC-4:** CAPE harmonisiert — Ampel nur HTML (1000/2500/3500), Roh & Plain nackte Zahl.
Given eine Mail mit aktiviertem CAPE
When sie gerendert wird
Then zeigt CAPE in **Einfach-HTML** einen Ampelpunkt 🟢🟡🟠🔴 nach den Schwellen
1000/2500/3500 J/kg, in **Roh** die nackte Zahl **ohne** Gelb-Markierung, und im
**Plain**-Teil in beiden Modi die Zahl (kein Emoji im Text).

**AC-5:** Sicht ist in allen vier Quadranten numerisch in km, ohne Wort/Markierung.
Given Einfach **oder** Roh
When die Mail (HTML und Plain) gerendert wird
Then zeigt Sicht in **allen vier** Quadranten die Zahl in km — **kein** Ampel-Emoji,
**kein** englisches Wort (good/fair/poor/fog), **keine** Markierung.

**AC-6:** Gewitter — Symbol in Einfach, deutsches Wort in Roh, keine Stufe verloren.
Given Gewitter-Werte NONE/MED/HIGH
When gerendert wird
Then zeigt Einfach das ⚡-Symbol (MED=„⚡ mögl.", HIGH=„⚡⚡", NONE=„–") und Roh ein
kurzes deutsches Wort (kein / mögl. / hoch); MED und HIGH bleiben in beiden Modi
unterscheidbar.

**AC-7:** Wetterbild- (Piktogramm) und Zahl-Metriken bleiben in beiden Modi unverändert.
Given Einfach **oder** Roh
When gerendert wird
Then verhalten sich cloud_total/low/mid/high und sunshine wie bisher (Piktogramm in
Einfach, Zahl in Roh) und temperature/wind_chill/dewpoint/humidity/pressure/uv_index/
freezing_level/snowfall_limit/snow_depth/fresh_snow/precip_type bleiben in beiden Modi Zahl.

**AC-8:** „Roh ist Roh" — im Roh-Modus keine inline-Farb-/Hintergrund-Markierung.
Given irgendeine Metrik im Roh-Modus
When als HTML gerendert wird
Then enthält die Zelle **keine** inline-Farb-/Hintergrund-Markierung (insbesondere weder
CAPEs Gelb-Highlight noch Sichts Orange-Highlight).

**AC-9:** Verpflichtender metrik-spezifischer Matrix-Test (#811-Muster) über alle Kombinationen.
Given ein parametrisierter Test über `{full, compact} × {Einfach, Roh} × {briefing, alert}`
When jede Kombination über den **echten** Renderer (`render_email`, mit real via
`build_format_modes`/Indikator-Set gebauten Parametern — **nicht** `fmt_val` mit
handgesetztem mode) gerendert wird
Then prüft der Test AC-1..AC-8 **für jede Metrik einzeln** (nicht „≥1 Ampel irgendwo",
damit CAPE den Fehler nicht maskiert); reproduziert die Regression als RED, GREEN nach Fix.

**AC-10:** Alt-Tests angeglichen — _XFAIL_810 entfernt und #759-Test auf neue Quelle.
Given der `_XFAIL_810`-Marker im Matrix-Test und der #759-Test
When der Fix steht
Then ist `_XFAIL_810` entfernt (Roh+full läuft als reguläres GREEN) und der #759-Test
spiegelt die neue Quelle (`use_friendly_format`) wider, ohne den Bug zu zementieren.

**AC-11:** Frontend — Sicht zeigt „nur Rohwert" ohne Roh/Einfach-Umschalter.
Given der Trip-Editor (Metrik-Tab) als eingeloggter Nutzer
When eine Tour mit aktivierter Sicht geöffnet wird
Then zeigt die Sicht-Zeile **„nur Rohwert"** und **keinen** Roh/Einfach-Umschalter
(visibility aus `INDICATOR_MAP` entfernt).

**AC-12:** Frontend — Regen (precipitation) hat den Roh/Einfach-Umschalter.
Given der Trip-Editor (Metrik-Tab)
When eine Tour mit aktiviertem Regen (`precipitation`) geöffnet wird
Then hat die Regen-Zeile den Roh/Einfach-Umschalter (precipitation zu `INDICATOR_MAP`
ergänzt) — konsistent mit Wind/Böen/Regenwahrscheinlichkeit.

## Out of Scope

- Mail-Befunde #806 (Doppel-Stunden), #807 (Zusammenfassungs-Ebenen), #808 (Sonne 0 min) —
  eigener kohärenter Folge-Workflow (gemeinsamer Aggregations-/Segment-Pfad).
- Echter Nebel-/Diesigkeits-Wächter für Sicht (Alarm-Ebene → #807/#808-Folge).
- Globale `format_mode`-Semantik (#435/#444/#629), Beaufort-/Regenintensitäts-Schwellen der vier.

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `render_email` (`email/__init__.py`) | Python | echter Render-Einstieg `(html, plain)` |
| `MetricConfig.use_friendly_format` (`models.py:491`) | Python | alleinige Quelle |
| `ampel_dot` (`helpers.py:369`) | Python | 4-stufige Ampel-SSoT |
| `INDICATOR_MAP` (`metricsEditor.ts:24`) | TS | steuert UI-Umschalter pro Metrik |
| `renderer_mail_gate.py` | Hook | #811-Commit-Gate verlangt Matrix-Nachweis |

## References

- Broken Patch: #810 (`e38d3224`). Ursprung Ampel: #759/#669. Gate-Infra: #811.
- Datenvalidierung Sicht/CAPE: echte Open-Meteo-Abrufe (10 Orte, 2026-06-14).

## Changelog

- 2.0 (2026-06-14): Vollständiger Metrik-Vertrag (CAPE/Gewitter/Sicht harmonisiert,
  Best-Practice-Schwellen datenvalidiert, Frontend-ACs, „Roh ist Roh").
- 1.0 (2026-06-14): Initiale Spec (nur die vier Ampel-Metriken).
