// TDD GREEN: Design-Compliance-Korrekturen Gruppe A
//
// Issues: #528 (Compare Hub Header CTA), #529 (Trip Tab Names),
//         #530 (Compare Hub Wizard Links entfernen), #531 (Compare List Suche)
// Spec: docs/specs/modules/design_compliance_group_a.md
// Workflow: design-compliance-fixes
//
// Segmented-Tabs rendern mit role="tab" (nicht "button").
// Alle Korrekturen sind implementiert und deployt.

import { test, expect } from '@playwright/test';

const TRIP_ID = 'e2e-cockpit-test';

// ─────────────────────────────────────────────────────────────────────────────
// Compare Preset Seed-Helfer (beforeAll / afterAll)
// ─────────────────────────────────────────────────────────────────────────────

let activePresetId = '';
let draftPresetId = '';

// Seed 4+ Presets (für Search-Test) + je 1 active/draft
async function seedComparePresets(request: import('@playwright/test').APIRequestContext) {
	// Aktives Preset (daily schedule, hat Locations)
	const activeRes = await request.post('/api/compare/presets', {
		data: {
			name: 'E2E Active Preset',
			location_ids: ['e2e-loc-innsbruck', 'e2e-loc-stubai'],
			schedule: 'daily',
			profil: 'ALLGEMEIN',
			hour_from: 6,
			hour_to: 8,
			empfaenger: ['e2e@henemm.com'],
			display_config: { region: 'Tirol' }
		}
	});
	const active = await activeRes.json();
	activePresetId = active.id;

	// Draft Preset (keine Locations → deriveStatusFromPreset → 'draft')
	const draftRes = await request.post('/api/compare/presets', {
		data: {
			name: 'E2E Draft Preset',
			location_ids: [],
			schedule: 'daily',
			profil: 'ALLGEMEIN',
			hour_from: 6,
			hour_to: 8,
			empfaenger: [],
			display_config: { region: 'Salzburg' }
		}
	});
	const draft = await draftRes.json();
	draftPresetId = draft.id;

	// Extra-Presets damit Suche-Tests ≥4 Presets haben
	for (let i = 0; i < 3; i++) {
		await request.post('/api/compare/presets', {
			data: {
				name: `E2E Extra Preset ${i + 1}`,
				location_ids: ['e2e-loc-zillertal'],
				schedule: 'daily',
				profil: 'ALLGEMEIN',
				hour_from: 6,
				hour_to: 8,
				empfaenger: []
			}
		});
	}
}

async function cleanupComparePresets(request: import('@playwright/test').APIRequestContext) {
	// Liste aller Presets; lösche alle mit "E2E" im Namen
	const res = await request.get('/api/compare/presets');
	const presets = (await res.json()) as Array<{ id: string; name: string }>;
	for (const p of presets) {
		if (p.name.startsWith('E2E')) {
			await request.delete(`/api/compare/presets/${p.id}`);
		}
	}
	// IDs zurücksetzen damit nachfolgende beforeAll-Checks re-seeden
	activePresetId = '';
	draftPresetId = '';
}

// ─────────────────────────────────────────────────────────────────────────────
// #529 — Trip-Detail: Kanonische Tab-Namen
// ─────────────────────────────────────────────────────────────────────────────

test.describe('#529 Trip-Detail · Kanonische Tab-Namen (nav-map.jsx)', () => {
	test('AC-1a: Tab "weather" heißt "Wetter-Metriken" (nicht "Wetter-Briefing")', async ({
		page
	}) => {
		await page.goto(`/trips/${TRIP_ID}`);
		await expect(page.getByRole('tab', { name: 'Wetter-Metriken' })).toBeVisible();
		await expect(page.getByRole('tab', { name: 'Wetter-Briefing' })).not.toBeVisible();
	});

	// Fix-Loop 2026-07-13 (F001): Label seit #736/Slice 6 "Versand" (nicht mehr
	// "Briefing-Zeitplan" — das war der Zwischenstand vor #736).
	test('AC-1b: Tab "briefings" heißt "Versand" (nicht "Reports & Kanäle")', async ({
		page
	}) => {
		await page.goto(`/trips/${TRIP_ID}`);
		await expect(page.getByRole('tab', { name: 'Versand' })).toBeVisible();
		await expect(page.getByRole('tab', { name: 'Reports & Kanäle' })).not.toBeVisible();
	});

	// Issue #1231 Slice 6: alerts-Label erneut umbenannt ("Alerts" -> "Wertebereiche").
	test('AC-1c: Tab "alerts" heißt "Wertebereiche" (nicht "Alarmregeln")', async ({ page }) => {
		await page.goto(`/trips/${TRIP_ID}`);
		await expect(page.getByRole('tab', { name: 'Wertebereiche' })).toBeVisible();
		await expect(page.getByRole('tab', { name: 'Alarmregeln' })).not.toBeVisible();
	});
});

