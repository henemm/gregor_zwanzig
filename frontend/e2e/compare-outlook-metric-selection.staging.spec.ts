// Staging-Validierung — Ortsvergleich-Ausblick: gruppierte Metrik-Auswahl
// (Issue #1406 Scheibe A). Auswahl-Block auf das gruppierte Muster von #1411
// gehoben (24 statt 26 Zeilen). Namensregel (CLAUDE.md): Datei nach Verhalten
// benannt, nicht nach Ticket — die Ticket-Referenz steht in den Testtiteln.
//
// 🔴 UMGESTELLT in Issue #1848 Scheibe A2: die frueher hier gepruefte
// Halbauswahl (unabhaengige Kaestchen fuer Temperatur-Hoechst- und
// -Tiefstwert) ist abgeschafft. Der Ausblick speichert die KENNUNG, jede
// Groesse hat genau EIN Kaestchen, und Tief und Hoch stehen seit #1848 A1 in
// EINER Spannen-Zelle. Die Zusicherungen sind entsprechend umgedreht, nicht
// entfernt; zusaetzlich pruefen AC-4 und Adversary-2 jetzt mit, dass die
// Paar-ALTFORM aus Bestandsdaten weiterhin gelesen und auf Kennungen
// normalisiert wird.
//
// Spec: docs/specs/modules/feat_1406a_ausblick_geteiltes_element.md
//       docs/specs/modules/feat_1848_a2_ausblick_kennungen.md
// Workflow: feat-1406a-ausblick-geteiltes-element · feat-1848-a2-outlook-kennungen
//
// AC-6/AC-7 (Mail) sind bewusst NICHT hier — deterministisch belegt
// (kein Versand, Kontingent-Schonung #1329).
//
// Ausfuehren (gegen Staging, aus frontend/):
//   set -a; source /home/hem/gregor_zwanzig/.claude/validator.env; set +a
//   set -a; source /home/hem/gregor_zwanzig/.env; set +a
//   npx playwright test --config=playwright.compare-outlook.staging.config.ts

import { test, expect, type Locator, type Page } from '@playwright/test';
import { createTestLocation } from './helpers';
type CatalogEntry = { key: string; label: string; metric_id: string; aggregation: string };

let createdPresetIds: string[] = [];
let createdLocationIds: string[] = [];

test.afterEach(async ({ page }) => {
	for (const id of createdPresetIds) {
		try {
			await page.request.delete(`/api/compare/presets/${id}`);
		} catch {
			/* Staging-Hygiene: Cleanup-Fehler ist nicht test-kritisch */
		}
	}
	createdPresetIds = [];
	for (const id of createdLocationIds) {
		try {
			await page.request.delete(`/api/locations/${id}`);
		} catch {
			/* Staging-Hygiene: Cleanup-Fehler ist nicht test-kritisch */
		}
	}
	createdLocationIds = [];
});

function groupByMetricId(metrics: CatalogEntry[]) {
	const groups: { metric_id: string; label: string; options: CatalogEntry[] }[] = [];
	const byId = new Map<string, (typeof groups)[number]>();
	for (const m of metrics) {
		let g = byId.get(m.metric_id);
		if (!g) {
			g = { metric_id: m.metric_id, label: m.label, options: [] };
			byId.set(m.metric_id, g);
			groups.push(g);
		}
		g.options.push(m);
	}
	return groups;
}
async function createLocation(page: Page, name: string): Promise<string> {
	const loc = await createTestLocation(page.request, {
		name,
		lat: 47.0 + Math.random() * 0.5,
		lon: 11.0 + Math.random() * 0.5
	});
	createdLocationIds.push(loc.id);
	return loc.id;
}

async function createPreset(
	page: Page,
	name: string,
	locationIds: string[],
	displayConfig: Record<string, unknown> = {}
): Promise<string> {
	const res = await page.request.post('/api/compare/presets', {
		data: {
			name,
			location_ids: locationIds,
			schedule: 'manual',
			profil: 'wandern',
			hour_from: 7,
			hour_to: 18,
			empfaenger: ['urlauber@example.com'],
			display_config: displayConfig
		}
	});
	expect(res.ok(), 'Preset-Anlage fehlgeschlagen: ' + res.status()).toBeTruthy();
	const body = await res.json();
	createdPresetIds.push(body.id);
	return body.id as string;
}

