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

import { test, expect, type Locator, type Page } from '@playwright/test';
import { HUB_KINDS, HUB_SEL, dragDndZoneItem, hubApiPath, openHub, seedHub, type HubKind } from './helpers';

type Stand = Record<string, unknown>;

/** Kind-Kontraste (Spec): Seed, Zeilen-Kennungen (fest, nie aus dem Produkt gelesen), Karten-Testid. */
const RO_SEL: Record<
	HubKind,
	{
		seed: Record<string, unknown>;
		start: [string, string, string];
		/** Erwartete Reihenfolge nach „dritte Zeile vor die erste ziehen" (Zeilen-Kennungen der Karte). */
		nachZug: [string, string, string];
		/** Dieselbe Reihenfolge im gespeicherten Zielfeld (Kennungsraum des Servers, fest). */
		serverNachZug: [string, string, string];
		panel: string;
		karte: string;
	}
> = {
	route: {
		// Metriken OHNE Auffächerung: `temperature` fächert in der Kanal-Karte in vier Zeilen
		// auf (temperature, _night, _day_low, _day_high) — dann wäre „dritte Zeile" keine Seed-Metrik.
		seed: {
			display_config: {
				metrics: [
					{ metric_id: 'wind', enabled: true, bucket: 'primary', order: 0 },
					{ metric_id: 'precipitation', enabled: true, bucket: 'primary', order: 1 },
					{ metric_id: 'gust', enabled: true, bucket: 'primary', order: 2 }
				]
			}
		},
		start: ['wind', 'precipitation', 'gust'],
		nachZug: ['gust', 'wind', 'precipitation'],
		// Zielfeld Trip (in /50 gemessen, Entscheidung 8): die Kanal-Karte schreibt über
		// PUT …/weather-config nach `display_config.channel_layouts.email` (aktive Einträge, `order`).
		serverNachZug: ['gust', 'wind', 'precipitation'],
		panel: 'weather-metrics-tab',
		karte: 'weather-metrics-kanal-reihenfolge'
	},
	vergleich: {
		seed: { display_config: { active_metrics: ['temp_max_c', 'wind_max_kmh', 'sunny_hours_h'] } },
		start: ['temp_max_c', 'wind_max_kmh', 'sunny_hours_h'],
		nachZug: ['sunny_hours_h', 'temp_max_c', 'wind_max_kmh'],
		// Zielfeld Vergleich (in /50 gemessen, Entscheidung 8): die Kanal-Karte (E-Mail) schreibt
		// `display_config.channel_active_metrics.email` im Register-Format {metric_id, aggregation}
		// (#1373); `active_metrics` behält die Ausgangsreihenfolge. Kennungen hier fest:
		// sunny_hours_h = sunshine/sum, temp_max_c = temperature/max, wind_max_kmh = wind/max.
		serverNachZug: ['sunshine:sum', 'temperature:max', 'wind:max'],
		panel: 'weather-metrics-tab-vergleich',
		karte: 'weather-metrics-vergleich-reihenfolge'
	}
};

async function stand(page: Page, kind: HubKind, id: string): Promise<Stand> {
	const res = await page.request.get(hubApiPath(kind, id));
	expect(res.ok(), `GET ${hubApiPath(kind, id)} HTTP ${res.status()}`).toBeTruthy();
	return (await res.json()) as Stand;
}

/** Reihenfolge der E-Mail-Kanal-Auswahl im gespeicherten Stand (Zielfeld je kind, siehe RO_SEL). */
function gespeicherteReihenfolge(kind: HubKind, s: Stand): string[] {
	const dc = (s.display_config as Stand | undefined) ?? {};
	if (kind === 'route') {
		const layouts = (dc.channel_layouts as Record<string, unknown> | undefined) ?? {};
		const email = (layouts.email as Array<{ metric_id: string; enabled?: boolean; order?: number }> | undefined) ?? [];
		return email
			.filter((m) => m.enabled === true)
			.sort((a, b) => (a.order ?? 0) - (b.order ?? 0))
			.map((m) => m.metric_id);
	}
	const kanal = (dc.channel_active_metrics as Record<string, unknown> | undefined) ?? {};
	const email = (kanal.email as Array<string | { metric_id: string; aggregation?: string }> | undefined) ?? [];
	return email.map((m) => (typeof m === 'string' ? m : `${m.metric_id}:${m.aggregation}`));
}

const zeilen = (karte: Locator) => karte.locator('[data-testid="wm2-reihenfolge-row"]');
const zeilenIds = (karte: Locator) => zeilen(karte).evaluateAll((els) => els.map((el) => el.getAttribute('data-metric-id')));

async function oeffneKarte(page: Page, kind: HubKind, id: string): Promise<Locator> {
	await openHub(page, kind, id, { tab: 'wetter-metriken' });
	const panel = page.locator(`[data-testid="${RO_SEL[kind].panel}"]:visible`);
	await expect(panel).toBeVisible({ timeout: 10_000 });
	const karte = panel.locator(`[data-testid="${RO_SEL[kind].karte}"]`);
	await expect(karte, 'Die Reihenfolge-Karte muss im Reiter Wetter-Metriken stehen').toBeVisible({ timeout: 10_000 });
	return karte;
}

