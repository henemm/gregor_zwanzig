// TDD RED: Bug #274 — Safe-Area-Insets für Sticky-Bottom-Bar im Trip-Edit
//
// Spec: docs/specs/modules/bug_274_safe_area_insets.md
// Phase 5 (TDD RED) — Test MUSS FEHLSCHLAGEN bis Phase 6.
//
// AC-1: app.html-Viewport-Meta enthält viewport-fit=cover (sonst ignoriert
//        iOS Safari alle env(safe-area-inset-*)-Aufrufe).
// AC-2: Die fixed Bottom-Action-Bar im Trip-Edit (Container von
//        [data-testid="edit-save-btn"]) hat ein style-Attribut mit
//        padding-bottom und env(safe-area-inset-bottom.
//
// KEINE Mocks — echter SvelteKit-Build via Playwright-Preview, echte DOM-Prüfung.
// env(safe-area-inset-bottom) ergibt im Test-Viewport immer 0px (kein iOS-Gerät);
// Akzeptanz-Nachweis daher über DOM-Attribut-Prüfung statt Pixel-Messung.

import { test, expect } from '@playwright/test';

const TRIP_ID = 'e2e-cockpit-test';
const EDIT_URL = `/trips/${TRIP_ID}/edit`;

// =============================================================================
// AC-1: Viewport-Meta-Tag enthält viewport-fit=cover
// =============================================================================

test('AC-1: viewport-meta enthält viewport-fit=cover', async ({ page }) => {
	await page.goto(EDIT_URL);
	const viewport = page.locator('meta[name="viewport"]');
	await expect(viewport).toHaveAttribute('content', /viewport-fit=cover/);
});

// =============================================================================
// AC-2: ENTFALLEN — der geprüfte Prüfling existiert nicht mehr
// =============================================================================
//
// AC-2 prüfte die fixed Bottom-Action-Bar der separaten Trip-Edit-Seite
// (Container von [data-testid="edit-save-btn"] in TripEditView.svelte).
// Issue #616 („EINE Trip-Seite") hat diese Fläche abgeschafft:
// `/trips/[id]/edit/+page.server.ts` wirft heute einen 307-Redirect auf
// `/trips/[id]`, und TripEditView.svelte wird von keiner Route mehr
// eingebunden. Der Test lief deshalb zwangsläufig in „element(s) not found" —
// er prüfte ein bewusst entferntes Verhalten (#1771 S3, Entscheidungsregel 1:
// veraltete Prüfung löschen).
//
// Die Safe-Area-Zusicherung selbst ist NICHT ersatzlos weg, sie sitzt heute an
// anderen Stellen und mit anderer Mechanik (CSS-Regel statt style-Attribut):
// BottomNav.svelte:28, routes/trips/+page.svelte:513, Sheet.svelte:136,
// SaveIndicator.svelte:83, app.css:196 sowie EditStagesPanelNew.svelte:83-88
// (liest den Inset zur Laufzeit als px-Zahl aus). Ein e2e-Nachweis dafür wäre
// ein eigener Test gegen eine andere Fläche, keine Reparatur dieses hier —
// er wird hier bewusst nicht nachgezogen.
//
// AC-1 (viewport-fit=cover in app.html) bleibt und trägt weiterhin die
// Vorbedingung, ohne die iOS Safari alle env(safe-area-inset-*) ignoriert.
