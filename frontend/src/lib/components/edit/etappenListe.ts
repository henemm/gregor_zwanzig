// Issue #3007 (Epic #2913): Inhalte der Etappen-Listenzeile im Hub (Mockup Fassung 3, viewEtappen
// Z. 577-587): „E{n} · Start → Ziel“, Zweitzeile „x km · ↑y m“, Meta „Gehzeit h:mm“.
// Reine Funktionen ohne DOM; Texte über die übergebene Katalogfunktion (`$t`) in der Nutzersprache.
// Gehzeit aus der vorhandenen Rechnung des Editors (computeArrivalTimes/activityToSpeed), damit sie
// mit den Ankunftszeiten der Wegpunkte übereinstimmt (AC-11).
// Spec: docs/specs/modules/feat_3007_etappen_orte_listen.md (AC-10 bis AC-12).
import type { Stage } from '$lib/types';
import type { Lang, MessageKey } from '$lib/i18n';
import { computeHeaderStats } from '../email-preview/headerStats.ts';
import { computeArrivalTimes } from '../../utils/naismith.ts';
import { isPauseStage } from '../shared/wizardHelpers.ts';

// Knopf „Tempo ändern“ folgt mit #2796; die Elementliste führt seinen Schlüssel schon:
// i18n-dynamic: trip.hub.tempo_aendern
type Katalog = (key: MessageKey, params?: Record<string, string | number>) => string;

export interface EtappenZeile {
	titel: string;
	zweitzeile?: string;
	meta?: string;
}

function zahl(lang: Lang, wert: number, nachkomma: number): string {
	const loc = lang === 'en' ? 'en-GB' : 'de-DE';
	return new Intl.NumberFormat(loc, { minimumFractionDigits: nachkomma, maximumFractionDigits: nachkomma }).format(wert);
}

const minuten = (hhmm: string): number => Number(hhmm.slice(0, 2)) * 60 + Number(hhmm.slice(3));

/** Gehzeit in Minuten: letzte minus erste Ankunft (über Mitternacht fortgezählt); null ohne Strecke. */
export function gehzeitMinuten(stage: Stage, tempoKmh: number): number | null {
	const ankunft = computeArrivalTimes(stage, stage.start_time, tempoKmh);
	if (ankunft.length < 2) return null;
	const d = minuten(ankunft[ankunft.length - 1]) - minuten(ankunft[0]);
	return d < 0 ? d + 24 * 60 : d;
}

/** `h:mm` (Protokollform, in beiden Sprachen gleich). */
export function dauerText(min: number): string {
	return `${Math.floor(min / 60)}:${String(min % 60).padStart(2, '0')}`;
}

/** Zweitzeile „x km · ↑y m“; fehlt der Aufstieg, nur die Distanz (kein verwaistes „·“). */
function kennzahlen(stage: Stage, lang: Lang, t: Katalog): string {
	const s = computeHeaderStats(stage);
	const km = zahl(lang, s.distanceKm, 1);
	const aufstieg = Math.round(s.ascentM);
	return aufstieg > 0 ? t('trip.hub.etappe_kennzahlen', { km, aufstieg: zahl(lang, aufstieg, 0) }) : `${km} km`;
}

/** Zeileninhalt der Etappe an Position `index` (0-basiert). Pausentag: nur Titel. */
export function etappenZeile(stage: Stage, index: number, lang: Lang, t: Katalog, tempoKmh: number): EtappenZeile {
	const n = index + 1;
	const wps = stage.waypoints ?? [];
	if (isPauseStage(stage) || wps.length < 2) {
		const name = stage.name?.trim() || t('bausteine.etappe.pausentag');
		return { titel: t('trip.hub.etappe_titel_name', { n, name }) };
	}
	const titel = t('trip.hub.etappe_titel', { n, start: wps[0].name, ziel: wps[wps.length - 1].name });
	const dauer = gehzeitMinuten(stage, tempoKmh);
	const meta = dauer === null ? undefined : t('trip.hub.etappe_gehzeit', { dauer: dauerText(dauer) });
	return { titel, zweitzeile: kennzahlen(stage, lang, t), meta };
}
