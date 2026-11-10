// Gemeinsame Helfer der CI-Specs, die mit #2794 Teil 3 vom Reiter „Wertebereiche" (CorridorEditor,
// bis Teil 3 nur lesbar) auf den Reiter Wetter (`WetterTab`, „Grenzen ändern") umgezogen sind:
// hub-wertebereiche-speichert-selbst.spec.ts (WS) und hub-wertebereiche-wertprops.spec.ts (WW).
// Spec: docs/specs/modules/feat_2794_s3a_teil3_wetter.md (§4, Datenfluss, AC-16, AC-19, AC-38).
//
// Keine .spec.ts-Datei. Seed je Kontext mit Vorlage „wandern" UND den Altfeldern, die der Reiter
// Wetter nie anfassen darf (Korridore, Vergleich zusätzlich ideal_ranges/telegram_style), Zähler für
// die Schreibvorgänge des Reiters, Stabilitätsfenster statt festem Schlaf.

import { expect, type APIRequestContext, type Locator, type Page, type Request } from '@playwright/test';
import { hubApiPath, seedHub, type HubKind, type SeededHub } from './helpers';
import { WT, aktiveDerVorlage, istWetterSchreiben, vorlagen, type Json } from './s3a2794-teil3.helpers';

export type Stand = Record<string, Json>;
export const dc = (s: Stand): Stand => (s.display_config as Stand | undefined) ?? {};

/** Altfelder je Kontext, die der Reiter Wetter NIE verändern darf (Spec Datenfluss, AC-30). */
export const ALTFELDER: Record<HubKind, (s: Stand) => Record<string, unknown>> = {
	route: (s) => ({ corridors: s.corridors }),
	vergleich: (s) => ({ corridors: s.corridors, ideal_ranges: dc(s).ideal_ranges, telegram_style: dc(s).telegram_style })
};

/**
 * Seed mit Vorlage „wandern" (Auswahl = aktive Metriken der Vorlage), `ampel` mit optionalen
 * Abweichungen, beide Warn-Felder gleich (AC-20) und den Altfeldern (Korridore usw.).
 */
export async function seedGrenzen(
	request: APIRequestContext,
	kind: HubKind,
	ampelMetrics: Json = {}
): Promise<SeededHub & { auswahl: string[] }> {
	const v = (await vorlagen(request)).wandern;
	expect(v, 'Vorlage wandern fehlt in /api/templates').toBeTruthy();
	const auswahl = aktiveDerVorlage(v);
	const ampel = { template: 'wandern', ...(Object.keys(ampelMetrics).length ? { metrics: ampelMetrics } : {}) };
	const gemeinsam = { official_alerts_enabled: true, official_warnings: { enabled: true } };
	const extra: Json =
		kind === 'route'
			? {
					...gemeinsam,
					corridors: [{ metric: 'wind_gust', range: [30, 70], notify: false, mark: false }],
					display_config: { preset_name: 'wandern', metrics: auswahl.map((metric_id) => ({ metric_id, enabled: true })), ampel }
				}
			: {
					...gemeinsam,
					radar_alert_enabled: false,
					send_telegram: true,
					send_sms: false,
					alert_cooldown_minutes: 45,
					corridors: [{ metric: 'snow_depth_cm', range: [30, 200], notify: false, mark: true }],
					display_config: {
						ideal_ranges: { snow_depth_cm: { min: 30, max: 200 } },
						active_metrics: auswahl.map((metric_id) => ({ metric_id, aggregation: 'max' })),
						telegram_style: 'kurzform',
						ampel
					}
				};
	const hub = await seedHub(request, kind, { extra });
	return { ...hub, auswahl };
}

export async function stand(page: Page, kind: HubKind, id: string): Promise<Stand> {
	const res = await page.request.get(hubApiPath(kind, id));
	expect(res.ok(), `GET ${hubApiPath(kind, id)} HTTP ${res.status()}`).toBeTruthy();
	return (await res.json()) as Stand;
}

/** Schreibvorgänge DES REITERS (Trip: PUT weather-config, Vergleich: PUT Preset), abgeschickt bzw. beantwortet. */
export function zaehleWetterSchreiben(page: Page, kind: HubKind, id: string): { puts: Request[]; beantwortet: Request[] } {
	const trifft = istWetterSchreiben(kind, id);
	const puts: Request[] = [];
	const beantwortet: Request[] = [];
	page.on('request', (r) => {
		if (trifft(r)) puts.push(r);
	});
	page.on('requestfinished', (r) => {
		if (trifft(r)) beantwortet.push(r);
	});
	return { puts, beantwortet };
}

/** Alle schreibenden Anfragen auf das Objekt und seine Unterpfade (PUT/PATCH/POST). */
export function zaehleAlleSchreiben(page: Page, kind: HubKind, id: string): Request[] {
	const basis = hubApiPath(kind, id);
	const liste: Request[] = [];
	page.on('request', (r) => {
		if (['PUT', 'PATCH', 'POST', 'DELETE'].includes(r.method()) && new URL(r.url()).pathname.startsWith(basis)) liste.push(r);
	});
	return liste;
}

/** Stabilitätsfenster statt festem Schlaf: `lies()` muss `ms` lang `soll` liefern. */
export async function bleibtBei(lies: () => number, soll: number, ms: number, message: string): Promise<void> {
	let seit = 0;
	await expect
		.poll(
			() => {
				const n = lies();
				if (n !== soll) {
					seit = 0;
					return n;
				}
				seit ||= Date.now();
				return Date.now() - seit >= ms ? 'stabil' : n;
			},
			{ message, timeout: ms + 8_000, intervals: [200] }
		)
		.toBe('stabil');
}

export const anzeige = (page: Page) => page.locator('[data-testid="save-indicator"]');

/** „Grenzen ändern" einer Zeile öffnen; liefert die Zeile. */
export async function grenzenOeffnen(reiter: Locator, id: string): Promise<Locator> {
	const zeile = reiter.getByTestId(WT.zeile(id));
	await zeile.getByTestId(WT.grenzenAendern(id)).click();
	await expect(zeile.getByTestId(WT.grenzenAendern(id))).toHaveText('Fertig');
	return zeile;
}

/** „Fertig" einer offenen Zeile. */
export async function fertig(zeile: Locator, id: string): Promise<void> {
	await zeile.getByTestId(WT.grenzenAendern(id)).click();
	await expect(zeile.getByTestId(WT.grenzenAendern(id))).toHaveText('Grenzen ändern');
}

/** Gespeicherte Seite einer Ampel-Zeile ohne leere Felder. */
export function seiteImStand(s: Stand, id: string, seite: 'lower' | 'upper'): Record<string, number> {
	const roh = (dc(s).ampel?.metrics?.[id]?.[seite] ?? {}) as Record<string, number | null>;
	return Object.fromEntries(Object.entries(roh).filter(([, v]) => v !== null && v !== undefined)) as Record<string, number>;
}
