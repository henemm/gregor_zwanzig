// TDD RED: Issue #377 — Contrast-Audit der Ink-Skala (WCAG-AA auf weisser Card)
//
// Spec:     docs/specs/modules/issue_377_contrast_audit.md
// Manifest: docs/specs/tests/issue_377_contrast_audit_tests.md
//
// Source-Inspection-Test (Pattern wie tokens-bridge.test.ts): liest die echten
// .svelte/.css-Quelldateien als String und prueft, dass FAIL-Tokens
// (--g-ink-faint, --g-ink-4) nicht mehr als TEXTFARBE (`color:`) verwendet werden,
// dass die drei nackten Accent-Body-Text-Stellen verschwunden sind und dass die
// Showcase-Route eine Kontrast-Belege-Sektion rendert. Keine Mocks, kein
// node_modules — nur Node-Bordmittel.
//
// RED: Vor der Implementierung existieren 47 ink-faint- + 2 ink-4-Textstellen,
// 3 nackte Accent-Stellen und keine contrast-section -> alle vier Asserts FAIL.
//
// Ausfuehrung:
//   cd frontend && node --experimental-strip-types --test src/lib/contrast-audit.test.ts

import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync, readdirSync, statSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { join } from 'node:path';

const SRC = fileURLToPath(new URL('..', import.meta.url)); // -> frontend/src/

/** Sammelt rekursiv alle .svelte/.css-Dateien unter SRC (ohne Test-Dateien). */
function collectFiles(dir: string, acc: string[] = []): string[] {
	for (const name of readdirSync(dir)) {
		const full = join(dir, name);
		const st = statSync(full);
		if (st.isDirectory()) {
			if (name === 'node_modules' || name === '.svelte-kit') continue;
			collectFiles(full, acc);
		} else if (
			(name.endsWith('.svelte') || name.endsWith('.css')) &&
			!name.includes('.test.')
		) {
			acc.push(full);
		}
	}
	return acc;
}

/**
 * Findet ALLE Textfarb-Nutzungen eines FAIL-Tokens — über die drei im Code genutzten
 * Mechanismen: CSS `color:`, Tailwind `text-[var(...)]`, Svelte style-Binding `'var(...)'`.
 * Ausgeschlossen: border/background/outline (Lookbehind bzw. eigene Utility-Präfixe) und
 * `audit:exempt`-markierte Glyphen (WCAG §1.4.3 Logo/dekorativ). Liefert `datei:zeile`-Liste.
 */
function textColorOffenders(token: string): string[] {
	const esc = token.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
	// `VAR` matcht var(--token) UND die Fallback-Form var(--token, #hex) —
	// aber NICHT var(--token-deep) (nach dem Token folgt nur `)` oder `,`, kein `-`).
	const VAR = 'var\\(' + esc + '(?:\\s*,[^)]*)?\\)';
	const reCss = new RegExp('(?<![-\\w])color:\\s*' + VAR, 'g'); // CSS color:
	const reTw = new RegExp('text-\\[' + VAR + '\\]', 'g'); // Tailwind text-[…]
	const reBind = new RegExp("'" + VAR + "'", 'g'); // Svelte style-Binding
	const offenders: string[] = [];
	for (const f of FILES) {
		const content = readFileSync(f, 'utf-8');
		for (const re of [reCss, reTw, reBind]) {
			let m: RegExpExecArray | null;
			re.lastIndex = 0;
			while ((m = re.exec(content)) !== null) {
				const win = content.slice(Math.max(0, m.index - 60), m.index + 150);
				if (/audit:exempt/.test(win)) continue; // Logo/dekorativer Glyph (WCAG §1.4.3)
				const line = content.slice(0, m.index).split('\n').length;
				offenders.push(`${f.replace(SRC, '')}:${line}`);
			}
		}
	}
	return offenders;
}

const FILES = collectFiles(SRC);

test('AC-6/AC-9: --g-ink-faint nirgends als Textfarbe (color: / text-[] / style-Binding)', () => {
	const offenders = textColorOffenders('--g-ink-faint');
	assert.equal(
		offenders.length,
		0,
		`--g-ink-faint als Textfarbe (→ --g-ink-muted, oder // audit:exempt):\n  ${offenders.join('\n  ')}`
	);
});

test('AC-6/AC-9: --g-ink-4 nirgends als Textfarbe (außer audit:exempt Logo-Glyph)', () => {
	const offenders = textColorOffenders('--g-ink-4');
	assert.equal(
		offenders.length,
		0,
		`--g-ink-4 als Textfarbe (→ --g-ink-muted, oder // audit:exempt):\n  ${offenders.join('\n  ')}`
	);
});

