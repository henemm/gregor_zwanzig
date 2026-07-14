// TDD RED→GREEN — Issue #1234: Auto-Save im Inhalt-Tab darf Metriken nicht
// stillschweigend leeren.
//
// Spec: docs/specs/modules/issue_1234_autosave_hydration_gate.md
//   § Implementation Details (Entscheidungstabelle v1.2), § Acceptance Criteria
// Kausalkette: docs/context/fix-1234-mount-autosave-metrics.md
//
// Fix-Loop 1 (Adversary-Finding F001, Verdict BROKEN): die Vorgänger-Fassung
// dieser Testdatei prüfte die inzwischen entfernte Datenlage-Prüfung
// (`nextMetricIds`/`savedMetricIds`). Die Spec wurde korrigiert (v1.2) — das
// Gate entscheidet jetzt ausschließlich nach `catalogLoaded` + `userTouched`.
//
// Vorbild-Muster (Daten-Gate statt Timing-Guard):
//   shared/corridor-editor/corridorEditorState.ts:517-519 `saveGateDecision()`
//
// Reine Verhaltenstests (echter Funktionsaufruf, KEIN Mock, KEINE
// Datei-Inhalt-Prüfung).
//
// Ausführen:
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types --test \
//     src/lib/components/trip-detail/__tests__/weatherSaveGate.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';

// Direkter Funktionsaufruf — kein Mock, kein DOM.
const { weatherSaveGate } = await import('../weatherSaveGate.ts');

describe('Zeile 1 der Entscheidungstabelle: Katalog nicht geladen → immer "skip"', () => {
	test('AC-3: catalogLoaded=false, keine Nutzerinteraktion → "skip" (kein Editor, kein Schreibzugriff)', () => {
		const decision = weatherSaveGate({ catalogLoaded: false, userTouched: false });
		assert.equal(decision, 'skip', 'ohne geladenen Katalog darf niemals gespeichert werden');
	});

	test('AC-3: catalogLoaded=false, TROTZ userTouched=true → "skip" (nichts geladen = nichts speichern)', () => {
		const decision = weatherSaveGate({ catalogLoaded: false, userTouched: true });
		assert.equal(
			decision,
			'skip',
			'auch ein gesetzter Absichts-Merker darf ohne geladenen Katalog keinen Speichervorgang auslösen'
		);
	});
});

describe('Zeile 2 der Entscheidungstabelle: Katalog geladen, keine Nutzergeste → "skip" (F001/AC-6)', () => {
	test('AC-6/F001: catalogLoaded=true, userTouched=false → "skip" (der Bug: bloßes Ansehen darf nichts speichern)', () => {
		const decision = weatherSaveGate({ catalogLoaded: true, userTouched: false });
		assert.equal(
			decision,
			'skip',
			'F001: ein Schreibzugriff ohne echte Nutzergeste darf nie stattfinden — unabhängig davon, ob der ' +
				'Payload leer wäre oder nicht (z.B. Normalisierungs-Rückschreiben von EditReportConfigSection beim Mounten)'
		);
	});
});

describe('Zeile 3 der Entscheidungstabelle: Katalog geladen, Nutzer hat etwas getan → "save" (AC-4/AC-5)', () => {
	test('AC-5: catalogLoaded=true, userTouched=true (normale Nutzeränderung) → "save"', () => {
		const decision = weatherSaveGate({ catalogLoaded: true, userTouched: true });
		assert.equal(decision, 'save', 'eine echte Nutzeraktion muss wie bisher automatisch gespeichert werden');
	});

	test('AC-4: catalogLoaded=true, userTouched=true (bewusste Abwahl aller Metriken) → "save"', () => {
		// Die Gate-Regel unterscheidet nicht nach Datenlage — das Abwählen selbst
		// IST die Nutzergeste, die "save" auslöst (unabhängig davon, dass der
		// resultierende Payload leer ist).
		const decision = weatherSaveGate({ catalogLoaded: true, userTouched: true });
		assert.equal(
			decision,
			'save',
			'AC-4: bewusstes Abwählen aller Metriken muss weiterhin gespeichert werden können — die Geste selbst genügt'
		);
	});
});
