// Issue #2621: Tailwind v4 setzt im Preflight fuer <button> `cursor: default` (v3: pointer).
// Rohe Knoepfe (z. B. Bestaetigen auf /verify-email) zeigen dadurch keine Hand und wirken nicht
// klickbar. Abhilfe ist EINE Boden-Regel in `@layer base`, in `:where()` (Spezifitaet 0), damit
// jede Bausteinregel (Btn-Atom `not-allowed`) und jede Utility (`cursor-default`) weiter gewinnt.
//
// Dieser Test sichert die FORM der Regel (Schicht, Spezifitaet, Ausschluesse) — den Nachweis aus
// Nutzersicht (berechneter Cursor im Browser) fuehrt e2e/hand-cursor-auth.spec.ts.
//
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types \
//     --experimental-test-module-mocks --test src/lib/__tests__/hand_cursor_boden.test.ts
import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { fileURLToPath } from 'node:url';

const FRONTEND_SRC = join(fileURLToPath(new URL('.', import.meta.url)), '..', '..');
const ohneKommentare = (s: string) => s.replace(/\/\*[\s\S]*?\*\//g, '');
const CSS = ohneKommentare(readFileSync(join(FRONTEND_SRC, 'app.css'), 'utf-8'));

/** Inhalt des Blocks, dessen oeffnende Klammer bei `auf` steht. */
function blockInhalt(quelle: string, auf: number): string {
	let tiefe = 0;
	for (let i = auf; i < quelle.length; i++) {
		if (quelle[i] === '{') tiefe++;
		else if (quelle[i] === '}' && --tiefe === 0) return quelle.slice(auf + 1, i);
	}
	throw new Error('Block ohne Ende');
}

/** Alle Top-Level-Bloecke `@layer base { … }` (ausserhalb jeder Media-Query). */
function topLevelLayerBase(quelle: string): string[] {
	const bloecke: string[] = [];
	let tiefe = 0;
	for (let i = 0; i < quelle.length; i++) {
		const c = quelle[i];
		if (c === '{') tiefe++;
		else if (c === '}') tiefe--;
		else if (tiefe === 0 && quelle.startsWith('@layer', i)) {
			const auf = quelle.indexOf('{', i);
			const kopf = quelle.slice(i, auf).trim();
			if (/^@layer\s+base$/.test(kopf)) bloecke.push(blockInhalt(quelle, auf));
		}
	}
	return bloecke;
}

type Regel = { selektor: string; rumpf: string };

/** Regeln auf oberster Ebene eines Blocks (keine verschachtelten At-Rules). */
function regelnIn(block: string): Regel[] {
	const regeln: Regel[] = [];
	let i = 0;
	while (i < block.length) {
		const auf = block.indexOf('{', i);
		if (auf < 0) break;
		const selektor = block.slice(i, auf).trim();
		const rumpf = blockInhalt(block, auf);
		regeln.push({ selektor, rumpf });
		i = auf + rumpf.length + 2;
	}
	return regeln;
}

function findeBodenRegel(): Regel | undefined {
	for (const block of topLevelLayerBase(CSS)) {
		for (const r of regelnIn(block)) {
			if (/cursor\s*:\s*pointer/.test(r.rumpf) && /\bbutton\b/.test(r.selektor)) return r;
		}
	}
	return undefined;
}

describe('#2621 Hand-Cursor-Boden-Regel in app.css', () => {
	test('AC-1..3: eine Regel mit `cursor: pointer` fuer button steht in @layer base, ausserhalb jeder Media-Query', () => {
		const r = findeBodenRegel();
		assert.ok(r, 'keine Top-Level-`@layer base`-Regel mit `cursor: pointer` fuer <button> gefunden');
	});

	test('AC-6: Selektor ist vollstaendig in :where() gekapselt (Spezifitaet 0)', () => {
		const r = findeBodenRegel();
		assert.ok(r, 'Boden-Regel fehlt');
		assert.match(r!.selektor.replace(/\s+/g, ' '), /^:where\(.*\)$/, `Selektor nicht in :where(): ${r!.selektor}`);
	});

	test('AC-1..3: erfasst button, [role="button"], label[for] und summary', () => {
		const r = findeBodenRegel();
		assert.ok(r, 'Boden-Regel fehlt');
		const s = r!.selektor;
		assert.match(s, /(^|[\s,(])button\b/, 'button fehlt');
		assert.match(s, /\[role=["']button["']\]/, '[role="button"] fehlt');
		assert.match(s, /label\[for\]/, 'label[for] fehlt');
		assert.match(s, /(^|[\s,(])summary\b/, 'summary fehlt');
	});

	test('AC-4: gesperrte Knoepfe (:disabled und aria-disabled="true") sind ausgenommen', () => {
		const r = findeBodenRegel();
		assert.ok(r, 'Boden-Regel fehlt');
		const s = r!.selektor;
		assert.match(s, /button:not\(:disabled\)/, 'button ohne :not(:disabled)');
		assert.match(s, /button[^,]*:not\(\[aria-disabled=["']true["']\]\)/, 'button ohne :not([aria-disabled="true"])');
		assert.match(
			s,
			/\[role=["']button["']\]:not\(\[aria-disabled=["']true["']\]\)/,
			'[role="button"] ohne :not([aria-disabled="true"])',
		);
	});
});
