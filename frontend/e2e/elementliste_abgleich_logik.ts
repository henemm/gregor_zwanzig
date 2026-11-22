// Issue #2913 (Epic #2791) — Bewertungslogik des Staging-Abgleichs der Elementliste.
// Spec: docs/specs/modules/einstellungen_neu_neustart_adr_waechter_elementliste.md (AC-13, AC-14).
//
// Ohne Browser: Scope-Filter, Bericht (JSON + Markdown), Exit-Code, Optionen. Den Live-Lauf gegen
// Staging macht e2e/elementliste-abgleich.staging.spec.ts (Config playwright.elementliste.staging.config.ts).
// Grundsatz: Jedes Element der (gefilterten) Liste steht im Bericht. Was nicht geprüft werden
// konnte, heißt `nicht_pruefbar` und trägt einen Grund — nie wird still übersprungen.
//
// Fix-Loop 1 (#2913, F002/F003): Die gesamte Verdrahtung der Staging-Spec liegt hier als
// browserfreie Funktionen (Plan mit Prod-Schutz/Optionen/Scope, Route-Abfangen-Plan je Zustand,
// Bewertung je Abschnitt, Bericht schreiben, Abschluss/Exit). Die Spec ruft nur diese Funktionen;
// die CLI-Flags --strict/--scope/--sprache/--abnahme übersetzt der Starter scripts/elementliste_abgleich.ts.
//
// Ganzseiten-Abgleich (Spec feat_2913_abgleich_ganzseite): Gegenrichtung (`zusaetzlich` = live sichtbarer
// Text ohne Eintrag), Besitzer je Abweichung (elementliste_besitzer.json) und Modus `--abnahme`.
import { createHash } from 'node:crypto';
import { mkdirSync, readFileSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';
import { assertNotProdBaseURL } from './prodUrlGuard.ts';

// #2913 Scheibe (c) Fix-Loop 2: `freigegeben` = Abweichung, die eine Spec ausdrücklich erlaubt (Liste
// elementliste_freigaben.json, je Eintrag Grund + Spec-Verweis). Eigener Zähler, nie als gefunden gezählt.
// `zusaetzlich` (Ganzseiten-Abgleich): Text ohne Listeneintrag; steht in einer eigenen Liste des Berichts.
export type Status = 'gefunden' | 'abweichend' | 'nicht_pruefbar' | 'freigegeben' | 'zusaetzlich';
export type Ergebnis = { status: Exclude<Status, 'zusaetzlich'>; grund?: string; ist?: string };
/** Verantwortlicher einer Abweichung: Scheibe (#2913-c2|d|e) oder Issue (#NNNN), immer mit Grund. */
export type BesitzerVerweis = { grund: string; verweis: string };

export type ListenElement = {
	id: string;
	ctx: string;
	reiter: string;
	zustand: string;
	segment: string | null;
	abschnitt: string;
	ordnung: number;
	rolle: string;
	text_de: string;
	muster: string | null;
	i18n_key: string | null;
	text_en: string | null;
	luecke: boolean;
	/** #2968 Regel c: EN = DE-Muster (Zahlen, Einheiten, Kurz-/Protokoll-Token, Eigennamen); fehlt = false. */
	sprachneutral?: boolean;
	/** #2968 Regel f: alle EN-Kandidaten bei mehrdeutigem DE-Text; der EN-Abgleich akzeptiert jeden. */
	text_en_alternativen?: string[];
};

export type BerichtEintrag = {
	id: string;
	ctx: string;
	reiter: string;
	zustand: string;
	segment: string | null;
	abschnitt: string;
	ordnung: number;
	text_de: string;
	status: Status;
	grund?: string;
	ist?: string;
	besitzer?: BesitzerVerweis;
};
/** Live sichtbarer Text, der keinem Eintrag, Konto-Text oder keiner Ausnahme entspricht. */
export type ZusaetzlichEintrag = { id: string; ctx: string; reiter: string; text: string; status: 'zusaetzlich'; besitzer?: BesitzerVerweis };
/** Gegenrichtungs-Kombination, auf der ein Hub-Anker (Kopf oder Reiterfläche) fehlte: nicht prüfbar, nie still grün. */
export type OhneHubEintrag = { ctx: string; reiter: string; grund: string };
export type Bericht = { eintraege: BerichtEintrag[]; zusaetzlich: ZusaetzlichEintrag[]; ohne_hub: OhneHubEintrag[]; zaehler: Record<Status, number> };

const OHNE_ERGEBNIS = 'kein Ergebnis: das Element wurde im Lauf nicht geprüft';

/** `--scope reiter` oder `--scope reiter/zustand`; null = alles. Unbekannter Scope ist ein Fehler. */
export function filtereScope<E extends { reiter: string; zustand: string }>(elemente: E[], scope: string | null): E[] {
	if (scope === null || scope.trim() === '') return elemente;
	const [reiter, zustand, rest] = scope.trim().split('/');
	if (rest !== undefined || !reiter) throw new Error(`Scope „${scope}“: erlaubt sind „reiter“ oder „reiter/zustand“`);
	if (!elemente.some((e) => e.reiter === reiter)) {
		const bekannt = [...new Set(elemente.map((e) => e.reiter))].join(', ');
		throw new Error(`Scope „${scope}“: Reiter „${reiter}“ unbekannt (bekannt: ${bekannt})`);
	}
	const treffer = elemente.filter((e) => e.reiter === reiter && (zustand === undefined || e.zustand === zustand));
	if (treffer.length === 0) {
		const bekannt = [...new Set(elemente.filter((e) => e.reiter === reiter).map((e) => e.zustand))].join(', ');
		throw new Error(`Scope „${scope}“: Zustand „${zustand}“ unbekannt (bekannt: ${bekannt})`);
	}
	return treffer;
}

/**
 * Bericht über ALLE übergebenen Elemente; fehlendes Ergebnis ⇒ nicht_pruefbar mit Grund. Zusätzliche Texte
 * (Gegenrichtung) stehen in einer eigenen Liste mit eigenem Zähler, nie in `eintraege`.
 */
export function baueBericht(
	elemente: ListenElement[],
	ergebnisse: Map<string, Ergebnis>,
	zusaetzlich: ZusaetzlichEintrag[] = [],
	ohneHub: OhneHubEintrag[] = []
): Bericht {
	const zaehler: Record<Status, number> = { gefunden: 0, abweichend: 0, nicht_pruefbar: 0, freigegeben: 0, zusaetzlich: zusaetzlich.length };
	const eintraege = elemente.map((e): BerichtEintrag => {
		const erg: Ergebnis = ergebnisse.get(e.id) ?? { status: 'nicht_pruefbar', grund: OHNE_ERGEBNIS };
		if ((erg.status === 'nicht_pruefbar' || erg.status === 'freigegeben') && !(erg.grund && erg.grund.trim())) {
			throw new Error(`${e.id}: ${erg.status} ohne Grund ist nicht erlaubt`);
		}
		zaehler[erg.status] += 1;
		const eintrag: BerichtEintrag = {
			id: e.id,
			ctx: e.ctx,
			reiter: e.reiter,
			zustand: e.zustand,
			segment: e.segment ?? null,
			abschnitt: e.abschnitt,
			ordnung: e.ordnung,
			text_de: e.text_de,
			status: erg.status
		};
		if (erg.grund) eintrag.grund = erg.grund;
		if (erg.ist !== undefined) eintrag.ist = erg.ist;
		return eintrag;
	});
	return { eintraege, zusaetzlich: [...zusaetzlich], ohne_hub: ohneHub.map((o) => ({ ...o })), zaehler };
}

const ohneHubAnzahl = (bericht: Bericht) => (bericht.ohne_hub ?? []).length;

export type Optionen = { strict: boolean; scope: string | null; abnahme: boolean };

/** Anzahl Abweichungen (abweichend, nicht_pruefbar, zusaetzlich) ohne Besitzer; Freigaben sind Besitzer. */
export function herrenlos(bericht: Bericht): number {
	const ohne = bericht.eintraege.filter((e) => (e.status === 'abweichend' || e.status === 'nicht_pruefbar') && !e.besitzer).length;
	return ohne + bericht.zusaetzlich.filter((z) => !z.besitzer).length;
}

/**
 * Ohne Flags immer 0. --strict (unverändert, AC-10): ≠ 0, sobald etwas abweicht oder nicht prüfbar ist
 * (freigegeben, zusaetzlich und ohne_hub zählen nicht). --abnahme: ≠ 0, sobald eine Abweichung keinen
 * Besitzer hat oder auf einer Gegenrichtungs-Kombination ein Hub-Anker fehlte (Gegenrichtung nicht prüfbar,
 * nie still grün). ohne_hub steht unabhängig davon immer im Bericht.
 */
export function exitCode(bericht: Bericht, opt: { strict: boolean; abnahme?: boolean }): number {
	if (opt.abnahme && ohneHubAnzahl(bericht) > 0) return 1;
	if (opt.strict && bericht.zaehler.abweichend + bericht.zaehler.nicht_pruefbar > 0) return 1;
	if (opt.abnahme && herrenlos(bericht) > 0) return 1;
	return 0;
}

const zelle = (s: string | null | undefined) => String(s ?? '').replace(/\|/g, '\\|').replace(/\n/g, ' ');
const besitzerZelle = (b: BesitzerVerweis | undefined) => (b ? zelle(`${b.verweis} (${b.grund})`) : '–');

export function berichtAlsMarkdown(bericht: Bericht): string {
	const z = bericht.zaehler;
	const zeilen = [
		'# Elementlisten-Abgleich (Staging)',
		'',
		`| gefunden | abweichend | nicht_pruefbar | freigegeben | zusaetzlich | gesamt |`,
		`|---|---|---|---|---|---|`,
		`| ${z.gefunden} | ${z.abweichend} | ${z.nicht_pruefbar} | ${z.freigegeben} | ${z.zusaetzlich} | ${bericht.eintraege.length} |`,
		'',
		'| id | Kontext | Reiter | Zustand | Segment | Abschnitt | Nr. | Text | Status | Grund / Ist | Besitzer |',
		'|---|---|---|---|---|---|---|---|---|---|---|'
	];
	for (const e of bericht.eintraege) {
		const hinweis = [e.grund, e.ist !== undefined ? `ist: ${e.ist}` : ''].filter(Boolean).join(' · ');
		zeilen.push(
			`| ${zelle(e.id)} | ${zelle(e.ctx)} | ${zelle(e.reiter)} | ${zelle(e.zustand)} | ${zelle(e.segment ?? '–')} | ${zelle(e.abschnitt)} | ${e.ordnung} | ${zelle(e.text_de)} | ${e.status} | ${zelle(hinweis)} | ${besitzerZelle(e.besitzer)} |`
		);
	}
	zeilen.push('', '## Zusätzlich (live sichtbar, ohne Eintrag)', '', '| id | Kontext | Reiter | Text | Besitzer |', '|---|---|---|---|---|');
	for (const x of bericht.zusaetzlich) {
		zeilen.push(`| ${zelle(x.id)} | ${zelle(x.ctx)} | ${zelle(x.reiter)} | ${zelle(x.text)} | ${besitzerZelle(x.besitzer)} |`);
	}
	if (ohneHubAnzahl(bericht) > 0) {
		zeilen.push('', `## Gegenrichtung nicht prüfbar: Hub-Marker fehlt (${ohneHubAnzahl(bericht)})`, '', '| Kontext | Reiter | Grund |', '|---|---|---|');
		for (const o of bericht.ohne_hub) zeilen.push(`| ${zelle(o.ctx)} | ${zelle(o.reiter)} | ${zelle(o.grund)} |`);
	}
	return zeilen.join('\n') + '\n';
}

const WAHR = new Set(['1', 'true', 'ja', 'yes']);

/**
 * `--strict`, `--abnahme`, `--scope X` bzw. `--scope=X`; ersatzweise ELEMENTLISTE_STRICT /
 * ELEMENTLISTE_ABNAHME / ELEMENTLISTE_SCOPE.
 */
export function leseOptionen(argv: string[], env: Record<string, string | undefined>): Optionen {
	let strict = WAHR.has(String(env.ELEMENTLISTE_STRICT ?? '').toLowerCase());
	let abnahme = WAHR.has(String(env.ELEMENTLISTE_ABNAHME ?? '').toLowerCase());
	let scope: string | null = env.ELEMENTLISTE_SCOPE && env.ELEMENTLISTE_SCOPE.trim() ? env.ELEMENTLISTE_SCOPE.trim() : null;
	for (let i = 0; i < argv.length; i++) {
		const a = argv[i];
		if (a === '--strict') strict = true;
		else if (a === '--abnahme') abnahme = true;
		else if (a === '--scope' && i + 1 < argv.length) scope = argv[++i];
		else if (a.startsWith('--scope=')) scope = a.slice('--scope='.length);
	}
	return { strict, scope, abnahme };
}

/** Text normalisieren (Leerraum, typografische Zeichen) für den Vergleich mit dem DOM. */
export function normalisiere(s: string): string {
	return s
		.replace(/[  ]/g, ' ')
		.replace(/[„“”]/g, '"')
		.replace(/[‚‘’]/g, "'")
		.replace(/\s+/g, ' ')
		.trim();
}

/** Muster (`{name}` = beliebiger Wert) als RegExp über normalisierten Text. */
export function musterAlsRegExp(muster: string): RegExp {
	const teile = normalisiere(muster).split(/\{[^}]+\}/);
	return new RegExp(teile.map((t) => t.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')).join('.+?'));
}

// ------------------------------------------------------------------ Verdrahtung (Fix-Loop 1, F002/F003)

export const STAGING_URL = 'https://staging.gregor20.henemm.com';
export type Sprache = 'de' | 'en';
export type Kombi = { ctx: string; reiter: string; zustand: string; segment: string | null };
export type Plan = {
	baseURL: string;
	optionen: Optionen;
	sprache: Sprache;
	elemente: ListenElement[];
	kombis: Array<{ k: Kombi; el: ListenElement[] }>;
};

const esc = (s: string) => s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');

/** Sprache des Abgleichs aus ELEMENTLISTE_SPRACHE (de|en); alles andere ist ein Fehler. */
export function leseSprache(env: Record<string, string | undefined>): Sprache {
	const s = (env.ELEMENTLISTE_SPRACHE ?? 'de').trim().toLowerCase();
	if (s !== 'de' && s !== 'en') throw new Error(`ELEMENTLISTE_SPRACHE „${s}“: erlaubt sind de oder en`);
	return s;
}

/**
 * Plan des Laufs, bevor eine Seite geladen wird: Prod-Schutz auf die echte Base-URL, Optionen aus der
 * Umgebung (der Starter übersetzt --strict/--scope), Scope-Filter, Gruppierung je Kombination.
 */
export function planeAbgleich(arg: { liste: ListenElement[]; env: Record<string, string | undefined>; baseURL: string | undefined }): Plan {
	const baseURL = arg.baseURL ?? STAGING_URL;
	assertNotProdBaseURL(baseURL);
	const optionen = leseOptionen([], arg.env);
	const sprache = leseSprache(arg.env);
	const elemente = filtereScope(arg.liste, optionen.scope);
	const gruppen = new Map<string, { k: Kombi; el: ListenElement[] }>();
	for (const e of elemente) {
		const k: Kombi = { ctx: e.ctx, reiter: e.reiter, zustand: e.zustand, segment: e.segment ?? null };
		const key = [k.ctx, k.reiter, k.zustand, k.segment ?? '-'].join('|');
		const g = gruppen.get(key) ?? { k, el: [] };
		g.el.push(e);
		gruppen.set(key, g);
	}
	return { baseURL, optionen, sprache, elemente, kombis: [...gruppen.values()] };
}

/** Datenabrufe des Browsers zu Metriken/Vorlagen/Wetter — Ziel des Route-Abfangens für lädt/Ladefehler. */
export const DATEN_ABRUF = /\/api\/(?:compare\/)?(?:metrics|presets|metric-presets|weather|trips\/[^/]+\/(?:weather|metrics))/;

/**
 * Lesende Abrufe des Kontos: GET /api/auth/profile (Komponenten im Browser) und die Seitendaten
 * `…/__data.json` (bei Navigation im Browser liefert SvelteKit darüber das serverseitig geladene
 * `profile` des Hubs). Ziel des Route-Abfangens für „Konto mit Lücken“.
 */
export const KONTO_ABRUF = /\/api\/auth\/profile(?:\?|$)|\/__data\.json(?:\?|$)/;

/**
 * Profil im Zustand „Konto mit Lücken“ wie im Mockup: Telegram-Chat fehlt, SMS-Nummer eingetragen,
 * aber nicht bestätigt, Premium-SMS-Rückadresse verfallen. E-Mail bleibt, wie sie ist. Nur die Antwort
 * an den Browser wird ersetzt; das Konto selbst ändert sich nicht.
 */
export function lueckenProfil(p: Record<string, unknown> | null): Record<string, unknown> {
	const basis = p ?? {};
	return {
		...basis,
		telegram_chat_id: '',
		sms_to: typeof basis.sms_to === 'string' && basis.sms_to ? basis.sms_to : '+49 171 0000000',
		sms_allowed: true,
		sms_verified: false,
		pending_sms_to: '',
		premium_sms_allowed: true,
		premium_sms_reply_to: typeof basis.premium_sms_reply_to === 'string' && basis.premium_sms_reply_to ? basis.premium_sms_reply_to : 'e2e-gz@inreach.garmin.com',
		premium_sms_reply_at: '2026-01-01T08:00:00Z',
		premium_sms_reply_state: 'stale'
	};
}

const istIndex = (x: unknown): x is number => typeof x === 'number' && Number.isInteger(x) && x >= 0;
const istObjekt = (x: unknown): x is Record<string, unknown> => typeof x === 'object' && x !== null && !Array.isArray(x);

/**
 * `profile` in einem devalue-flachen Datenfeld (Format von SvelteKits `__data.json`: Index 0 ist die Wurzel,
 * Objekte bilden Schlüssel auf Indizes ab) auf das Lücken-Profil umlenken. Bestehende Einträge werden nie
 * verändert (devalue teilt gleiche Werte über Indizes); neue Werte und das neue Profil-Objekt werden angehängt.
 */
export function lueckenImFlachenFeld(feld: unknown[]): boolean {
	const wurzel = feld[0];
	if (!istObjekt(wurzel) || !('profile' in wurzel)) return false;
	const altIdx = wurzel.profile;
	const altObj = istIndex(altIdx) && istObjekt(feld[altIdx]) ? (feld[altIdx] as Record<string, unknown>) : {};
	const altWerte: Record<string, unknown> = {};
	for (const [k, i] of Object.entries(altObj)) {
		if (istIndex(i) && (typeof feld[i] !== 'object' || feld[i] === null)) altWerte[k] = feld[i];
	}
	const neu = lueckenProfil(altWerte);
	const abbildung: Record<string, unknown> = { ...altObj };
	for (const [k, v] of Object.entries(neu)) {
		if (k in altWerte && altWerte[k] === v) continue;
		abbildung[k] = feld.length;
		feld.push(v);
	}
	wurzel.profile = feld.length;
	feld.push(abbildung);
	return true;
}

/** Ersetzt in den SvelteKit-Seitendaten (`__data.json`, erste Zeile; Folgezeilen sind Nachlieferungen) jedes `profile`. */
export function lueckenSeitenDaten(text: string): { text: string; geaendert: boolean } {
	const [kopf, ...rest] = text.split('\n');
	let wurzel: { type?: string; nodes?: Array<{ type?: string; data?: unknown } | null> };
	try {
		wurzel = JSON.parse(kopf);
	} catch {
		return { text, geaendert: false };
	}
	if (wurzel?.type !== 'data' || !Array.isArray(wurzel.nodes)) return { text, geaendert: false };
	let geaendert = false;
	for (const knoten of wurzel.nodes) {
		if (!knoten || knoten.type !== 'data' || !Array.isArray(knoten.data)) continue;
		if (lueckenImFlachenFeld(knoten.data)) geaendert = true;
	}
	return { text: geaendert ? [JSON.stringify(wurzel), ...rest].join('\n') : text, geaendert };
}

/** Antwort eines abgefangenen Konto-Abrufs in den Lücken-Zustand umschreiben (Profil-JSON bzw. Seitendaten). */
export function ersetzeKontoAntwort(url: string, text: string): { text: string; geaendert: boolean } {
	const pfad = url.replace(/^[a-z]+:\/\/[^/]+/i, '');
	if (/\/__data\.json(?:\?|$)/.test(pfad)) return lueckenSeitenDaten(text);
	if (/^\/api\/auth\/profile(?:\?|$)/.test(pfad)) {
		try {
			return { text: JSON.stringify(lueckenProfil(JSON.parse(text))), geaendert: true };
		} catch {
			return { text, geaendert: false };
		}
	}
	return { text, geaendert: false };
}

export type RoutenPlan =
	| { art: 'keiner' }
	| { art: 'haengen'; muster: RegExp }
	| { art: 'fehler'; muster: RegExp; status: number }
	| {
			art: 'konto_luecken';
			muster: RegExp;
			/** Nur diese Methode wird umgeschrieben; alles andere (Schreib-Requests) läuft unverändert durch. */
			methode: 'GET';
			ersetze: (url: string, text: string) => { text: string; geaendert: boolean };
			/** Die Hub-Daten kommen nur bei Navigation im Browser über __data.json; der erste Aufruf wäre serverseitig. */
			navigation: 'browser';
	  }
	| { art: 'nicht_herstellbar'; grund: string };

/** Wie der Zustand auf Staging hergestellt wird. Nichts wird still übersprungen: sonst nicht_herstellbar mit Grund. */
export function routenPlan(zustand: string): RoutenPlan {
	if (zustand === 'normal') return { art: 'keiner' };
	if (zustand === 'laedt') return { art: 'haengen', muster: DATEN_ABRUF };
	if (zustand === 'fehler') return { art: 'fehler', muster: DATEN_ABRUF, status: 500 };
	if (zustand === 'luecken') return { art: 'konto_luecken', muster: KONTO_ABRUF, methode: 'GET', ersetze: ersetzeKontoAntwort, navigation: 'browser' };
	return { art: 'nicht_herstellbar', grund: `unbekannter Zustand „${zustand}“` };
}

/**
 * Nach dem Seitenaufruf: ist der Zustand wirklich hergestellt? Für „Konto mit Lücken“ muss mindestens
 * eine Konto-Antwort umgeschrieben worden sein, sonst nicht_pruefbar mit konkretem Grund (nie still).
 */
export function herstellungsGrund(plan: RoutenPlan, umgeschrieben: number): string | null {
	if (plan.art === 'konto_luecken' && umgeschrieben === 0) {
		return 'Konto mit Lücken nicht hergestellt: kein Konto-Abruf (GET /api/auth/profile bzw. __data.json mit profile) beim Seitenaufruf abgefangen';
	}
	return null;
}

/** Seitenpfad je Kontext und Reiter. */
export function seitenPfad(ctx: string, id: string, reiter: string): string {
	const basis = ctx === 'trip' ? '/trips/' : '/compare/';
	return `${basis}${encodeURIComponent(id)}?tab=${encodeURIComponent(reiter)}`;
}

/** Abschnitte, die nur nach einer Bedienung erscheinen (Script-Zustände im Mockup). */
export const SCRIPT_ABSCHNITT = /^(grenzen-|vorlage-auswahl|vorlage-bestaetigung|vorlage-speichern|vorlage-abweichung|test-menue|kebab-)/;

/**
 * #3251: Abschnitt-Haken (data-abschnitt) in der App, wenn er vom Namen in der Elementliste abweicht. Der
 * Abweichungszustand der Vorlagenkarte ist in der App dieselbe Karte (data-abschnitt="vorlage"), nur auf
 * dem Prüf-Datensatz mit Abweichung (datensatzFuerAbschnitt).
 */
export function abschnittHaken(abschnitt: string): string {
	return abschnitt === 'vorlage-abweichung' ? 'vorlage' : abschnitt;
}

/**
 * #2966 (AC-6): Bedienplan je Abschnitt. Ein Schritt klickt ein testid, liest den Bereich oder schließt
 * (testid oder Taste). Nichts wird übernommen oder gespeichert: Grenzen nur öffnen und über „Fertig“
 * schließen, Wechsel-Frage nur abbrechen, Speichern-Dialog nur leer absenden (Pflichtfehler entsteht vor
 * jedem Netzaufruf) und per Escape schließen.
 */
export type BedienSchritt = { aktion: 'klick' | 'lesen' | 'schliessen'; testid?: string; taste?: string };
/** Lage des Prüf-Datensatzes: Metriken mit Grenzen-Knopf im Briefing, Systemvorlagen, aktive Vorlage. */
export type BedienLage = { ctx: string; briefing: string[]; vorlagen: string[]; aktiveVorlage: string };
export type BedienPlan = { art: 'ohne_bedienung' } | { art: 'plan'; schritte: BedienSchritt[] } | { art: 'nicht_herstellbar'; grund: string };

const LESEN: BedienSchritt = { aktion: 'lesen' };
const VORLAGE_PICKER = 'wetter-vorlage-picker';
const ALS_EIGENE = 'wetter-vorlage-als-eigene';
const SPEICHERN_ABBRECHEN = 'save-preset-cancel';

/** Reine Funktion: wie der Abschnitt hergestellt wird. Script-Abschnitt ohne Plan ⇒ nie still, immer mit Grund. */
export function bedienPlan(abschnitt: string, lage: BedienLage): BedienPlan {
	if (!SCRIPT_ABSCHNITT.test(abschnitt)) return { art: 'ohne_bedienung' };
	if (abschnitt.startsWith('grenzen-')) {
		const id = abschnitt.slice('grenzen-'.length);
		if (!id) return { art: 'nicht_herstellbar', grund: `Script-Zustand „${abschnitt}“: keine Metrik im Abschnittsnamen` };
		if (!lage.briefing.includes(id)) return { art: 'nicht_herstellbar', grund: `Metrik „${id}“ nicht im Briefing des Prüf-Datensatzes (kein Knopf „Grenzen ändern“)` };
		const knopf = `wetter-grenzen-aendern-${id}`;
		return { art: 'plan', schritte: [{ aktion: 'klick', testid: knopf }, LESEN, { aktion: 'schliessen', testid: knopf }] };
	}
	// #3251: kein Klick nötig — der Prüf-Datensatz mit Abweichung zeigt Abweichungszahl und Zurücksetzen-Zeile.
	if (abschnitt === 'vorlage-abweichung') return { art: 'plan', schritte: [LESEN] };
	if (abschnitt === 'vorlage-auswahl') {
		return { art: 'plan', schritte: [{ aktion: 'klick', testid: VORLAGE_PICKER }, LESEN, { aktion: 'schliessen', testid: VORLAGE_PICKER }] };
	}
	if (abschnitt === 'vorlage-bestaetigung') {
		// #3192 (AC-2): Wechselziel der Mockup-Lage je Kontext; „erste andere“ nur ohne Mockup-Ziel.
		const z = wechselZiel(lage.ctx, lage.vorlagen, lage.aktiveVorlage);
		if (z.art === 'nicht_herstellbar') return { art: 'nicht_herstellbar', grund: `Script-Zustand „${abschnitt}“: ${z.grund}` };
		const andere = z.id;
		return {
			art: 'plan',
			schritte: [
				{ aktion: 'klick', testid: VORLAGE_PICKER },
				{ aktion: 'klick', testid: `wetter-vorlage-option-${andere}` },
				LESEN,
				{ aktion: 'schliessen', testid: 'wetter-vorlage-wechsel-abbrechen' }
			]
		};
	}
	// #3190: die Speichern-Karte ist inline; Escape schließt sie nur bei Fokus in der Karte. Die Taste-Bedienung
	// löst den Fokus vorher (seitenOps), darum schließt der Plan über „Abbrechen“ (save-preset-cancel).
	if (abschnitt === 'vorlage-speichern') {
		return { art: 'plan', schritte: [{ aktion: 'klick', testid: ALS_EIGENE }, LESEN, { aktion: 'schliessen', testid: SPEICHERN_ABBRECHEN }] };
	}
	if (abschnitt === 'vorlage-speichern-fehler') {
		return {
			art: 'plan',
			schritte: [{ aktion: 'klick', testid: ALS_EIGENE }, { aktion: 'klick', testid: 'save-preset-submit' }, LESEN, { aktion: 'schliessen', testid: SPEICHERN_ABBRECHEN }]
		};
	}
	return { art: 'nicht_herstellbar', grund: `Script-Zustand „${abschnitt}“: kein Bedienplan im Abgleich hinterlegt` };
}

/**
 * #3192 (AC-2): Datenlage des Mockups je Kontext — aktive Systemvorlage, Wechselziel der Bestätigung,
 * beim Orts-Vergleich die Zahl der Orte („für diese Orte“).
 */
export const MOCKUP_LAGE = {
	trip: { aktiv: 'alpen-trekking', ziel: 'wandern' },
	orte: { aktiv: 'allgemein', ziel: 'alpen-trekking', orte: 3 }
};

export type WechselZiel = { art: 'ziel'; id: string } | { art: 'nicht_herstellbar'; grund: string };
/** #3192 (AC-2): Wechselziel der Vorlagen-Bestätigung; fehlt das Mockup-Ziel, nie still ersetzen. */
export function wechselZiel(ctx: string, vorlagen: string[], aktiv: string): WechselZiel {
	const mockup = (MOCKUP_LAGE as Record<string, { ziel: string } | undefined>)[ctx];
	if (mockup) {
		if (vorlagen.includes(mockup.ziel)) return { art: 'ziel', id: mockup.ziel };
		return { art: 'nicht_herstellbar', grund: `Wechselziel „${mockup.ziel}“ der Mockup-Lage (${ctx}) fehlt in der Vorlagenliste` };
	}
	const andere = vorlagen.find((v) => v !== aktiv);
	if (!andere) return { art: 'nicht_herstellbar', grund: `keine andere Systemvorlage als „${aktiv}“ für die Wechsel-Frage` };
	return { art: 'ziel', id: andere };
}

/**
 * #3192 (AC-1): Prüf-Datensatz je Abschnitt — Grenzen-Dialoge und (#3251) der Abweichungszustand der
 * Vorlagenkarte mit Abweichung, alles andere ohne.
 */
export function datensatzFuerAbschnitt(abschnitt: string): 'mit_abweichung' | 'ohne_abweichung' {
	return abschnitt.startsWith('grenzen-') || abschnitt === 'vorlage-abweichung' ? 'mit_abweichung' : 'ohne_abweichung';
}

type AmpelSeite = { red: number; orange: number; yellow: number };
export type AmpelMetrik = { lower?: AmpelSeite; upper?: AmpelSeite };
/**
 * #3192 (AC-1): gültiger Grenzen-Override je Metrik gemäß `allowed_sides` (lower aufsteigend rot<orange<gelb,
 * upper aufsteigend gelb<orange<rot, lower unter upper); Gewitter (`level`) über `thunder`.
 */
export function wetterOverrides(
	metriken: string[],
	eig: Record<string, { allowed_sides: string | null } | undefined>
): { metrics: Record<string, AmpelMetrik>; thunder?: { mittel: string; hoch: string } } {
	const metrics: Record<string, AmpelMetrik> = {};
	let thunder: { mittel: string; hoch: string } | undefined;
	for (const id of metriken) {
		const seiten = eig[id]?.allowed_sides ?? null;
		if (seiten === 'level') {
			thunder = { mittel: 'yellow', hoch: 'orange' };
			continue;
		}
		const e: AmpelMetrik = {};
		if (seiten === 'both' || seiten === 'lower') e.lower = { red: 1, orange: 2, yellow: 3 };
		if (seiten === 'both' || seiten === 'upper') e.upper = { yellow: 10, orange: 20, red: 30 };
		if (e.lower || e.upper) metrics[id] = e;
	}
	return thunder ? { metrics, thunder } : { metrics };
}

/**
 * #3192 (AC-4): Text eines Eingabefelds (INPUT und TEXTAREA). Selbstenthalten (keine Verweise auf den
 * Modul-Scope): die Staging-Spec gibt genau diese Funktion per `eingabeText.toString()` in den Browser,
 * `sichtbareTexte` ruft sie dort auf (Fix-Loop F001: die wirkende Regel IST die getestete).
 */
export function eingabeText(el: { tag: string; ariaLabel: string | null; placeholder: string | null; value: string }): string {
	if (el.tag !== 'INPUT' && el.tag !== 'TEXTAREA') return '';
	return el.ariaLabel || el.placeholder || el.value;
}

/** #3203: Knoten, wie ihn `sichtbareTextBloecke` liest (Teilmenge des DOM-Node). */
export type AbgleichKnoten = {
	nodeType: number;
	nodeValue: string | null;
	tagName?: string;
	childNodes: ArrayLike<AbgleichKnoten>;
	hasAttribute?(name: string): boolean;
	getAttribute?(name: string): string | null;
	value?: unknown;
};

/**
 * #3203 (AC-1 bis AC-3), Fix-Loop 1: sichtbare Texte unter `wurzel` in Dokumentreihenfolge, je Element wie
 * bisher (eigene Textknoten), aber Sichtbarkeit statt Überspringen von `aria-hidden`:
 * - Ein Element samt Teilbaum zählt nicht bei `display: none`, Attribut `hidden` oder als SCRIPT/STYLE/svg;
 *   Text unter `visibility: hidden` zählt nicht.
 * - Element mit eigenem (nicht leeren) Textknoten: EIN Block aus seinem eigenen Text und dem Text seiner
 *   `aria-hidden="true"`-Kinder (z. B. Trennpunkt „·“ vor „grün: …“), in Dokumentreihenfolge. Andere
 *   Kind-Elemente (Zähler, Badges, Hervorhebungen) bleiben eigene Texte wie bisher, nie verklebt.
 * - Text, der nur unter `aria-hidden` steht und weder Buchstaben noch Ziffern hat („–“, „－“, „:“, „✓“), ist
 *   Dekoration und zählt nicht als eigener Text; Skala-Zahlen und Stufenwörter zählen.
 * - Mit `eingabe` (Staging-Abgleich): je Element vorher der Eingabefeld-Text (`eingabeText`) bzw. das aria-label
 *   von Knöpfen und role=switch/group/textbox, wie bisher (unter `aria-hidden` wie bisher nicht); ohne `eingabe`
 *   nur die Textblöcke.
 * Selbstenthalten (keine Modul-Verweise): die Staging-Spec gibt die Funktion per `toString()` in den Browser.
 */
export function sichtbareTextBloecke(
	wurzel: AbgleichKnoten,
	stil: (el: AbgleichKnoten) => { display: string; visibility: string },
	eingabe?: (e: { tag: string; ariaLabel: string | null; placeholder: string | null; value: string }) => string
): string[] {
	const norm = (s: string | null | undefined): string => String(s ?? '').replace(/\s+/g, ' ').trim();
	const attr = (el: AbgleichKnoten, name: string): string | null =>
		typeof el.getAttribute === 'function' ? el.getAttribute(name) : typeof el.hasAttribute === 'function' && el.hasAttribute(name) ? '' : null;
	const ausgeschlossen = (el: AbgleichKnoten): boolean => {
		const tag = String(el.tagName ?? '').toLowerCase();
		return tag === 'script' || tag === 'style' || tag === 'svg' || attr(el, 'hidden') !== null || stil(el).display === 'none';
	};
	const ariaVerborgen = (el: AbgleichKnoten): boolean => el.nodeType === 1 && attr(el, 'aria-hidden') === 'true';
	const zeichen = /[\p{L}\p{N}]/u;
	const ganzerText = (k: AbgleichKnoten): string => {
		if (k.nodeType === 3) return k.nodeValue ?? '';
		if (k.nodeType !== 1 || ausgeschlossen(k) || stil(k).visibility === 'hidden') return '';
		let t = '';
		for (const kind of Array.from(k.childNodes)) t += ganzerText(kind);
		return t;
	};
	const MIT_LABEL = ['switch', 'group', 'textbox'];
	const texte: string[] = [];
	const lauf = (el: AbgleichKnoten, verborgen: boolean, unsichtbar: boolean): void => {
		if (el.nodeType !== 1 || ausgeschlossen(el)) return;
		const ohneSicht = unsichtbar || stil(el).visibility === 'hidden';
		const aria = verborgen || ariaVerborgen(el);
		const kinder = Array.from(el.childNodes);
		if (eingabe && !aria) {
			const wert = el.value;
			const t = norm(eingabe({ tag: String(el.tagName ?? ''), ariaLabel: attr(el, 'aria-label'), placeholder: attr(el, 'placeholder'), value: typeof wert === 'string' ? wert : '' }));
			if (t) {
				texte.push(t);
				for (const kind of kinder) lauf(kind, aria, ohneSicht);
				return;
			}
			const label = attr(el, 'aria-label');
			if (label && (el.tagName === 'BUTTON' || MIT_LABEL.includes(attr(el, 'role') ?? ''))) texte.push(norm(label));
		}
		const eigen = kinder.some((k) => k.nodeType === 3 && norm(k.nodeValue) !== '');
		const verbunden = new Set<AbgleichKnoten>();
		if (eigen && !ohneSicht) {
			let block = '';
			for (const k of kinder) {
				if (k.nodeType === 3) block += k.nodeValue ?? '';
				else if (!aria && ariaVerborgen(k)) {
					block += ganzerText(k);
					verbunden.add(k);
				}
			}
			const b = norm(block);
			if (b && (!aria || zeichen.test(b))) texte.push(b);
		}
		for (const kind of kinder) if (!verbunden.has(kind)) lauf(kind, aria, ohneSicht);
	};
	lauf(wurzel, false, false);
	return texte;
}

/** #3192 (AC-1), Fix-Loop F002: je Kontext zwei Wetter-Prüf-Datensätze. */
export type WetterDatensatz = 'mit_abweichung' | 'ohne_abweichung';
export const WETTER_DATENSAETZE: WetterDatensatz[] = ['mit_abweichung', 'ohne_abweichung'];
export type WetterIds = Record<string, Partial<Record<WetterDatensatz, string>> | null>;
/** Prüf-Namen und -IDs der Wetter-Prüf-Datensätze (Präfix E2E-GZ; der Prüfkonto-Seed trägt nie diese Namen). */
export const WETTER_NAME = 'E2E-GZ #2966 Wetter-Prüfung';
export const WETTER_TRIP_ID = 'e2e-gz-2966-wetter';
/** #3192 (AC-3): eigene Vorlage je Art wie im Mockup („eigene · aus GR221 gespeichert“), eindeutiger Prüf-Name. */
export const EIGENE_VORLAGE_NAME = 'E2E-GZ #3192 eigene Vorlage';
export const EIGENE_VORLAGE_BESCHREIBUNG = 'aus GR221 gespeichert';
/** Prüf-Datensätze aus `pruefDaten` (nur angelegt, wenn dem Konto Trip bzw. Orts-Vergleich fehlen). */
export const ABGLEICH_TRIP_ID = 'e2e-gz-2913-abgleich';
export const ABGLEICH_NAMEN = ['E2E-GZ #2913 Elementlisten-Abgleich', 'E2E-GZ #2913 Ort', 'E2E-GZ #2913 Orte-Abgleich'];

export function wetterTripId(d: WetterDatensatz): string {
	return `${WETTER_TRIP_ID}-${d === 'mit_abweichung' ? 'mit' : 'ohne'}`;
}
export function wetterName(d: WetterDatensatz): string {
	return `${WETTER_NAME} (${d === 'mit_abweichung' ? 'mit' : 'ohne'} Abweichung)`;
}

/**
 * Fix-Loop F002 (a): Seiten-ID eines Bedien-Abschnitts im Reiter Wetter — Grenzen-Abschnitte auf dem Datensatz
 * mit Abweichung, Vorlage-Abschnitte ohne (über datensatzFuerAbschnitt); fehlt der Datensatz, null (nie ersetzen).
 */
export function seitenIdFuer(abschnitt: string, ctx: string, wetterIds: WetterIds): string | null {
	return wetterIds[ctx]?.[datensatzFuerAbschnitt(abschnitt)] ?? null;
}

/** Aktive Metriken (`ampel.metrics[*].enabled === true`) einer Systemvorlage aus der Antwort von /api/templates. */
export function aktiveMetrikenDerVorlage(vorlagen: Record<string, unknown>[], vid: string): string[] {
	const m = ((vorlagen.find((v) => v.id === vid)?.ampel ?? {}) as { metrics?: Record<string, { enabled?: boolean }> }).metrics ?? {};
	return Object.entries(m).filter(([, e]) => e?.enabled === true).map(([id]) => id);
}

export type WetterPruefQuelle = {
	liste: ListenElement[];
	/** Antwort von /api/templates (Liste). */
	vorlagen: Record<string, unknown>[];
	/** `allowed_sides` je Metrik aus /api/metrics. */
	eig: Record<string, { allowed_sides: string | null } | undefined>;
	/** Orts-IDs des Vergleichs (nur ctx orte). */
	ortIds: string[];
	/** Datum der Etappe (YYYY-MM-DD, nur ctx trip). */
	datum: string;
};

/**
 * Fix-Loop F002 (c): Anlege-Payload eines Wetter-Prüf-Datensatzes. „ohne Abweichung“: Metrik-Auswahl = aktive
 * Metriken der Vorlage und Ampel nur mit Vorlage (sonst zählt die Auswahl als Abweichung und die Bestätigung
 * zeigt den Verlust-Satz); „mit Abweichung“: alle Grenzen-Metriken der Liste im Briefing, dazu gültige Overrides.
 */
export function wetterPruefPayload(ctx: 'trip' | 'orte', d: WetterDatensatz, q: WetterPruefQuelle): Record<string, unknown> {
	const vorlage = MOCKUP_LAGE[ctx].aktiv;
	const metriken = d === 'mit_abweichung' ? wetterPruefMetriken(q.liste, ctx) : aktiveMetrikenDerVorlage(q.vorlagen, vorlage);
	const ampel = d === 'mit_abweichung' ? { template: vorlage, ...wetterOverrides(metriken, q.eig) } : { template: vorlage };
	if (ctx === 'trip') {
		const id = wetterTripId(d);
		return {
			id,
			name: wetterName(d),
			region: 'Mallorca',
			stages: [
				{
					id: `${id}-stage-1`,
					name: 'Etappe 1',
					date: q.datum,
					waypoints: [
						{ id: `${id}-wp-1`, name: 'Start', lat: 39.6, lon: 2.5, elevation_m: 100 },
						{ id: `${id}-wp-2`, name: 'Ziel', lat: 39.7, lon: 2.6, elevation_m: 600 }
					]
				}
			],
			display_config: { preset_name: vorlage, metrics: metriken.map((m) => ({ metric_id: m, enabled: true })), ampel }
		};
	}
	return {
		name: wetterName(d),
		location_ids: q.ortIds,
		schedule: 'manual',
		profil: 'wandern',
		// Objektform: Katalog-Zeichenketten verwirft der Vergleich (leere Auswahl).
		display_config: { active_metrics: metriken.map((m) => ({ metric_id: m, aggregation: 'max' })), ampel }
	};
}

/** Fix-Loop F002 (c): eigene Prüf-Vorlage je Art wie im Mockup („eigene · aus GR221 gespeichert“). */
export function eigeneVorlagePayload(kind: 'route' | 'vergleich'): Record<string, unknown> {
	return { name: EIGENE_VORLAGE_NAME, description: EIGENE_VORLAGE_BESCHREIBUNG, kind, metrics: ['temperature', 'wind'], friendly_ids: [], is_default: false };
}

export type KontoBestand = {
	trips: Record<string, unknown>[];
	vergleiche: Record<string, unknown>[];
	orte: Record<string, unknown>[];
	vorlagen: Record<string, unknown>[];
};

/**
 * Fix-Loop F002 (b): Prüf-Reste nach dem Aufräumen — Objekte mit den Prüf-Namen bzw. -IDs dieses Abgleichs.
 * Nur exakte Prüf-Namen/Präfixe zählen; Seed-Daten des Prüfkontos (z. B. „Mallorca Frühling“, GR221,
 * Münsterland) sind nie ein Rest. Rückgabe: lesbare Liste, leer = kein Leck.
 */
export function pruefReste(b: KontoBestand): string[] {
	const name = (o: Record<string, unknown>) => String(o.name ?? '');
	const id = (o: Record<string, unknown>) => String(o.id ?? '');
	const istPruefName = (o: Record<string, unknown>) => name(o).startsWith(WETTER_NAME) || ABGLEICH_NAMEN.includes(name(o));
	const reste: string[] = [];
	for (const t of b.trips) if (istPruefName(t) || id(t).startsWith(WETTER_TRIP_ID) || id(t) === ABGLEICH_TRIP_ID) reste.push(`Trip ${id(t)} „${name(t)}“`);
	for (const v of b.vergleiche) if (istPruefName(v)) reste.push(`Orts-Vergleich ${id(v)} „${name(v)}“`);
	for (const o of b.orte) if (istPruefName(o)) reste.push(`Ort ${id(o)} „${name(o)}“`);
	for (const p of b.vorlagen) if (name(p) === EIGENE_VORLAGE_NAME) reste.push(`Vorlage ${id(p)} „${name(p)}“`);
	return reste;
}

/** #2966: Weg je Abschnitt vor der Bedienung — lesen, später bedienen (vorab mit allen Metriken) oder nicht herstellbar. */
export type AbschnittsWeg = { abschnitt: string; weg: 'lesen' } | { abschnitt: string; weg: 'bedienen' } | { abschnitt: string; weg: 'nicht_herstellbar'; grund: string };
export function ordneAbschnitte(abschnitte: string[], lage: Omit<BedienLage, 'briefing'>, liste: ListenElement[]): AbschnittsWeg[] {
	return abschnitte.map((abschnitt): AbschnittsWeg => {
		const vorab = bedienPlan(abschnitt, { ...lage, briefing: wetterPruefMetriken(liste, lage.ctx) });
		if (vorab.art === 'plan') return { abschnitt, weg: 'bedienen' };
		if (vorab.art === 'nicht_herstellbar') return { abschnitt, weg: 'nicht_herstellbar', grund: vorab.grund };
		return { abschnitt, weg: 'lesen' };
	});
}

export type BereichsBefund = { marker: boolean; texte: string[] };
/** Browser-Operationen eines Bedien-Abschnitts; `anfragen` speist der Request-Listener der Seite. */
export type BedienOps = {
	neuLaden(): Promise<void>;
	briefing(): Promise<string[]>;
	klick(testid: string): Promise<void>;
	taste(taste: string): Promise<void>;
	lesen(abschnitt: string): Promise<BereichsBefund>;
	/** Wartezeit nach der Bedienung, damit verzögerte Speicherungen in `anfragen` landen. */
	nachlauf(): Promise<void>;
	anfragen: { method: string; url: string }[];
};
export type BedienErgebnis = { art: 'gelesen'; befund: BereichsBefund } | { art: 'nicht_pruefbar'; grund: string } | { art: 'schreibbefund'; grund: string };

/**
 * #2966 (AC-6, AC-7): einen Bedien-Abschnitt herstellen — Seite neu laden, Plan mit dem echten Briefing bilden,
 * Schritte in Planreihenfolge ausführen; jede schreibende Anfrage ab Bedienbeginn (inkl. Nachlauf) ist ein Befund.
 */
export async function bedieneAbschnitt(abschnitt: string, lage: Omit<BedienLage, 'briefing'>, ops: BedienOps): Promise<BedienErgebnis> {
	await ops.neuLaden();
	const bp = bedienPlan(abschnitt, { ...lage, briefing: await ops.briefing() });
	if (bp.art === 'nicht_herstellbar') return { art: 'nicht_pruefbar', grund: bp.grund };
	if (bp.art !== 'plan') return { art: 'nicht_pruefbar', grund: `Script-Zustand „${abschnitt}“ ohne Bedienplan` };
	const start = ops.anfragen.length;
	let befund: BereichsBefund = { marker: false, texte: [] };
	let fehler: string | null = null;
	try {
		for (const s of bp.schritte) {
			if (s.aktion === 'lesen') befund = await ops.lesen(abschnitt);
			else if (s.testid) await ops.klick(s.testid);
			else if (s.taste) await ops.taste(s.taste);
		}
	} catch (e) {
		fehler = `Bedienung für „${abschnitt}“ fehlgeschlagen: ${e instanceof Error ? e.message.split('\n')[0] : String(e)}`;
	} finally {
		await ops.nachlauf();
	}
	const schreib = schreibBefund(ops.anfragen.slice(start));
	if (schreib) return { art: 'schreibbefund', grund: schreib };
	if (fehler) return { art: 'nicht_pruefbar', grund: fehler };
	return { art: 'gelesen', befund };
}

/** #2966 (AC-8): anlegen → arbeiten → aufräumen; jeder Aufräumschritt läuft, auch wenn Anlegen oder Arbeit scheitern. */
export async function mitAufraeumen<T, R>(anlegen: (aufraeumen: Array<() => Promise<unknown>>) => Promise<T>, arbeit: (daten: T) => Promise<R>): Promise<R> {
	const aufraeumen: Array<() => Promise<unknown>> = [];
	try {
		return await arbeit(await anlegen(aufraeumen));
	} finally {
		for (const f of aufraeumen) {
			try {
				await f();
			} catch {
				// Aufräumen ist bestmöglich; der ursprüngliche Fehler bleibt maßgeblich.
			}
		}
	}
}

/** #2966 (AC-8): alle Metriken mit Grenzen-Abschnitt im Reiter Wetter je Kontext (Briefing des Wetter-Prüf-Datensatzes). */
export function wetterPruefMetriken(liste: ListenElement[], ctx: string): string[] {
	const ids = liste.filter((e) => e.ctx === ctx && e.reiter === 'wetter' && e.abschnitt.startsWith('grenzen-')).map((e) => e.abschnitt.slice('grenzen-'.length));
	return [...new Set(ids.filter((id) => id.length > 0))];
}

const SCHREIBEND = new Set(['PUT', 'POST', 'PATCH', 'DELETE']);

/** #2966 (AC-7) Schreib-Tripwire: jede schreibende Anfrage während der Bedienung ist ein Befund (null = keine). */
export function schreibBefund(anfragen: { method: string; url: string }[]): string | null {
	const schreibend = anfragen.filter((a) => SCHREIBEND.has(a.method.toUpperCase()));
	if (schreibend.length === 0) return null;
	return `Schreib-Tripwire: ${schreibend.length} schreibende Anfrage(n) während der Bedienung: ${schreibend.map((a) => `${a.method.toUpperCase()} ${a.url}`).join(', ')}`;
}

const HAT_PLATZHALTER = /\{[^}]+\}/;

/**
 * Erwarteter Text als RegExp (DE: Muster bzw. exakt; EN: text_en mit beliebigen Zahlen); null = EN-Lücke.
 * #2913 Fix-Loop 2 (C5): EN-Texte mit Platzhaltern (`{metrik}`) sind Muster — der Generator setzt keine
 * DE-Werte mehr ein; ein Platzhalter passt auf jeden Wert.
 */
export function erwartung(e: ListenElement, sprache: Sprache): RegExp | null {
	if (sprache === 'en') {
		if (e.luecke || !e.text_en) return null;
		if (e.sprachneutral) return neutralMuster(e.text_en);
		const kandidaten = e.text_en_alternativen?.length ? e.text_en_alternativen : [e.text_en];
		return new RegExp('^(?:' + kandidaten.map(enQuelle).join('|') + ')$');
	}
	if (e.muster) return new RegExp('^' + musterAlsRegExp(e.muster).source + '$');
	return new RegExp('^' + esc(normalisiere(e.text_de)) + '$');
}

/** EN-Erwartung eines Kandidaten (ohne Anker): Platzhalter beliebig, sonst wörtlich mit beliebigen Zahlen. */
function enQuelle(text: string): string {
	if (HAT_PLATZHALTER.test(text)) return musterAlsRegExp(text).source;
	return normalisiere(text).split(/\d+(?:[.,]\d+)?/).map(esc).join('[\\d.,]+');
}

/** Zahl-Text, den `{zahl}` in der Gegenrichtung erklärt (Vorzeichen, Dezimal-, Tausender-, Uhrzeit-Trenner). */
const ZAHL_TEXT = '[-−+]?\\d+(?:[.,:]\\d+)*';

/**
 * #2968 (AC-6): sprachneutraler Eintrag im EN-Lauf wie das DE-Muster: `{zahl}` passt nur auf eine Zahl, alles
 * andere wörtlich (ein Eigenname oder Token erklärt keinen fremden Text).
 * Bewusst (Adversary F004): `{zahl}` passt auf JEDE Zahl, auch mit anderer Stellenzahl („60%“ erwartet „5%“ wie
 * „100%“) — AC-6 sagt „Zahlen beliebig“, wie das DE-Muster; geprüft wird die Form, nicht der Wert (Kontodaten).
 */
function neutralMuster(muster: string): RegExp {
	return new RegExp('^' + normalisiere(muster).split('{zahl}').map(esc).join('\\d+(?:[.,]\\d+)*') + '$');
}

/**
 * `{metrik}` der Gegenrichtung (#3011): genau einer der bekannten Namen (normalisiert, wörtlich escaped);
 * leere Menge ⇒ `(?!)`, passt nie (fail-closed: unbekannte Texte erscheinen als `zusaetzlich`).
 */
function metrikText(metrikNamen: string[]): string {
	const namen = [...new Set(metrikNamen.map(normalisiere).filter((n) => n !== ''))];
	return namen.length === 0 ? '(?!)' : '(?:' + namen.map(esc).join('|') + ')';
}

/**
 * Wie `musterAlsRegExp`, aber `{zahl}` passt nur auf Zahl-Text und `{metrik}` nur auf einen bekannten
 * Metriknamen (#3011); andere Platzhalter bleiben beliebig.
 */
function gegenMuster(muster: string, metrik: string): RegExp {
	const teile = normalisiere(muster).split(/(\{[^}]+\})/);
	const platzhalter = (t: string) => (t === '{zahl}' ? ZAHL_TEXT : t === '{metrik}' ? metrik : '.+?');
	const quelle = teile.map((t, i) => (i % 2 === 0 ? esc(t) : platzhalter(t))).join('');
	return new RegExp('^' + quelle + '$');
}

