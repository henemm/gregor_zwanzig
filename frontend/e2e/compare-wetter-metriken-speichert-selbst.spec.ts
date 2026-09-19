// E2E — Issue #2276 Scheibe S4 (Epic #2345): der Reiter „Wetter-Metriken" im
// Ortsvergleich-Hub bedient ZWEI fachlich unabhängige Datendomänen (Metrik-
// auswahl/Kanäle/Amtliche-Warnungen/Tagesfenster UND Stundenverlauf/Ausblick)
// über GENAU EINE kombinierte Orchestrierung — ohne die zwei historischen
// Wrapper-Divs (`.hub-wetter-metriken-wrap`/`.hub-layout-hourly-wrap`) und
// ohne zwei getrennte Commit-Funktionen. Nachweis am Wirkort.
//
// Spec: docs/specs/modules/rework_2276_s4_wetter_metriken.md
//   AC-1 (ein PUT statt bis zu zwei), AC-2 (Intra-Gesture-Kollision — beide
//   Domänen überleben eine gemeinsame Geste), AC-5 (drei bisher stille
//   Gesten bleiben wirksam), AC-6 (Reiterwechsel verliert nichts),
//   AC-7 (412 → „Nochmal speichern"), AC-12 (übrige Einstellungen bleiben)
//
// Warum E2E: die Frontend-Unit-Harness ist SSR-only (node --test +
// svelte/server), `$effect`/Ereignisse laufen dort nie. Die Verdrahtung — der
// reaktive `$effect` in WeatherMetricsTab.svelte, neue Props am Mount in
// CompareTabs.svelte, die zusammengeführte Hydration, der generische
// Flush-Guard in handleValueChange, Flush vor handleToggleActive, Wegfall
// der zwei Wrapper-Divs — ist nur im echten Browser messbar. Die
// Modul-Zusicherungen stehen in
// src/lib/components/shared/weather-metrics-tab/__tests__/wetter_metriken_*.test.ts.
//
// #2375: der erste PUT nach SSR-Laden geht ohne If-Match durch — für den
// 412-Fall (AC-7) speichert dieser Test deshalb ZUERST selbst, bevor er den
// Konflikt provoziert (Muster compare-wertebereiche-speichert-selbst.spec.ts).
//
// Läuft im isolierten CI-Stack (frontend/e2e/ci-stack.sh), Anmeldung über den
// gespeicherten storageState aus global.setup.ts. Presets tragen das Präfix
// E2E-GZ-, damit global.teardown.ts Reste räumt; afterEach löscht sie direkt.
// Aufnahme in .github/ci_e2e_specs.txt macht die Implementierung.

import { test, expect, type Page, type Request } from '@playwright/test';
import { E2E_TEST_PREFIX } from './helpers';

let angelegt: string[] = [];

test.afterEach(async ({ page }) => {
	for (const id of angelegt) {
		try {
			await page.request.delete(`/api/compare/presets/${id}`);
		} catch {
			/* Aufräumen ist nicht testkritisch */
		}
	}
	angelegt = [];
});

async function legeVergleichAn(page: Page): Promise<string> {
	const res = await page.request.post('/api/compare/presets', {
		data: {
			name: `${E2E_TEST_PREFIX}Wetter-Metriken speichert selbst ${Date.now()}`,
			// Seed-Orte aus global.setup.ts — mit Orten ist der Vergleich „aktiv",
			// der Kebab bietet dann „Pausieren" an.
			location_ids: ['e2e-loc-innsbruck', 'e2e-loc-stubai'],
			schedule: 'daily',
			profil: 'wandern',
			hour_from: 7,
			hour_to: 16,
			empfaenger: ['wetter-metriken-selbst@example.com'],
			official_alerts_enabled: true,
			radar_alert_enabled: false,
			send_telegram: true,
			send_sms: false,
			alert_cooldown_minutes: 45,
			hourly_enabled: true,
			outlook_enabled: true,
			day_window_start_hour: 4,
			day_window_end_hour: 19,
			corridors: [{ metric: 'snow_depth_cm', range: [30, 200], notify: false, mark: true }],
			display_config: {
				ideal_ranges: { snow_depth_cm: { min: 30, max: 200 } },
				active_metrics: ['snow_depth_cm'],
				hourly_metrics: ['snow_depth_cm'],
				outlook_metrics: ['snow_depth_cm'],
				telegram_style: 'kurzform'
			}
		}
	});
	expect(res.ok(), 'Vergleich-Anlage fehlgeschlagen: ' + res.status()).toBeTruthy();
	const body = await res.json();
	angelegt.push(body.id);
	return body.id as string;
}

