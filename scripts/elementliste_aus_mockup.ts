// Issue #2913 (Epic #2791) — Elementliste aus dem Mockup „Hub Wetter & Zustellung“ (Fassung 3).
// Spec: docs/specs/modules/einstellungen_neu_neustart_adr_waechter_elementliste.md (AC-9 bis AC-12).
//
// Das Mockup baut seine Oberfläche erst per Script; das statische HTML enthält die Elemente nicht.
// Darum rendert Playwright die Datei per file:// und stellt jede Kombination her:
//   Kontext (Trip, Orte) × Zustand (normal, lädt, Ladefehler, Konto mit Lücken)
//   × Reiter (Wetter, Zustellung, Etappen bzw. Orte) × Kanal-Segment (E-Mail, Telegram, SMS,
//   Premium-SMS, 3-Tages-Ausblick, bei Orte zusätzlich Stundenverlauf)
// dazu die reinen Script-Zustände (Grenzen bearbeiten = openEdit, Vorlagen-Auswahl = pickerOpen,
// Speichern-Dialog = saveOpen, Kebab-Bestätigung = kebabConfirm, Test-Menü). Die Zustandsvariablen
// liegen im Mockup in einer Closure (IIFE) und sind von außen nicht erreichbar; sie werden deshalb
// über dieselben Klicks hergestellt, die auch ein Mensch macht (data-ctx, data-zst, data-tab,
// data-seg, data-edit, data-picker, data-save, data-k).
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
export const STANDARD_MOCKUP = join(REPO, 'docs/context/einstellungen_neu/seiten/mockup-hub-fassung3.html');
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
};
export type Elementliste = { schema: number; mockup: string; mockup_hash: string; elemente: ListenEintrag[] };
export type Katalog = { de: Record<string, string>; en: Record<string, string> };
export type EnErgebnis = { i18n_key: string | null; text_en: string | null; muster: string | null; luecke: boolean };

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
const katalogIndex = new WeakMap<Katalog, { exakt: Map<string, string>; muster: MusterEintrag[] }>();

function index(katalog: Katalog) {
	const vorhanden = katalogIndex.get(katalog);
	if (vorhanden) return vorhanden;
	const exakt = new Map<string, string>();
	const muster: MusterEintrag[] = [];
	for (const key of Object.keys(katalog.de).sort()) {
		const en = katalog.en[key];
		if (typeof en !== 'string' || en.trim() === '') continue; // ohne EN-Wert kein Treffer
		const d = norm(katalog.de[key]);
		if (!exakt.has(d)) exakt.set(d, key);
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
	const idx = { exakt, muster };
	katalogIndex.set(katalog, idx);
	return idx;
}

/**
 * EN für einen Mockup-Text: exakter Treffer im DE-Katalog → EN desselben Schlüssels;
 * sonst Musterabgleich (Platzhalter) → EN mit eingesetzten Werten; sonst Lücke (nichts erfunden).
 */
export function ermittleEn(textDe: string, katalog: Katalog): EnErgebnis {
	const t = norm(textDe);
	const idx = index(katalog);
	const key = idx.exakt.get(t);
	if (key) return { i18n_key: key, text_en: katalog.en[key], muster: null, luecke: false };
	for (const m of idx.muster) {
		// Der Wortlaut des Musters muss den Text tragen (mind. die Hälfte), sonst wäre der Treffer
		// zufällig („{count} Etappe“ passte auf „°C · vor der Etappe“) und das EN erfunden.
		if (m.literal * 2 < t.length) continue;
		const treffer = t.match(m.re);
		if (!treffer || treffer.slice(1).some((w) => w.length > 40)) continue;
		const werte: Record<string, string> = {};
		m.namen.forEach((n, i) => (werte[n] = treffer[i + 1]));
		const en = katalog.en[m.key].replace(PLATZHALTER, (_: string, n: string) => werte[n] ?? `{${n}}`);
		return { i18n_key: m.key, text_en: en, muster: m.de, luecke: false };
	}
	return { i18n_key: null, text_en: null, muster: null, luecke: true };
}

// ------------------------------------------------------------------ Auslesen im Browser

type Roh = { abschnitt: string; rolle: string; text: string };
type AusleseArg = { wurzeln: string[]; abschnitt: string | null; nur: string | null; ohne: string | null };

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
		if (top.querySelector('[data-seg="channel"]')) return 'kanal-inhalt';
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
		if (el.closest('.pill')) return 'status';
		if (el.closest('h1,h2,h3')) return 'ueberschrift';
		if (el.closest('summary')) return 'aufklapper';
		if (el.closest('[role="menuitem"]')) return 'menuepunkt';
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
				if (arg.ohne && abschnitt === arg.ohne) continue;
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

type Rohgruppe = { ctx: string; reiter: string; zustand: string; segment: string | null; roh: Roh[] };

function baueElemente(gruppen: Rohgruppe[], katalog: Katalog): ListenEintrag[] {
	const elemente: ListenEintrag[] = [];
	for (const g of gruppen) {
		const abschnitte = new Map<string, Roh[]>();
		for (const r of g.roh) abschnitte.set(r.abschnitt, [...(abschnitte.get(r.abschnitt) ?? []), r]);
		for (const [abschnitt, liste] of abschnitte) {
			// Werte-Varianten (Texte, die sich nur in Zahlen unterscheiden) → EIN Element mit Muster
			const varianten = new Map<string, Set<string>>();
			for (const r of liste) {
				const k = zahlNeutral(r.text);
				varianten.set(k, (varianten.get(k) ?? new Set<string>()).add(r.text));
			}
			const zusammengefasst = new Set<string>();
			const vorkommen = new Map<string, number>();
			let ordnung = 0;
			for (const r of liste) {
				const k = zahlNeutral(r.text);
				if ((varianten.get(k)?.size ?? 0) > 1) {
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
				const en = ermittleEn(r.text, katalog);
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
					luecke: en.luecke
				});
			}
		}
	}
	return elemente;
}

