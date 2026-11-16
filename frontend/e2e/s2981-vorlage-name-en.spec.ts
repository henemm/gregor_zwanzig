// E2E — Issue #2981: eingebaute Wetter-Vorlagennamen zweisprachig (Reiter Wetter, Vorlage-Karte).
// Spec: docs/specs/modules/fix_2981_vorlage_name_en.md (AC-1 bis AC-4 auf Staging; AC-5/6/7 Kern-Schicht).
//   cd frontend && npx playwright test --config playwright.2981.staging.config.ts
import { test, expect, type Page } from '@playwright/test';
import { DESKTOP, WT, aktiveDerVorlage, oeffneWetter, seedWetter, vorlagen } from './s3a2794-teil3.helpers';
import type { HubKind } from './helpers';

const EN: Record<string, string> = {
	'alpen-trekking': 'Alpine trekking',
	wandern: 'Hiking',
	skitouren: 'Ski touring',
	wintersport: 'Winter sports',
	radtour: 'Cycling',
	wassersport: 'Water sports',
	allgemein: 'General'
};
const DE: Record<string, string> = {
	'alpen-trekking': 'Alpen-Trekking',
	wandern: 'Wandern',
	skitouren: 'Skitouren',
	wintersport: 'Wintersport',
	radtour: 'Radtour',
	wassersport: 'Wassersport',
	allgemein: 'Allgemein'
};

async function sprache(page: Page, lang: 'de' | 'en'): Promise<void> {
	const r = await page.request.put('/api/auth/profile', { data: { language: lang } });
	expect(r.ok(), `Sprache ${lang}: HTTP ${r.status()}`).toBeTruthy();
}

for (const kind of ['route', 'vergleich'] as HubKind[]) {
	for (const lang of ['en', 'de'] as const) {
		const N = lang === 'en' ? EN : DE;
		const ANDERE = lang === 'en' ? DE : EN;
		test(`AC-1/2/3 (${kind}, ${lang}): Karte, Auswahl, Rückfrage, Verlust-Text und Zurücksetzen`, async ({ page }) => {
			await page.setViewportSize(DESKTOP);
			const v = (await vorlagen(page.request))['wandern'];
			const auswahl = aktiveDerVorlage(v).slice(1); // eine Abweichung => Zurücksetzen + Verlust-Text
			const hub = await seedWetter(page.request, kind, { vorlageId: 'wandern', auswahl });
			try {
				await sprache(page, lang);
				const reiter = await oeffneWetter(page, kind, hub.id);
				const picker = reiter.getByTestId(WT.picker);
				await expect(picker).toContainText(N['wandern']);
				await expect(picker).not.toContainText(ANDERE['wandern']);
				const reset = reiter.getByTestId(WT.zuruecksetzen);
				await expect(reset).toBeVisible();
				await expect(reset).toContainText(N['wandern']);
				await picker.click();
				let gesehen = 0;
				for (const [id, name] of Object.entries(N)) {
					const opt = reiter.getByTestId(WT.vorlageOption(id));
					if ((await opt.count()) === 0) continue;
					gesehen++;
					await expect(opt.locator('span').first(), `Option ${id}`).toHaveText(name);
				}
				expect(gesehen, 'mindestens die eingebauten Vorlagen sind gelistet').toBeGreaterThanOrEqual(5);
				await reiter.getByTestId(WT.vorlageOption('radtour')).click();
				const dialog = reiter.getByTestId(WT.wechselDialog);
				await expect(dialog).toBeVisible();
				await expect(dialog).toContainText(N['radtour']);
				await expect(dialog).toContainText(N['wandern']); // Verlust-Text nennt die alte Vorlage
				await expect(dialog).not.toContainText(ANDERE['radtour']);
				await reiter.getByTestId(WT.wechselAbbrechen).click();
			} finally {
				await sprache(page, 'de').catch(() => {});
				await hub.aufraeumen();
			}
		});
	}
}

test('AC-4 (route): eigene Vorlage behält ihren Namen in EN und DE', async ({ page }) => {
	await page.setViewportSize(DESKTOP);
	const NAME = `E2E-GZ-2981 Mein Wochenende ${Date.now() % 100000}`;
	const hub = await seedWetter(page.request, 'route', { vorlageId: 'wandern' });
	try {
		const reiter = await oeffneWetter(page, 'route', hub.id);
		await reiter.getByTestId(WT.alsEigene).click();
		await page.getByTestId(WT.dialogName).fill(NAME);
		await page.getByTestId(WT.dialogSpeichern).click();
		await expect(reiter.getByTestId(WT.dialogErfolg)).toBeVisible({ timeout: 15_000 });
		for (const lang of ['en', 'de'] as const) {
			await sprache(page, lang);
			const r = await oeffneWetter(page, 'route', hub.id);
			await r.getByTestId(WT.picker).click();
			await expect(r.getByTestId(WT.eigeneGruppe)).toContainText(NAME);
		}
	} finally {
		await sprache(page, 'de').catch(() => {});
		const l = await page.request.get('/api/metric-presets');
		if (l.ok()) {
			for (const p of (await l.json()) as { id: string; name: string }[]) {
				if (p.name?.startsWith('E2E-GZ-2981')) await page.request.delete(`/api/metric-presets/${p.id}`).catch(() => {});
			}
		}
		await hub.aufraeumen();
	}
});
