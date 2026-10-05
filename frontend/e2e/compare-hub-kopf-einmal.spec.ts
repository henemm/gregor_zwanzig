// TDD RED — Issue #2284 Scheibe S1: Vergleich-Hub-Kopf auf den geteilten
// Baustein `SubscriptionHeader` umgestellt — EIN Kopf-Markup für Desktop und Mobil.
//
// Spec: docs/specs/modules/feat_2284_s1_subscription_header.md
//   AC-2, AC-3, AC-5, AC-8, AC-9, AC-10
//
// RED HEUTE (ehrlich): AC-8 — `+page.svelte` baut den Kopf zweimal (Desktop-
// und Mobil-Block, einer per CSS ausgeblendet), jede Kopf-testid zählt 2.
// Gezählt wird bewusst OHNE `:visible`, sonst bliebe die Zweitinstanz unsichtbar.
//
// REGRESSIONSWÄCHTER (heute grün by design, die Scheibe ist ein Umbau ohne
// Verhaltensänderung): AC-2 (Mobil-Ablauf + Reload), AC-3 (exakte Schlüssel-
// menge des PUT-Rumpfs je Feld, übrige Felder unverändert — Fehlerklasse
// #2375/#2381), AC-5 (Profil-Fehler), AC-9 (Eyebrow/Breadcrumb/Unterzeile),
// AC-10 (maxlength 60, Unterzeile während der Bearbeitung weg). Sie müssen
// nach der Umstellung grün BLEIBEN.
//
// Arbeitet nur gegen Wegwerf-Presets (Seed + Aufräumen), nie gegen PO-Daten.
// AC-1/AC-4 laufen unverändert in compare-hub-name-region-profil.spec.ts (AC-12).
//
// Ausführen (Staging):
//   set -a; source /home/hem/gregor_zwanzig_staging/.env
//   source /home/hem/gregor_zwanzig/.claude/validator.env; set +a
//   cd frontend && npx playwright test --config=e2e/playwright.2284-s1.red.config.ts

import { test, expect, type Page, type Request } from '@playwright/test';

const PRESET_URL_PART = '/api/compare/presets/';
const DESKTOP = { width: 1280, height: 900 };
const MOBIL = { width: 375, height: 812 };

interface SeededPreset {
	presetId: string;
	locIds: string[];
	name: string;
}

async function seedPreset(page: Page): Promise<SeededPreset> {
	const suffix = Date.now();
	const locIds: string[] = [];
	for (const [name, lat, lon] of [
		[`E2E 2284-S1 A ${suffix}`, 47.05, 11.05],
		[`E2E 2284-S1 B ${suffix}`, 46.5, 11.35]
	] as const) {
		const res = await page.request.post('/api/locations', { data: { name, lat, lon } });
		expect(res.ok(), `Location-Anlage fehlgeschlagen: ${res.status()}`).toBeTruthy();
		locIds.push((await res.json()).id as string);
	}
	const name = `E2E 2284-S1 ${suffix}`;
	const presetRes = await page.request.post('/api/compare/presets', {
		data: {
			name,
			location_ids: locIds,
			schedule: 'daily',
			profil: 'wandern',
			hour_from: 7,
			hour_to: 16,
			empfaenger: ['urlauber@example.com'],
			morning_time: '07:00',
			display_config: { region: 'Ötztal' }
		}
	});
	expect(presetRes.ok(), `Preset-Anlage fehlgeschlagen: ${presetRes.status()}`).toBeTruthy();
	return { presetId: (await presetRes.json()).id as string, locIds, name };
}

async function cleanup(page: Page, presetId: string, locIds: string[]) {
	await page.request.delete(`${PRESET_URL_PART}${presetId}`).catch(() => {});
	for (const id of locIds) await page.request.delete(`/api/locations/${id}`).catch(() => {});
}

async function fetchPreset(page: Page, presetId: string): Promise<Record<string, unknown>> {
	const res = await page.request.get(`${PRESET_URL_PART}${presetId}`);
	expect(res.ok(), `GET preset HTTP ${res.status()}`).toBeTruthy();
	return (await res.json()) as Record<string, unknown>;
}

