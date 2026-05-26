// TDD RED: Issue #394 — Trip-Terminologie-Konsistenz (Guard-Test)
//
// Spec: docs/specs/modules/trip_terminology_consistency.md
//
// Source-Inspection-Test (Pattern wie contrast-audit.test.ts): liest die echten
// .svelte-Quelldateien als String und prueft, dass KEIN user-sichtbarer String
// das Wort „Tour"/„Touren" (als Synonym fuer Trip) mehr enthaelt. PO-Direktive:
// „Verwende immer den Begriff Trip." Ueberall steht „Trip"/„Trips".
//
// Ausgeschlossen (kein Verstoss):
//   - Zeilen-/Block-Kommentare (// …, /* … */, <!-- … -->),
//   - data-testid-Werte,
//   - Import-/Pfad-Zeilen (import …, $lib/…, /trips, href=…),
//   - // audit:exempt-markierte Einzelfaelle (analog contrast-audit),
//   - Komposita ohne fuehrende Wortgrenze (Skitouren, Hochtour, Tagestouren) —
//     diese sind entweder Disziplin-Namen (kein Trip) oder werden bewusst manuell
//     im Sweep ersetzt; der Wortgrenzen-Regex faengt sie nicht.
//
// RED: Vor dem Sweep existieren ~25 user-sichtbare „Tour/Touren"-Strings -> FAIL.
//
// Ausfuehrung:
//   cd frontend && node --test --experimental-strip-types src/lib/trip-terminology.test.ts

import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync, readdirSync, statSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { join } from 'node:path';

const SRC = fileURLToPath(new URL('..', import.meta.url)); // -> frontend/src/

/** Sammelt rekursiv alle .svelte-Dateien unter SRC. */
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

const FILES = collectSvelte(SRC);

// Wort „Tour"/„Touren" mit fuehrender Wortgrenze — faengt „Tour", „Touren",
// „TOUR(EN)" (Eyebrow-Versalien), „Tour-Hoehe" etc., aber NICHT
// „Skitouren"/„Hochtour"/„Tagestouren" (kein \b vor „tour" mitten im Wort)
// und NICHT Identifier wie „ski_touring".
const WORD = /\b(Tour|Touren|TOUR|TOUREN)\b/g;

/**
 * Findet user-sichtbare „Tour/Touren"-Vorkommen. Schliesst Kommentar-Zeilen,
 * data-testid-Werte, Import-/Pfad-Zeilen und audit:exempt-markierte Zeilen aus.
 * Liefert `datei:zeile`-Liste mit dem getroffenen Wort.
 */
function offenders(): string[] {
	const hits: string[] = [];
	for (const f of FILES) {
		const content = readFileSync(f, 'utf-8');
		const lines = content.split('\n');
		let inBlockComment = false;
		for (let i = 0; i < lines.length; i++) {
			const raw = lines[i];
			const trimmed = raw.trim();

			// Block-Kommentar /* … */ (JS) — Mehrzeilen-Zustand verfolgen.
			if (inBlockComment) {
				if (trimmed.includes('*/')) inBlockComment = false;
				continue;
			}
			if (trimmed.startsWith('/*')) {
				if (!trimmed.includes('*/')) inBlockComment = true;
				continue;
			}
			// Zeilen-Kommentare: // (JS), * (JSDoc-Fortsetzung), <!-- --> (Markup).
			if (
				trimmed.startsWith('//') ||
				trimmed.startsWith('*') ||
				trimmed.startsWith('<!--')
			) {
				continue;
			}
			// audit:exempt-Konvention (begruendeter Einzelfall, analog contrast-audit).
			if (/audit:exempt/.test(raw)) continue;
			// Import-/Pfad-Zeilen (keine user-sichtbaren Strings).
			if (/^\s*import\b/.test(raw)) continue;

			// Treffer mit Wortgrenze sammeln.
			WORD.lastIndex = 0;
			let m: RegExpExecArray | null;
			while ((m = WORD.exec(raw)) !== null) {
				// data-testid-Wert? (Treffer liegt innerhalb eines data-testid="…").
				const before = raw.slice(0, m.index);
				const testidOpen = before.lastIndexOf('data-testid="');
				if (testidOpen >= 0) {
					const close = raw.indexOf('"', testidOpen + 'data-testid="'.length);
					if (close < 0 || m.index < close) continue; // im testid-Wert
				}
				hits.push(`${f.replace(SRC, '')}:${i + 1}  „${m[0]}"`);
			}
		}
	}
	return hits;
}

test('AC-1/AC-4: kein user-sichtbares „Tour"/„Touren" in .svelte-Dateien (→ „Trip"/„Trips")', () => {
	const found = offenders();
	assert.equal(
		found.length,
		0,
		`User-sichtbares „Tour"/„Touren" gefunden (→ „Trip"/„Trips", oder // audit:exempt):\n  ${found.join('\n  ')}`
	);
});