for (const kind of HUB_KINDS) {
	const ro = RO_SEL[kind];
	const sel = HUB_SEL[kind];

	test.describe(`Hub · Metrik-Reihenfolge ziehen (${kind})`, () => {
		test.beforeEach(async ({ page }) => {
			await page.setViewportSize({ width: 1440, height: 900 });
		});

		// RO-1 — Alt compare-metric-order AC-3. Fängt: Ziehen ruft den Speicherweg nicht auf
		// (Diff-Guard wertet reine Umsortierung als „keine Änderung"), Server speichert die alte
		// Reihenfolge, Neuladen zeigt die alte Reihenfolge.
		test(`RO-1 (${kind}): dritte Zeile vor die erste ziehen → PUT-Antwort, Server trägt die Reihenfolge, Neuladen zeigt sie`, async ({
			page
		}) => {
			const hub = await seedHub(page.request, kind, { extra: ro.seed });
			try {
				const karte = await oeffneKarte(page, kind, hub.id);
				await expect(zeilen(karte)).toHaveCount(ro.start.length, { timeout: 10_000 });
				expect(await zeilenIds(karte), 'Vorbedingung: Ausgangsreihenfolge laut Seed').toEqual(ro.start);

				// Nur ZIEHEN — keine Metrik an- oder abwählen. Antwort VOR der Geste vormerken.
				const pfad = hubApiPath(kind, hub.id);
				const antwort = page.waitForResponse(
					(r) => r.request().method() === 'PUT' && new URL(r.url()).pathname.startsWith(pfad),
					{ timeout: 15_000 }
				);
				await dragDndZoneItem(
					page,
					karte.locator(`[data-testid="wm2-reihenfolge-row"][data-metric-id="${ro.start[2]}"]`),
					karte.locator(`[data-testid="wm2-reihenfolge-row"][data-metric-id="${ro.start[0]}"]`)
				);
				await expect
					.poll(() => zeilenIds(karte), { message: 'RO-1 FAIL: die gezogene Zeile steht nicht an der neuen Position', timeout: 5_000 })
					.toEqual(ro.nachZug);

				const res = await antwort.catch(() => null);
				expect(
					res,
					'RO-1 FAIL: nach der Ziehgeste feuert kein PUT — der Diff-Guard wertet reine Umsortierung als „keine Änderung"'
				).not.toBeNull();
				expect(res!.status(), 'RO-1 FAIL: der Speichervorgang wurde nicht mit 200 beantwortet').toBe(200);
				await expect(page.locator('[data-testid="save-indicator"]')).toHaveAttribute('data-state', 'idle', { timeout: 10_000 });

				// Server-Stand trägt die neue Reihenfolge (Zielfeld je kind, im RED gemessen).
				await expect
					.poll(async () => gespeicherteReihenfolge(kind, await stand(page, kind, hub.id)), {
						timeout: 10_000,
						message: 'RO-1 FAIL: der Server trägt die neue Reihenfolge nicht'
					})
					.toEqual(ro.serverNachZug);

				// Neuladen zeigt sie unverändert.
				const nachLaden = await oeffneKarte(page, kind, hub.id);
				await expect
					.poll(() => zeilenIds(nachLaden), {
						timeout: 10_000,
						message: 'RO-1 FAIL: nach dem Neuladen steht wieder die alte Reihenfolge'
					})
					.toEqual(ro.nachZug);
			} finally {
				await hub.aufraeumen();
			}
		});

		// RO-2 — Alt compare-metric-order AC-6. „Amtliche Warnungen" ist KEINE ziehbare Zeile
		// (beide kinds). Der erklärende Hinweis ist Compare-eigen: im Trip sind Amtliche Warnungen
		// ein eigener Abschnitt `official_alerts` (Spec „Kind-Kontraste").
		test(`RO-2 (${kind}): „Amtliche Warnungen" ist keine ziehbare Zeile${kind === 'vergleich' ? ', der Hinweis erklärt es' : ''}`, async ({
			page
		}) => {
			const hub = await seedHub(page.request, kind, { extra: ro.seed });
			try {
				const karte = await oeffneKarte(page, kind, hub.id);
				await expect(zeilen(karte)).toHaveCount(ro.start.length, { timeout: 10_000 });
				const ids = (await zeilenIds(karte)).map((i) => String(i));
				expect(
					ids.filter((i) => /official|warn/i.test(i)),
					'RO-2 FAIL: „Amtliche Warnungen" darf keine ziehbare Zeile der Reihenfolge-Karte sein'
				).toEqual([]);

				if (kind === 'vergleich') {
					// Compare-eigen (Kind-Kontraste): nur der Vergleich trägt den Hinweis.
					const hinweis = page.getByTestId('weather-metrics-vergleich-warn-hint');
					await expect(hinweis).toBeVisible({ timeout: 10_000 });
					await expect(hinweis).toContainText(/Amtliche Warnungen/);
					await expect(hinweis).toContainText(/erste/i);
				}
				// Der Hub ist offen (Kontrolle gegen leeren Treffer durch falsche Seite).
				await expect(page.getByTestId(sel.reiterListe)).toBeVisible();
			} finally {
				await hub.aufraeumen();
			}
		});
	});
}
