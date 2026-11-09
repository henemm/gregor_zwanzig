// TDD RED — Issue #2400 (Epic #2508): vollständiger Dark Mode — Mechanik.
// Spec: docs/specs/modules/fix_2400_dark_mode_vollstaendig.md — AC-4 (Logik), AC-5 (Logik),
// AC-8, AC-10 (Logik).
//
// AC-4/AC-10: Das Inline-Skript im <head> von app.html (bzw. static/offline.html) wird so
// ausgeführt, wie der Browser es vor dem ersten Paint tut: synchron, mit dem echten Markup des
// Kopfes (meta-Elemente aus der Datei gelesen) und einem gesetzten bzw. fehlenden
// `localStorage gz-dark`. Gemessen wird der ZUSTAND danach (Attribut `data-theme`,
// `color-scheme`, `<meta name="theme-color">`) — egal, über welche DOM-API das Skript ihn setzt.
// Die DOM-Umgebung unten ist eine kleine, regelkonforme Nachbildung (Attribute, dataset, style),
// keine Spiegelung der erwarteten Antwort. Den Browser-Nachweis (kein Hell-Blitz im ersten Frame)
// liefert e2e/dark-mode-alle-routen.staging.spec.ts.
//
// AC-8: `dark:`-Klassen werden mit dem echten Tailwind-Compiler und der `@custom-variant dark`
// aus app.css übersetzt; der Selektor muss am Schalter-Attribut hängen, nicht an
// `prefers-color-scheme` (Betriebssystem).
//
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types \
//     --experimental-test-module-mocks --test src/lib/__tests__/dark_mechanik.test.ts
import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { fileURLToPath } from 'node:url';
import vm from 'node:vm';
import { compile } from 'tailwindcss';

const FRONTEND = join(fileURLToPath(new URL('.', import.meta.url)), '..', '..', '..');
const APP_HTML = readFileSync(join(FRONTEND, 'src/app.html'), 'utf-8');
const OFFLINE_HTML = readFileSync(join(FRONTEND, 'static/offline.html'), 'utf-8');
const APP_CSS = readFileSync(join(FRONTEND, 'src/app.css'), 'utf-8');

const HELL_THEME_COLOR = '#f6f4ee';

