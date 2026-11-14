// Issue #2795 S3b, Teilschritt 1b — der EINE Speicherer des Reiters „Zustellung“ (AC-33).
// Spec: docs/specs/modules/feat_2795_s3b_teil1_zustellung.md (Implementation Details §3).
//
// Aus Basis-Stand (zuletzt gespeichert) und aktuellem Formularstand entstehen zwei Nutzlast-Teile:
//   - Teil `versand` (Owner 'versand'): Morgen/Abend-Zeit und -Schalter, Briefing-Kanalschalter
//     (send_*), Laufzeit Orte (end_date). Trip unter `report_config` (Server-Merge je Schluessel),
//     Orte top-level.
//   - Teil `alarme` (Owner 'alarme'): alert_channels, alert_channel_thresholds,
//     alert_quiet_from/_to, alert_cooldown_minutes. Immer top-level.
// Gesendet werden NUR geaenderte Felder (AC-32). Nie gesendet: alert_metric_channels (AC-27),
// ampel, display_config, telegram_style und alle Felder des Uebergangsblocks.
// Eine Uhrzeit ausserhalb des Viertelstunden-Rasters wird nicht gesendet (AC-8).
//
// Kein Browser-/SvelteKit-Import — lauffaehig unter node --experimental-strip-types.

import type { SaveFn, SaveStatus } from '../../../stores/saveStatusStore.svelte.ts';
import { merkeNutzlast } from '../../../stores/nutzlastStand.ts';
import type { PutClient } from '../tripSpeicherung.ts';
import { toHHMMSS } from '../../../utils/time.ts';
import { KANAELE, zeitFehler, type Kontext, type ZustellungStand } from './zustellungModell.ts';

type Rec = Record<string, unknown>;
export type ZustellungTeil = 'versand' | 'alarme';
export interface ZustellungNutzlast {
	versand: Rec | null;
	alarme: Rec | null;
}

const gleich = (a: unknown, b: unknown) => JSON.stringify(a) === JSON.stringify(b);
const zeitGueltig = (z: string) => zeitFehler(z) === null;
const alleVier = <T>(r: Record<string, T>): Record<string, T> => Object.fromEntries(KANAELE.map((k) => [k, r[k]]));

/** Kontext-Unterschiede als Daten (Ratsche context_herkunft_zweige_eingefroren). Trip: Briefing-
 *  Felder unter `report_config` mit Gesamtschalter `enabled`, Laufzeit aus den Etappen; Orte:
 *  Felder top-level, eigene Laufzeit `end_date`. */
const KONTEXT: Record<Kontext, { pfad: (id: string) => string; verpacke: (f: Rec) => Rec; gesamtschalter: boolean; laufzeit: boolean }> = {
	route: { pfad: (id) => `/api/trips/${id}`, verpacke: (f) => ({ report_config: f }), gesamtschalter: true, laufzeit: false },
	vergleich: { pfad: (id) => `/api/compare/presets/${id}`, verpacke: (f) => f, gesamtschalter: false, laufzeit: true }
};

function versandTeil(context: Kontext, vorher: ZustellungStand, jetzt: ZustellungStand): Rec | null {
	const felder: Rec = {};
	if (jetzt.morgenAn !== vorher.morgenAn) felder.morning_enabled = jetzt.morgenAn;
	if (jetzt.abendAn !== vorher.abendAn) felder.evening_enabled = jetzt.abendAn;
	// Trip: `enabled` ist der Gesamtschalter (reportSlotAktiv) — er folgt den beiden Slots.
	if (KONTEXT[context].gesamtschalter && ('morning_enabled' in felder || 'evening_enabled' in felder)) {
		felder.enabled = jetzt.morgenAn || jetzt.abendAn;
	}
	if (jetzt.morgenZeit !== vorher.morgenZeit && zeitGueltig(jetzt.morgenZeit)) felder.morning_time = toHHMMSS(jetzt.morgenZeit);
	if (jetzt.abendZeit !== vorher.abendZeit && zeitGueltig(jetzt.abendZeit)) felder.evening_time = toHHMMSS(jetzt.abendZeit);
	for (const k of KANAELE) {
		if (jetzt.briefing[k] !== vorher.briefing[k]) felder[`send_${k}`] = jetzt.briefing[k];
	}
	// Laufzeit gibt es nur bei Orten; die Trip-Laufzeit kommt aus den Etappen.
	if (KONTEXT[context].laufzeit && (jetzt.endDate ?? null) !== (vorher.endDate ?? null)) {
		felder.end_date = jetzt.endDate ?? '';
	}
	if (Object.keys(felder).length === 0) return null;
	return KONTEXT[context].verpacke(felder);
}

function alarmeTeil(vorher: ZustellungStand, jetzt: ZustellungStand): Rec | null {
	const felder: Rec = {};
	if (!gleich(alleVier(jetzt.alarme), alleVier(vorher.alarme))) felder.alert_channels = alleVier(jetzt.alarme);
	if (!gleich(alleVier(jetzt.dringlichkeit), alleVier(vorher.dringlichkeit))) {
		felder.alert_channel_thresholds = alleVier(jetzt.dringlichkeit);
	}
	if (!jetzt.stilleAn) {
		// Ausschalten loescht beide Felder ausdruecklich (ein fehlender Schluessel hiesse „behalten“, #2211).
		if (vorher.stilleAn) {
			felder.alert_quiet_from = null;
			felder.alert_quiet_to = null;
		}
	} else {
		if (!vorher.stilleAn || jetzt.stilleVon !== vorher.stilleVon) felder.alert_quiet_from = jetzt.stilleVon;
		if (!vorher.stilleAn || jetzt.stilleBis !== vorher.stilleBis) felder.alert_quiet_to = jetzt.stilleBis;
	}
	if (jetzt.cooldown !== vorher.cooldown) felder.alert_cooldown_minutes = jetzt.cooldown;
	return Object.keys(felder).length === 0 ? null : felder;
}