/** Zählt die PUTs auf genau diesen Vergleich (Request = abgeschickter Rumpf). */
function zaehlePuts(page: Page, id: string): { puts: Request[]; beantwortet: Request[] } {
	const pfad = `/api/compare/presets/${id}`;
	const puts: Request[] = [];
	const beantwortet: Request[] = [];
	const trifft = (r: Request) => r.method() === 'PUT' && new URL(r.url()).pathname === pfad;
	page.on('request', (r) => {
		if (trifft(r)) puts.push(r);
	});
	page.on('requestfinished', (r) => {
		if (trifft(r)) beantwortet.push(r);
	});
	return { puts, beantwortet };
}

async function oeffneWetterMetriken(page: Page, id: string) {
	await page.goto(`/compare/${id}?tab=wetter-metriken`);
	await page.waitForLoadState('networkidle');
	await page.locator('[data-testid="compare-detail-tab-wetter-metriken"]:visible').click();
	const tab = page.locator('[data-testid="weather-metrics-tab-vergleich"]:visible');
	await expect(tab).toBeVisible({ timeout: 10_000 });
	await expect(tab.locator('[data-testid="weather-metrics-vergleich-row-snow_depth_cm"]')).toBeVisible({
		timeout: 10_000
	});
	return tab;
}

async function serverStand(page: Page, id: string): Promise<Record<string, unknown>> {
	const res = await page.request.get(`/api/compare/presets/${id}`);
	expect(res.ok()).toBeTruthy();
	return res.json();
}

const anzeige = (page: Page) => page.locator('[data-testid="save-indicator"]');
const dc = (body: Record<string, unknown>) => (body.display_config as Record<string, unknown>) ?? {};

