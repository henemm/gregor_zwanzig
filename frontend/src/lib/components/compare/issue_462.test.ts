// TDD RED: Issue #462 — Compare-Screen: Atomic-Migration (ui/ → atoms/)
//
// Spec:      docs/specs/modules/issue_462_compare_atomic_migration.md
// Verzeichnis: frontend/src/lib/components/compare/
//
// Source-Inspection-Tests (analog zu routes/trips/issue_402.test.ts):
// Liest die echten .svelte-Quelldateien als String und prüft, ob die
// Import-Migration von ui/ auf atoms/ korrekt umgesetzt wurde.
//
// Ausführung:
//   cd frontend && node --experimental-strip-types --test src/lib/components/compare/issue_462.test.ts

import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { join, dirname } from 'node:path';

const COMPARE_DIR = dirname(fileURLToPath(import.meta.url));

// ── Zu prüfende Dateien ────────────────────────────────────────────────────────
// Issue #1256 Scheibe 1 (2026-07-13): AutoReportCard.svelte, AutoReportsOverview.svelte
// und LocationsRail.svelte wurden als verifizierter Totcode gelöscht (kein
// produktiver Import mehr, Spec Zeilen 303-305) — Einträge entfernt.
// Issue #1256 Scheibe 4 (2026-07-14): Step3Idealwerte.svelte (Totcode) und
// Step4Layout.svelte (redundante Hülle um den geteilten LayoutTab-Organism)
// wurden gelöscht — Einträge entfernt.
// Epic #1301 Scheibe F3 (#1206, 2026-07-19/20): SavePresetDialog.svelte wurde
// als referenzloser Totcode gelöscht — Eintrag entfernt.
// Issue #1350 Teil 3 (2026-07-24): HourlyMatrix.svelte + CompareMatrix.svelte
// (bestaetigter Totcode) wurden geloescht — Eintrag entfernt.
// Issue #1232 Scheibe 2b / #1360: Step5Versand.svelte und CompareInhaltSection.svelte
// geloescht — Einträge entfernt.
// #3384 S4: die letzten beiden Einträge CreateGroupDialog.svelte und
// LocationPreviewMap.svelte sind als Waisen gelöscht. Damit ist die Liste der
// migrierten Dateien leer (0 Dateien); die drei Prüfungen, die nur über diese
// Liste liefen (AC-1 atoms-Import, AC-1 kein ui/-Import, AC-3 Hex-Farben), sind
// mit ihr entfallen, statt leer weiterzulaufen. Die Hex-Farb- und ui/-Regeln
// für alle Bausteine bewacht bausteine_waechter.test.ts.

function readFile(path: string): string {
	return readFileSync(path, 'utf-8');
}

// ── AC-1: Scope-Grenze — nicht-migrierbare ui/-Importe bleiben erhalten ──────

test('AC-1: Komponenten ohne Atom-Pendant (Dialog, Table, Checkbox) bleiben in ui/', () => {
	// Issue #1350 Teil 3: CompareMatrix.svelte (Card-NS-Beispiel) wurde als
	// bestaetigter Totcode geloescht — der Card-Check entfaellt ersatzlos.
	// Issue #1277: CompareGrid.svelte wurde gelöscht (Desktop-Übersicht läuft
	// jetzt über das geteilte ListTable-Organism). Der ConfirmDialog-Wrapper
	// (Löschen/Senden) lebt seitdem direkt in routes/compare/+page.svelte —
	// dort wird die ui/dialog-Kapselung weiterhin über das Molecule geprüft.
	const comparePage = readFile(
		join(COMPARE_DIR, '..', '..', '..', 'routes', 'compare', '+page.svelte')
	);
	assert.ok(
		comparePage.includes('ConfirmDialog'),
		'compare/+page.svelte: ConfirmDialog-Molecule-Import fehlt (Wrapper um ui/dialog)'
	);
});
