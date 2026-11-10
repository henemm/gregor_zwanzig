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
// die CLI-Flags --strict/--scope/--sprache übersetzt der Starter scripts/elementliste_abgleich.ts.
import { mkdirSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';
import { assertNotProdBaseURL } from './prodUrlGuard.ts';

export type Status = 'gefunden' | 'abweichend' | 'nicht_pruefbar';
export type Ergebnis = { status: Status; grund?: string; ist?: string };

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
};
export type Bericht = { eintraege: BerichtEintrag[]; zaehler: Record<Status, number> };

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

/** Bericht über ALLE übergebenen Elemente; fehlendes Ergebnis ⇒ nicht_pruefbar mit Grund. */
export function baueBericht(elemente: ListenElement[], ergebnisse: Map<string, Ergebnis>): Bericht {
	const zaehler: Record<Status, number> = { gefunden: 0, abweichend: 0, nicht_pruefbar: 0 };
	const eintraege = elemente.map((e): BerichtEintrag => {
		const erg: Ergebnis = ergebnisse.get(e.id) ?? { status: 'nicht_pruefbar', grund: OHNE_ERGEBNIS };
		if (erg.status === 'nicht_pruefbar' && !(erg.grund && erg.grund.trim())) {
			throw new Error(`${e.id}: nicht_pruefbar ohne Grund ist nicht erlaubt`);
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
	return { eintraege, zaehler };
}

/** Ohne --strict immer 0; mit --strict ≠ 0, sobald etwas abweicht oder nicht prüfbar ist. */
export function exitCode(bericht: Bericht, opt: { strict: boolean }): number {
	if (!opt.strict) return 0;
	return bericht.zaehler.abweichend + bericht.zaehler.nicht_pruefbar > 0 ? 1 : 0;
}

const zelle = (s: string | null | undefined) => String(s ?? '').replace(/\|/g, '\\|').replace(/\n/g, ' ');

export function berichtAlsMarkdown(bericht: Bericht): string {
	const z = bericht.zaehler;
	const zeilen = [
		'# Elementlisten-Abgleich (Staging)',
		'',
		`| gefunden | abweichend | nicht_pruefbar | gesamt |`,
		`|---|---|---|---|`,
		`| ${z.gefunden} | ${z.abweichend} | ${z.nicht_pruefbar} | ${bericht.eintraege.length} |`,
		'',
		'| id | Kontext | Reiter | Zustand | Segment | Abschnitt | Nr. | Text | Status | Grund / Ist |',
		'|---|---|---|---|---|---|---|---|---|---|'
	];
	for (const e of bericht.eintraege) {
		const hinweis = [e.grund, e.ist !== undefined ? `ist: ${e.ist}` : ''].filter(Boolean).join(' · ');
		zeilen.push(
			`| ${zelle(e.id)} | ${zelle(e.ctx)} | ${zelle(e.reiter)} | ${zelle(e.zustand)} | ${zelle(e.segment ?? '–')} | ${zelle(e.abschnitt)} | ${e.ordnung} | ${zelle(e.text_de)} | ${e.status} | ${zelle(hinweis)} |`
		);
	}
	return zeilen.join('\n') + '\n';
}

const WAHR = new Set(['1', 'true', 'ja', 'yes']);

/** `--strict`, `--scope X` bzw. `--scope=X`; ersatzweise ELEMENTLISTE_STRICT / ELEMENTLISTE_SCOPE. */
export function leseOptionen(argv: string[], env: Record<string, string | undefined>): { strict: boolean; scope: string | null } {
	let strict = WAHR.has(String(env.ELEMENTLISTE_STRICT ?? '').toLowerCase());
	let scope: string | null = env.ELEMENTLISTE_SCOPE && env.ELEMENTLISTE_SCOPE.trim() ? env.ELEMENTLISTE_SCOPE.trim() : null;
	for (let i = 0; i < argv.length; i++) {
		const a = argv[i];
		if (a === '--strict') strict = true;
		else if (a === '--scope' && i + 1 < argv.length) scope = argv[++i];
		else if (a.startsWith('--scope=')) scope = a.slice('--scope='.length);
	}
	return { strict, scope };
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
	optionen: { strict: boolean; scope: string | null };
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
export const SCRIPT_ABSCHNITT = /^(grenzen-|vorlage-auswahl|vorlage-bestaetigung|vorlage-speichern|test-menue|kebab-)/;

/** Erwarteter Text als RegExp (DE: Muster bzw. exakt; EN: text_en mit beliebigen Zahlen); null = EN-Lücke. */
export function erwartung(e: ListenElement, sprache: Sprache): RegExp | null {
	if (sprache === 'en') {
		if (e.luecke || !e.text_en) return null;
		return new RegExp('^' + normalisiere(e.text_en).split(/\d+(?:[.,]\d+)?/).map(esc).join('[\\d.,]+') + '$');
	}
	if (e.muster) return new RegExp('^' + musterAlsRegExp(e.muster).source + '$');
	return new RegExp('^' + esc(normalisiere(e.text_de)) + '$');
}

/** Alle Elemente einer Kombination als nicht_pruefbar mit demselben Grund. */
export function alleNichtPruefbar(el: ListenElement[], grund: string): Map<string, Ergebnis> {
	return new Map(el.map((e) => [e.id, { status: 'nicht_pruefbar' as const, grund }]));
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
	let zuletzt = -1;
	for (const e of [...liste].sort((a, b) => a.ordnung - b.ordnung)) {
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

/** Abschluss: jedes Element im Bericht (sonst Fehler), Exit-Entscheid nach Strict. */
export function abschluss(bericht: Bericht, elemente: ListenElement[], opt: { strict: boolean }): { exit: number; meldung: string } {
	if (bericht.eintraege.length !== elemente.length) {
		throw new Error(`Bericht unvollständig: ${bericht.eintraege.length} von ${elemente.length} Elementen`);
	}
	const z = bericht.zaehler;
	const exit = exitCode(bericht, opt);
	return { exit, meldung: `gefunden ${z.gefunden}, abweichend ${z.abweichend}, nicht_pruefbar ${z.nicht_pruefbar}${opt.strict ? ' (strict)' : ''} → Exit ${exit}` };
}

/** Starter: CLI-Flags --strict, --scope <x>, --sprache <de|en> in die Umgebung der Spec übersetzen. */
export function flagsAlsUmgebung(argv: string[]): Record<string, string> {
	const bekannt = new Set(['--strict', '--scope', '--sprache']);
	const rest: string[] = [];
	let sprache: string | null = null;
	for (let i = 0; i < argv.length; i++) {
		const a = argv[i];
		const name = a.split('=')[0];
		if (!bekannt.has(name)) throw new Error(`unbekannte Option „${a}“ (erlaubt: --strict, --scope <reiter[/zustand]>, --sprache <de|en>)`);
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