/** Oeffnet den Vergleich am Hub und wechselt per Klick auf den Metriken-Tab. */
async function openMetricsTab(page: Page, id: string): Promise<Locator> {
	await page.goto(`/compare/${id}`);
	await expect(page.getByTestId('compare-detail-tab-list')).toBeVisible({ timeout: 15000 });
	await page.waitForLoadState('networkidle');
	await page.getByTestId('compare-detail-tab-wetter-metriken').click();
	const panel = page.getByTestId('compare-detail-panel-wetter-metriken');
	await expect(panel).toBeVisible({ timeout: 10000 });
	return panel;
}

/** Scope fuer alles Ausblick-Bezogene — GRENZT explizit gegen die
 *  Uebersicht (grundauswahl) und den geteilten Reihenfolge-Block der
 *  Uebersicht ab, die dieselben `wm2-reihenfolge*`-Testids tragen. */
function outlookContainer(panel: Locator): Locator {
	return panel.getByTestId('weather-metrics-ausblick');
}

test.describe('Ortsvergleich-Ausblick: gruppierte Metrik-Auswahl (#1406 A, Staging)', () => {
	test.beforeEach(async ({ page }) => {
		await page.setViewportSize({ width: 1280, height: 900 });
	});

	// ── AC-1/AC-3/AC-8 ──────────────────────────────────────────────────────
	// ⚠️ #1848 A3 ZUGESCHNITTEN: der Titel lautete "24 Zeilen, Einzel-Optionen
	// ohne Zusatzelement, keine doppelten Testids". Die 24-Zeilen-Haelfte
	// bediente die Kaestchenliste, die Block A (#2029) ersatzlos entfernt hat
	// — sie ist hier entfallen. Die zwei uebrigen Zusicherungen haengen NICHT
	// an der Liste und bleiben: die Gruppierungs-Rechnung des Katalogs (26
	// flache Eintraege -> 24 Groessen, genau zwei davon mehrfach ausgewertet)
	// und die AC-8-Zusicherung, dass im Wetter-Metriken-Panel keine
	// unerwarteten doppelten `data-testid` stehen.
	test('AC-1/AC-8 (#1406 A): Katalog gruppiert 26 Eintraege zu 24 Groessen, keine doppelten Testids im Panel', async ({
		page,
		request
	}) => {
		const suffix = Date.now();
		const locA = await createLocation(page, `1406a-AC1-A-${suffix}`);
		const locB = await createLocation(page, `1406a-AC1-B-${suffix}`);
		const locC = await createLocation(page, `1406a-AC1-C-${suffix}`);
		const id = await createPreset(page, `1406a-AC1-${suffix}`, [locA, locB, locC]);

		const metricsRes = await request.get('/api/compare/metrics');
		expect(metricsRes.ok(), `GET /api/compare/metrics HTTP ${metricsRes.status()}`).toBeTruthy();
		const catalog = (await metricsRes.json()) as { metrics: CatalogEntry[] };
		expect(catalog.metrics.length, 'Katalog liefert weiterhin 26 flache Eintraege').toBe(26);
		const groups = groupByMetricId(catalog.metrics);
		expect(groups.length, 'AC-1: 24 Wettergroessen (gruppiert)').toBe(24);
		const multiGroups = groups.filter((g) => g.options.length > 1);
		expect(
			multiGroups.map((g) => g.metric_id).sort(),
			'AC-1: genau Temperatur + gefuehlte Temperatur mit >1 Auswertung'
		).toEqual(['temperature', 'wind_chill']);

		const panel = await openMetricsTab(page, id);
		const outlook = outlookContainer(panel);
		await expect(outlook.getByTestId('compare-layout-outlook-metrics')).toBeVisible({ timeout: 10000 });

		// #1848 A3: die Zeilen-/Kaestchen-Schleife ist entfallen (s. Kopf des
		// Tests). Was der Ausblick zeigt, entscheidet jetzt die Grundauswahl —
		// geprueft in ausblick-erbt-grundauswahl.staging.spec.ts::AC-5.
		await expect(
			panel.getByTestId('weather-metrics-vergleich-row-temperature'),
			'Uebersicht zeigt weiterhin eine Temperatur-Zeile'
		).toHaveCount(1);

		// Scope: NUR der Wetter-Metriken-Panel (Uebersicht + Ausblick), nicht die
		// ganze Seite — Kopfzeile/Navi (brand-wordmark, drag-handle etc.) tragen
		// bekannte, dokumentierte Mobil-/Desktop-Doppel-Testids ausserhalb dieses
		// Scopes (irrelevant fuer AC-8).
		const panelHandle = await panel.elementHandle();
		const dupCount = await page.evaluate((root) => {
			const counts = new Map<string, number>();
			root!.querySelectorAll('[data-testid]').forEach((el) => {
				const t = el.getAttribute('data-testid')!;
				counts.set(t, (counts.get(t) ?? 0) + 1);
			});
			return Array.from(counts.entries()).filter(([, n]) => n > 1);
		}, panelHandle);
		// Bekannte, dokumentierte Ausnahme (Nicht-Umfang dieser Spec): der
		// geteilte Reihenfolge-Block (wm2-*, inkl. drag-handle) traegt BEIDE
		// Male (Uebersicht + Ausblick) dieselben Testids — Bestandsverhalten,
		// durch AC-5 als Regressionsschutz abgedeckt, nicht hier.
		const unexpectedDupes = dupCount.filter(
			([t]) => !t.startsWith('wm2-') && t !== 'aggregation-choices-temperature' && t !== 'drag-handle'
		);
		expect(
			unexpectedDupes,
			`AC-8: unerwartete doppelte data-testid-Werte im DOM: ${JSON.stringify(unexpectedDupes)}`
		).toEqual([]);

		await page.screenshot({
			path: '../docs/artifacts/feat-1406a-ausblick-geteiltes-element/ac-1-3-8-grouped-list.png',
			fullPage: true
		});
	});

	// ── AC-2 (#1848 A2) — ERSATZLOS ENTFERNT in #1848 A3 ────────────────────
	// Zugesichert war: "Temperatur ist EIN Kaestchen — keine getrennten
	// Auswertungen mehr" (A2 hatte die Halbauswahl abgeschafft, PO-Entscheid
	// 2026-08-20). Mit Block A (#2029) gibt es gar keine Kaestchen mehr, an
	// denen sich "genau eines" zeigen liesse. Die Sache dahinter — eine
	// Groesse ist EIN Eintrag, eine Halbauswahl laesst sich nicht ablegen —
	// ist seither strukturell erzwungen statt bedienbar: der Ausblick spricht
	// nur noch Kennungen (kein Katalog-Schluessel mehr in `outlook_metrics`),
	// und genau das bewachen `test_outlook_metric_id_persistence.py` sowie der
	// AST-Waechter `outlook_erbt_grundauswahl_structure.test.ts`. Ein Ersatz
	// auf der "Aus"-Flaeche waere eine Zusicherung ueber etwas, das dort nicht
	// mehr entstehen kann.

	// ── AC-4 ────────────────────────────────────────────────────────────────
	test('AC-4 (#1406 A): gespeicherte Auswahl ueberlebt Reload — neu UND an einem Bestands-Vergleich', async ({
		page,
		request
	}) => {
		const suffix = Date.now();
		const locA = await createLocation(page, `1406a-AC4-A-${suffix}`);
		const locB = await createLocation(page, `1406a-AC4-B-${suffix}`);
		const locC = await createLocation(page, `1406a-AC4-C-${suffix}`);
		const id = await createPreset(page, `1406a-AC4-${suffix}`, [locA, locB, locC], {
			outlook_metrics: []
		});

		const panel = await openMetricsTab(page, id);
		const outlook = outlookContainer(panel);
		// #1848 A3: geschaltet wird ueber "Ein" in der Aus-Gruppe statt ueber
		// Kaestchen. Die Zusicherung ist unveraendert: zwei Gesten, zwei
		// Eintraege, Reihenfolge der Gesten erhalten, reine Kennungen im
		// Speicher, und der Stand ueberlebt den Reload. Start ist die bewusst
		// LEERE Auswahl (`outlook_metrics: []`) -- dann stehen alle Groessen
		// der Grundauswahl in der Aus-Gruppe und lassen sich einzeln holen.
		const ausGruppe = outlook.getByTestId('wm2-aus-gruppe');
		await expect(ausGruppe, 'Vorbedingung: leere Auswahl zeigt die Aus-Gruppe').toBeVisible({
			timeout: 10000
		});
		const einSchalten = async (metricId: string) => {
			const putPromise = page.waitForResponse(
				(r) => r.url().includes(`/api/compare/presets/${id}`) && r.request().method() === 'PUT',
				{ timeout: 8000 }
			);
			await ausGruppe
				.locator(`[data-testid="wm2-aus-row"][data-metric-id="${metricId}"]`)
				.getByRole('button', { name: 'Ein' })
				.click();
			await putPromise;
		};
		await einSchalten('temperature');
		await einSchalten('gust');
		await page.waitForTimeout(500);

		const getRes = await page.request.get(`/api/compare/presets/${id}`);
		const savedPreset = await getRes.json();
		const savedOutlook = (savedPreset.display_config?.outlook_metrics ?? []) as string[];
		expect(
			savedOutlook.every((m) => typeof m === 'string'),
			`#1848 A2: display_config.outlook_metrics muss reine Kennungen fuehren: ${JSON.stringify(savedOutlook)}`
		).toBe(true);
		expect(
			savedOutlook,
			'AC-4: display_config.outlook_metrics enthaelt beide geholten Kennungen in Klickreihenfolge'
		).toEqual(['temperature', 'gust']);

		const reloadedPanel = await openMetricsTab(page, id);
		const reloadedOutlook = outlookContainer(reloadedPanel);
		await expect(
			reloadedOutlook.locator('[data-testid="wm2-reihenfolge-row"][data-metric-id="temperature"]')
		).toBeVisible({ timeout: 10000 });
		await expect(
			reloadedOutlook.locator('[data-testid="wm2-reihenfolge-row"][data-metric-id="gust"]')
		).toBeVisible();

		await page.screenshot({
			path: '../docs/artifacts/feat-1848-a2-outlook-kennungen/ac-4-persisted-after-reload.png'
		});

		// AC-4 zweiter Teil: Bestands-Vergleich, NICHT von diesem Lauf angelegt
		// (Regel-Vorgabe der Aufgabe). Dynamisch ermittelt statt hartkodierter
		// ID — erster Vergleich, dessen Name nicht das reservierte Test-Praefix
		// traegt. Erwartung wird aus dem gespeicherten `outlook_metrics`
		// (bzw. der Default-Materialisierung bei `null`) hergeleitet, nicht aus
		// Annahmen ueber einen bestimmten Datensatz.
		const allRes = await page.request.get('/api/compare/presets');
		const allPresets = (await allRes.json()) as { id: string; name: string }[];
		const existingMeta = allPresets.find(
			(p) => !p.name.startsWith('E2E-GZ-') && !p.name.startsWith('1406a-')
		);
		test.skip(!existingMeta, 'Kein bestehender Vergleich auf Staging gefunden — Teil 2 uebersprungen');

		const existingRes = await page.request.get(`/api/compare/presets/${existingMeta!.id}`);
		const existingPreset = await existingRes.json();
		// #1848 A2: gespeichert wird die Kennung -- ein Bestands-Vergleich kann
		// aber noch die PAAR-ALTFORM tragen. Genau das ist der Sinn dieses
		// Teils: die Bedienflaeche muss beide lesen und daraus dieselbe
		// Kennungsmenge anzeigen. Zwei Paare derselben Groesse (Tief UND Hoch)
		// ergeben dabei EINEN Haken, nicht zwei.
		const storedOutlook = existingPreset.display_config?.outlook_metrics as
			| (string | { metric_id: string; aggregation: string })[]
			| null
			| undefined;
		const DEFAULT_OUTLOOK_IDS = [
			'temperature', 'precipitation', 'rain_probability', 'wind', 'gust', 'thunder'
		];
		const expectedActiveIds =
			storedOutlook && storedOutlook.length > 0
				? Array.from(
						new Set(
							storedOutlook.map((m) => (typeof m === 'string' ? m : m.metric_id)).filter(Boolean)
						)
					)
				: DEFAULT_OUTLOOK_IDS;

		const existingPanel = await openMetricsTab(page, existingMeta!.id);
		const existingOutlook = outlookContainer(existingPanel);
		await expect(existingOutlook.getByTestId('compare-layout-outlook-metrics')).toBeVisible({
			timeout: 10000
		});
		// #1848 A3: abgelesen wird die AKTIVE Reihenfolge-Liste statt der Haken.
		// 🔴 Bewusst nur die scharfe Richtung geprueft — "die aktive Liste
		// enthaelt NICHTS, was nicht in der Bestandsauswahl steht, und jede
		// Groesse hoechstens einmal". Die Umkehrung ("jede erwartete Kennung
		// ist aktiv") waere seit A3 kein sauberes Soll mehr: der Ausblick
		// klemmt gegen die Grundauswahl des Vergleichs, eine dort abgewaehlte
		// Groesse erscheint zu Recht nirgends. Sie einzufordern erzeugte
		// Fehlalarme an einem Bestands-Vergleich, dessen Grundauswahl dieser
		// Test gar nicht kennt.
		// Die eigentliche Zusicherung bleibt vollstaendig: die Paar-Altform
		// wird auf Kennungen normalisiert -- zwei Paare derselben Groesse
		// (Tief UND Hoch) ergeben EINEN Eintrag, nicht zwei.
		const aktiveIds = await existingOutlook
			.locator('[data-testid="wm2-reihenfolge-row"]')
			.evaluateAll((els) => els.map((e) => e.getAttribute('data-metric-id')));
		expect(
			aktiveIds.filter((id) => !expectedActiveIds.includes(id as string)),
			`Die aktive Ausblick-Liste zeigt Groessen, die nicht in der Bestandsauswahl stehen: ${JSON.stringify(aktiveIds)}`
		).toEqual([]);
		expect(
			aktiveIds.length,
			`Die Paar-Altform wurde nicht auf Kennungen normalisiert — doppelte Eintraege: ${JSON.stringify(aktiveIds)}`
		).toBe(new Set(aktiveIds).size);
		expect(
			aktiveIds.length,
			'Vakuum-Schutz: eine leere aktive Liste machte die Zusicherungen oben trivial wahr'
		).toBeGreaterThan(0);
		await page.screenshot({
			path: '../docs/artifacts/feat-1848-a2-outlook-kennungen/ac-4-existing-preset-untouched.png'
		});
	});

	// ── AC-5 (Regressionsschutz) ─────────────────────────────────────────────
	test('AC-5 (#1406 A): Reihenfolge-Block (Ziehen + Aus) funktioniert unveraendert', async ({ page, request }) => {
		const suffix = Date.now();
		const locA = await createLocation(page, `1406a-AC5-A-${suffix}`);
		const locB = await createLocation(page, `1406a-AC5-B-${suffix}`);
		const locC = await createLocation(page, `1406a-AC5-C-${suffix}`);
		// #1848 A2: reine Kennungen im Speicherformat.
		const startOrder = ['wind', 'precipitation', 'gust'];
		const id = await createPreset(page, `1406a-AC5-${suffix}`, [locA, locB, locC], {
			outlook_metrics: startOrder
		});

		const panel = await openMetricsTab(page, id);
		const outlook = outlookContainer(panel);
		const rows = outlook.locator('[data-testid="wm2-reihenfolge-row"]');
		await expect(rows).toHaveCount(3, { timeout: 10000 });
		const initialOrder = await rows.evaluateAll((els) => els.map((e) => e.getAttribute('data-metric-id')));
		expect(initialOrder).toEqual(['wind', 'precipitation', 'gust']);

		const source = outlook.locator('[data-testid="wm2-reihenfolge-row"][data-metric-id="gust"]');
		const target = outlook.locator('[data-testid="wm2-reihenfolge-row"][data-metric-id="wind"]');
		await source.scrollIntoViewIfNeeded();
		await target.scrollIntoViewIfNeeded();
		const sBox = await source.boundingBox();
		const tBox = await target.boundingBox();
		if (!sBox || !tBox) throw new Error('AC-5: source/target ohne BoundingBox');
		await page.mouse.move(sBox.x + sBox.width / 2, sBox.y + sBox.height / 2);
		await page.mouse.down();
		await page.mouse.move(sBox.x + sBox.width / 2, sBox.y + sBox.height / 2 - 12, { steps: 6 });
		await page.waitForTimeout(120);
		await page.mouse.move(tBox.x + tBox.width / 2, tBox.y + tBox.height / 2, { steps: 15 });
		await page.waitForTimeout(120);
		await page.mouse.up();

		// #1848 A2: EIN Vokabular. Der DOM (`data-metric-id`) und der
		// persistierte `outlook_metrics`-Eintrag tragen beide die Kennung --
		// vorher waren es zwei Vokabulare (flacher Katalog-Key im DOM,
		// Groesse+Auswertung im Speicher). Die Zusicherung "dieselbe
		// Reihenfolge auf beiden Seiten" bleibt und wird direkter pruefbar.
		const expectedDomOrder = ['gust', 'wind', 'precipitation'];
		const expectedMetricIdOrder = ['gust', 'wind', 'precipitation'];
		await expect
			.poll(async () => rows.evaluateAll((els) => els.map((e) => e.getAttribute('data-metric-id'))), {
				timeout: 5000
			})
			.toEqual(expectedDomOrder);

		await expect
			.poll(
				async () => {
					const r = await request.get(`/api/compare/presets/${id}`);
					const body = await r.json();
					return (body.display_config?.outlook_metrics ?? []) as string[];
				},
				{ message: 'AC-5: die gezogene Reihenfolge muss serverseitig persistent sein', timeout: 8000 }
			)
			.toEqual(expectedMetricIdOrder);

		const reloadedPanel = await openMetricsTab(page, id);
		const reloadedOutlook = outlookContainer(reloadedPanel);
		const reloadedRows = reloadedOutlook.locator('[data-testid="wm2-reihenfolge-row"]');
		await expect
			.poll(async () => reloadedRows.evaluateAll((els) => els.map((e) => e.getAttribute('data-metric-id'))), {
				timeout: 10000
			})
			.toEqual(expectedDomOrder);

		await page.screenshot({
			path: '../docs/artifacts/feat-1406a-ausblick-geteiltes-element/ac-5-reordered-after-reload.png'
		});

		const removeRow = reloadedOutlook.locator(
			'[data-testid="wm2-reihenfolge-row"][data-metric-id="precipitation"]'
		);
		await removeRow.getByRole('button', { name: 'Aus' }).click();
		await expect
			.poll(async () => reloadedRows.evaluateAll((els) => els.map((e) => e.getAttribute('data-metric-id'))), {
				timeout: 5000
			})
			.toEqual(['gust', 'wind']);

		await expect
			.poll(
				async () => {
					const r = await request.get(`/api/compare/presets/${id}`);
					const body = await r.json();
					return (body.display_config?.outlook_metrics ?? []) as string[];
				},
				{ message: 'AC-5: "Aus" muss serverseitig persistent sein', timeout: 8000 }
			)
			.toEqual(['gust', 'wind']);

		await page.screenshot({
			path: '../docs/artifacts/feat-1406a-ausblick-geteiltes-element/ac-5-removed-after-aus.png'
		});
	});
});