test.describe('Issue #2276 S4: Reiter „Wetter-Metriken" im Vergleich speichert über genau EINE kombinierte Orchestrierung', () => {
	test.beforeEach(async ({ page }) => {
		await page.setViewportSize({ width: 1280, height: 900 });
	});

	// AC-1 — fängt: zwei Wrapper-Divs wieder aktiv (Doppel-Commit) ⇒ zwei PUTs
	// statt einem.
	test('AC-1: eine Metrik-Checkbox umschalten → genau EIN PUT, danach „Gespeichert"', async ({ page }) => {
		const id = await legeVergleichAn(page);
		const { puts, beantwortet } = zaehlePuts(page, id);
		const tab = await oeffneWetterMetriken(page, id);
		expect(puts.length, 'Vorbedingung: das Öffnen des Reiters speichert nichts').toBe(0);

		await tab
			.locator('[data-testid="weather-metrics-vergleich-row-snow_depth_cm"] input[type="checkbox"]')
			.click();

		await expect.poll(() => beantwortet.length, { timeout: 10_000 }).toBeGreaterThanOrEqual(1);
		await expect(anzeige(page)).toHaveAttribute('data-state', 'idle', { timeout: 10_000 });
		await expect(anzeige(page)).toContainText('Gespeichert');
		// kurze Nachfrist: ein zweiter, verspäteter PUT (Layout-Domäne nachgezogen) wäre jetzt sichtbar
		await page.waitForTimeout(1_200);

		expect(puts.length, 'genau EIN PUT für eine Geste — historisch bis zu zwei (Wetter-Metriken + Layout)').toBe(1);
	});

	// AC-2 — fängt: die kombinierte Orchestrierung wieder in zwei getrennte
	// schedule()-Aufrufe aufgeteilt ⇒ die zuerst geplante Änderung geht
	// verloren (Einzel-Slot-Überschreibung), ODER es entstehen zwei PUTs.
	test('AC-2: Metrikauswahl UND Stundenverlauf-Schalter im selben Entprell-Fenster → EIN PUT trägt BEIDE Änderungen', async ({
		page
	}) => {
		const id = await legeVergleichAn(page);
		const { puts, beantwortet } = zaehlePuts(page, id);
		const tab = await oeffneWetterMetriken(page, id);

		// Domäne A: Metrikauswahl (Wetter-Metriken)
		await tab
			.locator('[data-testid="weather-metrics-vergleich-row-snow_depth_cm"] input[type="checkbox"]')
			.click();
		// Domäne B: Stundenverlauf-Schalter (Layout) — im selben Entprell-Fenster, ohne await auf Speichern
		await tab.locator('[data-testid="compare-layout-hourly-enabled-toggle"]').click();

		await expect.poll(() => beantwortet.length, { timeout: 10_000 }).toBeGreaterThanOrEqual(1);
		await expect(anzeige(page)).toHaveAttribute('data-state', 'idle', { timeout: 10_000 });
		await page.waitForTimeout(1_200);

		expect(puts.length, 'eine Geste im gemeinsamen Reiter darf nur EINEN PUT auslösen').toBe(1);
		const stand = await serverStand(page, id);
		expect(
			(dc(stand).active_metrics as string[]).includes('snow_depth_cm'),
			'die Metrikauswahl-Änderung darf vom Layout-Bubble nicht überschrieben werden'
		).toBe(false); // snow_depth_cm war aktiv → Checkbox-Klick entfernt sie
		expect(stand.hourly_enabled, 'die Stundenverlauf-Schalter-Änderung muss im selben PUT stehen').toBe(false);
	});

	// AC-5 — fängt: der reaktive Ersatzweg für eine der drei „stillen" Gesten
	// (Amtliche-Warnungen-Schalter) fehlt ⇒ kein PUT, obwohl keine Ziehgeste
	// verwendet wurde.
	test('AC-5: Amtliche-Warnungen-Schalter (keine Ziehgeste) → trotzdem gespeichert', async ({ page }) => {
		const id = await legeVergleichAn(page);
		const { beantwortet } = zaehlePuts(page, id);
		const tab = await oeffneWetterMetriken(page, id);

		await tab.locator('[data-testid="report-show-official-alerts"] input[type="checkbox"]').click();

		await expect.poll(() => beantwortet.length, { timeout: 10_000 }).toBeGreaterThanOrEqual(1);
		await expect(anzeige(page)).toHaveAttribute('data-state', 'idle', { timeout: 10_000 });
		const stand = await serverStand(page, id);
		expect(stand.official_alerts_enabled, 'der Schalter (ohne Ziehgeste) muss gespeichert sein').toBe(false);
	});

	// AC-6 — fängt: 'wetter-metriken' fehlt im generischen Flush-Guard ⇒ der
	// Alarm-Vorgang verdrängt die Wetter-Metriken-Änderung vom einen Platz.
	test('AC-6: Wetter-Metriken ändern, sofort zu „Alarme", dort Radar an → BEIDE Änderungen gespeichert', async ({
		page
	}) => {
		const id = await legeVergleichAn(page);
		const { puts, beantwortet } = zaehlePuts(page, id);
		const tab = await oeffneWetterMetriken(page, id);

		await tab
			.locator('[data-testid="weather-metrics-vergleich-row-snow_depth_cm"] input[type="checkbox"]')
			.click();
		// sofort, innerhalb des Entprell-Fensters, den Reiter wechseln
		await page.locator('[data-testid="compare-detail-tab-alarme"]:visible').click();
		await expect(page.locator('[data-testid="alarme-tab"]').first()).toBeVisible({ timeout: 10_000 });
		expect(
			beantwortet.length,
			'die Wetter-Metriken-Änderung war beim Reiterwechsel noch nicht gesendet'
		).toBeGreaterThanOrEqual(1);

		const radar = page.locator('[data-testid="alarme-radar-toggle"] input[type="checkbox"]').first();
		await radar.click();
		await expect(radar).toBeChecked();

		await expect.poll(() => beantwortet.length, { timeout: 10_000 }).toBe(2);
		await expect(anzeige(page)).toHaveAttribute('data-state', 'idle', { timeout: 10_000 });

		const stand = await serverStand(page, id);
		expect(
			(dc(stand).active_metrics as string[]).includes('snow_depth_cm'),
			'die Wetter-Metriken-Änderung ging beim Reiterwechsel verloren'
		).toBe(false);
		expect(stand.radar_alert_enabled).toBe(true);
	});

	// AC-7 — fängt: 412 als generischer Fehler (setError) bzw. Rollback auch
	// bei 412.
	test('AC-7: fremde Änderung dazwischen → „Nochmal speichern" → gespeichert, Wert bleibt sichtbar', async ({
		page
	}) => {
		const id = await legeVergleichAn(page);
		const { puts, beantwortet } = zaehlePuts(page, id);
		const tab = await oeffneWetterMetriken(page, id);

		// GIVEN: eigene erste Änderung gespeichert — die Seite kennt jetzt den ETag (#2375)
		await tab
			.locator('[data-testid="weather-metrics-vergleich-row-snow_depth_cm"] input[type="checkbox"]')
			.click();
		await expect.poll(() => beantwortet.length, { timeout: 10_000 }).toBe(1);
		await expect(anzeige(page)).toHaveAttribute('data-state', 'idle', { timeout: 10_000 });

		// An der Oberfläche vorbei: fremde Änderung ohne If-Match (anderes Gerät)
		const vorher = await serverStand(page, id);
		const fremd = await page.request.put(`/api/compare/presets/${id}`, {
			data: { ...vorher, name: `${vorher.name} (fremd)` }
		});
		expect(fremd.status(), 'fremder Schreibvorgang ohne If-Match wird angenommen').toBe(200);

		// WHEN: zweite Änderung auf dem jetzt veralteten Stand
		await tab.locator('[data-testid="report-show-official-alerts"] input[type="checkbox"]').click();

		// THEN: echter 412 → „Nochmal speichern", keine Rücknahme in der Oberfläche
		await expect(anzeige(page)).toHaveAttribute('data-state', 'conflict', { timeout: 10_000 });
		expect(puts.length, 'Vorbedingung: der zweite PUT wurde gesendet').toBe(2);
		expect((await puts[1].response())?.status(), 'der Server muss den veralteten Stand ablehnen').toBe(412);
		const nochmal = anzeige(page).getByRole('button', { name: 'Nochmal speichern' });
		await expect(nochmal).toBeVisible();

		// WHEN: „Nochmal speichern" → THEN: gespeichert, Wert bleibt sichtbar und auf dem Server
		await nochmal.click();
		await expect(anzeige(page)).toHaveAttribute('data-state', 'idle', { timeout: 10_000 });
		await expect(anzeige(page)).toContainText('Gespeichert');
		expect(puts.length, 'der Wiederholungs-PUT wurde gesendet').toBe(3);
		expect((await puts[2].response())?.status(), 'der Wiederholungs-PUT muss durchgehen').toBe(200);

		const stand = await serverStand(page, id);
		expect(stand.official_alerts_enabled, 'der Wiederholungs-PUT muss die Änderung tragen').toBe(false);
	});

	// AC-12 — fängt: Teil-Nutzlast / fehlendes Bestandsfeld im Wetter-Metriken-PUT.
	test('AC-12: Metrikauswahl ändern → nach Neuladen sind alle übrigen Einstellungen unverändert', async ({ page }) => {
		const id = await legeVergleichAn(page);
		const vorher = await serverStand(page, id);
		const { beantwortet } = zaehlePuts(page, id);
		const tab = await oeffneWetterMetriken(page, id);

		await tab
			.locator('[data-testid="weather-metrics-vergleich-row-snow_depth_cm"] input[type="checkbox"]')
			.click();
		await expect.poll(() => beantwortet.length, { timeout: 10_000 }).toBeGreaterThanOrEqual(1);
		await expect(anzeige(page)).toHaveAttribute('data-state', 'idle', { timeout: 10_000 });

		const nachher = await serverStand(page, id);
		const WETTER_METRIKEN_OBEN = new Set(['display_config', 'updated_at', 'etag']);
		for (const key of Object.keys(vorher)) {
			if (WETTER_METRIKEN_OBEN.has(key)) continue;
			expect(nachher[key], `Feld „${key}" hat sich durch das Wetter-Metriken-Speichern verändert`).toEqual(
				vorher[key]
			);
		}
		const vdc = dc(vorher);
		const ndc = dc(nachher);
		const WETTER_METRIKEN_DC = new Set(['active_metrics', 'channel_active_metrics', 'hourly_metrics', 'outlook_metrics', 'outlook_metric_formats']);
		for (const key of Object.keys(vdc)) {
			if (WETTER_METRIKEN_DC.has(key)) continue;
			expect(ndc[key], `display_config.${key} hat sich verändert`).toEqual(vdc[key]);
		}
		expect((ndc.active_metrics as string[]).includes('snow_depth_cm'), 'nur die Metrikauswahl weicht ab').toBe(false);
	});
});
