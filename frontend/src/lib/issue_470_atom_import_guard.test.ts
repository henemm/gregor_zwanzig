// TDD RED: Issue #470 — ui/-Atom-Importe auf atoms/ migrieren
//
// Spec:     docs/specs/modules/issue_470_atom_migration.md
//
// Source-Inspection-Test: prüft, dass keine .svelte-Datei außerhalb von ui/ und
// atoms/ mehr direkt aus $lib/components/ui/{atom} importiert. Betrifft die 9
// Wrapper-Atome: Btn, Eyebrow, Pill, Input, Segmented, Dot, WIcon, ElevSparkline,
// TopoBg. Compound-Primitive (Dialog, Table, Select, Card, etc.) sind NICHT im Scope.
//
// RED: Vor Migration importieren >100 Stellen direkt aus ui/ -> FAIL.
//
// Ausführung:
//   cd frontend && node --experimental-strip-types --test src/lib/issue_470_atom_import_guard.test.ts

import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync, readdirSync, statSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { join } from 'node:path';

const SRC = fileURLToPath(new URL('..', import.meta.url));

// ui/-Pfade, die für die 9 Wrapper-Atome verboten sind
const FORBIDDEN_PATTERNS = [
	/\$lib\/components\/ui\/btn/,
	/\$lib\/components\/ui\/eyebrow/,
	/\$lib\/components\/ui\/pill/,
	/\$lib\/components\/ui\/input/,
	/\$lib\/components\/ui\/segmented/,
	/\$lib\/components\/ui\/dot/,
	/\$lib\/components\/ui\/wicon/,
	/\$lib\/components\/ui\/elev-sparkline/,
	/\$lib\/components\/ui\/topo/,
];

function collectSvelteFiles(dir: string, acc: string[] = []): string[] {
	for (const name of readdirSync(dir)) {
		const full = join(dir, name);
		if (statSync(full).isDirectory()) {
			// Verzeichnisse ui/ und atoms/ selbst überspringen
			if (name === 'ui' || name === 'atoms') continue;
			if (name === 'node_modules' || name === '.svelte-kit' || name === 'build') continue;
			collectSvelteFiles(full, acc);
		} else if (name.endsWith('.svelte')) {
			acc.push(full);
		}
	}
	return acc;
}

test('Keine direkten ui/-Atom-Importe außerhalb von ui/ und atoms/', () => {
	const files = collectSvelteFiles(SRC);
	const violations: string[] = [];

	for (const file of files) {
		const content = readFileSync(file, 'utf-8');
		const relPath = file.replace(SRC, '');
		for (const pattern of FORBIDDEN_PATTERNS) {
			if (pattern.test(content)) {
				// Import-Zeilen extrahieren für bessere Fehler-Meldung
				const lines = content.split('\n');
				for (let i = 0; i < lines.length; i++) {
					if (pattern.test(lines[i]) && lines[i].includes('import')) {
						violations.push(`${relPath}:${i + 1}: ${lines[i].trim()}`);
					}
				}
			}
		}
	}

	assert.deepEqual(
		violations,
		[],
		`${violations.length} direkte ui/-Atom-Import(e) gefunden — müssen auf atoms/ migriert werden:\n${violations.join('\n')}`
	);
});
