// TDD RED — Issue #2268 (S1 von #2146, Epic #2138): Lesbarkeit des Footers und
// des Hinweissatzes (Design-Leitprinzip „hoher Kontrast = Lesbarkeit").
//
// Spec: docs/specs/modules/app_footer_rechtstexte.md (AC-11)
//
// MESSUNG STATT DATEI-GREP: Der Test liest die Token-WERTE aus `app.css`,
// rechnet die WCAG-Kontrastformel und stellt fest, WELCHE Farbe der gerenderte
// Footer tatsächlich trägt — aus dem SSR-Markup (Inline-Stil) UND dem mit dem
// echten Svelte-Compiler übersetzten Komponenten-CSS. Wechselt jemand auf
// `--g-ink-4` (2.85:1 auf Weiß), wird der Test rot; ebenso, wenn die Tippfläche
// unter 44 px fällt. Die echte Höhe im Browser misst die Live-Prüfung auf
// Staging (`getBoundingClientRect`).
//
// RED HEUTE: `AppFooter.svelte` existiert nicht.
//
// Pfadregel #1409: Prüfling relativ zu DIESER Datei auflösen.
//
// Ausführen:
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types \
//     --test src/lib/components/shared/__tests__/app_footer_kontrast_und_tippflaeche.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { register } from 'node:module';
import { readFileSync } from 'node:fs';
import { fileURLToPath, pathToFileURL } from 'node:url';
import path from 'node:path';

const HERE = path.dirname(fileURLToPath(import.meta.url));
// __tests__ -> shared -> components -> lib -> src -> frontend
const FRONTEND = path.resolve(HERE, '../../../../..');

register(
	pathToFileURL(path.join(FRONTEND, 'test-svelte-ssr-hooks.mjs')).href,
	pathToFileURL(FRONTEND + '/').href
);

const { render } = await import('svelte/server');
const { compile } = await import('svelte/compiler');

const FOOTER_DATEI = path.join(FRONTEND, 'src/lib/components/shared/AppFooter.svelte');
const APP_CSS = readFileSync(path.join(FRONTEND, 'src/app.css'), 'utf-8');

function token(name: string): string {
	const m = APP_CSS.match(new RegExp(`--${name}:\\s*(#[0-9a-fA-F]{6})\\b`));
	assert.ok(m, `Token --${name} nicht (als #rrggbb) in app.css gefunden`);
	return m[1];
}

function luminanz(hex: string): number {
	const kanal = (i: number) => {
		const c = parseInt(hex.slice(1 + i * 2, 3 + i * 2), 16) / 255;
		return c <= 0.03928 ? c / 12.92 : Math.pow((c + 0.055) / 1.055, 2.4);
	};
	return 0.2126 * kanal(0) + 0.7152 * kanal(1) + 0.0722 * kanal(2);
}

function kontrast(a: string, b: string): number {
	const [hell, dunkel] = [luminanz(a), luminanz(b)].sort((x, y) => y - x);
	return (hell + 0.05) / (dunkel + 0.05);
}

/** Footer-Markup, alle Inline-Stile daraus und das übersetzte Komponenten-CSS. */
async function footerStilquellen(): Promise<{ html: string; stil: string }> {
	const Footer = (await import(pathToFileURL(FOOTER_DATEI).href)).default;
	const html = render(Footer, { props: {} }).body.replace(/<!--[\s\S]*?-->/g, '');
	const inline = [...html.matchAll(/style="([^"]*)"/g)].map((m) => m[1]).join(' ');
	const css = compile(readFileSync(FOOTER_DATEI, 'utf-8'), {
		generate: 'server',
		filename: FOOTER_DATEI
	}).css?.code ?? '';
	return { html, stil: `${inline}\n${css}` };
}

describe('AC-11: Kontrast (WCAG-AA, mindestens 4.5:1)', () => {
	test('Footer-Farbe --g-ink-3 hat auf --g-paper UND auf Weiß mindestens 4.5:1', () => {
		const ink3 = token('g-ink-3');
		assert.ok(kontrast(ink3, token('g-paper')) >= 4.5, 'zu schwach auf --g-paper');
		assert.ok(kontrast(ink3, token('g-card')) >= 4.5, 'zu schwach auf Weiß');
	});

	test('Hinweissatz-Farbe --g-ink-muted hat auf --g-paper mindestens 4.5:1', () => {
		assert.ok(kontrast(token('g-ink-muted'), token('g-paper')) >= 4.5);
	});

	test('der gerenderte Footer nutzt --g-ink-3 als Textfarbe und NIE --g-ink-4', async () => {
		const { stil } = await footerStilquellen();
		assert.match(stil, /color:\s*var\(--g-ink-3\)/, 'Footer-Textfarbe ist nicht --g-ink-3');
		assert.ok(!stil.includes('--g-ink-4'), '--g-ink-4 (2.85:1) im Footer verwendet');
	});
});

describe('AC-11/AC-6: Tippfläche und Verankerung', () => {
	test('jeder Footer-Link ist mindestens 44 px hoch tippbar', async () => {
		const { stil } = await footerStilquellen();
		const m = stil.match(/min-height:\s*(\d+(?:\.\d+)?)px/);
		assert.ok(m, 'keine min-height in Inline-Stil/Komponenten-CSS des Footers');
		assert.ok(Number(m[1]) >= 44, `min-height ${m[1]}px < 44px`);
	});

	// Der 44px-Test oben liest alle Stilquellen zusammen. `min-height` wirkt auf
	// einem reinen Inline-Element aber nicht — ohne display-Wert am <a> selbst ist
	// die Tippfläche unwirksam. Deshalb hier auf den Anker-Stil scopen: ein
	// globaler Match wäre schon vom `display: flex` des <nav> erfüllt.
	test('jeder Footer-Link trägt display UND min-height am selben Element', async () => {
		const { html } = await footerStilquellen();
		const linkStile = [...html.matchAll(/<a\b[^>]*style="([^"]*)"/g)].map((m) => m[1]);
		assert.equal(linkStile.length, 2, 'nicht beide Footer-Links tragen einen Inline-Stil');
		for (const s of linkStile) {
			assert.match(
				s,
				/display:\s*(inline-flex|flex|block)/,
				`kein display-Wert am <a> — min-height wird vom Inline-Element ignoriert: ${s}`
			);
			const m = s.match(/min-height:\s*(\d+(?:\.\d+)?)px/);
			assert.ok(m, `keine min-height am <a>: ${s}`);
			assert.ok(Number(m[1]) >= 44, `min-height ${m[1]}px < 44px`);
		}
	});

	test('der Footer ist weder fixed noch sticky', async () => {
		const { stil } = await footerStilquellen();
		assert.ok(!/position:\s*(fixed|sticky)/.test(stil), 'Footer ist fixed/sticky');
	});

	test('der Footer hat genau zwei Links in einer <nav aria-label="Rechtliches">', async () => {
		const { html } = await footerStilquellen();
		assert.match(html, /<footer\b/);
		assert.match(html, /<nav\b[^>]*aria-label="Rechtliches"/);
		assert.equal((html.match(/<a\b/g) ?? []).length, 2);
	});
});
