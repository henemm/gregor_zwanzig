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

// #2794 Teil 3 (Spec feat_2794_s3a_teil3_wetter.md §4/§5, AC-10, AC-11, AC-42): der Reiter Wetter ist
// der WetterTab. Eigene Profile heißen „eigene Vorlagen"; sie stehen im Vorlagen-Picker unter
// „Eigene" (getrennt von den Systemvorlagen) statt als Pille in einer Preset-Leiste. Der Dialog
// „Als eigene Vorlage speichern" (Knopf `wetter-vorlage-als-eigene`) speichert die Ampel des Abos;
// eine eigene Vorlage wird über den Picker samt Rückfrage übernommen (AC-11). Laut AC-42 meldet der
// Reiter nach dem Speichern den Erfolg, die Vorlage wird dabei nicht automatisch übernommen.
const reiter = (page: Page) => page.locator('[data-testid="wetter-tab"]:visible');

async function openWeatherTab(page: Page, tripId: string) {
	await page.goto(`/trips/${tripId}?tab=wetter`);
	await expect(reiter(page)).toBeVisible({ timeout: 15_000 });
	await expect(reiter(page).getByTestId('wetter-tab-laden')).toHaveCount(0, { timeout: 15_000 });
}

/** Metrik-Zeilen (ohne die „−"-Knöpfe) — die Auswahl, wie der Reiter sie zeigt. */
async function zeilenIds(page: Page): Promise<string[]> {
	const ids = await reiter(page)
		.locator('[data-testid^="wetter-zeile-"]:not([data-testid^="wetter-zeile-entfernen-"])')
		.evaluateAll((els) => els.map((e) => (e.getAttribute('data-testid') ?? '').replace('wetter-zeile-', '')));
	return ids.sort();
}

async function pickerOeffnen(page: Page) {
	await reiter(page).getByTestId('wetter-vorlage-picker').click();
	await expect(reiter(page).getByTestId('wetter-vorlage-eigene')).toBeVisible();
}

/** Eine Metrik aus dem Briefing nehmen (AC-19) — der Stand weicht danach von der Vorlage ab. */
async function makeDirty(page: Page) {
	await reiter(page).locator('[data-testid^="wetter-zeile-entfernen-"]').first().click();
	await expect(reiter(page).getByTestId('wetter-vorlage-status')).toHaveText(/^\d+ Abweichung/);
}

// Speichern-Dialog öffnen („Als eigene Vorlage speichern").
async function openSaveDialog(page: Page) {
	await reiter(page).getByTestId('wetter-vorlage-als-eigene').click();
	await expect(page.locator('[data-testid="save-preset-dialog"]')).toBeVisible();
}

type Preset = { id: string; name: string; kind?: string; ampel?: { metrics?: Record<string, { enabled?: boolean }> } };

