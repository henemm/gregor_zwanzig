// gz-eigenstaendig: Regressionsnachweis der Compare-Verdrahtung (CompareTabs reichte die eingefrorene Seiten-Prop an HubUebersicht); der Trip-Hub reicht seit jeher den lebenden `trip` (TripTabs.svelte), sein Gegenstueck ist compare-hub-fidelity-s8c.spec.ts UE-1/UE-2
// E2E — Issue #2828 (B1-46, Epic #2345): die Übersicht im Ortsvergleich-Hub zeigt
// den LEBENDEN Stand. Nach einer gespeicherten Änderung in einem Reiter (Orte,
// Wertebereiche, Versand) und nach Pausieren zeigt die Übersicht den neuen Stand,
// OHNE dass die Seite neu geladen wird.
//
// Spec: docs/specs/bugfix/bug_2828_compare_uebersicht_stale.md § AC-2, AC-3, AC-5 (AC-1 per Verdrahtungs-Test, Editor seit #2792 gesperrt)
//
// „Ohne Neuladen" wird belegt, nicht angenommen: vor der Änderung wird ein Merker im
// `window` gesetzt; ein Neuladen würde ihn verwerfen, am Ende muss er noch stehen.
//
// Diskriminierend gegen den Alt-Code (Seiten-Prop `preset` an HubUebersicht):
//   AC-3 (Briefings-Kennzahl). AC-2 (Orte-Karte) war schon
//   vorher lebend (`resolvedLocations`) und läuft hier als Regressionsschutz mit; AC-5
//   (Status) prüft das Zusammenspiel `currentPreset` + lokaler Pausier-Override.
//
// Läuft im isolierten CI-Stack bzw. in /e2e-verify gegen Staging (storageState aus
// global.setup.ts). Wegwerf-Objekte E2E-GZ-, Aufräumen im finally. Wartebedingungen
// nur waitForResponse / expect-Polling, kein fester Schlaf.

import { test, expect, type Locator, type Page } from '@playwright/test';
import { createTestLocation, hubApiPath, openHub, seedHub } from './helpers';

const DESKTOP = { width: 1280, height: 900 };

type Stand = Record<string, unknown>;

const uebersicht = (page: Page): Locator =>
	page.locator('[data-testid="compare-detail-panel-uebersicht"]:visible').first();

async function zurUebersicht(page: Page): Promise<Locator> {
	await page.locator('[data-testid="compare-detail-tab-uebersicht"]:visible').first().click();
	const p = uebersicht(page);
	await expect(p).toBeVisible({ timeout: 10_000 });
	return p;
}

/** Merker gegen Neuladen: steht er am Ende noch, wurde die Seite nicht neu geladen. */
async function setzeKeinReloadMerker(page: Page): Promise<void> {
	await page.evaluate(() => {
		(window as unknown as Record<string, unknown>).__gz2828KeinReload = true;
	});
}

async function erwarteKeinReload(page: Page): Promise<void> {
	const steht = await page.evaluate(
		() => (window as unknown as Record<string, unknown>).__gz2828KeinReload === true
	);
	expect(steht, 'die Seite wurde neu geladen — „ohne Neuladen" ist nicht belegt').toBe(true);
}

function putAntwort(page: Page, id: string) {
	const pfad = hubApiPath('vergleich', id);
	return page.waitForResponse((r) => r.request().method() === 'PUT' && new URL(r.url()).pathname === pfad);
}

async function stand(page: Page, id: string): Promise<Stand> {
	const res = await page.request.get(hubApiPath('vergleich', id));
	expect(res.ok(), `GET ${hubApiPath('vergleich', id)} HTTP ${res.status()}`).toBeTruthy();
	return (await res.json()) as Stand;
}

