// Issue #3031 (Inhalt je Kanal A1): Zeilenmodell der Karte „Inhalt je Kanal und Fläche“.
// Spec: docs/specs/modules/feat_3031_inhalt_je_kanal_listen.md, Implementation Details 1–7.
//
// Die Karte kennt nur `KanalZeile[]` je Kanal. Trip und Ortsvergleich lesen und schreiben
// dieselbe Struktur `display_config.channel_layouts` ({kanal: [{metric_id, enabled,
// use_friendly_format}]}); der Vergleich faellt ohne `channel_layouts` auf
// `channel_active_metrics` zurueck (#3039). Alle Operationen sind rein (Eingabe unveraendert).
// Kein Browser-/SvelteKit-Import, lauffaehig unter node --experimental-strip-types.

export type Kontext = 'route' | 'vergleich';
/** Kanaele mit eigener Liste. */
export type ListenKanal = 'email' | 'telegram' | 'sms';
/** Segment der Karte; Premium-SMS folgt bis S9 der SMS-Liste (ADR-0049). */
export type Kanal = ListenKanal | 'premium_sms';
export type Format = 'roh' | 'einfach';

export interface KanalZeile {
	id: string;
	enabled: boolean;
	format: Format;
}

export type KanalListen = Record<ListenKanal, KanalZeile[]>;

/** Katalog-Eintrag (`/api/metrics`) plus angezeigter Name. */
export type KatalogEintrag = {
	id?: string;
	label: string;
	col_label?: string;
	sms_code?: string;
	format_modes?: string[];
	default_format_mode?: string;
	has_friendly_format?: boolean;
};

export type LayoutEintrag = Record<string, unknown> & {
	metric_id: string;
	enabled: boolean;
	use_friendly_format: boolean;
};

export const KANAELE: readonly Kanal[] = ['email', 'telegram', 'sms', 'premium_sms'];
export const LISTEN_KANAELE: readonly ListenKanal[] = ['email', 'telegram', 'sms'];

/** Python `_BUCKET_RANK` (models.py): primary vor secondary, Unbekanntes dahinter. */
const BUCKET_RANG: Record<string, number> = { primary: 0, secondary: 1 };
/** Python `_LEGACY_FORMAT_MODES` (loader.py): diese Modi gelten als Einfach. */
const ALT_EINFACH = new Set(['scale', 'symbol']);

type Roh = Record<string, unknown>;

function kennung(e: unknown): string | null {
	if (typeof e === 'string') return e;
	const id = (e as Roh | null)?.metric_id;
	return typeof id === 'string' ? id : null;
}

/**
 * Teilmenge der Wetter-Auswahl: abgewaehlte Metriken fallen weg, Aus-Zeilen behalten ihre
 * Position, eine neue Metrik steht eingeschaltet am Ende (Format laut `formatFuer`).
 * Ohne Liste gilt die Auswahl, alle eingeschaltet.
 */
export function normalisiereZeilen(
	zeilen: KanalZeile[] | null | undefined,
	auswahl: string[],
	formatFuer: (id: string) => Format
): KanalZeile[] {
	const erlaubt = new Set(auswahl);
	const gesehen = new Set<string>();
	const aus: KanalZeile[] = [];
	for (const z of zeilen ?? []) {
		if (!erlaubt.has(z.id) || gesehen.has(z.id)) continue;
		gesehen.add(z.id);
		aus.push({ id: z.id, enabled: z.enabled, format: z.format });
	}
	for (const id of auswahl) {
		if (gesehen.has(id)) continue;
		gesehen.add(id);
		aus.push({ id, enabled: true, format: formatFuer(id) });
	}
	return aus;
}

/** Roh/Einfach eines gespeicherten Eintrags wie Python `_normalize_legacy_mode`. */
function formatAusEintrag(e: Roh): Format {
	if (typeof e.format_mode === 'string' && ALT_EINFACH.has(e.format_mode)) return 'einfach';
	return e.use_friendly_format === false ? 'roh' : 'einfach';
}

/** Zeilen aus `channel_layouts[kanal]` in Renderer-Reihenfolge (bucket, dann order; stabil). */
function zeilenAusLayout(eintraege: unknown[]): KanalZeile[] {
	return eintraege
		.map((e, i) => ({ e: e as Roh, i }))
		.filter(({ e }) => kennung(e) !== null)
		.sort((a, b) => {
			const ra = BUCKET_RANG[String(a.e.bucket ?? 'primary')] ?? 2;
			const rb = BUCKET_RANG[String(b.e.bucket ?? 'primary')] ?? 2;
			if (ra !== rb) return ra - rb;
			const oa = typeof a.e.order === 'number' ? a.e.order : 0;
			const ob = typeof b.e.order === 'number' ? b.e.order : 0;
			return oa !== ob ? oa - ob : a.i - b.i;
		})
		.map(({ e }) => ({ id: kennung(e)!, enabled: e.enabled !== false, format: formatAusEintrag(e) }));
}

