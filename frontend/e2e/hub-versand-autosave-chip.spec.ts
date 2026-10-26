// E2E — Issue #2347 S1 (Epic #2345, Etappe P6): Versand-Autosave + geteilter
// Speicher-Chip — EINE Zusicherung für BEIDE Hubs (Trip und Ortsvergleich) per
// Schleife über HUB_KINDS.
//
// Spec: docs/specs/modules/feat_2347_s1_paritaets_e2e.md § AC-1
//
// Ersetzt: AC-1 aus compare-versand-speichert-selbst.spec.ts (Fall `vergleich`)
// und den Versand-Anhang aus AC-11 (Trip) in trip-hub-kopf-region-aktivitaet.spec.ts
// (Fall `route`). Zusätzlich neu für beide: der Wert überlebt das Neuladen.
//
// Kein `waitForTimeout`: „genau ein PUT" wird mit `page.reload()` als Schranke
// geprüft — der Request-Listener der Seite überlebt das Neuladen, ein verspäteter
// zweiter PUT derselben Geste wäre bis dahin abgeschickt.
//
// Läuft im isolierten CI-Stack (frontend/e2e/ci-stack.sh) bzw. gegen Staging,
// Anmeldung über den storageState aus global.setup.ts (Admin-Sitzung).

import { test, expect, type Page, type Request } from '@playwright/test';
import { HUB_KINDS, hubApiPath, openHub, seedHub, type HubKind } from './helpers';

// Selektor-/Feldpfad-Unterschiede je kind — bewusst im Spec, nicht im Helfer.
const HUB_SEL: Record<HubKind, { morningTime: (stand: Record<string, unknown>) => unknown }> = {
	route: { morningTime: (s) => (s.report_config as Record<string, unknown> | undefined)?.morning_time },
	vergleich: { morningTime: (s) => s.morning_time }
};

/** Zählt die PUTs auf genau dieses Objekt (abgeschickt bzw. beantwortet). */
function zaehlePuts(page: Page, pfad: string): { puts: Request[]; beantwortet: Request[] } {
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

const morgenUhrzeit = (page: Page) =>
	page.locator('[data-testid="versand-abschnitt"]:visible [data-testid="report-morning-time"]:visible');

for (const kind of HUB_KINDS) {
	test(`AC-1 (${kind}): Versand-Uhrzeit 06:00 → 08:00 ⇒ genau ein PUT, Chip „Gespeichert HH:MM", Stand 08:00, überlebt Neuladen`, async ({
		page
	}) => {
		await page.setViewportSize({ width: 1280, height: 900 });
		const hub = await seedHub(page.request, kind);
		try {
			const pfad = hubApiPath(kind, hub.id);
			const { puts, beantwortet } = zaehlePuts(page, pfad);

			await openHub(page, kind, hub.id, { tab: 'wetter-metriken', hash: 'versand' });
			await expect(page.locator('[data-testid="versand-abschnitt"]:visible')).toBeVisible({ timeout: 10_000 });
			const uhrzeit = morgenUhrzeit(page);
			await expect(uhrzeit).toBeVisible({ timeout: 10_000 });
			await expect(uhrzeit, 'Vorbedingung: geseedet mit 06:00').toHaveValue('06:00');
			expect(puts.length, 'Vorbedingung: das Öffnen des Abschnitts speichert nichts').toBe(0);

			await uhrzeit.selectOption('08:00');

			await expect.poll(() => beantwortet.length, { timeout: 10_000 }).toBeGreaterThanOrEqual(1);
			const chip = page.locator('[data-testid="save-indicator"]');
			await expect(chip).toHaveAttribute('data-state', 'idle', { timeout: 10_000 });
			await expect(chip).toContainText('Gespeichert');
			await expect(chip.locator('.save-time')).toHaveText(/^\d{2}:\d{2}$/);

			const res = await page.request.get(pfad);
			expect(res.ok(), `GET ${pfad} HTTP ${res.status()}`).toBeTruthy();
			const stand = (await res.json()) as Record<string, unknown>;
			expect(String(HUB_SEL[kind].morningTime(stand)), 'gespeicherter Stand trägt 08:00').toMatch(/^08:00/);

			// Schranke für einen verspäteten zweiten PUT derselben Geste (kein Schlaf).
			await page.reload();
			await expect(uhrzeit).toBeVisible({ timeout: 10_000 });
			await expect(uhrzeit, 'Wert überlebt das Neuladen').toHaveValue('08:00');
			expect(puts.length, 'eine Geste im Versand-Abschnitt darf nur EINEN PUT auslösen').toBe(1);
		} finally {
			await hub.aufraeumen();
		}
	});
}