/** Dunkler Seitengrund aus dem Dark-Block der app.css (Quelle für theme-color dunkel). */
function darkPaper(): string {
	const kopf = /:root\[data-theme=(["'])dark\1\]\s*\{/.exec(APP_CSS);
	assert.ok(kopf, 'app.css hat keinen Dark-Block `:root[data-theme="dark"]`');
	const rest = APP_CSS.slice(kopf!.index);
	const m = rest.match(/--g-paper\s*:\s*(#[0-9a-fA-F]{6})\b/);
	assert.ok(m, 'Dark-Block ohne --g-paper');
	return m![1].toLowerCase();
}

// ─── kleine DOM-Umgebung ──────────────────────────────────────────────────────

const kebab = (s: string) => s.replace(/[A-Z]/g, (c) => '-' + c.toLowerCase());
const camel = (s: string) => s.replace(/-([a-z])/g, (_, c) => c.toUpperCase());

class Element {
	tagName: string;
	attrs = new Map<string, string>();
	children: Element[] = [];
	private props = new Map<string, string>();
	style: Record<string, unknown>;
	dataset: Record<string, string | undefined>;
	classList: { add: (...c: string[]) => void; remove: (...c: string[]) => void; toggle: (c: string, an?: boolean) => boolean; contains: (c: string) => boolean };
	constructor(tag: string, attrs: Record<string, string> = {}) {
		this.tagName = tag.toUpperCase();
		for (const [k, v] of Object.entries(attrs)) this.attrs.set(k, v);
		const props = this.props;
		const stilApi = {
			setProperty: (n: string, v: string) => void props.set(n, String(v)),
			getPropertyValue: (n: string) => props.get(n) ?? '',
			removeProperty: (n: string) => {
				const alt = props.get(n) ?? '';
				props.delete(n);
				return alt;
			}
		};
		this.style = new Proxy(stilApi as Record<string, unknown>, {
			get: (t, p: string) => (p in t ? t[p] : (props.get(kebab(p)) ?? '')),
			set: (_t, p: string, v) => (props.set(kebab(p), String(v)), true)
		});
		const self = this;
		this.dataset = new Proxy({} as Record<string, string | undefined>, {
			get: (_t, p: string) => self.attrs.get('data-' + kebab(p)),
			set: (_t, p: string, v) => (self.attrs.set('data-' + kebab(p), String(v)), true),
			deleteProperty: (_t, p: string) => (self.attrs.delete('data-' + kebab(p)), true)
		});
		const klassen = () => new Set((this.attrs.get('class') ?? '').split(/\s+/).filter(Boolean));
		const schreibe = (s: Set<string>) => this.attrs.set('class', [...s].join(' '));
		this.classList = {
			add: (...c) => schreibe(new Set([...klassen(), ...c])),
			remove: (...c) => {
				const s = klassen();
				c.forEach((x) => s.delete(x));
				schreibe(s);
			},
			toggle: (c, an) => {
				const s = klassen();
				const soll = an ?? !s.has(c);
				if (soll) s.add(c);
				else s.delete(c);
				schreibe(s);
				return soll;
			},
			contains: (c) => klassen().has(c)
		};
	}
	setAttribute(n: string, v: string) {
		this.attrs.set(n.toLowerCase(), String(v));
	}
	getAttribute(n: string) {
		return this.attrs.get(n.toLowerCase()) ?? null;
	}
	hasAttribute(n: string) {
		return this.attrs.has(n.toLowerCase());
	}
	removeAttribute(n: string) {
		this.attrs.delete(n.toLowerCase());
	}
	appendChild(c: Element) {
		this.children.push(c);
		return c;
	}
	get content() {
		return this.getAttribute('content') ?? '';
	}
	set content(v: string) {
		this.setAttribute('content', v);
	}
	get name() {
		return this.getAttribute('name') ?? '';
	}
	set name(v: string) {
		this.setAttribute('name', v);
	}
	get className() {
		return this.getAttribute('class') ?? '';
	}
	set className(v: string) {
		this.setAttribute('class', v);
	}
}

/** Kopf einer HTML-Datei: meta-Elemente (Attribute aus dem Markup) und Inline-Skripte im <head>. */
function kopf(html: string) {
	const head = html.match(/<head[^>]*>([\s\S]*?)<\/head>/i);
	assert.ok(head, 'kein <head>');
	const metas = [...head![1].matchAll(/<meta\b([^>]*?)\/?>/gi)].map((m) => {
		const attrs: Record<string, string> = {};
		for (const a of m[1].matchAll(/([\w-]+)\s*=\s*(["'])(.*?)\2/g)) attrs[a[1].toLowerCase()] = a[3];
		return attrs;
	});
	const skripte = [...head![1].matchAll(/<script\b([^>]*)>([\s\S]*?)<\/script>/gi)]
		.filter((m) => !/\bsrc\s*=/.test(m[1]) && !/type\s*=\s*["']?module/.test(m[1]))
		.map((m) => m[2]);
	return { metas, skripte, headInhalt: head![1] };
}

type Speicher = Record<string, string> | 'gesperrt';
interface Ergebnis {
	theme: string | null;
	colorScheme: string;
	themeColor: string | null;
}

/** Führt die Inline-Skripte des Kopfes aus wie der Browser vor dem ersten Paint. */
function fuehreKopfAus(html: string, speicher: Speicher, osDunkel = false): Ergebnis {
	const { metas, skripte } = kopf(html);
	assert.ok(skripte.length > 0, 'kein Inline-Skript im <head> — data-theme wird erst nach der Hydrierung gesetzt (Hell-Blitz)');
	const root = new Element('html', { lang: 'de' });
	const head = new Element('head');
	for (const a of metas) head.appendChild(new Element('meta', a));
	root.appendChild(head);
	const alleMetas = () => head.children.filter((e) => e.tagName === 'META');
	const passt = (sel: string, e: Element): boolean => {
		const m = sel.trim().match(/^meta\[name\s*=\s*["']?([\w-]+)["']?\]$/i);
		return !!m && e.getAttribute('name') === m[1];
	};
	const document = {
		documentElement: root,
		head,
		querySelector: (sel: string) => alleMetas().find((e) => passt(sel, e)) ?? null,
		querySelectorAll: (sel: string) => alleMetas().filter((e) => passt(sel, e)),
		getElementsByTagName: (t: string) => (t.toLowerCase() === 'meta' ? alleMetas() : []),
		createElement: (t: string) => new Element(t)
	};
	const daten = speicher === 'gesperrt' ? null : new Map(Object.entries(speicher));
	const sperre = () => {
		throw new Error('SecurityError: localStorage nicht verfügbar');
	};
	const localStorage = {
		getItem: (k: string) => (daten ? (daten.get(k) ?? null) : sperre()),
		setItem: (k: string, v: string) => (daten ? void daten.set(k, String(v)) : sperre()),
		removeItem: (k: string) => (daten ? void daten.delete(k) : sperre())
	};
	const matchMedia = (q: string) => ({ matches: /prefers-color-scheme:\s*dark/.test(q) ? osDunkel : false, media: q });
	const window: Record<string, unknown> = { document, localStorage, matchMedia };
	window.window = window;
	const ctx = vm.createContext({ ...window, window, self: window, globalThis: window });
	for (const code of skripte) vm.runInContext(code, ctx);
	const meta = alleMetas().find((e) => e.getAttribute('name') === 'theme-color');
	return {
		theme: root.getAttribute('data-theme'),
		colorScheme: (root.style as unknown as { getPropertyValue: (n: string) => string }).getPropertyValue('color-scheme'),
		themeColor: meta ? (meta.getAttribute('content') ?? '').toLowerCase() : null
	};
}

// ─── Tests ────────────────────────────────────────────────────────────────────

for (const [datei, html] of [
	['app.html', APP_HTML],
	['static/offline.html', OFFLINE_HTML]
] as const) {
	const ac = datei === 'app.html' ? 'AC-4/AC-5' : 'AC-10';
	describe(`${ac}: Kopf-Skript in ${datei} setzt den Modus vor dem ersten Paint`, () => {
		test('gz-dark=1 ⇒ data-theme="dark", color-scheme dark, theme-color = dunkles paper', () => {
			const e = fuehreKopfAus(html, { 'gz-dark': '1' });
			assert.equal(e.theme, 'dark', 'data-theme nicht "dark" — erster Frame wäre hell');
			assert.equal(e.colorScheme, 'dark');
			assert.equal(e.themeColor, darkPaper());
		});
		test('gz-dark=0 ⇒ hell: kein data-theme="dark", theme-color hell', () => {
			const e = fuehreKopfAus(html, { 'gz-dark': '0' });
			assert.notEqual(e.theme, 'dark');
			assert.notEqual(e.colorScheme, 'dark');
			assert.equal(e.themeColor, HELL_THEME_COLOR);
		});
		test('keine gespeicherte Wahl, Betriebssystem dunkel ⇒ hell (Schalter ist einzige Quelle)', () => {
			const e = fuehreKopfAus(html, {}, true);
			assert.notEqual(e.theme, 'dark');
			assert.equal(e.themeColor, HELL_THEME_COLOR);
		});
		test('localStorage gesperrt (privates Fenster) ⇒ kein Fehler, hell', () => {
			let e: Ergebnis | undefined;
			assert.doesNotThrow(() => {
				e = fuehreKopfAus(html, 'gesperrt');
			});
			assert.notEqual(e!.theme, 'dark');
		});
		test('Skript steht im <head> vor den Stilen/dem App-Kopf', () => {
			const { headInhalt } = kopf(html);
			const skript = headInhalt.search(/<script\b(?![^>]*\bsrc=)/i);
			assert.ok(skript >= 0, 'kein Inline-Skript im <head>');
			for (const marke of ['%sveltekit.head%', '<style', '<link rel="stylesheet"']) {
				const i = headInhalt.indexOf(marke);
				if (i >= 0) assert.ok(skript < i, `Skript muss vor ${marke} stehen`);
			}
		});
	});
}

describe('AC-8: dark:-Varianten folgen dem Schalter, nicht dem Betriebssystem', () => {
	/** `@custom-variant dark …` aus app.css (Kurzform mit `;` oder Blockform mit @slot). */
	function darkVariante(): string {
		const i = APP_CSS.search(/@custom-variant\s+dark\b/);
		assert.ok(i >= 0, 'app.css definiert keine `@custom-variant dark` — dark:-Klassen folgen prefers-color-scheme');
		const rest = APP_CSS.slice(i);
		const semi = rest.indexOf(';');
		const auf = rest.indexOf('{');
		if (semi >= 0 && (auf < 0 || semi < auf)) return rest.slice(0, semi + 1);
		let tiefe = 0;
		for (let j = auf; j < rest.length; j++) {
			if (rest[j] === '{') tiefe++;
			else if (rest[j] === '}' && --tiefe === 0) return rest.slice(0, j + 1);
		}
		throw new Error('@custom-variant dark ohne Ende');
	}
	async function baue(klassen: string[]): Promise<string> {
		const css = `${darkVariante()}\n@theme { --color-input: #000; --color-destructive: #f00; }\n@tailwind utilities;`;
		const c = await compile(css, { base: FRONTEND, loadStylesheet: async (id: string) => ({ path: id, content: '', base: FRONTEND }) });
		return c.build(klassen);
	}
	for (const klasse of ['dark:bg-input/30', 'dark:aria-invalid:ring-destructive/40']) {
		test(`${klasse} hängt an data-theme="dark", nicht an prefers-color-scheme`, async () => {
			const out = await baue([klasse]);
			assert.match(out, /data-theme=["']?dark["']?/, `Selektor ohne data-theme:\n${out}`);
			assert.doesNotMatch(out, /prefers-color-scheme/, `dark: folgt weiter dem Betriebssystem:\n${out}`);
		});
	}
});
