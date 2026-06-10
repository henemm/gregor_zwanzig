// TDD RED: Issue #690 — Eigene Wetter-Metriken-Profile: aktivieren, kennzeichnen, eindeutig benennen
//
// Spec: docs/specs/modules/issue_690_custom_metric_presets.md
//
// Diese E2E laufen als Verhaltensnachweis in der Acceptance-Stage (/e2e-verify)
// gegen die Remote-Staging-Umgebung (staging.gregor20.henemm.com), wo der
// E2E-Admin existiert. Lokal zeigt der SvelteKit-/api-Proxy per Default auf
// die Produktions-API — daher NICHT lokal gegen Prod fahren.
//
// RED: Diese Tests MÜSSEN aktuell scheitern, weil folgende Versprechen fehlen:
//   - AC-1: nach „Preset speichern" wird das neue Profil NICHT auto-aktiviert
//           (WeatherMetricsTab.onPresetSaved prependet nur, ruft applyPreset nicht)
//           → erwartete data-testid="weather-preset-pill-{id}" mit aria-pressed/active fehlt
//   - AC-2: eigene Profile tragen KEINE „Eigene"-Pille
//           → erwartete data-testid="weather-preset-own-badge-{id}" fehlt
//   - AC-4: Dialog prüft Namen NICHT auf Eindeutigkeit (kein name_exists-Fehler)
//
// Erwarteter Selektor-Vertrag (von der Implementierung zu erfüllen):
//   - data-testid="weather-preset-pill-{id}"        Pille je Profil/Vorlage
//   - aria-pressed="true" / class active             aktive Pille
//   - data-testid="weather-preset-own-badge-{id}"   „Eigene"-Markierung (nur userPresets)

import { test, expect } from '@playwright/test';
import type { APIRequestContext, Page } from '@playwright/test';

const PREFIX = 'E2E690';
const TRIP_A = 'e2e-690-trip-a';
const TRIP_B = 'e2e-690-trip-b';

async function createTrip(request: APIRequestContext, id: string, name: string) {
	await request.post('/api/trips', {
		data: {
			id,
			name,
			stages: [
				{
					id: `${id}-s1`,
					name: 'Tag 1',
					date: '2026-06-10',
					waypoints: [
						{ id: `${id}-w1`, name: 'Start', lat: 46.5, lon: 8.1, elevation_m: 1800 },
						{ id: `${id}-w2`, name: 'Gipfel', lat: 46.6, lon: 8.2, elevation_m: 2400 },
					],
				},
			],
		},
	});
}

async function deleteTrip(request: APIRequestContext, id: string) {
	await request.delete(`/api/trips/${id}`).catch(() => {});
}

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

async function openWeatherTab(page: Page, tripId: string) {
	await page.goto(`/trips/${tripId}?tab=weather`);
	await page.waitForSelector('[data-testid="weather-metrics-tab"]', { timeout: 15_000 });
}

// Eine Metrik umschalten → Tab wird „dirty" → der Speichern-Link erscheint.
async function makeDirty(page: Page) {
	const firstCheckbox = page.locator('[data-testid^="weather-metrics-tab-checkbox-"]').first();
	await firstCheckbox.click();
	await expect(page.locator('[data-testid="weather-metrics-dirty-pill"]')).toBeVisible();
}

// Speichern-Dialog öffnen (Link „als eigenes Profil speichern" im Dirty-Hinweis).
async function openSaveDialog(page: Page) {
	await page.getByRole('button', { name: 'als eigenes Profil speichern' }).click();
	await expect(page.locator('[data-testid="save-preset-dialog"]')).toBeVisible();
}

