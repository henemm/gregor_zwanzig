// TDD RED — Issue #436: Wizard-Save navigiert zu /trips/${id}
//
// Spec: docs/specs/modules/issue_436_wizard_save_navigation.md
//
// Diese Tests pruefen das NEUE Verhalten nach Umsetzung von #436:
//   - save() navigiert zu /trips/${created.id} statt /trips
//   - void created und TODO(epic-135) sind entfernt
//   - Fallback auf /trips wenn keine id vorhanden
//
// Ausfuehrung:
//   cd frontend && node --experimental-strip-types --test \
//     src/lib/components/trip-wizard/__tests__/issue_436_wizard_save_navigation.test.ts

import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

// Hilfsfunktion: Extrahiert den Body der save()-Methode aus dem Source-Code.
// Kopiert aus wizardState.test.ts (AC-1..4 #197) — gleiche Logik.
function extractSaveMethod(source: string): string {
	const startMarker = 'async save(): Promise<void>';
	const startIdx = source.indexOf(startMarker);
	assert.ok(startIdx >= 0, 'save()-Methoden-Header nicht gefunden in wizardState.svelte.ts');
	const braceStart = source.indexOf('{', startIdx);
	assert.ok(braceStart >= 0, "save()-Methoden-Body-Start '{' nicht gefunden");
	let depth = 0;
	for (let i = braceStart; i < source.length; i++) {
		const c = source[i];
		if (c === '{') depth++;
		else if (c === '}') {
			depth--;
			if (depth === 0) return source.slice(braceStart, i + 1);
		}
	}
	throw new Error('save()-Methoden-Body nicht geschlossen — Klammer-Balance gebrochen');
}

// AC-1 #436: save() muss zu /trips/${created.id} navigieren (Template-Literal mit id)
test("AC-1 #436: save() navigiert zu '/trips/${created.id}' — NICHT mehr zur Tripliste '/trips'", () => {
	const sourcePath = new URL('../wizardState.svelte.ts', import.meta.url);
	const source = readFileSync(sourcePath, 'utf-8');
	const saveBody = extractSaveMethod(source);

	// Erwartete Form: Template-Literal goto(`/trips/${...}`)
	// z.B. goto(`/trips/${created.id}`) oder goto(`/trips/${targetPath}`)
	const expectedPattern = /goto\(\s*`\/trips\/\$\{/;
	assert.ok(
		expectedPattern.test(saveBody),
		"save() muss 'goto(`/trips/${...}`)' enthalten — Navigation zum neu erstellten Trip (AC-1 #436)"
	);
});

// AC-2 #436: Fallback — save() muss bei fehlendem id auf '/trips' fallbacken
// Pruefen via Source-Code: id-Pruefung vor goto muss vorhanden sein.
test('AC-2 #436: save() enthält eine Bedingung (id-Check) vor der Navigation — Fallback-Logik', () => {
	const sourcePath = new URL('../wizardState.svelte.ts', import.meta.url);
	const source = readFileSync(sourcePath, 'utf-8');
	const saveBody = extractSaveMethod(source);

	// Fallback-Logik: ternary oder if-Block mit id-Pruefung.
	// Akzeptierte Formen (Code, nicht Kommentar):
	//   created?.id ? ... : '/trips'   (ternary)
	//   if (created?.id) { ... }       (if-Block)
	const conditionalPattern = /(?:created(\?\.|\.)id\s*\?)|(?:if\s*\(\s*created\?\.id\s*\))/;
	assert.ok(
		conditionalPattern.test(saveBody),
		"save() muss eine Bedingung 'created?.id ?' oder 'if (created?.id)' enthalten — Fallback-Logik fuer fehlende id (AC-2 #436)"
	);
});

// AC-4a #436: 'void created' muss aus save() entfernt sein
test("AC-4a #436: save() darf 'void created' nicht mehr enthalten — wurde mit TODO(epic-135) entfernt", () => {
	const sourcePath = new URL('../wizardState.svelte.ts', import.meta.url);
	const source = readFileSync(sourcePath, 'utf-8');
	const saveBody = extractSaveMethod(source);

	assert.equal(
		saveBody.includes('void created'),
		false,
		"save() darf 'void created' nicht enthalten — created.id wird jetzt genutzt (AC-4 #436)"
	);
});

// AC-4b #436: TODO(epic-135)-Marker muss aus save() entfernt sein
test("AC-4b #436: save() darf 'TODO(epic-135)' nicht mehr enthalten — Cleanup-Marker aufgeloest", () => {
	const sourcePath = new URL('../wizardState.svelte.ts', import.meta.url);
	const source = readFileSync(sourcePath, 'utf-8');
	const saveBody = extractSaveMethod(source);

	assert.equal(
		saveBody.includes('TODO(epic-135)'),
		false,
		"save() darf 'TODO(epic-135)' nicht enthalten — Epic #135 ist abgeschlossen, Marker aufgeloest (AC-4 #436)"
	);
});
