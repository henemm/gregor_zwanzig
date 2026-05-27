# Context: Issue #406 — Epic #404 Phase 3: SOLL-IST-Vergleich

## Request Summary

Systematischer visueller Vergleich von 26 IST-Screenshots (Playwright gegen Staging) mit den
korrespondierenden SOLL-Screenshots (aus den Claude-Design-Handoffs). Reihenfolge: Bottom-Up
(Atoms → Molecules → Screens). Output: Findings-Liste (BLOCKER/MEDIUM/LOW) + GitHub Issues +
Abschlussbericht `docs/analysis/epic_404_phase3_soll_ist_vergleich.md`.

## Voraussetzungen — alle erfüllt ✅

| Issue | Status |
|-------|--------|
| #392 organisms.jsx / Metrics-Editor | CLOSED |
| #396 Archiv-Statistiken | CLOSED |
| #402 Trips Atomic Migration | CLOSED |
| #403 TripTabs Segmented | CLOSED |
| #405 SMS-Preview-Screenshot-Fix | CLOSED |

## Screenshot-Bestände

### SOLL (50 PNGs aus Design-Handoff)
- **Verzeichnis:** `claude-code-handoff/soll-audit-2026-05-27/soll-screenshots/`
- Desktop: `desktop-*.png` (22 Dateien, inkl. compare-email-Varianten)
- Mobile: `mobile-m-*.png` (21 Dateien)
- Komponenten: `komponenten-ds-desktop.png`, `komponenten-ds-mobile.png`, `komponenten-full.png`, `komponenten-legend.png`

### IST (26 PNGs via Playwright gegen Staging)
- **Verzeichnis:** `claude-code-handoff/soll-audit-2026-05-27/ist-screenshots/`
- Desktop: 15 Dateien (`desktop-alerts.png`, `desktop-archive.png`, `desktop-compare-main.png`, `desktop-email-preview.png`, `desktop-home.png`, `desktop-location-new.png`, `desktop-metrics.png`, `desktop-sms-preview.png`, `desktop-trip-detail.png`, `desktop-trips-list.png`, `desktop-wizard-step1–4.png`, `desktop-wp-editor.png`)
- Mobile: 11 Dateien (`mobile-m-alerts.png`, `mobile-m-compare.png`, `mobile-m-home.png`, `mobile-m-metrics.png`, `mobile-m-trip-detail.png`, `mobile-m-trips.png`, `mobile-m-wiz-1–4.png`, `mobile-m-wp-editor.png`)

### Paare (SOLL → IST)
26 direkte Namensgleich-Paare. Keine IST-Entsprechung für:
- `desktop-compare-email-*.png` (4 Varianten, SOLL-only — E-Mail-Outputs, nicht navigierbar)
- `desktop-full.png`, `mobile-full.png`, `komponenten-full.png` (Übersichtsbilder)
- `mobile-m-login.png`, `mobile-m-modal.png`, `mobile-m-output.png` etc. (zusätzliche SOLL-Screens)

## Vergleichs-Ebenen (Bottom-Up)

### Ebene 1 — Atoms
- **SOLL:** `soll-screenshots/komponenten-ds-desktop.png` + `komponenten-ds-mobile.png`
- **IST:** Live-Showcase unter `/_design-system` (kein Screenshot vorhanden — Playwright-Lauf oder visuelle Prüfung nötig)
- **Code:** `frontend/src/lib/components/atoms/` (Btn, Card, Dot, Eyebrow, Input, KV, Pill, SectionH, Segmented, Switch, TopoBg, WIcon, ElevSparkline)

### Ebene 2 — Molecules
- **SOLL:** Gleiche `komponenten-ds-*`-Screens (Molecules-Sektion)
- **IST:** `/_design-system` Molecules-Sektion
- **Code:** `frontend/src/lib/components/molecules/` (AlertRow, BriefingScheduleRow, BriefingTimelineRow, ChannelChip, ChannelRow, DetailRow, Field, StagePill, Stat, ThresholdRow)

### Ebene 3 — Screens (26 Paare)
| Gruppe | Screens |
|--------|---------|
| Desktop (15) | home, trips-list, trip-detail, metrics, alerts, email-preview, sms-preview, wp-editor, wizard-step1–4, compare-main, archive, location-new |
| Mobile (11) | m-home, m-trips, m-trip-detail, m-alerts, m-metrics, m-wiz-1–4, m-compare, m-wp-editor |

## Code-Quellen (IST)

| Screen | Haupt-Datei |
|--------|-------------|
| Home | `frontend/src/routes/+page.svelte` |
| Trips-Liste | `frontend/src/routes/trips/+page.svelte` |
| Trip-Detail | `frontend/src/routes/trips/[id]/+page.svelte` |
| Trip-Wizard | `frontend/src/routes/trips/new/+page.svelte` |
| Compare | `frontend/src/routes/compare/+page.svelte` |
| Archiv | `frontend/src/routes/archiv/+page.svelte` |
| Wegpunkt-Editor | `frontend/src/routes/trips/[id]/edit/+page.svelte` |
| Atoms | `frontend/src/lib/components/atoms/` |
| Molecules | `frontend/src/lib/components/molecules/` |
| Design-System Showcase | `frontend/src/routes/_design-system/+page.svelte` |

## Design-System Tokens

- **Zentral:** `frontend/src/app.css`
- **Python-Tokens:** `src/app/design_tokens.py`
- **Referenz:** `docs/design-system/TOKENS.md`, `docs/design-system/COMPONENTS.md`

## Findings-Klassifikation

| Stufe | Bedeutung |
|-------|-----------|
| BLOCKER | Sichtbarer Inhaltsfehler, fehlende Funktionalität, WCAG-Verstoß |
| MEDIUM | Visuelle Abweichung mit Nutzer-Impact (Farbe, Spacing, Typografie) |
| LOW | Kosmetik, Feintuning, kein Nutzer-Impact |

## Output

- **Primär:** `docs/analysis/epic_404_phase3_soll_ist_vergleich.md` (Abschlussbericht + alle Findings)
- **Sekundär:** GitHub Issues für jede echte Lücke (BLOCKER + ausgewählte MEDIUM)

## Abhängigkeiten

- **Upstream:** Phase 1 (SOLL) + Phase 2 (IST) — beide abgeschlossen
- **Downstream:** Phase 4 (Validator-Agents), Phase 5 (Issue-Erstellung)
- **Staging:** `https://staging.gregor20.henemm.com` — muss laufen für etwaige /_design-system-Prüfung

## Risiken

- `desktop-sms-preview.png` war in Phase 2 fehlerhaft (byte-identisch mit email) → durch #405 behoben, aber Screenshot muss auf Korrektheit geprüft werden
- Atoms/Molecules-IST hat keinen fertigen Screenshot → muss live oder per neuem Playwright-Lauf geprüft werden
- Manche SOLL-Screens zeigen UI-Zustände, die schwer reproduzierbar sind (Modal, Sheet, Toast) → kein IST vorhanden, kein Vergleich möglich