test.describe('#2828: Compare-Übersicht zeigt den lebenden Stand ohne Neuladen', () => {
	test.beforeEach(async ({ page }) => {
		await page.setViewportSize(DESKTOP);
	});

	// AC-3 — fängt: HubUebersicht bekommt die eingefrorene Prop `preset` statt `currentPreset`.
	test('AC-3: Briefing-Zeit im Versand ändern ⇒ Briefings-Kennzahl der Übersicht zeigt die neue Zeit', async ({
		page
	}) => {
		const hub = await seedHub(page.request, 'vergleich');
		try {
			await openHub(page, 'vergleich', hub.id);
			const briefings = page.locator('[data-testid="compare-detail-stat-briefings"]:visible');
			await expect(briefings, 'Vorbedingung: Seed-Zeit 06:00').toContainText('06:00', { timeout: 10_000 });
			await setzeKeinReloadMerker(page);

			await openVersandOhneReload(page);
			const morgen = page.locator('[data-testid="versand-abschnitt"]:visible [data-testid="report-morning-time"]:visible');
			await expect(morgen).toBeVisible({ timeout: 10_000 });
			const put = putAntwort(page, hub.id);
			await morgen.selectOption('10:00');
			const res = await put;
			expect(res.ok(), 'PUT nach Uhrzeit-Änderung fehlgeschlagen: ' + res.status()).toBeTruthy();

			await zurUebersicht(page);
			await expect(briefings, 'AC-3: die Übersicht zeigt noch die alte Briefing-Zeit').toContainText('10:00', {
				timeout: 10_000
			});
			await expect(briefings).not.toContainText('06:00');
			await erwarteKeinReload(page);
		} finally {
			await hub.aufraeumen();
		}
	});

	// AC-1 entfällt hier: der Wertebereiche-Editor ist seit #2792 gesperrt (nur lesbar). Der lesende Stand
	// der Wertebereiche-Karte ist durch compare_uebersicht_liest_lebenden_stand.test.ts belegt.

	// AC-2 — Regressionsschutz: Orte-Karte zeigt die neue Ortsliste samt Anzahl.
	test('AC-2: Ort im Reiter Orte entfernen ⇒ Orte-Karte der Übersicht zeigt neue Anzahl und Liste', async ({ page }) => {
		const a = await createTestLocation(page.request, { name: '2828-Ort-A', lat: 47.21, lon: 11.11 });
		const b = await createTestLocation(page.request, { name: '2828-Ort-B', lat: 47.22, lon: 11.12 });
		const hub = await seedHub(page.request, 'vergleich', { extra: { location_ids: [a.id, b.id] } });
		try {
			await openHub(page, 'vergleich', hub.id);
			const p = uebersicht(page);
			await expect(p.getByText('2 Kandidaten'), 'Vorbedingung: zwei Orte').toBeVisible({ timeout: 10_000 });
			await expect(p).toContainText(b.name);
			await setzeKeinReloadMerker(page);

			await page.locator('[data-testid="compare-detail-tab-orte"]:visible').first().click();
			const rows = page.locator('[data-testid="hub-orte-row"]');
			await expect(rows).toHaveCount(2, { timeout: 10_000 });
			const put = putAntwort(page, hub.id);
			await page.locator(`[data-testid="hub-orte-row"][data-loc-id="${b.id}"] [data-testid="hub-orte-remove"]`).click();
			const res = await put;
			expect(res.ok(), 'PUT nach Entfernen fehlgeschlagen: ' + res.status()).toBeTruthy();

			await zurUebersicht(page);
			await expect(p.getByText('1 Kandidaten'), 'AC-2: die Orte-Karte zeigt nicht die neue Anzahl').toBeVisible({
				timeout: 10_000
			});
			await expect(p).toContainText(a.name);
			await expect(p).not.toContainText(b.name);
			await erwarteKeinReload(page);
		} finally {
			await hub.aufraeumen();
			for (const id of [a.id, b.id]) {
				try {
					await page.request.delete(`/api/locations/${id}`);
				} catch {
					/* Staging-Hygiene: Cleanup-Fehler ist nicht test-kritisch */
				}
			}
		}
	});

	// AC-5 — fängt: `status` an HubUebersicht hängt nicht am lebenden Stand bzw. am Override.
	test('AC-5: Pausieren und Aktivieren ⇒ Status-Kennzahl der Übersicht springt sofort um', async ({ page }) => {
		const hub = await seedHub(page.request, 'vergleich');
		try {
			await openHub(page, 'vergleich', hub.id);
			const p = uebersicht(page);
			await expect(p.getByText('Läuft automatisch'), 'Vorbedingung: aktiv').toBeVisible({ timeout: 10_000 });
			await expect(p.getByText('Pausiert', { exact: true })).toHaveCount(0);
			await setzeKeinReloadMerker(page);

			let put = putAntwort(page, hub.id);
			await kebabWaehle(page, 'Pausieren');
			let res = await put;
			expect(res.ok(), 'Pausier-PUT fehlgeschlagen: ' + res.status()).toBeTruthy();
			await expect(p.getByText('Pausiert', { exact: true }), 'AC-5: Status-Kennzahl zeigt nicht „Pausiert"').toBeVisible({
				timeout: 10_000
			});
			await expect(p.getByText('Läuft automatisch')).toHaveCount(0);
			expect((await stand(page, hub.id)).schedule, 'Vorbedingung: gespeichert pausiert').toBe('manual');

			put = putAntwort(page, hub.id);
			await kebabWaehle(page, 'Fortsetzen');
			res = await put;
			expect(res.ok(), 'Aktivier-PUT fehlgeschlagen: ' + res.status()).toBeTruthy();
			await expect(p.getByText('Läuft automatisch'), 'AC-5: Status-Kennzahl springt nicht zurück').toBeVisible({
				timeout: 10_000
			});
			await expect(p.getByText('Pausiert', { exact: true })).toHaveCount(0);
			await erwarteKeinReload(page);
		} finally {
			await hub.aufraeumen();
		}
	});
});

/** Reiterwechsel zum Versand-Abschnitt per Klick (kein page.goto — sonst wäre es ein Neuladen). */
async function openVersandOhneReload(page: Page): Promise<void> {
	await page.locator('[data-testid="compare-detail-tab-zustellung"]:visible').first().click(); // #2794 S3a
	await expect(page.locator('[data-testid="versand-abschnitt"]:visible')).toBeVisible({ timeout: 10_000 });
}

/** Kebab im Hub-Kopf öffnen und Lebenszyklus-Punkt wählen (Muster hub-versand-inline-bearbeiten). */
async function kebabWaehle(page: Page, punkt: 'Pausieren' | 'Fortsetzen'): Promise<void> {
	await page.getByRole('button', { name: 'Weitere Aktionen' }).first().click();
	const eintrag = page.getByRole('menuitem', { name: punkt });
	await expect(eintrag, `Vorbedingung: der Hub bietet „${punkt}" an`).toBeVisible({ timeout: 10_000 });
	await eintrag.click();
}
