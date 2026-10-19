// E2E — Issue #2361 Fix-Loop 2 (F-R2-2): die Langlaeufer-Budgets wirken an
// der AUFRUFSTELLE, nicht nur in api.ts.
//
// Spec: docs/specs/modules/fix_2361_abruf_zeitlimit.md (AC-3)
// Workflow: fix-2361-abruf-zeitlimit
//
// Jeder Abruf ueber `send()` bekommt ein Standard-Zeitlimit von 25 s. Fuenf
// bewusst lange Aktionen tragen ein eigenes, groesseres Budget:
//   Compare-Vorschau 70 s · Test-Versand (Konto) 130 s · Alarm-Vorschau 40 s ·
//   Orts-Aufloesung im Vergleichs-Editor 40 s · Orts-Aufloesung „Neuer Ort" 40 s.
//
// Messweg je Aufrufstelle (echter Klickpfad, Uhr der Seite gestellt):
//   1. `page.clock.install()` vor dem Laden der Seite.
//   2. `page.route` haelt den Langlaeufer-Abruf fest (Antwort bleibt aus).
//   3. Aktion ausloesen, warten bis der Abruf unterwegs ist.
//   4. Uhr 26 s vorspulen — ueber das 25-s-Standard-Limit hinaus.
//   5. Zusicherung: der Abruf ist NICHT abgebrochen, die Aktion laeuft noch,
//      keine Offline-Sperre, kein Fehlertext.
//   6. Antwort freigeben ⇒ das Ergebnis erscheint.
// Faellt das Budget an der Aufrufstelle weg, feuert bei 26 s das Standard-
// Limit: der Abruf bricht ab, die Seite meldet „offline" — Schritt 5 wird rot.
//
// Der festgehaltene Abruf erreicht den Server nie: es wird nichts versandt
// und nichts aufgeloest (kein externer Dienst).
//
// Issue #2283 (docs/specs/modules/shared_preview_tab.md, AC-9): migriert auf den
// geteilten Vorschau-Reiter — Abruf GET /api/briefings/{id}/preview?kind=vergleich,
// gezaehlt wird jeder Aufruf daran (kein Laden vor dem Oeffnen, genau einer
// trotz Kanal-/Ansichtswechsel). Alarm-Vorschau auf
// POST /api/briefings/{id}/alert-preview?kind=route (AC-20/AC-21).

import { test, expect, type Page, type Route, type Request } from '@playwright/test';
import { createTestComparePreset, createTestLocation, cleanupTracked, login, registerForCleanup } from './helpers.js';

/** Haelt jeden Abruf auf `pfad` fest, bis `freigeben()` die Antwort liefert. */
async function halteAbrufFest(page: Page, pfad: RegExp, antwort: unknown) {
	const festgehalten: Route[] = [];
	const abgebrochen: Request[] = [];
	await page.route(pfad, (route) => {
		festgehalten.push(route);
	});
	page.on('requestfailed', (req) => {
		if (pfad.test(req.url())) abgebrochen.push(req);
	});
	return {
		abgebrochen,
		unterwegs: () => festgehalten.length,
		freigeben: async () => {
			for (const route of festgehalten.splice(0)) {
				// Ein bereits vom Browser abgebrochener Abruf laesst sich nicht
				// mehr beantworten — das ist dann der Befund, kein Testfehler.
				await route.fulfill({ status: 200, json: antwort }).catch(() => {});
			}
		}
	};
}

/** Uhr ueber das 25-s-Standard-Limit vorspulen und den Laufzustand pruefen. */
async function nachStandardLimitLaeuftNoch(
	page: Page,
	abruf: Awaited<ReturnType<typeof halteAbrufFest>>
): Promise<void> {
	await expect
		.poll(() => abruf.unterwegs(), { message: 'der Langlaeufer-Abruf muss unterwegs sein' })
		.toBeGreaterThan(0);
	await page.clock.fastForward(26_000);
	// Dem Seiten-Code Gelegenheit geben, auf einen etwaigen Abbruch zu reagieren.
	await page.evaluate(() => new Promise((r) => setTimeout(r, 0)));
	await expect(page.getByTestId('offline-sperre-hinweis')).toHaveCount(0);
	expect(
		abruf.abgebrochen,
		'der Abruf wurde nach 26 s abgebrochen — das eigene Budget fehlt an der Aufrufstelle'
	).toHaveLength(0);
}