/**
 * Erwartung der Gegenrichtung (#2913 Fix-Loop 4): wie `erwartung`, nur erklärt `{zahl}` keinen beliebigen
 * Text (sonst wird ein Eintrag `muster: "{zahl}"` zu `^.+?$` und erklärt jeden Live-Text), und `{metrik}`
 * nur einen bekannten Metriknamen (#3011, `metrik` aus `metrikText`). Die Hinrichtung nutzt weiter `erwartung`.
 */
function erwartungGegenrichtung(e: ListenElement, sprache: Sprache, metrik: string): RegExp | null {
	const vorlage = sprache === 'en' ? e.text_en : e.muster;
	if (sprache === 'en' && (e.luecke || !vorlage)) return null;
	if (vorlage && HAT_PLATZHALTER.test(vorlage)) return gegenMuster(vorlage, metrik);
	return erwartung(e, sprache);
}

/**
 * Metriknamen aus der Antwort von GET /api/metrics (Kategorie → [{label, label_de, label_en, …}]): alle
 * nicht-leeren Labels. Ungültige Antwort ⇒ [] (nie geraten).
 */
export function metrikNamenAusRegister(antwort: unknown): string[] {
	if (!istObjekt(antwort)) return [];
	const out = new Set<string>();
	for (const metriken of Object.values(antwort)) {
		if (!Array.isArray(metriken)) continue;
		for (const m of metriken) {
			if (!istObjekt(m)) continue;
			for (const feld of ['label', 'label_de', 'label_en']) if (nichtLeer(m[feld])) out.add(m[feld].trim());
		}
	}
	return [...out];
}

