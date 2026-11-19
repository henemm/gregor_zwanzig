// E2E — Issue #2347 S3d (Epic #2345, Etappe P6): Metrik-Reihenfolge per Ziehen im Hub —
// EINE Zusicherung für BEIDE Hubs (Trip und Ortsvergleich) per Schleife über HUB_KINDS.
// Die Reihenfolge-Karte ist in beiden Kontexten DERSELBE Baustein (WeatherV2Reihenfolge,
// WeatherMetricsTab.svelte); nur Zeilen-Kennungen und Zielfeld sind je kind verschieden.
//
// Spec: docs/specs/modules/feat_2347_s3d_paritaets_e2e.md § AC-8 (RO-1, RO-2)
//
// Ersetzt compare-metric-order.spec.ts (Alt AC-3 → RO-1, Alt AC-6 → RO-2). Die veraltete
// Vorbedingung „keine wm2-aus-gruppe im Vergleich" entfällt (seit #1703 S8 gilt „Aus ist
// ein Zustand" auch dort, Spec Entscheidung 7). Trip-Vorbild: layout-tab-route.spec.ts AC-3.
//
// Kein fester Schlaf: der Speichervorgang wird über die abgewartete PUT-ANTWORT belegt,
// nicht über die Bildschirm-Optik. Anmeldung über den storageState aus global.setup.ts.
//
// #3154 (#3122 B3b, Spec feat_3122_was_steht_wo.md Teil B Nr. 13/14, AC-24): die Kanal-Reihenfolge-Karte
// des Übergangsblocks (Reiter Zustellung) ist entfernt. Es gibt EINE Reihenfolge für alle Stellen, gezogen
// in der Karte „Was steht wo“ im Reiter Wetter (Griff je Zeile, SortableList), gespeichert als `rows` der
// Tabelle (PUT /api/briefings/{id}/placements). RO-1/RO-2 laufen dort; Ausgangsreihenfolge ist die Folge
// der gespeicherten Grundauswahl, die die Karte ohne gespeicherte Tabelle zeigt.

import { test, expect, type Locator, type Page } from '@playwright/test';
import { HUB_KINDS, HUB_SEL, openHub, seedHub, type HubKind } from './helpers';

/** Kind-Kontraste (Spec): Seed je Abo-Art; drei Metriken ohne Auffächerung. */
const RO_SEL: Record<HubKind, { seed: Record<string, unknown>; start: [string, string, string] }> = {
	route: {
		seed: {
			display_config: {
				metrics: [
					{ metric_id: 'wind', enabled: true, bucket: 'primary', order: 0 },
					{ metric_id: 'precipitation', enabled: true, bucket: 'primary', order: 1 },
					{ metric_id: 'gust', enabled: true, bucket: 'primary', order: 2 }
				]
			}
		},
		start: ['wind', 'precipitation', 'gust']
	},
	vergleich: {
		seed: { display_config: { active_metrics: ['temp_max_c', 'wind_max_kmh', 'sunny_hours_h'] } },
		start: ['temp_max_c', 'wind_max_kmh', 'sunny_hours_h']
	}
};

const tabellenPfad = (id: string) => `/api/briefings/${id}/placements`;

/** Reihenfolge der Zeilen laut Endpoint (als dieser Nutzer). */
async function serverFolge(page: Page, kind: HubKind, id: string): Promise<string[]> {
	const r = await page.request.get(`${tabellenPfad(id)}?kind=${kind}`);
	expect(r.ok(), `GET Tabelle HTTP ${r.status()}`).toBeTruthy();
	return ((await r.json()).rows as Array<{ metric_id: string }>).map((x) => x.metric_id);
}

const zeilen = (karte: Locator) => karte.locator('[data-slot="et-zeile"]');
const zeilenIds = (karte: Locator) => zeilen(karte).evaluateAll((els) => els.map((el) => el.getAttribute('data-metrik')!));

async function oeffneKarte(page: Page, kind: HubKind, id: string): Promise<Locator> {
	await openHub(page, kind, id, { tab: 'wetter' });
	const karte = page.locator('[data-testid="was-steht-wo"]:visible');
	await expect(karte.getByTestId('was-steht-wo-tabelle'), 'Die Tabelle „Was steht wo“ muss im Reiter Wetter stehen').toBeVisible({ timeout: 20_000 });
	return karte;
}

