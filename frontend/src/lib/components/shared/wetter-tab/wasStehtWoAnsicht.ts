// Issue #3122 B3b — Karte „Was steht wo“: aus der Antwort von GET /api/briefings/{id}/placements die Props der
// Bausteine (EinstellTabelle, Haken, RohEinfachKnopf) und die Texte unter der Tabelle. Spec Teil B Nr. 10 bis 12;
// Soll-Bild docs/context/einstellungen_neu/seiten/mockup-hub-fassung4.html, Wortlaut einstellungen_neu.md §5 Punkt 8.
// Namen, Kürzel, Beispielwerte, SMS-Beispiel kommen aus der Antwort; alle übrigen Texte aus dem Katalog
// (wetter.json). Kontext-Unterschiede stehen als Daten in der Antwort (Spalten, Unterzeilen, Zahl der Orte).
// Kein Browser-/SvelteKit-Import, lauffähig unter node --experimental-strip-types.

import type { EinstellFesteZeile, EinstellMetrik, EinstellStelle, EinstellZelle } from '../../molecules/EinstellTabelle.svelte';
import type { MessageKey } from '../../../i18n/index.ts';
import type { ApiZelle, PlacementsAntwort } from './wasStehtWoStand.ts';

export type Uebersetzer = (key: MessageKey, params?: Record<string, string | number>) => string;
export type MehrzahlUebersetzer = (key: string, count: number, params?: Record<string, string | number>) => string;

/** Zustand der Schalter, die die Spalten steuern (lokal, damit ein Klick sofort wirkt). */
export interface Spaltenlage {
	kurzstil: boolean;
	stundenverlaufAn: boolean;
	ausblickAn: boolean;
}

const SPALTE: Record<string, { titel: MessageKey; kurz?: MessageKey; zelle: MessageKey; abgesetzt?: boolean }> = {
	email: { titel: 'wetter.wsw.spalte.email', zelle: 'wetter.wsw.zelle.email' },
	telegram: { titel: 'wetter.wsw.spalte.telegram', kurz: 'wetter.wsw.spalte.telegram_kurz', zelle: 'wetter.wsw.zelle.telegram' },
	sms: { titel: 'wetter.wsw.spalte.sms', zelle: 'wetter.wsw.zelle.sms' },
	hourly: { titel: 'wetter.wsw.spalte.hourly', kurz: 'wetter.wsw.spalte.hourly_kurz', zelle: 'wetter.wsw.zelle.hourly', abgesetzt: true },
	outlook: { titel: 'wetter.wsw.spalte.outlook', kurz: 'wetter.wsw.spalte.outlook_kurz', zelle: 'wetter.wsw.zelle.outlook', abgesetzt: true }
};
const UNTERZEILE: Record<string, MessageKey> = {
	stundentabelle: 'wetter.wsw.unterzeile.stundentabelle',
	uebersicht: 'wetter.wsw.unterzeile.uebersicht',
	nachricht: 'wetter.wsw.unterzeile.nachricht',
	und_premium_sms: 'wetter.wsw.unterzeile.und_premium_sms',
	nur_email: 'wetter.wsw.unterzeile.nur_email',
	email_und_telegram: 'wetter.wsw.unterzeile.email_und_telegram'
};
const GRUND: Record<string, MessageKey> = {
	kein_stundenwert: 'wetter.wsw.grund.kein_stundenwert',
	keine_eigene_spalte: 'wetter.wsw.grund.keine_eigene_spalte',
	kein_tageswert: 'wetter.wsw.grund.kein_tageswert',
	kein_kuerzel: 'wetter.wsw.grund.kein_kuerzel'
};
const MARKE: Record<string, { text: MessageKey; ton: 'warn' | 'leise' }> = {
	passt_nicht_mehr: { text: 'wetter.wsw.marke.passt_nicht_mehr', ton: 'warn' },
	nur_tageswert: { text: 'wetter.wsw.marke.nur_tageswert', ton: 'leise' }
};
const AMPEL: Record<string, MessageKey> = {
	green: 'wetter.farbe.green',
	yellow: 'wetter.farbe.yellow',
	orange: 'wetter.farbe.orange',
	red: 'wetter.farbe.red'
};
const LEGENDE: Record<string, MessageKey> = {
	zeit_ab_gelb: 'wetter.wsw.legende.zeit_ab_gelb',
	amtliche_warnung: 'wetter.wsw.legende.amtliche_warnung',
	stufe_gelb: 'wetter.wsw.legende.stufe_gelb',
	stufe_orange: 'wetter.wsw.legende.stufe_orange',
	stufe_rot: 'wetter.wsw.legende.stufe_rot',
	warnung_wind: 'wetter.wsw.legende.warnung_wind',
	warnung_starkregen: 'wetter.wsw.legende.warnung_starkregen',
	lawinenstufe: 'wetter.wsw.legende.lawinenstufe',
	warnquelle_nicht_erreichbar: 'wetter.wsw.legende.warnquelle_nicht_erreichbar'
};
/** Spalte nicht bedienbar: Telegram ruht im Kurzstil, Stundenverlauf/Ausblick bei ausgeschaltetem Block. */
const RUHT: Record<string, (l: Spaltenlage) => boolean> = {
	telegram: (l) => l.kurzstil,
	hourly: (l) => !l.stundenverlaufAn,
	outlook: (l) => !l.ausblickAn
};

