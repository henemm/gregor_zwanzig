---
entity_id: issue_1056_vigilance_badge_color
type: module
created: 2026-07-10
updated: 2026-07-10
status: draft
version: "2.0"
tags: [bug, official-alerts, email-renderer, design-tokens]
---

<!-- Issue #1056 — Vigilance-Badge: Level 2 (gelb) wird fälschlich grün gerendert -->

# Issue 1056 — Amtliche-Warnung-Farben: einheitliche 4-Stufen-Skala

## Approval

- [x] Approved v2.0 (PO 2026-07-10 — „go", vereinheitlichte Level-Färbung inkl. Hitze-Stufe-4 → violett)

> **v1.0 war PO-approved (2026-07-10, Palette Variante B).** Beim Rebase auf origin/main
> stellte sich heraus, dass die parallel gemergte #1134 die **Compare-Mail** auf ein
> **Gefahren-Art-Farbschema** (severity) umgestellt hat — Badge UND Übersichts-Chips.
> PO-Entscheidung 2026-07-10: **beide Mail-Typen vereinheitlichen** auf die amtliche
> **Warnstufen-Skala**. Das erweitert den Scope und ersetzt #1134s Severity-Färbung für
> amtliche Warnungen. Daher Neu-Freigabe der v2.0-ACs erforderlich.

## Purpose

Amtliche Warnungen werden farblich **uneinheitlich** dargestellt: Der Trip-Briefing färbt
nach Warnstufe (und rendert Stufe 2 fälschlich grün = „kein Alert", der ursprüngliche Bug),
der Orts-Vergleich seit #1134 nach Gefahren-Art. Ziel: **eine** kanonische, amtstreue
4-Stufen-Skala (grün/gelb/orange-rot/violett) für amtliche Warnungen — angewandt auf
**alle drei** Darstellungen: Trip-Briefing-Badge, Compare-Badge und Compare-Übersichts-Chips.
Die Farbe folgt konsequent der amtlichen `OfficialAlert.level`-Einstufung.

## Source

- **File:** `src/output/renderers/alert/official_alerts.py` — `render_official_alerts_html()`,
  Level→Farb-Mapping (Zeile 56-61). Python-Core / Domain-Backend.
- **File:** `src/output/renderers/email/design_tokens.py` — +3 additive Farb-Tokens `G_ALERT_L2/L3/L4`.

## Estimated Scope

- **LoC:** ~+90/−40 (< 250)
- **Files:** ~7 (2 src: `official_alerts.py`, `compare_html.py`; `design_tokens.py`; 4 Test-Dateien inkl. Neufassung von #1134-Farb-Asserts)
- **Effort:** medium

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `OfficialAlert.level` | Datentyp | int 1-4, Behörden-Warnstufe — **alleinige** Farbquelle (amtstreu) |
| `design_tokens.py` G_* | Konstanten | Rand-Farben; neue `G_ALERT_L2/L3/L4` additiv |
| #1134 (`severity_fn`, `_compare_alert_severity`, Chip-Färbung) | Vorgänger | wird für amtliche Warnungen **ersetzt** (severity → level); Tests neu gefasst |
| `_RISK_CELL` (Wetter-Metrik-Zellen) | UNBERÜHRT | teilt sich das Modul, wird NICHT geändert (nur Warn-Chips bekommen eigene Level-Zellfarben) |
| Renderer-Mailgate #811 | Gate | Commit blockt bis Matrix-Test + Briefing- **und** Radar-Validator frisch grün |

## Implementation Details

**Ausgangslage (nach Rebase auf origin/main):** `render_official_alerts_html(entries, severity_fn=None)`
färbt den Badge im `severity_fn is None`-Zweig level-basiert (buggy: `level<=2 → G_SUCCESS`) und im
`severity_fn`-Zweig (Compare, #1134) hazard-severity-basiert. Zusätzlich färbt `_render_warn_cell()`
in `compare_html.py` die Übersichts-Chips hazard-severity-basiert (`_warn_short` → `_RISK_CELL`).

**Ziel — eine amtstreue Level-Skala für ALLE amtlichen-Warnung-Farben:**

```python
# design_tokens.py (additiv; G_WARNING/G_DANGER unverändert)
G_ALERT_L2 = '#9a6f00'   # gelb  (Rand-Kontrast 4,11:1 auf G_PAPER)
G_ALERT_L3 = '#c8482a'   # orange→rot (4,32:1)
G_ALERT_L4 = '#6d28d9'   # violett = höchste Stufe (6,46:1)

# official_alerts.py — severity_fn-Parameter entfällt für die FARBE; immer level-basiert:
_LEVEL_COLORS = {1: G_SUCCESS, 2: G_ALERT_L2, 3: G_ALERT_L3, 4: G_ALERT_L4}
color = _LEVEL_COLORS.get(alert.level, G_ALERT_L4)   # >4 → höchste Stufe

# compare_html.py — Übersichts-Chips: Zellfarbe nach LEVEL (eigene Map, NICHT _RISK_CELL):
_ALERT_LEVEL_CELL = {   # (bg-Tint, fg) je Stufe, harmonisch zu den Rand-Farben
    1: ('<grün-tint>',   G_SUCCESS),
    2: ('<gelb-tint>',   G_ALERT_L2),
    3: ('<orange-tint>', G_ALERT_L3),
    4: ('<violett-tint>',G_ALERT_L4),
}   # _warn_short() liefert weiterhin den Kürzel-TEXT; nur die Farbe kommt jetzt aus dem Level.
```

**Amtstreue statt Hazard-Heuristik:** #1134 remappte z.B. eine Stufe-4-Hitzewarnung auf „warn" (orange).
v2.0 färbt strikt nach amtlicher Stufe (Stufe 4 → violett = höchste), in Briefing UND Compare, Badge UND Chip.

## Expected Behavior

- **Input:** `OfficialAlert` mit `level ∈ {1,2,3,4}` (Vigilance emittiert real nur ≥2).
- **Output:** In allen drei Darstellungen (Trip-Badge, Compare-Badge, Compare-Chip) folgt die Farbe der Stufe.
- **Side effects:** reine Präsentationsänderung; `_RISK_CELL` (Metrik-Zellen) und Datenpfade unberührt.

## Acceptance Criteria

- **AC-1:** Given eine amtliche Warnung der Stufe 2 / When das Trip-Briefing-Badge gerendert wird /
  Then ist die Rand-Farbe `G_ALERT_L2` (#9a6f00) und **nicht** `G_SUCCESS` (#3a7d44) — Bug-Repro.
  - Test: `render_official_alerts_html([("",[level2])])` → `border-left:4px solid #9a6f00`, `#3a7d44` ausgeschlossen.

- **AC-2:** Given Stufen 1/2/3/4 / When je ein Badge gerendert wird / Then vier verschiedene Rand-Farben
  1=#3a7d44, 2=#9a6f00, 3=#c8482a, 4=#6d28d9.
  - Test: je Level rendern, Farben extrahieren, paarweise Verschiedenheit + exakte Zuordnung.

- **AC-3:** Given Warnstufe > 4 / When ein Badge gerendert wird / Then Fallback auf `G_ALERT_L4` (#6d28d9), kein Fehler.
  - Test: `level=5` → Rand #6d28d9.

- **AC-4:** Given der Fix ist aktiv / When Semantik-Tokens geprüft / Then `G_WARNING` (#c8882a) und
  `G_DANGER` (#b33a2a) unverändert; `G_ALERT_L2/L3/L4` vorhanden.
  - Test: `test_email_design_tokens.py` — Bestand grün, neue Token-Asserts.

- **AC-5 (vereinheitlicht):** Given ein Stufe-2-Alert / When **Compare-Mail UND Trip-Briefing** gerendert werden /
  Then zeigt der Badge in **beiden** die Level-Farbe (#9a6f00 gelb) — der Compare-Badge färbt NICHT mehr
  hazard-severity-basiert (#1134 severity_fn für amtliche Warnungen ersetzt).
  - Test: `render_compare_html()` mit Level-2-Alert enthält `border-left:4px solid #9a6f00`; Trip-Pfad
    (`collect_trip_alert_entries → render_official_alerts_html`) ebenso. Zusätzlich: eine `extreme_heat`-Warnung
    Stufe 4 färbt violett (#6d28d9), NICHT G_WARNING — Beleg, dass Level statt Hazard entscheidet.

- **AC-6 (neu — Chip/Badge-Konsistenz):** Given ein Compare mit einem Stufe-N-Alert / When die
  Übersichtstabelle gerendert wird / Then trägt der Warn-Chip die zur Stufe passende Zellfarbe aus
  `_ALERT_LEVEL_CELL` — dieselbe Stufen-Familie wie der zugehörige Badge (keine Badge↔Chip-Inkonsistenz).
  - Test: Compare mit Stufe-2-Alert → Chip trägt Gelb-Familie; Stufe-4 → Violett-Familie; `_RISK_CELL`-basierte
    **Metrik**-Zellen (Temp/Wind) bleiben unverändert (Regressionsschutz).

- **AC-7 (Regression/Supersede #1134):** Given die vereinheitlichte Färbung / When die Test-Suite läuft /
  Then sind die #1134-Farb-Asserts (severity-basiert) auf Level-Färbung nachgezogen und grün; keine
  ungewollte Regression an Dedup/Zeitfenster/Segment-Bezug (#1134/#1200 Nicht-Farb-Verhalten unverändert).
  - Test: `test_issue_1134_compare_mail_formatting.py` (Farbteil neu gefasst) + `test_issue_1087` Compare-Fragment
    auf Level-Farben nachgezogen; Dedup-/Segment-Tests bleiben grün.

## Known Limitations

- Der Badge/Chip trägt weiterhin **nur Farbe** als Stufen-Cue (kein Level-Wort im Badge; nur im
  Standalone-Alert-Text #1172). Farbfehlsichtigkeit nicht adressiert → Folge-Eintrag #1199.
- Violett als höchste Stufe weicht bewusst von der Météo-France/Meteoalarm-Rot-Konvention ab (PO 2026-07-10).
- **Supersede #1134 (amtliche Warnungen):** Die hazard-aware Severity-Färbung (`severity_fn`, Chip-`_RISK_CELL`
  für Warnungen) wird für amtliche Warnungen durch die Level-Skala ersetzt. Konsequenz: eine hazard-basiert
  „abgemilderte" Warnung (z.B. Hitze Stufe 4 → vorher orange) folgt jetzt der amtlichen Stufe (violett).
  PO-entschieden zugunsten Amtstreue. #1134s Dedup/Zeitfenster/Übersichts-Metrik-Färbung bleiben erhalten.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Weiterhin innerhalb bestehender Architektur (ADR-0011 geteilter Renderer, ADR-0016 Datentyp).
  Die Vereinheitlichung ersetzt eine Färbungs-Policy durch eine amtstreuere — kein neuer Architektur-Freiheitsgrad,
  aber bewusst dokumentierter Supersede von #1134s Färbungs-Entscheidung.

## Changelog

- 2026-07-10: v1.0 — Initial spec (Issue #1056), PO-approved (level-basiertes Badge, Palette Variante B).
- 2026-07-10: v2.0 — Nach Rebase auf #1134/#1200: Scope erweitert auf **Vereinheitlichung** aller amtlichen-Warnung-
  Farben (Trip-Badge + Compare-Badge + Compare-Chip) auf die Level-Skala; ersetzt #1134s Severity-Färbung. Neu-Freigabe.