/** DE-Metriknamen der Elementliste: Wert von `{metrik}` in `text_de` aller Einträge mit `{metrik}` im Muster. */
export function metrikNamenAusListe(liste: ListenElement[]): string[] {
	const out = new Set<string>();
	for (const e of liste) {
		if (!e.muster || !e.muster.includes('{metrik}')) continue;
		const teile = normalisiere(e.muster).split(/(\{[^}]+\})/);
		const quelle = teile.map((t, i) => (i % 2 === 0 ? esc(t) : t === '{metrik}' ? '(.+?)' : '.+?')).join('');
		const treffer = new RegExp('^' + quelle + '$').exec(normalisiere(e.text_de));
		for (const wert of treffer?.slice(1) ?? []) if (nichtLeer(wert)) out.add(wert.trim());
	}
	return [...out];
}

/** Freigegebene Abweichung: Elemente eines Abschnitts (per Katalogschlüssel), die laut Spec fehlen dürfen. */
export type Freigabe = { ctx: string; reiter: string; abschnitt: string; i18n_keys: string[]; grund: string; spec: string };

/** Freigaben aus dem JSON-Text ({"freigaben": [...]}); jede braucht Grund und Spec-Verweis. */
export function leseFreigaben(text: string): Freigabe[] {
	const liste = (JSON.parse(text) as { freigaben?: unknown }).freigaben;
	if (!Array.isArray(liste)) throw new Error('Freigaben: Feld „freigaben“ fehlt');
	return liste.map((f: Freigabe, i) => {
		for (const feld of ['ctx', 'reiter', 'abschnitt', 'grund', 'spec'] as const) {
			if (typeof f[feld] !== 'string' || !f[feld].trim()) throw new Error(`Freigabe ${i}: „${feld}“ fehlt`);
		}
		if (!Array.isArray(f.i18n_keys) || f.i18n_keys.length === 0) throw new Error(`Freigabe ${i}: „i18n_keys“ fehlt`);
		return f;
	});
}

