// Gemeinsame Helfer der Playwright-Specs `s3a2794-teil3-*.spec.ts` — Issue #2794 S3a, Teil-PR 3 (Reiter Wetter).
// Spec: docs/specs/modules/feat_2794_s3a_teil3_wetter.md
//
// Keine .spec.ts-Datei. Enthaelt:
//   - WT: die testids des neuen Reiters (VERTRAG fuer die Umsetzung — der Developer setzt genau diese),
//   - Seed je Kontext (Trip `route` / Orts-Briefing `vergleich`) mit Vorlagen-Auswahl aus /api/templates,
//   - Lesen des gespeicherten Abo-Zustands per API (Datei-Zustand vorher/nachher),
//   - Warten auf den EINEN Schreibvorgang des Reiters (Trip: PUT /api/trips/{id}/weather-config,
//     Vergleich: PUT /api/compare/presets/{id}).
// Daten nur Wegwerf (Praefix E2E-GZ-), kein fester Schlaf, kein networkidle, nie gegen Produktion.

import { expect, type APIRequestContext, type Page, type Request, type Locator } from '@playwright/test';
import { createTestLocation, hubApiPath, openHub, seedHub, HUB_SEL, type HubKind, type SeededHub } from './helpers';

export type Json = any; // eslint-disable-line @typescript-eslint/no-explicit-any

export const DESKTOP = { width: 1280, height: 900 };
export const MOBIL = { width: 390, height: 844 };

/** testids des Reiters Wetter (shared/wetter-tab/, gleich fuer route und vergleich). */
export const WT = {
	tab: 'wetter-tab', // Wurzel von WetterTab.svelte, traegt data-context="route"|"vergleich"
	titel: 'wetter-tab-titel',
	erklaer: 'wetter-tab-erklaer',
	laden: 'wetter-tab-laden', // „Lade Metriken …" mit Platzhaltern
	fehler: 'wetter-tab-fehler',
	erneutLaden: 'wetter-tab-erneut-laden',
	// Vorlage-Karte
	picker: 'wetter-vorlage-picker', // Ausloeser „{Vorlage} ▾ {n Abweichungen | unverändert}"
	pickerStatus: 'wetter-vorlage-status', // nur „unverändert" bzw. „{n} Abweichung(en)"
	vorlageOption: (id: string) => `wetter-vorlage-option-${id}`, // Systemvorlage in der Liste
	vorlageBeschreibung: (id: string) => `wetter-vorlage-beschreibung-${id}`, // Kurzbeschreibung („14 Metriken · …")
	eigeneGruppe: 'wetter-vorlage-eigene',
	eigeneOption: (id: string) => `wetter-vorlage-eigene-${id}`,
	wechselDialog: 'wetter-vorlage-wechsel-dialog',
	wechselUebernehmen: 'wetter-vorlage-wechsel-uebernehmen',
	wechselAbbrechen: 'wetter-vorlage-wechsel-abbrechen',
	zuruecksetzen: 'wetter-vorlage-zuruecksetzen',
	alsEigene: 'wetter-vorlage-als-eigene',
	// Alarm ab fuer alle
	alarmAlle: 'wetter-alarm-ab-alle',
	alarmAlleStufe: (s: string) => `wetter-alarm-ab-alle-${s}`,
	zaehler: 'wetter-alarm-zaehler',
	// Metrik-Zeilen
	gruppe: (g: string) => `wetter-gruppe-${g}`,
	zeile: (id: string) => `wetter-zeile-${id}`,
	entfernen: (id: string) => `wetter-zeile-entfernen-${id}`,
	leiste: (id: string) => `wetter-ampel-leiste-${id}`,
	erklaersatz: (id: string) => `wetter-erklaersatz-${id}`,
	gruen: (id: string) => `wetter-gruen-${id}`,
	alarmAb: (id: string) => `wetter-alarm-ab-${id}`, // Segment bzw. Text „kein Alarm (Vorbote)" / „kein Alarm"
	alarmAbStufe: (id: string, s: string) => `wetter-alarm-ab-${id}-${s}`,
	grenzenAendern: (id: string) => `wetter-grenzen-aendern-${id}`, // Text „Grenzen ändern" / „Fertig"
	grenze: (id: string, seite: 'lower' | 'upper', farbe: 'yellow' | 'orange' | 'red') => `wetter-grenze-${id}-${seite}-${farbe}`,
	grenzenHinweis: (id: string) => `wetter-grenzen-hinweis-${id}`,
	grenzenAbweichend: (id: string) => `wetter-grenzen-abweichend-${id}`,
	grenzenFehler: (id: string) => `wetter-grenzen-fehler-${id}`,
	gewitterStufe: (stufe: 'mittel' | 'hoch') => `wetter-gewitter-${stufe}`, // Farbwahl je Stufe
	gewitterFarbe: (stufe: 'mittel' | 'hoch', farbe: string) => `wetter-gewitter-${stufe}-${farbe}`,
	gewitterKeins: 'wetter-gewitter-keins-hinweis',
	// Nicht im Briefing
	nichtImBriefing: 'wetter-nicht-im-briefing',
	plus: (id: string) => `wetter-nicht-im-briefing-plus-${id}`,
	hinzuMeldung: 'wetter-hinzugefuegt-meldung',
	// Karten
	warnungen: 'wetter-warnungen-schalter', // role=switch, aria-checked
	radar: 'wetter-radar-schalter', // nur vergleich
	anpassen: 'wetter-anpassen-karte',
	anpassenAuf: 'wetter-anpassen-aufklappen',
	// #2913 Scheibe (c): Uhrzeitfelder (molecules/UhrzeitFeld) im Stundenraster statt Select-Atom;
	// bedienen mit setzeStunde(), lesen mit stundeAnzeige().
	tagVon: 'day-window-start-hour',
	tagBis: 'day-window-end-hour',
	tagHinweisMitternacht: 'day-window-wrap-hint',
	// Dialog „Als eigene Vorlage speichern" (SavePresetDialog, bestehende testids)
	dialog: 'save-preset-dialog',
	dialogName: 'save-preset-name',
	dialogBeschreibung: 'save-preset-description',
	dialogStandard: 'save-preset-is-default',
	dialogHinweis: 'save-preset-hinweis',
	dialogFehler: 'save-preset-error',
	dialogSpeichern: 'save-preset-submit',
	dialogErfolg: 'wetter-vorlage-gespeichert'
} as const;

