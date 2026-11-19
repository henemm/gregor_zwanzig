// TDD RED — Issue #3010 (Epic #2913): Schriftgrößen aus Schrift-Tokens statt Abstands-Tokens.
// Spec: docs/specs/modules/feat_3010_wetter_schrift_tokens.md — AC-1 (Kern-Schicht; der
// Browser-Nachweis per getComputedStyle läuft in der Staging-Verifikation).
//
// Messweise: Die Token-Definitionen in app.css sind Gegenstand der Regel (wie tokens_masse);
// app.css wird mit postcss geparst (echter CSS-Parser, keine Regex auf Freitext).
// doc-compliance-test
//
//   cd frontend && npm test -- src/lib/__tests__/schrift_tokens_3010.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import postcss from 'postcss';

const HIER = dirname(fileURLToPath(import.meta.url));
const WURZEL = postcss.parse(readFileSync(join(HIER, '..', '..', 'app.css'), 'utf8'));

/** Custom Properties der Regeln mit genau diesem Selektor (erste Definition gewinnt). */
function tokens(selektor: string): Map<string, string> {
	const aus = new Map<string, string>();
	WURZEL.walkRules((regel) => {
		if (regel.selector.trim() !== selektor) return;
		regel.walkDecls((d) => {
			if (d.prop.startsWith('--g-') && !aus.has(d.prop)) aus.set(d.prop, d.value.trim());
		});
	});
	return aus;
}

const HELL = tokens(':root');
const DUNKEL = tokens(':root[data-theme="dark"]');

describe('AC-1: Schrift-Stufen --g-text-12px und --g-text-16px', () => {
	test('Bezug: die Schriftskala --g-text-xs liegt im hellen :root', () => {
		assert.equal(HELL.get('--g-text-xs'), '11px');
	});
	test('--g-text-12px ist im hellen :root als 12px definiert', () => {
		assert.equal(HELL.get('--g-text-12px'), '12px', 'TDD RED: --g-text-12px fehlt oder ist nicht 12px');
	});
	test('--g-text-16px ist im hellen :root als 16px definiert', () => {
		assert.equal(HELL.get('--g-text-16px'), '16px', 'TDD RED: --g-text-16px fehlt oder ist nicht 16px');
	});
	test('Dunkel-Theme überschreibt die Stufen nicht mit anderen Werten', () => {
		for (const [k, soll] of [['--g-text-12px', '12px'], ['--g-text-16px', '16px']] as const) {
			const dunkel = DUNKEL.get(k);
			assert.ok(dunkel === undefined || dunkel === soll, `${k} im Dunkel-Theme: ${dunkel}`);
		}
	});
});
