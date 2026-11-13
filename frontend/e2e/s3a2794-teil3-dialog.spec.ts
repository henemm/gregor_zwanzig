// E2E — Issue #2794 S3a, Teil-PR 3 (Reiter Wetter): Dialog „Als eigene Vorlage speichern“ (AC-42), zwei Konten.
// Spec: docs/specs/modules/feat_2794_s3a_teil3_wetter.md — AC-42 (W5b), Mandantentrennung
// Derselbe Test-Code fuer Trip (route) und Orts-Briefing (vergleich).
//
//   - Dialog: Name (Pflicht), Beschreibung, Schalter „Als Standard für neue {Trips|Orte}“, Hinweis
//     „Gespeichert werden Metrik-Auswahl, Ampel-Grenzen und Alarmstufen. …“, KEINE Zeithorizonte, KEINE Zusammenfassung.
//   - gespeicherte Vorlage (GET /api/metric-presets) mit `ampel` des Abos und `kind` des Kontexts, ohne horizons;
//     Erfolgsmeldung; erscheint unter „Eigene“ nur in der passenden Art.
//   - vorhandener Name -> „Eine Vorlage ‚{n}‘ gibt es schon. Wähle einen anderen Namen.“
//   - zweites Konto sieht die Vorlage nicht (Mandantentrennung).
//
//   cd frontend && npx playwright test --config playwright.2794-s3a3.staging.config.ts s3a2794-teil3-dialog

import { test, expect, type APIRequestContext } from '@playwright/test';
import { HUB_KINDS, registriereBestaetigtenZweitnutzer, type HubKind } from './helpers';
import { DESKTOP, WT, oeffneWetter, seedWetter, type Json } from './s3a2794-teil3.helpers';
import { wegwerfPasswort } from './stagingZugang';

const STANDARD_TEXT: Record<HubKind, string> = { route: 'Als Standard für neue Trips', vergleich: 'Als Standard für neue Orte' };
const ANDERE: Record<HubKind, HubKind> = { route: 'vergleich', vergleich: 'route' };

async function presets(request: APIRequestContext): Promise<Json[]> {
	const r = await request.get('/api/metric-presets');
	expect(r.ok(), `GET /api/metric-presets: ${r.status()}`).toBeTruthy();
	const b = await r.json();
	return Array.isArray(b) ? b : (b.presets ?? []);
}

const enthaeltHorizons = (x: unknown): boolean =>
	x !== null && typeof x === 'object' && Object.entries(x as Record<string, unknown>).some(([k, v]) => k === 'horizons' || enthaeltHorizons(v));

