// E2E — Issue #2795 S3b, Teilschritt 1b (Reiter Zustellung): Abschnitte, Uebergangsblock, entfernte Doppelungen, Spruenge.
// Spec: docs/specs/modules/feat_2795_s3b_teil1_zustellung.md — AC-1/AC-37 (Marker, Reihenfolge), AC-27, AC-30, AC-31,
// AC-39 (U2 „Bearbeiten →“, V13 bleibt in der Uebersicht), AC-40 (K13-Ziel `?tab=zustellung#versand`, Alt-Kennungen)
// Derselbe Test-Code fuer Trip (route) und Orts-Briefing (vergleich).
//
// AC-37/AC-38 selbst (Elementlisten-Abgleich, Soll/Ist-Bild) laufen in /e2e-verify ueber
// `npm run elementliste:abgleich -- --scope zustellung` und den Agenten mockup-bildpruefer; hier nur die Marker.
//
//   cd frontend && npx playwright test --config playwright.2795-s3b1b.staging.config.ts s3b2795-zustellung-uebergang

import { test, expect, type Locator, type Page } from '@playwright/test';
import { HUB_KINDS, HUB_SEL, openHub, type HubKind } from './helpers';
import { DESKTOP, MARKER, ZT, oeffneZustellung, seedZustellung } from './s3b2795-zustellung.helpers';

const VERSAND_EDIT = { route: 'hub-uebersicht-versand-edit', vergleich: 'compare-hub-versand-edit' } as const;

async function imSichtfenster(page: Page, el: Locator): Promise<boolean> {
	const box = await el.boundingBox();
	const vp = page.viewportSize();
	return !!box && !!vp && box.y < vp.height && box.y + box.height > 0;
}

/** Text des Reiters ausserhalb des Uebergangsblocks (dort steht Inhalt je Kanal bis Teil 2). */
async function textOhneUebergang(reiter: Locator): Promise<string> {
	const teile: string[] = [];
	for (const m of MARKER.filter((x) => x !== 'uebergang')) {
		for (const el of await reiter.locator(`[data-abschnitt="${m}"]`).all()) teile.push(await el.innerText());
	}
	return teile.join('\n');
}

const reiterPanel = (page: Page, kind: HubKind) => page.locator(`[data-testid="${HUB_SEL[kind].panel}-zustellung"]:visible`).first();

for (const kind of HUB_KINDS) {
	test(`AC-1/AC-37/AC-30 (${kind}): Abschnitte in Mockup-Reihenfolge, Uebergangsblock am Ende`, async ({ page }) => {
		await page.setViewportSize(DESKTOP);
		const hub = await seedZustellung(page.request, kind);
		try {
			const reiter = await oeffneZustellung(page, kind, hub.id);
			const ys: number[] = [];
			for (const m of MARKER) {
				const el = reiter.locator(`[data-abschnitt="${m}"]`).first();
				await expect(el, `Abschnitt ${m} fehlt`).toBeVisible();
				ys.push((await el.boundingBox())!.y);
			}
			expect([...ys].sort((a, b) => a - b), `Reihenfolge ${MARKER.join(' → ')}`).toEqual(ys);

			const ueb = reiter.getByTestId(ZT.uebergang);
			await expect(ueb).toHaveAttribute('data-abschnitt', 'uebergang');
			await expect(ueb, 'Beispiel-Alarm (bis S5) im Uebergangsblock').toContainText('Beispiel-Warnung');
			await expect(ueb.locator('#versand'), 'kein alter Versand-Abschnitt im Uebergangsblock').toHaveCount(0);
		} finally {
			await hub.aufraeumen();
		}
	});

	test(`AC-27/AC-31 (${kind}): keine Kanaele je Wettergroesse, keine amtlichen Warnungen/Radar, kein „Alarm ab“, eine Kanalauswahl`, async ({ page }) => {
		await page.setViewportSize(DESKTOP);
		const hub = await seedZustellung(page.request, kind);
		try {
			const reiter = await oeffneZustellung(page, kind, hub.id);
			await expect(reiter.getByText('Kanäle je Wettergröße')).toHaveCount(0);
			const text = await textOhneUebergang(reiter);
			expect(text).not.toMatch(/Amtliche Warnungen/);
			expect(text).not.toMatch(/Radar/);
			expect(text).not.toMatch(/Alarm ab\b/);
			await expect(reiter.locator('[data-testid="alert-channel-picker"]'), 'keine zweite Alarm-Kanalauswahl').toHaveCount(0);
			await expect(reiter.getByTestId(ZT.tabelle)).toHaveCount(1);
			expect(text, 'V13: „Nächstes Briefing“ steht in der Uebersicht, nicht im Reiter').not.toMatch(/Nächstes Briefing/);
		} finally {
			await hub.aufraeumen();
		}
	});

	test(`AC-39 (${kind}): Uebersicht „Bearbeiten →“ landet im Reiter Zustellung an den Briefing-Zeiten (#versand)`, async ({ page }) => {
		await page.setViewportSize(DESKTOP);
		const hub = await seedZustellung(page.request, kind);
		try {
			await openHub(page, kind, hub.id, { tab: 'uebersicht' });
			await page.locator(`[data-testid="${VERSAND_EDIT[kind]}"]:visible`).first().click();
			await expect.poll(() => new URL(page.url()).searchParams.get('tab')).toBe('zustellung');
			await expect.poll(() => new URL(page.url()).hash).toBe('#versand');
			const reiter = reiterPanel(page, kind).getByTestId(ZT.tab);
			const karte = reiter.locator('[data-abschnitt="briefing-zeiten"]').first();
			await expect(karte).toBeVisible({ timeout: 15_000 });
			await expect.poll(() => imSichtfenster(page, karte), { message: 'Briefing-Zeiten-Karte im Sichtfenster' }).toBe(true);
			await expect(page.locator('#versand')).toHaveCount(1);
		} finally {
			await hub.aufraeumen();
		}
	});

	test(`AC-40 (${kind}): Sprungziel ?tab=zustellung#versand und Alt-Kennungen versand/alarme fuehren auf den Reiter`, async ({ page }) => {
		await page.setViewportSize(DESKTOP);
		const hub = await seedZustellung(page.request, kind);
		try {
			const basis = kind === 'route' ? `/trips/${hub.id}` : `/compare/${hub.id}`;
			await page.goto(`${basis}?tab=zustellung#versand`);
			const reiter = reiterPanel(page, kind).getByTestId(ZT.tab);
			const karte = reiter.locator('[data-abschnitt="briefing-zeiten"]').first();
			await expect(karte).toBeVisible({ timeout: 15_000 });
			await expect.poll(() => imSichtfenster(page, karte)).toBe(true);
			for (const alt of ['versand', 'alarme']) {
				await page.goto(`${basis}?tab=${alt}`);
				await expect.poll(() => new URL(page.url()).searchParams.get('tab'), { message: `?tab=${alt}` }).toBe('zustellung');
				await expect(reiterPanel(page, kind).getByTestId(ZT.tab)).toBeVisible({ timeout: 15_000 });
			}
		} finally {
			await hub.aufraeumen();
		}
	});
}
