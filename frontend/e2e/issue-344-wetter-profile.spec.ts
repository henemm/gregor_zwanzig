// TDD RED: Issue #344 — Wetter-Profile-Karte auf /account
//
// Spec: docs/specs/modules/issue_344_wetter_profile_account.md
//
// Diese Tests MÜSSEN in der RED-Phase scheitern, weil folgende Elemente noch
// nicht existieren (Karte „Wetter-Profile" auf /account):
//   - data-testid="wetter-profile-card"
//   - data-testid="wetter-profile-row-{id}"
//   - data-testid="wetter-profile-name-{id}"
//   - data-testid="wetter-profile-count-{id}"
//   - data-testid="wetter-profile-default-{id}"   (nur bei is_default)
//   - data-testid="wetter-profile-edit-{id}"       (Bleistift)
//   - data-testid="wetter-profile-rename-input-{id}"
//   - data-testid="wetter-profile-delete-{id}"     (Papierkorb)
//   - data-testid="wetter-profile-empty"           (Leerer Zustand)
//
// Ausführung NICHT lokal gegen Prod (8090) — der lokale SvelteKit-/api-Proxy
// zeigt per Default auf die Produktions-API. Die echte E2E-Verifikation läuft
// post-push via /e2e-verify gegen die Remote-Staging-Umgebung
// (staging.gregor20.henemm.com), wo der E2E-Admin existiert.

import { test, expect } from '@playwright/test';
import type { APIRequestContext } from '@playwright/test';

const PREFIX = 'E2E-344';

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
	isDefault = false,
): Promise<string> {
	const resp = await request.post('/api/metric-presets', {
		data: { name, metrics, friendly_ids: [], is_default: isDefault },
	});
	const body = (await resp.json()) as { id: string };
	return body.id;
}

test.describe('Issue #344: Wetter-Profile-Karte auf /account', () => {
	test.beforeEach(async ({ request }) => {
		await clearTestPresets(request);
	});

	test.afterAll(async ({ request }) => {
		await clearTestPresets(request);
	});

	test('AC-1: beide Presets erscheinen mit Name + Metrik-Anzahl', async ({ page, request }) => {
		const idA = await seedPreset(request, `${PREFIX} Alpha`, ['temperature', 'wind', 'precipitation']);
		const idB = await seedPreset(request, `${PREFIX} Beta`, ['temperature']);

		await page.goto('/account');
		const card = page.locator('[data-testid="wetter-profile-card"]');
		await expect(card).toBeVisible();

		await expect(page.locator(`[data-testid="wetter-profile-name-${idA}"]`)).toHaveText(`${PREFIX} Alpha`);
		await expect(page.locator(`[data-testid="wetter-profile-count-${idA}"]`)).toContainText('3 Metriken');
		await expect(page.locator(`[data-testid="wetter-profile-name-${idB}"]`)).toHaveText(`${PREFIX} Beta`);
		await expect(page.locator(`[data-testid="wetter-profile-count-${idB}"]`)).toContainText('1 Metriken');
	});

	test('AC-2: Default-Markierung nur am Default-Preset', async ({ page, request }) => {
		const idDefault = await seedPreset(request, `${PREFIX} Standard`, ['temperature'], true);
		const idNormal = await seedPreset(request, `${PREFIX} Normal`, ['wind']);

		await page.goto('/account');
		await expect(page.locator(`[data-testid="wetter-profile-default-${idDefault}"]`)).toBeVisible();
		await expect(page.locator(`[data-testid="wetter-profile-default-${idNormal}"]`)).toHaveCount(0);
	});

	test('AC-3: Inline-Umbenennen via Enter speichert und aktualisiert die Liste', async ({ page, request }) => {
		const id = await seedPreset(request, `${PREFIX} AltName`, ['temperature']);

		await page.goto('/account');
		await page.click(`[data-testid="wetter-profile-edit-${id}"]`);

		const input = page.locator(`[data-testid="wetter-profile-rename-input-${id}"]`);
		await expect(input).toBeVisible();
		await input.fill(`${PREFIX} NeuerName`);
		await input.press('Enter');

		await expect(page.locator(`[data-testid="wetter-profile-name-${id}"]`)).toHaveText(`${PREFIX} NeuerName`);

		// Persistiert: API liefert den neuen Namen
		const resp = await request.get('/api/metric-presets');
		const presets = (await resp.json()) as Array<{ id: string; name: string }>;
		expect(presets.find((p) => p.id === id)?.name).toBe(`${PREFIX} NeuerName`);
	});

	test('AC-4: Escape verwirft die Bearbeitung, kein PATCH', async ({ page, request }) => {
		const id = await seedPreset(request, `${PREFIX} Unveraendert`, ['temperature']);

		await page.goto('/account');
		await page.click(`[data-testid="wetter-profile-edit-${id}"]`);
		const input = page.locator(`[data-testid="wetter-profile-rename-input-${id}"]`);
		await input.fill(`${PREFIX} SollNichtSpeichern`);
		await input.press('Escape');

		await expect(page.locator(`[data-testid="wetter-profile-name-${id}"]`)).toHaveText(`${PREFIX} Unveraendert`);

		const resp = await request.get('/api/metric-presets');
		const presets = (await resp.json()) as Array<{ id: string; name: string }>;
		expect(presets.find((p) => p.id === id)?.name).toBe(`${PREFIX} Unveraendert`);
	});

	test('AC-5: Löschen mit Bestätigung entfernt das Preset', async ({ page, request }) => {
		const id = await seedPreset(request, `${PREFIX} ZuLoeschen`, ['temperature']);

		await page.goto('/account');
		await expect(page.locator(`[data-testid="wetter-profile-row-${id}"]`)).toBeVisible();

		page.once('dialog', (d) => d.accept());
		await page.click(`[data-testid="wetter-profile-delete-${id}"]`);

		await expect(page.locator(`[data-testid="wetter-profile-row-${id}"]`)).toHaveCount(0);

		const resp = await request.get('/api/metric-presets');
		const presets = (await resp.json()) as Array<{ id: string }>;
		expect(presets.some((p) => p.id === id)).toBe(false);
	});

	test('AC-5b: Abbruch der Bestätigung behält das Preset', async ({ page, request }) => {
		const id = await seedPreset(request, `${PREFIX} Bleibt`, ['temperature']);

		await page.goto('/account');
		page.once('dialog', (d) => d.dismiss());
		await page.click(`[data-testid="wetter-profile-delete-${id}"]`);

		await expect(page.locator(`[data-testid="wetter-profile-row-${id}"]`)).toBeVisible();
	});

	test('AC-7: read-only Karte „Wetter-Templates" bleibt sichtbar', async ({ page, request }) => {
		await seedPreset(request, `${PREFIX} Irgendwas`, ['temperature']);

		await page.goto('/account');
		await expect(page.locator('[data-testid="wetter-profile-card"]')).toBeVisible();
		await expect(page.getByText('Wetter-Templates', { exact: false })).toBeVisible();
	});
});

