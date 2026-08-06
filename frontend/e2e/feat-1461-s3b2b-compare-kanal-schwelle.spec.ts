// E2E (Staging) — Issue #1461 Scheibe S3b-2b: einstellbare
// Dringlichkeits-Schwelle je Alarm-Kanal, jetzt auch für Ortsvergleiche.
// Fokus: AC-13 (Hub-Persistenz über drei Kanäle), AC-14 (Anlege-Pfad
// überlebt Aktivieren), AC-15 (Speicher-Bugfix Telegram/SMS im Hub), plus
// "vier Flächen zeigen die Auswahl" (Trip-Reiter/Hub/Anlegen Desktop+Mobil,
// wertunabhängig — Regress auf AC-10 aus S3b-2a) und AC-16 (Trip unberührt).
//
// Spec: docs/specs/modules/feat_1461_s3b2b_compare_kanal_schwelle.md
//
// Ausführen (gegen Staging, aus frontend/):
//   set -a; source /home/hem/gregor_zwanzig/.claude/validator.env; set +a
//   npx playwright test --config=playwright.1461-s3b2b.staging.config.ts

import { test, expect, type Page } from '@playwright/test';
import { createTestLocation, createTestComparePreset, createTestTrip, cleanupTracked } from './helpers';

function trackConsoleErrors(page: Page): string[] {
	const errors: string[] = [];
	page.on('console', (msg) => {
		if (msg.type() === 'error') errors.push(msg.text());
	});
	page.on('pageerror', (err) => errors.push(String(err)));
	return errors;
}

async function thresholdBtn(page: Page, kind: 'telegram' | 'sms' | 'email', level: 'LOW' | 'MODERATE' | 'HIGH') {
	return page.getByTestId(`alert-channel-threshold-${kind}-${level}`);
}

// CompareNewEditor.svelte montiert BEIDE Layouts (.cm-desktop UND .cm-mobile)
// gleichzeitig ins DOM (CSS-Sichtbarkeits-Schalter, kein bedingtes Mounten) --
// ungescopte getByTestId-Abfragen treffen dort auf zwei Elemente. Für die
// Anlege-Maske deshalb explizit auf das jeweilige Layout scopen.
function scoped(page: Page, layout: '.cm-desktop' | '.cm-mobile') {
	return page.locator(layout);
}
async function thresholdBtnIn(
	root: ReturnType<Page['locator']>,
	kind: 'telegram' | 'sms' | 'email',
	level: 'LOW' | 'MODERATE' | 'HIGH'
) {
	return root.getByTestId(`alert-channel-threshold-${kind}-${level}`);
}

