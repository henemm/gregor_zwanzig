// E2E (Staging, Marker `live`) — Issue #1745 Scheibe A: Premium-SMS als
// vierter Kanal in der Alarm-Kanal-Auswahl.
// Spec: docs/specs/modules/fix_1745_a_alarm_kanal_premium_sms_ui.md
//   AC-8  — Ortsvergleichs-Hub: Dringlichkeits-Schwelle überlebt Speichern+Reload
//   AC-10 — Ortsvergleichs-Hub: Haken überlebt Speichern+Reload, PUT trägt send_premium_sms
//   AC-14 — TRIP: Haken überlebt Speichern+Reload, PUT trägt alert_channels.premium_sms
//
// 🔴 WARUM DREI KLICKPFADE UND NICHT EINER: Trip und Ortsvergleich teilen die
// KOMPONENTE (AlarmeTab.svelte), aber NICHT den SPEICHERWEG. Der Trip
// persistiert über `buildAlarmeDeliveryPayload` (ein konsolidierter PUT auf
// /api/trips/{id}), der Ortsvergleich über die Bridge-Kette
// (currentAlarmSnapshot → flushPendingAlarmSave → buildHubPutPayload → PUT auf
// /api/compare/presets/{id}). Ein Nachweis, der die eine Kette prüft und die
// andere annimmt, prüft das Falsche — und der Trip ist der Fall, an dem dieses
// Issue aufgefallen ist (KHW 403).
//
// Diese Datei wird in der RED-Phase GESCHRIEBEN, NICHT AUSGEFÜHRT: sie läuft
// gegen Staging, wo der Code noch nicht liegt. Ausführung gehört zur
// Staging-Verifikation nach dem Merge.
//
// Vorbild/Struktur: feat-1461-s3b2b-compare-kanal-schwelle.spec.ts
//
// Ausführen (gegen Staging, aus frontend/):
//   set -a; source /home/hem/gregor_zwanzig/.claude/validator.env; set +a
//   npx playwright test --config=playwright.1745-a.staging.config.ts
// (Die Config selbst legt Phase 6 an — Muster playwright.1461-s3b2b.staging.config.ts,
//  Setup-Projekt: e2e/feat-1745-a.staging.setup.ts.)

import { test, expect, type Page } from '@playwright/test';
import { createTestLocation, createTestComparePreset, createTestTrip, cleanupTracked } from './helpers';

const KIND = 'premium_sms';

function trackConsoleErrors(page: Page): string[] {
	const errors: string[] = [];
	page.on('console', (msg) => {
		if (msg.type() === 'error') errors.push(msg.text());
	});
	page.on('pageerror', (err) => errors.push(String(err)));
	return errors;
}

function premiumSwitch(page: Page) {
	return page.getByTestId(`alert-channel-toggle-${KIND}`).locator('[role="switch"]');
}

function thresholdBtn(page: Page, level: 'LOW' | 'MODERATE' | 'HIGH') {
	return page.getByTestId(`alert-channel-threshold-${KIND}-${level}`);
}

/**
 * Vorbedingung für alle drei Klickpfade: der Staging-Nutzer muss Tarif
 * `premium` haben (user_tier.py:33) — sonst ist die Zeile korrekt gesperrt
 * (AC-5/D3) und der Klickpfad gar nicht begehbar. Das ist dann KEIN
 * Produktfehler, sondern eine fehlende Testvoraussetzung; die Meldung sagt das.
 */
async function assertPremiumTarifVorhanden(page: Page): Promise<void> {
	const res = await page.request.get('/api/auth/profile');
	expect(res.ok(), `GET /api/auth/profile fehlgeschlagen: ${res.status()}`).toBeTruthy();
	const profile = (await res.json()) as { premium_sms_allowed?: boolean };
	expect(
		profile.premium_sms_allowed,
		'VORBEDINGUNG, kein Produktbefund: der Staging-Nutzer hat keinen Premium-Tarif ' +
			'(premium_sms_allowed !== true). Die Premium-SMS-Zeile ist dann absichtlich gesperrt ' +
			'(AC-5/D3) und dieser Klickpfad nicht begehbar — Tarif setzen, dann erneut laufen.'
	).toBe(true);
}