/** Die beiden Nutzlast-Teile (null = nichts geaendert). Reine Funktion. */
export function zustellungNutzlast(context: Kontext, vorher: ZustellungStand, jetzt: ZustellungStand): ZustellungNutzlast {
	return { versand: versandTeil(context, vorher, jetzt), alarme: alarmeTeil(vorher, jetzt) };
}

/** Uebernimmt nach erfolgreichem Speichern die Felder EINES Teils in die Basis. Eine nicht
 *  gesendete (rasterfremde) Uhrzeit bleibt auf dem gespeicherten Wert. */
function basisNachSpeichern(teil: ZustellungTeil, basis: ZustellungStand, gesendet: ZustellungStand): ZustellungStand {
	const kopie = JSON.parse(JSON.stringify(gesendet)) as ZustellungStand;
	if (teil === 'versand') {
		return {
			...basis,
			morgenAn: kopie.morgenAn,
			abendAn: kopie.abendAn,
			morgenZeit: zeitGueltig(kopie.morgenZeit) ? kopie.morgenZeit : basis.morgenZeit,
			abendZeit: zeitGueltig(kopie.abendZeit) ? kopie.abendZeit : basis.abendZeit,
			briefing: kopie.briefing,
			endDate: kopie.endDate
		};
	}
	return {
		...basis,
		alarme: kopie.alarme,
		dringlichkeit: kopie.dringlichkeit,
		stilleAn: kopie.stilleAn,
		stilleVon: kopie.stilleVon,
		stilleBis: kopie.stilleBis,
		cooldown: kopie.cooldown
	};
}

export interface ZustellungSpeicherungOptionen {
	context: Kontext;
	/** Trip-ID bzw. Preset-ID. */
	id: string;
	/** `api` (If-Match, Server-Merge). */
	client: PutClient;
	saveController: SaveStatus;
	/** Stand nach Hydration (zuletzt gespeichert). */
	basis: ZustellungStand;
	/** Nur vergleich: Hub-Schreibschlange (Serialisierung mit den Nachbar-Reitern). */
	enqueueHubWrite?: <T>(fn: () => Promise<T>) => Promise<T>;
	/** Server-Antwort nach Erfolg (Trip bzw. Preset). */
	onAntwort?: (antwort: unknown) => void;
}

/**
 * Orchestrierung: `aenderungMelden(jetzt)` merkt den Formularstand und plant je geaendertem Teil
 * einen Speichervorgang unter dem Owner des Teils ein. Die Speicherfunktion liest Basis und Stand
 * erst bei Ausfuehrung (eine waehrend der Entprellung gemeldete Aenderung geht mit). Ohne
 * Unterschied zur Basis wird ein eigener, noch nicht gestarteter Vorgang verworfen.
 * Bei einem Fehler bleibt die Basis stehen — der naechste Vorgang (oder „Erneut versuchen“
 * des Controllers) sendet denselben Unterschied erneut.
 */
export function erstelleZustellungSpeicherung(opt: ZustellungSpeicherungOptionen): { aenderungMelden(jetzt: ZustellungStand): void } {
	const { context, client, saveController } = opt;
	const pfad = KONTEXT[context].pfad(opt.id);
	let basis: ZustellungStand = JSON.parse(JSON.stringify(opt.basis));
	let aktuell: ZustellungStand = JSON.parse(JSON.stringify(opt.basis));
	const aussteht: Record<ZustellungTeil, boolean> = { versand: false, alarme: false };

	function speicherFn(teil: ZustellungTeil): SaveFn {
		const fn: SaveFn = async (init) => {
			aussteht[teil] = false;
			const lauf = async () => {
				const gesendet: ZustellungStand = JSON.parse(JSON.stringify(aktuell));
				const nutzlast = zustellungNutzlast(context, basis, gesendet)[teil];
				if (!nutzlast) return;
				merkeNutzlast(fn, nutzlast);
				const antwort = await client.put<unknown>(pfad, nutzlast, init);
				basis = basisNachSpeichern(teil, basis, gesendet);
				opt.onAntwort?.(antwort);
			};
			await (opt.enqueueHubWrite ? opt.enqueueHubWrite(lauf) : lauf());
		};
		return fn;
	}

	function melden(teil: ZustellungTeil, geaendert: boolean): void {
		if (!geaendert) {
			if (aussteht[teil]) {
				aussteht[teil] = false;
				saveController.cancel(teil);
			}
			return;
		}
		aussteht[teil] = true;
		if (teil === 'versand') saveController.schedule(speicherFn('versand'), 700, 'versand');
		else saveController.schedule(speicherFn('alarme'), 700, 'alarme');
	}

	return {
		aenderungMelden(jetzt: ZustellungStand): void {
			aktuell = JSON.parse(JSON.stringify(jetzt));
			const n = zustellungNutzlast(context, basis, aktuell);
			melden('versand', n.versand !== null);
			melden('alarme', n.alarme !== null);
		}
	};
}