/** Server-Felder, die sich bei jedem Schreiben ändern dürfen. */
function ohneZeitstempel(p: Record<string, unknown>): Record<string, unknown> {
	const { updated_at: _u, created_at: _c, etag: _e, version: _v, ...rest } = p;
	return rest;
}

async function oeffneHub(page: Page, presetId: string) {
	await page.goto(`/compare/${presetId}`);
	await expect(page.getByTestId('compare-detail-tab-list')).toBeVisible({ timeout: 10_000 });
}

/** Mitschnitt aller PUTs auf das Preset (nur Rumpf). */
function putMitschnitt(page: Page, presetId: string): Record<string, unknown>[] {
	const bodies: Record<string, unknown>[] = [];
	page.on('request', (req: Request) => {
		if (req.method() === 'PUT' && req.url().endsWith(`${PRESET_URL_PART}${presetId}`)) {
			bodies.push(JSON.parse(req.postData() ?? '{}') as Record<string, unknown>);
		}
	});
	return bodies;
}

const KOPF_IDS = [
	'compare-hub-name-edit-toggle',
	'compare-hub-region-edit-toggle',
	'compare-hub-profil-option-allgemein',
	'compare-hub-profil-option-wintersport',
	'compare-hub-profil-option-wandern',
	'compare-hub-profil-option-summer_trekking'
];