export const tid = (page: Page | Locator, id: string): Locator => page.locator(`[data-testid="${id}"]:visible`).first();

/**
 * #2913 Scheibe (c): Stunde in ein Tagesfenster-Uhrzeitfeld (molecules/UhrzeitFeld, Stundenraster) tippen.
 * Nur die Stunde ist ein Segment, die Minute steht fest auf 00. Zwei Ziffern machen das Segment fertig,
 * der Wert geht sofort als `HH:00` hinaus (segmentFeldMeldung.ts).
 */
export async function setzeStunde(page: Page, feld: Locator, stunde: number): Promise<void> {
	await feld.locator('[data-segment="hour"]').click();
	await page.keyboard.type(String(stunde).padStart(2, '0'));
}

/** Angezeigter Wert eines Tagesfenster-Uhrzeitfelds als `HH:00` (für toHaveText statt toHaveValue). */
export const stundeAnzeige = (stunde: number): string => `${String(stunde).padStart(2, '0')}:00`;

/** Eingabebereich eines Uhrzeitfelds (Segment Stunde + feste Minute). */
export const stundeEingabe = (feld: Locator): Locator => feld.locator('[data-slot="uhrzeit-feld-eingabe"]');

/** /api/templates (Vorlagen mit vollstaendiger Ampel). */
export async function vorlagen(request: APIRequestContext): Promise<Record<string, Json>> {
	const r = await request.get('/api/templates');
	expect(r.ok(), `GET /api/templates: ${r.status()}`).toBeTruthy();
	return Object.fromEntries(((await r.json()) as Json[]).map((t) => [t.id, t]));
}

/** /api/metrics flach: id -> Eintrag (group, alertable, is_precursor, allowed_sides, display_only, unit, label). */
export async function metriken(request: APIRequestContext): Promise<Record<string, Json>> {
	const r = await request.get('/api/metrics');
	expect(r.ok(), `GET /api/metrics: ${r.status()}`).toBeTruthy();
	const out: Record<string, Json> = {};
	for (const liste of Object.values((await r.json()) as Record<string, Json[]>)) for (const m of liste) out[m.id] = m;
	return out;
}

export const aktiveDerVorlage = (v: Json): string[] =>
	Object.entries(v.ampel.metrics as Record<string, Json>).filter(([, e]) => e.enabled === true).map(([id]) => id);

/**
 * Seed je Kontext mit Vorlage `vorlageId`: Auswahl = enabled-Metriken der Vorlage
 * (Trip: display_config.metrics[], Vergleich: display_config.active_metrics), ampel = {template, ...abo}.
 */
