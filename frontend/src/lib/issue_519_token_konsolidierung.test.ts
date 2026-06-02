// Regression-Guard: Issue #519 + #541 — Token-Konsolidierung (kanonischer Zustand)
//
// Spec: docs/specs/modules/issue_519_token_konsolidierung.md
// Folge-Spec: docs/specs/modules/bug-541-543-544-token-checkbox-tailwind.md
//
// HISTORIE:
//   #519 (2026-05-xx) führte die kanonischen Token-Namen --g-success/warning/danger
//        als Brücken-Aliasse auf --g-good/warn/bad ein. Übergangszustand: alte Namen
//        blieben in app.css als Quelldefinition erhalten.
//   #541 (2026-06-02) schloss die Konsolidierung ab: Aliasse wurden zu direkten
//        Hex-Definitionen umgeschrieben, die alten Namen --g-good/warn/bad entfernt,
//        und alle 35 Svelte-Dateien auf die kanonischen Namen umgestellt.
//
// Source-Inspection-Test (Pattern wie tokens-bridge.test.ts):
// liest app.css und Svelte-Quelltext und prueft, dass:
//   AC-1 (#541): --g-success/warning/danger sind direkte Hex-Definitionen in app.css
//   AC-2 (#541): keine Svelte-Datei nutzt var(--g-good)/var(--g-warn)/var(--g-bad) mehr
//   AC-3 (#519):  --color-destructive zeigt auf var(--g-danger) (shadcn-Bridge)
//   AC-4 (#519):  _design-system/+page.svelte nutzt --g-wx-* statt --g-weather-*
//   AC-5 (#541): die alten Token-Namen --g-good/warn/bad existieren nicht mehr in app.css
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
// THEN alle drei sind direkte Hex-Definitionen (kanonischer Endzustand nach #541)

test('AC-1: --g-success ist direkte Hex-Definition #3d6b3a (#541)', () => {
	assert.ok(
		hasDecl('--g-success', '#3d6b3a'),
		'--g-success muss direkte Hex-Definition sein (war Bridge-Alias zu --g-good, nach #541 aufgelöst)'
	);
});

test('AC-1: --g-warning ist direkte Hex-Definition #c08a1a (#541)', () => {
	assert.ok(
		hasDecl('--g-warning', '#c08a1a'),
		'--g-warning muss direkte Hex-Definition sein (war Bridge-Alias zu --g-warn, nach #541 aufgelöst)'
	);
});

test('AC-1: --g-danger ist direkte Hex-Definition #a83232 (#541)', () => {
	assert.ok(
		hasDecl('--g-danger', '#a83232'),
		'--g-danger muss direkte Hex-Definition sein (war Bridge-Alias zu --g-bad, nach #541 aufgelöst)'
	);
});

// ── AC-2 ─────────────────────────────────────────────────────────────────────
// GIVEN alle Svelte-Dateien in frontend/src/
// WHEN nach var(--g-good), var(--g-warn) oder var(--g-bad) gesucht wird
// THEN keine Fundstelle in einer .svelte-Datei (kanonische Namen --g-success/warning/danger sind Pflicht)
//
// Nach #541 sind die alten Alias-Tokens entfernt — jede Verwendung in einer
// Svelte-Datei würde zu einem ungültigen Token-Ref führen.

function findOldTokensInSvelte(): string[] {
	const hits: string[] = [];
	const patternGood = /var\(--g-good[,)]/g;
	const patternWarn = /var\(--g-warn[,)]/g;
	const patternBad = /var\(--g-bad[,)]/g;
	for (const file of ALL_SVELTE) {
		const content = readFileSync(file, 'utf-8');
		const lines = content.split('\n');
		for (let i = 0; i < lines.length; i++) {
			const line = lines[i];
			// Kommentare ueberspringen
			const trimmed = line.trim();
			if (trimmed.startsWith('//') || trimmed.startsWith('*') || trimmed.startsWith('<!--')) continue;
			patternGood.lastIndex = 0;
			patternWarn.lastIndex = 0;
			patternBad.lastIndex = 0;
			if (patternGood.test(line) || patternWarn.test(line) || patternBad.test(line)) {
				hits.push(`${file.replace(SRC, '')}:${i + 1}  ${line.trim()}`);
			}
		}
	}
	return hits;
}

test('AC-2 (#541): kein Svelte-File nutzt var(--g-good)/var(--g-warn)/var(--g-bad) — kanonische Namen sind Pflicht', () => {
	const found = findOldTokensInSvelte();
	assert.equal(
		found.length,
		0,
		`var(--g-good) / var(--g-warn) / var(--g-bad) noch in Svelte-Dateien (nach #541 verboten — nutze --g-success/warning/danger):\n  ${found.join('\n  ')}`
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
// Regression Guard — alte Token-Namen existieren nicht mehr in app.css (#541)
// GIVEN app.css geladen
// WHEN nach --g-good, --g-warn, --g-bad als Token-Definition gesucht
// THEN keine Fundstelle (die kanonischen Werte aus Contrast-Audit #377 leben jetzt
//      direkt in --g-success/--g-warning/--g-danger)

test('AC-5 (#541): --g-good ist nicht mehr in app.css definiert', () => {
	assert.ok(!/--g-good(?![a-z-])\s*:/.test(css), '--g-good darf nicht mehr in app.css existieren (durch --g-success ersetzt)');
});

test('AC-5 (#541): --g-warn ist nicht mehr in app.css definiert', () => {
	assert.ok(!/--g-warn(?![a-z-])\s*:/.test(css), '--g-warn darf nicht mehr in app.css existieren (durch --g-warning ersetzt)');
});

test('AC-5 (#541): --g-bad ist nicht mehr in app.css definiert', () => {
	assert.ok(!/--g-bad(?![a-z-])\s*:/.test(css), '--g-bad darf nicht mehr in app.css existieren (durch --g-danger ersetzt)');
});
