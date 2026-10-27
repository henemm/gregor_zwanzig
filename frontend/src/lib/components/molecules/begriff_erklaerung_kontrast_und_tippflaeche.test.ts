// TDD RED — Issue #2521 S1, AC-14 (Spec begriff_erklaerung_infobox.md):
// Lesbarkeit der Infobox und der Sprechblase (Design-Leitprinzip „hoher Kontrast
// = Lesbarkeit“) und Tippflaeche des ⓘ.
//
// Muster: shared/__tests__/app_footer_kontrast_und_tippflaeche.test.ts. Gemessen
// wird nicht „steht ein Token im Quelltext“, sondern fuer das PAAR aus Textfarbe
// und Hintergrund, das die Datei WIRKLICH deklariert (Inline-Stil im Markup und
// uebersetztes Komponenten-CSS), der WCAG-Kontrast mit den Werten aus app.css.
//
// Vertrag an den Implementierer (damit die Messung greift):
//   * Infobox.svelte UND ui/popover/popover-content.svelte deklarieren Textfarbe UND
//     Hintergrund ausdruecklich als `var(--g-…)`-Token, die in app.css als #rrggbb
//     stehen (z. B. color: var(--g-ink-2); background: var(--g-card)).
//   * Kein `--g-ink-4` in einem der drei Bausteine (2.85:1, nur Placeholder/Disabled).
//   * Das ⓘ (BegriffErklaerung.svelte) deklariert `color: var(--g-…)` und traegt am
//     <button> SELBST `display` (flex/inline-flex/block/inline-block/grid) plus
//     Breite UND Hoehe (min-/width, min-/height) von mindestens 24 px — `min-height`
//     wirkt auf einem reinen Inline-Element nicht (Lehre aus dem Footer-Test).
//     @media-Regeln zaehlen nicht (die Tippflaeche gilt auf jedem Viewport).
//   Die echte Groesse im Browser misst frontend/e2e/begriff-erklaerung.spec.ts.
//
// Pfadregel #1409: alles relativ zu DIESER Datei.
//
//   cd frontend && npm test -- src/lib/components/molecules/begriff_erklaerung_kontrast_und_tippflaeche.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { existsSync, readFileSync } from 'node:fs';
import { join } from 'node:path';
import { compile } from 'svelte/compiler';
import { COMPONENTS, FRONTEND, lade, renderKomponente, tagsMitTestid, attribut } from '../shared/__tests__/infoboxSsr.ts';

const APP_CSS = readFileSync(join(FRONTEND, 'src/app.css'), 'utf-8');

