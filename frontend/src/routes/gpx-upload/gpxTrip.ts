// Issue #2657 (i18n F8): Hochladen und Speichern der GPX-Seite als pruefbare Helfer.
// Nutzertexte stehen nur als Katalogschluessel (layout.gpx.*), die Seite zeigt sie
// ueber $t — so folgt ein Fehlerhinweis auch einem spaeteren Sprachwechsel.
// Der Trip-Name bleibt exakt der Nutzereingabe (keine Uebersetzung, keine Kuerzung).

import type { Waypoint } from '$lib/types.js';
import type { MessageKey } from '$lib/i18n';

export interface GpxEtappe {
	name: string;
	date: string;
	waypoints: Waypoint[];
}

export const GPX_MAX_BYTES = 10 * 1024 * 1024; // 10 MB

/** Fehlerschluessel der Dateipruefung vor dem Hochladen, `null` = Datei ist in Ordnung. */
export function gpxDateiFehler(datei: { name: string; size: number } | undefined): MessageKey | null {
	if (!datei) return 'layout.gpx.fehler_keine_datei';
	if (datei.size > GPX_MAX_BYTES) return 'layout.gpx.fehler_zu_gross';
	if (!datei.name.toLowerCase().endsWith('.gpx')) return 'layout.gpx.fehler_nur_gpx';
	return null;
}

/** Trip-Kennung aus dem Namen (Kleinbuchstaben, Ziffern, Bindestriche). */
export function gpxTripId(name: string): string {
	return name
		.toLowerCase()
		.replace(/\s+/g, '-')
		.replace(/[^a-z0-9-]/g, '')
		.replace(/-+/g, '-')
		.replace(/^-|-$/g, '');
}

/** Datei an POST /api/gpx/parse; wirft das Fehlerobjekt des Servers unveraendert weiter. */
export async function gpxHochladen(datei: File, stageDate: string, startHour: number): Promise<GpxEtappe> {
	const formData = new FormData();
	formData.append('file', datei);
	if (stageDate) formData.append('stage_date', stageDate);
	formData.append('start_hour', String(startHour));
	const res = await fetch('/api/gpx/parse', { method: 'POST', body: formData });
	if (!res.ok) throw await res.json().catch(() => ({ error: `HTTP ${res.status}` }));
	return (await res.json()) as GpxEtappe;
}

/** Nutzlast fuer POST /api/trips: ein Trip mit genau der hochgeladenen Etappe. */
export function baueGpxTrip(tripName: string, etappe: GpxEtappe) {
	const id = gpxTripId(tripName);
	return {
		id,
		name: tripName,
		stages: [{ id: id + '-t1', name: etappe.name, date: etappe.date, waypoints: etappe.waypoints }]
	};
}