/**
 * Macht aus `abweichend` ein `freigegeben` (Grund + Spec), wenn eine Freigabe das Element deckt. Gefunden
 * bleibt gefunden (die Abweichung besteht nicht mehr), nicht_pruefbar bleibt nicht_pruefbar (nicht geprüft).
 */
export function wendeFreigabenAn(elemente: ListenElement[], ergebnisse: Map<string, Ergebnis>, freigaben: Freigabe[]): Map<string, Ergebnis> {
	const out = new Map(ergebnisse);
	for (const e of elemente) {
		const erg = out.get(e.id);
		if (!erg || erg.status !== 'abweichend' || !e.i18n_key) continue;
		const f = freigaben.find((x) => x.ctx === e.ctx && x.reiter === e.reiter && x.abschnitt === e.abschnitt && x.i18n_keys.includes(e.i18n_key as string));
		if (f) out.set(e.id, { status: 'freigegeben', grund: `${f.grund} (${f.spec})`, ist: erg.ist ?? erg.grund });
	}
	return out;
}

// ------------------------------------------------------------------ Ganzseiten-Abgleich (feat_2913_abgleich_ganzseite)

/** Wurzel der Gegenrichtung: alle Hub-Container (Kopf und Reiterfläche), nie `body` (Seitenleiste, BottomNav, SaveIndicator). */
export const GEGENRICHTUNG_WURZEL = '[data-seite="hub"]';
/** Anker der Gegenrichtung (Fix-Loop 3, F002): HubKopf und Reiterfläche (TripTabs/CompareTabs-Wurzel, Geschwister des Kopfs). */
export const HUB_ANKER_KOPF = '[data-seite="hub"][data-abschnitt="kopf"]';
export const HUB_ANKER_FLAECHE = '[data-seite="hub"]:not([data-abschnitt="kopf"])';
/** Rohwerte aus dem Browser: Anzahl Treffer je Anker. */
export type HubAnker = { kopf: number; flaeche: number };

