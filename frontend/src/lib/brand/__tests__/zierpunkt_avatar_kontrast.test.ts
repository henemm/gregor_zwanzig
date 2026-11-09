// TDD RED — Issue #2896 (Folge aus #2371, Epic #2508): Kontrast Logo-Punkt und Avatar-Initialen.
// Spec docs/specs/modules/fix_2896_kontrast_zierpunkt_avatar.md, AC-4 und AC-5 (Kern-Schicht).
//
// Gemessen wird am GERENDERTEN Markup (echter SSR-Render via svelte/server) bzw. am
// KOMPILIERTEN Komponenten-CSS (svelte/compiler), nie am Quelltext. Token-Hexwerte kommen
// aus app.css; Alpha-Farben werden gegen ihren Grund gemischt (WCAG-Formel).
//
//   AC-4: Wortmarke dark=true — Punkt (rgba, Alpha gemischt) gegen --g-ink >= 4,5:1.
//   AC-5: Wortmarke hell — Punkt gegen --g-paper-deep UND --g-paper >= 4,5:1;
//         BrandUserBadge accent=true — Initialen gegen Avatar-Grund >= 4,5:1;
//         Avatar-CSS von BottomNav (.konto-kreis__avatar) und KontoSheet (.konto__avatar)
//         >= 4,5:1 und beide mit gleichem Grund (ein Muster, AC-3).
//
//   cd frontend && npm test -- src/lib/brand/__tests__/zierpunkt_avatar_kontrast.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { register } from 'node:module';
import { fileURLToPath, pathToFileURL } from 'node:url';
import path from 'node:path';
import { compile } from 'svelte/compiler';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const LIB = path.resolve(HERE, '../..');
const FRONTEND = path.resolve(LIB, '../..');
const base = pathToFileURL(FRONTEND + '/').href;
const hook = (p: string) => register(pathToFileURL(p).href, base);
hook(path.join(FRONTEND, 'test-app-environment-stub-hooks.mjs'));
hook(path.join(FRONTEND, 'test-svelte-ssr-hooks.mjs'));
hook(path.join(LIB, 'components/trip-new/__tests__/ssrRunesHook.mjs'));

const { render } = await import('svelte/server');
const lade = async (rel: string) => (await import(pathToFileURL(path.join(LIB, rel)).href)).default;

const APP_CSS = readFileSync(path.join(FRONTEND, 'src/app.css'), 'utf-8');
const MIN = 4.5;

function token(name: string): string {
	const m = APP_CSS.match(new RegExp(`--${name}:\\s*(#[0-9a-fA-F]{6})\\b`));
	assert.ok(m, `Token --${name} ist in app.css nicht als #rrggbb definiert`);
	return m![1].toLowerCase();
}

type Rgb = [number, number, number];
function hexZuRgb(hex: string): Rgb {
	return [0, 1, 2].map((i) => parseInt(hex.slice(1 + i * 2, 3 + i * 2), 16)) as Rgb;
}
/** Löst eine CSS-Farbe (var(--g-…), #rrggbb, rgba(...)) gegen den Grund zu einer deckenden RGB-Farbe auf. */
function deckend(farbe: string, grund: string): Rgb {
	const f = farbe.trim().toLowerCase();
	const v = f.match(/^var\(--([a-z0-9-]+)\)$/);
	if (v) return hexZuRgb(token(v[1]));
	if (/^#[0-9a-f]{6}$/.test(f)) return hexZuRgb(f);
	if (f === '#fff') return [255, 255, 255];
	const r = f.match(/^rgba?\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*(?:,\s*([\d.]+)\s*)?\)$/);
	assert.ok(r, `Farbe nicht auswertbar: ${farbe}`);
	const a = r![4] === undefined ? 1 : parseFloat(r![4]);
	const g = hexZuRgb(grund);
	return [1, 2, 3].map((i, k) => Math.round(parseInt(r![i], 10) * a + g[k] * (1 - a))) as Rgb;
}
function luminanz([r, g, b]: Rgb): number {
	const k = (c: number) => {
		const s = c / 255;
		return s <= 0.03928 ? s / 12.92 : Math.pow((s + 0.055) / 1.055, 2.4);
	};
	return 0.2126 * k(r) + 0.7152 * k(g) + 0.0722 * k(b);
}
function kontrast(a: Rgb, b: Rgb): number {
	const [h, d] = [luminanz(a), luminanz(b)].sort((x, y) => y - x);
	return (h + 0.05) / (d + 0.05);
}

