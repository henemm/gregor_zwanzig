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

test('AC-1: Btn/Input/Eyebrow werden aus $lib/components/atoms importiert', () => {
	const src = readPage();
	const atoms = namedImportsFrom(src, '$lib/components/atoms');
	for (const name of ['Btn', 'Input', 'Eyebrow']) {
		assert.ok(
			atoms.includes(name),
			`${name} wird nicht aus '$lib/components/atoms' importiert (gefunden: ${atoms.join(', ') || 'keine'})`
		);
	}
});

// AC-1 Stat-Import: durch #411 superseded — Stats-Strip nutzt jetzt Inline-HTML, kein <Stat> mehr

test('AC-1: Btn/Input/Dot/Eyebrow werden NICHT mehr direkt aus ui/ importiert', () => {
	const src = readPage();
	for (const uiPath of ['ui/btn', 'ui/input', 'ui/dot', 'ui/eyebrow']) {
		assert.ok(
			!src.includes(uiPath),
			`Direkter Import aus '$lib/components/${uiPath}' noch vorhanden — auf Atom-Barrel umstellen`
		);
	}
});

// ── AC-2: Stats-Streifen — durch #411 superseded ─────────────────────────────
// #411 ersetzt <Stat layout="inline"> durch Inline-HTML mit --g-accent-Zahlen.
// Neue Assertions für Stats-Strip: issue_411_413.test.ts

// AC-2 (deriveTripStatus in statusTone/primaryLabel) und AC-3 (<Dot tone> in der Inline-Karte) sind mit
// #2278 abgeloest: statusTone/primaryLabel sind toter Code gewesen und entfernt, die mobile Karte ist
// der geteilte SubscriptionCard (Status-Punkt dort, bewacht in organisms/__tests__/subscription_card.test.ts).

// ── AC-4: durch #477 superseded ──────────────────────────────────────────────
// Table/Dialog/Select/EmptyState/Checkbox wurden per #477+#486 aus +page.svelte
// entfernt und in ReportConfigDialog / TestReportDialog / native HTML gekapselt.
// Gegenbeweis: issue_477_486.test.ts AC-1 prüft die Abwesenheit explizit.