/**
 * Im Browser (per `page.evaluate(zaehleAnker, { kopf: HUB_ANKER_KOPF, flaeche: HUB_ANKER_FLAECHE })`):
 * Anzahl Treffer je Hub-Anker. Fix-Runde 4 (F003): hier statt in der Spec, damit die Verdrahtung bewacht ist.
 * page.evaluate serialisiert die Funktion: keine Modul-Closures, Selektoren nur aus `arg`, Wurzel `document`.
 */
export function zaehleAnker(arg: { kopf: string; flaeche: string }, wurzel: ParentNode = document): HubAnker {
	return { kopf: wurzel.querySelectorAll(arg.kopf).length, flaeche: wurzel.querySelectorAll(arg.flaeche).length };
}

/**
 * Beide Anker sind Pflicht: fehlt einer, wäre ein Teil der Seite still nicht gelesen. null = prüfbar,
 * sonst der Grund mit dem fehlenden Anker.
 */
export function pruefeHubAnker(anker: HubAnker): string | null {
	const fehlt: string[] = [];
	if (!(anker.kopf > 0)) fehlt.push(`Kopf ${HUB_ANKER_KOPF}`);
	if (!(anker.flaeche > 0)) fehlt.push(`Reiterfläche ${HUB_ANKER_FLAECHE}`);
	return fehlt.length === 0 ? null : `Hub-Marker fehlt: ${fehlt.join(' und ')} nicht auf der Seite: Gegenrichtung nicht prüfbar`;
}

