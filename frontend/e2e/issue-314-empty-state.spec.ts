// TDD RED: Issue #314 — EmptyState-Komponente + Migration aller Inline-Leerzustände
//
// Spec: docs/specs/modules/issue_314_ui_state_patterns.md
//
// Diese Tests MÜSSEN in der RED-Phase scheitern, weil:
//   1. EmptyState.svelte existiert noch nicht (kein data-slot="empty-state" in aktuellem Code)
//   2. compare/+page.svelte zeigt keinen Leerzustand bei 0 Locations
//   3. account/+page.svelte nutzt window.confirm() statt Dialog.Root
//
// Die existierenden inline-Blöcke haben data-testid="empty-state" aber KEIN
// data-slot="empty-state" — nach Migration setzt EmptyState.svelte BEIDE Attribute.

import { test, expect } from '@playwright/test';
import type { APIRequestContext } from '@playwright/test';
import { login } from './helpers.js';

const PREFIX = 'E2E-314';

async function clearTestPresets(request: APIRequestContext) {
	const resp = await request.get('/api/metric-presets');
	if (!resp.ok()) return;
	const presets = (await resp.json()) as Array<{ id: string; name: string }>;
	for (const p of presets) {
		if (p.name.startsWith(PREFIX)) {
			await request.delete(`/api/metric-presets/${p.id}`).catch(() => {});
		}
	}
}

async function seedPreset(
	request: APIRequestContext,
	name: string,
	metrics: string[],
): Promise<string> {
	const resp = await request.post('/api/metric-presets', {
		data: { name, metrics, friendly_ids: [], is_default: false },
	});
	const body = (await resp.json()) as { id: string };
	return body.id;
}

// ---------------------------------------------------------------------------
// AC-1 / AC-2: EmptyState-Komponente setzt data-slot="empty-state"
// ---------------------------------------------------------------------------

test.describe('Issue #314: EmptyState — data-slot-Attribut auf Trips-Seite', () => {
	test.beforeEach(async ({ page }) => {
		await login(page);
	});

	test('AC-2a: Trips-EmptyState hat data-slot="empty-state"', async ({ page }) => {
		await page.goto('/trips');

		// Falls kein EmptyState sichtbar ist (es gibt Trips), Test überspringen.
		const emptyState = page.locator('[data-testid="empty-state"]');
		const hasEmptyState = await emptyState.isVisible({ timeout: 3000 }).catch(() => false);
		if (!hasEmptyState) {
			test.skip();
			return;
		}

		// RED: data-slot="empty-state" existiert nicht im aktuellen Inline-Block.
		// GREEN: EmptyState.svelte setzt data-slot="empty-state" immer.
		await expect(page.locator('[data-slot="empty-state"]')).toBeVisible();
	});

	test('AC-2b: Locations-EmptyState hat data-slot="empty-state"', async ({ page }) => {
		await page.goto('/locations');

		const emptyState = page.locator('[data-testid="empty-state"]');
		const hasEmptyState = await emptyState.isVisible({ timeout: 3000 }).catch(() => false);
		if (!hasEmptyState) {
			test.skip();
			return;
		}

		// RED: data-slot="empty-state" existiert nicht im aktuellen Inline-Block.
		await expect(page.locator('[data-slot="empty-state"]')).toBeVisible();
	});

	test('AC-2c: Subscriptions-EmptyState hat data-slot="empty-state"', async ({ page }) => {
		await page.goto('/subscriptions');

		const emptyState = page.locator('[data-testid="empty-state"]');
		const hasEmptyState = await emptyState.isVisible({ timeout: 3000 }).catch(() => false);
		if (!hasEmptyState) {
			test.skip();
			return;
		}

		// RED: data-slot="empty-state" existiert nicht im aktuellen Inline-Block.
		await expect(page.locator('[data-slot="empty-state"]')).toBeVisible();
	});
});

// ---------------------------------------------------------------------------
// AC-2 + AC-4: Compare-Seite zeigt Leerzustand wenn 0 Locations
// ---------------------------------------------------------------------------

test.describe('Issue #314: EmptyState — Compare-Seite', () => {
	test.beforeEach(async ({ page }) => {
		await login(page);
	});

	test('AC-2d: Compare-Seite zeigt data-slot="empty-state" wenn keine Locations', async ({
		page,
		request,
	}) => {
		// Prüfen ob Locations vorhanden sind; wenn ja, Test überspringen.
		const resp = await request.get('/api/locations');
		const locations = (await resp.json()) as Array<unknown>;
		if (locations.length > 0) {
			test.skip();
			return;
		}

		await page.goto('/compare');

		// RED: Compare zeigt aktuell AutoReportsOverview, keinen Leerzustand.
		// GREEN: EmptyState.svelte wird gerendert wenn locations.length === 0.
		await expect(page.locator('[data-slot="empty-state"]')).toBeVisible({ timeout: 5000 });
		await expect(page.locator('[data-testid="empty-state"]')).toBeVisible();
	});
});

// ---------------------------------------------------------------------------
// AC-3: EmptyKachel (Home) nutzt EmptyState (data-slot-Attribut)
// ---------------------------------------------------------------------------

