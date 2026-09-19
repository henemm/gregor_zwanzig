// E2E — Issue #2276 Scheibe S2 (Epic #2345): der Reiter „Alarme" im
// Ortsvergleich-Hub speichert SELBST (ohne Wrapper) — Nachweis am Wirkort.
//
// Spec: docs/specs/modules/rework_2276_s2_alarme.md — AC-1, AC-6, Design Punkt 5
//
// Warum E2E: die Frontend-Unit-Harness ist SSR-only (node --test +
// svelte/server), `$effect` läuft dort nie. Die Verdrahtung — `$effect`-
// Delegation in AlarmeTab.svelte, neue Props am <AlarmeTab>-Mount in
// CompareTabs.svelte, Flush beim Reiterwechsel (handleValueChange) und Flush
// vor Pausieren/Aktivieren (handleToggleActive) — ist nur im echten Browser
// messbar (Adversary-Findings F001–F004).
//
// Läuft im isolierten CI-Stack (frontend/e2e/ci-stack.sh), Anmeldung über den
// gespeicherten storageState aus global.setup.ts (kein eigener Login — das
// IP-Limit gehört bug-703). Presets tragen das Präfix E2E-GZ-, damit
// global.teardown.ts Reste räumt; afterEach löscht sie direkt.

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
			name: `${E2E_TEST_PREFIX}Alarme speichert selbst ${Date.now()}`,
			// Seed-Orte aus global.setup.ts — mit Orten ist der Vergleich „aktiv",
			// der Kebab bietet dann „Pausieren" an.
			location_ids: ['e2e-loc-innsbruck', 'e2e-loc-stubai'],
			schedule: 'daily',
			profil: 'wandern',
			hour_from: 7,
			hour_to: 16,
			empfaenger: ['alarme-selbst@example.com'],
			radar_alert_enabled: false,
			display_config: { active_metrics: ['wind_max_kmh'] }
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

async function oeffneAlarme(page: Page, id: string): Promise<void> {
	await page.goto(`/compare/${id}`);
	await page.waitForLoadState('networkidle');
	await page.locator('[data-testid="compare-detail-tab-alarme"]').click();
	await expect(page.locator('[data-testid="alarme-tab"]').first()).toBeVisible({ timeout: 10_000 });
}

function radarSchalter(page: Page) {
	return page.locator('[data-testid="alarme-radar-toggle"] input[type="checkbox"]').first();
}

async function serverStand(page: Page, id: string): Promise<Record<string, unknown>> {
	const res = await page.request.get(`/api/compare/presets/${id}`);
	expect(res.ok()).toBeTruthy();
	return res.json();
}

test.describe('Issue #2276 S2: Reiter „Alarme" im Vergleich speichert selbst', () => {
	test.beforeEach(async ({ page }) => {
		await page.setViewportSize({ width: 1280, height: 900 });
	});

	// AC-1 — fängt: $effect-Delegation (AlarmeTab) und Mount-Props (CompareTabs)
	test('AC-1: Alarm ändern → genau ein PUT mit dem neuen Wert, danach „Gespeichert"', async ({ page }) => {
		const id = await legeVergleichAn(page);
		const { puts, beantwortet } = zaehlePuts(page, id);
		await oeffneAlarme(page, id);
		expect(puts.length, 'Vorbedingung: das Öffnen des Reiters speichert nichts').toBe(0);

		await radarSchalter(page).click();
		await expect(radarSchalter(page)).toBeChecked();

		await expect.poll(() => beantwortet.length, { timeout: 10_000 }).toBeGreaterThanOrEqual(1);
		const anzeige = page.locator('[data-testid="save-indicator"]');
		await expect(anzeige).toHaveAttribute('data-state', 'idle', { timeout: 10_000 });
		await expect(anzeige).toContainText('Gespeichert');

		expect(puts.length, 'genau EIN PUT für eine Alarm-Änderung').toBe(1);
		expect(puts[0].postDataJSON().radar_alert_enabled).toBe(true);
		expect((await serverStand(page, id)).radar_alert_enabled).toBe(true);
	});

	// AC-6 — fängt: sichereSelbstSpeichererVorReiterwechsel in handleValueChange
	test('AC-6: Alarm ändern und sofort zu „Versand" wechseln → PUT ist beim Wechsel schon beantwortet', async ({
		page
	}) => {
		const id = await legeVergleichAn(page);
		const { puts, beantwortet } = zaehlePuts(page, id);
		await oeffneAlarme(page, id);

		await radarSchalter(page).click();
		// sofort, innerhalb des Entprell-Fensters (700 ms) den Reiter wechseln
		await page.locator('[data-testid="compare-detail-tab-versand"]').click();
		await expect(page.locator('[data-testid="compare-detail-panel-versand"]')).toBeVisible();

		// Der Wechsel wird erst freigegeben, NACHDEM der Alarm-PUT beantwortet ist —
		// ohne Flush käme der PUT erst nach Ablauf der Entprellung.
		expect(beantwortet.length, 'Alarm-PUT war beim Reiterwechsel noch nicht gesendet').toBeGreaterThanOrEqual(1);
		expect(beantwortet[0].postDataJSON().radar_alert_enabled).toBe(true);

		await expect(page.locator('[data-testid="save-indicator"]')).toHaveAttribute('data-state', 'idle', {
			timeout: 10_000
		});
		expect(puts.length).toBe(1);
		expect((await serverStand(page, id)).radar_alert_enabled).toBe(true);
	});

	// Design Punkt 5 — fängt: saveController.flush() vor handleToggleActive
	test('Pausieren direkt nach Alarm-Änderung → Alarm-PUT geht VOR dem Pausieren-PUT, beide Werte bleiben', async ({
		page
	}) => {
		const id = await legeVergleichAn(page);
		const { puts, beantwortet } = zaehlePuts(page, id);
		await oeffneAlarme(page, id);

		await radarSchalter(page).click();
		// sofort (innerhalb der Entprellung) über den Kopf-Kebab pausieren
		await page.getByRole('button', { name: 'Weitere Aktionen' }).first().click();
		await page.getByRole('menuitem', { name: 'Pausieren' }).click();

		await expect.poll(() => beantwortet.length, { timeout: 10_000 }).toBe(2);
		await expect(page.locator('[data-testid="save-indicator"]')).toHaveAttribute('data-state', 'idle', {
			timeout: 10_000
		});

		const [erster, zweiter] = puts.map((r) => r.postDataJSON());
		expect(erster.radar_alert_enabled, 'erster PUT muss die Alarm-Änderung sein').toBe(true);
		expect(erster.schedule, 'erster PUT darf noch nicht pausieren').toBe('daily');
		expect(zweiter.schedule).toBe('manual');
		expect(zweiter.radar_alert_enabled, 'Pausieren-PUT schreibt den alten Alarmwert zurück').toBe(true);

		const stand = await serverStand(page, id);
		expect(stand.radar_alert_enabled).toBe(true);
		expect(stand.schedule).toBe('manual');
		expect(puts.length).toBe(2);
	});
});