/**
 * #2973: Hub-Anker erscheinen bei langsamer Staging-Antwort verzögert. Zählt per `zaehle()`, bis
 * `pruefeHubAnker` null meldet oder die Versuche aufgebraucht sind (Vorgabe 10 × 500 ms ≈ 5 s); zwischen
 * den Versuchen `warte(abstandMs)`, nach dem letzten nicht. Gibt den letzten Befund zurück; die Entscheidung
 * (fail-closed) bleibt bei pruefeHubAnker über werteGegenrichtungAus.
 */
export async function warteAufHubAnker(
	zaehle: () => Promise<HubAnker>,
	warte: (ms: number) => Promise<void>,
	opt: { versuche?: number; abstandMs?: number } = {}
): Promise<HubAnker> {
	const versuche = Math.max(1, opt.versuche ?? 10);
	const abstandMs = opt.abstandMs ?? 500;
	let anker = await zaehle();
	for (let i = 1; i < versuche && pruefeHubAnker(anker) !== null; i++) {
		await warte(abstandMs);
		anker = await zaehle();
	}
	return anker;
}

/** Gegenrichtung nur im Zustand normal und ohne Kanal-Segment (Desktop-Lauf). */
export function istGegenrichtung(k: Kombi): boolean {
	return k.zustand === 'normal' && (k.segment ?? null) === null;
}

/** Abschnitte, die auf jedem Reiter eines ctx sichtbar sind (in der Liste unter Reiter wetter geführt). */
const REITERUEBERGREIFEND = new Set(['kopf', 'reiterleiste']);

/** Stabile ID eines zusätzlichen Texts: `zus:<ctx>/<reiter>/<hash>`; Zahlen werden vor dem Hash zu `{zahl}`. */
export function zusaetzlichId(ctx: string, reiter: string, text: string): string {
	const basis = normalisiere(normalisiere(text).replace(/\d+(?:[.,:]\d+)*/g, '{zahl}'));
	return `zus:${ctx}/${reiter}/${createHash('sha1').update(basis).digest('hex').slice(0, 12)}`;
}

/** Live-Text, der bewusst nicht in der Elementliste steht (Text oder Muster), mit Grund und Spec-Verweis. */
export type Ausnahme = { ctx?: string; reiter?: string; text?: string; muster?: string; grund: string; spec: string };

const nichtLeer = (x: unknown): x is string => typeof x === 'string' && x.trim() !== '';

/** Ausnahmen aus dem JSON-Text ({"ausnahmen": [...]}); jede braucht Text oder Muster, Grund und Spec. */
export function leseAusnahmen(text: string): Ausnahme[] {
	const liste = (JSON.parse(text) as { ausnahmen?: unknown }).ausnahmen;
	if (!Array.isArray(liste)) throw new Error('Ausnahmen: Feld „ausnahmen“ fehlt');
	return liste.map((a: Ausnahme, i) => {
		if (!nichtLeer(a.text) && !nichtLeer(a.muster)) throw new Error(`Ausnahme ${i}: „text“ oder „muster“ fehlt`);
		for (const feld of ['grund', 'spec'] as const) {
			if (!nichtLeer(a[feld])) throw new Error(`Ausnahme ${i}: „${feld}“ fehlt`);
		}
		return a;
	});
}

/**
 * Muster einer Ausnahme bzw. eines Besitzers als verankerte RegExp: `{zahl}` passt nur auf Zahl-Text (#3258,
 * ein Zahl-Muster erklärt keinen beliebigen Text), jeder andere Platzhalter (`{name}`) auf einen beliebigen Wert.
 */
function zielMuster(muster: string): RegExp {
	const teile = normalisiere(muster).split(/(\{[^}]+\})/);
	return new RegExp('^' + teile.map((t, i) => (i % 2 === 0 ? esc(t) : t === '{zahl}' ? ZAHL_TEXT : '.+?')).join('') + '$');
}

/** Passt ein normalisierter Text auf Text bzw. Muster (siehe `zielMuster`) und ggf. ctx/Reiter? */
function trifftZiel(ziel: { ctx?: string; reiter?: string; text?: string; muster?: string }, ctx: string, reiter: string, t: string): boolean {
	if ((ziel.ctx !== undefined && ziel.ctx !== ctx) || (ziel.reiter !== undefined && ziel.reiter !== reiter)) return false;
	if (nichtLeer(ziel.text) && normalisiere(ziel.text) === t) return true;
	return nichtLeer(ziel.muster) && zielMuster(ziel.muster).test(t);
}

/** Alle `name`-Werte (Trip, Preset, Etappe, Ort) aus API-Antworten; IDs sind keine Konto-Texte. */
export function sammleKontoTexte(daten: unknown): string[] {
	const out = new Set<string>();
	const gehe = (x: unknown): void => {
		if (Array.isArray(x)) x.forEach(gehe);
		else if (istObjekt(x)) {
			for (const [k, v] of Object.entries(x)) {
				if (k === 'name' && nichtLeer(v)) out.add(v.trim());
				else gehe(v);
			}
		}
	};
	gehe(daten);
	return [...out];
}

/**
 * Gegenrichtung: sichtbare Texte einer Kombination (ctx × Reiter, Zustand normal), die weder zu einem
 * Eintrag des Reiters bzw. zu kopf/reiterleiste desselben ctx (DE/EN), noch zu einem Konto-Text, noch zu
 * einer Ausnahme passen. Reihenfolge egal; jeder Text (je ID) höchstens einmal.
 */
export function findeZusaetzliche(
	befund: { ctx: string; reiter: string; texte: string[] },
	liste: ListenElement[],
	ausnahmen: Ausnahme[],
	kontoTexte: string[],
	sprache: Sprache,
	metrikNamen: string[] = []
): ZusaetzlichEintrag[] {
	const { ctx, reiter } = befund;
	// #3011: `{metrik}` erklärt nur Register-Namen (metrikNamen) und DE-Namen der Elementliste.
	const metrik = metrikText([...metrikNamen, ...metrikNamenAusListe(liste)]);
	const regeln = liste
		.filter((e) => e.ctx === ctx && e.zustand === 'normal' && (e.reiter === reiter || REITERUEBERGREIFEND.has(e.abschnitt)))
		.map((e) => erwartungGegenrichtung(e, sprache, metrik))
		.filter((re): re is RegExp => re !== null);
	const konto = new Set(kontoTexte.map(normalisiere));
	const out = new Map<string, ZusaetzlichEintrag>();
	for (const roh of befund.texte) {
		const t = normalisiere(roh);
		if (!t || konto.has(t) || regeln.some((re) => re.test(t))) continue;
		if (ausnahmen.some((a) => trifftZiel(a, ctx, reiter, t))) continue;
		const id = zusaetzlichId(ctx, reiter, t);
		if (!out.has(id)) out.set(id, { id, ctx, reiter, text: t, status: 'zusaetzlich' });
	}
	return [...out.values()];
}

