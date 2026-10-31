// doc-compliance-test (Verwender-Test: liest Quelltexte und Katalog als DATEN)
//
// Issue #2649 (i18n S4, Epic #2644) — jeder Schluessel der vereinigten
// de-Karte hat einen Verwender in frontend/src/ (ohne __tests__/ und
// *.test.ts/*.spec.ts). Verwender sind: t/$t/tr/trFor-Aufrufe und jedes
// andere Schluessel-Literal (Zuordnungstabellen, Muster infoboxKeys.ts),
// Plural-Aufrufe tn/$tn/trn/trnFor('k', …) fuer k.one/k.other, und ein
// Kommentar `// i18n-dynamic: <praefix>` fuer alle Schluessel mit dem Praefix.
// Spec: docs/specs/modules/i18n_s4_ratsche_frontend_2649.md
//
//   cd frontend && npm test -- src/lib/i18n/__tests__/katalog_schluessel_haben_verwender.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { readdirSync, readFileSync, statSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';
import { de } from '../messages/de/index.ts';

const SRC = join(dirname(fileURLToPath(import.meta.url)), '..', '..', '..');

// Bindestrich: Bestandsschluessel wie `info.wetter-metriken.route` (S2, ohne Umbenennung).
const LITERAL = /(['"`])([a-z0-9_-]+(?:\.[a-z0-9_-]+)+)\1/g;
const PLURAL = /(?:\$?\b(?:tn|trn)\(\s*|\btrnFor\(\s*[^,()]*,\s*)(['"`])([a-z0-9_.-]+)\1/g;
const DYNAMISCH = /\/\/\s*i18n-dynamic:\s*([a-z0-9_.-]+)/g;

/** Die Katalogschluessel, die in den Quelltexten einen Verwender haben. */
export function verwenderSchluessel(quelltexte: string[], schluessel: string[]): Set<string> {
	const katalog = new Set(schluessel);
	const benutzt = new Set<string>();
	const praefixe: string[] = [];
	for (const q of quelltexte) {
		for (const m of q.matchAll(LITERAL)) if (katalog.has(m[2])) benutzt.add(m[2]);
		for (const m of q.matchAll(PLURAL)) {
			for (const k of [`${m[2]}.one`, `${m[2]}.other`]) if (katalog.has(k)) benutzt.add(k);
		}
		for (const m of q.matchAll(DYNAMISCH)) praefixe.push(m[1]);
	}
	for (const k of schluessel) if (praefixe.some((p) => k.startsWith(p))) benutzt.add(k);
	return benutzt;
}

export function verwaisteSchluessel(quelltexte: string[], schluessel: string[]): string[] {
	const benutzt = verwenderSchluessel(quelltexte, schluessel);
	return schluessel.filter((k) => !benutzt.has(k)).sort();
}

function quelltexte(verzeichnis: string): string[] {
	const texte: string[] = [];
	for (const name of readdirSync(verzeichnis)) {
		const pfad = join(verzeichnis, name);
		if (statSync(pfad).isDirectory()) {
			if (name !== '__tests__') texte.push(...quelltexte(pfad));
		} else if (/\.(svelte|ts|js)$/.test(name) && !/\.(test|spec)\.ts$/.test(name)) {
			texte.push(readFileSync(pfad, 'utf8'));
		}
	}
	return texte;
}

describe('verwenderSchluessel (AC-5)', () => {
	const KATALOG = [
		'a.store', 'a.tr', 'a.trfor', 'a.tabelle', 'a.tn.one', 'a.tn.other', 'a.trn.one',
		'a.trn.other', 'a.dyn.x', 'a.dyn.y', 'a.ohne', 'a.nur_t.one', 'a.nur_t.other'
	];
	const QUELLEN = [
		"<p>{$t('a.store')}</p>",
		"const s = tr('a.tr'); const u = trFor(locals.lang, \"a.trfor\");",
		"const TABELLE: Record<string, MessageKey> = { foo: 'a.tabelle' };",
		"<span>{$tn('a.tn', anzahl)}</span>",
		"const p = trnFor(lang, 'a.trn', n, { n });",
		'// i18n-dynamic: a.dyn.\nconst k = `a.dyn.${x}`;',
		"<p>{$t('a.nur_t')}</p>"
	];

	test('alle vier Verwenderarten zaehlen, unbenutzte Schluessel werden genannt', () => {
		assert.deepEqual(verwaisteSchluessel(QUELLEN, KATALOG), [
			'a.nur_t.one',
			'a.nur_t.other',
			'a.ohne'
		]);
	});

	test('ohne Quelltexte ist jeder Schluessel verwaist', () => {
		assert.deepEqual(verwaisteSchluessel([], ['x.y']), ['x.y']);
	});

	test('Literal eines fremden Schluessels zaehlt nicht fuer einen Praefix-Nachbarn', () => {
		assert.deepEqual(verwaisteSchluessel(["t('a.b')"], ['a.b', 'a.bc', 'a.b.c']), ['a.b.c', 'a.bc']);
	});
});

describe('Bestand (AC-5)', () => {
	test('jeder Schluessel der vereinigten de-Karte hat einen Verwender in frontend/src', () => {
		const schluessel = Object.keys(de);
		const texte = quelltexte(SRC);
		assert.ok(schluessel.length >= 100, `Katalog zu klein: ${schluessel.length}`);
		assert.ok(texte.length >= 300, `Messaufbau leer: nur ${texte.length} Quelltexte`);
		const verwaist = verwaisteSchluessel(texte, schluessel);
		assert.deepEqual(verwaist, [], `Katalogschluessel ohne Verwender:\n${verwaist.join('\n')}`);
	});
});