/** Rueckfall Vergleich (#3039): gelistete Kennungen an in dieser Folge, uebrige Auswahl aus. */
function zeilenAusAktiv(liste: unknown[], auswahl: string[], formatFuer: (id: string) => Format): KanalZeile[] {
	const ids = liste.map(kennung).filter((x): x is string => x !== null);
	const an = new Set(ids);
	return [
		...ids.map((id) => ({ id, enabled: true, format: formatFuer(id) })),
		...auswahl.filter((id) => !an.has(id)).map((id) => ({ id, enabled: false, format: formatFuer(id) }))
	];
}

/** Gespeicherte Zeilen eines Kanals je Kontext (Tabelle statt Kontext-Weiche). */
const GESPEICHERT: Record<Kontext, (dc: Roh, k: ListenKanal, auswahl: string[], f: (id: string) => Format) => KanalZeile[] | null> = {
	route: (dc, k) => {
		const cl = (dc.channel_layouts as Record<string, unknown> | undefined)?.[k];
		return Array.isArray(cl) ? zeilenAusLayout(cl) : null;
	},
	vergleich: (dc, k, auswahl, f) => {
		const cl = (dc.channel_layouts as Record<string, unknown> | undefined)?.[k];
		if (Array.isArray(cl)) return zeilenAusLayout(cl);
		const cam = (dc.channel_active_metrics as Record<string, unknown> | undefined)?.[k];
		return Array.isArray(cam) ? zeilenAusAktiv(cam, auswahl, f) : null;
	}
};

function nichtLeer(x: unknown): boolean {
	return !!x && typeof x === 'object' && Object.keys(x as Roh).length > 0;
}

/**
 * Fuehrt das Abo eigene Kanallisten? Dann muss jede Aenderung der Wetter-Auswahl die Listen
 * mitschreiben (neue Metrik ans Ende, AC-8). Ohne eigene Listen gilt im Renderer die
 * Wetter-Auswahl; geschrieben wird dann erst, wenn der Nutzer die Karte bedient.
 */
export function hatGespeicherteListen(kontext: Kontext, abo: { display_config?: Roh | null } | null | undefined): boolean {
	const dc = (abo?.display_config ?? {}) as Roh;
	return nichtLeer(dc.channel_layouts) || (AKTIV_RUECKFALL[kontext] && nichtLeer(dc.channel_active_metrics));
}

/** Nur der Vergleich kennt das Uebergangsfeld `channel_active_metrics` (#3039). */
const AKTIV_RUECKFALL: Record<Kontext, boolean> = { route: false, vergleich: true };

/** Die drei Kanallisten aus dem gespeicherten Abo (Trip bzw. Vergleich), normalisiert. */
export function listenAusAbo(
	kontext: Kontext,
	abo: { display_config?: Roh | null } | null | undefined,
	auswahl: string[],
	formatFuer: (id: string) => Format
): KanalListen {
	const dc = (abo?.display_config ?? {}) as Roh;
	const aus = {} as KanalListen;
	for (const k of LISTEN_KANAELE) {
		aus[k] = normalisiereZeilen(GESPEICHERT[kontext](dc, k, auswahl, formatFuer), auswahl, formatFuer);
	}
	return aus;
}

/**
 * Voller `channel_layouts`-Stand aller drei Listen (Go ersetzt den Schluessel als Ganzes).
 * Bestandsfelder eines Eintrags (horizons, sms_threshold …) bleiben erhalten; Reihenfolge =
 * Listenreihenfolge (`bucket` primary, `order` = Listenindex), kein `format_mode`.
 */
export function channelLayoutsAusListen(
	listen: KanalListen,
	bestand?: Record<string, unknown> | null
): Record<ListenKanal, LayoutEintrag[]> {
	const aus = {} as Record<ListenKanal, LayoutEintrag[]>;
	for (const k of LISTEN_KANAELE) {
		const alt = Array.isArray(bestand?.[k]) ? (bestand![k] as unknown[]) : [];
		const nachId = new Map<string, Roh>();
		for (const e of alt) {
			const id = kennung(e);
			if (id !== null && typeof e === 'object' && !nachId.has(id)) nachId.set(id, e as Roh);
		}
		aus[k] = (listen[k] ?? []).map((z, i) => {
			const basis: Roh = { ...(nachId.get(z.id) ?? {}) };
			delete basis.format_mode;
			return { ...basis, metric_id: z.id, enabled: z.enabled, use_friendly_format: z.format === 'einfach', bucket: 'primary', order: i };
		});
	}
	return aus;
}

