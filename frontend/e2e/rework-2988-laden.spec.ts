// E2E — Issue #2988 S3 (AC-9, AC-10, AC-11): der Reiter Wetter zeigt die vom Server aufgelöste Ampel wie bisher,
// meldet eine gescheiterte Auflösung mit „Erneut laden“ und speichert beim Öffnen nichts.
// Spec: docs/specs/modules/rework_2988_ampel_ableitung.md. Echte Server (Staging in /e2e-verify); nur der Abbruch
// der Auflösung entsteht im Browser-Netz (page.route).
//
//   cd frontend && npx playwright test e2e/rework-2988-laden.spec.ts --workers=1 --trace off

import { test, expect, type Locator, type Page } from '@playwright/test';
import { HUB_KINDS, HUB_SEL, cleanupTracked, openHub, type HubKind } from './helpers';
import { DESKTOP, WT, abweichungen, oeffneWetter, seedWetter, stand, vorlagen, warteAufSpeichern, type Json } from './s3a2794-teil3.helpers';

const AUFLOESUNG = '/api/ampel/aufloesung';
const istAufloesung = (url: URL) => url.pathname === AUFLOESUNG;
/** Eine Abweichung je Art: Grenze, Alarmstufe, Gewitterfarbe. */
const DREI = { metrics: { gust: { upper: { yellow: 41, orange: 61, red: 77 } }, wind: { alarm_ab: 'red' } }, thunder: { mittel: 'red' } };

test.afterEach(async ({ page }) => {
	await cleanupTracked(page.request);
});

/** Alle schreibenden Aufrufe der Seite auf Abo, Vorlagen und Karte; die Auflösung liest nur. */
function schreibZaehler(page: Page): string[] {
	const liste: string[] = [];
	page.on('request', (r) => {
		const pfad = new URL(r.url()).pathname;
		if (r.method() === 'GET' || pfad === AUFLOESUNG) return;
		if (/^\/api\/(trips|compare|briefings|metric-presets)/.test(pfad)) liste.push(`${r.method()} ${pfad}`);
	});
	return liste;
}
function aufloesungen(page: Page): Json[] {
	const liste: Json[] = [];
	page.on('request', (r) => {
		if (istAufloesung(new URL(r.url()))) liste.push(r.postDataJSON());
	});
	return liste;
}
const reiterIm = (page: Page, kind: HubKind): Locator =>
	page.locator(`[data-testid="${HUB_SEL[kind].panel}-wetter"]:visible`).first().getByTestId(WT.tab);

async function pruefeDreiAbweichungen(reiter: Locator, label: string): Promise<void> {
	await expect(reiter.getByTestId(WT.picker)).toContainText(label);
	expect(await abweichungen(reiter)).toBe(3);
	const gust = reiter.getByTestId(WT.zeile('gust'));
	await gust.getByTestId(WT.grenzenAendern('gust')).click();
	for (const [farbe, wert] of [['yellow', '41'], ['orange', '61'], ['red', '77']] as const)
		await expect(gust.getByTestId(WT.grenze('gust', 'upper', farbe))).toHaveValue(wert);
	await gust.getByTestId(WT.grenzenAendern('gust')).click();
	await expect(reiter.getByTestId(WT.zeile('wind')).getByTestId(WT.alarmAbStufe('wind', 'red'))).toHaveAttribute('aria-checked', 'true');
	const gewitter = reiter.getByTestId(WT.zeile('thunder'));
	await gewitter.getByTestId(WT.grenzenAendern('thunder')).click();
	await expect(gewitter.getByTestId(WT.gewitterFarbe('mittel', 'red'))).toHaveAttribute('aria-checked', 'true');
	await gewitter.getByTestId(WT.grenzenAendern('thunder')).click();
}