test.describe('Issue #1745 Scheibe A: Premium-SMS in der Alarm-Kanal-Auswahl', () => {
	test.afterEach(async ({ page }) => {
		await cleanupTracked(page.request);
	});

	// ── AC-8: Ortsvergleichs-Hub — Dringlichkeits-Schwelle ───────────────────
	// Mutation (Spec): handleThresholdChange()s `vergleich`-Zweig bleibt bei der
	// Drei-Felder-Konstruktion {telegram, sms, email} (Landmine 1) — der Regler
	// wäre sichtbar, der Wert ginge beim Speichern still verloren.
	test('AC-8: hub_premium_sms_schwelle_ueberlebt_speichern_und_reload', async ({ page }) => {
		const errors = trackConsoleErrors(page);
		const suffix = Date.now();
		const locA = await createTestLocation(page.request, { name: `1745A AC8 A ${suffix}`, lat: 46.6, lon: 12.9 });
		const locB = await createTestLocation(page.request, { name: `1745A AC8 B ${suffix}`, lat: 46.7, lon: 13.0 });
		const preset = await createTestComparePreset(page.request, {
			name: `1745A AC8 ${suffix}`,
			locationIds: [locA.id, locB.id]
		});

		await page.goto(`/compare/${preset.id}?tab=alarme`);
		await page.waitForLoadState('networkidle');
		await expect(page.getByTestId('compare-detail-panel-alarme')).toBeVisible({ timeout: 15_000 });
		await expect(page.getByTestId('alert-channel-picker')).toBeVisible({ timeout: 10_000 });
		await assertPremiumTarifVorhanden(page);

		// Die vierte Zeile existiert überhaupt (AC-1 am echten Klickpfad) und
		// startet — nie eingestellt — auf „gering".
		await expect(page.getByTestId(`alert-channel-row-${KIND}`)).toBeVisible({ timeout: 10_000 });
		await expect(page.getByTestId(`alert-channel-threshold-${KIND}`)).toBeVisible({ timeout: 10_000 });
		await expect(thresholdBtn(page, 'LOW')).toHaveAttribute('aria-pressed', 'true');

		const putPromise = page.waitForResponse(
			(res) => res.url().includes(`/api/compare/presets/${preset.id}`) && res.request().method() === 'PUT'
		);
		await thresholdBtn(page, 'HIGH').click();
		const putRes = await putPromise;
		expect(putRes.ok(), `PUT nach Premium-SMS-Schwellenänderung fehlgeschlagen: ${putRes.status()}`).toBeTruthy();

		const body = putRes.request().postDataJSON() as { alert_channel_thresholds?: Record<string, string> };
		expect(body.alert_channel_thresholds, 'PUT-Body ohne alert_channel_thresholds').toBeTruthy();
		expect(
			body.alert_channel_thresholds![KIND],
			'Der PUT-Body trägt die Premium-SMS-Schwelle nicht — Landmine 1: der vergleich-Zweig von ' +
				'handleThresholdChange baut sein Rückschreibe-Objekt dreifeldig und verwirft den ' +
				'berechneten vierten Wert still.'
		).toBe('HIGH');

		// Die anderen drei Kanäle dürfen dabei nicht mitgezogen werden.
		expect(body.alert_channel_thresholds!.telegram).toBe('LOW');
		expect(body.alert_channel_thresholds!.sms).toBe('LOW');

		// ── Der eigentliche Beweis: neu laden ────────────────────────────────
		await page.reload();
		await page.waitForLoadState('networkidle');
		await expect(page.getByTestId('compare-detail-panel-alarme')).toBeVisible({ timeout: 15_000 });
		await expect(thresholdBtn(page, 'HIGH')).toHaveAttribute('aria-pressed', 'true', { timeout: 10_000 });
		await page.screenshot({
			path: '../docs/artifacts/fix-1745-alarm-kanaele-premium-sms/ac-8-hub-schwelle-nach-reload-PASS.png',
			fullPage: true
		});

		expect(errors, `Konsolenfehler während AC-8-Lauf: ${JSON.stringify(errors)}`).toEqual([]);
	});

	// ── AC-10: Ortsvergleichs-Hub — Haken ────────────────────────────────────
	// Mutation (Spec): currentAlarmSnapshot() (CompareTabs.svelte:575-596) liest
	// `sendPremiumSms` nicht aus `wizardState` — der Klick wäre sichtbar, käme
	// aber nie im PUT-Body an.
	test('AC-10: hub_premium_sms_haken_ueberlebt_speichern_und_reload', async ({ page }) => {
		const errors = trackConsoleErrors(page);
		const suffix = Date.now() + 1;
		const locA = await createTestLocation(page.request, { name: `1745A AC10 A ${suffix}`, lat: 46.8, lon: 13.1 });
		const locB = await createTestLocation(page.request, { name: `1745A AC10 B ${suffix}`, lat: 46.9, lon: 13.2 });
		const preset = await createTestComparePreset(page.request, {
			name: `1745A AC10 ${suffix}`,
			locationIds: [locA.id, locB.id]
		});

		await page.goto(`/compare/${preset.id}?tab=alarme`);
		await page.waitForLoadState('networkidle');
		await expect(page.getByTestId('compare-detail-panel-alarme')).toBeVisible({ timeout: 15_000 });
		await expect(page.getByTestId('alert-channel-picker')).toBeVisible({ timeout: 10_000 });
		await assertPremiumTarifVorhanden(page);

		const sw = premiumSwitch(page);
		await expect(sw).toBeVisible({ timeout: 10_000 });
		// Neuanlage-Default ist AUS (D1, Kostenkanal) — und der Schalter ist bei
		// vorhandenem Premium-Tarif bedienbar, nicht gesperrt (AC-6).
		await expect(sw).toHaveAttribute('aria-checked', 'false');
		await expect(sw).not.toHaveAttribute('aria-disabled', 'true');

		const putPromise = page.waitForResponse(
			(res) => res.url().includes(`/api/compare/presets/${preset.id}`) && res.request().method() === 'PUT'
		);
		await sw.click();
		const putRes = await putPromise;
		expect(putRes.ok(), `PUT nach Premium-SMS-Schalter fehlgeschlagen: ${putRes.status()}`).toBeTruthy();

		const body = putRes.request().postDataJSON() as { send_premium_sms?: boolean };
		expect(
			body.send_premium_sms,
			'PUT-Body enthält kein send_premium_sms — der Haken wäre sichtbar und wirkungslos ' +
				'(currentAlarmSnapshot()/buildHubPutPayload, Landmine 3).'
		).toBe(true);

		// ── Der eigentliche Beweis: neu laden ────────────────────────────────
		await page.reload();
		await page.waitForLoadState('networkidle');
		await expect(page.getByTestId('compare-detail-panel-alarme')).toBeVisible({ timeout: 15_000 });
		await expect(premiumSwitch(page)).toHaveAttribute('aria-checked', 'true', { timeout: 10_000 });
		await page.screenshot({
			path: '../docs/artifacts/fix-1745-alarm-kanaele-premium-sms/ac-10-hub-haken-nach-reload-PASS.png',
			fullPage: true
		});

		// Gegenprobe am Server, nicht nur an der Oberfläche.
		const getRes = await page.request.get(`/api/compare/presets/${preset.id}`);
		expect(getRes.ok()).toBeTruthy();
		expect((await getRes.json()).send_premium_sms).toBe(true);

		expect(errors, `Konsolenfehler während AC-10-Lauf: ${JSON.stringify(errors)}`).toEqual([]);
	});

	// ── AC-14: TRIP — Haken (die ANDERE Speicherkette) ───────────────────────
	// Mutation (Spec): buildAlarmeDeliveryPayload() nimmt `premium_sms`
	// entgegen, schreibt es aber nicht in das alert_channels-Objekt der Payload.
	test('AC-14: trip_premium_sms_haken_ueberlebt_speichern_und_reload', async ({ page }) => {
		const errors = trackConsoleErrors(page);
		const suffix = Date.now() + 2;
		const today = new Date().toISOString().slice(0, 10);
		const trip = await createTestTrip(page.request, {
			id: `e2e-1745a-trip-${suffix}`,
			name: `1745A AC14 Trip ${suffix}`,
			stages: [
				{
					id: `s1745a-stage-1-${suffix}`,
					name: 'Etappe 1',
					date: today,
					waypoints: [
						{ id: `s1745a-wp-1-${suffix}`, name: 'Start', lat: 46.6, lon: 12.9, elevation_m: 1400 },
						{ id: `s1745a-wp-2-${suffix}`, name: 'Ziel', lat: 46.7, lon: 13.0, elevation_m: 1900 }
					]
				}
			]
		});

		await page.goto(`/trips/${trip.id}?tab=alarme`);
		await page.waitForLoadState('networkidle');
		await expect(page.getByTestId('trip-detail-panel-alarme')).toBeVisible({ timeout: 15_000 });
		await expect(page.getByTestId('alert-channel-picker')).toBeVisible({ timeout: 10_000 });
		await assertPremiumTarifVorhanden(page);

		const sw = premiumSwitch(page);
		await expect(
			page.getByTestId(`alert-channel-row-${KIND}`),
			'Die vierte Kanalzeile fehlt im TRIP-Alarme-Reiter — genau der gemeldete Zustand: kein ' +
				'einziger Alarm erreicht das Garmin-Gerät, obwohl das Backend seit #1701 sendebereit ist.'
		).toBeVisible({ timeout: 10_000 });
		await expect(sw).toHaveAttribute('aria-checked', 'false');
		await expect(sw).not.toHaveAttribute('aria-disabled', 'true');

		const putPromise = page.waitForResponse(
			(res) => res.url().includes(`/api/trips/${trip.id}`) && res.request().method() === 'PUT'
		);
		await sw.click();
		const putRes = await putPromise;
		expect(putRes.ok(), `Trip-PUT nach Premium-SMS-Schalter fehlgeschlagen: ${putRes.status()}`).toBeTruthy();

		const body = putRes.request().postDataJSON() as { alert_channels?: Record<string, boolean> };
		expect(body.alert_channels, 'Trip-PUT-Body ohne alert_channels').toBeTruthy();
		expect(
			body.alert_channels![KIND],
			'Der Trip-PUT trägt alert_channels.premium_sms nicht — der Trip speichert über eine ANDERE ' +
				'Kette als der Ortsvergleich (buildAlarmeDeliveryPayload), und das ist die Kette, an der ' +
				'dieses Issue aufgefallen ist.'
		).toBe(true);
		// Die drei Bestandskanäle reisen unverändert mit (D7: vier explizite Werte).
		expect(Object.keys(body.alert_channels!).sort()).toEqual(
			['email', 'premium_sms', 'sms', 'telegram'].sort()
		);

		// ── Der eigentliche Beweis: neu laden ────────────────────────────────
		await page.reload();
		await page.waitForLoadState('networkidle');
		await expect(page.getByTestId('trip-detail-panel-alarme')).toBeVisible({ timeout: 15_000 });
		await expect(premiumSwitch(page)).toHaveAttribute('aria-checked', 'true', { timeout: 10_000 });
		await page.screenshot({
			path: '../docs/artifacts/fix-1745-alarm-kanaele-premium-sms/ac-14-trip-haken-nach-reload-PASS.png',
			fullPage: true
		});

		// Gegenprobe am Server: der scharfe Kanalsatz des Trips trägt den Kanal.
		const getRes = await page.request.get(`/api/trips/${trip.id}`);
		expect(getRes.ok()).toBeTruthy();
		const gespeichert = (await getRes.json()) as { alert_channels?: Record<string, boolean> };
		expect(
			gespeichert.alert_channels?.premium_sms,
			'Server-Bestand ohne alert_channels.premium_sms — _effective_alert_channels() ' +
				'(trip_alert.py:1518-1525) würde den Kanal weiterhin nicht auflösen.'
		).toBe(true);

		expect(errors, `Konsolenfehler während AC-14-Lauf: ${JSON.stringify(errors)}`).toEqual([]);
	});

	// ── Mandantentrennung (Pflicht bei jedem datenbewegenden Endpoint) ───────
	test('Mandantentrennung: der Premium-SMS-Haken von Nutzer A ist für Nutzer B unsichtbar und unschreibbar', async ({
		page: pageA,
		browser
	}) => {
		const suffix = Date.now() + 3;
		let tripAId: string | null = null;
		let ctxB: Awaited<ReturnType<typeof browser.newContext>> | null = null;
		try {
			const today = new Date().toISOString().slice(0, 10);
			const tripA = await createTestTrip(pageA.request, {
				id: `e2e-1745a-mandant-${suffix}`,
				name: `1745A Mandant A ${suffix}`,
				stages: [
					{
						id: `s1745a-m-stage-${suffix}`,
						name: 'Etappe 1',
						date: today,
						waypoints: [
							{ id: `s1745a-m-wp1-${suffix}`, name: 'Start', lat: 46.6, lon: 12.9, elevation_m: 1400 }
						]
					}
				]
			});
			tripAId = tripA.id;

			const putA = await pageA.request.put(`/api/trips/${tripA.id}`, {
				data: { alert_channels: { email: true, telegram: false, sms: false, premium_sms: true } }
			});
			expect(putA.ok(), `Vorbereitungs-PUT (Nutzer A) fehlgeschlagen: ${putA.status()}`).toBeTruthy();

			ctxB = await browser.newContext({ storageState: undefined });
			const pageB = await ctxB.newPage();
			const userB = `e2e1745a${suffix}`;
			const reg = await pageB.request.post('/api/auth/register', {
				data: { username: userB, password: 'Test1234!x', email: `${userB}@example.com` }
			});
			expect([200, 201].includes(reg.status()), `Registrierung B fehlgeschlagen: ${reg.status()}`).toBeTruthy();
			const loginB = await pageB.request.post('/api/auth/login', {
				data: { username: userB, password: 'Test1234!x' }
			});
			expect(loginB.ok(), `Login B fehlgeschlagen: ${loginB.status()}`).toBeTruthy();

			// B sieht As Trip nicht.
			const getBOnA = await pageB.request.get(`/api/trips/${tripAId}`);
			expect(getBOnA.status(), 'Nutzer B darf den Trip von A nicht lesen können').toBe(404);

			// B kann As Kanal-Satz nicht überschreiben.
			const putBOnA = await pageB.request.put(`/api/trips/${tripAId}`, {
				data: { alert_channels: { email: true, telegram: true, sms: true, premium_sms: false } }
			});
			expect(putBOnA.status()).toBe(404);

			// As Bestand bleibt unverändert.
			const getA = await pageA.request.get(`/api/trips/${tripAId}`);
			expect(getA.ok()).toBeTruthy();
			expect(((await getA.json()) as { alert_channels?: Record<string, boolean> }).alert_channels?.premium_sms).toBe(
				true
			);
		} finally {
			if (tripAId) await pageA.request.delete(`/api/trips/${tripAId}`).catch(() => {});
			if (ctxB) await ctxB.close();
		}
	});
});
