// Issue #2913 (Epic #2791) — Elementliste aus dem Mockup „Hub Wetter & Zustellung“ (Fassung 4, #3122).
// Spec: docs/specs/modules/einstellungen_neu_neustart_adr_waechter_elementliste.md (AC-9 bis AC-12).
// Fassung 4 (ADR-0124): Die Karte „Inhalt je Kanal und Fläche“ mit ihren Kanal-Segmenten gibt es nicht mehr.
// An ihrer Stelle steht die Tabelle „Was steht wo“ (Abschnitt was-steht-wo); sie wird mit dem Reiter Wetter
// in einem Zug gelesen. Das Feld `segment` bleibt im Schema und ist immer null.
//
// Das Mockup baut seine Oberfläche erst per Script; das statische HTML enthält die Elemente nicht.
// Darum rendert Playwright die Datei per file:// und stellt jede Kombination her:
//   Kontext (Trip, Orte) × Zustand (normal, lädt, Ladefehler, Konto mit Lücken)
//   × Reiter (Wetter, Zustellung, Etappen bzw. Orte, Übersicht)
// Vom Reiter Übersicht nur der Bereichskopf (Titel, Erklärsatz); die Inhaltskarte ist Mockup-Notiz (#2969).
// Der Ein-Ort-Kontext des Mockups (data-ctx="ort1") wird nicht gelesen: Der Staging-Abgleich kennt nur
// die Kontexte trip und orte.
// dazu die reinen Script-Zustände (Grenzen bearbeiten = openEdit, Vorlagen-Auswahl = pickerOpen,
// Speichern-Dialog = saveOpen, Kebab-Bestätigung = kebabConfirm, Test-Menü, Vorlagen-Abweichung = devs>0
// nach Abwahl einer Metrik per data-rm, #3251). Die Zustandsvariablen
// liegen im Mockup in einer Closure (IIFE) und sind von außen nicht erreichbar; sie werden deshalb
// über dieselben Klicks hergestellt, die auch ein Mensch macht (data-ctx, data-zst, data-tab,
// data-edit, data-picker, data-save, data-k).
// Ausgeschlossen: Mockup-Rahmen (.frame), Rückmeldungsbereich (.fb, data-fb), Marken (.tag).
//
// Aufruf (schreibt docs/context/einstellungen_neu/elementliste.json):
//   cd frontend && node --experimental-strip-types ../scripts/elementliste_aus_mockup.ts
//
// Playwright wird erst in erzeugeElementliste dynamisch geladen (aus frontend/node_modules), damit
// der Hash-Check ohne Browser importieren kann (elementliste_aktuell.test.ts).
import { createHash } from 'node:crypto';
import { readFileSync, readdirSync, writeFileSync } from 'node:fs';
import { createRequire } from 'node:module';
import { join, relative, dirname, resolve } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

const HIER = dirname(fileURLToPath(import.meta.url));
const REPO = resolve(HIER, '..');
export const STANDARD_MOCKUP = join(REPO, 'docs/context/einstellungen_neu/seiten/mockup-hub-fassung4.html');
export const STANDARD_LISTE = join(REPO, 'docs/context/einstellungen_neu/elementliste.json');
export const STANDARD_MESSAGES = join(REPO, 'frontend/src/lib/i18n/messages');

export type ListenEintrag = {
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
	/** #2968 Regel c: nur gesetzt (true), wenn EN = DE-Muster gilt. */
	sprachneutral?: boolean;
	/** #2968 Regel f: nur gesetzt bei mehrdeutigem EN (alle Kandidaten, sortiert). */
	text_en_alternativen?: string[];
};
export type Elementliste = { schema: number; mockup: string; mockup_hash: string; elemente: ListenEintrag[] };
export type Katalog = { de: Record<string, string>; en: Record<string, string> };
export type EnErgebnis = {
	i18n_key: string | null;
	text_en: string | null;
	muster: string | null;
	luecke: boolean;
	/** #2968 Regel c: EN = DE-Muster (Zahlen, Einheiten, Kurz-/Protokoll-Token, Eigennamen aus der Liste). */
	sprachneutral?: boolean;
	/** #2968 Regel f: alle EN-Kandidaten, wenn der DE-Text unter mehreren Schlüsseln mit verschiedenem EN steht. */
	text_en_alternativen?: string[];
};
/**
 * #2968 Regel d: bekannte Werte aus den Schnappschüssen unter docs/context/einstellungen_neu/daten/.
 * metriknamen = DE-Metriknamen (label_de, alert_label); token = Kurz-/Protokoll-Token (sms_code,
 * sms_multi_symbols, kuerzel, compact_label, col_label); eigennamen = `text` aus eigennamen.json.
 */
export type Bekannte = { metriknamen: string[]; token: string[]; eigennamen: string[] };

// ------------------------------------------------------------------ Hash (ohne Browser)

/** 'sha256:<hex>' über die Datei-Bytes. */
export function mockupHash(inhalt: string | Buffer): string {
	return 'sha256:' + createHash('sha256').update(inhalt).digest('hex');
}

/** Vergleicht den Hash in der Elementliste mit dem Hash der Mockup-Datei. */
export function pruefeHashAktuell(mockupPfad: string, jsonPfad: string): { ok: boolean; erwartet: string; ist: string } {
	const erwartet = String(JSON.parse(readFileSync(jsonPfad, 'utf8')).mockup_hash ?? '');
	const ist = mockupHash(readFileSync(mockupPfad));
	return { ok: erwartet === ist, erwartet, ist };
}

// ------------------------------------------------------------------ Katalog und EN

function ladeSprache(dir: string): Record<string, string> {
	const out: Record<string, string> = {};
	for (const f of readdirSync(dir).filter((n) => n.endsWith('.json')).sort()) {
		const daten = JSON.parse(readFileSync(join(dir, f), 'utf8')) as Record<string, unknown>;
		for (const [k, v] of Object.entries(daten)) if (typeof v === 'string') out[k] = v;
	}
	return out;
}

/** Lädt den flachen i18n-Katalog (alle Bereichsdateien je Sprache). */
export function ladeKatalog(messagesDir: string): Katalog {
	return { de: ladeSprache(join(messagesDir, 'de')), en: ladeSprache(join(messagesDir, 'en')) };
}

const norm = (s: string) => s.replace(/\s+/g, ' ').trim();
const PLATZHALTER = /\{([a-zA-Z_]\w*)\}/g;

type MusterEintrag = { key: string; de: string; re: RegExp; namen: string[]; literal: number };
const katalogIndex = new WeakMap<Katalog, { exakt: Map<string, string>; enJeDe: Map<string, string[]>; muster: MusterEintrag[] }>();

