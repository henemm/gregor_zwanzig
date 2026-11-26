// Issue #3122 B3b — Karte „Was steht wo“: Aufbau des gespeicherten `placements`-Objekts aus den Ereignissen der
// Karte und der Grundauswahl, dazu die Sofortanzeige bis zum frischen GET.
// Spec docs/specs/modules/feat_3122_was_steht_wo.md Teil A Nr. 1 und Teil B Nr. 13; ADR-0124.
//
// Regeln des Speicherformats: Listenposition = Reihenfolge aller Stellen; `places.<stelle>` fehlt = angehakt,
// `false` = abgewählt (ein Wiederhaken entfernt das `false`, schreibt nie ein `true` dazu); `formats` nur für
// email, telegram, hourly, outlook. Jede Funktion arbeitet auf einer Kopie und lässt unbekannte Felder des
// gespeicherten Stands stehen (Read-Modify-Write, ADR-0101). Der PUT sendet immer den vollständigen Stand.
// Kein Browser-/SvelteKit-Import, lauffähig unter node --experimental-strip-types.

import { klon } from './klon.ts';

export type Stelle = 'email' | 'telegram' | 'sms' | 'hourly' | 'outlook';
export type Form = 'raw' | 'simplified';
export type ZellenZustandApi = 'on' | 'off' | 'locked' | 'not_in_email';
export const FORMAT_STELLEN: readonly string[] = ['email', 'telegram', 'hourly', 'outlook'];
/** Stellen, die nur gelten, wenn die Metrik auch in der E-Mail steht (ADR-0124 Nr. 4). */
const HAENGT_AN_EMAIL: readonly string[] = ['hourly', 'outlook'];

export interface PlacementsZeile {
	metric_id: string;
	places?: Record<string, unknown>;
	formats?: Record<string, unknown>;
	[feld: string]: unknown;
}
export interface Placements {
	version: number;
	rows: PlacementsZeile[];
	outlook_reports?: string[];
	[feld: string]: unknown;
}

/** Antwort von GET /api/briefings/{id}/placements (docs/reference/api_contract.md, #3122 B2). */
export interface ApiZelle {
	state: ZellenZustandApi;
	format: Form | null;
	reason: string | null;
	example: string | null;
	ampel: 'green' | 'yellow' | 'orange' | 'red' | null;
	mark: 'passt_nicht_mehr' | 'nur_tageswert' | null;
}
export interface ApiZeile {
	metric_id: string;
	name: string;
	position: number;
	parent: string | null;
	cells: Record<string, ApiZelle>;
}
export interface PlacementsAntwort {
	kind: 'route' | 'vergleich';
	lang: string;
	stored: boolean;
	placements: Placements;
	location_count: number | null;
	columns: { stelle: string; subtitle: string; block_off: boolean; rests: string | null }[];
	fixed_rows: { id: string; position: Record<string, string> }[];
	rows: ApiZeile[];
	sms_example: { text: string; length: number; max_length: number } | null;
	outlook_reports: string[];
	blocks: Record<string, unknown>;
	legend: { metrics: { metric_id: string; kuerzel: string; meaning: string | null }[]; fixed: { token: string; key: string; meaning?: string }[] };
	example_version: number;
}

// ── placements ────────────────────────────────────────────────────────────────

function kopie(p: Placements): Placements {
	const k = klon(p ?? ({} as Placements));
	return { ...k, version: typeof k.version === 'number' ? k.version : 1, rows: Array.isArray(k.rows) ? k.rows : [] };
}

/** Jede angezeigte Metrik ohne Zeile bekommt eine (in Anzeigefolge hinten, wie der Resolver sie zeigt). */
function vervollstaendigt(p: Placements, anzeige: readonly string[]): Placements {
	const da = new Set(p.rows.map((r) => r.metric_id));
	for (const id of anzeige) {
		if (da.has(id)) continue;
		da.add(id);
		p.rows.push({ metric_id: id });
	}
	return p;
}

function zeileVon(p: Placements, metrik: string): PlacementsZeile {
	return p.rows.find((r) => r.metric_id === metrik)!;
}

/** Haken an einer Stelle setzen (`an`) oder entfernen. */
export function mitHaken(alt: Placements, anzeige: readonly string[], metrik: string, stelle: string, an: boolean): Placements {
	const p = vervollstaendigt(kopie(alt), [...anzeige, metrik]);
	const z = zeileVon(p, metrik);
	if (!an) {
		z.places = { ...(z.places ?? {}), [stelle]: false };
		return p;
	}
	if (z.places && z.places[stelle] === false) {
		const { [stelle]: _weg, ...rest } = z.places;
		if (Object.keys(rest).length) z.places = rest;
		else delete z.places;
	}
	return p;
}

/** Roh/Einfach an einer Stelle; SMS und unbekannte Stellen haben keine Wahl (unverändert). */
export function mitFormat(alt: Placements, anzeige: readonly string[], metrik: string, stelle: string, form: Form): Placements {
	if (!FORMAT_STELLEN.includes(stelle)) return kopie(alt);
	const p = vervollstaendigt(kopie(alt), [...anzeige, metrik]);
	const z = zeileVon(p, metrik);
	z.formats = { ...(z.formats ?? {}), [stelle]: form };
	return p;
}