/**
 * Gegenrichtung einer Kombination aus dem DOM-Befund unter `GEGENRICHTUNG_WURZEL`. Fehlt einer der beiden
 * Anker (Kopf, Reiterfläche; `pruefeHubAnker`), ist die Gegenrichtung nicht prüfbar: kein `zusaetzlich`,
 * aber ein Befund `ohneHub` mit dem fehlenden Anker (im Bericht sichtbar, unter --abnahme rot). Sonst wie
 * `findeZusaetzliche`.
 */
export function werteGegenrichtungAus(
	befund: { ctx: string; reiter: string; anker: HubAnker; texte: string[] },
	liste: ListenElement[],
	ausnahmen: Ausnahme[],
	kontoTexte: string[],
	sprache: Sprache,
	metrikNamen: string[] = []
): { zusaetzlich: ZusaetzlichEintrag[]; ohneHub: OhneHubEintrag | null } {
	const { ctx, reiter } = befund;
	const grund = pruefeHubAnker(befund.anker);
	if (grund !== null) return { zusaetzlich: [], ohneHub: { ctx, reiter, grund } };
	return { zusaetzlich: findeZusaetzliche({ ctx, reiter, texte: befund.texte }, liste, ausnahmen, kontoTexte, sprache, metrikNamen), ohneHub: null };
}

/** Besitzer einer Abweichung: ein Element (id), ein ganzer Abschnitt oder ein zusätzlicher Text (Text/Muster). */
export type Besitzer =
	| { art: 'element'; id: string; grund: string; verweis: string }
	| { art: 'abschnitt'; ctx: string; reiter: string; abschnitt: string; grund: string; verweis: string }
	| { art: 'zusaetzlich'; ctx?: string; reiter?: string; text?: string; muster?: string; grund: string; verweis: string };

/** Scheibe von #2913 (c2, d, e) oder ein Issue `#NNNN`. */
export const BESITZER_VERWEIS = /^#(?:2913-(?:c2|d|e)|\d+)$/;

const PFLICHT_JE_ART: Record<string, string[]> = { element: ['id'], abschnitt: ['ctx', 'reiter', 'abschnitt'], zusaetzlich: [] };

/**
 * Besitzer aus dem JSON-Text ({"besitzer": [...]}); Grund und gültiger Verweis sind Pflicht. Mit `elemente`
 * (Elementliste) muss jeder element-Besitzer auf eine bekannte ID zeigen und jeder abschnitt-Besitzer auf
 * ein vorhandenes Tripel (ctx, reiter, abschnitt) (#3008 F001).
 */
export function leseBesitzer(text: string, elemente?: ListenElement[]): Besitzer[] {
	const liste = (JSON.parse(text) as { besitzer?: unknown }).besitzer;
	if (!Array.isArray(liste)) throw new Error('Besitzer: Feld „besitzer“ fehlt');
	const ids = elemente ? new Set(elemente.map((e) => e.id)) : null;
	const tripel = elemente ? new Set(elemente.map((e) => `${e.ctx}|${e.reiter}|${e.abschnitt}`)) : null;
	return liste.map((b: unknown, i) => {
		if (!istObjekt(b)) throw new Error(`Besitzer ${i}: Eintrag ist kein Objekt`);
		const geprueft = pruefeBesitzer(b, i);
		if (ids && geprueft.art === 'element' && !ids.has(geprueft.id)) throw new Error(`Besitzer ${i}: Element „${geprueft.id}“ steht nicht in der Elementliste`);
		if (tripel && geprueft.art === 'abschnitt' && !tripel.has(`${geprueft.ctx}|${geprueft.reiter}|${geprueft.abschnitt}`)) {
			throw new Error(`Besitzer ${i}: Abschnitt „${geprueft.abschnitt}“ (${geprueft.ctx}/${geprueft.reiter}) steht nicht in der Elementliste`);
		}
		return geprueft;
	});
}

/** Ein Besitzer-Eintrag: bekannte Ziel-Art, Pflichtfelder je Art, Grund und gültiger Verweis. */
function pruefeBesitzer(b: Record<string, unknown>, i: number): Besitzer {
	// Fix-Loop 2 (Befund 2): nur eigene Schlüssel; „constructor“, „toString“, „__proto__“ kämen sonst vom Prototyp.
	const pflicht = Object.hasOwn(PFLICHT_JE_ART, String(b.art)) ? PFLICHT_JE_ART[String(b.art)] : undefined;
	if (!pflicht) throw new Error(`Besitzer ${i}: „art“ „${String(b.art)}“ unbekannt (erlaubt: element, abschnitt, zusaetzlich)`);
	for (const feld of [...pflicht, 'grund', 'verweis']) {
		if (!nichtLeer(b[feld])) throw new Error(`Besitzer ${i}: „${feld}“ fehlt`);
	}
	if (!BESITZER_VERWEIS.test(String(b.verweis).trim())) {
		throw new Error(`Besitzer ${i}: „verweis“ „${String(b.verweis)}“ ungültig (erlaubt: #2913-c2, #2913-d, #2913-e oder #NNNN)`);
	}
	if (b.art === 'zusaetzlich' && !nichtLeer(b.text) && !nichtLeer(b.muster)) throw new Error(`Besitzer ${i}: „text“ oder „muster“ fehlt`);
	return b as Besitzer;
}

const alsVerweis = (b: Besitzer): BesitzerVerweis => ({ grund: b.grund, verweis: b.verweis });

/** Besitzer eines Listen-Eintrags: zuerst per Element-ID, sonst per Abschnitt. */
function besitzerFuerEintrag(e: BerichtEintrag, besitzer: Besitzer[]): Besitzer | undefined {
	return (
		besitzer.find((b) => b.art === 'element' && b.id === e.id) ??
		besitzer.find((b) => b.art === 'abschnitt' && b.ctx === e.ctx && b.reiter === e.reiter && b.abschnitt === e.abschnitt)
	);
}

/**
 * Setzt `besitzer` an jeder gedeckten Abweichung (abweichend, nicht_pruefbar, zusaetzlich). Status und
 * Zähler bleiben unverändert; der Bericht wird nicht verändert, sondern kopiert.
 */
export function wendeBesitzerAn(bericht: Bericht, besitzer: Besitzer[]): Bericht {
	const eintraege = bericht.eintraege.map((e) => {
		if (e.status !== 'abweichend' && e.status !== 'nicht_pruefbar') return { ...e };
		const b = besitzerFuerEintrag(e, besitzer);
		return b ? { ...e, besitzer: alsVerweis(b) } : { ...e };
	});
	const zusaetzlich = bericht.zusaetzlich.map((z) => {
		const b = besitzer.find((x) => x.art === 'zusaetzlich' && trifftZiel(x, z.ctx, z.reiter, z.text));
		return b ? { ...z, besitzer: alsVerweis(b) } : { ...z };
	});
	return { eintraege, zusaetzlich, ohne_hub: (bericht.ohne_hub ?? []).map((o) => ({ ...o })), zaehler: { ...bericht.zaehler } };
}

/** Regeln des Laufs: Freigaben, Besitzer und Ausnahmen (aus dem Kontext-Ordner der Elementliste). */
export type Regeln = { freigaben: Freigabe[]; besitzer: Besitzer[]; ausnahmen: Ausnahme[] };

/**
 * Liest die Freigaben- und die Besitzer-Datei (elementliste_freigaben.json, elementliste_besitzer.json). Ein
 * ungültiger Eintrag (auch ein element-Besitzer mit einer ID, die nicht in `liste` steht) bricht den Lauf
 * vor jedem Seitenaufruf ab.
 */
export function ladeRegeln(dateien: { freigaben: string; besitzer: string }, liste: ListenElement[]): Regeln {
	const besitzerText = readFileSync(dateien.besitzer, 'utf8');
	return {
		freigaben: leseFreigaben(readFileSync(dateien.freigaben, 'utf8')),
		besitzer: leseBesitzer(besitzerText, liste),
		ausnahmen: leseAusnahmen(besitzerText)
	};
}

/** Minimaler Ausschnitt einer Playwright-Antwort für lesende Konto-Abrufe. */
export type GetAntwort = { ok(): boolean; json(): Promise<unknown> };

/** API-Pfade, deren `name`-Werte Konto-Texte sind (Trip, Etappen, Orte, Orts-Vergleiche, Wetter-Vorlagen). */
export function kontoPfade(ids: Record<string, string | null>): string[] {
	const pfade = ['/api/compare/presets', '/api/locations', '/api/metric-presets'];
	if (ids.trip) pfade.push(`/api/trips/${encodeURIComponent(ids.trip)}`);
	if (ids.orte) pfade.push(`/api/compare/presets/${encodeURIComponent(ids.orte)}`);
	return pfade;
}

/** Konto-Texte aller `kontoPfade`; ein gescheiterter Abruf liefert keine Texte (nie geraten). */
export async function ladeKontoTexte(get: (pfad: string) => Promise<GetAntwort>, ids: Record<string, string | null>): Promise<string[]> {
	const texte = new Set<string>();
	for (const pfad of kontoPfade(ids)) {
		const r = await get(pfad).catch(() => null);
		if (!r || !r.ok()) continue;
		for (const t of sammleKontoTexte(await r.json().catch(() => null))) texte.add(t);
	}
	return [...texte];
}

/**
 * Auswertung nach dem Lauf: Freigaben, Bericht mit Zusätzlich-Liste, Besitzer, Bericht schreiben und
 * Abschluss mit den VOLLSTÄNDIGEN Optionen des Plans (strict und abnahme).
 */
export function werteLaufAus(arg: {
	plan: Plan;
	ergebnisse: Map<string, Ergebnis>;
	zusaetzlich: ZusaetzlichEintrag[];
	ohneHub?: OhneHubEintrag[];
	regeln: Regeln;
	berichtDir: string;
}): {
	bericht: Bericht;
	pfade: { json: string; md: string };
	ende: { exit: number; meldung: string };
} {
	const { plan, regeln } = arg;
	const roh = baueBericht(plan.elemente, wendeFreigabenAn(plan.elemente, arg.ergebnisse, regeln.freigaben), arg.zusaetzlich, arg.ohneHub ?? []);
	const bericht = wendeBesitzerAn(roh, regeln.besitzer);
	const pfade = schreibeBericht(arg.berichtDir, bericht, { optionen: plan.optionen, sprache: plan.sprache, baseURL: plan.baseURL });
	return { bericht, pfade, ende: abschluss(bericht, plan.elemente, plan.optionen) };
}

/**
 * #2913 Fix-Loop 2 (C3): Die Profilsprache überstimmt das Cookie. Nach dem Setzen der Profilsprache muss
 * `<html lang>` der Seite die Soll-Sprache tragen; sonst sagt der Lauf nichts aus ⇒ Grund für nicht_pruefbar.
 */
export function sprachGrund(soll: Sprache, htmlLang: string | null): string | null {
	const ist = String(htmlLang ?? '').trim().toLowerCase().split('-')[0];
	return ist === soll ? null : `Seite rendert Sprache „${ist || 'unbekannt'}“ statt „${soll}“ (<html lang>); Abgleich in dieser Sprache nicht aussagekräftig`;
}