test.describe('#2284 S1 — Vergleich-Hub-Kopf: ein Markup, unverändertes Verhalten', () => {
	// #2284 S2 v1.2 (AC-15-Ausnahme, Entscheidung 14): die Mobil-Variante dieser
	// Schleife ist unten als eigener Fall `AC-8 (Mobil 375)` umgestellt (Knopf +
	// Auswahl statt sichtbarer Kacheln). Der Desktop-Teil bleibt unverändert.
	for (const [label, viewport] of [
		['Desktop 1280', DESKTOP]
	] as const) {
		test(`AC-8 (${label}): jede Kopf-testid genau einmal im DOM und sichtbar`, async ({ page }) => {
			await page.setViewportSize(viewport);
			const { presetId, locIds } = await seedPreset(page);
			try {
				await oeffneHub(page, presetId);
				for (const id of KOPF_IDS) {
					const loc = page.locator(`[data-testid="${id}"]`);
					await expect(loc.filter({ visible: true }).first()).toBeVisible({ timeout: 10_000 });
					expect(await loc.count(), `${id}: Anzahl im DOM (ohne :visible)`).toBe(1);
					await expect(loc).toBeVisible();
				}
				// Orte-Anzahl: je Viewport eine eigene testid, jede genau einmal im DOM;
				// die frühere gemeinsame testid existiert nicht mehr (keine Zweitinstanz).
				expect(await page.locator('[data-testid="compare-hub-orte-anzahl"]').count(), 'alte gemeinsame testid').toBe(0);
				const orteDesktop = page.locator('[data-testid="compare-hub-orte-anzahl-desktop"]');
				const orteMobil = page.locator('[data-testid="compare-hub-orte-anzahl-mobil"]');
				expect(await orteDesktop.count(), 'compare-hub-orte-anzahl-desktop: Anzahl im DOM').toBe(1);
				expect(await orteMobil.count(), 'compare-hub-orte-anzahl-mobil: Anzahl im DOM').toBe(1);
				if (viewport === DESKTOP) {
					await expect(orteDesktop).toBeVisible();
					await expect(orteMobil).toBeHidden();
				} else {
					await expect(orteMobil).toBeVisible();
					await expect(orteDesktop).toBeHidden();
				}
				// Bearbeiten-Modus: Eingabe und Speichern-Knopf ebenfalls genau einmal.
				await page.locator('[data-testid="compare-hub-name-edit-toggle"]:visible').click();
				for (const id of ['compare-hub-name-edit', 'compare-hub-name-save']) {
					const loc = page.locator(`[data-testid="${id}"]`);
					await expect(loc.filter({ visible: true }).first()).toBeVisible();
					expect(await loc.count(), `${id}: Anzahl im DOM (ohne :visible)`).toBe(1);
				}
			} finally {
				await cleanup(page, presetId, locIds);
			}
		});
	}

	// #2284 S2 v1.2 (AC-15-Ausnahme): auf dem Handy zeigt der Kopf die Aktivität als
	// EINEN Knopf `compare-hub-profil-knopf` mit Auswahl `compare-hub-profil-auswahl`
	// (Spec feat_2284_s2_trip_kopf, Entscheidung 14). Gleiche Strenge wie vorher:
	// jede Kopf-testid genau einmal im DOM (ohne :visible); die Kacheln bleiben im
	// Markup (genau einmal), sind mobil aber unsichtbar; Knopf sichtbar und genau
	// einmal, Auswahl-Container genau einmal (geschlossen versteckt).
	test('AC-8 (Mobil 375): jede Kopf-testid genau einmal im DOM und sichtbar', async ({ page }) => {
		await page.setViewportSize(MOBIL);
		const { presetId, locIds } = await seedPreset(page);
		try {
			await oeffneHub(page, presetId);
			for (const id of KOPF_IDS) {
				const loc = page.locator(`[data-testid="${id}"]`);
				expect(await loc.count(), `${id}: Anzahl im DOM (ohne :visible)`).toBe(1);
				if (id.startsWith('compare-hub-profil-option-')) {
					await expect(loc, `${id}: Kachel ist auf dem Handy sichtbar (Entscheidung 14: Knopf statt Kacheln)`).toBeHidden();
				} else {
					await expect(loc).toBeVisible({ timeout: 10_000 });
				}
			}
			const knopf = page.locator('[data-testid="compare-hub-profil-knopf"]');
			const auswahl = page.locator('[data-testid="compare-hub-profil-auswahl"]');
			await expect(knopf, 'compare-hub-profil-knopf: auf dem Handy nicht sichtbar').toBeVisible({ timeout: 10_000 });
			expect(await knopf.count(), 'compare-hub-profil-knopf: Anzahl im DOM (ohne :visible)').toBe(1);
			expect(await auswahl.count(), 'compare-hub-profil-auswahl: Anzahl im DOM (ohne :visible)').toBe(1);
			await expect(knopf).toHaveAttribute('data-selected-value', 'wandern');
			for (const v of ['allgemein', 'wintersport', 'wandern', 'summer_trekking']) {
				const opt = page.locator(`[data-testid="compare-hub-profil-auswahl-option-${v}"]`);
				expect(await opt.count(), `compare-hub-profil-auswahl-option-${v}: Anzahl im DOM (ohne :visible)`).toBe(1);
			}
			// Orte-Anzahl: je Viewport eine eigene testid, jede genau einmal im DOM;
			// die frühere gemeinsame testid existiert nicht mehr (keine Zweitinstanz).
			expect(await page.locator('[data-testid="compare-hub-orte-anzahl"]').count(), 'alte gemeinsame testid').toBe(0);
			const orteDesktop = page.locator('[data-testid="compare-hub-orte-anzahl-desktop"]');
			const orteMobil = page.locator('[data-testid="compare-hub-orte-anzahl-mobil"]');
			expect(await orteDesktop.count(), 'compare-hub-orte-anzahl-desktop: Anzahl im DOM').toBe(1);
			expect(await orteMobil.count(), 'compare-hub-orte-anzahl-mobil: Anzahl im DOM').toBe(1);
			await expect(orteMobil).toBeVisible();
			await expect(orteDesktop).toBeHidden();
			// Bearbeiten-Modus: Eingabe und Speichern-Knopf ebenfalls genau einmal.
			await page.locator('[data-testid="compare-hub-name-edit-toggle"]:visible').click();
			for (const id of ['compare-hub-name-edit', 'compare-hub-name-save']) {
				const loc = page.locator(`[data-testid="${id}"]`);
				await expect(loc.filter({ visible: true }).first()).toBeVisible();
				expect(await loc.count(), `${id}: Anzahl im DOM (ohne :visible)`).toBe(1);
			}
		} finally {
			await cleanup(page, presetId, locIds);
		}
	});

	test('AC-2 (Mobil 375): Name, Region, Profil ändern → nach Reload persistiert', async ({ page }) => {
		await page.setViewportSize(MOBIL);
		const { presetId, locIds } = await seedPreset(page);
		const neuName = `Mobil ${Date.now()}`;
		const neuRegion = `Zillertal ${Date.now()}`.slice(0, 40);
		try {
			await oeffneHub(page, presetId);
			const sicht = (id: string) => page.locator(`[data-testid="${id}"]:visible`);

			await sicht('compare-hub-name-edit-toggle').click();
			await sicht('compare-hub-name-edit').fill(neuName);
			await sicht('compare-hub-name-save').click();
			await expect(page.getByText(neuName).filter({ visible: true }).first()).toBeVisible({ timeout: 5_000 });

			await sicht('compare-hub-region-edit-toggle').click();
			await sicht('compare-hub-region-edit').fill(neuRegion);
			await sicht('compare-hub-region-save').click();
			await expect(page.getByText(neuRegion).filter({ visible: true }).first()).toBeVisible({ timeout: 5_000 });

			// #2284 S2 v1.2 (AC-15-Ausnahme, Entscheidung 14): mobil Wahl über Knopf +
			// Auswahl statt Kachel; Knopf und Auswahl-Container je genau einmal im DOM.
			const knopf = page.locator('[data-testid="compare-hub-profil-knopf"]');
			const auswahl = page.locator('[data-testid="compare-hub-profil-auswahl"]');
			expect(await knopf.count(), 'compare-hub-profil-knopf: Anzahl im DOM (ohne :visible)').toBe(1);
			expect(await auswahl.count(), 'compare-hub-profil-auswahl: Anzahl im DOM (ohne :visible)').toBe(1);
			await knopf.click();
			await expect(auswahl).toBeVisible({ timeout: 5_000 });
			await page.locator('[data-testid="compare-hub-profil-auswahl-option-wintersport"]').click();
			await expect(auswahl).toBeHidden({ timeout: 5_000 });
			await expect(knopf).toHaveAttribute('data-selected-value', 'wintersport', { timeout: 5_000 });

			await page.reload();
			await expect(page.getByText(neuName).filter({ visible: true }).first()).toBeVisible({ timeout: 10_000 });
			await expect(page.getByText(neuRegion).filter({ visible: true }).first()).toBeVisible();
			await expect(knopf).toHaveAttribute('data-selected-value', 'wintersport');
			expect(await knopf.count(), 'compare-hub-profil-knopf nach Reload: Anzahl im DOM').toBe(1);
			expect(await auswahl.count(), 'compare-hub-profil-auswahl nach Reload: Anzahl im DOM').toBe(1);

			const p = await fetchPreset(page, presetId);
			expect(p.name).toBe(neuName);
			expect((p.display_config as Record<string, unknown>).region).toBe(neuRegion);
			expect(p.profil).toBe('wintersport');
		} finally {
			await cleanup(page, presetId, locIds);
		}
	});

	test('AC-3 (Desktop): jeder Kopf-PUT trägt nur das geänderte Feld, übrige Felder bleiben', async ({
		page
	}) => {
		await page.setViewportSize(DESKTOP);
		const { presetId, locIds } = await seedPreset(page);
		try {
			await oeffneHub(page, presetId);
			const vorher = ohneZeitstempel(await fetchPreset(page, presetId));
			const bodies = putMitschnitt(page, presetId);
			const sicht = (id: string) => page.locator(`[data-testid="${id}"]:visible`);

			// Region
			await sicht('compare-hub-region-edit-toggle').click();
			await sicht('compare-hub-region-edit').fill('Pitztal');
			await sicht('compare-hub-region-save').click();
			await expect(sicht('compare-hub-region-edit-toggle')).toBeVisible({ timeout: 5_000 });
			expect(bodies.length, 'genau ein PUT nach Region-Speichern').toBe(1);
			expect(Object.keys(bodies[0]).sort()).toEqual(['display_config']);
			expect(Object.keys(bodies[0].display_config as object).sort()).toEqual(['region']);

			// Name
			await sicht('compare-hub-name-edit-toggle').click();
			await sicht('compare-hub-name-edit').fill('Nur Name');
			await sicht('compare-hub-name-save').click();
			await expect(page.getByRole('heading', { level: 1 })).toContainText('Nur Name', { timeout: 5_000 });
			expect(bodies.length).toBe(2);
			expect(Object.keys(bodies[1]).sort()).toEqual(['name']);

			// Profil
			await sicht('compare-hub-profil-option-allgemein').click();
			await expect(sicht('compare-hub-profil-option-allgemein')).toHaveAttribute('data-selected', 'true', {
				timeout: 5_000
			});
			expect(bodies.length).toBe(3);
			expect(Object.keys(bodies[2]).sort()).toEqual(['profil']);

			// Server-Wahrheit: nur die drei Felder geändert, alles andere wie vorher.
			const nachher = ohneZeitstempel(await fetchPreset(page, presetId));
			expect(nachher.name).toBe('Nur Name');
			expect(nachher.profil).toBe('allgemein');
			expect((nachher.display_config as Record<string, unknown>).region).toBe('Pitztal');
			const { display_config: dcV, name: _nv, profil: _pv, ...restV } = vorher;
			const { display_config: dcN, name: _nn, profil: _pn, ...restN } = nachher;
			expect(restN).toEqual(restV);
			const { region: _rv, ...dcRestV } = (dcV ?? {}) as Record<string, unknown>;
			const { region: _rn, ...dcRestN } = (dcN ?? {}) as Record<string, unknown>;
			expect(dcRestN).toEqual(dcRestV);
		} finally {
			await cleanup(page, presetId, locIds);
		}
	});

	test('AC-5 (Desktop): Profil-PUT scheitert → Fehler unter den Kacheln, alte Kachel bleibt gewählt', async ({
		page
	}) => {
		await page.setViewportSize(DESKTOP);
		const { presetId, locIds } = await seedPreset(page);
		try {
			await oeffneHub(page, presetId);
			await page.route(`**${PRESET_URL_PART}${presetId}`, (route) =>
				route.request().method() === 'PUT'
					? route.fulfill({
							status: 500,
							contentType: 'application/json',
							body: JSON.stringify({ error: 'Serverfehler' })
						})
					: route.continue()
			);
			const sicht = (id: string) => page.locator(`[data-testid="${id}"]:visible`);
			await sicht('compare-hub-profil-option-wintersport').click();
			const fehler = sicht('compare-hub-profil-save-error');
			await expect(fehler).toBeVisible({ timeout: 5_000 });
			await expect(fehler).toHaveAttribute('role', 'alert');
			await expect(fehler).toContainText('Serverfehler');
			const gewaehlt = page.locator('[data-testid^="compare-hub-profil-option-"][data-selected="true"]:visible');
			await expect(gewaehlt).toHaveCount(1);
			await expect(gewaehlt).toHaveAttribute('data-testid', 'compare-hub-profil-option-wandern');
			await page.unroute(`**${PRESET_URL_PART}${presetId}`);
			expect((await fetchPreset(page, presetId)).profil).toBe('wandern');
		} finally {
			await cleanup(page, presetId, locIds);
		}
	});

	test('AC-9 (Mobil 375): Eyebrow über dem Namen, Unterzeile „Wandern · 2 Orte"', async ({ page }) => {
		await page.setViewportSize(MOBIL);
		const { presetId, locIds } = await seedPreset(page);
		try {
			await oeffneHub(page, presetId);
			await expect(page.getByText('Orts-Vergleich · Hub', { exact: true })).toBeVisible();
			await expect(page.getByText(/Wandern\s*·\s*2 Orte/).filter({ visible: true }).first()).toBeVisible();
			await expect(page.getByText(/·\s*·/)).toHaveCount(0);
		} finally {
			await cleanup(page, presetId, locIds);
		}
	});

	test('AC-9 (Desktop 1280): keine Eyebrow, Breadcrumb „ORTS-VERGLEICHE / Hub", Unterzeile mit Profil', async ({
		page
	}) => {
		await page.setViewportSize(DESKTOP);
		const { presetId, locIds } = await seedPreset(page);
		try {
			await oeffneHub(page, presetId);
			await expect(page.getByText('Orts-Vergleich · Hub', { exact: true })).toBeHidden();
			await expect(page.getByText(/Orts-Vergleiche/i).filter({ visible: true }).first()).toBeVisible();
			await expect(page.getByText('Hub', { exact: true }).filter({ visible: true }).first()).toBeVisible();
			await expect(page.getByText(/Wandern\s*·\s*2 Orte/).filter({ visible: true }).first()).toBeVisible();
		} finally {
			await cleanup(page, presetId, locIds);
		}
	});

	for (const [label, viewport] of [
		['Desktop 1280', DESKTOP],
		['Mobil 375', MOBIL]
	] as const) {
		test(`AC-10 (${label}): Region höchstens 60 Zeichen, Unterzeile während Bearbeitung weg`, async ({
			page
		}) => {
			await page.setViewportSize(viewport);
			const { presetId, locIds } = await seedPreset(page);
			try {
				await oeffneHub(page, presetId);
				const sicht = (id: string) => page.locator(`[data-testid="${id}"]:visible`);
				const unterzeile = page.getByText(/Wandern\s*·\s*2 Orte/).filter({ visible: true }).first();
				await expect(unterzeile).toBeVisible();

				await sicht('compare-hub-region-edit-toggle').click();
				const eingabe = sicht('compare-hub-region-edit');
				await expect(eingabe).toHaveAttribute('maxlength', '60');
				await eingabe.fill('');
				await eingabe.pressSequentially('x'.repeat(61));
				expect((await eingabe.inputValue()).length).toBe(60);
				await expect(page.locator('span:visible', { hasText: /2 Orte/ })).toHaveCount(0);

				await page.getByRole('button', { name: /^(Abbrechen|×)$/ }).filter({ visible: true }).first().click();
				await expect(page.getByText(/Wandern\s*·\s*2 Orte/).filter({ visible: true }).first()).toBeVisible();
			} finally {
				await cleanup(page, presetId, locIds);
			}
		});
	}

	// Adversary F002/F003/F005 (#2284 S1 Fix-Loop 1): Bedienverhalten im Browser.
	test('Bedienung (Desktop): Vorbelegung, Kacheln gesperrt während Speichern, Fallback-Text, Abbrechen verwirft Fehler', async ({
		page
	}) => {
		await page.setViewportSize(DESKTOP);
		const { presetId, locIds, name } = await seedPreset(page);
		try {
			await oeffneHub(page, presetId);
			const sicht = (id: string) => page.locator(`[data-testid="${id}"]:visible`);
			const abbrechen = () =>
				page.getByRole('button', { name: /^(Abbrechen|×)$/ }).filter({ visible: true }).first().click();

			// F005: Stift öffnen ⇒ Feld trägt den aktuellen Wert.
			await sicht('compare-hub-name-edit-toggle').click();
			await expect(sicht('compare-hub-name-edit')).toHaveValue(name);
			await abbrechen();
			await sicht('compare-hub-region-edit-toggle').click();
			await expect(sicht('compare-hub-region-edit')).toHaveValue('Ötztal');
			await abbrechen();

			// F003: Profil-PUT hängt ⇒ alle Kacheln gesperrt, bis die Antwort kommt.
			let freigeben: () => void = () => {};
			const gehalten = new Promise<void>((r) => (freigeben = r));
			await page.route(`**${PRESET_URL_PART}${presetId}`, async (route) => {
				if (route.request().method() !== 'PUT') return route.continue();
				await gehalten;
				return route.continue();
			});
			await sicht('compare-hub-profil-option-allgemein').click();
			for (const id of KOPF_IDS.filter((i) => i.includes('profil-option-'))) {
				await expect(sicht(id)).toBeDisabled();
			}
			freigeben();
			await expect(sicht('compare-hub-profil-option-allgemein')).toHaveAttribute('data-selected', 'true', {
				timeout: 5_000
			});
			await expect(sicht('compare-hub-profil-option-wandern')).toBeEnabled();
			await page.unroute(`**${PRESET_URL_PART}${presetId}`);

			// F002: 500 ohne `error` im Rumpf ⇒ „Speichern fehlgeschlagen".
			await page.route(`**${PRESET_URL_PART}${presetId}`, (route) =>
				route.request().method() === 'PUT'
					? route.fulfill({ status: 500, contentType: 'application/json', body: '{}' })
					: route.continue()
			);
			await sicht('compare-hub-region-edit-toggle').click();
			await sicht('compare-hub-region-edit').fill('Wallis');
			await sicht('compare-hub-region-save').click();
			await expect(sicht('compare-hub-region-save-error')).toHaveText('Speichern fehlgeschlagen', {
				timeout: 5_000
			});

			// F003: Abbrechen verwirft den Fehler; erneut öffnen ⇒ kein Fehler, alter Wert.
			await abbrechen();
			await expect(page.locator('[data-testid="compare-hub-region-save-error"]')).toHaveCount(0);
			await sicht('compare-hub-region-edit-toggle').click();
			await expect(page.locator('[data-testid="compare-hub-region-save-error"]')).toHaveCount(0);
			await expect(sicht('compare-hub-region-edit')).toHaveValue('Ötztal');
			await page.unroute(`**${PRESET_URL_PART}${presetId}`);
		} finally {
			await cleanup(page, presetId, locIds);
		}
	});

	// Adversary F007 (#2284 S1 Fix-Loop 2): Orte-Anzahl je Viewport aus derselben
	// Quelle wie vor der Umstellung — Desktop zählt die gespeicherten IDs
	// (`location_ids`), Mobil die aufgelösten Orte (`data.locations`). Sichtbar
	// unterscheiden sie sich nur, wenn ein Ort gelöscht ist (das Löschen bereinigt
	// das Preset nicht). Zwei Spans mit getrennten testids
	// (`compare-hub-orte-anzahl-desktop` / `-mobil`), je Viewport genau einer sichtbar.
	test('F007: Orte-Anzahl — Desktop zählt gespeicherte IDs, Mobil aufgelöste Orte (Singular)', async ({ page }) => {
		const { presetId, locIds } = await seedPreset(page);
		try {
			const del = await page.request.delete(`/api/locations/${locIds[1]}`);
			expect(del.ok(), `Ort-Löschen fehlgeschlagen: ${del.status()}`).toBeTruthy();
			expect(((await fetchPreset(page, presetId)).location_ids as string[]).length, 'Messaufbau: Preset behält beide IDs').toBe(2);

			const desktop = page.locator('[data-testid="compare-hub-orte-anzahl-desktop"]');
			const mobil = page.locator('[data-testid="compare-hub-orte-anzahl-mobil"]');
			for (const [viewport, sichtbar, verborgen, soll] of [
				[DESKTOP, desktop, mobil, /^\s*·\s*2 Orte\s*$/],
				[MOBIL, mobil, desktop, /^\s*·\s*1 Ort\s*$/]
			] as const) {
				await page.setViewportSize(viewport);
				await oeffneHub(page, presetId);
				expect(await desktop.count(), 'Desktop-Span genau 1 im DOM').toBe(1);
				expect(await mobil.count(), 'Mobil-Span genau 1 im DOM').toBe(1);
				await expect(verborgen).toBeHidden();
				await expect(sichtbar).toBeVisible();
				await expect(sichtbar).toHaveText(soll);
			}
		} finally {
			await cleanup(page, presetId, locIds);
		}
	});

	test('F007: Orte-Anzahl Desktop-Singular — Preset mit 1 Ort zeigt „· 1 Ort"', async ({ page }) => {
		await page.setViewportSize(DESKTOP);
		const suffix = Date.now();
		const locRes = await page.request.post('/api/locations', {
			data: { name: `E2E 2284-S1 Einzel ${suffix}`, lat: 47.05, lon: 11.05 }
		});
		expect(locRes.ok(), `Location-Anlage fehlgeschlagen: ${locRes.status()}`).toBeTruthy();
		const locId = (await locRes.json()).id as string;
		const presetRes = await page.request.post('/api/compare/presets', {
			data: { name: `E2E 2284-S1 Einzel ${suffix}`, location_ids: [locId], schedule: 'daily', profil: 'wandern' }
		});
		expect(presetRes.ok(), `Preset-Anlage fehlgeschlagen: ${presetRes.status()}`).toBeTruthy();
		const presetId = (await presetRes.json()).id as string;
		try {
			await oeffneHub(page, presetId);
			const sichtbar = page.locator('[data-testid="compare-hub-orte-anzahl-desktop"]');
			await expect(sichtbar).toBeVisible();
			await expect(page.locator('[data-testid="compare-hub-orte-anzahl-mobil"]')).toBeHidden();
			await expect(sichtbar).toHaveText(/^\s*·\s*1 Ort\s*$/);
		} finally {
			await cleanup(page, presetId, [locId]);
		}
	});
});