/** Spalten in der Folge der Antwort; eine unbekannte Stelle (etwa eine künftige Premium-SMS) zeigt die Karte nicht. */
export function stellenAus(a: PlacementsAntwort, lage: Spaltenlage, t: Uebersetzer): EinstellStelle[] {
	const spalten = a.columns.filter((c) => SPALTE[c.stelle]);
	const eng = spalten.length > 4;
	return spalten.map((c) => {
		const s = SPALTE[c.stelle];
		const kurzstil = c.stelle === 'telegram' && lage.kurzstil;
		const kurz = s.kurz && (eng || c.stelle !== 'telegram') ? t(s.kurz) : undefined;
		return {
			id: c.stelle,
			titel: t(s.titel),
			titelKurz: kurz,
			unterzeile: kurzstil ? t('wetter.wsw.unterzeile.kurzstil') : UNTERZEILE[c.subtitle] ? t(UNTERZEILE[c.subtitle]) : undefined,
			abgesetzt: s.abgesetzt,
			schmal: s.abgesetzt,
			bedienbar: !(RUHT[c.stelle]?.(lage) ?? false),
			zellenName: (metrik: string) => t(s.zelle, { metrik })
		};
	});
}

function zelleAus(stelle: string, z: ApiZelle, t: Uebersetzer): EinstellZelle {
	const grund = z.state === 'locked' && z.reason && GRUND[z.reason] ? t(GRUND[z.reason]) : z.state === 'not_in_email' ? t('wetter.wsw.grund.nicht_in_email') : undefined;
	const marke = z.state === 'on' && z.mark && MARKE[z.mark] ? { text: t(MARKE[z.mark].text), ton: MARKE[z.mark].ton } : undefined;
	return {
		zustand: z.state,
		grund,
		// Roh/Einfach nie in der SMS (Spec Teil A Nr. 4), sonst nur, wo die Antwort zwei Formen meldet.
		format: stelle === 'sms' ? null : (z.format ?? null),
		beispiel: z.example ?? undefined,
		ampel: z.ampel && AMPEL[z.ampel] ? { farbe: z.ampel, name: t(AMPEL[z.ampel]) } : undefined,
		marke
	};
}

export function metrikenAus(a: PlacementsAntwort, t: Uebersetzer): EinstellMetrik[] {
	return a.rows.map((r) => ({
		id: r.metric_id,
		name: r.name,
		zellen: Object.fromEntries(Object.entries(r.cells).map(([stelle, z]) => [stelle, zelleAus(stelle, z, t)]))
	}));
}

/** Feste Zeile „Amtliche Warnungen“ nur, wenn die Antwort sie liefert (Warnungen eingeschaltet). */
export function festeZeileAus(a: PlacementsAntwort, t: Uebersetzer): EinstellFesteZeile | undefined {
	const w = a.fixed_rows.find((f) => f.id === 'amtliche_warnungen');
	if (!w) return undefined;
	return {
		name: t('wetter.wsw.warnungen.name'),
		hinweis: t('wetter.wsw.warnungen.hinweis'),
		grund: t('wetter.wsw.warnungen.grund'),
		stellen: Object.keys(w.position)
	};
}

/** „+N“ je Ort im SMS-Beispiel mehrerer Orte (Zahl der weggefallenen Werte, vom Renderer gesetzt). */
function plusJeOrt(text: string): number | null {
	const m = text.match(/\s\+(\d+)(?=;|$)/);
	return m ? Number(m[1]) : null;
}

export interface SmsZeile {
	text: string;
	zeichen: string;
	hinweis: string | null;
}

/** SMS-Beispiel unter der Tabelle; Hinweissatz für mehrere Orte bzw. für Trip und einen Ort. */
export function smsAus(a: PlacementsAntwort, t: Uebersetzer, tn: MehrzahlUebersetzer): SmsZeile | null {
	const s = a.sms_example;
	if (!s) return null;
	const k = a.rows.filter((r) => r.cells.sms?.state === 'on' && r.cells.sms?.mark === 'passt_nicht_mehr').length;
	let hinweis: string | null = null;
	if (k > 0) {
		const orte = a.location_count ?? 0;
		const plus = plusJeOrt(s.text);
		const teile =
			orte > 1
				? [tn('wetter.wsw.sms_orte_passt_nicht', k, { orte }), ...(plus !== null ? [t('wetter.wsw.sms.plus_je_ort', { plus })] : [])]
				: [tn('wetter.wsw.sms_passt_nicht', k)];
		hinweis = [...teile, t('wetter.wsw.sms.hochziehen')].join(' ');
	}
	return { text: s.text, zeichen: t('wetter.wsw.sms.zeichen', { n: s.length, max: s.max_length }), hinweis };
}

export interface LegendenEintrag {
	token: string;
	text: string;
}

/** „Kürzel erklärt“: Kürzel der Metriken mit SMS-Haken (Bedeutung aus der Antwort), dann die festen Einträge. */
export function legendeAus(a: PlacementsAntwort, t: Uebersetzer): LegendenEintrag[] {
	const smsAn = new Set(a.rows.filter((r) => r.cells.sms?.state === 'on').map((r) => r.metric_id));
	const metriken = a.legend.metrics.filter((m) => smsAn.has(m.metric_id)).map((m) => ({ token: m.kuerzel, text: m.meaning ?? '' }));
	const fest = a.legend.fixed.filter((f) => LEGENDE[f.key]).map((f) => ({ token: f.token, text: t(LEGENDE[f.key]) }));
	// Dasselbe Kürzel kann für zwei Zeilen kommen (Eltern- und abgeleitete Größe): jeder Eintrag nur einmal.
	const gesehen = new Set<string>();
	return [...metriken, ...fest].filter((e) => {
		const k = `${e.token}\u0000${e.text}`;
		if (gesehen.has(k)) return false;
		gesehen.add(k);
		return true;
	});
}
