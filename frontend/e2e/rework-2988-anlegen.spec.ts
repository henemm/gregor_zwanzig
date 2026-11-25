// E2E — Issue #2988 S3 (AC-15): beim Anlegen von Trip und Ortsvergleich im Reiter Wetter eine Vorlage wählen und
// eine Grenze ändern; das angelegte Abo trägt dieselbe Ampel und Auswahl, vor dem Anlegen wird nichts gespeichert.
// Spec: docs/specs/modules/rework_2988_ampel_ableitung.md. Echte Server (Staging in /e2e-verify).
//
//   cd frontend && npx playwright test e2e/rework-2988-anlegen.spec.ts --workers=1 --trace off

import { test, expect, type APIRequestContext, type Page } from '@playwright/test';
import { ANLEGE_SEL, E2E_TEST_PREFIX, HUB_KINDS, anlegenPflicht, cleanupTracked, registerForCleanup, type HubKind } from './helpers';
import { DESKTOP, WT, abgeleiteteKinder, abweichungen, aktiveDerVorlage, auswahlImStand, oeffneWetter, stand, vorlageImReiterWaehlen, vorlagen, type Json } from './s3a2794-teil3.helpers';

const AUFLOESUNG = '/api/ampel/aufloesung';
const VORSCHAU = '/api/briefings/placements/vorschau';
const HUELLE: Record<HubKind, string> = { route: '.tn-desktop', vergleich: '.cm-desktop' };
const ART: Record<HubKind, 'trip' | 'preset'> = { route: 'trip', vergleich: 'preset' };
const VORLAGE = 'skitouren';

test.afterEach(async ({ page }) => {
	await cleanupTracked(page.request);
});

type Aufruf = { methode: string; pfad: string; rumpf: Json };
function mitschneiden(page: Page): Aufruf[] {
	const alle: Aufruf[] = [];
	page.on('request', (r) => {
		const { pathname } = new URL(r.url());
		if (!pathname.startsWith('/api/') || r.method() === 'GET') return;
		let rumpf: Json = null;
		try {
			rumpf = r.postDataJSON();
		} catch {
			rumpf = null;
		}
		alle.push({ methode: r.method(), pfad: pathname, rumpf });
	});
	return alle;
}
/** Speichernde Aufrufe; die Auflösung, die Vorschau und die Hilfsaufrufe (GPX, Ortssuche) speichern nichts. */
const speichernd = (alle: Aufruf[]) => alle.filter((a) => ![AUFLOESUNG, VORSCHAU].includes(a.pfad) && !/^\/api\/(gpx\/|locations)/.test(a.pfad));

/** Auswahl der Vorlage, wie der Kontext sie ausgibt. */
async function sollAuswahl(request: APIRequestContext, kind: HubKind, v: Json): Promise<string[]> {
	const aktiv = aktiveDerVorlage(v);
	const alle = [...new Set([...aktiv, ...abgeleiteteKinder(kind, aktiv)])].sort();
	if (kind === 'route') return alle;
	const r = await request.get('/api/compare/metrics');
	expect(r.ok(), `GET /api/compare/metrics: ${r.status()}`).toBeTruthy();
	const katalog = new Set(((await r.json()) as { metrics: { metric_id?: string }[] }).metrics.map((m) => m.metric_id));
	return alle.filter((id) => katalog.has(id));
}

for (const kind of HUB_KINDS) {
	test(`AC-15 (${kind}): Vorlage wählen, Grenze ändern, anlegen – Ampel und Auswahl im Abo, vorher kein Speichern`, async ({ page }) => {
		const v = (await vorlagen(page.request))[VORLAGE];
		const soll = { ...v.ampel.metrics.gust.upper, yellow: v.ampel.metrics.gust.upper.yellow + 1 };
		expect(soll.yellow, 'Messaufbau: Grenzen der Vorlage').toBeLessThan(soll.orange);
		const sel = ANLEGE_SEL[kind];
		const alle = mitschneiden(page);
		let id = '';
		page.on('response', async (r) => {
			if (r.request().method() !== 'POST' || new URL(r.url()).pathname !== sel.postPfad || !r.ok()) return;
			id = ((await r.json().catch(() => ({}))) as { id?: string }).id ?? '';
			if (id) registerForCleanup(ART[kind], id);
		});

		await anlegenPflicht(page, kind, { name: `${E2E_TEST_PREFIX}2988-${kind}-${Date.now()}`, viewport: DESKTOP });
		await sel.reiter(page, 'wetter').click();
		const reiter = page.locator(`${HUELLE[kind]} [data-testid="${WT.tab}"][data-context="${kind}"]`);
		await expect(reiter.getByTestId(WT.laden)).toHaveCount(0, { timeout: 20_000 });
		const fragen = () => alle.filter((a) => a.pfad === AUFLOESUNG).length;
		expect(fragen(), 'der Reiter fragt die Auflösung nicht').toBeGreaterThanOrEqual(1);
		const nachLaden = fragen();

		await vorlageImReiterWaehlen(page, VORLAGE);
		await expect(reiter.getByTestId(WT.picker)).toContainText(v.label);
		await expect(reiter.getByTestId(WT.pickerStatus)).toHaveText('unverändert');
		const gust = reiter.getByTestId(WT.zeile('gust'));
		await gust.getByTestId(WT.grenzenAendern('gust')).click();
		await gust.getByTestId(WT.grenze('gust', 'upper', 'yellow')).fill(String(soll.yellow));
		await gust.getByTestId(WT.grenzenAendern('gust')).click();
		await expect.poll(() => abweichungen(reiter)).toBe(1);

		// Länger als die Speicher-Entprellung (700 ms).
		await page.waitForTimeout(1500);
		expect(speichernd(alle), 'AC-15: vor dem Anlegen gespeichert').toEqual([]);
		expect(fragen(), 'Eingaben fragen die Auflösung').toBe(nachLaden);

		await sel.reiter(page, 'zustellung').click();
		const post = page.waitForResponse((r) => r.request().method() === 'POST' && new URL(r.url()).pathname === sel.postPfad, { timeout: 30_000 });
		await sel.abschluss(page).click();
		expect((await post).ok(), 'Anlege-POST').toBeTruthy();
		await expect.poll(() => id).not.toBe('');
		const gespeichert = speichernd(alle);
		expect(gespeichert.map((a) => `${a.methode} ${a.pfad}`), 'genau ein Anlege-POST').toEqual([`POST ${sel.postPfad}`]);

		const ampel = { template: VORLAGE, metrics: { gust: { upper: soll } } };
		expect(gespeichert[0].rumpf.display_config.ampel, 'Ampel im Anlege-POST').toEqual(ampel);
		const abo = await stand(page.request, kind, id);
		expect(abo.display_config.ampel, 'Ampel im Abo').toEqual(ampel);
		expect(auswahlImStand(kind, abo), 'Auswahl im Abo').toEqual(await sollAuswahl(page.request, kind, v));

		const hub = await oeffneWetter(page, kind, id);
		await expect(hub.getByTestId(WT.picker)).toContainText(v.label);
		expect(await abweichungen(hub)).toBe(1);
	});
}