function index(katalog: Katalog) {
	const vorhanden = katalogIndex.get(katalog);
	if (vorhanden) return vorhanden;
	const exakt = new Map<string, string>();
	const enJeDe = new Map<string, string[]>(); // #2968 Regel f: alle EN-Kandidaten je DE-Text
	const muster: MusterEintrag[] = [];
	for (const key of Object.keys(katalog.de).sort()) {
		const en = katalog.en[key];
		if (typeof en !== 'string' || en.trim() === '') continue; // ohne EN-Wert kein Treffer
		const d = norm(katalog.de[key]);
		if (!exakt.has(d)) exakt.set(d, key);
		const kandidaten = enJeDe.get(d) ?? [];
		if (!kandidaten.includes(en)) enJeDe.set(d, [...kandidaten, en].sort());
		const namen = [...d.matchAll(PLATZHALTER)].map((m) => m[1]);
		if (namen.length === 0) continue;
		const teile = d.split(PLATZHALTER).filter((_, i) => i % 2 === 0);
		const literal = teile.join('');
		// Nur Muster mit echtem Wortlaut (mind. 4 Zeichen, ein Buchstabe) — sonst passte „{name}“ auf alles.
		if (literal.replace(/\s/g, '').length < 4 || !/\p{L}/u.test(literal)) continue;
		// EN muss mit den DE-Platzhaltern füllbar sein, sonst würde EN erfunden.
		const enNamen = [...en.matchAll(PLATZHALTER)].map((m) => m[1]);
		if (enNamen.some((n) => !namen.includes(n))) continue;
		const quelle = teile.map((t) => t.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')).join('(.+?)');
		muster.push({ key, de: d, re: new RegExp('^' + quelle + '$', 'u'), namen, literal: literal.length });
	}
	muster.sort((a, b) => b.literal - a.literal || (a.key < b.key ? -1 : 1));
	const idx = { exakt, enJeDe, muster };
	katalogIndex.set(katalog, idx);
	return idx;
}

// ------------------------------------------------------------------ #2968: bekannte Werte (Schnappschüsse)

export const STANDARD_DATEN = join(REPO, 'docs/context/einstellungen_neu/daten');
const bekannteCache = new Map<string, Bekannte>();

type MetrikSchnappschuss = {
	label_de: string;
	alert_label: string;
	compact_label: string;
	col_label: string;
	sms_code: string;
	sms_multi_symbols: string[];
	kuerzel: string[];
};

/**
 * #2968 Regel d: liest daten/metriknamen.json (Drift-Test tests/test_2968_metriknamen_schnappschuss.py gegen
 * src/app/metric_catalog.py) und daten/eigennamen.json. Kein Python-Aufruf zur Laufzeit.
 */
export function ladeBekannte(datenDir: string = STANDARD_DATEN): Bekannte {
	const vorhanden = bekannteCache.get(datenDir);
	if (vorhanden) return vorhanden;
	const lies = (datei: string) => JSON.parse(readFileSync(join(datenDir, datei), 'utf8'));
	const metriken = (lies('metriknamen.json') as { metriken: MetrikSchnappschuss[] }).metriken;
	const eigen = (lies('eigennamen.json') as { eigennamen: Array<{ text: string }> }).eigennamen;
	const liste = (xs: string[]) => [...new Set(xs.map((x) => norm(String(x ?? ''))).filter((x) => x !== ''))];
	const b: Bekannte = {
		metriknamen: liste(metriken.flatMap((m) => [m.label_de, m.alert_label])),
		token: liste(metriken.flatMap((m) => [m.sms_code, m.compact_label, m.col_label, ...m.sms_multi_symbols, ...m.kuerzel])),
		eigennamen: liste(eigen.map((e) => e.text))
	};
	bekannteCache.set(datenDir, b);
	return b;
}

// ------------------------------------------------------------------ #2968: Zuordner (Regeln a bis d)

const ZAHL_WERT = '[-−+]?\\d+(?:[.,:]\\d+)*';
const EINHEIT = '(?:°C|km/h|mm|%|m|h)';
/** Zahl, Einheit oder Zahl mit Einheit („30“, „-15“, „°C“, „1200 m“, „60%“). */
const ZAHL_ODER_EINHEIT = new RegExp(`^(?:${ZAHL_WERT}|(?:${ZAHL_WERT} ?)?${EINHEIT})$`, 'u');
/** Rekursionstiefe der Regel a: äußeres Muster = 1, Muster als Wert darin = 2. */
const MAX_TIEFE = 2;
const TRENNER = ' · ';
const luecke = (): EnErgebnis => ({ i18n_key: null, text_en: null, muster: null, luecke: true });

/**
 * Regel c: Text ohne Buchstaben, Zahl/Einheit, Eigenname der Liste oder bekanntes Token, dem nur Zahlen,
 * Zeichen oder eine Zahl mit Einheit folgen („N10“, „SnowL 1820“, „VS-“, „W 20-38@15“, „G 51 km/h“).
 */
function istSprachneutral(t: string, b: Bekannte): boolean {
	if (!/\p{L}/u.test(t) || ZAHL_ODER_EINHEIT.test(t) || b.eigennamen.includes(t)) return true;
	return b.token.some((k) => {
		if (!t.startsWith(k)) return false;
		const rest = t.slice(k.length);
		return !/\p{L}/u.test(rest) || (/^ ?\d/.test(rest) && ZAHL_ODER_EINHEIT.test(rest.trim()));
	});
}

/** Regel c: EN = DE-Muster (Zahlen als {zahl}), kein Katalogschlüssel. */
function neutral(t: string): EnErgebnis {
	const muster = t.replace(ZAHL, '{zahl}');
	return { i18n_key: null, text_en: muster, muster: muster === t ? null : muster, luecke: false, sprachneutral: true };
}

/** Regel a: ein eingesetzter Wert ist aufgelöst (Katalogwert, Metrikname, Zahl/Einheit, Muster bis Tiefe 2). */
function wertAufgeloest(w: string, katalog: Katalog, b: Bekannte, tiefe: number): boolean {
	const v = norm(w);
	if (index(katalog).exakt.has(v) || b.metriknamen.includes(v) || ZAHL_ODER_EINHEIT.test(v)) return true;
	return tiefe < MAX_TIEFE && musterAufgeloest(v, katalog, b, tiefe + 1) !== null;
}

/**
 * #3192: Plural-Schlüssel (`x.one`/`x.other`, implizites `{count}`) passen nur zur Zahl im Text. Im DE-Katalog
 * steht dieselbe Form teils unter `.one` und `.other` („{count} Metriken“); ohne diese Prüfung gewann der
 * alphabetisch erste Schlüssel `.one` und das EN-Soll wurde Einzahl („12 Metriken“ ⇒ „{count} metric“).
 * `.one` gilt nur für den Wert 1, `.other` nur für andere Zahlen; ein nicht-numerischer Wert lässt beide zu.
 */
export function pluralPasst(key: string, namen: string[], werte: string[]): boolean {
	const form = key.endsWith('.one') ? 'one' : key.endsWith('.other') ? 'other' : null;
	const i = namen.indexOf('count');
	if (form === null || i < 0) return true;
	const w = norm(werte[i] ?? '');
	if (!/^\d+$/.test(w)) return true;
	return form === 'one' ? Number(w) === 1 : Number(w) !== 1;
}

/** Regel a: erstes Katalogmuster, dessen eingesetzte Werte alle aufgelöst sind (ohne Wortlaut-Hälfte). */
function musterAufgeloest(t: string, katalog: Katalog, b: Bekannte, tiefe: number): MusterEintrag | null {
	for (const m of index(katalog).muster) {
		const treffer = t.match(m.re);
		if (!treffer || !pluralPasst(m.key, m.namen, treffer.slice(1))) continue;
		if (treffer.slice(1).every((w) => wertAufgeloest(w, katalog, b, tiefe))) return m;
	}
	return null;
}

/**
 * Muster für den ganzen Text: Regel a (alle Werte aufgelöst) oder die alte Wortlaut-Hälfte. Der Wortlaut muss
 * dort den Text tragen (mind. die Hälfte, Werte ≤ 40 Zeichen), sonst wäre der Treffer zufällig
 * („{count} Etappe“ passte auf „°C · vor der Etappe“) und das EN erfunden.
 */
function musterTreffer(t: string, katalog: Katalog, b: Bekannte): MusterEintrag | null {
	for (const m of index(katalog).muster) {
		const treffer = t.match(m.re);
		if (!treffer || !pluralPasst(m.key, m.namen, treffer.slice(1))) continue;
		const werte = treffer.slice(1);
		if (werte.every((w) => wertAufgeloest(w, katalog, b, 1))) return m;
		if (m.literal * 2 >= t.length && werte.every((w) => w.length <= 40)) return m;
	}
	return null;
}

/** Regel b: ein Segment ist aufgelöst über Katalog exakt, Muster nach Regel a oder sprachneutral (Regel c). */
function segmentEn(s: string, katalog: Katalog, b: Bekannte): EnErgebnis | null {
	const key = index(katalog).exakt.get(s);
	if (key) return { i18n_key: key, text_en: katalog.en[key], muster: s, luecke: false };
	const m = musterAufgeloest(s, katalog, b, 1);
	if (m) return { i18n_key: m.key, text_en: katalog.en[m.key], muster: m.de, luecke: false };
	if (istSprachneutral(s, b)) return { ...neutral(s), muster: s.replace(ZAHL, '{zahl}') };
	return null;
}

/**
 * Regel b: Text mit „ · “ (oder führendem „· “) segmentweise; aufgelöst nur, wenn jedes Segment aufgelöst ist.
 * null = kein Segmenttext. EN = Segment-EN mit „ · “ verbunden, führendes „· “ bleibt vorn.
 */
function segmenteEn(t: string, katalog: Katalog, b: Bekannte): EnErgebnis | null {
	const fuehrend = t.startsWith('· ');
	const teile = (fuehrend ? t.slice(2) : t).split(TRENNER).map(norm);
	if (!fuehrend && teile.length < 2) return null;
	const erg = teile.map((s) => segmentEn(s, katalog, b));
	if (erg.some((e) => e === null || !e.text_en)) return luecke();
	const fertig = erg as EnErgebnis[];
	if (fertig.every((e) => e.sprachneutral)) return neutral(t);
	const vorn = fuehrend ? '· ' : '';
	const muster = vorn + fertig.map((e) => e.muster).join(TRENNER);
	// Ohne Platzhalter ist das Muster fester Text (wie ein exakter Treffer): kein Muster.
	return { i18n_key: null, text_en: vorn + fertig.map((e) => e.text_en).join(TRENNER), muster: /\{\w+\}/.test(muster) ? muster : null, luecke: false };
}

/**
 * EN für einen Mockup-Text, nichts erfunden: exakter Treffer im DE-Katalog → EN desselben Schlüssels;
 * sonst Katalogmuster (Regel a bzw. Wortlaut-Hälfte) → EN-Muster MIT Platzhaltern; sonst sprachneutral
 * (Regel c) → EN = DE-Muster; sonst Segmente an „ · “ (Regel b); sonst Lücke.
 * #2913 Fix-Loop 2 (C5): die eingesetzten Werte stammen aus dem deutschen Mockup (z. B. Metriknamen);
 * sie in den EN-Text zu kopieren, hieße Deutsch als Englisch zu erwarten. Der Abgleich liest
 * Platzhalter als „beliebiger Wert“.
 */
export function ermittleEn(textDe: string, katalog: Katalog, bekannte: Bekannte = ladeBekannte()): EnErgebnis {
	const t = norm(textDe);
	const exakt = exaktEn(t, katalog);
	if (exakt) return exakt;
	const m = musterTreffer(t, katalog, bekannte);
	if (m) return { i18n_key: m.key, text_en: katalog.en[m.key], muster: m.de, luecke: false };
	if (istSprachneutral(t, bekannte)) return neutral(t);
	const bisher = zeichenEn(t, katalog) ?? segmenteEn(t, katalog, bekannte);
	if (bisher && !bisher.luecke) return bisher;
	// #3194 Regel g: erst nach a–f und nur für bisherige Lücken — ältere Zuordnungen bleiben unverändert.
	// #3154: danach der Metrikname aus dem Schnappschuss (Zeilennamen der Tabelle „Was steht wo“).
	return zusammengesetztEn(t, katalog) ?? metrikNameEn(t) ?? luecke();
}

const metrikNamenCache = new Map<string, Map<string, string>>();

/**
 * #3154 (AC-10): DE→EN der Metriknamen aus dem Schnappschuss daten/metrik_namen.json (label_de/label_en aus
 * src/app/metric_catalog.py, wie kuerzel_bedeutung.json #3258). Live steht der Zeilenname in der Sprache des
 * Nutzers aus dem Server-Katalog. Kein Python-Aufruf zur Laufzeit.
 */
export function ladeMetrikNamen(datenDir: string = STANDARD_DATEN): Map<string, string> {
	const vorhanden = metrikNamenCache.get(datenDir);
	if (vorhanden) return vorhanden;
	const roh = JSON.parse(readFileSync(join(datenDir, 'metrik_namen.json'), 'utf8')) as { namen: Array<{ de: string; en: string }> };
	const m = new Map(roh.namen.filter((n) => n.de && n.en).map((n) => [norm(n.de), n.en] as [string, string]));
	metrikNamenCache.set(datenDir, m);
	return m;
}

/** #3154: EN eines Metriknamens aus dem Schnappschuss; null = kein Metrikname. */
export function metrikNameEn(textDe: string, namen: Map<string, string> = ladeMetrikNamen()): EnErgebnis | null {
	const en = namen.get(norm(textDe));
	return en ? { i18n_key: null, text_en: en, muster: null, luecke: false } : null;
}

/**
 * #3194 Regel g „zusammengesetzt“: Texte, die die App aus mehreren Katalogschlüsseln zusammensetzt
 * (GrenzenEditor: Titel `_1`+`_2` ohne Fuge, Hinweis + „Abweichend …“; VorlageKarte: Rumpf `ersetzt_*` + `bleibt`).
 * Je Zeile eine benannte Schlüsselfolge mit Fuge. Neue Folgen nur hier eintragen, nie EN-Text.
 */
export type ZusammengesetztZeile = { name: string; schluessel: string[]; fuge: string };

export const ZUSAMMENGESETZT: readonly ZusammengesetztZeile[] = [
	{ name: 'A1 Grenzen-Titel oben', schluessel: ['wetter.grenzen.oben_1', 'wetter.grenzen.oben_2'], fuge: '' },
	{ name: 'A2 Grenzen-Titel unten', schluessel: ['wetter.grenzen.unten_1', 'wetter.grenzen.unten_2'], fuge: '' },
	{ name: 'B Grünhinweis + abweichend', schluessel: ['wetter.grenzen.hinweis', 'wetter.grenzen.abweichend'], fuge: ' ' },
	{ name: 'C Gewitter-Hinweis + abweichend', schluessel: ['wetter.gewitter.keins_gruen', 'wetter.grenzen.abweichend'], fuge: ' ' },
	{ name: 'D1 Rumpf Trip', schluessel: ['wetter.vorlage.ersetzt_route', 'wetter.vorlage.bleibt'], fuge: ' ' },
	{ name: 'D2 Rumpf Orte', schluessel: ['wetter.vorlage.ersetzt_vergleich', 'wetter.vorlage.bleibt'], fuge: ' ' },
	// #3154: SMS-Hinweis der Karte „Was steht wo“ (wasStehtWoAnsicht.ts smsAus: Kürzungssatz + „Zieh nach oben …“).
	{ name: 'E1 SMS gekürzt Trip', schluessel: ['wetter.wsw.sms_passt_nicht.other', 'wetter.wsw.sms.hochziehen'], fuge: ' ' },
	{ name: 'E2 SMS gekürzt Trip, eine', schluessel: ['wetter.wsw.sms_passt_nicht.one', 'wetter.wsw.sms.hochziehen'], fuge: ' ' },
	{ name: 'E3 SMS gekürzt Orte', schluessel: ['wetter.wsw.sms_orte_passt_nicht.other', 'wetter.wsw.sms.hochziehen'], fuge: ' ' },
	{ name: 'E4 SMS gekürzt Orte, eine', schluessel: ['wetter.wsw.sms_orte_passt_nicht.one', 'wetter.wsw.sms.hochziehen'], fuge: ' ' }
];

const REGEX_ZEICHEN = /[.*+?^${}()|[\]\\]/g;

/**
 * Regel g: Treffer nur, wenn der Text exakt der mit der Fuge verketteten DE-Folge entspricht (Platzhalter
 * wie `{vorlage}` als beliebiger Wert) und JEDER Schlüssel in DE und EN existiert. EN = EN-Werte mit derselben
 * Fuge, Platzhalter bleiben stehen. `i18n_key` = erster Schlüssel, `muster` = DE-Gesamtmuster (nur mit Platzhalter).
 */
export function zusammengesetztEn(textDe: string, katalog: Katalog): EnErgebnis | null {
	const t = norm(textDe);
	for (const zeile of ZUSAMMENGESETZT) {
		const deWerte = zeile.schluessel.map((k) => katalog.de[k]);
		const enWerte = zeile.schluessel.map((k) => katalog.en[k]);
		if (deWerte.some((w) => typeof w !== 'string' || w.trim() === '')) continue;
		if (enWerte.some((w) => typeof w !== 'string' || w.trim() === '')) continue;
		const deMuster = deWerte.join(zeile.fuge);
		const namen = [...deMuster.matchAll(PLATZHALTER)].map((m) => m[1]);
		const enMuster = enWerte.join(zeile.fuge);
		if ([...enMuster.matchAll(PLATZHALTER)].some((m) => !namen.includes(m[1]))) continue; // EN nicht füllbar
		const quelle = deMuster
			.split(PLATZHALTER)
			.filter((_, i) => i % 2 === 0)
			.map((s) => s.replace(REGEX_ZEICHEN, '\\$&'))
			.join('(.+?)');
		if (!new RegExp('^' + quelle + '$', 'u').test(t)) continue;
		return { i18n_key: zeile.schluessel[0], text_en: enMuster, muster: namen.length > 0 ? deMuster : null, luecke: false };
	}
	return null;
}

/**
 * Exakter Katalogtreffer; #2968 Regel f: steht der DE-Text unter mehreren Schlüsseln mit verschiedenem EN
 * („Fertig“ ⇒ Done, Finished), trägt das Ergebnis alle Kandidaten — nicht nur den ersten Schlüssel.
 */
function exaktEn(t: string, katalog: Katalog, zeichen = ''): EnErgebnis | null {
	const idx = index(katalog);
	const key = idx.exakt.get(t);
	if (!key) return null;
	const kandidaten = idx.enJeDe.get(t) ?? [];
	const r: EnErgebnis = { i18n_key: key, text_en: katalog.en[key] + zeichen, muster: null, luecke: false };
	if (kandidaten.length > 1) r.text_en_alternativen = kandidaten.map((k) => k + zeichen);
	return r;
}

/**
 * #2968 Regel e: „<Katalogwert> <Zeichen>“ („gelb >“, „rot <“) — die App setzt Grenzen-Beschriftungen so
 * zusammen. Zeichen = weder Buchstabe noch Ziffer; der Wert muss als Ganzes exakt im Katalog stehen.
 * EN = EN des Werts mit demselben Zeichen.
 */
function zeichenEn(t: string, katalog: Katalog): EnErgebnis | null {
	const m = t.match(/^(.+) ([^\p{L}\p{N}\s]+)$/u);
	return m ? exaktEn(m[1], katalog, ' ' + m[2]) : null;
}

/**
 * #3007 (Listenzeile): Titel- und Lagezeilen der Listen in den Reitern Etappen und Orte sind Kontodaten in
 * einem Katalogmuster ohne Mindest-Wortlaut („E{n} · {start} → {ziel}“, „{name}“, „{gruppe} · {hoehe} m“).
 * Wie bei `chipEn` macht der Ort (Reiter + Abschnitt `liste`) den Treffer eindeutig. Greift nur, wenn der
 * allgemeine Zuordner keinen Katalogschlüssel gefunden hat (Lücke oder sprachneutral); EN bleibt das Muster.
 */
const LISTENZEILE: Record<string, string[]> = {
	etappen: ['trip.hub.etappe_titel'],
	orte: ['vergleich.hub.ort_gruppe_hoehe', 'vergleich.hub.ort_name']
};

export function listenzeileEn(reiter: string, abschnitt: string, textDe: string, katalog: Katalog, allgemein: EnErgebnis): EnErgebnis {
	if (abschnitt !== 'liste' || allgemein.i18n_key || !Object.hasOwn(LISTENZEILE, reiter)) return allgemein;
	const t = norm(textDe);
	for (const key of LISTENZEILE[reiter]) {
		const de = katalog.de[key];
		const en = katalog.en[key];
		if (typeof de !== 'string' || typeof en !== 'string' || !en.trim()) continue;
		const teile = norm(de).split(PLATZHALTER).filter((_, i) => i % 2 === 0);
		const re = new RegExp('^' + teile.map((x) => x.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')).join('(.+?)') + '$', 'u');
		if (re.test(t)) return { i18n_key: key, text_en: en, muster: norm(de), luecke: false };
	}
	return allgemein;
}

/**
 * #3251 (Fix-Loop 1, F001): Im Mockup ist „▾ 1 Abweichung“ EIN Textknoten, live (VorlageKarte.svelte) sind
 * Auswahlpfeil „▾ “ und Stand („1 Abweichung“, Katalog wetter.vorlage.abweichungen.*) eigene Textblöcke. Der
 * Abschnitt vorlage-abweichung führt darum den Stand ohne Pfeil; der Pfeil ist live bereits als „zusätzlich“
 * belegt (Besitzer #2913). Andere Texte bleiben unverändert.
 */
export function ohneAuswahlpfeil(r: Roh): Roh {
	return { ...r, text: r.text.replace(/^▾\s+/u, '') };
}

/**
 * #3251 (Fix-Loop 2, F001): Die Abweichungszahl der Vorlagenkarte hängt live am Prüf-Datensatz mit Abweichung
 * (gemessen 21.11.: Trip „14 Abweichungen“, Orte „8 Abweichungen“), im Mockup ist sie „1 Abweichung“. Der
 * Soll-Eintrag führt darum die Zahl als Platzhalter in der Mehrzahl-Form des Katalogs (wie „{count} Metriken“):
 * `.one` → `.other`, Muster und EN-Soll aus dem Katalog. Nur im Abschnitt vorlage-abweichung; text_de und ID
 * bleiben der Mockup-Text.
 */
export function abweichungsZahlAlsMuster(abschnitt: string, en: EnErgebnis, katalog: Katalog): EnErgebnis {
	if (abschnitt !== 'vorlage-abweichung' || !en.i18n_key?.endsWith('.one')) return en;
	const mehrzahl = en.i18n_key.slice(0, -'.one'.length) + '.other';
	if (!katalog.de[mehrzahl] || !katalog.en[mehrzahl]) return en;
	return { ...en, i18n_key: mehrzahl, muster: katalog.de[mehrzahl], text_en: katalog.en[mehrzahl], luecke: false };
}

/** #3258: Katalog-Präfix der festen Legenden-Einträge (Kürzel erklärt). */
export const LEGENDE_PRAEFIX = 'wetter.wsw.legende.';

const bedeutungCache = new Map<string, Map<string, string>>();

/**
 * #3258 (Fix-Loop 1, F002): DE→EN der Kürzel-Bedeutungen aus dem Schnappschuss daten/kuerzel_bedeutung.json
 * (Server-Katalog kuerzel_bedeutung_de/en und vergleich.sms.ort_nummer; Drift-Test
 * tests/test_3258_kuerzel_bedeutung_schnappschuss.py). Kein Python-Aufruf zur Laufzeit.
 */
export function ladeKuerzelBedeutungen(datenDir: string = STANDARD_DATEN): Map<string, string> {
	const vorhanden = bedeutungCache.get(datenDir);
	if (vorhanden) return vorhanden;
	const roh = JSON.parse(readFileSync(join(datenDir, 'kuerzel_bedeutung.json'), 'utf8')) as { bedeutungen: Array<{ de: string; en: string }> };
	const m = new Map(roh.bedeutungen.map((p) => [norm(p.de), p.en] as [string, string]));
	bedeutungCache.set(datenDir, m);
	return m;
}

/**
 * #3258: EN der Legende „Kürzel erklärt“. Kürzel sind Protokoll-Token und werden nie übersetzt (ADR-0104):
 * EN = DE-Muster (sprachneutral). Eine Bedeutung trägt EN aus dem Katalog `wetter.wsw.legende.*` (feste
 * Einträge), sonst aus dem Server-Katalog (`ladeKuerzelBedeutungen`, Metrik-Bedeutungen und O1); nie aus
 * einem zufälligen Treffer im übrigen Frontend-Katalog („Böen“ → „Wind gusts“, live „gusts“). Ohne Treffer
 * Lücke. null = keine Legenden-Rolle.
 */
export function legendeEn(rolle: string, textDe: string, katalog: Katalog, bedeutungen: Map<string, string> = ladeKuerzelBedeutungen()): EnErgebnis | null {
	if (rolle === 'kuerzel') return neutral(norm(textDe));
	if (rolle !== 'bedeutung') return null;
	const en = ermittleEn(textDe, katalog);
	if (en.i18n_key?.startsWith(LEGENDE_PRAEFIX)) return en;
	const server = bedeutungen.get(norm(textDe));
	return server ? { i18n_key: null, text_en: server, muster: null, luecke: false } : luecke();
}

/** Katalogschlüssel der „+ Metrik“-Chips in „Nicht im Briefing“. */
export const CHIP_SCHLUESSEL = 'wetter.nicht_im_briefing.hinzufuegen';

/**
 * #2913 Fix-Loop 2 (C5): Chip „+ Name“ (Rolle chip) → Muster „+ {metrik}“ aus dem Katalog. Das Muster ist
 * zu kurz für den allgemeinen Musterabgleich (Mindest-Wortlaut), die Chip-Rolle macht den Treffer eindeutig.
 * Welche Metriken Chips sind, sind Kontodaten; der Abgleich prüft Präfix und Vorhandensein.
 */
export function chipEn(rolle: string, textDe: string, katalog: Katalog): EnErgebnis | null {
	const de = katalog.de[CHIP_SCHLUESSEL];
	const en = katalog.en[CHIP_SCHLUESSEL];
	if (rolle !== 'chip' || typeof de !== 'string' || typeof en !== 'string' || !en.trim()) return null;
	const praefix = de.split('{')[0];
	if (!praefix.trim() || !norm(textDe).startsWith(praefix) || norm(textDe).length <= praefix.length) return null;
	return { i18n_key: CHIP_SCHLUESSEL, text_en: en, muster: de, luecke: false };
}

// ------------------------------------------------------------------ Auslesen im Browser

export type Roh = { abschnitt: string; rolle: string; text: string };
type AusleseArg = { wurzeln: string[]; abschnitt: string | null; nur: string | null };

/**
 * Läuft im Browser (page.evaluate): liest sichtbare Texte und Bedienelemente unter den Wurzeln aus.
 * Abschnitte werden aus den stabilen Haken des Mockups abgeleitet (data-*, Klassen), nicht aus Positionen.
 */
function ausleseImBrowser(arg: AusleseArg): Roh[] {
	const SKIP = '.tag,.frame,.fb,[data-fb],script,style,[aria-hidden="true"]';
	const hatInhalt = (s: string) => /[\p{L}\p{N}]/u.test(s);
	const n = (s: string | null) => String(s || '').replace(/\s+/g, ' ').trim();
	function abschnittVon(el: Element): string {
		if (arg.abschnitt) return arg.abschnitt;
		if (el.closest('#testMenu')) return 'test-menue';
		if (el.closest('#kebabMenu')) return el.closest('.confirm') ? 'kebab-bestaetigung' : 'kebab-menue';
		if (el.closest('.crumbs') || el.closest('#head')) return 'kopf';
		if (el.closest('#tabs')) return 'reiterleiste';
		const content = document.getElementById('content') as HTMLElement;
		let top: Element | null = el;
		while (top && top.parentElement !== content) top = top.parentElement;
		if (!top) return 'sonstiges';
		const row = el.closest('.mr') as HTMLElement | null;
		if (row && row.querySelector('.edit') && (el.closest('.edit') || el.closest('[data-edit]'))) return 'grenzen-' + row.dataset.row;
		if (top.classList.contains('sectionh')) return 'abschnittskopf';
		if (top.classList.contains('vorlage')) {
			if (el.closest('.vmenu .confirm')) return 'vorlage-bestaetigung';
			if (el.closest('.vmenu')) return 'vorlage-auswahl';
			return 'vorlage';
		}
		if (top.querySelector('.dialog')) return el.closest('.err') ? 'vorlage-speichern-fehler' : 'vorlage-speichern';
		if (top.matches('[data-abschnitt="was-steht-wo"]')) return 'was-steht-wo';
		if (top.querySelector('.mgroup,[data-seg="alarmall"],.more')) return 'metriken';
		if (top.querySelector('[data-sw="official"]')) return 'warnungen-radar';
		if (top.getAttribute('aria-busy') === 'true') return 'laden';
		if (top.classList.contains('warnbox')) return 'warnung';
		if (top.classList.contains('two')) return 'briefing-zeiten';
		if (top.querySelector('table.kt')) return 'kanaele';
		if (top.querySelector('[data-sw="quiet"]')) return 'stille-stunden';
		if (top.querySelector('[data-seg="laufzeit"],[data-tab]')) return 'laufzeit';
		if (top.querySelector('[data-seg="fort"]')) return 'tempo';
		if (top.querySelector('details.adv')) return 'anpassen';
		if (top.querySelector('.lrow')) return 'liste';
		return 'block-' + Array.prototype.indexOf.call(content.children, top);
	}
	function rolleVon(el: Element): string {
		const b = el.closest('button');
		if (b) {
			const r = b.getAttribute('role');
			if (r === 'radio') return 'option';
			if (r === 'menuitem') return 'menuepunkt';
			if (b.classList.contains('tab')) return 'reiter';
			if (b.classList.contains('chip')) return 'chip';
			return 'knopf';
		}
		// #3154: Beispieltext einer Zelle bzw. SMS-Beispielzeile (Mockup-Haken data-beispiel).
		if (el.closest('[data-beispiel]')) return 'beispiel';
		if (el.closest('.pill')) return 'status';
		if (el.closest('h1,h2,h3')) return 'ueberschrift';
		if (el.closest('summary')) return 'aufklapper';
		if (el.closest('[role="menuitem"]')) return 'menuepunkt';
		// #3258: Legende „Kürzel erklärt“ (Definitionsliste): Kürzel und Bedeutung.
		if (el.closest('dt')) return 'kuerzel';
		if (el.closest('dd')) return 'bedeutung';
		if (el.closest('[role="alert"],.warnbox,.err')) return 'hinweis';
		if (el.closest('label,th,.eyebrow,.gh,.vg,.sub')) return 'beschriftung';
		if (el.closest('.kz')) return 'kuerzel';
		return 'text';
	}
	const sichtbar = (el: Element) => el.checkVisibility();
	const out: Roh[] = [];
	const gesehen = new Set<Element>();
	for (const sel of arg.wurzeln) {
		for (const wurzel of Array.from(document.querySelectorAll(sel))) {
			for (const el of [wurzel, ...Array.from(wurzel.querySelectorAll('*'))]) {
				if (gesehen.has(el)) continue;
				gesehen.add(el);
				if (el.closest(SKIP) || !sichtbar(el)) continue;
				const abschnitt = abschnittVon(el);
				if (arg.nur && abschnitt !== arg.nur) continue;
				if (el instanceof HTMLInputElement) {
					const t = n(el.getAttribute('aria-label') || el.getAttribute('placeholder') || (el.type === 'checkbox' ? '' : el.value));
					if (t && hatInhalt(t)) out.push({ abschnitt, rolle: 'eingabe', text: t });
					continue;
				}
				if (el.getAttribute('role') === 'switch') {
					const t = n(el.getAttribute('aria-label'));
					if (t) out.push({ abschnitt, rolle: 'schalter', text: t });
					continue;
				}
				let eigen = '';
				for (const k of Array.from(el.childNodes)) if (k.nodeType === 3) eigen += k.nodeValue;
				eigen = n(eigen);
				if (el.tagName === 'BUTTON' && !hatInhalt(eigen) && el.getAttribute('aria-label')) {
					out.push({ abschnitt, rolle: rolleVon(el), text: n(el.getAttribute('aria-label')) });
					continue;
				}
				if (hatInhalt(eigen)) out.push({ abschnitt, rolle: rolleVon(el), text: eigen });
			}
		}
	}
	return out;
}

// ------------------------------------------------------------------ Zusammenbau

const ZAHL = /\d+([.,]\d+)?/g;
const zahlNeutral = (t: string) => t.replace(ZAHL, '#');

/** #3154: Roh-Rolle eines Beispieltexts (Zelle der Tabelle „Was steht wo“, SMS-Beispielzeile). */
export const BEISPIEL = 'beispiel';

/**
 * #3154 (AC-7): Beispieltexte hängen am festen Beispiel-Datensatz der App (`placements_beispiel.py`), nicht
 * am Mockup; geprüft wird nur, dass an der Stelle ein Beispiel steht. Muster `{wert}` (beliebiger Text außer
 * einem Zellennamen, siehe Abgleich), sprachneutral, ohne Katalogschlüssel.
 */
function beispielEn(): EnErgebnis {
	return { i18n_key: null, text_en: '{wert}', muster: '{wert}', luecke: false, sprachneutral: true };
}

export type Rohgruppe = { ctx: string; reiter: string; zustand: string; segment: string | null; roh: Roh[] };

/**
 * Roh-Gruppen (aus dem Browser) → Listeneinträge, ohne Browser (reine Funktion, #2968 F002 testbar):
 * EN je Element über `chipEn` (Chip-Rolle), sonst `ermittleEn` mit Sonderfall `listenzeileEn` (#3007).
 */
export function baueElemente(gruppen: Rohgruppe[], katalog: Katalog): ListenEintrag[] {
	const elemente: ListenEintrag[] = [];
	for (const g of gruppen) {
		const abschnitte = new Map<string, Roh[]>();
		for (const r of g.roh) abschnitte.set(r.abschnitt, [...(abschnitte.get(r.abschnitt) ?? []), r]);
		for (const [abschnitt, liste] of abschnitte) {
			// Werte-Varianten (Texte, die sich nur in Zahlen unterscheiden) → EIN Element mit Muster
			const varianten = new Map<string, Set<string>>();
			for (const r of liste) {
				if (r.rolle === BEISPIEL) continue; // #3154: Beispiele werden nie zusammengefasst
				const k = zahlNeutral(r.text);
				varianten.set(k, (varianten.get(k) ?? new Set<string>()).add(r.text));
			}
			const zusammengefasst = new Set<string>();
			const vorkommen = new Map<string, number>();
			let ordnung = 0;
			for (const r of liste) {
				const k = zahlNeutral(r.text);
				if (r.rolle !== BEISPIEL && (varianten.get(k)?.size ?? 0) > 1) {
					if (zusammengefasst.has(k)) continue;
					zusammengefasst.add(k);
				}
				ordnung += 1;
				const identitaet = [g.ctx, g.reiter, g.zustand, g.segment ?? '-', abschnitt, r.rolle, k].join('|');
				const nr = (vorkommen.get(identitaet) ?? 0) + 1;
				vorkommen.set(identitaet, nr);
				const id =
					[g.ctx, g.reiter, g.zustand, g.segment ?? '-', abschnitt].join('.') +
					'.' +
					createHash('sha256').update(identitaet + '|' + nr).digest('hex').slice(0, 10);
				const en = r.rolle === BEISPIEL ? beispielEn() : abweichungsZahlAlsMuster(abschnitt, chipEn(r.rolle, r.text, katalog) ?? legendeEn(r.rolle, r.text, katalog) ?? listenzeileEn(g.reiter, abschnitt, r.text, katalog, ermittleEn(r.text, katalog)), katalog);
				// Muster: aus dem Katalog (Platzhalter) oder, ohne Katalogtreffer, Zahlen als {zahl}.
				// Ein exakter Katalogtreffer ist fester Text (z. B. „3-Tages-Ausblick“), kein Muster.
				const zahlMuster = !en.i18n_key && /\d/.test(r.text) ? r.text.replace(ZAHL, '{zahl}') : null;
				elemente.push({
					id,
					ctx: g.ctx,
					reiter: g.reiter,
					zustand: g.zustand,
					segment: g.segment,
					abschnitt,
					ordnung,
					rolle: r.rolle,
					text_de: r.text,
					muster: en.muster ?? zahlMuster,
					i18n_key: en.i18n_key,
					text_en: en.text_en,
					luecke: en.luecke,
					...(en.sprachneutral ? { sprachneutral: true } : {}),
					...(en.text_en_alternativen ? { text_en_alternativen: en.text_en_alternativen } : {})
				});
			}
		}
	}
	return elemente;
}

// ------------------------------------------------------------------ Steuerung des Mockups

const KONTEXTE = ['trip', 'orte'];
const ZUSTAENDE = ['normal', 'laedt', 'fehler', 'luecken'];
const KOPF = ['.crumbs #path', '.crumbs #kebabBtn', '.crumbs #testBtn', '#head', '#tabs'];

// Minimaler Ausschnitt der Playwright-API, den der Generator braucht (Typen ohne Import).
type Seite = {
	goto(url: string): Promise<unknown>;
	click(sel: string): Promise<void>;
	evaluate<R, A>(fn: (a: A) => R, arg: A): Promise<R>;
	locator(sel: string): { count(): Promise<number> };
	$$eval<R>(sel: string, fn: (els: Element[]) => R): Promise<R>;
};
type Browser = {
	newContext(o: object): Promise<{
		route(muster: RegExp, fn: (r: { abort(): Promise<void> }) => unknown): Promise<void>;
		newPage(): Promise<Seite>;
		close(): Promise<void>;
	}>;
	close(): Promise<void>;
};

async function ladeChromium(): Promise<{ launch(o: object): Promise<Browser> }> {
	const req = createRequire(join(REPO, 'frontend', 'package.json'));
	type Chromium = { launch(o: object): Promise<Browser> };
	const pw = (await import(pathToFileURL(req.resolve('@playwright/test')).href)) as {
		chromium?: Chromium;
		default?: { chromium: Chromium };
	};
	// CommonJS-Einstieg: je nach Lader liegt chromium direkt oder unter default.
	return (pw.chromium ?? pw.default?.chromium) as Chromium;
}

/** Rendert das Mockup und erzeugt die Elementliste (deterministisch, ohne Zeitstempel). */
export async function erzeugeElementliste(opt: { mockupPfad: string; messagesDir: string }): Promise<Elementliste> {
	const katalog = ladeKatalog(opt.messagesDir);
	const url = pathToFileURL(opt.mockupPfad).href;
	const browser = await (await ladeChromium()).launch({ headless: true });
	const gruppen: Rohgruppe[] = [];
	try {
		const context = await browser.newContext({ viewport: { width: 1280, height: 900 }, locale: 'de-DE' });
		// Nur die Datei selbst; Schriften aus dem Netz werden nicht geladen (deterministisch, offline).
		await context.route(/^https?:/, (route) => route.abort());
		const page = await context.newPage();

		const frisch = async (ctx: string, zustand: string) => {
			await page.goto(url);
			if (ctx !== 'trip') await page.click(`.frame [data-ctx="${ctx}"]`);
			if (zustand !== 'normal') await page.click(`.frame [data-zst="${zustand}"]`);
		};
		const lies = (wurzeln: string[], extra: { abschnitt?: string; nur?: string } = {}) =>
			page.evaluate(ausleseImBrowser, {
				wurzeln,
				abschnitt: extra.abschnitt ?? null,
				nur: extra.nur ?? null
			});
		const aufklappen = () =>
			page.evaluate(() => {
				document.querySelectorAll('#content details').forEach((d) => ((d as HTMLDetailsElement).open = true));
			}, null);
		const da = async (sel: string) => (await page.locator(sel).count()) > 0;

		for (const ctx of KONTEXTE) {
			const zweiter = ctx === 'trip' ? 'etappen' : 'orte';
			for (const zustand of ZUSTAENDE) {
				// --- Wetter: Kopf, Reiterleiste, Inhalt samt Tabelle „Was steht wo“
				await frisch(ctx, zustand);
				await aufklappen();
				const wetter: Roh[] = [...(await lies(KOPF)), ...(await lies(['#content']))];

				// Script-Zustände im Wetter-Reiter (nur wo der Zustand die Elemente zeigt)
				await frisch(ctx, zustand);
				if (await da('[data-edit]')) {
					const ids = await page.$$eval('[data-edit]', (bs) => bs.map((b) => (b as HTMLElement).dataset.edit as string));
					for (const id of ids) {
						await page.click(`[data-edit="${id}"]`);
						wetter.push(...(await lies([`.mr[data-row="${id}"]`], { nur: `grenzen-${id}` })));
					}
				}
				await frisch(ctx, zustand);
				if (await da('[data-picker]')) {
					await page.click('[data-picker]');
					wetter.push(...(await lies(['.vmenu'], { nur: 'vorlage-auswahl' })));
					await page.click('.vmenu [data-vorlage]:not(.cur)');
					wetter.push(...(await lies(['.vmenu .confirm'], { nur: 'vorlage-bestaetigung' })));
				}
				// #3251: Abweichungszustand der Vorlagenkarte (devs>0) — eine Metrik abwählen, dann Picker-Zahl
				// und Zurücksetzen-Zeile lesen. Nur Zustand normal (Bedienzustand, kein globaler Seiten-Zustand).
				await frisch(ctx, zustand);
				if (zustand === 'normal' && (await da('[data-rm]'))) {
					await page.click('[data-rm]');
					wetter.push(...(await lies(['[data-picker] small', '[data-reset]'], { abschnitt: 'vorlage-abweichung' })).map(ohneAuswahlpfeil));
				}
				await frisch(ctx, zustand);
				if (await da('[data-save]')) {
					await page.click('[data-save]');
					wetter.push(...(await lies(['#content'], { nur: 'vorlage-speichern' })));
					await page.click('[data-savego]');
					wetter.push(...(await lies(['#content'], { nur: 'vorlage-speichern-fehler' })));
				}
				// Menüs im Kopf (Test schicken, Weitere Aktionen samt Bestätigungen)
				await frisch(ctx, zustand);
				await page.click('#testBtn');
				wetter.push(...(await lies(['#testMenu'])));
				await frisch(ctx, zustand);
				await page.click('#kebabBtn');
				wetter.push(...(await lies(['#kebabMenu'])));
				for (const k of ['archivieren', 'loeschen']) {
					await page.click(`#kebabMenu [data-k="${k}"]`);
					wetter.push(...(await lies(['#kebabMenu .confirm'], { abschnitt: `kebab-bestaetigung-${k}` })));
					await page.click('#kebabMenu [data-kno]');
				}
				gruppen.push({ ctx, reiter: 'wetter', zustand, segment: null, roh: wetter });

				// --- Zustellung
				await frisch(ctx, zustand);
				await page.click('#tabs [data-tab="zustellung"]');
				await aufklappen();
				gruppen.push({ ctx, reiter: 'zustellung', zustand, segment: null, roh: await lies(['#content']) });

				// --- Etappen bzw. Orte
				await frisch(ctx, zustand);
				await page.click(`#tabs [data-tab="${zweiter}"]`);
				await aufklappen();
				gruppen.push({ ctx, reiter: zweiter, zustand, segment: null, roh: await lies(['#content']) });

				// --- Übersicht: nur der Bereichskopf ist Soll. Die Karte „Im Mockup nicht ausgearbeitet.“ ist
				// Mockup-Notiz (viewUebersicht, Inhalt „unverändert“), kein Produkttext (#2969).
				await frisch(ctx, zustand);
				await page.click('#tabs [data-tab="uebersicht"]');
				gruppen.push({ ctx, reiter: 'uebersicht', zustand, segment: null, roh: await lies(['#content'], { nur: 'abschnittskopf' }) });
			}
		}
		await context.close();
	} finally {
		await browser.close();
	}
	return {
		schema: 1,
		mockup: relative(REPO, opt.mockupPfad).split('\\').join('/'),
		mockup_hash: mockupHash(readFileSync(opt.mockupPfad)),
		elemente: baueElemente(gruppen, katalog)
	};
}

/** Eine Zeile je Element: diff-freundlich und trotzdem gültiges JSON. */
export function alsJson(liste: Elementliste): string {
	return (
		'{\n' +
		`"schema": ${liste.schema},\n` +
		`"mockup": ${JSON.stringify(liste.mockup)},\n` +
		`"mockup_hash": ${JSON.stringify(liste.mockup_hash)},\n` +
		'"elemente": [\n' +
		liste.elemente.map((e) => JSON.stringify(e)).join(',\n') +
		'\n]\n}\n'
	);
}

// ------------------------------------------------------------------ #2968 (AC-10): Lücken je Grund

export const STANDARD_BESITZER = join(REPO, 'docs/context/einstellungen_neu/elementliste_besitzer.json');
type BesitzerRoh = { art: string; id?: string; ctx?: string; reiter?: string; abschnitt?: string; grund: string; verweis: string };

/** Klasse einer Restlücke aus dem Grund ihres Besitzers (nur für die Ausgabe). */
export function lueckenKlasse(b: BesitzerRoh | undefined): string {
	if (!b) return 'ohne Besitzer';
	const g = b.grund;
	if (g.startsWith('EN-Lücke (Zusammensetzung im Code)')) return 'Zusammensetzung im Code (kein Katalogmuster)';
	if (/Mockup-Beispieldaten|Prüfkonto|Kontodaten/.test(g)) return 'Kontodaten/Eigennamen ohne Listeneintrag';
	if (/noch nicht gebaut|neu gebaut|fehlen noch|braucht persistente/.test(g)) return 'ungebautes Pendant';
	return 'Mockup≠App-Abweichung';
}

/**
 * #2968 (AC-10): verbleibende EN-Lücken je Grund (Klasse) und Besitzer-Verweis; Besitzer wie im Abgleich
 * (Element-ID vor Abschnitt). Rückgabe absteigend nach Anzahl, eine Zeile je Klasse und Verweis.
 */
export function lueckenJeGrund(elemente: ListenEintrag[], besitzerJson: string): Array<{ klasse: string; verweis: string; anzahl: number }> {
	const besitzer = (JSON.parse(besitzerJson) as { besitzer: BesitzerRoh[] }).besitzer;
	const zaehler = new Map<string, { klasse: string; verweis: string; anzahl: number }>();
	for (const e of elemente.filter((x) => x.luecke)) {
		const b =
			besitzer.find((x) => x.art === 'element' && x.id === e.id) ??
			besitzer.find((x) => x.art === 'abschnitt' && x.ctx === e.ctx && x.reiter === e.reiter && x.abschnitt === e.abschnitt);
		const klasse = lueckenKlasse(b);
		const verweis = b?.verweis ?? '—';
		const z = zaehler.get(klasse + '|' + verweis) ?? { klasse, verweis, anzahl: 0 };
		z.anzahl += 1;
		zaehler.set(klasse + '|' + verweis, z);
	}
	return [...zaehler.values()].sort((a, b) => b.anzahl - a.anzahl || (a.klasse + a.verweis < b.klasse + b.verweis ? -1 : 1));
}

if (process.argv[1] && pathToFileURL(resolve(process.argv[1])).href === import.meta.url) {
	const liste = await erzeugeElementliste({ mockupPfad: STANDARD_MOCKUP, messagesDir: STANDARD_MESSAGES });
	writeFileSync(STANDARD_LISTE, alsJson(liste));
	const luecken = liste.elemente.filter((e) => e.luecke).length;
	const neutral = liste.elemente.filter((e) => e.sprachneutral).length;
	console.log(`${relative(REPO, STANDARD_LISTE)}: ${liste.elemente.length} Elemente, ${luecken} EN-Lücken, ${neutral} sprachneutral, ${liste.mockup_hash}`);
	console.log('Verbleibende EN-Lücken je Grund (Besitzer aus elementliste_besitzer.json):');
	for (const z of lueckenJeGrund(liste.elemente, readFileSync(STANDARD_BESITZER, 'utf8'))) {
		console.log(`  ${String(z.anzahl).padStart(4)}  ${z.klasse} · ${z.verweis}`);
	}
}
