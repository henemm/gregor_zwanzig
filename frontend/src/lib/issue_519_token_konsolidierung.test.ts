// TDD RED: Issue #519 — Token-Konsolidierung: Duale Semantik-Token-Systeme
//
// Spec: docs/specs/modules/issue_519_token_konsolidierung.md
//
// Source-Inspection-Test (Pattern wie tokens-bridge.test.ts / trip-terminology.test.ts):
// liest app.css und Svelte-Quelltext und prueft, dass:
//   AC-1: --g-success/warning/danger sind Aliases in app.css (nicht mehr Literal-Hex)
//   AC-2: kein Svelte-File nutzt var(--g-success) oder var(--g-warning) direkt
//   AC-3: --color-destructive zeigt weiterhin auf var(--g-danger) (shadcn-Bridge)
//   AC-4: _design-system/+page.svelte nutzt --g-wx-* statt --g-weather-*
//   AC-5: kanonische Token --g-good/warn/bad haben unveraenderte Werte
//
// RED: Vor der Implementierung:
//   AC-1 FAILS  — --g-success: #3a7d44 (kein Alias)
//   AC-2 FAILS  — ~37 Svelte-Dateien nutzen noch var(--g-success)/var(--g-warning)
//   AC-3 PASSES — Regression Guard (muss nach dem Fix erhalten bleiben)
//   AC-4 FAILS  — _design-system/+page.svelte nutzt noch --g-weather-*
//   AC-5 PASSES — Regression Guard (kanonische Werte unveraendert)
//
// Ausfuehrung:
//   cd frontend && node --experimental-strip-types --test src/lib/issue_519_token_konsolidierung.test.ts

import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync, readdirSync, statSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { join } from 'node:path';

const APP_CSS_URL = new URL('../app.css', import.meta.url);
const css = readFileSync(APP_CSS_URL, 'utf-8');

const SRC = fileURLToPath(new URL('..', import.meta.url)); // -> frontend/src/

/** true, wenn `--name: value` (mit beliebigem Whitespace) in app.css vorkommt. */
function hasDecl(name: string, value: string): boolean {
	const esc = (s: string) => s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
	return new RegExp(esc(name) + '\\s*:\\s*' + esc(value)).test(css);
}

/** Sammelt rekursiv alle .svelte-Dateien unter dir. */
function collectSvelte(dir: string, acc: string[] = []): string[] {
	for (const name of readdirSync(dir)) {
		const full = join(dir, name);
		const st = statSync(full);
		if (st.isDirectory()) {
			if (name === 'node_modules' || name === '.svelte-kit') continue;
			collectSvelte(full, acc);
		} else if (name.endsWith('.svelte')) {
			acc.push(full);
		}
	}
	return acc;
}

const ALL_SVELTE = collectSvelte(SRC);

// ── AC-1 ─────────────────────────────────────────────────────────────────────
// GIVEN app.css geladen
// WHEN --g-success, --g-warning, --g-danger ausgelesen
// THEN alle drei verweisen auf kanonische Alias-Werte

test('AC-1: --g-success ist Alias auf var(--g-good)', () => {
	assert.ok(
		hasDecl('--g-success', 'var(--g-good)'),
		'--g-success muss var(--g-good) sein, war #3a7d44'
	);
});

test('AC-1: --g-warning ist Alias auf var(--g-warn)', () => {
	assert.ok(
		hasDecl('--g-warning', 'var(--g-warn)'),
		'--g-warning muss var(--g-warn) sein, war #c8882a'
	);
});

test('AC-1: --g-danger ist Alias auf var(--g-bad)', () => {
	assert.ok(
		hasDecl('--g-danger', 'var(--g-bad)'),
		'--g-danger muss var(--g-bad) sein, war #b33a2a'
	);
});

// ── AC-2 ─────────────────────────────────────────────────────────────────────
// GIVEN alle Svelte-Dateien in frontend/src/
// WHEN nach var(--g-success) oder var(--g-warning) gesucht wird
// THEN keine Fundstelle in einer .svelte-Datei

