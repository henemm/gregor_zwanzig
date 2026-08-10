// Issue #1667 S2 — Paritaet der HH:MM-Formatierung (TS-Seite).
//
// Spec: docs/specs/modules/fix_1667_s2_naismith_wrap.md
//
// AC-1: Eigenschaftsnachweis der Inertheit ueber den vollen Minutenbereich
//       0..1439 gegen die alte Klemmformel als lokale Referenz.
// AC-3: Randfaelle 1439/1440/1441/2879 gegen die GEMEINSAME JSON-Fixture
//       tests/fixtures/naismith_hhmm_wrap.json, die auch der Python- und der
//       Go-Test lesen — keine drei gespiegelten Listen.
//
// Pfadanker: Aufstieg ab der EIGENEN Datei (import.meta.url) bis zu einem
// Verzeichnis, das go.mod ODER .git traegt (Vorbild
// internal/mail/recipient_parity_test.go::findRepoRoot). Bewusst KEINE feste
// ../../../../-Kette: die bricht lautlos beim Verschieben der Testdatei und
// verstiesse gegen Pfadregel #1409. Im git-worktree ist .git eine DATEI, kein
// Verzeichnis — existsSync deckt beide Faelle ab.
//
// Ausfuehrung:
//   cd frontend && npm test -- src/lib/utils/naismith_wrap_parity.test.ts

import { test } from 'node:test';
import assert from 'node:assert/strict';
import { existsSync, readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

import { formatHHMM } from './naismith.ts';

const MAX_ROOT_ASCENT = 8;
const DAY_MINUTES = 24 * 60;

function findRepoRoot(): string {
	let dir = dirname(fileURLToPath(import.meta.url));
	for (let i = 0; i < MAX_ROOT_ASCENT; i++) {
		if (existsSync(join(dir, 'go.mod')) || existsSync(join(dir, '.git'))) {
			return dir;
		}
		const parent = dirname(dir);
		if (parent === dir) break;
		dir = parent;
	}
	throw new Error(
		`findRepoRoot: weder go.mod noch .git innerhalb von ${MAX_ROOT_ASCENT} Ebenen ` +
			`ueber ${dirname(fileURLToPath(import.meta.url))} gefunden — Pfadanker verloren, ` +
			'die Paritaets-Fixture ist nicht auffindbar.'
	);
}

interface WrapFall {
	id: string;
	total_min: number;
	expected_hhmm: string;
	kommentar: string;
}

function wrapFaelle(): WrapFall[] {
	const pfad = join(findRepoRoot(), 'tests', 'fixtures', 'naismith_hhmm_wrap.json');
	return JSON.parse(readFileSync(pfad, 'utf-8')).faelle as WrapFall[];
}

/**
 * Die ALTE Formel (min(m, 1439)) als lokale Referenz fuer AC-1. Bewusst hier
 * hinterlegt statt aus dem Produktivcode gelesen: nach dem Fix existiert sie
 * dort nicht mehr, der Inertheits-Nachweis braucht sie aber weiterhin.
 */
function referenzKlemme(totalMin: number): string {
	const m = Math.min(totalMin, DAY_MINUTES - 1);
	return `${String(Math.floor(m / 60)).padStart(2, '0')}:${String(m % 60).padStart(2, '0')}`;
}

// Ohne diese Zusicherung koennte eine leere Fixture-Liste den AC-3-Test still
// auf null Faelle schrumpfen lassen und "nichts geprueft" als gruen ausgeben.
test('#1667 S2: Fixture traegt die vier Randfaelle', () => {
	const werte = wrapFaelle()
		.map((f) => f.total_min)
		.sort((a, b) => a - b);
	assert.deepEqual(werte, [1439, 1440, 1441, 2879], `Fixture-Randfaelle veraendert: ${werte}`);
});

test('#1667 S2 AC-1: Normalbereich 0..1439 bit-identisch zur alten Klemme', () => {
	const abweichungen: string[] = [];
	for (let m = 0; m < DAY_MINUTES; m++) {
		const ist = formatHHMM(m);
		const soll = referenzKlemme(m);
		if (ist !== soll) abweichungen.push(`${m}: ${ist} != ${soll}`);
	}
	assert.deepEqual(
		abweichungen.slice(0, 3),
		[],
		`${abweichungen.length} Minutenwerte im Normalbereich weichen von der alten Klemmformel ab`
	);
});

test('#1667 S2 AC-3: Randfaelle gegen die gemeinsame Fixture', () => {
	for (const fall of wrapFaelle()) {
		assert.equal(
			formatHHMM(fall.total_min),
			fall.expected_hhmm,
			`total_min=${fall.total_min} (${fall.id}): erwartet ${fall.expected_hhmm}, ` +
				`bekommen ${formatHHMM(fall.total_min)} — ${fall.kommentar}`
		);
	}
});