test.describe('Issue #314: EmptyState — Home-Seite (EmptyKachel)', () => {
	test.beforeEach(async ({ page }) => {
		await login(page);
	});

	test('AC-3: Home-EmptyKachel hat data-slot="empty-state"', async ({ page, request }) => {
		// Prüfen ob Trips vorhanden sind; wenn ja, Test überspringen.
		const resp = await request.get('/api/trips');
		const trips = (await resp.json()) as Array<unknown>;
		if (trips.length > 0) {
			test.skip();
			return;
		}

		await page.goto('/');

		// RED: EmptyKachel.svelte hat eigenes Custom-Markup, kein data-slot="empty-state".
		// GREEN: EmptyKachel nutzt <EmptyState>, das data-slot setzt.
		await expect(page.locator('[data-slot="empty-state"]')).toBeVisible({ timeout: 5000 });
	});
});

// ---------------------------------------------------------------------------
// AC-5: Account — deletePreset öffnet Dialog.Root (kein window.confirm)
// ---------------------------------------------------------------------------

test.describe('Issue #314: EmptyState — Account deletePreset via Dialog.Root', () => {
	test.beforeEach(async ({ request }) => {
		await clearTestPresets(request);
	});

	test.afterAll(async ({ request }) => {
		await clearTestPresets(request);
	});

	test('AC-5: Löschen-Button öffnet Dialog.Root statt window.confirm', async ({
		page,
		request,
	}) => {
		const id = await seedPreset(request, `${PREFIX} Dialog-Test`, ['temperature']);

		await page.goto('/account');
		await expect(page.locator(`[data-testid="wetter-profile-row-${id}"]`)).toBeVisible();

		// Sicherstellen: kein window.confirm-Dialog feuert (würde Test blockieren).
		// Falls doch einer feuert, sofort abweisen — der Test schlägt dann trotzdem fehl
		// weil der Dialog.Root nicht erscheint.
		let nativeDialogFired = false;
		page.on('dialog', async (d) => {
			nativeDialogFired = true;
			await d.dismiss();
		});

		await page.click(`[data-testid="wetter-profile-delete-${id}"]`);

		// RED: window.confirm feuert → role="dialog" erscheint nie.
		// GREEN: Dialog.Root öffnet sich mit Bestätigung.
		await expect(page.locator('[role="dialog"]')).toBeVisible({ timeout: 3000 });
		expect(nativeDialogFired).toBe(false);
	});

	test('AC-5b: Dialog-Abbrechen behält Preset', async ({ page, request }) => {
		const id = await seedPreset(request, `${PREFIX} Bleibt-Dialog`, ['temperature']);

		await page.goto('/account');
		await expect(page.locator(`[data-testid="wetter-profile-row-${id}"]`)).toBeVisible();

		page.on('dialog', async (d) => d.dismiss());

		await page.click(`[data-testid="wetter-profile-delete-${id}"]`);

		// RED: kein Dialog.Root, window.confirm feuert stattdessen und dismiss() lässt nichts erscheinen.
		// GREEN: Dialog.Root öffnet sich, Abbrechen-Button schließt ihn.
		const dialog = page.locator('[role="dialog"]');
		await expect(dialog).toBeVisible({ timeout: 3000 });
		await page.getByRole('button', { name: 'Abbrechen' }).click();
		await expect(dialog).not.toBeVisible();

		// Preset muss noch vorhanden sein.
		await expect(page.locator(`[data-testid="wetter-profile-row-${id}"]`)).toBeVisible();
	});
});

// ---------------------------------------------------------------------------
// AC-6: Account — deleteAccount öffnet Dialog.Root (kein window.confirm)
// ---------------------------------------------------------------------------

test.describe('Issue #314: EmptyState — Account deleteAccount via Dialog.Root', () => {
	test.beforeEach(async ({ page }) => {
		await login(page);
	});

	test('AC-6: Account-Löschen-Button öffnet Dialog.Root statt window.confirm', async ({
		page,
	}) => {
		await page.goto('/account');

		// Zur Danger Zone scrollen (am Seitenende).
		const dangerBtn = page.getByRole('button', { name: /Account löschen|Konto löschen/i });
		const hasDangerBtn = await dangerBtn.isVisible({ timeout: 3000 }).catch(() => false);
		if (!hasDangerBtn) {
			test.skip();
			return;
		}

		let nativeDialogFired = false;
		page.on('dialog', async (d) => {
			nativeDialogFired = true;
			await d.dismiss();
		});

		await dangerBtn.click();

		// RED: window.confirm feuert → role="dialog" erscheint nie.
		// GREEN: Dialog.Root öffnet sich mit Bestätigung.
		await expect(page.locator('[role="dialog"]')).toBeVisible({ timeout: 3000 });
		expect(nativeDialogFired).toBe(false);

		// Dialog abbrechen (nicht wirklich löschen).
		await page.getByRole('button', { name: 'Abbrechen' }).click();
		await expect(page.locator('[role="dialog"]')).not.toBeVisible();
	});
});
