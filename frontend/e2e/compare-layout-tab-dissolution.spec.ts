// gz-eigenstaendig: „Kappung der Orte je Kanal"-Aussagen (FORBIDDEN_CLAIMS über alle fünf Reiter) und der Bestandsschutz von hour_from/hour_to nach einem Stundenverlauf-Commit gibt es nur beim Ortsvergleich (Orte als Spalten, Zeitfenster-Felder ohne RMW-Schutz im Go-Handler); Trip-Pendants: hub-wetter-metriken-speichert-selbst und hub-kopf-bearbeiten KB-11.
//
// E2E (Staging) — Ortsvergleich: Layout-Reiter aufgelöst, Stundenverlauf zieht in
// den Reiter „Wetter-Metriken" (Issue #1360, Scheibe S1a von Epic #1372).
//
// Spec: docs/specs/modules/compare_layout_tab_dissolution.md § Acceptance Criteria
// Abgedeckt hier (seit #2347 S4): AC-4, AC-5.
// #2347 S4 (feat_2347_s4_paritaets_e2e.md, Befund 5/9): AC-1 (veraltete Erwartung
// „sieben Reiter") → hub-tab-bar HT-4 + Reihenfolge-Tests in
// hub-reiter-alt-kennungen-umleitung; AC-2 (Stundengröße ⇒ PUT, bleibt) →
// hub-wetter-metriken-speichert-selbst MS-2 + compare-stundenverlauf-wertprops;
// AC-3 (?tab=layout) → hub-reiter-alt-kennungen-umleitung; AC-6 (Anlege-Seite,
// Stundenverlauf, kein top_n) → hub-anlegen-ablauf AN-6/AN-12.
//
// ── Warum Live-Schicht ───────────────────────────────────────────────────────
//   AC-4      — was der Nutzer in den Reitern liest.
//   AC-5      — Bestandsschutz von `hour_from`/`hour_to` gegen den ECHTEN
//               Go-Handler. Der hat für diese beiden Felder KEINEN Read-Modify-
//               Write-Schutz (Adversary-Fund F003 aus #1268: fehlen sie im PUT,
//               dekodiert Go Zero-Value 0 und schreibt 0 — stiller Datenverlust).
//               Ein Unit-Test auf die Payload-Bau-Funktion beweist das NICHT.
//               Vorbild: hub-kopf-bearbeiten.spec.ts KB-11 (Bestandsfelder bitgleich).
//
// NICHT hier: der Mail-Anteil von AC-2 und AC-7 (Stundentabellen-Spalten in der
// echt zugestellten Mail). Der läuft in `/e2e-verify` über das Stalwart-Test-
// Postfach + `email_spec_validator.py` (Marker `X-GZ-Mail-Type: compare`).
// Die deterministische Struktur-Invarianz der Mail (AC-7) liegt in der
// Kern-Schicht: tests/test_compare_top_n_render_invariance.py.
//
// ── Ausführen (gegen STAGING, aus frontend/, NACH Push + Staging-Deploy) ─────
//   set -a; source /home/hem/gregor_zwanzig/.claude/validator.env; set +a
//   npx playwright test --config=playwright.compare-layout-tab-dissolution.staging.config.ts
//
// Die Config `frontend/playwright.compare-layout-tab-dissolution.staging.config.ts`
// liegt daneben (1:1 nach `playwright.compare-hourly-metric-order.staging.config.ts`).
// Kein `webServer`-Block: geprüft wird die auf Staging deployte App selbst.
// WICHTIG: `GZ_API_BASE` zeigt per Default auf PRODUKTION (playwright.config.ts).
// Deshalb baseURL in der Config explizit auf `GZ_SVELTE_BASE ??
// 'https://staging.gregor20.henemm.com'`, und `assertNotProdBaseURL` im Setup
// sperrt jeden Lauf gegen die Prod-Domain (#1265).
// Anmeldung über gespeicherten Sitzungszustand (storageState), NICHT per
// Test-Login — der Login ist auf 30/h gedeckelt
// (reference_staging_e2e_storagestate_login_rate_limit).
// Testids kommen doppelt vor (Desktop/Mobil-Zweig) ⇒ durchgängig `:visible`.

import { test, expect, type Locator, type Page, type Request } from '@playwright/test';
import { cleanupTracked, createTestLocation, createTestComparePreset } from './helpers';

/**
 * Aussagen, die es im Vergleichs-Editor NICHT mehr geben darf (AC-4).
 * Belegte Renderer-Regel: ALLE drei Kanäle geben ALLE Orte aus — gekappt werden
 * Metrikwerte je Ort bzw. die Nachrichtenlänge, nie die Orts-Spalten.
 * Heutiger Ist-Stand (CompareTabs.svelte:774-775,1303,1319): „Telegram · max 8",
 * „SMS · flach · 0", „Renderer kappt je Kanal".
 */
const FORBIDDEN_CLAIMS: RegExp[] = [
	/Telegram\s*·\s*max\s*\d+/i,
	/kappt\s+je\s+Kanal/i,
	/Spalten\s+pro\s+Kanal/i,
	/Übersicht\s+pro\s+Kanal/i,
	/max\.?\s*\d+\s*(Orte|Spalten)/i
];

test.afterEach(async ({ page }) => {
	await cleanupTracked(page.request);
});

