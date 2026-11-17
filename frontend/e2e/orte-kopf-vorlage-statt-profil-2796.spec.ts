// E2E — Issue #2796 S4a (ADR-0108 P3): Orts-Vergleich — Profil-Kacheln im Kopf entfallen,
// die Vorlage ersetzt das Profil in Übersicht und Liste.
// Spec: docs/specs/modules/feat_2796_s4a_orte_vorlage_statt_profil.md (AC-1, AC-2, AC-7)
//
//   AC-1: Desktop 1280×900, DE und EN — keine `compare-hub-profil-*`, kein Profilname hinter der
//         Region, Meta-Zeile mit Orte-Anzahl bleibt.
//   AC-2: Handy 390×844 — kein `compare-hub-profil-knopf`, keine `compare-hub-profil-auswahl`.
//   AC-7: Übersicht nennt die Vorlage (nicht das Profil); Vorlagenwechsel → neu laden → neuer Name.
// Der Trip-Kopf (AC-3) bleibt unverändert: hub-kopf-aufbau.spec.ts / hub-kopf-bearbeiten.spec.ts.
//
// Wegwerf-Daten räumt jeder Fall im `finally` ab; die Kontosprache wird auf `de` zurückgesetzt.

import { test, expect, type Page } from '@playwright/test';
import { openHub, seedHub } from './helpers';

const DESKTOP = { width: 1280, height: 900 };
const HANDY = { width: 390, height: 844 };
const REGION = 'Ötztal';
// Gespeichertes Profil weicht bewusst von der Vorlage ab (Wandern vs. Wintersport).
const SEED = { profil: 'wandern', display_config: { region: REGION, ampel: { template: 'wintersport' } } };
const NAME = {
	de: { profil: 'Wandern', vorlage: 'Wintersport', orte: /^\d+ Orte? · / },
	en: { profil: 'Hiking', vorlage: 'Winter sports', orte: /^\d+ locations? · / }
} as const;

async function sprache(page: Page, lang: 'de' | 'en'): Promise<void> {
	const res = await page.request.put('/api/auth/profile', { data: { language: lang } });
	expect(res.ok(), `Sprache ${lang} setzen: HTTP ${res.status()}`).toBeTruthy();
}

async function keinProfilImKopf(page: Page): Promise<void> {
	// Zählung OHNE :visible — auch eine ausgeblendete Kachel/Knopf-Instanz wäre ein Befund.
	expect(await page.locator('[data-testid^="compare-hub-profil"]').count(), 'Profil-Bedienelemente im Kopf').toBe(0);
}

for (const lang of ['de', 'en'] as const) {
	test(`AC-1 (${lang}): Desktop 1280 — Orte-Kopf ohne Profil-Kacheln und ohne Profilnamen`, async ({ page }) => {
		await page.setViewportSize(DESKTOP);
		const hub = await seedHub(page.request, 'vergleich', { extra: SEED });
		try {
			await sprache(page, lang);
			for (const tab of [undefined, 'wetter', 'zustellung']) {
				await openHub(page, 'vergleich', hub.id, tab ? { tab } : {});
				await expect(page.locator('[data-testid="compare-hub-region-edit-toggle"]:visible')).toBeVisible({ timeout: 10_000 });
				await keinProfilImKopf(page);
				const zeile = page.locator('[data-testid="compare-hub-region-edit-toggle"]:visible').locator('xpath=..');
				await expect(zeile).toContainText(REGION);
				await expect(zeile).not.toContainText(NAME[lang].profil);
				await expect(page.getByTestId('hub-kopf-meta')).toHaveText(NAME[lang].orte);
				await expect(page.locator('[data-testid="compare-hub-name-edit-toggle"]:visible')).toBeVisible();
			}
		} finally {
			await sprache(page, 'de').catch(() => {});
			await hub.aufraeumen();
		}
	});
}

test('AC-2: Handy 390 — kein Profil-Knopf und keine Profil-Auswahl', async ({ page }) => {
	await page.setViewportSize(HANDY);
	const hub = await seedHub(page.request, 'vergleich', { extra: SEED });
	try {
		await openHub(page, 'vergleich', hub.id);
		await expect(page.locator('[data-testid="compare-hub-region-edit-toggle"]:visible')).toBeVisible({ timeout: 10_000 });
		expect(await page.locator('[data-testid="compare-hub-profil-knopf"]').count()).toBe(0);
		expect(await page.locator('[data-testid="compare-hub-profil-auswahl"]').count()).toBe(0);
		await keinProfilImKopf(page);
	} finally {
		await hub.aufraeumen();
	}
});

test('AC-7: Übersicht nennt die Vorlage, nach Vorlagenwechsel den neuen Namen', async ({ page }) => {
	await page.setViewportSize(HANDY);
	const hub = await seedHub(page.request, 'vergleich', { extra: SEED });
	const pfad = `/api/compare/presets/${hub.id}`;
	const wetterZeile = () => page.locator('[data-testid="hub-summary-row-mobile"]:visible').nth(1);
	try {
		await openHub(page, 'vergleich', hub.id);
		await expect(wetterZeile()).toContainText(NAME.de.vorlage, { timeout: 10_000 });
		await expect(wetterZeile()).not.toContainText(NAME.de.profil);

		// Vorlagenwechsel per Read-Modify-Write (nur ampel.template ändert sich).
		const stand = (await (await page.request.get(pfad)).json()) as { display_config?: Record<string, unknown> };
		const dc = { ...(stand.display_config ?? {}), ampel: { ...((stand.display_config?.ampel as object) ?? {}), template: 'alpen-trekking' } };
		const res = await page.request.put(pfad, { data: { display_config: dc } });
		expect(res.ok(), `Vorlage wechseln: HTTP ${res.status()}`).toBeTruthy();

		await page.reload();
		await expect(wetterZeile()).toContainText('Alpen-Trekking', { timeout: 10_000 });
		await expect(wetterZeile()).not.toContainText(NAME.de.vorlage);
	} finally {
		await hub.aufraeumen();
	}
});
