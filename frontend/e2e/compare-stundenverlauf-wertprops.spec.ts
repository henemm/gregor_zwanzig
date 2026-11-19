// gz-eigenstaendig: Stundenverlauf-Steuerung existiert nur im Ortsvergleich (COMPARE_ONLY_SECTIONS in weatherMetricsTabSections.ts, #2346 S3: beim Trip ist die Mail-Haupttabelle selbst die Stundentabelle) -- kein Trip-Pendant moeglich
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
//
// #3154 (#3122 B3b, Spec feat_3122_was_steht_wo.md Teil B Nr. 13/14, AC-26/AC-29): die Stundenverlauf-Liste
// und ihr Ein/Aus-Schalter sind aus dem Uebergangsblock des Reiters Zustellung entfernt. Im Hub bedient sie
// allein die Karte „Was steht wo“ im Reiter Wetter: Spalte „Stundenverlauf“ (Haken je Metrik, gespeichert als
// `places.hourly` der Tabelle) und Schalter „Stundenverlauf“ unter der Tabelle (`hourly_enabled`). Dieselben
// Zusicherungen (waehlen/abwaehlen, Schalter, Neuladen, keine Fremdfelder) laufen dort.

import { test, expect, type Locator, type Page } from '@playwright/test';
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

const tabellenPfad = (id: string) => `/api/briefings/${id}/placements`;

/** Karte „Was steht wo“ im Reiter Wetter des Orte-Hubs. */
async function oeffneKarte(page: Page, id: string): Promise<Locator> {
	await page.goto(`/compare/${id}?tab=wetter`);
	await page.locator('[data-testid="compare-detail-tab-wetter"]:visible').click();
	const karte = page.locator('[data-testid="was-steht-wo"]:visible');
	await expect(karte.getByTestId('was-steht-wo-tabelle'), 'Die Tabelle muss im Reiter Wetter stehen').toBeVisible({ timeout: 20_000 });
	return karte;
}

const hourlyHaken = (karte: Locator, m: string) => karte.locator(`[data-slot="et-zeile"][data-metrik="${m}"] [data-slot="et-zelle"][data-stelle="hourly"] input[type="checkbox"]`);

/** Gespeicherter Stundenverlauf-Haken einer Metrik (null = Tabelle nicht gespeichert). */
async function hourlyGespeichert(page: Page, id: string, m: string): Promise<boolean | null> {
	const r = await page.request.get(`${tabellenPfad(id)}?kind=vergleich`);
	expect(r.ok()).toBeTruthy();
	const a = await r.json();
	if (!a.stored) return null;
	const row = (a.placements.rows as Array<{ metric_id: string; places?: Record<string, boolean> }>).find((x) => x.metric_id === m);
	return row?.places?.hourly !== false;
}

/** Die erste Metrik, deren Stundenverlauf-Haken bedienbar ist und den gesuchten Zustand hat.
 *  Bewusst zur Laufzeit ermittelt: Zeilen und Zellen kommen aus der Antwort des Endpoints. */
async function ersteZeile(karte: Locator, angehakt: boolean): Promise<string> {
	const zeilen = karte.locator('[data-slot="et-zeile"]');
	for (let i = 0; i < (await zeilen.count()); i++) {
		const m = (await zeilen.nth(i).getAttribute('data-metrik'))!;
		const kasten = hourlyHaken(karte, m);
		if (!(await kasten.count()) || (await kasten.isDisabled())) continue;
		if ((await kasten.isChecked()) === angehakt) return m;
	}
	throw new Error(`Messgrundlage weg: keine bedienbare Stundenverlauf-Zelle mit checked=${angehakt}.`);
}

/** Klick auf einen Haken und Warten auf den gespeicherten Stand der Tabelle. */
async function hakenUndSpeichern(page: Page, karte: Locator, id: string, m: string): Promise<void> {
	const put = page.waitForResponse((r) => r.request().method() === 'PUT' && new URL(r.url()).pathname === tabellenPfad(id), { timeout: 20_000 });
	await hourlyHaken(karte, m).click();
	expect((await put).status()).toBe(200);
}