async function makeThreeLocationIds(page: Page): Promise<string[]> {
	const ids: string[] = [];
	for (let i = 0; i < 3; i++) {
		const loc = await createTestLocation(page.request, { lat: 47.0 + i * 0.1, lon: 11.0 + i * 0.1 });
		ids.push(loc.id);
	}
	return ids;
}

async function makePreset(
	page: Page,
	opts: { hourFrom?: number; hourTo?: number } = {}
): Promise<string> {
	const locationIds = await makeThreeLocationIds(page);
	const preset = await createTestComparePreset(page.request, {
		name: `Layout-Auflösung ${Date.now()}`,
		locationIds,
		hourFrom: opts.hourFrom,
		hourTo: opts.hourTo
	});
	return preset.id;
}

/** Öffnet den Hub und wartet die Hydration ab (SvelteKit-Race, s. #1359). */
async function openHub(page: Page, id: string, query = ''): Promise<void> {
	await page.goto(`/compare/${id}${query}`);
	await expect(page.getByTestId('compare-detail-tab-list')).toBeVisible({ timeout: 15_000 });
	// Die Tab-Leiste kommt server-gerendert VOR der Hydration; ein Klick davor
	// geht spurlos verloren (reproduzierbar ~2/3 auf Staging, #1359).
	await page.waitForLoadState('networkidle');
}

async function openHubMetricsTab(page: Page, id: string): Promise<Locator> {
	await openHub(page, id);
	await page.locator('[data-testid="compare-detail-tab-wetter-metriken"]:visible').first().click();
	const panel = page.locator('[data-testid="compare-detail-panel-wetter-metriken"]:visible').first();
	await expect(panel).toBeVisible({ timeout: 10_000 });
	return panel;
}

/** Zeichnet jeden PUT auf diesen Vergleich auf (Speicher-Nachweis, AC-5). */
function collectPresetPuts(page: Page, id: string): Request[] {
	const puts: Request[] = [];
	page.on('request', (req) => {
		if (req.method() === 'PUT' && req.url().includes(`/api/compare/presets/${id}`)) {
			puts.push(req);
		}
	});
	return puts;
}

async function readPreset(page: Page, id: string): Promise<Record<string, unknown>> {
	const res = await page.request.get(`/api/compare/presets/${id}`);
	expect(res.ok(), `GET des Presets fehlgeschlagen: ${res.status()}`).toBeTruthy();
	return (await res.json()) as Record<string, unknown>;
}

test.describe('Issue #1360: Layout-Reiter aufgelöst, Stundenverlauf bei den Wetter-Metriken', () => {
	test.beforeEach(async ({ page }) => {
		await page.setViewportSize({ width: 1280, height: 900 });
	});

	// ── AC-4 ──────────────────────────────────────────────────────────────────
	test('AC-4: keine Fläche behauptet mehr eine Kappung der Orte je Kanal', async ({ page }) => {
		const id = await makePreset(page);
		await openHub(page, id);

		const collected: string[] = [];
		// Issue #1743: der Versand-Inhalt steht im Panel wetter-metriken (#versand).
		for (const tab of ['uebersicht', 'orte', 'wetter-metriken', 'wertebereiche', 'alarme']) {
			await page.locator(`[data-testid="compare-detail-tab-${tab}"]:visible`).first().click();
			const panel = page.locator(`[data-testid="compare-detail-panel-${tab}"]:visible`).first();
			await expect(panel).toBeVisible({ timeout: 10_000 });
			collected.push(await panel.innerText());
		}
		const allText = collected.join('\n---\n');

		for (const claim of FORBIDDEN_CLAIMS) {
			expect(
				allText,
				`AC-4: der Editor behauptet weiterhin eine Orts-Kappung je Kanal (${claim}). ` +
					'Belegte Renderer-Regel: alle drei Kanäle geben ALLE Orte aus.'
			).not.toMatch(claim);
		}
	});

	// ── AC-5 ──────────────────────────────────────────────────────────────────
	test('AC-5: gespeichertes Zeitfenster überlebt eine Änderung im neuen Aufbau', async ({
		page
	}) => {
		const id = await makePreset(page, { hourFrom: 10, hourTo: 14 });

		// Vorbedingung: der Server hat die Werte wirklich übernommen — sonst
		// prüft der Test unten gegen Defaults und wäre wertlos.
		const before = await readPreset(page, id);
		expect(before.hour_from, 'Vorbedingung: hour_from=10 angelegt').toBe(10);
		expect(before.hour_to, 'Vorbedingung: hour_to=14 angelegt').toBe(14);

		const panel = await openHubMetricsTab(page, id);
		const puts = collectPresetPuts(page, id);
		const toggle = panel
			.locator('[data-testid="compare-layout-hourly-metric-uv_index"] input')
			.first();
		await expect(toggle).toBeVisible({ timeout: 10_000 });
		await toggle.click();
		await expect.poll(() => puts.length, { timeout: 10_000 }).toBeGreaterThan(0);

		const after = await readPreset(page, id);
		expect(
			after.hour_from,
			'AC-5: hour_from muss den Speichervorgang bitgleich überleben — der Go-Handler ' +
				'hat für dieses Feld KEINEN Read-Modify-Write-Schutz (#1268 F003), fehlt es im ' +
				'PUT-Body wird still 0 geschrieben'
		).toBe(10);
		expect(after.hour_to, 'AC-5: hour_to muss bitgleich überleben').toBe(14);
	});
});