async function speichereVorlage(page: Page, request: APIRequestContext, name: string): Promise<Preset> {
	await page.fill('[data-testid="save-preset-name"]', name);
	await page.click('[data-testid="save-preset-submit"]');
	await expect(page.locator('[data-testid="save-preset-dialog"]')).not.toBeVisible({ timeout: 5_000 });
	const presets = (await (await request.get('/api/metric-presets')).json()) as Preset[];
	const created = presets.find((p) => p.name === name);
	expect(created, 'neues Profil muss persistiert sein').toBeTruthy();
	return created!;
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

	// AC-1: nach dem Speichern steht das neue Profil sofort (ohne Neuladen) zur Wahl und trägt
	// genau die aktuelle Auswahl des Abos (#2794 Teil 3, AC-42: Erfolgsmeldung + „Eigene").
	test('AC-1: gespeichertes Profil steht unmittelbar unter „Eigene" und trägt die aktuelle Auswahl', async ({ page, request }) => {
		const name = `${PREFIX} Aktiv ${Date.now()}`;

		await openWeatherTab(page, TRIP_A);
		await makeDirty(page);
		await openSaveDialog(page);
		const created = await speichereVorlage(page, request, name);

		await expect(reiter(page).getByTestId('wetter-vorlage-gespeichert')).toContainText(name);
		await pickerOeffnen(page);
		await expect(reiter(page).getByTestId('wetter-vorlage-eigene').getByTestId(`wetter-vorlage-eigene-${created.id}`)).toBeVisible();
		expect(created.kind, 'AC-42: die Vorlage trägt die Art des Kontexts').toBe('route');
		const aktivInVorlage = Object.entries(created.ampel?.metrics ?? {})
			.filter(([, e]) => e?.enabled === true)
			.map(([m]) => m)
			.sort();
		expect(aktivInVorlage, 'die Vorlage trägt genau die aktuelle Auswahl des Abos').toEqual(await zeilenIds(page));
	});

	// AC-2: eigenes Profil trägt die Kennzeichnung „Eigene", System-Vorlagen nicht.
	test('AC-2: eigenes Profil steht unter „Eigene", System-Vorlage nicht', async ({ page, request }) => {
		const name = `${PREFIX} Markiert ${Date.now()}`;

		await openWeatherTab(page, TRIP_A);
		await makeDirty(page);
		await openSaveDialog(page);
		const { id } = await speichereVorlage(page, request, name);

		await pickerOeffnen(page);
		const eigene = reiter(page).getByTestId('wetter-vorlage-eigene');
		await expect(eigene.getByTestId(`wetter-vorlage-eigene-${id}`)).toBeVisible();
		const system = reiter(page).locator('[data-testid^="wetter-vorlage-option-"]');
		await expect(system.first(), 'Systemvorlagen fehlen im Picker').toBeVisible();
		await expect(eigene.locator('[data-testid^="wetter-vorlage-option-"]'), 'eine Systemvorlage steht unter „Eigene"').toHaveCount(0);
		await expect(system.filter({ hasText: name }), 'die eigene Vorlage steht bei den Systemvorlagen').toHaveCount(0);
	});

	// AC-3: Profil erscheint auch im Picker eines anderen Trips desselben Nutzers und lässt sich
	// dort übernehmen — Trip B zeigt danach genau die Auswahl der Vorlage, auch nach Neuladen.
	test('AC-3: eigenes Profil erscheint im Picker eines anderen Trips und lässt sich dort übernehmen', async ({ page, request }) => {
		const name = `${PREFIX} Uebergreifend ${Date.now()}`;

		await openWeatherTab(page, TRIP_A);
		await makeDirty(page);
		await openSaveDialog(page);
		const { id } = await speichereVorlage(page, request, name);
		const auswahlA = await zeilenIds(page);

		await openWeatherTab(page, TRIP_B);
		await pickerOeffnen(page);
		const eintrag = reiter(page).getByTestId('wetter-vorlage-eigene').getByTestId(`wetter-vorlage-eigene-${id}`);
		await expect(eintrag).toBeVisible();
		await eintrag.click();
		await expect(reiter(page).getByTestId('wetter-vorlage-wechsel-dialog')).toBeVisible();
		const speichern = page.waitForResponse(
			(r) => r.request().method() === 'PUT' && new URL(r.url()).pathname === `/api/trips/${TRIP_B}/weather-config`
		);
		await reiter(page).getByTestId('wetter-vorlage-wechsel-uebernehmen').click();
		expect((await speichern).ok()).toBeTruthy();
		expect(await zeilenIds(page), 'Trip B zeigt die Auswahl der eigenen Vorlage').toEqual(auswahlA);
		await openWeatherTab(page, TRIP_B);
		expect(await zeilenIds(page), 'nach Neuladen bleibt die übernommene Vorlage stehen').toEqual(auswahlA);
	});

	// AC-4: zweites Profil mit gleichem Namen (andere Schreibweise/Leerzeichen) → Fehler, kein Duplikat.
	test('AC-4: Dublettenname wird im Dialog abgelehnt, kein zweites Profil', async ({ page, request }) => {
		const base = `${PREFIX} Bergtour ${Date.now()}`;

		// 1. Erstes Profil anlegen.
		await openWeatherTab(page, TRIP_A);
		await makeDirty(page);
		await openSaveDialog(page);
		await speichereVorlage(page, request, base);

		const before = (await (await request.get('/api/metric-presets')).json()) as Preset[];
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
		const after = (await (await request.get('/api/metric-presets')).json()) as Preset[];
		const countAfter = after.filter((p) => p.name.trim().toLowerCase() === base.trim().toLowerCase()).length;
		expect(countAfter, 'kein Duplikat angelegt').toBe(1);
	});
});
