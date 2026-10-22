---
entity_id: mobile_ux_audit_2601
type: module
created: 2026-10-22
updated: 2026-10-22
status: draft
version: "1.0"
tags: [mobile, ux, e2e, audit]
---

# Mobile-UX-Audit (#2601)

## Approval

- [ ] Approved

## Purpose

Wiederholbarer Audit aller Routen in drei Smartphone-Profilen (390×844, 402×874, Querformat 844×390), der Erreichbarkeit und Bedienbarkeit prüft, plus die Behebung der dabei gefundenen Befunde. Leitfrage: Ist jedes Bedienelement auf dem Telefon antippbar und lesbar?

## Source

- **File:** `frontend/e2e/mobile-ux-audit.spec.ts`, `frontend/playwright.mobile-ux.local.config.ts`
- **Identifier:** `LAYOUT_CHECK`, `auditRoute`, `OVERLAYS`
- **Fixes (Frontend):** `frontend/src/app.css` (Touch-Regeln, `.g-link-tap`, Hinweis-Freihaltung), `StageCardM.svelte`, `StageDateField.svelte`, `StageTimeField.svelte`, `DragHandle.svelte`, `AlertChannelPicker.svelte`, `Select.svelte`, `Stat.svelte`, Login/Register/Forgot-Links, Startseiten-Links, Kleintexte < 11px in mobil sichtbaren Bausteinen

## Estimated Scope

- **LoC:** ~180 (davon ~120 Audit-Spec, Rest CSS/Markup-Einzeiler)
- **Files:** 38
- **Effort:** medium

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `frontend/e2e/ci-stack.sh` | Script | Offline-Stack (Go + Python) für den lokalen Lauf |
| `frontend/e2e/global.setup.ts` | Setup | Anmeldung + Seed (`playwright/.auth/admin.json`) |
| `mobile_tab_leisten_mtabbar` | Spec | Tab-Leiste (44px-Trigger) bleibt unverändert |

## Implementation Details

```
Audit (je Route, je Detail-Tab, je Overlay):
  (a) page-level horizontaler Overflow (Fenster UND <main class="mobile-scroll-pad">)
  (b) überstehende Elemente ohne overflow-x auto/scroll
  (c) interaktive Elemente horizontal außerhalb des Viewports (nicht in h-scrollbarem Container)
  (d) interaktive Elemente am Scroll-Ende unter fixen/sticky Leisten (elementFromPoint)
  (e) Tap-Ziele < 24px (hart) / < 40px (Hinweis); ::after-Trefferflächen zählen mit;
      Inline-Textlinks ausgenommen (WCAG 2.5.8)
  (f) Text < 11px; input/select/textarea < 16px (iOS-Auto-Zoom)
  (g) overflow-hidden-Clipping, scrollbare Mini-Bereiche (Hinweis)
  GZ_AUDIT_STRICT=1 → (a),(c),(d),(e-hart) lassen den Lauf fehlschlagen.

Fixes:
  - @media (max-width: 899px), (pointer: coarse): input/select/textarea 16px;
    Häkchen/Radios 20px + Label min-height 44px; Btn[sm] 36px; sonstige <button> 36px;
    Textfelder 40px; segmented-item 36px; Schalter mit ::after-Trefferfläche
  - .g-link-tap: Padding + negativer Rand → 44px Trefferhöhe ohne Layoutänderung
  - body:has(ios-install-hint|passkey-angebot) .mobile-scroll-pad: +72px Freihaltung
  - @media (max-height: 500px): iOS-Install-Hinweis ausgeblendet (Querformat)
  - StageCardM .top/.date-edit: flex-wrap (Zeitfeld ragte auf 390px aus dem Viewport)
  - Kleintexte 9–10.5px → 11px (= --g-text-xs)
```

## Expected Behavior

- **Input:** Preview auf `localhost:4173`, Stack auf 8091, `playwright/.auth/admin.json`
- **Output:** `test-results/mobile-ux/report-<projekt>[-public].{json,md}` + Screenshots je Route/Tab/Overlay
- **Side effects:** keine (nur lesende Navigation; Overlays werden per Escape geschlossen)

## Acceptance Criteria

- **AC-1:** Given ein Trip mit 8 Etappen und Datums-/Zeitbearbeitung / When der Etappen-Tab auf 390px Breite geöffnet wird / Then liegt kein interaktives Element (Datum, Startzeit) horizontal außerhalb des Viewports und die Seite hat keinen horizontalen Overflow.
  - Test: `mobile-ux-audit.spec.ts` (strict) — `offscreenInteractive` und `pageOverflowPx` leer auf `/trips/[id]#etappen`.

- **AC-2:** Given der iOS-Install-Hinweis ist sichtbar / When eine beliebige Seite bis zum Ende gescrollt wird / Then sind Footer-Links und letzte Bedienelemente antippbar (nicht unter Hinweis oder Bottom-Nav).
  - Test: Audit-Check (d) `coveredInteractive` leer auf allen Routen.

- **AC-3:** Given Alarme-Tab (Trip und Vergleich) / When die Schwellen-Knöpfe und Kanal-Schalter gemessen werden / Then ist jedes Tap-Ziel mindestens 24×24px (Schalter inkl. unsichtbarer Trefferfläche, Knöpfe ≥ 32px hoch).
  - Test: Audit-Check (e) `tinyTargets` leer auf `#alarme`.

- **AC-4:** Given Login-, Registrier- und Passwort-vergessen-Seite im Querformat / When die Seite geladen wird / Then haben alle Eingabefelder ≥ 16px Schrift und die Textlinks ≥ 44px Trefferhöhe.
  - Test: Audit `öffentliche Routen` (landscape): `smallInputs` und `tinyTargets` leer.

- **AC-5:** Given Konto-Sheet, Karten-Menü und Sende-Dialog / When sie auf dem Telefon geöffnet werden / Then sind sie sichtbar, ohne horizontalen Overflow und ohne Tap-Ziel < 24px.
  - Test: Audit `OVERLAYS`-Proben (`konto-sheet`, `karten-menue`, `sende-dialog`).

- **AC-6:** Given Native Häkchen/Radios (Wetter-Metriken, Mail-Format, Vorschau) / When auf Touch/≤899px gerendert / Then sind sie 20px groß und ihr Label mindestens 44px hoch.
  - Test: Audit-Check (e) auf `#wetter-metriken`, `#vorschau`.

## Known Limitations

- Nur Chromium-Emulation (kein WebKit in der Umgebung); Safari-spezifisches Rendering bleibt dem Staging-Audit (`playwright.mobile-usability.config.ts`) vorbehalten.
- Tap-Ziele zwischen 24 und 40px bleiben Hinweise (116 Stellen, v. a. 32–36px-Chips) — kein Blocker.
- Drei Kleintexte bleiben bei 10px: Icon-Glyphen ✉/✈ in der Übersicht und der „Aktionen"-Kopf im Karten-Menü (bits-ui-Dropdown).

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** reine Darstellungs-/Erreichbarkeits-Korrekturen und ein zusätzlicher Nachweis; keine Entscheidungsfläche berührt.

## Changelog

- 2026-10-22: Erstfassung (#2601).
