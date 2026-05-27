// TDD RED: Issue #402 — Trips-Seite auf Atomic-Bibliothek migrieren
//
// Spec:  docs/specs/modules/issue_402_trips_atomic.md
// Route: /trips  →  frontend/src/routes/trips/+page.svelte
//
// Source-Inspection-Tests (analog zu routes/archiv/issue_388.test.ts):
// Liest die echte +page.svelte als String und prüft, ob die Atomic-Migration
// korrekt umgesetzt wurde.
//
// RED: Gegen den aktuellen Stand (Btn/Input/Dot/Eyebrow aus ui/, Inline-
// Stats-Streifen mit <span> statt <Stat>) schlagen AC-1/AC-2/AC-3 fehl.
//
// Ausführung:
//   cd frontend && node --experimental-strip-types --test src/routes/trips/issue_402.test.ts

import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { join, dirname } from 'node:path';

const TRIPS_DIR = dirname(fileURLToPath(import.meta.url));
const PAGE_SVELTE = join(TRIPS_DIR, '+page.svelte');

// ── Hilfsfunktionen ──────────────────────────────────────────────────────────

function readPage(): string {
	return readFileSync(PAGE_SVELTE, 'utf-8');
}

function escapeRegex(s: string): string {
	return s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

/** Liefert die benannten Importe aus einem bestimmten Modul-Pfad. */
function namedImportsFrom(src: string, modulePath: string): string[] {
	const re = new RegExp(
		`import\\s*\\{([^}]*)\\}\\s*from\\s*['"]${escapeRegex(modulePath)}['"]`,
		'g'
	);
	const names: string[] = [];
	let m: RegExpExecArray | null;
	while ((m = re.exec(src))) {
		for (const part of m[1].split(',')) {
			const name = part.trim().split(/\s+as\s+/)[0].trim();
			if (name) names.push(name);
		}
	}
	return names;
}

// ── AC-1: Atom-/Molecule-Barrel-Importe ──────────────────────────────────────

test('AC-1: Btn/Input/Dot/Eyebrow werden aus $lib/components/atoms importiert', () => {
	const src = readPage();
	const atoms = namedImportsFrom(src, '$lib/components/atoms');
	for (const name of ['Btn', 'Input', 'Dot', 'Eyebrow']) {
		assert.ok(
			atoms.includes(name),
			`${name} wird nicht aus '$lib/components/atoms' importiert (gefunden: ${atoms.join(', ') || 'keine'})`
		);
	}
});

test('AC-1: Stat wird aus $lib/components/molecules importiert', () => {
	const src = readPage();
	const molecules = namedImportsFrom(src, '$lib/components/molecules');
	assert.ok(
		molecules.includes('Stat'),
		`Stat wird nicht aus '$lib/components/molecules' importiert (gefunden: ${molecules.join(', ') || 'keine'})`
	);
});

test('AC-1: Btn/Input/Dot/Eyebrow werden NICHT mehr direkt aus ui/ importiert', () => {
	const src = readPage();
	for (const uiPath of ['ui/btn', 'ui/input', 'ui/dot', 'ui/eyebrow']) {
		assert.ok(
			!src.includes(uiPath),
			`Direkter Import aus '$lib/components/${uiPath}' noch vorhanden — auf Atom-Barrel umstellen`
		);
	}
});

// ── AC-2: Stats-Streifen via Stat-Molecule ───────────────────────────────────

test('AC-2: Stats-Streifen nutzt <Stat layout="inline">', () => {
	const src = readPage();
	assert.ok(src.includes('<Stat'), 'Keine <Stat>-Komponente im Markup gefunden');
	assert.ok(
		/<Stat[^>]*layout=["']inline["']/.test(src),
		'<Stat> ohne layout="inline" — Stats-Streifen nicht über Stat-Molecule umgesetzt'
	);
});

test('AC-2: Zähler basieren weiterhin auf deriveTripStatus', () => {
	const src = readPage();
	assert.ok(
		src.includes('deriveTripStatus'),
		'deriveTripStatus nicht mehr verwendet — Zähler-Logik darf nicht geändert werden'
	);
});

// ── AC-3: Farbige Status-Punkte bleiben erhalten (PO-Entscheidung Variante A) ──

test('AC-3: Status-Streifen behält farbige Dot-Punkte mit tone neben Stat', () => {
	const src = readPage();
	assert.ok(src.includes('<Dot'), 'Kein <Dot> im Markup — Status-Punkte gingen verloren');
	assert.ok(
		/<Dot[^>]*tone=/.test(src),
		'<Dot> ohne tone-Prop — Status-Farb-Codierung fehlt'
	);
	// Dot und Stat müssen koexistieren (komponierter Streifen, nicht entweder/oder)
	assert.ok(
		src.includes('<Dot') && src.includes('<Stat'),
		'Dot und Stat koexistieren nicht — Variante A (Punkte + Baustein) nicht umgesetzt'
	);
});

// ── AC-4: Nicht-atomisierte Komponenten bleiben unverändert aus ui/ ───────────

test('AC-4: Table/Dialog/Select/EmptyState/Checkbox bleiben aus ui/ importiert', () => {
	const src = readPage();
	for (const uiPath of ['ui/table', 'ui/dialog', 'ui/select', 'ui/empty-state', 'ui/checkbox']) {
		assert.ok(
			src.includes(uiPath),
			`Import aus '$lib/components/${uiPath}' fehlt — diese Komponenten haben kein Atom-Pendant und müssen aus ui/ bleiben`
		);
	}
});