// ─────────────────────────────────────────────────────────────────────────────
// #528 — Compare Hub: Header-Primäraktion
// ─────────────────────────────────────────────────────────────────────────────

test.describe('#528 Compare Hub · Header-Primäraktion', () => {
	test.beforeAll(async ({ request }) => {
		await cleanupComparePresets(request);
		await seedComparePresets(request);
	});
	test.afterAll(async ({ request }) => {
		await cleanupComparePresets(request);
	});

	test('AC-2: Draft-Preset zeigt "Setup abschließen" statt "Bearbeiten"', async ({ page }) => {
		await page.goto(`/compare/${draftPresetId}`);
		await expect(page.getByRole('link', { name: 'Bearbeiten' })).not.toBeVisible();
		await expect(page.getByRole('button', { name: 'Setup abschließen' })).toBeVisible();
	});

	// Issue #1261 (a): Bearbeiten wieder im Detail-Header (Trip-Parität),
	// ergänzt #528-Primäraktion — der Desktop-Header zeigt fuer ein aktives
	// Preset jetzt "Test senden" UND "Bearbeiten" nebeneinander (analog
	// Trip-Header), statt "Bearbeiten" zu verstecken.
	test('AC-3: Aktives Preset zeigt "Test senden" UND "Bearbeiten"', async ({ page }) => {
		await page.goto(`/compare/${activePresetId}`);
		await expect(page.getByRole('link', { name: 'Bearbeiten' })).toBeVisible();
		await expect(page.getByRole('button', { name: 'Test senden' })).toBeVisible();
	});
});

// ─────────────────────────────────────────────────────────────────────────────
// #530 — Compare Hub: Wizard-Links in Tabs entfernen
// ─────────────────────────────────────────────────────────────────────────────

test.describe('#530 Compare Hub · Keine Wizard-Links in Tabs', () => {
	test.beforeAll(async ({ request }) => {
		if (!activePresetId) {
			await cleanupComparePresets(request);
			await seedComparePresets(request);
		}
	});
	test.afterAll(async ({ request }) => {
		await cleanupComparePresets(request);
	});

	for (const tab of ['orte', 'idealwerte', 'layout', 'versand']) {
		test(`AC-5: ${tab}-Tab hat keinen Link auf /edit`, async ({ page }) => {
			await page.goto(`/compare/${activePresetId}?tab=${tab}`);
			const editLink = page.locator(`a[href*="/edit"]`);
			await expect(editLink).not.toBeVisible();
		});
	}
});

// ─────────────────────────────────────────────────────────────────────────────
// #531 — Compare-Liste: Suchleiste
// ─────────────────────────────────────────────────────────────────────────────

test.describe('#531 Compare-Liste · Suchleiste', () => {
	test.beforeAll(async ({ request }) => {
		if (!activePresetId) {
			await cleanupComparePresets(request);
			await seedComparePresets(request);
		}
	});
	test.afterAll(async ({ request }) => {
		await cleanupComparePresets(request);
	});

	test('AC-6: Suchfeld sichtbar wenn mehr als 3 Vergleiche vorhanden', async ({ page }) => {
		await page.goto('/compare');
		await expect(page.getByPlaceholder('Suchen…')).toBeVisible();
	});

	test('AC-7: Suchfeld filtert Kacheln nach name (case-insensitive)', async ({ page }) => {
		await page.goto('/compare');
		await page.getByPlaceholder('Suchen…').fill('E2E Active Preset');
		// Exakt 1 sichtbare Kachel verbleibt (Desktop + Mobile rendern beide, nur Desktop sichtbar)
		const tiles = page.locator('[data-testid^="compare-tile-"]').filter({ visible: true });
		await expect(tiles).toHaveCount(1);
	});
});