/** Profilsprache, die nach dem Lauf wiederhergestellt wird (geteiltes Staging-Konto): de/en, sonst de. */
export function wiederherzustellendeSprache(profil: unknown): Sprache {
	const s = typeof profil === 'object' && profil !== null ? String((profil as Record<string, unknown>).language ?? '') : '';
	return s === 'en' ? 'en' : 'de';
}

/** Minimaler Ausschnitt einer Playwright-Antwort für den Sprach-PUT. */
export type PutAntwort = { ok(): boolean; status(): number };

/**
 * #2913 Fix-Loop 2 (F005): Profilsprache des geteilten Staging-Hilfskontos auf den Wert VOR dem Lauf
 * zurückstellen. Nie still: ein Fehlschlag (HTTP ≠ 2xx oder Ausnahme) wird per console.error gemeldet und
 * als `ok: false` mit Meldung zurückgegeben; die Spec lässt den Lauf daran scheitern.
 */
export async function stelleSpracheWieder(
	put: (daten: { language: Sprache }) => Promise<PutAntwort>,
	vorherSprache: Sprache
): Promise<{ ok: true } | { ok: false; meldung: string }> {
	let meldung: string;
	try {
		const r = await put({ language: vorherSprache });
		if (r.ok()) return { ok: true };
		meldung = `HTTP ${r.status()}`;
	} catch (e) {
		meldung = e instanceof Error ? e.message : String(e);
	}
	meldung = `Profilsprache NICHT auf „${vorherSprache}“ zurückgestellt (${meldung}) — geteiltes Staging-Hilfskonto bitte prüfen`;
	console.error(`Elementlisten-Abgleich: ${meldung}`);
	return { ok: false, meldung };
}

/** Alle Elemente einer Kombination als nicht_pruefbar mit demselben Grund. */
export function alleNichtPruefbar(el: ListenElement[], grund: string): Map<string, Ergebnis> {
	return new Map(el.map((e) => [e.id, { status: 'nicht_pruefbar' as const, grund }]));
}

/** Chip aus Kontodaten (z. B. „+ {metrik}“ in „Nicht im Briefing“): Rolle chip mit Platzhalter-Muster. */
export function istKontoChip(e: ListenElement): boolean {
	return e.rolle === 'chip' && !!e.muster && HAT_PLATZHALTER.test(e.muster);
}

/**
 * #2913 Fix-Loop 2 (C5): Welche Metriken als Chip erscheinen, sind Kontodaten — Menge und Reihenfolge
 * werden nicht verglichen. Geprüft wird: Abschnitt-Haken da und mindestens ein sichtbarer Text passt auf
 * das Chip-Muster (sonst alle abweichend). Dann: das erste Chip-Element steht für die Chip-Zeile
 * (gefunden); jedes weitere ist gefunden, wenn genau sein DE-Text sichtbar ist, sonst nicht_pruefbar
 * mit Grund (in EN ist der Einzeltext nicht ableitbar, nur das Muster).
 */
export function bewerteKontoChips(
	chips: ListenElement[],
	befund: { marker: boolean; texte: string[] },
	sprache: Sprache,
	abschnitt: string
): Map<string, Ergebnis> {
	const out = new Map<string, Ergebnis>();
	const sortiert = [...chips].sort((a, b) => a.ordnung - b.ordnung);
	if (sortiert.length === 0) return out;
	const re = erwartung(sortiert[0], sprache);
	const treffer = re ? befund.texte.filter((t) => re.test(t)) : [];
	const muster = sprache === 'en' ? sortiert[0].text_en : sortiert[0].muster;
	sortiert.forEach((e, i) => {
		if (!befund.marker) out.set(e.id, { status: 'abweichend', grund: `Abschnitt-Haken data-abschnitt="${abschnitt}" fehlt` });
		else if (!re) out.set(e.id, { status: 'nicht_pruefbar', grund: 'EN-Lücke: kein Katalogtext' });
		else if (treffer.length === 0) out.set(e.id, { status: 'abweichend', grund: `kein Chip mit Muster „${muster}“ sichtbar`, ist: 'nicht gefunden' });
		else if (sprache === 'de' && treffer.includes(normalisiere(e.text_de))) out.set(e.id, { status: 'gefunden' });
		else if (i === 0) out.set(e.id, { status: 'gefunden', grund: `Chip-Zeile mit Muster „${muster}“ vorhanden (${treffer.length} Chips; Menge ist Kontodaten)` });
		else {
			const warum = sprache === 'en' ? 'in EN ist nur das Muster prüfbar' : `„${e.text_de}“ ist in diesem Konto kein Chip`;
			out.set(e.id, { status: 'nicht_pruefbar', grund: `Chip-Menge ist Kontodaten: ${warum}`, ist: `${treffer.length} Chips mit Muster „${muster}“` });
		}
	});
	return out;
}

/**
 * Bewertung eines Abschnitts aus dem DOM-Befund (sichtbare Texte in DOM-Reihenfolge, Abschnitt-Haken
 * `data-abschnitt` vorhanden?): gefunden nur mit Haken und in Reihenfolge; ohne Haken abweichend;
 * Script-Abschnitt ohne Haken nicht_pruefbar; EN-Lücke nicht_pruefbar.
 */
export function bewerteAbschnitt(
	liste: ListenElement[],
	befund: { marker: boolean; texte: string[] },
	sprache: Sprache,
	abschnitt: string
): Map<string, Ergebnis> {
	const out = new Map<string, Ergebnis>();
	if (!befund.marker && SCRIPT_ABSCHNITT.test(abschnitt)) {
		for (const e of liste) out.set(e.id, { status: 'nicht_pruefbar', grund: `Script-Zustand „${abschnitt}“: ohne Haken data-abschnitt nicht herstellbar` });
		return out;
	}
	const norm = befund.texte.map(normalisiere);
	const chips = liste.filter(istKontoChip);
	for (const [i, e] of bewerteKontoChips(chips, { marker: befund.marker, texte: norm }, sprache, abschnitt)) out.set(i, e);
	let zuletzt = -1;
	for (const e of liste.filter((x) => !istKontoChip(x)).sort((a, b) => a.ordnung - b.ordnung)) {
		const re = erwartung(e, sprache);
		if (!re) {
			out.set(e.id, { status: 'nicht_pruefbar', grund: 'EN-Lücke: kein Katalogtext' });
			continue;
		}
		const nachher = norm.findIndex((t, i) => i > zuletzt && re.test(t));
		const irgendwo = norm.findIndex((t) => re.test(t));
		if (nachher >= 0 && befund.marker) {
			out.set(e.id, { status: 'gefunden' });
			zuletzt = nachher;
		} else if (nachher >= 0) {
			out.set(e.id, { status: 'abweichend', grund: `Abschnitt-Haken data-abschnitt="${abschnitt}" fehlt`, ist: 'nur seitenweit gefunden' });
			zuletzt = nachher;
		} else if (irgendwo >= 0) {
			out.set(e.id, { status: 'abweichend', grund: 'Reihenfolge im Abschnitt', ist: `vor Element Nr. ${e.ordnung - 1}` });
		} else {
			out.set(e.id, { status: 'abweichend', grund: 'Text nicht sichtbar', ist: 'nicht gefunden' });
		}
	}
	return out;
}

/** Bericht als bericht.json und bericht.md in `dir`; gibt die Pfade zurück. */
export function schreibeBericht(dir: string, bericht: Bericht, meta: Record<string, unknown>): { json: string; md: string } {
	mkdirSync(dir, { recursive: true });
	const json = join(dir, 'bericht.json');
	const md = join(dir, 'bericht.md');
	writeFileSync(json, JSON.stringify({ ...meta, ...bericht }, null, 1));
	writeFileSync(md, berichtAlsMarkdown(bericht));
	return { json, md };
}

/** Abschluss: jedes Element im Bericht (sonst Fehler), Exit-Entscheid nach Strict bzw. Abnahme. */
export function abschluss(bericht: Bericht, elemente: ListenElement[], opt: { strict: boolean; abnahme?: boolean }): { exit: number; meldung: string } {
	if (bericht.eintraege.length !== elemente.length) {
		throw new Error(`Bericht unvollständig: ${bericht.eintraege.length} von ${elemente.length} Elementen`);
	}
	const z = bericht.zaehler;
	const exit = exitCode(bericht, opt);
	const modus = [opt.strict ? ' (strict)' : '', opt.abnahme ? ` (abnahme: ${herrenlos(bericht)} ohne Besitzer)` : ''].join('');
	const hub = ohneHubAnzahl(bericht) > 0 ? `, Gegenrichtung: Hub-Marker fehlt ${ohneHubAnzahl(bericht)}` : '';
	return {
		exit,
		meldung: `gefunden ${z.gefunden}, abweichend ${z.abweichend}, nicht_pruefbar ${z.nicht_pruefbar}, freigegeben ${z.freigegeben}, zusaetzlich ${z.zusaetzlich}${hub}${modus} → Exit ${exit}`
	};
}

/** Starter: CLI-Flags --strict, --abnahme, --scope <x>, --sprache <de|en> in die Umgebung der Spec übersetzen. */
export function flagsAlsUmgebung(argv: string[]): Record<string, string> {
	const bekannt = new Set(['--strict', '--abnahme', '--scope', '--sprache']);
	const rest: string[] = [];
	let sprache: string | null = null;
	for (let i = 0; i < argv.length; i++) {
		const a = argv[i];
		const name = a.split('=')[0];
		if (!bekannt.has(name)) throw new Error(`unbekannte Option „${a}“ (erlaubt: --strict, --abnahme, --scope <reiter[/zustand]>, --sprache <de|en>)`);
		if ((a === '--scope' || a === '--sprache') && (i + 1 >= argv.length || argv[i + 1].startsWith('--'))) {
			throw new Error(`${a} braucht einen Wert`);
		}
		if (name === '--sprache') {
			sprache = a.includes('=') ? a.slice(a.indexOf('=') + 1) : argv[++i];
			continue;
		}
		rest.push(a);
		if (a === '--scope') rest.push(argv[++i]);
	}
	const opt = leseOptionen(rest, {});
	const env: Record<string, string> = {};
	if (opt.strict) env.ELEMENTLISTE_STRICT = '1';
	if (opt.abnahme) env.ELEMENTLISTE_ABNAHME = '1';
	if (opt.scope) env.ELEMENTLISTE_SCOPE = opt.scope;
	if (sprache !== null) env.ELEMENTLISTE_SPRACHE = leseSprache({ ELEMENTLISTE_SPRACHE: sprache });
	return env;
}

/** Nur GZ_AUTH_USER/GZ_AUTH_PASS aus dem Text einer .env-Datei (Anführungszeichen entfernt). */
export function loginAusEnvText(text: string): { GZ_AUTH_USER?: string; GZ_AUTH_PASS?: string } {
	const out: { GZ_AUTH_USER?: string; GZ_AUTH_PASS?: string } = {};
	for (const zeile of text.split('\n')) {
		const m = zeile.match(/^\s*(?:export\s+)?(GZ_AUTH_USER|GZ_AUTH_PASS)\s*=\s*(.*?)\s*$/);
		if (m) out[m[1] as 'GZ_AUTH_USER' | 'GZ_AUTH_PASS'] = m[2].replace(/^(["'])(.*)\1$/, '$2');
	}
	return out;
}