export async function seedWetter(
	request: APIRequestContext,
	kind: HubKind,
	opts: { vorlageId?: string; ampel?: Json; auswahl?: string[]; ohneActiveMetrics?: boolean; extra?: Json } = {}
): Promise<SeededHub & { orte: string[] }> {
	const vorlageId = opts.vorlageId ?? 'alpen-trekking';
	const v = (await vorlagen(request))[vorlageId];
	expect(v, `Vorlage ${vorlageId} fehlt in /api/templates`).toBeTruthy();
	const auswahl = opts.auswahl ?? aktiveDerVorlage(v);
	const ampel = { template: vorlageId, ...(opts.ampel ?? {}) };
	if (kind === 'route') {
		const hub = await seedHub(request, kind, {
			extra: {
				display_config: { preset_name: vorlageId, metrics: auswahl.map((metric_id) => ({ metric_id, enabled: true })), ampel },
				...(opts.extra ?? {})
			}
		});
		return { ...hub, orte: [] };
	}
	const orte: string[] = [];
	for (let i = 0; i < 2; i++) orte.push((await createTestLocation(request, { lat: 47.1 + i * 0.1, lon: 11.2 + i * 0.1 })).id);
	const display_config: Json = { ampel };
	if (!opts.ohneActiveMetrics) display_config.active_metrics = auswahl.map((metric_id) => ({ metric_id, aggregation: 'max' }));
	const hub = await seedHub(request, kind, { extra: { location_ids: orte, display_config, ...(opts.extra ?? {}) } });
	return {
		...hub,
		orte,
		aufraeumen: async () => {
			await hub.aufraeumen();
			for (const o of orte) await request.delete(`/api/locations/${o}`).catch(() => {});
		}
	};
}

/** Gespeicherter Abo-Zustand (Trip bzw. Vergleichs-Preset) per API. */
export async function stand(request: APIRequestContext, kind: HubKind, id: string): Promise<Json> {
	const r = await request.get(hubApiPath(kind, id));
	expect(r.ok(), `GET ${hubApiPath(kind, id)}: ${r.status()}`).toBeTruthy();
	return r.json();
}

/** Aktive Auswahl aus der Abo-Quelle (Trip: metrics[] enabled, Vergleich: active_metrics), als Menge. */
export function auswahlImStand(kind: HubKind, s: Json): string[] {
	const dc = s.display_config ?? {};
	const ids =
		kind === 'route'
			? ((dc.metrics ?? []) as Json[]).filter((m) => m.enabled !== false).map((m) => m.metric_id)
			: ((dc.active_metrics ?? []) as Json[]).map((m) => (typeof m === 'string' ? m : m.metric_id));
	return [...new Set(ids)].sort();
}

/** Ist das ein Schreibvorgang DES REITERS WETTER? */
export function istWetterSchreiben(kind: HubKind, id: string): (r: Request) => boolean {
	return (r) => {
		if (r.method() !== 'PUT') return false;
		const p = new URL(r.url()).pathname;
		return kind === 'route' ? p === `/api/trips/${id}/weather-config` : p === `/api/compare/presets/${id}`;
	};
}

/** Wartet auf die (erfolgreiche) Antwort des naechsten Schreibvorgangs des Reiters. */
export async function warteAufSpeichern(page: Page, kind: HubKind, id: string): Promise<void> {
	const pruef = istWetterSchreiben(kind, id);
	const antwort = await page.waitForResponse((r) => pruef(r.request()), { timeout: 20_000 });
	expect(antwort.ok(), `Speichern ${antwort.request().url()}: HTTP ${antwort.status()}`).toBeTruthy();
}

/** Oeffnet den Hub im Reiter Wetter und wartet, bis der Reiter geladen ist (kein Ladezustand mehr). */
export async function oeffneWetter(page: Page, kind: HubKind, id: string): Promise<Locator> {
	await openHub(page, kind, id, { tab: 'wetter' });
	const panel = page.locator(`[data-testid="${HUB_SEL[kind].panel}-wetter"]:visible`).first();
	const reiter = panel.getByTestId(WT.tab);
	await expect(reiter).toBeVisible({ timeout: 15_000 });
	await expect(reiter).toHaveAttribute('data-context', kind);
	await expect(reiter.getByTestId(WT.laden)).toHaveCount(0, { timeout: 15_000 });
	return reiter;
}

/** Picker-Status als Zahl (0 = „unverändert"). */
export async function abweichungen(reiter: Locator): Promise<number> {
	const t = ((await reiter.getByTestId(WT.pickerStatus).first().innerText()) ?? '').trim();
	if (/^unverändert$/i.test(t) || /^unchanged$/i.test(t)) return 0;
	const m = t.match(/(\d+)/);
	expect(m, `Picker-Status nicht lesbar: „${t}"`).toBeTruthy();
	return Number(m![1]);
}

/** Schluessel, die der Reiter Wetter NICHT anfassen darf (Zustellung, Etappen/Orte, Name). */
export function fremdeFelder(kind: HubKind, s: Json): Json {
	const dc = { ...(s.display_config ?? {}) };
	for (const k of ['ampel', 'metrics', 'active_metrics', 'preset_name']) delete dc[k];
	const rc = { ...(s.report_config ?? {}) };
	delete rc.day_window_start_hour;
	delete rc.day_window_end_hour;
	return kind === 'route'
		? { name: s.name, stages: s.stages, report_config: rc, display_config: dc, alert_cooldown_minutes: s.alert_cooldown_minutes }
		: {
				name: s.name,
				location_ids: s.location_ids,
				morning_time: s.morning_time,
				evening_time: s.evening_time,
				empfaenger: s.empfaenger,
				display_config: dc
			};
}