test.describe('Issue #690: Eigene Metrik-Profile — aktivieren, kennzeichnen, eindeutig', () => {
	test.beforeAll(async ({ request }) => {
		await deleteTrip(request, TRIP_A);
		await deleteTrip(request, TRIP_B);
		await clearTestPresets(request);
		await createTrip(request, TRIP_A, 'E2E #690 Trip A');
		await createTrip(request, TRIP_B, 'E2E #690 Trip B');
	});

	test.afterAll(async ({ request }) => {
		await deleteTrip(request, TRIP_A);
		await deleteTrip(request, TRIP_B);
		await clearTestPresets(request);
	});

	test.beforeEach(async ({ request }) => {
		await clearTestPresets(request);
	});

	// AC-1: nach dem Speichern ist das neue Profil sofort aktiv (ohne manuellen Klick).
	test('AC-1: gespeichertes Profil ist unmittelbar das aktive Profil', async ({ page, request }) => {
		const name = `${PREFIX} Aktiv ${Date.now()}`;

		await openWeatherTab(page, TRIP_A);
		await makeDirty(page);
		await openSaveDialog(page);

		await page.fill('[data-testid="save-preset-name"]', name);
		await page.click('[data-testid="save-preset-submit"]');

		// Dialog schließt.
		await expect(page.locator('[data-testid="save-preset-dialog"]')).not.toBeVisible({ timeout: 5_000 });

		// Die ID des neu erstellten Profils via API ermitteln.
		const presets = (await (await request.get('/api/metric-presets')).json()) as Array<{
			id: string;
			name: string;
		}>;
		const created = presets.find((p) => p.name === name);
		expect(created, 'neues Profil muss persistiert sein').toBeTruthy();
		const id = created!.id;

		// Die Pille des neuen Profils ist als aktiv markiert — OHNE manuellen Klick.
		const pill = page.locator(`[data-testid="weather-preset-pill-${id}"]`);
		await expect(pill).toBeVisible();
		await expect(pill).toHaveClass(/active/);
	});

	// AC-2: eigenes Profil trägt „Eigene"-Markierung, System-Vorlage nicht.
	test('AC-2: eigenes Profil hat „Eigene"-Pille, System-Vorlage nicht', async ({ page, request }) => {
		const name = `${PREFIX} Markiert ${Date.now()}`;

		await openWeatherTab(page, TRIP_A);
		await makeDirty(page);
		await openSaveDialog(page);
		await page.fill('[data-testid="save-preset-name"]', name);
		await page.click('[data-testid="save-preset-submit"]');
		await expect(page.locator('[data-testid="save-preset-dialog"]')).not.toBeVisible({ timeout: 5_000 });

		const presets = (await (await request.get('/api/metric-presets')).json()) as Array<{
			id: string;
			name: string;
		}>;
		const id = presets.find((p) => p.name === name)!.id;

		// Eigenes Profil: „Eigene"-Markierung sichtbar.
		await expect(page.locator(`[data-testid="weather-preset-own-badge-${id}"]`)).toBeVisible();

		// Mindestens eine System-Vorlage-Pille existiert und trägt KEINE „Eigene"-Markierung.
		const ownBadges = page.locator('[data-testid^="weather-preset-own-badge-"]');
		const pills = page.locator('[data-testid^="weather-preset-pill-"]');
		await expect(pills.first()).toBeVisible();
		// Es gibt mehr Pillen (inkl. System-Vorlagen) als „Eigene"-Badges.
		expect(await pills.count()).toBeGreaterThan(await ownBadges.count());
	});

	// AC-3 (optional): Profil erscheint auch in der Leiste eines anderen Trips desselben Nutzers.
	test('AC-3: eigenes Profil erscheint in der Leiste eines anderen Trips', async ({ page, request }) => {
		const name = `${PREFIX} Uebergreifend ${Date.now()}`;

		// Profil auf Trip A anlegen.
		await openWeatherTab(page, TRIP_A);
		await makeDirty(page);
		await openSaveDialog(page);
		await page.fill('[data-testid="save-preset-name"]', name);
		await page.click('[data-testid="save-preset-submit"]');
		await expect(page.locator('[data-testid="save-preset-dialog"]')).not.toBeVisible({ timeout: 5_000 });

		const presets = (await (await request.get('/api/metric-presets')).json()) as Array<{
			id: string;
			name: string;
		}>;
		const id = presets.find((p) => p.name === name)!.id;

		// Trip B öffnen → Profil erscheint dort als auswählbare „Eigene"-Pille.
		await openWeatherTab(page, TRIP_B);
		const pill = page.locator(`[data-testid="weather-preset-pill-${id}"]`);
		await expect(pill).toBeVisible();
		await expect(page.locator(`[data-testid="weather-preset-own-badge-${id}"]`)).toBeVisible();

		// Klick wendet es auf Trip B an → Pille wird aktiv.
		await pill.click();
		await expect(pill).toHaveClass(/active/);
	});

	// AC-4: zweites Profil mit gleichem Namen (andere Schreibweise/Leerzeichen) → Fehler, kein Duplikat.
	test('AC-4: Dublettenname wird im Dialog abgelehnt, kein zweites Profil', async ({ page, request }) => {
		const base = `${PREFIX} Bergtour ${Date.now()}`;

		// 1. Erstes Profil anlegen.
		await openWeatherTab(page, TRIP_A);
		await makeDirty(page);
		await openSaveDialog(page);
		await page.fill('[data-testid="save-preset-name"]', base);
		await page.click('[data-testid="save-preset-submit"]');
		await expect(page.locator('[data-testid="save-preset-dialog"]')).not.toBeVisible({ timeout: 5_000 });

		const before = (await (await request.get('/api/metric-presets')).json()) as Array<{
			id: string;
			name: string;
		}>;
		const countBefore = before.filter((p) => p.name.trim().toLowerCase() === base.trim().toLowerCase()).length;
		expect(countBefore).toBe(1);

		// 2. Dublette mit abweichender Schreibweise + umgebenden Leerzeichen.
		await makeDirty(page);
		await openSaveDialog(page);
		await page.fill('[data-testid="save-preset-name"]', `  ${base.toUpperCase()} `);
		await page.click('[data-testid="save-preset-submit"]');

		// Fehlermeldung erscheint, Dialog bleibt offen.
		await expect(page.locator('[data-testid="save-preset-error"]')).toBeVisible();
		await expect(page.locator('[data-testid="save-preset-dialog"]')).toBeVisible();

		// Kein zweites Profil mit diesem Namen.
		const after = (await (await request.get('/api/metric-presets')).json()) as Array<{
			id: string;
			name: string;
		}>;
		const countAfter = after.filter((p) => p.name.trim().toLowerCase() === base.trim().toLowerCase()).length;
		expect(countAfter, 'kein Duplikat angelegt').toBe(1);
	});
});