for (const kind of HUB_KINDS) {
	const ro = RO_SEL[kind];
	const sel = HUB_SEL[kind];

	test.describe(`Hub · Metrik-Reihenfolge ziehen (${kind})`, () => {
		test.beforeEach(async ({ page }) => {
			await page.setViewportSize({ width: 1440, height: 900 });
		});

		// RO-1 — Alt compare-metric-order AC-3. Fängt: Ziehen ruft den Speicherweg nicht auf, Server
		// speichert die alte Reihenfolge, Neuladen zeigt die alte Reihenfolge.
		test(`RO-1 (${kind}): dritte Zeile vor die erste ziehen → PUT-Antwort, Server trägt die Reihenfolge, Neuladen zeigt sie`, async ({
			page
		}) => {
			const hub = await seedHub(page.request, kind, { extra: ro.seed });
			try {
				const karte = await oeffneKarte(page, kind, hub.id);
				const start = await serverFolge(page, kind, hub.id);
				expect(start.length, 'Vorbedingung: drei Zeilen laut Seed').toBe(ro.start.length);
				await expect.poll(() => zeilenIds(karte), { message: 'Vorbedingung: Karte zeigt die Folge des Endpoints' }).toEqual(start);
				const nachZug = [start[2], start[0], start[1]];

				// Nur ZIEHEN — keine Metrik an- oder abwählen. Antwort VOR der Geste vormerken.
				const antwort = page.waitForResponse((r) => r.request().method() === 'PUT' && new URL(r.url()).pathname === tabellenPfad(hub.id), { timeout: 15_000 });
				const mitte = async (l: Locator) => {
					const b = (await l.boundingBox())!;
					return { x: b.x + b.width / 2, y: b.y + b.height / 2 };
				};
				const griff = (m: string) => karte.locator(`[data-slot="et-zeile"][data-metrik="${m}"]`).getByTestId('drag-handle');
				await karte.locator(`[data-slot="et-zeile"][data-metrik="${start[0]}"]`).scrollIntoViewIfNeeded();
				const von = await mitte(griff(start[2]));
				const nach = await mitte(griff(start[0]));
				await page.mouse.move(von.x, von.y);
				await page.mouse.down();
				await page.mouse.move(von.x, von.y - 12, { steps: 6 });
				await page.mouse.move(nach.x, nach.y, { steps: 15 });
				await expect
					.poll(() => zeilenIds(karte), { message: 'RO-1 FAIL: die gezogene Zeile steht nicht an der neuen Position', timeout: 5_000 })
					.toEqual(nachZug);
				await page.mouse.up();

				const res = await antwort.catch(() => null);
				expect(res, 'RO-1 FAIL: nach der Ziehgeste feuert kein PUT').not.toBeNull();
				expect(res!.status(), 'RO-1 FAIL: der Speichervorgang wurde nicht mit 200 beantwortet').toBe(200);

				await expect
					.poll(() => serverFolge(page, kind, hub.id), { timeout: 10_000, message: 'RO-1 FAIL: der Server trägt die neue Reihenfolge nicht' })
					.toEqual(nachZug);

				const nachLaden = await oeffneKarte(page, kind, hub.id);
				await expect
					.poll(() => zeilenIds(nachLaden), { timeout: 10_000, message: 'RO-1 FAIL: nach dem Neuladen steht wieder die alte Reihenfolge' })
					.toEqual(nachZug);
			} finally {
				await hub.aufraeumen();
			}
		});

		// RO-2 — Alt compare-metric-order AC-6. „Amtliche Warnungen" ist KEINE ziehbare Zeile (beide kinds):
		// in der Karte eine feste Zeile ohne Griff über den Metrik-Zeilen.
		test(`RO-2 (${kind}): „Amtliche Warnungen" ist keine ziehbare Zeile`, async ({ page }) => {
			const hub = await seedHub(page.request, kind, { extra: ro.seed });
			try {
				const karte = await oeffneKarte(page, kind, hub.id);
				await expect(zeilen(karte)).toHaveCount(ro.start.length, { timeout: 10_000 });
				const ids = await zeilenIds(karte);
				expect(ids.filter((i) => /official|warn/i.test(i)), 'RO-2 FAIL: „Amtliche Warnungen" darf keine ziehbare Zeile sein').toEqual([]);
				const fest = karte.locator('[data-slot="et-fest"]');
				await expect(fest).toHaveCount(1);
				await expect(fest).toContainText('Amtliche Warnungen');
				await expect(fest.getByTestId('drag-handle'), 'RO-2 FAIL: die feste Zeile hat einen Griff').toHaveCount(0);
				// Der Hub ist offen (Kontrolle gegen leeren Treffer durch falsche Seite).
				await expect(page.getByTestId(sel.reiterListe)).toBeVisible();
			} finally {
				await hub.aufraeumen();
			}
		});
	});
}