function findAltTokensInSvelte(): string[] {
	const hits: string[] = [];
	const patternSuccess = /var\(--g-success[,)]/g;
	const patternWarning = /var\(--g-warning[,)]/g;
	for (const file of ALL_SVELTE) {
		const content = readFileSync(file, 'utf-8');
		const lines = content.split('\n');
		for (let i = 0; i < lines.length; i++) {
			const line = lines[i];
			// Kommentare ueberspringen
			const trimmed = line.trim();
			if (trimmed.startsWith('//') || trimmed.startsWith('*') || trimmed.startsWith('<!--')) continue;
			patternSuccess.lastIndex = 0;
			patternWarning.lastIndex = 0;
			if (patternSuccess.test(line) || patternWarning.test(line)) {
				hits.push(`${file.replace(SRC, '')}:${i + 1}  ${line.trim()}`);
			}
		}
	}
	return hits;
}

test('AC-2: kein Svelte-File nutzt var(--g-success) oder var(--g-warning) direkt', () => {
	const found = findAltTokensInSvelte();
	assert.equal(
		found.length,
		0,
		`var(--g-success) / var(--g-warning) noch in Svelte-Dateien:\n  ${found.join('\n  ')}`
	);
});

// ── AC-3 ─────────────────────────────────────────────────────────────────────
// Regression Guard — muss VOR und NACH der Implementierung bestehen
// GIVEN app.css geladen
// WHEN --color-destructive ausgelesen
// THEN Wert ist var(--g-danger) (shadcn-Bridge unveraendert)

test('AC-3 (Regression Guard): --color-destructive zeigt auf var(--g-danger)', () => {
	assert.ok(
		hasDecl('--color-destructive', 'var(--g-danger)'),
		'--color-destructive muss var(--g-danger) sein (shadcn-Bridge C1)'
	);
});

// ── AC-4 ─────────────────────────────────────────────────────────────────────
// GIVEN _design-system/+page.svelte ist der aktuelle Quellstand
// WHEN Wetter-Token-Array ausgelesen
// THEN alle Token-Referenzen nutzen var(--g-wx-*), keine var(--g-weather-*)

test('AC-4: _design-system/+page.svelte nutzt --g-wx-* statt --g-weather-*', () => {
	const showcasePath = join(SRC, 'routes/_design-system/+page.svelte');
	const content = readFileSync(showcasePath, 'utf-8');
	const weatherOld = /var\(--g-weather-[^)]+\)/g;
	const matches: string[] = [];
	let m: RegExpExecArray | null;
	while ((m = weatherOld.exec(content)) !== null) {
		const lineNum = content.slice(0, m.index).split('\n').length;
		matches.push(`Zeile ${lineNum}: ${m[0]}`);
	}
	assert.equal(
		matches.length,
		0,
		`_design-system/+page.svelte nutzt noch --g-weather-* Tokens (statt --g-wx-*):\n  ${matches.join('\n  ')}`
	);
});

// ── AC-5 ─────────────────────────────────────────────────────────────────────
// Regression Guard — kanonische Werte unveraendert (C2/C3)
// GIVEN app.css geladen
// WHEN --g-good, --g-warn, --g-bad ausgelesen
// THEN exakt die durch Contrast-Audit #377 bestaettigten Werte

test('AC-5 (Regression Guard): --g-good ist #3d6b3a (kanonisch)', () => {
	assert.ok(hasDecl('--g-good', '#3d6b3a'), '--g-good muss #3d6b3a bleiben (C2/C3)');
});

test('AC-5 (Regression Guard): --g-warn ist #c08a1a (kanonisch)', () => {
	assert.ok(hasDecl('--g-warn', '#c08a1a'), '--g-warn muss #c08a1a bleiben (C2/C3)');
});

test('AC-5 (Regression Guard): --g-bad ist #a83232 (kanonisch)', () => {
	assert.ok(hasDecl('--g-bad', '#a83232'), '--g-bad muss #a83232 bleiben (C2/C3)');
});