test.describe('Ortsvergleich-Ausblick — Runde 2: Adversary-Grenzfaelle (#1406 A, Staging)', () => {
	test.beforeEach(async ({ page }) => {
		await page.setViewportSize({ width: 1280, height: 900 });
	});

	// Doppel-Klick-Analog: schnelles Doppel-Toggle auf DASSELBE Kaestchen
	// (an -> aus) darf keinen Race erzeugen, der den Server-Stand vom
	// UI-Stand abweichen laesst.
	// #1848 A3: geschaltet wird ueber "Ein"/"Aus" statt ueber ein Kaestchen —
	// die bewachte Fehlerklasse ist unveraendert: drei Gesten in schneller
	// Folge, ohne auf die einzelnen PUTs zu warten, duerfen den Server-Stand
	// nicht auf einem Zwischenwert stehen lassen.
	test('Adversary (#1406 A): schnelles Ein/Aus derselben Groesse bleibt konsistent', async ({ page }) => {
		const suffix = Date.now();
		const locA = await createLocation(page, `1406a-ADV1-A-${suffix}`);
		const locB = await createLocation(page, `1406a-ADV1-B-${suffix}`);
		const locC = await createLocation(page, `1406a-ADV1-C-${suffix}`);
		const id = await createPreset(page, `1406a-ADV1-${suffix}`, [locA, locB, locC], {
			outlook_metrics: []
		});

		const panel = await openMetricsTab(page, id);
		const outlook = outlookContainer(panel);
		const aktiveTemp = outlook.locator(
			'[data-testid="wm2-reihenfolge-row"][data-metric-id="temperature"]'
		);
		const ausTemp = outlook
			.getByTestId('wm2-aus-gruppe')
			.locator('[data-testid="wm2-aus-row"][data-metric-id="temperature"]');
		await expect(ausTemp, 'Vorbedingung: Temperatur startet abgewaehlt').toBeVisible({
			timeout: 10000
		});

		// Ein -> Aus -> Ein in schneller Folge, ohne auf einzelne PUTs zu warten.
		await ausTemp.getByRole('button', { name: 'Ein' }).click();
		await aktiveTemp.getByRole('button', { name: 'Aus' }).click();
		await ausTemp.getByRole('button', { name: 'Ein' }).click();
		// Netto-Effekt von drei Gesten aus dem Startzustand "aus": an.
		await expect(aktiveTemp).toBeVisible();
		await page.waitForLoadState('networkidle');
		await page.waitForTimeout(800);

		const getRes = await page.request.get(`/api/compare/presets/${id}`);
		const saved = await getRes.json();
		const savedIds = (saved.display_config?.outlook_metrics ?? []) as string[];
		expect(
			savedIds.includes('temperature'),
			`AC-4-Regression: Server-Stand nach schneller Dreifach-Geste muss "an" sein, tatsaechlich: ${JSON.stringify(savedIds)}`
		).toBe(true);

		const reloadedPanel = await openMetricsTab(page, id);
		const reloadedOutlook = outlookContainer(reloadedPanel);
		await expect(
			reloadedOutlook.locator('[data-testid="wm2-reihenfolge-row"][data-metric-id="temperature"]')
		).toBeVisible({ timeout: 10000 });

		await page.screenshot({
			path: '../docs/artifacts/feat-1848-a2-outlook-kennungen/adv-1-rapid-toggle-consistent.png'
		});
	});

	// Leer-Zustand: ALLE Groessen abwaehlen (bewusste Leerauswahl) darf den
	// Ausblick-Block nicht unbedienbar machen — sonst gaebe es keinen Weg
	// zurueck.
	// 🔴 #1848 A3 macht diese Zusicherung WICHTIGER, nicht kleiner: bis dahin
	// war der Rueckweg die Kaestchenliste, die stehen blieb. Die gibt es nicht
	// mehr (Block A, #2029) — der einzige Rueckweg ist jetzt die "Aus"-Gruppe
	// (ADR-0050 Regel 4). Bleibt sie bei Totalabwahl nicht stehen, ist der
	// Ausblick dauerhaft verloren.
	// WICHTIG: der Ausblick-Block fehlt komplett im DOM, solange der Katalog
	// laedt (`WeatherMetricsTab.svelte`, bewusst so gebaut,
	// `compareCatalogLoaded`-Gate). JEDE Existenzpruefung einer einzelnen
	// Zeile muss deshalb auf das Element WARTEN, nie per Sofort-`count()`
	// entscheiden — ein zu frueher `count()===0` liest "noch nicht da" als
	// "gibt es nicht" und ueberspringt die Zeile dauerhaft (Ex-Befund
	// #1423, tatsaechlich ein Test-Bug, kein Produktfehler — root-caused
	// durch das Team, s. Wait + `existsSoon` unten).
	test('Adversary (#1406 A): alle Ausblick-Groessen abgewaehlt — die Aus-Gruppe bleibt der Rueckweg', async ({ page }) => {
		const suffix = Date.now();
		const locA = await createLocation(page, `1406a-ADV2-A-${suffix}`);
		const locB = await createLocation(page, `1406a-ADV2-B-${suffix}`);
		const locC = await createLocation(page, `1406a-ADV2-C-${suffix}`);
		// Bewusst mit EXPLIZITEN outlook_metrics angelegt (nicht null): ein
		// Debug-Befund zeigte, dass der allererste Toggle-Klick auf einem NIE
		// konfigurierten (`null`) Ausblick intermittierend verloren ging (~25%
		// der Laeufe, immer das ERSTE geklickte Kaestchen) — vermutlich ein
		// Race zwischen den zwei verschachtelten Commit-Wrappern beim
		// Materialisierungs-Uebergang null->Array. Das ist ein eigener Befund
		// (an Team/PO gemeldet), NICHT Gegenstand dieses Tests — deshalb hier
		// mit bereits konkretem Array gestartet, identisch zu den 7
		// Default-Spalten, um den Adversary-Fall "alle abwaehlen" isoliert zu
		// pruefen.
		// #1848 A2: bewusst in der PAAR-ALTFORM angelegt — so liegen
		// Bestandsdaten auf Staging. Der Fall prueft damit gleich mit, dass die
		// Bedienflaeche die Altform liest und die beiden Temperatur-Paare als
		// EINEN Haken zeigt (sonst faende die Abwahl-Schleife unten sieben
		// statt sechs Kaestchen).
		const id = await createPreset(page, `1406a-ADV2-${suffix}`, [locA, locB, locC], {
			outlook_metrics: [
				{ metric_id: 'temperature', aggregation: 'min' },
				{ metric_id: 'temperature', aggregation: 'max' },
				{ metric_id: 'precipitation', aggregation: 'sum' },
				{ metric_id: 'rain_probability', aggregation: 'max' },
				{ metric_id: 'wind', aggregation: 'max' },
				{ metric_id: 'gust', aggregation: 'max' },
				{ metric_id: 'thunder', aggregation: 'max' }
			]
		});

		const panel = await openMetricsTab(page, id);
		const outlook = outlookContainer(panel);
		// WURZEL-FIX: der Ausblick-Block existiert erst NACH Katalog-Ladeende
		// im DOM (`compareCatalogLoaded`-Gate, s. Kommentar oben). Ohne diesen
		// Wait koennte eine Existenzpruefung auf die erste Zeile treffen,
		// waehrend der Block noch gar nicht gemountet ist, und sie fuer immer
		// als "gibt es nicht" ueberspringen. `compare-layout-outlook-metrics`
		// ist genau der Container, der erst nach dem Laden erscheint.
		await expect(outlook.getByTestId('compare-layout-outlook-metrics')).toBeVisible({ timeout: 10000 });

		// #1848 A2: sechs KENNUNGEN statt sieben Paaren -- Temperatur-Tief und
		// -Hoch sind ein Eintrag geworden.
		const defaultMetricIds = [
			'temperature', 'precipitation', 'rain_probability', 'wind', 'gust', 'thunder'
		];
		async function ausSchaltenUndBestaetigen(zeile: Locator): Promise<void> {
			const putPromise = page.waitForResponse(
				(r) => r.url().includes(`/api/compare/presets/${id}`) && r.request().method() === 'PUT',
				{ timeout: 8000 }
			);
			await zeile.getByRole('button', { name: 'Aus' }).click();
			await putPromise;
			await page.waitForLoadState('networkidle');
		}
		// Existenzpruefung WARTET (statt einer Sofort-`count()`-Momentaufnahme)
		// — auch als zweite Verteidigungslinie hinter dem Wait oben: "noch
		// nicht da" darf nie mit "gibt es nicht" verwechselt werden.
		async function existsSoon(locator: Locator, timeoutMs = 3000): Promise<boolean> {
			try {
				await locator.waitFor({ state: 'attached', timeout: timeoutMs });
				return true;
			} catch {
				return false;
			}
		}
		// #1848 A2/A3: EINE Zeilenform fuer alle Groessen. Dass die
		// Paar-Altform beim Lesen auf Kennungen normalisiert wird, zeigt sich
		// daran, dass die beiden Temperatur-Paare EINE Zeile ergeben — sonst
		// faende die Schleife sieben statt sechs.
		for (const mid of defaultMetricIds) {
			const zeile = outlook.locator(
				`[data-testid="wm2-reihenfolge-row"][data-metric-id="${mid}"]`
			);
			expect(
				await existsSoon(zeile),
				`#1848 A2: Ausblick-Zeile fuer ${mid} fehlt — die Bestands-Altform wurde beim ` +
					'Lesen nicht auf Kennungen normalisiert'
			).toBe(true);
			await ausSchaltenUndBestaetigen(zeile);
		}

		// Server-Stand ist die eigentliche Aussage (nicht nur der DOM) — s.
		// reference_concurrency_tests_must_prove_arrival_not_status.
		await expect
			.poll(
				async () => {
					const r = await page.request.get(`/api/compare/presets/${id}`);
					const body = await r.json();
					return ((body.display_config?.outlook_metrics ?? []) as unknown[]).length;
				},
				{ message: 'AC-Adversary: Server muss nach allen Abwahlen 0 Ausblick-Metriken zeigen', timeout: 10000 }
			)
			.toBe(0);

		// 🔴 Der Kern der Zusicherung seit #1848 A3: die aktive Liste ist leer,
		// aber der Block bleibt da und die Aus-Gruppe traegt jede abgewaehlte
		// Groesse. Waere sie mit der letzten Abwahl verschwunden, gaebe es
		// keinen Rueckweg mehr (ADR-0050 Regel 4).
		await expect(outlook.getByTestId('compare-layout-outlook-metrics')).toBeVisible();
		await expect(outlook.locator('[data-testid="wm2-reihenfolge-row"]')).toHaveCount(0);
		const ausGruppe = outlook.getByTestId('wm2-aus-gruppe');
		await expect(
			ausGruppe,
			'Adversary: nach der Totalabwahl fehlt die Aus-Gruppe — der Ausblick waere unwiederbringlich leer'
		).toBeVisible();
		for (const mid of defaultMetricIds) {
			await expect(
				ausGruppe.locator(`[data-testid="wm2-aus-row"][data-metric-id="${mid}"]`),
				`Adversary: ${mid} fehlt in der Aus-Gruppe und ist damit nicht zurueckholbar`
			).toBeVisible();
		}

		// Zurueck: eine Groesse wieder anwaehlen funktioniert weiterhin.
		await ausGruppe
			.locator('[data-testid="wm2-aus-row"][data-metric-id="wind"]')
			.getByRole('button', { name: 'Ein' })
			.click();
		await expect(
			outlook.locator('[data-testid="wm2-reihenfolge-row"][data-metric-id="wind"]')
		).toBeVisible();

		await page.screenshot({
			path: '../docs/artifacts/feat-1406a-ausblick-geteiltes-element/adv-2-empty-then-reselect.png'
		});
	});
});