for (const kind of HUB_KINDS) {
	test(`AC-9 (${kind}): Vorlage, Grenzen, Alarmstufen, Zähler und eigene Vorlagen (auch Altformat) wie bisher`, async ({ page }) => {
		await page.setViewportSize(DESKTOP);
		const hub = await seedWetter(page.request, kind, { vorlageId: 'wandern', ampel: DREI });
		const eigene: string[] = [];
		try {
			const v = await vorlagen(page.request);
			const marke = `${kind}-${Date.now()}`;
			const neu = { ...v.skitouren.ampel, metrics: { ...v.skitouren.ampel.metrics, gust: { enabled: true, lower: {}, upper: { yellow: 33, orange: 44, red: 55 }, alarm_ab: 'red' } } };
			for (const rumpf of [
				{ name: `E2E-GZ-Ampel-${marke}`, kind, metrics: [{ metric_id: 'gust', enabled: true, use_friendly_format: false }], ampel: neu },
				{ name: `E2E-GZ-Alt-${marke}`, kind, metrics: [{ metric_id: 'wind', enabled: true, use_friendly_format: false }, { metric_id: 'gust', enabled: false, use_friendly_format: false }] }
			]) {
				const r = await page.request.post('/api/metric-presets', { data: rumpf });
				expect(r.ok(), `Eigene Vorlage: ${r.status()}`).toBeTruthy();
				eigene.push(((await r.json()) as Json).id);
			}
			const vorher = await stand(page.request, kind, hub.id);
			const fragen = aufloesungen(page);
			const schreib = schreibZaehler(page);
			const reiter = await oeffneWetter(page, kind, hub.id);
			expect(fragen.length, 'AC-9: der Reiter fragt die Auflösung nicht').toBeGreaterThanOrEqual(1);
			expect(fragen[0].eintraege[0], 'Eintrag 0 ist das Abo').toMatchObject({ ampel: vorher.display_config.ampel });
			expect(fragen[0].eintraege[0], 'Abo-Eintrag ohne Metrikliste').not.toHaveProperty('metrics');

			await pruefeDreiAbweichungen(reiter, v.wandern.label);
			await reiter.getByTestId(WT.picker).click();
			for (const id of eigene) await expect(page.getByTestId(WT.eigeneOption(id))).toBeVisible();
			expect(schreib, 'Ansehen speichert').toEqual([]);

			// Altformat übernehmen: Vorlage „allgemein“, nur die gelistete, aktive Metrik.
			const speichern = warteAufSpeichern(page, kind, hub.id);
			await page.getByTestId(WT.eigeneOption(eigene[1])).click();
			await page.getByTestId(WT.wechselUebernehmen).click();
			await speichern;
			await expect(reiter.getByTestId(WT.picker)).toContainText(v.allgemein.label);
			await expect(reiter.locator('[data-testid^="wetter-grenzen-aendern-"]')).toHaveCount(1);
			await expect(reiter.getByTestId(WT.zeile('wind'))).toBeVisible();

			// Vorlage mit Ampel übernehmen: ihre Grenzen und Alarmstufe.
			const nochmal = warteAufSpeichern(page, kind, hub.id);
			await reiter.getByTestId(WT.picker).click();
			await page.getByTestId(WT.eigeneOption(eigene[0])).click();
			await page.getByTestId(WT.wechselUebernehmen).click();
			await nochmal;
			await expect(reiter.getByTestId(WT.picker)).toContainText(v.skitouren.label);
			const ampel = (await stand(page.request, kind, hub.id)).display_config.ampel;
			expect(ampel.template).toBe('skitouren');
			expect(ampel.metrics.gust).toEqual({ upper: { yellow: 33, orange: 44, red: 55 }, alarm_ab: 'red' });
		} finally {
			for (const id of eigene) await page.request.delete(`/api/metric-presets/${id}`).catch(() => {});
			await hub.aufraeumen();
		}
	});

	for (const [art, abbruch] of [
		['Netzabbruch', (r: Json) => r.abort('connectionfailed')],
		['HTTP 503', (r: Json) => r.fulfill({ status: 503, contentType: 'application/json', body: '{"error":"upstream_unreachable"}' })]
	] as const) {
		test(`AC-10 (${kind}, ${art}): „Erneut laden“, nichts gespeichert, danach bereit`, async ({ page }) => {
			await page.setViewportSize(DESKTOP);
			const hub = await seedWetter(page.request, kind, { vorlageId: 'wandern', ampel: DREI });
			try {
				const v = await vorlagen(page.request);
				const vorher = await stand(page.request, kind, hub.id);
				const schreib = schreibZaehler(page);
				await page.route(istAufloesung, abbruch);
				await openHub(page, kind, hub.id, { tab: 'wetter' });
				const reiter = reiterIm(page, kind);
				await expect(reiter.getByTestId(WT.fehler)).toBeVisible({ timeout: 15_000 });
				await expect(reiter.getByTestId(WT.erneutLaden)).toHaveText('Erneut laden');
				await expect(reiter.locator('[data-testid^="wetter-zeile-"]')).toHaveCount(0);
				// Länger als die Speicher-Entprellung (700 ms).
				await page.waitForTimeout(1500);
				expect(schreib, 'AC-10: trotz Fehler gespeichert').toEqual([]);
				expect((await stand(page.request, kind, hub.id)).display_config).toEqual(vorher.display_config);

				await page.unroute(istAufloesung);
				await reiter.getByTestId(WT.erneutLaden).click();
				await expect(reiter.getByTestId(WT.fehler)).toHaveCount(0, { timeout: 15_000 });
				await pruefeDreiAbweichungen(reiter, v.wandern.label);
				expect(schreib).toEqual([]);
			} finally {
				await page.unroute(istAufloesung).catch(() => {});
				await hub.aufraeumen();
			}
		});
	}

	// Bestand: vollständiges Abo, Altformat der Auswahl, nie eingestellt.
	const ALTFORMAT: Record<HubKind, Json> = {
		route: { display_config: { preset_name: 'wandern', metrics: ['temperature', 'gust', 'wind'] } },
		vergleich: { display_config: { active_metrics: ['temp_max_c', 'wind_max_kmh', 'snow_depth_cm'] } }
	};
	const BESTAND: [string, Json][] = [
		['mit Abweichungen', { vorlageId: 'wandern', ampel: DREI }],
		['Altformat ohne Ampel', { extra: ALTFORMAT[kind] }],
		['nie eingestellt', { extra: { display_config: {} } }]
	];
	for (const [name, seed] of BESTAND) {
		test(`AC-11 (${kind}, ${name}): Öffnen und Warten speichert nichts`, async ({ page }) => {
			await page.setViewportSize(DESKTOP);
			const hub = await seedWetter(page.request, kind, seed);
			try {
				const vorher = await stand(page.request, kind, hub.id);
				const schreib = schreibZaehler(page);
				const fragen = aufloesungen(page);
				await oeffneWetter(page, kind, hub.id);
				expect(fragen.length, 'der Reiter fragt die Auflösung nicht').toBeGreaterThanOrEqual(1);
				await page.waitForTimeout(2000);
				expect(schreib, 'AC-11: Öffnen hat gespeichert').toEqual([]);
				expect(await stand(page.request, kind, hub.id)).toEqual(vorher);
			} finally {
				await hub.aufraeumen();
			}
		});
	}
}