// ------------------------------------------------------------------ Steuerung des Mockups

const KONTEXTE = ['trip', 'orte'];
const ZUSTAENDE = ['normal', 'laedt', 'fehler', 'luecken'];
const KANAL_SEGMENTE = ['E-Mail', 'Telegram', 'SMS', 'Premium-SMS', '3-Tages-Ausblick'];
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
		const lies = (wurzeln: string[], extra: { abschnitt?: string; nur?: string; ohne?: string } = {}) =>
			page.evaluate(ausleseImBrowser, {
				wurzeln,
				abschnitt: extra.abschnitt ?? null,
				nur: extra.nur ?? null,
				ohne: extra.ohne ?? null
			});
		const aufklappen = () =>
			page.evaluate(() => {
				document.querySelectorAll('#content details').forEach((d) => ((d as HTMLDetailsElement).open = true));
			}, null);
		const da = async (sel: string) => (await page.locator(sel).count()) > 0;

		for (const ctx of KONTEXTE) {
			const segmente = ctx === 'orte' ? [...KANAL_SEGMENTE, 'Stundenverlauf'] : KANAL_SEGMENTE;
			const zweiter = ctx === 'trip' ? 'etappen' : 'orte';
			for (const zustand of ZUSTAENDE) {
				// --- Wetter: Kopf, Reiterleiste, Inhalt ohne die Kanal-Karte
				await frisch(ctx, zustand);
				await aufklappen();
				const wetter: Roh[] = [...(await lies(KOPF)), ...(await lies(['#content'], { ohne: 'kanal-inhalt' }))];

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

				// --- Wetter: Karte „Inhalt je Kanal und Fläche“ je Kanal-Segment
				await frisch(ctx, zustand);
				if (await da('[data-seg="channel"]')) {
					for (const seg of segmente) {
						await page.click(`[data-seg="channel"][data-v="${seg}"]`);
						await aufklappen();
						gruppen.push({ ctx, reiter: 'wetter', zustand, segment: seg, roh: await lies(['#content'], { nur: 'kanal-inhalt' }) });
					}
				}

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

if (process.argv[1] && pathToFileURL(resolve(process.argv[1])).href === import.meta.url) {
	const liste = await erzeugeElementliste({ mockupPfad: STANDARD_MOCKUP, messagesDir: STANDARD_MESSAGES });
	writeFileSync(STANDARD_LISTE, alsJson(liste));
	const luecken = liste.elemente.filter((e) => e.luecke).length;
	console.log(`${relative(REPO, STANDARD_LISTE)}: ${liste.elemente.length} Elemente, ${luecken} EN-Lücken, ${liste.mockup_hash}`);
}
