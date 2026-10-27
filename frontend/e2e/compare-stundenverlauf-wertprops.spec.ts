// E2E — Issue #2276 Scheibe S6b (Epic #2345): die Stundenverlauf-Bedienflaeche
// des Ortsvergleichs arbeitet auf reinen WERTPROPS + Rueckrufen statt auf dem
// Zustandsobjekt `wiz`. Nachweis am Wirkort: Browser.
//
// Spec: docs/specs/modules/rework_2276_s6b_wetter_metriken.md
//   AC-2  Verhaltensgleichheit — Metrik waehlen/abwaehlen, Ein/Aus-Schalter,
//         Auswahl uebersteht Speichern und Neuladen
//   AC-4  der verkuerzte Guard (`WeatherMetricsTab.svelte:1273`) laesst den
//         Speicherpfad unveraendert wirken
//
// 🔴 CHARAKTERISIERUNG, nicht RED. Eine Umstellung auf Wertprops darf das
// sichtbare Verhalten NICHT aendern — dieser Test ist deshalb schon vor der
// Implementierung gruen und muss es danach bleiben. Sein Wert liegt in den
// Mutations-Gegenproben der Spec:
//   * `onMetricKeys` am Mount weglassen  -> „Metrik abwaehlen" wirkt nicht  -> rot
//   * `onEnabledChange` am Mount weglassen -> der Schalter fehlt im DOM      -> rot
//   * `:1273` zu `if (false) return;`     -> es wird nie gespeichert         -> rot
// KEIN Kern-Test faengt diese drei: die Kernsuite ist SSR-only
// (`generate: 'server'`, kein DOM), `$effect` und Ereignisse laufen dort nie.
// Die Modul-/Verdrahtungs-Zusicherungen stehen in
// src/lib/components/shared/__tests__/compare_stundenverlauf_wertprops.test.ts.
//
// Laeuft im isolierten CI-Stack (frontend/e2e/ci-stack.sh), Anmeldung ueber den
// gespeicherten storageState aus global.setup.ts. Presets tragen das Praefix
// E2E-GZ-, damit global.teardown.ts Reste raeumt; afterEach loescht sie direkt.
// Die Aufnahme in .github/ci_e2e_specs.txt macht die Implementierung — sie
// setzt einen frischen Filter-B-Beleg (3x gruen im Zielverbund) voraus.

import { test, expect, type Page } from '@playwright/test';
import { E2E_TEST_PREFIX } from './helpers';

let angelegt: string[] = [];

test.afterEach(async ({ page }) => {
	for (const id of angelegt) {
		try {
			await page.request.delete(`/api/compare/presets/${id}`);
		} catch {
			/* Aufraeumen ist nicht testkritisch */
		}
	}
	angelegt = [];
});

async function legeVergleichAn(page: Page): Promise<string> {
	const res = await page.request.post('/api/compare/presets', {
		data: {
			name: `${E2E_TEST_PREFIX}Stundenverlauf Wertprops ${Date.now()}`,
			// Seed-Orte aus global.setup.ts.
			location_ids: ['e2e-loc-innsbruck', 'e2e-loc-stubai'],
			schedule: 'daily',
			profil: 'wandern',
			hour_from: 7,
			hour_to: 16,
			empfaenger: ['stundenverlauf-wertprops@example.com'],
			hourly_enabled: true,
			display_config: { telegram_style: 'kurzform' }
		}
	});
	expect(res.ok(), 'Vergleich-Anlage fehlgeschlagen: ' + res.status()).toBeTruthy();
	const body = await res.json();
	angelegt.push(body.id);
	return body.id as string;
}

async function serverStand(page: Page, id: string): Promise<Record<string, unknown>> {
	const res = await page.request.get(`/api/compare/presets/${id}`);
	expect(res.ok()).toBeTruthy();
	return res.json();
}

const dc = (body: Record<string, unknown>) => (body.display_config as Record<string, unknown>) ?? {};

async function oeffneStundenverlauf(page: Page, id: string) {
	await page.goto(`/compare/${id}?tab=wetter-metriken`);
	await page.waitForLoadState('networkidle');
	await page.locator('[data-testid="compare-detail-tab-wetter-metriken"]:visible').click();
	const block = page.locator('[data-testid="weather-metrics-stundenverlauf"]:visible');
	await expect(block, 'Der Stundenverlauf-Block muss im Reiter stehen').toBeVisible({
		timeout: 10_000
	});
	await expect(block.locator('[data-testid^="compare-layout-hourly-metric-"]').first()).toBeVisible({
		timeout: 10_000
	});
	return block;
}

/** Die Kennung der ersten anwaehlbaren Zeile mit dem gesuchten Zustand.
 *  Bewusst zur Laufzeit ermittelt statt hartkodiert: die Vorgabemenge kommt
 *  aus der Katalogantwort, nicht aus einer Frontend-Liste. */
async function ersteZeile(block: ReturnType<Page['locator']>, angehakt: boolean): Promise<string> {
	const zeilen = block.locator('[data-testid^="compare-layout-hourly-metric-"]');
	const anzahl = await zeilen.count();
	for (let i = 0; i < anzahl; i++) {
		const zeile = zeilen.nth(i);
		const kasten = zeile.locator('input[type="checkbox"]');
		if (await kasten.isDisabled()) continue;
		if ((await kasten.isChecked()) !== angehakt) continue;
		const testid = await zeile.getAttribute('data-testid');
		return String(testid).replace('compare-layout-hourly-metric-', '');
	}
	throw new Error(
		`Messgrundlage weg: keine anwaehlbare Stundenverlauf-Zeile mit checked=${angehakt}.`
	);
}