/** Uebergangsfeld des Vergleichs: nur eingeschaltete Kennungen in Listenreihenfolge. */
export type AktivEintrag = { metric_id: string; aggregation?: string } | string;
const eKey = (e: AktivEintrag) => (typeof e === 'string' ? e : `${e.metric_id}|${e.aggregation ?? ''}`);

/** #3031 F001: Vergleichs-`channel_active_metrics` im BISHERIGEN Format `{metric_id, aggregation}`
 *  (der Python-Leser loest nackte Kennungen zu [] auf, bis #3039): je eingeschalteter Zeile die
 *  Eintraege der Grundauswahl `aktiv`; fuehrte der Kanal schon gueltige Eintraege, bleiben diese. */
export function channelActiveMetricsFuerVergleich(listen: KanalListen, aktiv: AktivEintrag[], bestand: unknown, idVon: (e: AktivEintrag) => string): Record<ListenKanal, AktivEintrag[]> {
	const erlaubt = new Set(aktiv.map(eKey));
	const aus = {} as Record<ListenKanal, AktivEintrag[]>;
	for (const k of LISTEN_KANAELE) {
		const roh = (bestand as Record<string, unknown> | null | undefined)?.[k];
		const alt = (Array.isArray(roh) ? (roh as AktivEintrag[]) : []).filter((e) => erlaubt.has(eKey(e)));
		aus[k] = (listen[k] ?? []).filter((z) => z.enabled).flatMap((z) => {
			const eigen = alt.filter((e) => idVon(e) === z.id);
			return (eigen.length ? eigen : aktiv.filter((e) => idVon(e) === z.id)).map((e) => (typeof e === 'string' ? e : { metric_id: e.metric_id, aggregation: e.aggregation }));
		});
	}
	return aus;
}

/** Liste eines Segments: Premium-SMS zeigt die SMS-Liste (ADR-0049, bis S9). */
export function zeilenFuerKanal(listen: KanalListen, kanal: Kanal): KanalZeile[] {
	return listen[kanal === 'premium_sms' ? 'sms' : kanal];
}

export function istSchreibgeschuetzt(kanal: Kanal): boolean {
	return kanal === 'premium_sms';
}

/** Amtliche Warnungen: E-Mail/Telegram ganz oben, SMS/Premium-SMS am Ende. */
export function warnungsPosition(kanal: Kanal): 'oben' | 'unten' {
	return kanal === 'email' || kanal === 'telegram' ? 'oben' : 'unten';
}

/** „Temperatur (Temp | T)“; leeres Kuerzel bzw. leerer Spaltenname ⇒ „–“. */
export function zeilenName(eintrag: KatalogEintrag): string {
	const spalte = eintrag.col_label?.trim() || '–';
	const kuerzel = eintrag.sms_code?.trim() || '–';
	return `${eintrag.label} (${spalte} | ${kuerzel})`;
}

/** Roh/Einfach-Wahl, wenn der Katalog mehr als einen Format-Modus fuehrt. */
export function hatFormatWahl(eintrag: KatalogEintrag | null | undefined): boolean {
	return (eintrag?.format_modes ?? []).length > 1 || eintrag?.has_friendly_format === true;
}

/** Standard-Darstellung einer neuen Zeile laut Katalog: `default_format_mode` ≠ raw ⇒ Einfach. */
export function formatAusKatalog(eintrag: KatalogEintrag | null | undefined): Format {
	const m = eintrag?.default_format_mode;
	return m && m !== 'raw' ? 'einfach' : 'roh';
}

function mitKanal(listen: KanalListen, kanal: ListenKanal, zeilen: KanalZeile[]): KanalListen {
	return { ...listen, [kanal]: zeilen };
}

/** Neue Reihenfolge eines Kanals (unbekannte Kennungen ignoriert, fehlende hinten). */
export function mitReihenfolge(listen: KanalListen, kanal: ListenKanal, ids: string[]): KanalListen {
	const alt = listen[kanal];
	const nachId = new Map(alt.map((z) => [z.id, z]));
	const neu = ids.flatMap((id) => (nachId.has(id) ? [{ ...nachId.get(id)! }] : []));
	const drin = new Set(neu.map((z) => z.id));
	return mitKanal(listen, kanal, [...neu, ...alt.filter((z) => !drin.has(z.id)).map((z) => ({ ...z }))]);
}

export function mitSchalter(listen: KanalListen, kanal: ListenKanal, id: string, an: boolean): KanalListen {
	return mitKanal(listen, kanal, listen[kanal].map((z) => (z.id === id ? { ...z, enabled: an } : { ...z })));
}

export function mitFormat(listen: KanalListen, kanal: ListenKanal, id: string, format: Format): KanalListen {
	return mitKanal(listen, kanal, listen[kanal].map((z) => (z.id === id ? { ...z, format } : { ...z })));
}