test.describe('Issue #1461 S3b-2b: Kanal-Schwelle Ortsvergleiche', () => {
	test.afterEach(async ({ page }) => {
		await cleanupTracked(page.request);
	});

	// ── AC-13: Vergleichs-Hub — drei Kanal-Stufen ändern, speichern, Reload ────
	test('AC-13: Hub — alle drei Kanal-Schwellen ändern, speichern, Reload zeigt genau die zuletzt gesetzten Werte', async ({
		page
	}) => {
		const errors = trackConsoleErrors(page);
		const suffix = Date.now();
		const locA = await createTestLocation(page.request, { name: `S3b2b Hub A ${suffix}`, lat: 47.1, lon: 11.2 });
		const locB = await createTestLocation(page.request, { name: `S3b2b Hub B ${suffix}`, lat: 47.2, lon: 11.3 });
		const preset = await createTestComparePreset(page.request, {
			name: `S3b2b Hub ${suffix}`,
			locationIds: [locA.id, locB.id]
		});

		await page.goto(`/compare/${preset.id}?tab=alarme`);
		await page.waitForLoadState('networkidle');
		await expect(page.getByTestId('compare-detail-panel-alarme')).toBeVisible({ timeout: 15_000 });
		await expect(page.getByTestId('alert-channel-picker')).toBeVisible({ timeout: 10_000 });

		// Vorbedingung (auch Beleg für "vier Flächen, wertunabhängig"): frisch
		// angelegtes Preset, NIE eine Schwelle gesetzt — alle drei Kanäle zeigen
		// dennoch die Stufen-Auswahl, Startwert "gering".
		for (const kind of ['telegram', 'sms', 'email'] as const) {
			await expect(page.getByTestId(`alert-channel-threshold-${kind}`)).toBeVisible({ timeout: 10_000 });
			await expect(await thresholdBtn(page, kind, 'LOW')).toHaveAttribute('aria-pressed', 'true');
		}
		await page.screenshot({
			path: '../docs/artifacts/feat-1461-s3b2b-compare-kanal-schwelle/ac-13-hub-initial-PASS.png',
			fullPage: true
		});

		// Jeden der drei Kanäle ändern, je einzeln speichern (Wrapper-onclick löst
		// pro Klick einen PUT aus).
		const targets: Record<'telegram' | 'sms' | 'email', 'MODERATE' | 'HIGH'> = {
			telegram: 'MODERATE',
			sms: 'HIGH',
			email: 'MODERATE'
		};
		for (const kind of ['telegram', 'sms', 'email'] as const) {
			const putPromise = page.waitForResponse(
				(res) => res.url().includes(`/api/compare/presets/${preset.id}`) && res.request().method() === 'PUT'
			);
			await (await thresholdBtn(page, kind, targets[kind])).click();
			const putRes = await putPromise;
			expect(putRes.ok(), `PUT nach ${kind}-Schwellenänderung fehlgeschlagen: ${putRes.status()}`).toBeTruthy();
			const body = putRes.request().postDataJSON() as { alert_channel_thresholds?: Record<string, string> };
			expect(body.alert_channel_thresholds, `PUT-Body ohne alert_channel_thresholds (${kind})`).toBeTruthy();
			expect(body.alert_channel_thresholds![kind]).toBe(targets[kind]);
			await expect(await thresholdBtn(page, kind, targets[kind])).toHaveAttribute('aria-pressed', 'true', {
				timeout: 5_000
			});
		}

		// ── Der eigentliche Beweis: Seite neu laden ──────────────────────────
		await page.reload();
		await page.waitForLoadState('networkidle');
		await expect(page.getByTestId('compare-detail-panel-alarme')).toBeVisible({ timeout: 15_000 });
		await expect(page.getByTestId('alert-channel-picker')).toBeVisible({ timeout: 10_000 });

		for (const kind of ['telegram', 'sms', 'email'] as const) {
			await expect(await thresholdBtn(page, kind, targets[kind])).toHaveAttribute('aria-pressed', 'true', {
				timeout: 10_000
			});
		}
		await page.screenshot({
			path: '../docs/artifacts/feat-1461-s3b2b-compare-kanal-schwelle/ac-13-hub-after-reload-PASS.png',
			fullPage: true
		});

		expect(errors, `Konsolenfehler während AC-13-Lauf: ${JSON.stringify(errors)}`).toEqual([]);
	});

	// ── AC-15: Telegram/SMS-Schalter im Hub — Speicher-Bugfix ──────────────────
	test('AC-15: Hub — Telegram- und SMS-Schalter speichern jetzt wirklich, Reload behält Stellung (vorher: Rücksprung-Bug)', async ({
		page
	}) => {
		const errors = trackConsoleErrors(page);
		const suffix = Date.now() + 1;
		const locA = await createTestLocation(page.request, { name: `S3b2b AC15 A ${suffix}`, lat: 47.3, lon: 11.4 });
		const locB = await createTestLocation(page.request, { name: `S3b2b AC15 B ${suffix}`, lat: 47.4, lon: 11.5 });
		const preset = await createTestComparePreset(page.request, {
			name: `S3b2b AC15 ${suffix}`,
			locationIds: [locA.id, locB.id]
		});

		await page.goto(`/compare/${preset.id}?tab=alarme`);
		await page.waitForLoadState('networkidle');
		await expect(page.getByTestId('compare-detail-panel-alarme')).toBeVisible({ timeout: 15_000 });

		const telegramSwitch = page.getByTestId('alert-channel-toggle-telegram').locator('[role="switch"]');
		const smsSwitch = page.getByTestId('alert-channel-toggle-sms').locator('[role="switch"]');
		await expect(telegramSwitch).toBeVisible({ timeout: 10_000 });
		const telegramBefore = await telegramSwitch.getAttribute('aria-checked');
		const smsBefore = await smsSwitch.getAttribute('aria-checked');

		// Telegram umlegen, speichern.
		const putPromise1 = page.waitForResponse(
			(res) => res.url().includes(`/api/compare/presets/${preset.id}`) && res.request().method() === 'PUT'
		);
		await telegramSwitch.click();
		const putRes1 = await putPromise1;
		expect(putRes1.ok(), `PUT nach Telegram-Switch fehlgeschlagen: ${putRes1.status()}`).toBeTruthy();
		const body1 = putRes1.request().postDataJSON() as { send_telegram?: boolean };
		expect(body1.send_telegram, 'PUT-Body enthält kein send_telegram — der bestätigte Speicher-Bug wäre noch da').toBeDefined();
		expect(body1.send_telegram).toBe(telegramBefore === 'false');
		await expect(telegramSwitch).toHaveAttribute('aria-checked', telegramBefore === 'false' ? 'true' : 'false', {
			timeout: 5_000
		});

		// SMS umlegen, speichern.
		const putPromise2 = page.waitForResponse(
			(res) => res.url().includes(`/api/compare/presets/${preset.id}`) && res.request().method() === 'PUT'
		);
		await smsSwitch.click();
		const putRes2 = await putPromise2;
		expect(putRes2.ok(), `PUT nach SMS-Switch fehlgeschlagen: ${putRes2.status()}`).toBeTruthy();
		const body2 = putRes2.request().postDataJSON() as { send_sms?: boolean };
		expect(body2.send_sms, 'PUT-Body enthält kein send_sms').toBeDefined();
		expect(body2.send_sms).toBe(smsBefore === 'false');

		// ── Reload — der eigentliche Beweis, kein Rücksprung ────────────────
		await page.reload();
		await page.waitForLoadState('networkidle');
		await expect(page.getByTestId('compare-detail-panel-alarme')).toBeVisible({ timeout: 15_000 });
		const telegramAfter = page.getByTestId('alert-channel-toggle-telegram').locator('[role="switch"]');
		const smsAfter = page.getByTestId('alert-channel-toggle-sms').locator('[role="switch"]');
		await expect(telegramAfter).toHaveAttribute('aria-checked', telegramBefore === 'false' ? 'true' : 'false', {
			timeout: 10_000
		});
		await expect(smsAfter).toHaveAttribute('aria-checked', smsBefore === 'false' ? 'true' : 'false', {
			timeout: 10_000
		});
		await page.screenshot({
			path: '../docs/artifacts/feat-1461-s3b2b-compare-kanal-schwelle/ac-15-hub-switch-survives-reload-PASS.png',
			fullPage: true
		});

		expect(errors, `Konsolenfehler während AC-15-Lauf: ${JSON.stringify(errors)}`).toEqual([]);
	});

	// ── AC-14: Compare-Anlegen (Desktop) — Stufe überlebt Aktivieren ──────────
	test('AC-14: Anlegen (Desktop) — im Alarme-Schritt gesetzte Stufe steht nach Aktivieren/Neuladen unverändert da', async ({
		page
	}) => {
		const errors = trackConsoleErrors(page);
		await page.setViewportSize({ width: 1280, height: 900 });
		const suffix = Date.now() + 2;
		const locA = await createTestLocation(page.request, { name: `S3b2b AC14 A ${suffix}`, lat: 47.5, lon: 11.6 });
		const locB = await createTestLocation(page.request, { name: `S3b2b AC14 B ${suffix}`, lat: 47.6, lon: 11.7 });

		await page.goto('/compare/new');
		await page.waitForLoadState('networkidle');
		await expect(page.getByTestId('compare-editor')).toBeVisible({ timeout: 10_000 });

		const name = `S3b2b AC14 Vergleich ${suffix}`;
		await page.getByTestId('compare-editor-name').fill(name);

		await page.locator('[data-testid="compare-editor-tab-orte"]:visible').first().click();
		const lib = page.locator('[data-testid="compare-step2-library"]:visible').first();
		await lib.waitFor({ timeout: 8_000 });
		for (const loc of [locA, locB]) {
			await lib.getByText(loc.name, { exact: true }).click();
		}

		await page.locator('[data-testid="compare-editor-tab-metriken"]:visible').first().click();
		await page.locator('[data-testid="compare-editor-tab-idealwerte"]:visible').first().click();
		await page.locator('[data-testid="compare-editor-tab-alarme"]:visible').first().click();

		// CompareNewEditor montiert .cm-desktop UND .cm-mobile gleichzeitig —
		// auf das sichtbare Desktop-Layout scopen (sonst strict-mode-Fehler:
		// zwei alert-channel-picker im DOM).
		const desktop = scoped(page, '.cm-desktop');
		const picker = desktop.getByTestId('alert-channel-picker');
		await expect(picker).toBeVisible({ timeout: 10_000 });

		// Vorbedingung "vier Flächen, wertunabhängig": frisch angelegter Vergleich,
		// noch nie gespeichert — die Auswahl ist trotzdem sichtbar, Startwert "gering".
		for (const kind of ['telegram', 'sms', 'email'] as const) {
			await expect(desktop.getByTestId(`alert-channel-threshold-${kind}`)).toBeVisible({ timeout: 10_000 });
			await expect(await thresholdBtnIn(desktop, kind, 'LOW')).toHaveAttribute('aria-pressed', 'true');
		}
		await page.screenshot({
			path: '../docs/artifacts/feat-1461-s3b2b-compare-kanal-schwelle/ac-14-anlegen-desktop-alarme-step-PASS.png',
			fullPage: true
		});

		// Telegram auf "hoch" setzen — höher als "gering".
		await (await thresholdBtnIn(desktop, 'telegram', 'HIGH')).click();
		await expect(await thresholdBtnIn(desktop, 'telegram', 'HIGH')).toHaveAttribute('aria-pressed', 'true');

		await page.locator('[data-testid="compare-editor-tab-versand"]:visible').first().click();

		const [postRes] = await Promise.all([
			page.waitForResponse(
				(res) => res.url().endsWith('/api/compare/presets') && res.request().method() === 'POST'
			),
			page.getByTestId('compare-editor-activate').click()
		]);
		expect(postRes.ok(), `POST beim Aktivieren fehlgeschlagen: ${postRes.status()}`).toBeTruthy();
		const postBody = postRes.request().postDataJSON() as { alert_channel_thresholds?: Record<string, string> };
		expect(postBody.alert_channel_thresholds, 'POST-Body ohne alert_channel_thresholds').toBeTruthy();
		expect(postBody.alert_channel_thresholds!.telegram).toBe('HIGH');
		expect(postBody.alert_channel_thresholds!.sms).toBe('LOW');
		expect(postBody.alert_channel_thresholds!.email).toBe('LOW');

		const created = (await postRes.json()) as { id: string };
		expect(created.id, 'Aktivieren lieferte keine Preset-ID').toBeTruthy();

		// Die App macht nach dem POST selbst einen client-seitigen goto() zu
		// /compare/{id} (saveNewPreset). Erst DAS abwarten, sonst kollidiert
		// unser eigenes page.goto() unten mit dem noch laufenden App-internen
		// fetch/Navigations-Zyklus (beobachtet: "TypeError: Failed to fetch"
		// als Konsolenfehler — ein Race durch den Test, kein Produktfehler).
		await page.waitForURL(new RegExp(`/compare/${created.id}`), { timeout: 15_000 }).catch(() => {});

		// ── Neu laden (frischer GET) — der eigentliche Beweis ────────────────
		await page.goto(`/compare/${created.id}?tab=alarme`);
		await page.waitForLoadState('networkidle');
		await expect(page.getByTestId('compare-detail-panel-alarme')).toBeVisible({ timeout: 15_000 });
		await expect(await thresholdBtn(page, 'telegram', 'HIGH')).toHaveAttribute('aria-pressed', 'true', {
			timeout: 10_000
		});
		await expect(await thresholdBtn(page, 'sms', 'LOW')).toHaveAttribute('aria-pressed', 'true');
		await expect(await thresholdBtn(page, 'email', 'LOW')).toHaveAttribute('aria-pressed', 'true');
		await page.screenshot({
			path: '../docs/artifacts/feat-1461-s3b2b-compare-kanal-schwelle/ac-14-after-activate-reload-PASS.png',
			fullPage: true
		});

		await page.request.delete(`/api/compare/presets/${created.id}`).catch(() => {});
		expect(errors, `Konsolenfehler während AC-14-Lauf: ${JSON.stringify(errors)}`).toEqual([]);
	});

	// ── Vierte Fläche: Compare-Anlegen Mobil — Auswahl sichtbar, wertunabhängig ──
	test('Vierte Fläche: Anlegen (Mobil) zeigt die Stufen-Auswahl ebenfalls, Startwert "gering", nichts gesetzt', async ({
		page
	}) => {
		const errors = trackConsoleErrors(page);
		await page.setViewportSize({ width: 390, height: 844 });
		const suffix = Date.now() + 3;
		const locA = await createTestLocation(page.request, { name: `S3b2b Mobil A ${suffix}`, lat: 47.7, lon: 11.8 });
		const locB = await createTestLocation(page.request, { name: `S3b2b Mobil B ${suffix}`, lat: 47.8, lon: 11.9 });

		await page.goto('/compare/new');
		await page.waitForLoadState('networkidle');
		const mobile = scoped(page, '.cm-mobile');
		await mobile.getByTestId('compare-editor-name-mobile').fill(`S3b2b Mobil ${suffix}`);

		// Orte-Tab öffnen (Step2Orte(dense) mountet nur bei activeTab === 'orte').
		await mobile.getByTestId('cm-mobile-tab-orte').click({ force: true });
		await mobile.getByTestId('compare-step2-mobile-library-btn').click();
		for (const loc of [locA, locB]) {
			await page.getByTestId(`compare-step2-mobile-lib-check-${loc.id}`).click();
		}
		// Sheet schließen (mobile/Sheet.svelte hat keinen Escape-Handler — der
		// echte Klickpfad geht über den X-Knopf, aria-label "Schliessen").
		await page.getByRole('button', { name: 'Schliessen' }).click();

		await mobile.getByTestId('cm-mobile-tab-metriken').click({ force: true });
		await mobile.getByTestId('cm-mobile-tab-idealwerte').click({ force: true });
		await mobile.getByTestId('cm-mobile-tab-alarme').click({ force: true });

		const picker = mobile.getByTestId('alert-channel-picker');
		await expect(picker).toBeVisible({ timeout: 10_000 });
		for (const kind of ['telegram', 'sms', 'email'] as const) {
			await expect(mobile.getByTestId(`alert-channel-threshold-${kind}`)).toBeVisible({ timeout: 10_000 });
			await expect(await thresholdBtnIn(mobile, kind, 'LOW')).toHaveAttribute('aria-pressed', 'true');
		}
		await page.screenshot({
			path: '../docs/artifacts/feat-1461-s3b2b-compare-kanal-schwelle/vier-flaechen-mobil-anlegen-PASS.png',
			fullPage: true
		});

		expect(errors, `Konsolenfehler während Mobil-Anlegen-Lauf: ${JSON.stringify(errors)}`).toEqual([]);
	});

	// ── AC-16: Trip unberührt — Regress ─────────────────────────────────────
	test('AC-16: Trip-Alarm-Reiter unverändert — Stufen-Auswahl weiterhin da, Speichern weiterhin fehlerfrei', async ({
		page
	}) => {
		const errors = trackConsoleErrors(page);
		const suffix = Date.now() + 4;
		const today = new Date().toISOString().slice(0, 10);
		const trip = await createTestTrip(page.request, {
			id: `e2e-1461-s3b2b-trip-${suffix}`,
			name: `S3b2b AC16 Trip ${suffix}`,
			stages: [
				{
					id: `s3b2b-stage-1-${suffix}`,
					name: 'Etappe 1',
					date: today,
					waypoints: [
						{ id: `s3b2b-wp-1-${suffix}`, name: 'Start', lat: 42.1, lon: 9.0, elevation_m: 800 },
						{ id: `s3b2b-wp-2-${suffix}`, name: 'Ziel', lat: 42.2, lon: 9.1, elevation_m: 1000 }
					]
				}
			]
		});

		await page.goto(`/trips/${trip.id}?tab=alarme`);
		await page.waitForLoadState('networkidle');
		await expect(page.getByTestId('trip-detail-panel-alarme')).toBeVisible({ timeout: 15_000 });
		await expect(page.getByTestId('alert-channel-picker')).toBeVisible({ timeout: 10_000 });
		for (const kind of ['telegram', 'sms', 'email'] as const) {
			await expect(page.getByTestId(`alert-channel-threshold-${kind}`)).toBeVisible({ timeout: 10_000 });
		}

		// Speichern über einen unbeteiligten Weg (Stages-Tab, Aktivität ändern) —
		// AC-16 verlangt: Trip-Oberfläche öffnen und speichern, kein Fehler.
		await page.goto(`/trips/${trip.id}?tab=stages`);
		await expect(page.getByTestId('trip-detail-panel-stages')).toBeVisible({ timeout: 15_000 });
		const activitySelect = page.getByTestId('edit-activity-dropdown');
		await expect(activitySelect).toBeVisible({ timeout: 10_000 });
		const putPromise = page.waitForResponse(
			(res) => res.url().includes(`/api/trips/${trip.id}`) && res.request().method() === 'PUT'
		);
		await activitySelect.selectOption('mtb');
		const putRes = await putPromise;
		expect(putRes.ok(), `Trip-Speichern fehlgeschlagen: ${putRes.status()}`).toBeTruthy();
		await page.screenshot({
			path: '../docs/artifacts/feat-1461-s3b2b-compare-kanal-schwelle/ac-16-trip-unberuehrt-PASS.png',
			fullPage: true
		});

		expect(errors, `Konsolenfehler während AC-16-Lauf: ${JSON.stringify(errors)}`).toEqual([]);
	});

	// ── Mandantentrennung ────────────────────────────────────────────────────
	test('Mandantentrennung: Nutzer-A-Schwelle bleibt bei Nutzer B unsichtbar, Cross-User-PUT scheitert', async ({
		page: pageA,
		browser
	}) => {
		const suffix = Date.now() + 5;
		let presetAId: string | null = null;
		let ctxB: Awaited<ReturnType<typeof browser.newContext>> | null = null;
		try {
			const locA = await createTestLocation(pageA.request, { name: `S3b2b Mandant A ${suffix}`, lat: 48.1, lon: 12.2 });
			const locA2 = await createTestLocation(pageA.request, { name: `S3b2b Mandant A2 ${suffix}`, lat: 48.2, lon: 12.3 });
			const presetA = await createTestComparePreset(pageA.request, {
				name: `S3b2b Mandant A ${suffix}`,
				locationIds: [locA.id, locA2.id]
			});
			presetAId = presetA.id;

			// Nutzer A setzt Telegram auf "hoch". PUT /api/compare/presets/{id}
			// dekodiert das VOLLE ComparePreset-Modell (anders als beim Trip) —
			// die Pflichtfelder müssen mitgesendet werden, sonst 400 "name is
			// required" (gemessen: ein reiner alert_channel_thresholds-Body
			// scheitert an der Validierung, bevor der RMW-Merge greift).
			const putA = await pageA.request.put(`/api/compare/presets/${presetA.id}`, {
				data: {
					name: presetA.name,
					location_ids: [locA.id, locA2.id],
					schedule: 'daily',
					profil: 'wandern',
					hour_from: 7,
					hour_to: 18,
					empfaenger: ['urlauber@example.com'],
					alert_channel_thresholds: { telegram: 'HIGH' }
				}
			});
			expect(
				putA.ok(),
				`Vorbereitungs-PUT (Nutzer A, Telegram=HIGH) fehlgeschlagen: ${putA.status()} ${await putA.text()}`
			).toBeTruthy();

			// Nutzer B: eigener Kontext, eigene Registrierung (kein geerbtes
			// Admin-Cookie — sonst liefe der PUT unten fälschlich unter A).
			ctxB = await browser.newContext({ storageState: undefined });
			const pageB = await ctxB.newPage();
			const userB = `e2e1461s3b2b${suffix}`;
			const reg = await pageB.request.post('/api/auth/register', {
				data: { username: userB, password: 'Test1234!x', email: `${userB}@example.com` }
			});
			expect([200, 201].includes(reg.status()), `Registrierung B fehlgeschlagen: ${reg.status()}`).toBeTruthy();
			const loginB = await pageB.request.post('/api/auth/login', {
				data: { username: userB, password: 'Test1234!x' }
			});
			expect(loginB.ok(), `Login B fehlgeschlagen: ${loginB.status()}`).toBeTruthy();

			// Nutzer B legt eigenen Ortsvergleich an — ohne eigene Schwelle: "gering".
			const locB = await createTestLocation(pageB.request, { name: `S3b2b Mandant B ${suffix}`, lat: 48.3, lon: 12.4 });
			const locB2 = await createTestLocation(pageB.request, { name: `S3b2b Mandant B2 ${suffix}`, lat: 48.4, lon: 12.5 });
			const presetB = await pageB.request.post('/api/compare/presets', {
				data: {
					name: `S3b2b Mandant B ${suffix}`,
					location_ids: [locB.id, locB2.id],
					schedule: 'daily',
					profil: 'wandern',
					hour_from: 7,
					hour_to: 18,
					empfaenger: []
				}
			});
			expect(presetB.ok(), 'Preset-Anlage B fehlgeschlagen').toBeTruthy();
			const presetBBody = (await presetB.json()) as { id: string };

			const getB = await pageB.request.get(`/api/compare/presets/${presetBBody.id}`);
			expect(getB.ok()).toBeTruthy();
			const presetBData = (await getB.json()) as { alert_channel_thresholds?: Record<string, string> | null };
			// Nutzer B sieht NICHT As Schwelle — sein eigener Kanal ist unberührt
			// (fehlt entweder ganz oder steht auf "gering", nie "HIGH" von A).
			expect(presetBData.alert_channel_thresholds?.telegram).not.toBe('HIGH');

			// Nutzer B kann As Preset per PUT NICHT überschreiben (404, Mandantentrennung).
			const putBOnA = await pageB.request.put(`/api/compare/presets/${presetAId}`, {
				data: {
					name: 'Hijack',
					location_ids: [],
					schedule: 'daily',
					profil: 'wandern',
					hour_from: 7,
					hour_to: 18,
					empfaenger: []
				}
			});
			expect(putBOnA.status()).toBe(404);

			// As Preset bleibt bei A unverändert (Telegram weiterhin "hoch").
			const getA = await pageA.request.get(`/api/compare/presets/${presetAId}`);
			expect(getA.ok()).toBeTruthy();
			const presetAData = (await getA.json()) as { alert_channel_thresholds?: Record<string, string> };
			expect(presetAData.alert_channel_thresholds?.telegram).toBe('HIGH');

			await pageB.request.delete(`/api/compare/presets/${presetBBody.id}`).catch(() => {});
			await pageB.request.delete(`/api/locations/${locB.id}`).catch(() => {});
			await pageB.request.delete(`/api/locations/${locB2.id}`).catch(() => {});
		} finally {
			if (presetAId) await pageA.request.delete(`/api/compare/presets/${presetAId}`).catch(() => {});
			if (ctxB) await ctxB.close();
		}
	});

	// ── Runde 2 (Adversary-Sweep): Doppelklick-Race im Hub ─────────────────
	test('Adversary: Doppelklick auf zwei verschiedene Schwellen-Stufen im Hub — Endzustand nach Reload konsistent', async ({
		page
	}) => {
		const errors = trackConsoleErrors(page);
		const suffix = Date.now() + 6;
		const locA = await createTestLocation(page.request, { name: `S3b2b Adv A ${suffix}`, lat: 46.9, lon: 10.9 });
		const locB = await createTestLocation(page.request, { name: `S3b2b Adv B ${suffix}`, lat: 47.0, lon: 11.0 });
		const preset = await createTestComparePreset(page.request, {
			name: `S3b2b Adv ${suffix}`,
			locationIds: [locA.id, locB.id]
		});

		await page.goto(`/compare/${preset.id}?tab=alarme`);
		await page.waitForLoadState('networkidle');
		await expect(page.getByTestId('alert-channel-picker')).toBeVisible({ timeout: 10_000 });

		// Schnelle Doppel-Aktion: zwei verschiedene Stufen desselben Kanals kurz
		// hintereinander klicken (MODERATE, dann sofort HIGH) — die Wrapper-
		// Persistenz (onclick-Bubble, hubPutQueue.enqueue) muss das serialisieren,
		// nicht verlieren. Letzter Klick gewinnt.
		await (await thresholdBtn(page, 'telegram', 'MODERATE')).click();
		await (await thresholdBtn(page, 'telegram', 'HIGH')).click();
		// Auf die letzte PUT-Antwort warten (Queue serialisiert, kann also erst
		// nach der ersten fertig sein).
		await expect(await thresholdBtn(page, 'telegram', 'HIGH')).toHaveAttribute('aria-pressed', 'true', {
			timeout: 10_000
		});

		await page.reload();
		await page.waitForLoadState('networkidle');
		await expect(page.getByTestId('alert-channel-picker')).toBeVisible({ timeout: 10_000 });
		await expect(await thresholdBtn(page, 'telegram', 'HIGH')).toHaveAttribute('aria-pressed', 'true', {
			timeout: 10_000
		});
		// Unberührte Kanäle bleiben beim Startwert.
		await expect(await thresholdBtn(page, 'sms', 'LOW')).toHaveAttribute('aria-pressed', 'true');
		await expect(await thresholdBtn(page, 'email', 'LOW')).toHaveAttribute('aria-pressed', 'true');

		expect(errors, `Konsolenfehler während Adversary-Doppelklick-Lauf: ${JSON.stringify(errors)}`).toEqual([]);
	});

	// ── Runde 2 (Adversary-Sweep): AC-9 am echten Klickpfad ─────────────────
	test('Adversary: eine Schwelle setzen, dann eine ANDERE Hub-Einstellung ändern — Schwelle bleibt (AC-9 am UI-Pfad)', async ({
		page
	}) => {
		const errors = trackConsoleErrors(page);
		const suffix = Date.now() + 7;
		const locA = await createTestLocation(page.request, { name: `S3b2b AC9ui A ${suffix}`, lat: 46.7, lon: 10.7 });
		const locB = await createTestLocation(page.request, { name: `S3b2b AC9ui B ${suffix}`, lat: 46.8, lon: 10.8 });
		const preset = await createTestComparePreset(page.request, {
			name: `S3b2b AC9ui ${suffix}`,
			locationIds: [locA.id, locB.id]
		});

		await page.goto(`/compare/${preset.id}?tab=alarme`);
		await page.waitForLoadState('networkidle');
		await expect(page.getByTestId('alert-channel-picker')).toBeVisible({ timeout: 10_000 });

		const putPromise1 = page.waitForResponse(
			(res) => res.url().includes(`/api/compare/presets/${preset.id}`) && res.request().method() === 'PUT'
		);
		await (await thresholdBtn(page, 'sms', 'HIGH')).click();
		await putPromise1;
		await expect(await thresholdBtn(page, 'sms', 'HIGH')).toHaveAttribute('aria-pressed', 'true', { timeout: 5_000 });

		// Andere Einstellung im selben Reiter ändern (amtliche Warnungen), OHNE
		// die Schwelle anzufassen.
		const officialToggle = page.getByTestId('alerts-tab-official-alert-triggers-toggle');
		await expect(officialToggle).toBeVisible({ timeout: 10_000 });
		const putPromise2 = page.waitForResponse(
			(res) => res.url().includes(`/api/compare/presets/${preset.id}`) && res.request().method() === 'PUT'
		);
		await officialToggle.click();
		const putRes2 = await putPromise2;
		expect(putRes2.ok(), `PUT nach Toggle-Änderung fehlgeschlagen: ${putRes2.status()}`).toBeTruthy();
		const body2 = putRes2.request().postDataJSON() as { alert_channel_thresholds?: Record<string, string> };
		// AC-9-Kernaussage am UI-Pfad: der konsolidierte Snapshot sendet die
		// Schwelle unverändert MIT (kein separates Vergessen), sms bleibt HIGH.
		expect(body2.alert_channel_thresholds?.sms).toBe('HIGH');

		await page.reload();
		await page.waitForLoadState('networkidle');
		await expect(page.getByTestId('alert-channel-picker')).toBeVisible({ timeout: 10_000 });
		await expect(await thresholdBtn(page, 'sms', 'HIGH')).toHaveAttribute('aria-pressed', 'true', {
			timeout: 10_000
		});

		expect(errors, `Konsolenfehler während AC-9-UI-Lauf: ${JSON.stringify(errors)}`).toEqual([]);
	});
});
