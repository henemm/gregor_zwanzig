// Gemeinsame Helfer fuer Specs, die seit #3154 (#3122 B3b, Spec feat_3122_was_steht_wo.md Teil B Nr. 13/14)
// die Karte „Was steht wo“ im Reiter Wetter statt der entfernten Bedienelemente im Reiter Zustellung pruefen.
// Keine .spec.ts-Datei. Laeuft relativ zur baseURL der jeweiligen Config (lokaler Stapel oder Staging).
//
// Die Karte speichert die Tabelle als `display_config.placements` (PUT /api/briefings/{id}/placements?kind=…);
// die Schalter unter der Tabelle schreiben ihre Felder am heutigen Ort (Trip `report_config`, Orte oben bzw.
// `display_config.telegram_style`). Die Antwort des Endpoints (GET) traegt Zeilen, Zellen, Beispielwerte,
// Marken, SMS-Beispiel und Legende — sie ist die „Vorschau“ der Karte.

import { expect, type APIRequestContext, type Locator, type Page } from '@playwright/test';
import { createTestLocation, hubApiPath, openHub, seedHub, type HubKind } from './helpers';

export type Json = any; // eslint-disable-line @typescript-eslint/no-explicit-any
export type { HubKind };

export const TRIP_METRIKEN = ['temperature', 'wind', 'gust', 'precipitation', 'thunder'];
export const ORTE_METRIKEN = ['temp_max_c', 'wind_max_kmh', 'precip_sum_mm', 'sunny_hours_h'];

export interface Abo {
	kind: HubKind;
	id: string;
	aufraeumen: () => Promise<void>;
}

/** Wegwerf-Abo mit fester Grundauswahl. `oben` ueberschreibt Felder oben, `dc` ergaenzt `display_config`. */
export async function seedAbo(
	request: APIRequestContext,
	kind: HubKind,
	opts: { metriken?: string[]; oben?: Json; dc?: Json; orte?: number } = {}
): Promise<Abo> {
	if (kind === 'route') {
		const metriken = opts.metriken ?? TRIP_METRIKEN;
		const hub = await seedHub(request, 'route', {
			extra: { ...opts.oben, display_config: { metrics: metriken.map((metric_id) => ({ metric_id, enabled: true })), ...opts.dc } }
		});
		return { kind, id: hub.id, aufraeumen: hub.aufraeumen };
	}
	const orte: string[] = [];
	for (let i = 0; i < (opts.orte ?? 2); i++) orte.push((await createTestLocation(request, { name: `WSW-Helfer-${Date.now()}-${i}`, lat: 47.1 + i * 0.1, lon: 11.2 + i * 0.1 })).id);
	const metriken = opts.metriken ?? ORTE_METRIKEN;
	const hub = await seedHub(request, 'vergleich', {
		extra: { location_ids: orte, ...opts.oben, display_config: { active_metrics: metriken, ...opts.dc } }
	});
	return {
		kind,
		id: hub.id,
		aufraeumen: async () => {
			await hub.aufraeumen();
			for (const o of orte) await request.delete(`/api/locations/${o}`).catch(() => {});
		}
	};
}

/** Oeffnet den Hub im Reiter Wetter und wartet auf die geladene Karte. */
export async function oeffneKarte(page: Page, kind: HubKind, id: string): Promise<Locator> {
	await openHub(page, kind, id, { tab: 'wetter' });
	const karte = page.locator('[data-testid="was-steht-wo"]:visible').first();
	await expect(karte.locator('[data-testid="was-steht-wo-tabelle"], [data-testid="was-steht-wo-leer"]').first()).toBeVisible({ timeout: 20_000 });
	return karte;
}

export const zeile = (karte: Locator, metrik: string) => karte.locator(`[data-slot="et-zeile"][data-metrik="${metrik}"]`);
export const zelle = (karte: Locator, metrik: string, stelle: string) => zeile(karte, metrik).locator(`[data-slot="et-zelle"][data-stelle="${stelle}"]`);
export const haken = (karte: Locator, metrik: string, stelle: string) => zelle(karte, metrik, stelle).locator('input[type="checkbox"]');
export const knopf = (karte: Locator, metrik: string, stelle: string) => zelle(karte, metrik, stelle).locator('[data-slot="roh-einfach"]');
export const folge = (karte: Locator) => karte.locator('[data-slot="et-zeile"]').evaluateAll((z) => z.map((e) => e.getAttribute('data-metrik')!));

const tabellenPfad = (id: string) => `/api/briefings/${id}/placements`;

/** Antwort des Endpoints (als dieser Nutzer). */
export async function tabelle(request: APIRequestContext, kind: HubKind, id: string): Promise<Json> {
	const r = await request.get(`${tabellenPfad(id)}?kind=${kind}`);
	expect(r.ok(), `GET Tabelle: ${r.status()}`).toBeTruthy();
	return r.json();
}

/** Gespeicherter Abo-Stand (Trip bzw. Orte). */
export async function stand(request: APIRequestContext, kind: HubKind, id: string): Promise<Json> {
	const r = await request.get(hubApiPath(kind, id));
	expect(r.ok(), `GET ${hubApiPath(kind, id)}: ${r.status()}`).toBeTruthy();
	return r.json();
}

/** Wartet auf den erfolgreichen PUT der Tabelle und das folgende GET (Karte aktualisiert). */
export function tabelleGespeichert(page: Page, id: string): Promise<void> {
	const put = page.waitForResponse((r) => r.request().method() === 'PUT' && new URL(r.url()).pathname === tabellenPfad(id), { timeout: 20_000 });
	return put.then(async (r) => {
		expect(r.status(), `PUT Tabelle: ${r.status()}`).toBe(200);
		await page.waitForResponse((g) => g.request().method() === 'GET' && new URL(g.url()).pathname === tabellenPfad(id), { timeout: 20_000 });
	});
}

/** Wartet auf den erfolgreichen PUT eines Schalters unter der Tabelle (Trip- bzw. Orte-Ressource). */
export function schalterGespeichert(page: Page, kind: HubKind, id: string): Promise<Json> {
	return page
		.waitForResponse((r) => r.request().method() === 'PUT' && new URL(r.url()).pathname === hubApiPath(kind, id), { timeout: 20_000 })
		.then((r) => {
			expect(r.status(), `PUT Schalter: ${r.status()}`).toBe(200);
			return r.request().postDataJSON();
		});
}

/** Stellen-Flagge einer Zeile im gespeicherten `placements` (fehlende Flagge = an). */
export function gespeichertAn(placements: Json, metrik: string, stelle: string): boolean {
	const row = ((placements?.rows ?? []) as Json[]).find((r) => r.metric_id === metrik);
	return row?.places?.[stelle] !== false;
}

/** Erste Zeile, deren Zelle an `stelle` angehakt und bedienbar ist. */
export async function ersteAngehakte(karte: Locator, stelle: string, ohne: string[] = []): Promise<string> {
	for (const m of await folge(karte)) {
		if (ohne.includes(m)) continue;
		const h = haken(karte, m, stelle);
		if ((await h.count()) && (await h.isChecked()) && (await h.isEnabled())) return m;
	}
	throw new Error(`keine angehakte, bedienbare Zelle in ${stelle}`);
}