test.describe('Ortsvergleich · Stundenverlauf in der Karte „Was steht wo“ (#2276 S6b, #3154)', () => {
	test('AC-2: eine Metrik abwaehlen wirkt und uebersteht das Neuladen', async ({ page }) => {
		const id = await legeVergleichAn(page);
		const karte = await oeffneKarte(page, id);
		await expect(page.locator('[data-testid="weather-metrics-stundenverlauf"]'), 'alte Liste doppelt').toHaveCount(0);

		const kennung = await ersteZeile(karte, true);
		await hakenUndSpeichern(page, karte, id, kennung);
		await expect(hourlyHaken(karte, kennung)).not.toBeChecked();
		expect(await hourlyGespeichert(page, id, kennung), `AC-2 FAIL: „${kennung}" wurde abgewaehlt, der Server hat es nicht uebernommen`).toBe(false);

		await page.reload();
		const nachReload = await oeffneKarte(page, id);
		await expect(hourlyHaken(nachReload, kennung), 'AC-2 FAIL: die abgewaehlte Metrik ist nach dem Neuladen wieder angehakt.').not.toBeChecked();
	});

	test('AC-2: eine Metrik anwaehlen wirkt und uebersteht das Neuladen', async ({ page }) => {
		const id = await legeVergleichAn(page);
		let karte = await oeffneKarte(page, id);
		// Ausgangslage: eine abgewaehlte Zeile (frisch angelegt ist jede angehakt).
		const kennung = await ersteZeile(karte, true);
		await hakenUndSpeichern(page, karte, id, kennung);
		await page.reload();
		karte = await oeffneKarte(page, id);
		await expect(hourlyHaken(karte, kennung)).not.toBeChecked();

		await hakenUndSpeichern(page, karte, id, kennung);
		await expect(hourlyHaken(karte, kennung)).toBeChecked();
		expect(await hourlyGespeichert(page, id, kennung), `AC-2 FAIL: „${kennung}" wurde angewaehlt, steht aber nicht im Stundenverlauf`).toBe(true);

		await page.reload();
		const nachReload = await oeffneKarte(page, id);
		await expect(hourlyHaken(nachReload, kennung), 'AC-2 FAIL: die angewaehlte Metrik ist nach dem Neuladen wieder leer.').toBeChecked();
	});

	test('AC-2: der Ein/Aus-Schalter ist da, wirkt und uebersteht das Neuladen', async ({ page }) => {
		const id = await legeVergleichAn(page);
		const karte = await oeffneKarte(page, id);

		const schalter = karte.getByTestId('was-steht-wo-stundenverlauf');
		await expect(schalter, 'AC-2 FAIL: der Ein/Aus-Schalter fehlt.').toBeVisible();
		await expect(schalter).toHaveAttribute('aria-checked', 'true');
		await schalter.click();

		await expect
			.poll(async () => (await serverStand(page, id)).hourly_enabled, {
				timeout: 15_000,
				message: 'AC-2/AC-4 FAIL: der ausgeschaltete Stundenverlauf ist nicht gespeichert worden.'
			})
			.toBe(false);

		await page.reload();
		const nachReload = await oeffneKarte(page, id);
		await expect(nachReload.getByTestId('was-steht-wo-stundenverlauf'), 'AC-2 FAIL: der Schalter steht nach dem Neuladen wieder auf „ein".').toHaveAttribute('aria-checked', 'false');
	});

	test('AC-4: die Stundenverlauf-Geste laesst die uebrigen Einstellungen unangetastet', async ({ page }) => {
		const id = await legeVergleichAn(page);
		const vorher = await serverStand(page, id);
		const karte = await oeffneKarte(page, id);

		await hakenUndSpeichern(page, karte, id, await ersteZeile(karte, true));

		const nachher = await serverStand(page, id);
		expect(nachher.empfaenger, 'AC-4 FAIL: die Empfaenger haben sich veraendert.').toEqual(vorher.empfaenger);
		expect(nachher.location_ids, 'AC-4 FAIL: die Orte haben sich veraendert.').toEqual(vorher.location_ids);
		expect(nachher.hourly_enabled, 'AC-4 FAIL: der Stundenverlauf-Schalter wurde mitgeschrieben.').toBe(true);
		expect(dc(nachher).telegram_style, 'AC-4 FAIL: eine fremde Anzeige-Einstellung wurde mitgeschrieben.').toBe('kurzform');
	});
});
