// Gemeinsame Helper fuer den Trip-Wizard (Epic #136 Master-Spec).
// Quelle: docs/specs/modules/epic_136_trip_wizard.md §1.3, §3.2, §3.3

import type { ActivityType, Stage } from '$lib/types';

/**
 * Kanonische Aggregations-Profile aus `docs/specs/modules/activity_profile.md`.
 *
 * Hinweis: `'wandern'` wird aktuell von keinem `mapActivityToProfile`-Output
 * produziert (kein UI-`ActivityType` mappt darauf). Der Wert bleibt im Union,
 * weil das Backend ihn akzeptiert und kuenftige Aktivitaeten (z.B. ein
 * dediziertes "Tageswanderung"-Profil) ihn liefern koennten.
 */
export type AggregationProfile = 'wintersport' | 'wandern' | 'summer_trekking' | 'allgemein';

/**
 * Erzeugt eine kurze, eindeutige ID (8 Zeichen aus crypto.randomUUID).
 */
export function newId(): string {
	return crypto.randomUUID().slice(0, 8);
}

/**
 * Liefert das heutige Datum als ISO YYYY-MM-DD (lokale Zeitzone).
 */
export function today(): string {
	const now = new Date();
	const yyyy = now.getFullYear();
	const mm = String(now.getMonth() + 1).padStart(2, '0');
	const dd = String(now.getDate()).padStart(2, '0');
	return `${yyyy}-${mm}-${dd}`;
}

/**
 * Addiert `days` Tage zu einem ISO-Datum YYYY-MM-DD und liefert das neue ISO-Datum.
 * UTC-sicher; respektiert Monats- und Jahresgrenzen.
 */
export function addDays(iso: string, days: number): string {
	const [y, m, d] = iso.split('-').map(Number);
	const dt = new Date(Date.UTC(y, m - 1, d));
	dt.setUTCDate(dt.getUTCDate() + days);
	const yyyy = dt.getUTCFullYear();
	const mm = String(dt.getUTCMonth() + 1).padStart(2, '0');
	const dd = String(dt.getUTCDate()).padStart(2, '0');
	return `${yyyy}-${mm}-${dd}`;
}

/**
 * Formatiert eine Etappen-Nummer fuer die UI.
 * 0-basierter Index; Ausgabe T + (index+1) gepadded auf min. 2 Stellen.
 * formatStageNumber(0)  === 'T01'
 * formatStageNumber(9)  === 'T10'
 * formatStageNumber(99) === 'T100'
 */
export function formatStageNumber(index: number): string {
	return `T${String(index + 1).padStart(2, '0')}`;
}

/**
 * Pausentag-Heuristik: Etappe ohne Wegpunkte zaehlt als Pause.
 * Kein neues Modellfeld — UI-Logik aus Master-Spec §3.2.
 */
export function isPauseStage(stage: Pick<Stage, 'waypoints'>): boolean {
	return !stage.waypoints || stage.waypoints.length === 0;
}

/**
 * Maskiert eine Telefonnummer fuer die UI: nur die letzten 4 Ziffern bleiben
 * sichtbar, der Praefix (Laender-/Vorwahl) bleibt erhalten, dazwischen `•••`.
 * Issue #412 — Kanal-Karte (Signal/SMS-Nummer maskiert).
 *
 * maskPhone('+49 151 23 45 8847') === '+49 151 ••• 8847'
 * maskPhone('') === maskPhone(undefined) === maskPhone(null) === ''
 */
export function maskPhone(raw?: string | null): string {
	if (!raw) return '';
	const s = raw.trim();
	if (!s) return '';
	const digits = s.replace(/\D/g, '');
	if (digits.length <= 6) return s; // zu kurz zum sinnvollen Maskieren
	const plus = s.startsWith('+') ? '+' : '';
	const cc = digits.slice(0, 2); // Laendervorwahl, z.B. "49"
	const net = digits.slice(2, 5); // Netz/Vorwahl, z.B. "151"
	const last4 = digits.slice(-4); // letzte 4 sichtbar
	return `${plus}${cc} ${net} ••• ${last4}`;
}

/**
 * Mapping UI-Aktivitaet → kanonisches Aggregations-Profil
 * (siehe Master-Spec §1.3).
 */
export function mapActivityToProfile(activity: ActivityType): AggregationProfile {
	switch (activity) {
		case 'skitour':
			return 'wintersport';
		case 'trekking':
			return 'summer_trekking';
		case 'hochtour':
			return 'summer_trekking';
		case 'klettersteig':
			return 'summer_trekking';
		case 'mtb':
			return 'allgemein';
	}
}