test.describe('#2361 Langlaeufer-Budgets wirken an der Aufrufstelle', () => {
	test.afterEach(async ({ page }) => {
		await page.unrouteAll({ behavior: 'ignoreErrors' });
		await cleanupTracked(page.request);
	});

	test('Compare-Vorschau (70 s): laeuft nach 26 s noch und zeigt danach die Vorschau', async ({ page }, testInfo) => {
		await login(page);
		const a = await createTestLocation(page.request, { name: `Budget-Ort-A-${Date.now()}`, lat: 47.5, lon: 10.3 });
		const b = await createTestLocation(page.request, { name: `Budget-Ort-B-${Date.now()}`, lat: 47.55, lon: 10.35 });
		const preset = await createTestComparePreset(page.request, { locationIds: [a.id, b.id] });

		await page.clock.install();
		// Issue #2283 (AC-9/AC-15): der geteilte Vorschau-Reiter holt ueber
		// GET /api/briefings/{id}/preview?kind=vergleich (Buendel-Antwortform).
		const abruf = await halteAbrufFest(page, /\/api\/briefings\/[^/?]+\/preview\?kind=vergleich/, {
			subject: 'Budget-Betreff',
			email_html: '<html><body><p>Budget-Vorschau angekommen</p></body></html>',
			sms: { text: 'Budget-SMS', char_count: 10 },
			telegram: { body: 'Budget-Telegram' }
		});
		// AC-9: kein Abruf vor dem Oeffnen des Reiters (Hub zuerst auf der Uebersicht)
		await page.goto(`/compare/${preset.id}`);
		// erst nach der Hydration messen — sonst entginge ein Eager-Load beim Hub-Mount
		await expect(page.locator('[data-testid="compare-detail-panel-uebersicht"]:visible')).toBeVisible({
			timeout: 10_000
		});
		await page.evaluate(() => new Promise((r) => setTimeout(r, 0)));
		expect(abruf.unterwegs(), 'die Vorschau wurde schon beim Oeffnen des Hubs geladen').toBe(0);
		await page.locator('[data-testid="compare-detail-tab-vorschau"]:visible').click();
		const panel = page.locator('[data-testid="compare-detail-panel-vorschau"]:visible');
		await expect(panel).toBeVisible({ timeout: 10_000 });

		await nachStandardLimitLaeuftNoch(page, abruf);
		await expect(panel.getByTestId('preview-loading')).toBeVisible();
		await expect(panel.getByTestId('preview-error')).toHaveCount(0);
		await page.screenshot({ path: testInfo.outputPath('laeuft-noch-bei-26s.png'), fullPage: true });

		await abruf.freigeben();
		await expect(panel.getByTestId('email-iframe')).toBeVisible({ timeout: 10_000 });
		await expect(panel.getByTestId('preview-loading')).toHaveCount(0);

		// AC-9: Kanal- und Ansichtswechsel laden nicht neu — genau EIN Abruf.
		await panel.getByRole('button', { name: /^SMS/ }).click();
		await expect(panel.getByTestId('sms-token-bubble')).toHaveText('Budget-SMS');
		await panel.getByRole('button', { name: /^Telegram/ }).click();
		await expect(panel.getByTestId('preview-telegram')).toContainText('Budget-Telegram');
		await panel.getByRole('button', { name: /^(E-Mail|Email)/ }).click();
		await panel.getByTestId('preview-email-view-mobile').click();
		await panel.getByTestId('preview-email-view-desktop').click();
		await page.evaluate(() => new Promise((r) => setTimeout(r, 0)));
		expect(abruf.unterwegs(), 'Kanal-/Ansichtswechsel hat die Vorschau erneut abgerufen').toBe(1);
	});

	test('Test-Versand im Konto (130 s): laeuft nach 26 s noch und meldet danach „Gesendet"', async ({ page }) => {
		await login(page);
		await page.clock.install();
		const abruf = await halteAbrufFest(page, /\/api\/notify\/test$/, { status: 'ok', channel: 'email' });
		await page.goto('/account');
		await page.locator('#mailTo').fill('budget-test@example.com');
		await page.getByRole('button', { name: 'Test senden' }).first().click();

		await nachStandardLimitLaeuftNoch(page, abruf);
		await expect(page.getByText('Senden fehlgeschlagen')).toHaveCount(0);
		await expect(page.getByRole('button', { name: '...' }).first()).toBeDisabled();

		await abruf.freigeben();
		await expect(page.getByText('Gesendet', { exact: true })).toBeVisible({ timeout: 10_000 });
	});

	test('Alarm-Vorschau (40 s): laeuft nach 26 s noch und zeigt danach den Betreff', async ({ page }) => {
		await login(page);
		const tripId = `e2e-gz-2361-alarm-${Date.now()}`;
		const res = await page.request.post('/api/trips', {
			data: {
				id: tripId,
				name: 'E2E-GZ-2361 Alarm-Vorschau',
				stages: [
					{
						id: `${tripId}-s1`,
						name: 'Etappe 1',
						date: '2026-08-01',
						waypoints: [{ id: `${tripId}-wp1`, name: 'Start', lat: 42.1, lon: 9.0, elevation_m: 500 }]
					}
				],
				// Alarm-Regeln leitet der Server aus den aktiven Wetter-Metriken ab
				// (SyncAlertRules) — ohne aktive Boeen-Metrik bliebe die Vorschau gesperrt.
				display_config: { metrics: [{ metric_id: 'gust', enabled: true }] },
				alert_rules: [
					{ id: 'r1', kind: 'absolute', metric: 'wind_gust', threshold: 50, severity: 'warning', enabled: true }
				]
			}
		});
		expect([200, 201]).toContain(res.status());
		registerForCleanup('trip', tripId);

		await page.clock.install();
		// Issue #2283 (AC-20/AC-21): kind-neutraler Weg POST /api/briefings/{id}/alert-preview?kind=route.
		const abruf = await halteAbrufFest(page, new RegExp(`/api/briefings/${tripId}/alert-preview\\?kind=route$`), {
			subject: 'Budget-Alarm-Betreff',
			email_html: '<html><body>Alarm</body></html>',
			email_plain: 'Alarm',
			telegram: 'Alarm',
			sms: 'Alarm'
		});
		await page.goto(`/trips/${tripId}`);
		await page.getByTestId('trip-detail-tab-alarme').first().click();
		const panel = page.getByTestId('trip-detail-panel-alarme');
		await expect(panel).toBeVisible();
		const knopf = panel.getByTestId('alert-preview-load-btn');
		await knopf.click();

		await nachStandardLimitLaeuftNoch(page, abruf);
		await expect(knopf).toHaveText('Lade…');
		await expect(panel.getByTestId('alert-preview-error')).toHaveCount(0);

		await abruf.freigeben();
		await expect(panel.getByTestId('alert-preview-subject')).toHaveText('Budget-Alarm-Betreff', { timeout: 10_000 });
	});

	test('Orts-Aufloesung im Vergleichs-Editor (40 s): laeuft nach 26 s noch und zeigt danach den Treffer', async ({ page }) => {
		await login(page);
		await page.clock.install();
		const abruf = await halteAbrufFest(page, /\/api\/locations\/resolve$/, {
			lat: 47.2692,
			lon: 11.4041,
			timezone: 'Europe/Vienna',
			suggested_name: 'Budget-Treffer',
			source_type: 'decimal'
		});
		await page.goto('/compare/new');
		await page.locator('[data-testid="compare-editor-name"]:visible').fill(`E2E-GZ-2361 Budget ${Date.now()}`);
		await page.locator('[data-testid="compare-editor-continue-orte"]:visible').click();
		await page.locator('[data-testid="compare-step2-smart-import-input"]:visible').fill('47.2692, 11.4041');
		const knopf = page.locator('[data-testid="compare-step2-resolve-btn"]:visible');
		await knopf.click();

		await nachStandardLimitLaeuftNoch(page, abruf);
		await expect(knopf).toHaveText('…');
		await expect(page.getByText('Format nicht erkannt')).toHaveCount(0);

		await abruf.freigeben();
		await expect(page.locator('[data-testid="compare-step2-name-input"]:visible')).toHaveValue('Budget-Treffer', {
			timeout: 10_000
		});
	});

	test('Orts-Aufloesung „Neuer Ort" (40 s): laeuft nach 26 s noch und zeigt danach den Treffer', async ({ page }) => {
		await login(page);
		await page.clock.install();
		const abruf = await halteAbrufFest(page, /\/api\/locations\/resolve$/, {
			lat: 47.0789,
			lon: 11.6856,
			timezone: 'Europe/Vienna',
			suggested_name: 'Budget-Ort-Neu',
			source_type: 'decimal'
		});
		await page.goto('/locations');
		await page.getByRole('button', { name: 'Neuer Ort' }).first().click();
		const eingabe = page.getByPlaceholder('Komoot-Link, Google-Maps-URL oder Koordinaten…');
		await eingabe.fill('47.0789, 11.6856');
		await eingabe.press('Enter');

		await nachStandardLimitLaeuftNoch(page, abruf);
		await expect(page.getByText('erkannt · decimal')).toHaveCount(0);

		await abruf.freigeben();
		await expect(page.getByText('erkannt · decimal')).toBeVisible({ timeout: 10_000 });
	});
});