function token(name: string): string {
	const m = APP_CSS.match(new RegExp(`--${name}:\\s*(#[0-9a-fA-F]{6})\\b`));
	assert.ok(m, `Token --${name} ist in app.css nicht als #rrggbb definiert (Bausteine duerfen nur solche Tokens als Text-/Hintergrundfarbe nutzen)`);
	return m![1];
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

const DATEIEN = {
	infobox: join(COMPONENTS, 'molecules/Infobox.svelte'),
	ii: join(COMPONENTS, 'molecules/BegriffErklaerung.svelte'),
	popover: join(COMPONENTS, 'ui/popover/popover-content.svelte')
};

/** Quelltext ohne Kommentare + uebersetztes CSS: alle Stilquellen einer Datei. */
function stilquellen(datei: string): { quelle: string; stil: string } {
	assert.ok(existsSync(datei), `${datei} existiert nicht`);
	const quelle = readFileSync(datei, 'utf-8');
	const css = compile(quelle, { generate: 'server', filename: datei }).css?.code ?? '';
	const inline = [...quelle.matchAll(/style="([^"]*)"/g)].map((m) => m[1]).join(' ');
	const klassen = [...quelle.matchAll(/class="([^"]*)"/g)].map((m) => m[1]).join(' ');
	return { quelle: quelle.replace(/<!--[\s\S]*?-->/g, '').replace(/\/\*[\s\S]*?\*\//g, ''), stil: `${inline}\n${css}\n${klassen}` };
}

function tokensFuer(stil: string, eigenschaft: RegExp): string[] {
	const treffer: string[] = [];
	const re = new RegExp(`(?:^|[;{\\s])${eigenschaft.source}\\s*:\\s*var\\(--(g-[a-z0-9-]+)\\)`, 'g');
	let m: RegExpExecArray | null;
	while ((m = re.exec(stil))) treffer.push(m[1]);
	return treffer;
}

describe('AC-14: Kontrast (WCAG-AA, mindestens 4.5:1) — nie --g-ink-4', () => {
	for (const [name, datei] of [
		['Infobox', DATEIEN.infobox],
		['Sprechblase (popover-content)', DATEIEN.popover]
	] as const) {
		test(`${name}: deklarierte Textfarbe auf deklariertem Hintergrund hat mindestens 4.5:1`, () => {
			const { stil } = stilquellen(datei);
			const farben = tokensFuer(stil, /color/);
			const gründe = tokensFuer(stil, /background(?:-color)?/);
			assert.ok(farben.length > 0, `${name}: keine Textfarbe als var(--g-…) deklariert`);
			assert.ok(gründe.length > 0, `${name}: kein Hintergrund als var(--g-…) deklariert`);
			for (const f of farben) {
				for (const b of gründe) {
					const k = kontrast(token(f), token(b));
					assert.ok(k >= 4.5, `${name}: --${f} auf --${b} hat nur ${k.toFixed(2)}:1`);
				}
			}
		});
	}

	test('das ⓘ-Zeichen (--g-…) hat auf Seite (--g-paper) UND Karte (--g-card) mindestens 4.5:1', () => {
		const { stil } = stilquellen(DATEIEN.ii);
		const farben = tokensFuer(stil, /color/);
		assert.ok(farben.length > 0, 'BegriffErklaerung deklariert keine Textfarbe als var(--g-…)');
		for (const f of farben) {
			for (const grund of ['g-paper', 'g-card']) {
				assert.ok(kontrast(token(f), token(grund)) >= 4.5, `--${f} auf --${grund} unter 4.5:1`);
			}
		}
	});

	test('keiner der drei Bausteine verwendet --g-ink-4', () => {
		for (const [name, datei] of Object.entries(DATEIEN)) {
			const { quelle, stil } = stilquellen(datei);
			assert.ok(!quelle.includes('--g-ink-4') && !stil.includes('--g-ink-4'), `${name}: --g-ink-4 (2.85:1) verwendet`);
		}
	});
});

// ── Tippflaeche ─────────────────────────────────────────────────────────────

/** Regeln ohne @media/@supports-Bloecke. */
function ohneAtRegeln(css: string): string {
	let aus = '';
	let tiefe = 0;
	let imAt = false;
	for (let i = 0; i < css.length; i++) {
		const c = css[i];
		if (tiefe === 0 && c === '@') imAt = true;
		if (c === '{') tiefe++;
		if (!imAt) aus += c;
		if (c === '}') {
			tiefe--;
			if (tiefe === 0) imAt = false;
		}
	}
	return aus;
}

function px(stil: string, eigenschaften: string[]): number {
	let best = 0;
	for (const e of eigenschaften) {
		for (const m of stil.matchAll(new RegExp(`(?:^|[;{\\s])${e}\\s*:\\s*(\\d+(?:\\.\\d+)?)px`, 'g'))) best = Math.max(best, Number(m[1]));
	}
	return best;
}

describe('AC-14: Tippflaeche des ⓘ — mindestens 24 px, am <button> selbst', () => {
	test('display UND Breite/Hoehe >= 24 px am selben Element (Inline-Stil oder Klassen-Regel ausserhalb @media)', async () => {
		const BegriffErklaerung = await lade('molecules/BegriffErklaerung.svelte');
		const html = renderKomponente(BegriffErklaerung, { begriff: 'cooldown' });
		const tag = tagsMitTestid(html, 'begriff-erklaerung-cooldown')[0];
		assert.ok(tag, 'ⓘ nicht gerendert');
		const klassen = (attribut(tag, 'class') ?? '').split(/\s+/).filter(Boolean);
		const { stil } = stilquellen(DATEIEN.ii);
		const regeln = [...ohneAtRegeln(stil).matchAll(/([^{}]+)\{([^{}]*)\}/g)]
			.filter(([, sel]) => sel.split(',').some((s) => klassen.some((k) => s.includes(`.${k}`))))
			.map(([, , body]) => body)
			.join(';');
		const wirksam = `${attribut(tag, 'style') ?? ''};${regeln}`;
		assert.match(
			wirksam,
			/display\s*:\s*(inline-flex|flex|block|inline-block|grid)/,
			`kein display-Wert am ⓘ-Button — min-/Breite wirkt auf Inline-Elementen nicht. Wirksam: ${wirksam}`
		);
		const breite = px(wirksam, ['min-width', 'width']);
		const hoehe = px(wirksam, ['min-height', 'height']);
		assert.ok(breite >= 24, `Tippflaeche Breite ${breite}px < 24px`);
		assert.ok(hoehe >= 24, `Tippflaeche Hoehe ${hoehe}px < 24px`);
	});
});
