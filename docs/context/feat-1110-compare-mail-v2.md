# Context: feat-1110-compare-mail-v2

## Request Summary

Issue #1110: Die Ortsvergleich-E-Mail bekommt das neue v2-Layout aus der importierten
Design-Vorlage (`docs/design-requests/compare_mail_v2/screen-compare-email-v2.jsx`).
PO-Vorgaben: kein Score/Winner mehr, Übersichtstabelle Metriken×Orte inkl. Warn-Zeile,
Stundentabellen für ALLE Orte, visuelles Vokabular = Trip-Briefing-Mail. Der gelieferte
Design-Code ist 1:1-Vorlage (Struktur/Farben/Abstände), kein freihändiger Nachbau.

## PO-Entscheidungen (2026-07-08, AskUserQuestion)

1. **Reihenfolge:** Neues Layout ZUERST (dieses Issue), Konfigurierbarkeit #1104–#1107
   setzt danach auf dem neuen Layout auf. Dieses Issue rendert den heutigen Metrik-Stand.
2. **Score-Scope:** Streichung nur in der E-Mail (HTML + Klartext). App-Detailansicht /
   andere Kanäle → separates Folge-Issue.

## Related Files

| File | Relevance |
|------|-----------|
| `docs/design-requests/compare_mail_v2/screen-compare-email-v2.jsx` | Maßgebliche Design-Vorlage (`CompareEmailV2`, Desktop 680px / Mobile 380px) |
| `docs/design-requests/compare_mail_v2/Gregor20-Ortsvergleich-Mail.html` | Canvas-Rahmen der Vorlage |
| `src/output/renderers/email/compare_html.py` | Zu ersetzender HTML-Renderer (675 LoC): `render_compare_html()` mit Winner-Card, Matrix, Hourly-Top-N |
| `src/output/renderers/comparison.py` | `render_compare_email()` = Versand-Wrapper (HTML+Text). Enthält Klartext-Renderer mit „🏆 EMPFEHLUNG / Score" (Z. 356–383) und einen älteren HTML-Pfad (Z. 59–172, Verdacht toter Renderer → #1108) |
| `src/services/scheduler_dispatch_service.py` | `send_one_compare_preset()` (Z. 198–262): einziger echter Versandpfad, ruft `render_compare_email(result, profile=profile)` |
| `src/services/validator_render_service.py` | Zweiter Aufrufer von `render_compare_html` (Validator-Probe) |
| `src/output/renderers/email/design_tokens.py` | Farb-/Font-Konstanten der Mail-Renderer |
| `src/output/renderers/alert/official_alerts.py` | Kanonischer Warn-Renderer (`render_official_alerts_html`, ADR-0011) — Quelle für Warn-Kürzel/Langform |
| `src/app/user.py` | `LocationResult` (Z. 148, inkl. `official_alerts`, `hourly_data`), `ComparisonResult` (Z. 178, `winner`-Property) |
| `src/app/models.py` | `ForecastDataPoint` (Z. 88): alle Stundenfelder für die v2-Tabelle vorhanden |
| `.claude/hooks/email_spec_validator.py` | Compare-Mail-Gate: verlangt heute „Winner-Box/Empfehlung", `matrix-table`-Klasse, Hourly (Z. 119–242) — muss auf v2-Vertrag umgestellt werden |
| `src/services/comparison_engine.py` | Erzeugt `ComparisonResult` inkl. `official_alerts_enabled` (#1040) |

## Datenverfügbarkeit für das v2-Layout

**Stundentabelle (Vorlage: Zeit/Temp/Gef./Wind/Böen/Regen/Wolken/UV):**
`ForecastDataPoint` liefert `t2m_c`, `wind10m_kmh`, `gust_kmh`, `precip_1h_mm`,
`cloud_total_pct`, `uv_index` ✓. **Lücke:** „Gefühlt" existiert nur als Winter-Feld
`wind_chill_c`; eine Sommer-„gefühlte Temperatur" (apparent temperature / Hitzeindex)
gibt es nicht → Spec-Entscheidung nötig (Spalte berechnen aus t2m+humidity, Provider-Feld
ergänzen, oder Spalte vorerst weglassen).

**Übersichtstabelle (Temp max / Wind / Sonne / Wolken / UV max):**
`LocationResult` hat `temp_max`, `wind_max`, `sunny_hours`, `cloud_avg` ✓;
`uv_max` nicht aggregiert → aus `hourly_data` ableitbar (max `uv_index`).

**Warn-Zeile / Warn-Streifen:** `LocationResult.official_alerts` vorhanden (#1034),
Massiv-Sperren/Zugang (#1037) und Vigilance-Typen (Hitze, Waldbrand-Stufen) existieren.
Kürzel-Chips (Vorlage: „Hitze", „Brand · 3", „Zugang") aus dem kanonischen Katalog ableiten.

## Existing Patterns

- **Trip-Briefing-Mail** (`src/output/renderers/email/html.py`): gleiche Risk-Zellfärbung
  (4 Stufen), Mono-Tabellen, dunkler Footer — v2 übernimmt exakt dieses Vokabular; Farben
  der Vorlage (`CV2_RISK_CELL`, `CV2_TAG`) decken sich mit den bestehenden Tag-Farben in
  `compare_html.py` (`_TAG_COLORS`, Issue #460).
- **Atomic-Design in Renderern:** kleine private Render-Helfer je Baustein (bestehendes
  Muster `_render_tag`, `_render_header` …) — v2-Bausteine: Eyebrow, Tag, Stat, SectionHead,
  WarnChip/WarnStack, OverviewTable, HourTable, Legend, AboFooter, AppFooter.
- **Mail-Kompatibilität:** Inline-CSS only (Outlook), `@media (max-width:480px)`-Block,
  Marker-Header `X-GZ-Mail-Type: compare` (gesetzt im Versandpfad, bleibt unverändert).

## Dependencies

- **Upstream:** `ComparisonEngine.run()` (Datenlage unverändert), `profile_signature`,
  `design_tokens`, `render_official_alerts_html`.
- **Downstream:** `send_one_compare_preset` (Versand), `validator_render_service`
  (Validator-Probe), `.claude/hooks/email_spec_validator.py` (Gate),
  Frontend-Preview? — `render_compare_email` wird nur von den beiden o.g. Stellen genutzt
  (Preview-/Versand-Divergenz-Falle beachten, vgl. #954).

## Existing Specs

- `docs/specs/modules/issue_253_compare_email.md` — Spec des ALTEN Layouts (wird ersetzt/superseded)
- ADR-0011 (kanonischer Alert-Renderer) — Warn-Darstellung muss daraus abgeleitet werden

## Verwandte Issues

- #1104–#1107 (Konfigurierbarkeit, setzt NACH diesem Issue auf) · #1108 (Validator
  config-bewusst + toter Renderer) · #1038 (fehlende Sektionen — Winner-Box-Erwartung wird
  durch v2 bewusst überholt) · #1055 (Validator-Sprachvertrag veraltet) · #1095 (Alerts
  konfigurierbar)

## Risks & Considerations

1. **Gate-Kopplung:** `email_spec_validator.py` verlangt „Empfehlung/Winner-Box" — ohne
   gleichzeitige Vertrags-Umstellung ist das Gate nach dem Redesign strukturell unbestehbar
   (Gate-Erosion-Gefahr). Umstellung gehört in DIESEN Change (koordiniert mit #1108).
2. **Klartext-Teil:** `render_compare_email` liefert auch text_body mit Score/🏆 — muss
   mitgezogen werden, sonst widersprechen sich HTML und Text.
3. **„Gefühlt"-Spalte:** Datenlücke (s.o.) — Spec muss Entscheidung festhalten.
4. **LoC-Limit 250/Workflow:** kompletter Renderer-Rewrite (~675 LoC alt) reißt das Limit
   fast sicher → Override nur mit User-Permission (Memory-Regel) frühzeitig klären.
5. **Renderer-Commit-Gate (#811):** `compare_html.py` liegt unter `src/output/renderers/email/`
   → Commit verlangt frischen `test_issue_811_mode_matrix.py`-Lauf + `briefing_mail_validator`.
   Achtung: das ist der Trip-Briefing-Validator; für Compare gilt zusätzlich
   `email_spec_validator.py` gegen echte Staging-Mail (Stalwart, `X-GZ-Mail-Type: compare`).
6. **Score-Reste:** `LocationResult.score` bleibt im Modell (App nutzt ihn weiter) — nur die
   Mail-Darstellung entfällt. Sortierung der Orte in der Mail: Vorlage sortiert nicht nach
   Score → Spec-Punkt (Reihenfolge = Preset-Reihenfolge?).
7. **Webfonts:** Vorlage lädt Google Fonts — Mail-Clients laden diese oft nicht; Font-Stacks
   mit Fallbacks (wie in Vorlage) genügen, `WEB_FONT_LINK`-Muster existiert bereits.

## Analysis (Phase 2, 2026-07-08)

### Type
Feature (Design-Umsetzung nach Vorlage, Issue #1110)

### Affected Files (with changes)

| File | Change Type | Description |
|------|-------------|-------------|
| `src/output/renderers/email/compare_html.py` | REWRITE | v2-Layout nach JSX-Vorlage; Winner-Card/-Tags, `_generate_winner_tags`, Score-Matrix, Top-N-Hourly raus; neue atomare Bausteine (Header, Stats, Warn-Lead, Overview inkl. Warn-Zeile, HourTable alle Orte, Legende, Abo-/App-Footer) |
| `src/output/renderers/comparison.py` | MODIFY | `render_comparison_text` (Z. 330–461) Neuschrieb ohne 🏆/Score; `render_comparison_html` (Z. 26–327) = bestätigt toter Alt-Renderer → entfernen (koordiniert mit #1108) |
| `src/services/validator_render_service.py` | MODIFY | Aufruf Z. 170 an neue Signatur anpassen (winner_tags entfällt) |
| `src/services/compare_subscription.py` | MODIFY | privater Import `_generate_winner_tags` (Z. 54) entfällt; Abo-Footer-Daten (Abo-Name, nächster Versand) durchreichen |
| `.claude/hooks/email_spec_validator.py` | REWRITE (Kern) | Vertrag ist noch ALTER Ski-Vergleich (8 englische Pflicht-Labels, „Recommendation/Empfehlung"-Pflicht, Z. 214–244) — Umstellung auf v2-Vertrag (Übersicht Metriken×Orte + Warn-Zeile, KEINE Winner-Box, Hourly für alle Orte) |
| `tests/tdd/test_compare_html_email.py` | REWRITE | 20 Tests größtenteils Winner/Score-spezifisch |
| `tests/tdd/test_issue_464_compare_email_preview.py` | MODIFY | Tag-Farben-/winner_tags-Asserts |
| `docs/specs/modules/issue_253_compare_email.md`, `issue_460_…`, `docs/reference/mail_validators.md` | MODIFY | Spec-/Doku-Nachzug (superseded-Vermerk bzw. neuer Vertrag) |

### Scope Assessment
- Files: ~8 Code/Test + 3 Doku
- Estimated LoC: 600–900 angefasst (Renderer + Klartext + Validator + Tests; toter Renderer −300)
- **Workflow-LoC-Limit 250 wird sicher gerissen → User-Erlaubnis für Override (~600) VOR Implementierung einholen (Memory-Regel)**
- Risk Level: MEDIUM (reines Rendering, aber Gate-Kopplung + zwei Voll-Rewrites)

### Technical Approach (Plan-Agent-Empfehlung, übernommen)
- **Voller Neuschrieb** von `compare_html.py` statt inkrementellem Umbau — JSX-Struktur (flache Metrik-Liste, kein primary/secondary, kein Winner) passt nicht auf `CE_PROFILES`. `METRIC_LABELS/UNITS/DIRECTION` bleiben als Datenbasis der Highlight-Logik.
- **Outlook-Pattern statt wörtlichem CSS:** Vorlage nutzt flex/grid → in Mail-Clients nicht tragfähig; bestehendes Doppel-`<table>`-Pattern (Desktop/Mobile via media query, compare_html.py:364–385) für alle Grid-Stellen übernehmen. „1:1" = Farben/Abstände/Typo/Struktur-Absicht.
- **Warn-Kürzel:** `OfficialAlert.hazard` existiert zuverlässig (verifiziert: vigilance `_PHENOMENON_MAP` → (hazard, label); `wildfire_risk`; `access_ban`) → dünnes Anzeige-Mapping hazard→Kürzel („Hitze", „Brand · N" aus level, „Zugang") mit Fallback auf `label` für unbekannte hazards. KEINE neue Taxonomie. (Korrektur zur Plan-Agent-Aussage „kein hazard-Feld".)
- **„Gefühlt"-Spalte:** KEINE Datenlücke — Open-Meteo mappt `apparent_temperature` →
  `ForecastDataPoint.wind_chill_c` (src/providers/openmeteo.py:305, 712); die Trip-Mail rendert
  genau dieses Feld als „gef. X°" (html.py:191). PO-Klärung 2026-07-08: gleiche Daten wie Trips
  1:1 verwenden → Spalte kommt rein, `wind_chill_c` als Quelle, „—" wenn None. (Feldname ist
  historisch irreführend, im Sommer = Hitze-gefühlte Temperatur.)
- **Ort-Reihenfolge:** ohne Score keine Rangfolge → Reihenfolge = `result.locations` (Preset-Reihenfolge), kein Sort.
- **Klartext-Teil** wird strukturell an v2 angeglichen (Übersicht + Warnungen, kein 🏆/Score).

### Dependencies
- Aufrufer: `send_one_compare_preset` (scheduler_dispatch_service.py:198), `compare_subscription.py:53`, `validator_render_service.py:170` (Preview-Endpoint issue_464).
- Gates pro Commit: Renderer-Commit-Gate #811 (mode-matrix-Test + briefing_mail_validator) UND `email_spec_validator.py` gegen echte Staging-Mail (`X-GZ-Mail-Type: compare`).
- Koordination: #1108 (Validator + toter Renderer — Löschung von `render_comparison_html` hier miterledigt, im Issue vermerken), #1104–#1107 setzen danach auf.

### PO-Entscheidungen Phase 2 (2026-07-08)
- [x] LoC-Override 600 genehmigt (gesetzt via `workflow.py set-field loc_limit_override 600`)
- [x] „Gefühlt"-Spalte bleibt drin — gleiche Datenquelle wie Trips (`wind_chill_c` = Open-Meteo
      `apparent_temperature`), kein Provider-Ausbau nötig
