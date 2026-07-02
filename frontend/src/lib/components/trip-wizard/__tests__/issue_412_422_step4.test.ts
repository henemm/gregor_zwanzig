// Issue #412 (BLOCKER) + #422 (MEDIUM): Trip-Wizard Step Reports.
//
// HINWEIS — Aktualisierung durch Issue #432 (PR 4/Epic #428):
//   - Datei Step4Reports.svelte → Step5Reports.svelte umbenannt.
//   - Die „DEINE KANÄLE"-Sammelkarte ist durch PO-Entscheidung 2026-05-28
//     entfernt (siehe `docs/specs/modules/issue_432_step3_step5_polish.md`).
//   - AC-1, AC-3, AC-4, AC-5, AC-9 aus #412/#422 sind damit **nicht mehr
//     gültig** und wurden hier entfernt. Die neuen Acceptance-Kriterien
//     werden in `issue_432_step5_reports.test.ts` abgebildet.
//
// AKTIV BLEIBEN:
//   - AC-2: maskPhone-Helfer (wird weiter in Step5Reports genutzt) — echter
//     Verhaltens-Test (Funktionsaufruf, kein Mock).
//
// Die ursprünglichen AC-6/AC-7/AC-8-Tests (readFileSync-Source-Inspection
// gegen wizardState.svelte.ts / Step5Reports.svelte / +page.server.ts /
// +page.svelte) wurden entfernt — Dateiinhalt-Checks sind laut CLAUDE.md
// verboten (Präzedenz #893).
//
// Ausführung:
//   cd frontend && node --experimental-strip-types --test \
//     src/lib/components/trip-wizard/__tests__/issue_412_422_step4.test.ts

import { test } from 'node:test';
import assert from 'node:assert/strict';

// ───────────────────────────────────────────────────────────────────────────
// AC-2: maskPhone-Helfer (Telefon maskiert, letzte 4 Ziffern sichtbar)
// ───────────────────────────────────────────────────────────────────────────

test('AC-2: maskPhone ist exportiert und maskiert SOLL-konform', async () => {
	const helpers = (await import('../wizardHelpers.ts')) as {
		maskPhone?: (v?: string | null) => string;
	};
	assert.equal(typeof helpers.maskPhone, 'function', 'maskPhone muss exportiert sein');

	const out = helpers.maskPhone!('+49 151 23 45 8847');
	assert.ok(out.includes('•••'), `Maskierungs-Token "•••" fehlt in "${out}"`);
	assert.ok(out.endsWith('8847'), `letzte 4 Ziffern müssen sichtbar bleiben: "${out}"`);
	assert.ok(out.startsWith('+49'), `Länder-Präfix sollte erhalten bleiben: "${out}"`);
	assert.notEqual(out, '+49 151 23 45 8847', 'die Nummer darf nicht unverändert durchgereicht werden');
});

test('AC-2: maskPhone gibt bei leerem/fehlendem Wert "" zurück', async () => {
	const helpers = (await import('../wizardHelpers.ts')) as {
		maskPhone?: (v?: string | null) => string;
	};
	assert.equal(typeof helpers.maskPhone, 'function', 'maskPhone muss exportiert sein');
	assert.equal(helpers.maskPhone!(''), '');
	assert.equal(helpers.maskPhone!(undefined), '');
	assert.equal(helpers.maskPhone!(null), '');
});
