// E2E — Issue #2361 Fix-Loop 2 (F-R2-2): die Langlaeufer-Budgets wirken an
// der AUFRUFSTELLE, nicht nur in api.ts.
//
// Spec: docs/specs/modules/fix_2361_abruf_zeitlimit.md (AC-3)
// Workflow: fix-2361-abruf-zeitlimit
//
// Jeder Abruf ueber `send()` bekommt ein Standard-Zeitlimit von 25 s. Vier
// bewusst lange Aktionen tragen ein eigenes, groesseres Budget:
//   Test-Versand (Konto) 130 s · (Alarm-Vorschau 40 s: entfallen mit #3458) ·
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
// Issue #1743 (docs/specs/modules/feat_1743_reiter_aufraeumen.md): der Reiter
// „Vorschau" und GET /api/briefings/{id}/preview sind entfernt — der Fall
// „Compare-Vorschau (70 s)" hat keine Aufrufstelle mehr und ist entfallen.
// Issue #3458: die Alarm-Vorschau-Oberflaeche ist entfernt — der Fall
// „Alarm-Vorschau (40 s)" hat keine Aufrufstelle mehr und ist entfallen.

import { test, expect, type Page, type Route, type Request } from '@playwright/test';
import { cleanupTracked, login, registerForCleanup } from './helpers.js';

/** Haelt jeden Abruf auf `pfad` fest, bis `freigeben()` die Antwort liefert. */
async function halteAbrufFest(page: Page, pfad: RegExp, antwort: unknown) {
	const festgehalten: Route[] = [];
	const abgebrochen: Request[] = [];
	// Gesamtzahl aller Abrufe — anders als `festgehalten` nie geleert, damit
	// ein Neuabruf auch NACH `freigeben()` noch zaehlbar bleibt.
	let gesamt = 0;
	await page.route(pfad, (route) => {
		gesamt += 1;
		festgehalten.push(route);
	});
	page.on('requestfailed', (req) => {
		if (pfad.test(req.url())) abgebrochen.push(req);
	});
	return {
		abgebrochen,
		unterwegs: () => festgehalten.length,
		aufrufe: () => gesamt,
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

	// #3458: Fall „Alarm-Vorschau (40 s)“ entfaellt — das Zeitbudget war nur ueber den Knopf
	// „Vorschau laden“ erreichbar, der mit der Vorschau-Karte entfernt ist.

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