/** Neue Reihenfolge: Zeilen in der Folge von `ids`; Zeilen außerhalb der Anzeige behalten Inhalt und stehen hinten. */
export function mitReihenfolge(alt: Placements, ids: readonly string[]): Placements {
	const p = vervollstaendigt(kopie(alt), ids);
	const proId = new Map(p.rows.map((r) => [r.metric_id, r]));
	const rest = p.rows.filter((r) => !ids.includes(r.metric_id));
	p.rows = [...ids.map((id) => proId.get(id)!), ...rest];
	return p;
}

/** 3-Tages-Ausblick: in welchem Briefing er steht (`outlook_reports`). */
export function mitAusblick(alt: Placements, berichte: { morning: boolean; evening: boolean }): Placements {
	const p = kopie(alt);
	p.outlook_reports = (['morning', 'evening'] as const).filter((b) => berichte[b]);
	return p;
}

/**
 * #3361: Kopie ohne `outlook_reports`. Im Anlege-POST steht der Ausblick nur bei eigener Wahl;
 * ohne Wert löst der Kern die Vorbelegung (ADR-0124 Nr. 6) nach der echten Zustellung auf.
 */
export function ohneAusblick(p: Placements): Placements {
	const { outlook_reports: _weg, ...rest } = p;
	return rest as Placements;
}

/** „−“ in der Grundauswahl: die Zeile der Metrik fällt weg (später wieder aufgenommen ist sie überall angehakt). */
export function ohneZeile(alt: Placements, metrik: string): Placements {
	const p = kopie(alt);
	p.rows = p.rows.filter((r) => r.metric_id !== metrik);
	return p;
}

/** „+“ in der Grundauswahl: neue Zeile hinten, überall angehakt (eine alte Zeile der Metrik fällt weg). */
export function mitZeileHinten(alt: Placements, metrik: string): Placements {
	const p = ohneZeile(alt, metrik);
	p.rows.push({ metric_id: metrik });
	return p;
}

/** Fix-Loop F2: Die Grundauswahl hat sich geändert (−, +, Vorlage). Eine Abwahl gilt nur, solange die Metrik in der
 *  Grundauswahl steht: weggefallene Metriken verlieren ihre Zeile, neu hinzugekommene stehen hinten, überall angehakt
 *  (eine Altzeile fällt weg). Metriken in beiden Auswahlen bleiben unverändert. */
export function mitGrundauswahl(alt: Placements, vorher: readonly string[], nachher: readonly string[]): Placements {
	let p = kopie(alt);
	for (const m of vorher) if (!nachher.includes(m)) p = ohneZeile(p, m);
	for (const m of nachher) if (!vorher.includes(m)) p = mitZeileHinten(p, m);
	return p;
}

// ── Sofortanzeige der Antwort (bis das frische GET kommt) ─────────────────────

function antwortKopie(a: PlacementsAntwort): PlacementsAntwort {
	return klon(a);
}

/** Haken in der Anzeige; die E-Mail-Spalte nimmt Stundenverlauf und Ausblick mit (gesperrt bleibt gesperrt). */
export function antwortMitHaken(alt: PlacementsAntwort, metrik: string, stelle: string, an: boolean): PlacementsAntwort {
	const a = antwortKopie(alt);
	const zeile = a.rows.find((r) => r.metric_id === metrik);
	const z = zeile?.cells[stelle];
	if (!zeile || !z) return a;
	z.state = an ? 'on' : 'off';
	if (!an) Object.assign(z, { example: null, mark: null, ampel: null });
	if (stelle !== 'email') return a;
	const gespeichert = a.placements?.rows?.find((r) => r.metric_id === metrik)?.places ?? {};
	for (const s of HAENGT_AN_EMAIL) {
		const abh = zeile.cells[s];
		if (!abh || abh.state === 'locked') continue;
		if (!an) Object.assign(abh, { state: 'not_in_email', example: null, mark: null, ampel: null });
		else if (abh.state === 'not_in_email') abh.state = gespeichert[s] === false ? 'off' : 'on';
	}
	return a;
}

export function antwortMitFormat(alt: PlacementsAntwort, metrik: string, stelle: string, form: Form): PlacementsAntwort {
	const a = antwortKopie(alt);
	const z = a.rows.find((r) => r.metric_id === metrik)?.cells[stelle];
	if (z && z.format !== null) Object.assign(z, { format: form, example: null, ampel: null });
	return a;
}

export function antwortMitReihenfolge(alt: PlacementsAntwort, ids: readonly string[]): PlacementsAntwort {
	const a = antwortKopie(alt);
	const proId = new Map(a.rows.map((r) => [r.metric_id, r]));
	a.rows = [...ids.flatMap((id) => (proId.has(id) ? [proId.get(id)!] : [])), ...a.rows.filter((r) => !ids.includes(r.metric_id))];
	return a;
}

export function antwortOhneZeile(alt: PlacementsAntwort, metrik: string): PlacementsAntwort {
	const a = antwortKopie(alt);
	a.rows = a.rows.filter((r) => r.metric_id !== metrik);
	return a;
}