test.describe('Ortsvergleich · Stundenverlauf auf Wertprops (#2276 S6b)', () => {
	test('AC-2: eine Metrik abwaehlen wirkt und uebersteht das Neuladen', async ({ page }) => {
		const id = await legeVergleichAn(page);
		const block = await oeffneStundenverlauf(page, id);

		const kennung = await ersteZeile(block, true);
		const kasten = block.locator(
			`[data-testid="compare-layout-hourly-metric-${kennung}"] input[type="checkbox"]`
		);
		await kasten.uncheck();
		await expect(kasten).not.toBeChecked();

		await expect
			.poll(
				async () => {
					const gespeichert = (dc(await serverStand(page, id)).hourly_metrics ??
						null) as string[] | null;
					return gespeichert === null ? 'nichts gespeichert' : gespeichert.includes(kennung);
				},
				{
					timeout: 15_000,
					message:
						`AC-2/AC-4 FAIL: „${kennung}" wurde abgewaehlt, aber der Server hat die ` +
						`Auswahl nicht (oder falsch) uebernommen. Fehlt der Rueckruf am Mount, ` +
						`bleibt die Geste wirkungslos; ist der Guard verfaelscht, wird nie gespeichert.`
				}
			)
			.toBe(false);

		await page.reload();
		await page.waitForLoadState('networkidle');
		const nachReload = await oeffneStundenverlauf(page, id);
		await expect(
			nachReload.locator(
				`[data-testid="compare-layout-hourly-metric-${kennung}"] input[type="checkbox"]`
			),
			'AC-2 FAIL: die abgewaehlte Metrik ist nach dem Neuladen wieder angehakt.'
		).not.toBeChecked();
	});

	test('AC-2: eine Metrik anwaehlen wirkt und uebersteht das Neuladen', async ({ page }) => {
		const id = await legeVergleichAn(page);
		const block = await oeffneStundenverlauf(page, id);

		const kennung = await ersteZeile(block, false);
		const kasten = block.locator(
			`[data-testid="compare-layout-hourly-metric-${kennung}"] input[type="checkbox"]`
		);
		await kasten.check();
		await expect(kasten).toBeChecked();

		await expect
			.poll(
				async () =>
					((dc(await serverStand(page, id)).hourly_metrics ?? []) as string[]).includes(kennung),
				{
					timeout: 15_000,
					message:
						`AC-2/AC-4 FAIL: „${kennung}" wurde angewaehlt, steht aber nicht in ` +
						`display_config.hourly_metrics.`
				}
			)
			.toBe(true);

		const nachReload = await (async () => {
			await page.reload();
			await page.waitForLoadState('networkidle');
			return oeffneStundenverlauf(page, id);
		})();
		await expect(
			nachReload.locator(
				`[data-testid="compare-layout-hourly-metric-${kennung}"] input[type="checkbox"]`
			),
			'AC-2 FAIL: die angewaehlte Metrik ist nach dem Neuladen wieder leer.'
		).toBeChecked();
	});

	test('AC-2: der Ein/Aus-Schalter ist da, wirkt und uebersteht das Neuladen', async ({ page }) => {
		const id = await legeVergleichAn(page);
		const block = await oeffneStundenverlauf(page, id);

		const schalter = block.locator('[data-testid="compare-layout-hourly-enabled-toggle"]');
		await expect(
			schalter,
			'AC-2 FAIL: der Ein/Aus-Schalter fehlt. Ohne `onEnabledChange` am Mount wird er ' +
				'gar nicht erst gerendert.'
		).toBeVisible();

		const kasten = schalter.locator('input[type="checkbox"]');
		await expect(kasten).toBeChecked();
		await kasten.uncheck();

		await expect
			.poll(async () => (await serverStand(page, id)).hourly_enabled, {
				timeout: 15_000,
				message:
					'AC-2/AC-4 FAIL: der ausgeschaltete Stundenverlauf ist nicht gespeichert worden.'
			})
			.toBe(false);

		await page.reload();
		await page.waitForLoadState('networkidle');
		const nachReload = await oeffneStundenverlauf(page, id);
		await expect(
			nachReload.locator(
				'[data-testid="compare-layout-hourly-enabled-toggle"] input[type="checkbox"]'
			),
			'AC-2 FAIL: der Schalter steht nach dem Neuladen wieder auf „ein".'
		).not.toBeChecked();
	});

	test('AC-4: die Stundenverlauf-Geste laesst die uebrigen Einstellungen unangetastet', async ({
		page
	}) => {
		const id = await legeVergleichAn(page);
		const vorher = await serverStand(page, id);
		const block = await oeffneStundenverlauf(page, id);

		const kennung = await ersteZeile(block, true);
		await block
			.locator(`[data-testid="compare-layout-hourly-metric-${kennung}"] input[type="checkbox"]`)
			.uncheck();

		await expect
			.poll(
				async () => (dc(await serverStand(page, id)).hourly_metrics ?? null) !== null,
				{ timeout: 15_000, message: 'AC-4 FAIL: es wurde ueberhaupt nichts gespeichert.' }
			)
			.toBe(true);

		const nachher = await serverStand(page, id);
		expect(nachher.empfaenger, 'AC-4 FAIL: die Empfaenger haben sich veraendert.').toEqual(
			vorher.empfaenger
		);
		expect(nachher.location_ids, 'AC-4 FAIL: die Orte haben sich veraendert.').toEqual(
			vorher.location_ids
		);
		expect(
			dc(nachher).telegram_style,
			'AC-4 FAIL: eine fremde Anzeige-Einstellung wurde mitgeschrieben.'
		).toBe('kurzform');
	});
});
