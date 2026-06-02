// TDD RED: Design-Compliance-Korrekturen Gruppe A
//
// Issues: #528 (Compare Hub Header CTA), #529 (Trip Tab Names),
//         #530 (Compare Hub Wizard Links entfernen), #531 (Compare List Suche)
// Spec: docs/specs/modules/design_compliance_group_a.md
// Workflow: design-compliance-fixes
//
// Diese Tests schlagen in RED fehl, weil:
//   - Tab "weather" heißt noch "Wetter-Briefing" statt "Wetter-Metriken"
//   - Tab "briefings" heißt noch "Reports & Kanäle" statt "Briefing-Zeitplan"
//   - Tab "alerts" heißt noch "Alarmregeln" statt "Alerts"
//   - Compare Hub Header zeigt "Bearbeiten" statt kontextabhängiger CTA
//   - Compare Hub Tabs haben noch Wizard-Links "/edit"
//   - Compare Liste hat kein Suchfeld

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
			profil: 'wandern',
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
			profil: 'wandern',
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
				profil: 'wandern',
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
}

// ─────────────────────────────────────────────────────────────────────────────
// #529 — Trip-Detail: Kanonische Tab-Namen
// ─────────────────────────────────────────────────────────────────────────────

test.describe('#529 Trip-Detail · Kanonische Tab-Namen (nav-map.jsx)', () => {
	test('AC-1a: Tab "weather" heißt "Wetter-Metriken" (nicht "Wetter-Briefing")', async ({
		page
	}) => {
		await page.goto(`/trips/${TRIP_ID}`);
		await expect(page.getByRole('button', { name: 'Wetter-Metriken' })).toBeVisible();
		await expect(page.getByRole('button', { name: 'Wetter-Briefing' })).not.toBeVisible();
	});

	test('AC-1b: Tab "briefings" heißt "Briefing-Zeitplan" (nicht "Reports & Kanäle")', async ({
		page
	}) => {
		await page.goto(`/trips/${TRIP_ID}`);
		await expect(page.getByRole('button', { name: 'Briefing-Zeitplan' })).toBeVisible();
		await expect(page.getByRole('button', { name: 'Reports & Kanäle' })).not.toBeVisible();
	});

	test('AC-1c: Tab "alerts" heißt "Alerts" (nicht "Alarmregeln")', async ({ page }) => {
		await page.goto(`/trips/${TRIP_ID}`);
		await expect(page.getByRole('button', { name: 'Alerts' })).toBeVisible();
		await expect(page.getByRole('button', { name: 'Alarmregeln' })).not.toBeVisible();
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

	test('AC-3: Aktives Preset zeigt "Test senden" statt "Bearbeiten"', async ({ page }) => {
		await page.goto(`/compare/${activePresetId}`);
		await expect(page.getByRole('link', { name: 'Bearbeiten' })).not.toBeVisible();
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
		// Exakt 1 Kachel verbleibt
		const tiles = page.locator('[data-testid^="compare-tile-"]');
		await expect(tiles).toHaveCount(1);
	});
});