test('AC-7: --g-accent als Textfarbe nur mit Ruhezustand-Underline oder audit:exempt', () => {
	// --g-accent (4.34:1) ist für normalen Body-Text NICHT AA-konform. Erlaubt nur:
	//   (a) Ruhezustand-`text-decoration: underline` IM SELBEN Block/style-Attribut
	//       (NICHT `text-decoration: none`; NICHT eine :hover-Regel → daher block-genau
	//        bis zur nächsten `}` oder `"`, sonst leakt der hover-underline rein), oder
	//   (b) `audit:exempt`-Kommentar (Large-Text/h1, Logo/Markenname, §1.4.11-Icon).
	// Drei Mechanismen: CSS `color:`, Tailwind `text-[var(…)]`, Svelte `style:color="var(…)"`.
	const offenders: string[] = [];
	const restUnderline = (block: string) => /text-decoration:\s*underline/.test(block);
	for (const f of FILES) {
		const content = readFileSync(f, 'utf-8');
		// (a) CSS color: — block-genau (bis nächste } oder ") gegen :hover-Leak.
		//     Erfasst var(--g-accent) UND Fallback var(--g-accent, #hex), nicht --g-accent-deep.
		const reCss = /(?<![-\w])color:\s*var\(--g-accent(?:\s*,[^)]*)?\)/g;
		let m: RegExpExecArray | null;
		while ((m = reCss.exec(content)) !== null) {
			const brace = content.indexOf('}', m.index);
			const quote = content.indexOf('"', m.index);
			const end = Math.min(brace < 0 ? Infinity : brace, quote < 0 ? Infinity : quote);
			const block = content.slice(m.index, end === Infinity ? m.index + 200 : end);
			const ctx = content.slice(Math.max(0, m.index - 150), m.index + 200);
			if (restUnderline(block) || /audit:exempt/.test(ctx)) continue;
			offenders.push(`${f.replace(SRC, '')}:${content.slice(0, m.index).split('\n').length} (color:)`);
		}
		// (b) Tailwind text-[…] + (c) style:color="…" + (d) JS-Binding 'var(--g-accent[,…])'
		// (für style:color={variable} / statusColors-Maps; Icon-/bg-Defaults via audit:exempt).
		for (const re of [
			/text-\[var\(--g-accent(?:\s*,[^)]*)?\)\]/g,
			/style:color="var\(--g-accent(?:\s*,[^)]*)?\)"/g,
			/'var\(--g-accent(?:\s*,[^)]*)?\)'/g
		]) {
			while ((m = re.exec(content)) !== null) {
				const ctx = content.slice(Math.max(0, m.index - 150), m.index + 150);
				if (/audit:exempt/.test(ctx)) continue;
				offenders.push(`${f.replace(SRC, '')}:${content.slice(0, m.index).split('\n').length} (utility/binding)`);
			}
		}
	}
	assert.equal(
		offenders.length,
		0,
		`--g-accent als Textfarbe ohne Affordance (→ --g-accent-deep, oder // audit:exempt):\n  ${offenders.join('\n  ')}`
	);
});

test('AC-8: _design-Route enthaelt Kontrast-Belege-Sektion', () => {
	const route = fileURLToPath(new URL('../routes/_design/+page.svelte', import.meta.url));
	const content = readFileSync(route, 'utf-8');
	assert.ok(
		content.includes('data-testid="contrast-section"'),
		'data-testid="contrast-section" fehlt in _design/+page.svelte'
	);
});

test('AC-1 §1.4.11: --g-ink-faint nirgends als SVG stroke ohne audit:exempt', () => {
	const offenders: string[] = [];
	for (const f of FILES.filter(f => f.endsWith('.svelte'))) {
		const content = readFileSync(f, 'utf-8');
		const re = /stroke="var\(--g-ink-faint\)"/g;
		let m: RegExpExecArray | null;
		while ((m = re.exec(content)) !== null) {
			const ctx = content.slice(Math.max(0, m.index - 60), m.index + 120);
			if (/audit:exempt/.test(ctx)) continue;
			const line = content.slice(0, m.index).split('\n').length;
			offenders.push(`${f.replace(SRC, '')}:${line}`);
		}
	}
	assert.equal(
		offenders.length,
		0,
		`stroke="var(--g-ink-faint)" ohne audit:exempt (§1.4.11 FAIL):\n  ${offenders.join('\n  ')}`
	);
});