for (const kind of HUB_KINDS) {
	test(`AC-42 (${kind}): Dialog speichert ampel + kind, ohne Zeithorizonte/Zusammenfassung; Duplikat; nur passende Art`, async ({ page, browser }) => {
		await page.setViewportSize(DESKTOP);
		const hub = await seedWetter(page.request, kind, { vorlageId: 'wandern', ampel: { metrics: { gust: { alarm_ab: 'red' } } } });
		const andererHub = await seedWetter(page.request, ANDERE[kind], { vorlageId: 'wandern' });
		const name = `E2E-GZ-Vorlage-${kind}-${Date.now()}`;
		const angelegt: string[] = [];
		try {
			const reiter = await oeffneWetter(page, kind, hub.id);
			await reiter.getByTestId(WT.alsEigene).click();
			const dialog = page.getByTestId(WT.dialog);
			await expect(dialog).toContainText('Als eigene Vorlage speichern');
			await expect(dialog.getByTestId(WT.dialogName)).toBeVisible();
			await expect(dialog.getByTestId(WT.dialogBeschreibung)).toBeVisible();
			await expect(dialog.getByTestId(WT.dialogStandard)).toContainText(STANDARD_TEXT[kind]);
			await expect(dialog.getByTestId(WT.dialogHinweis)).toHaveText(
				'Gespeichert werden Metrik-Auswahl, Ampel-Grenzen und Alarmstufen. Zustellung, Etappen und Orte gehören nicht dazu.'
			);
			for (const alt of ['save-preset-horizon-summary', 'save-preset-summary', 'save-preset-bucket-summary']) {
				await expect(dialog.getByTestId(alt), `AC-42: ${alt} im Dialog`).toHaveCount(0);
			}

			// Name ist Pflicht
			await dialog.getByTestId(WT.dialogSpeichern).click();
			await expect(dialog.getByTestId(WT.dialogFehler)).toHaveText('Gib der Vorlage einen Namen.');

			await dialog.getByTestId(WT.dialogName).fill(name);
			await dialog.getByTestId(WT.dialogBeschreibung).fill('E2E Beschreibung');
			const post = page.waitForResponse((r) => r.request().method() === 'POST' && new URL(r.url()).pathname === '/api/metric-presets');
			await dialog.getByTestId(WT.dialogSpeichern).click();
			const antwort = await post;
			expect(antwort.ok(), `POST /api/metric-presets: ${antwort.status()}`).toBeTruthy();
			const body = antwort.request().postDataJSON() as Json;
			expect(body.kind).toBe(kind);
			expect(enthaeltHorizons(body), 'AC-42: Body mit Zeithorizonten').toBe(false);
			expect('summary' in body, 'AC-42: Body mit Zusammenfassung').toBe(false);
			await expect(page.getByTestId(WT.dialogErfolg)).toHaveText(`Vorlage ‚${name}‘ gespeichert. Du findest sie unter ‚Eigene‘.`);

			const gespeichert = (await presets(page.request)).find((p) => p.name === name);
			expect(gespeichert, 'Vorlage nicht gespeichert').toBeTruthy();
			angelegt.push(gespeichert.id);
			expect(gespeichert.kind).toBe(kind);
			expect(gespeichert.ampel?.metrics?.gust?.alarm_ab, 'AC-42: ampel des Abos fehlt in der Vorlage').toBe('red');
			expect(enthaeltHorizons(gespeichert)).toBe(false);

			await reiter.getByTestId(WT.picker).click();
			await expect(page.getByTestId(WT.eigeneGruppe)).toContainText(name);
			await page.keyboard.press('Escape');

			// Duplikat
			await reiter.getByTestId(WT.alsEigene).click();
			await page.getByTestId(WT.dialog).getByTestId(WT.dialogName).fill(name);
			await page.getByTestId(WT.dialog).getByTestId(WT.dialogSpeichern).click();
			await expect(page.getByTestId(WT.dialog).getByTestId(WT.dialogFehler)).toHaveText(`Eine Vorlage ‚${name}‘ gibt es schon. Wähle einen anderen Namen.`);
			await page.keyboard.press('Escape');

			// andere Art: nicht unter „Eigene“
			const anders = await oeffneWetter(page, ANDERE[kind], andererHub.id);
			await anders.getByTestId(WT.picker).click();
			await expect(page.getByTestId(WT.eigeneGruppe).getByText(name)).toHaveCount(0);
			await page.keyboard.press('Escape');

			// zweites Konto sieht die Vorlage nicht
			const neu = { baseURL: test.info().project.use.baseURL, storageState: undefined, serviceWorkers: 'block' as const };
			const gast = await browser.newContext(neu);
			try {
				const kennwort = wegwerfPasswort();
				await registriereBestaetigtenZweitnutzer(page.request, gast.request, `e2eteil3dialog${Date.now()}`, kennwort);
				expect((await presets(gast.request)).map((p) => p.name), 'Mandantentrennung: fremde Vorlage sichtbar').not.toContain(name);
				await gast.request.post('/api/auth/account/delete', { data: { password: kennwort } }).catch(() => {});
			} finally {
				await gast.close();
			}
		} finally {
			for (const id of angelegt) await page.request.delete(`/api/metric-presets/${id}`).catch(() => {});
			await hub.aufraeumen();
			await andererHub.aufraeumen();
		}
	});
}