test.describe('Issue #344: Wetter-Profile — leerer Zustand (AC-6)', () => {
	// Snapshot ALLER Presets des Test-Users, damit wir den leeren Zustand sicher
	// herstellen und danach exakt wiederherstellen koennen (Test-Account auf Staging).
	let snapshot: Array<{
		name: string;
		description?: string;
		is_default: boolean;
		metrics: unknown[];
	}> = [];

	test.beforeAll(async ({ request }) => {
		const resp = await request.get('/api/metric-presets');
		const all = resp.ok() ? ((await resp.json()) as typeof snapshot) : [];
		snapshot = all.map((p) => ({
			name: p.name,
			description: (p as { description?: string }).description,
			is_default: p.is_default,
			metrics: p.metrics ?? [],
		}));
		// Alle loeschen → leerer Zustand
		const list = (await (await request.get('/api/metric-presets')).json()) as Array<{ id: string }>;
		for (const p of list) {
			await request.delete(`/api/metric-presets/${p.id}`).catch(() => {});
		}
	});

	test.afterAll(async ({ request }) => {
		// Wiederherstellen (neue IDs, aber Name/Beschreibung/Default/Metriken identisch).
		// Erst sicherheitshalber erneut leeren (falls der Test Presets angelegt hat).
		const list = (await (await request.get('/api/metric-presets')).json()) as Array<{ id: string }>;
		for (const p of list) {
			await request.delete(`/api/metric-presets/${p.id}`).catch(() => {});
		}
		for (const p of snapshot) {
			await request
				.post('/api/metric-presets', {
					data: {
						name: p.name,
						description: p.description,
						is_default: p.is_default,
						metrics: p.metrics,
					},
				})
				.catch(() => {});
		}
	});

	test('AC-6: leerer Zustand zeigt Hinweistext', async ({ page }) => {
		await page.goto('/account');
		await expect(page.locator('[data-testid="wetter-profile-card"]')).toBeVisible();
		const empty = page.locator('[data-testid="wetter-profile-empty"]');
		await expect(empty).toBeVisible();
		await expect(empty).toContainText('Du hast noch keine Wetter-Profile angelegt');
	});
});