const ent = (s: string) => s.replace(/&quot;/g, '"').replace(/&#39;/g, "'").replace(/&amp;/g, '&');

/** Farbe des Punkt-Spans der Wortmarke aus dem gerenderten HTML (Span, dessen Text genau "." ist). */
function punktFarben(html: string): string[] {
	const treffer = [...html.matchAll(/<span\b([^>]*)>\.<\/span>/g)];
	return treffer.map((m) => {
		const stil = ent(m[1].match(/style="([^"]*)"/)?.[1] ?? '');
		const c = stil.match(/(?:^|;)\s*color:\s*([^;]+)/);
		assert.ok(c, `Punkt-Span ohne Textfarbe: ${m[0]}`);
		return c![1].trim();
	});
}

async function renderWortmarke(props: Record<string, unknown>): Promise<string> {
	const W = await lade('brand/BrandWordmark.svelte');
	return render(W as never, { props: props as never }).body;
}

describe('AC-4: Wortmarke dunkel — Punkt mindestens 4,5:1 gegen --g-ink', () => {
	for (const icon of ['left', 'none'] as const) {
		test(`icon=${icon}: gemischter Punkt gegen --g-ink`, async () => {
			const html = await renderWortmarke({ dark: true, icon, caption: null });
			const farben = punktFarben(html);
			assert.equal(farben.length, 1, `genau ein Punkt-Span erwartet (icon=${icon})`);
			const grund = token('g-ink');
			const k = kontrast(deckend(farben[0], grund), hexZuRgb(grund));
			assert.ok(k >= MIN, `Punkt dunkel ${farben[0]} auf --g-ink = ${k.toFixed(2)}:1 < ${MIN}`);
		});
	}
	test('Gegenprobe: Alpha 0,45 (Ist-Stand vor #2896) fällt durch', () => {
		const grund = token('g-ink');
		const k = kontrast(deckend('rgba(246,244,238,0.45)', grund), hexZuRgb(grund));
		assert.ok(k < MIN, `Messlogik zu großzügig: 0,45 ergibt ${k.toFixed(2)}`);
	});
});

describe('AC-5: Wortmarke hell — Punkt mindestens 4,5:1 auf --g-paper-deep und --g-paper', () => {
	for (const icon of ['left', 'none'] as const) {
		for (const grundToken of ['g-paper-deep', 'g-paper']) {
			test(`icon=${icon}: Punkt gegen --${grundToken}`, async () => {
				const html = await renderWortmarke({ icon, caption: null });
				const farben = punktFarben(html);
				assert.equal(farben.length, 1, `genau ein Punkt-Span erwartet (icon=${icon})`);
				const grund = token(grundToken);
				const k = kontrast(deckend(farben[0], grund), hexZuRgb(grund));
				assert.ok(k >= MIN, `Punkt hell ${farben[0]} auf --${grundToken} = ${k.toFixed(2)}:1 < ${MIN}`);
			});
		}
	}
	test('Gegenprobe: --g-ink-4 auf --g-paper-deep fällt durch', () => {
		assert.ok(kontrast(hexZuRgb(token('g-ink-4')), hexZuRgb(token('g-paper-deep'))) < MIN);
	});
});

describe('AC-5: BrandUserBadge accent=true — Initialen mindestens 4,5:1', () => {
	test('gerenderte Initialen-Farbe gegen gerenderten Avatar-Grund', async () => {
		const B = await lade('brand/BrandUserBadge.svelte');
		const html = render(B as never, { props: { name: 'Anna Berg', accent: true } as never }).body;
		const m = html.match(/<div\b[^>]*style="([^"]*)"[^>]*>\s*AB\s*<\/div>/);
		assert.ok(m, 'Avatar mit Initialen "AB" nicht im Render gefunden');
		const stil = ent(m![1]);
		const bg = stil.match(/(?:^|;)\s*background:\s*([^;]+)/)?.[1].trim();
		const fg = stil.match(/(?:^|;)\s*color:\s*([^;]+)/)?.[1].trim();
		assert.ok(bg && fg, `Avatar ohne background/color: ${stil}`);
		const grund = deckend(bg!, '#ffffff');
		const k = kontrast(deckend(fg!, '#ffffff'), grund);
		assert.ok(k >= MIN, `Badge ${fg} auf ${bg} = ${k.toFixed(2)}:1 < ${MIN}`);
	});
});

function avatarRegel(datei: string, selektor: string): { bg: string; fg: string } {
	const voll = path.join(LIB, datei);
	const css = compile(readFileSync(voll, 'utf-8'), { generate: 'server', filename: voll }).css?.code ?? '';
	const esc = selektor.replace(/[.]/g, '\\.');
	const m = css.match(new RegExp(`${esc}(?:\\.svelte-[a-z0-9]+)?\\s*\\{([^}]*)\\}`));
	assert.ok(m, `Regel ${selektor} nicht im kompilierten CSS von ${datei}`);
	const bg = m![1].match(/background(?:-color)?:\s*([^;]+)/)?.[1].trim();
	const fg = m![1].match(/(?:^|[;\s])color:\s*([^;]+)/)?.[1].trim();
	assert.ok(bg && fg, `${selektor}: background/color fehlt`);
	return { bg: bg!, fg: fg! };
}

describe('AC-5/AC-3: Avatar-Initialen in BottomNav und KontoSheet mindestens 4,5:1, ein Muster', () => {
	const stellen = [
		{ datei: 'components/ui/sidebar/BottomNav.svelte', sel: '.konto-kreis__avatar' },
		{ datei: 'components/ui/sidebar/KontoSheet.svelte', sel: '.konto__avatar' }
	];
	for (const { datei, sel } of stellen) {
		test(`${sel}: Initialen gegen Avatar-Grund`, () => {
			const { bg, fg } = avatarRegel(datei, sel);
			const grund = deckend(bg, '#ffffff');
			const k = kontrast(deckend(fg, '#ffffff'), grund);
			assert.ok(k >= MIN, `${sel}: ${fg} auf ${bg} = ${k.toFixed(2)}:1 < ${MIN}`);
		});
	}
	test('Konto-Kreis und Konto-Blatt nutzen denselben Avatar-Grund', () => {
		const [a, b] = stellen.map(({ datei, sel }) => avatarRegel(datei, sel));
		assert.equal(a.bg, b.bg);
		assert.equal(a.fg, b.fg);
	});
});
