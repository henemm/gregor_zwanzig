// E2E (Staging) — Issue #3399 S1, AC-1: „Alarm ab" im Reiter Alarme kommt aus der Vorlage, die der
// SERVER aufgelöst hat (POST /api/ampel/aufloesung), nie aus einer im Frontend errechneten.
// Spec: docs/specs/modules/rework_3399_vorlage_aufloesung.md (Test Plan „Live", AC-1).
//
// Der Reiter Alarme sitzt im Anlegen-Fluss (Schritt Zustellung) von Trip UND Ortsvergleich. Gemessen
// wird je kind: die Zeilen der Alarm-Tabelle tragen `data-alarm-ab` (Stufe oder „offen" = „—"). Der Test
// ermittelt die Soll-Stufe selbst: die Anfrage, die die Seite an die Aufloesung stellt, wird mitgeschnitten
// und mit der angemeldeten Sitzung erneut gestellt; die Vorlage muss in GET /api/templates stehen.
// Wegwerf-Daten (Praefix E2E-GZ-), kein fester Schlaf, nie gegen Produktion.
//
//   cd frontend && npx playwright test --config playwright.3399.staging.config.ts rework-3399-alarme

import { test, expect, type Page, type Request } from '@playwright/test';
import { ANLEGE_SEL, anlegenPflicht, cleanupTracked, E2E_TEST_PREFIX, HUB_KINDS, type HubKind } from './helpers';
import { DESKTOP } from './s3b2795-zustellung.helpers';

const AUFLOESUNG = '/api/ampel/aufloesung';
/** Alarm-Zeile (AlertMetric) -> Katalog-ID der Ampel (Spec Alarm-Ab-Anzeige, generiertes Mapping). */
const KATALOG: Record<string, string> = {
	wind_gust: 'gust',
	precipitation_sum: 'precipitation',
	temperature_max: 'temperature',
	temperature_min: 'temperature',
	thunder_level: 'thunder'
};
const STUFEN = ['never', 'yellow', 'orange', 'red'];

test.afterEach(async ({ page }) => {
	await cleanupTracked(page.request);
});

// Sprachneutral: Trip-Reiter über data-testid (`trip-new-tab-<id>`), nicht über das übersetzte Label.
function reiterSel(page: Page, kind: HubKind, id: string) {
	return kind === 'route' ? page.locator(`.tn-desktop [data-testid="trip-new-tab-${id}"]`) : ANLEGE_SEL[kind].reiter(page, id);
}

async function schritt(page: Page, kind: HubKind, id: string): Promise<void> {
	await reiterSel(page, kind, id).click();
	await expect.poll(async () => (await ANLEGE_SEL[kind].zustand(reiterSel(page, kind, id))).aktiv, { timeout: 10_000 }).toBe(true);
}

for (const kind of HUB_KINDS) {
	test(`AC-1 (${kind}): „Alarm ab" zeigt die Stufe der vom Server aufgelösten Vorlage, nie „—"`, async ({ page }) => {
		const anfragen: Request[] = [];
		page.on('request', (r) => {
			if (r.method() === 'POST' && new URL(r.url()).pathname === AUFLOESUNG) anfragen.push(r);
		});
		await anlegenPflicht(page, kind, { name: `${E2E_TEST_PREFIX}R3399-${kind}-${Date.now()}`, viewport: DESKTOP });
		await schritt(page, kind, 'wetter');
		await schritt(page, kind, 'zustellung');

		const reiter = ANLEGE_SEL[kind].inhalt.alarme(page);
		await expect(reiter, 'Reiter Alarme fehlt im Schritt Zustellung').toBeVisible({ timeout: 15_000 });
		const zeilen = reiter.locator('[data-testid^="alert-metric-row-"]');
		await expect.poll(() => zeilen.count(), { message: 'Alarm-Tabelle ohne Zeilen', timeout: 15_000 }).toBeGreaterThan(0);

		// Die Seite hat die Aufloesung wirklich befragt; dieselbe Anfrage stellt der Test selbst.
		await expect.poll(() => anfragen.length, { message: 'kein POST /api/ampel/aufloesung', timeout: 15_000 }).toBeGreaterThan(0);
		const antwort = await page.request.post(AUFLOESUNG, { data: anfragen[0].postDataJSON() });
		expect(antwort.ok(), `Aufloesung HTTP ${antwort.status()}`).toBeTruthy();
		const erg = ((await antwort.json()) as { ergebnisse: { vorlage_id: string; ampel: { metrics: Record<string, { alarm_ab?: string }> } }[] }).ergebnisse[0];
		expect(erg.vorlage_id, 'Server liefert eine Vorlagen-ID').toBeTruthy();

		// Die aufgeloeste Vorlage ist eine echte Vorlage des Nutzers/Systems.
		const vorlagen = (await (await page.request.get('/api/templates')).json()) as { id?: string; ampel?: { metrics?: Record<string, { alarm_ab?: string }> } }[];
		const vorlage = vorlagen.find((v) => v.id === erg.vorlage_id);
		expect(vorlage, `Vorlage ${erg.vorlage_id} nicht in /api/templates`).toBeTruthy();

		let geprueft = 0;
		for (const zeile of await zeilen.all()) {
			const metrik = (await zeile.getAttribute('data-metric')) ?? '';
			const katalogId = KATALOG[metrik];
			if (!katalogId) continue; // Vorboten und D4-Zeilen haben keine Ampel-Vorgabe
			const ist = await zeile.getAttribute('data-alarm-ab');
			expect(ist, `${metrik}: „Alarm ab" bleibt „—"`).not.toBe('offen');
			const soll = erg.ampel.metrics?.[katalogId]?.alarm_ab ?? vorlage?.ampel?.metrics?.[katalogId]?.alarm_ab ?? 'never';
			expect(STUFEN, `${metrik}: unbekannte Soll-Stufe`).toContain(soll);
			expect(ist, `${metrik}: Anzeige weicht von der Server-Vorlage ${erg.vorlage_id} ab`).toBe(soll);
			geprueft++;
		}
		expect(geprueft, 'keine Ampel-Zeile geprueft').toBeGreaterThan(0);
	});
}
