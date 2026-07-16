// Kern-Test — Issue #1269 Fix-Loop 2/3 (Adversary F001/F002): DOM-Containment
// der Gesten-Capture-Listener (onpointerdowncapture/onkeydowncapture/
// onchangecapture/oninputcapture, s. onEditorTouchGesture/onEditorValueChange
// in CompareEditor.svelte).
//
// Svelte-5-Komponenten mit Snippet-Props sind in diesem Test-Setup nicht
// mountbar (kein @testing-library/svelte) — Source-Inspection-Tests sind das
// etablierte Projekt-Idiom für genau diese Klasse von Struktur-Prüfungen
// (Vorbild: compare_editor_layout_tab_wiring.test.ts, issue_683_wizard_remove.test.ts).
// Reines DOM-Verhalten wird ergänzend über Playwright (save-status-indicator-
// honesty.spec.ts, mobiler Viewport) gegen Staging abgesichert.
//
// Fix-Loop 2 (F001): die 4 Capture-Listener sassen urspruenglich auf dem
// AEUSSERSTEN Editor-Wrapper (Kopf/Aktionsleiste/Tab-Leiste eingeschlossen) —
// jeder Tab-Klick (echtes <button>) setzte faelschlich userTouched=true.
// Fix: Listener NUR um den Tab-Inhalt (Desktop + Mobile).
//
// Fix-Loop 3 (F002): das mobile "Ort waehlen"-Sheet (Issue #682) rendert als
// Geschwister NACH `.cm-mobile` (Sheet.svelte portalt seinen children-Snippet
// in eine eigene fixed-Overlay-DOM-Struktur) — lag dadurch AUSSERHALB des
// Fix-Loop-2-Wrappers. Fix: eigener Capture-Scope NUR um die Sheet-
// Checkbox-Liste (Sheet-Chrome/Close-Button bleiben aussen).
//
// Ausführung:
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types --test \
//     src/lib/components/compare/__tests__/compare_editor_gesture_capture_scope.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const here = dirname(fileURLToPath(import.meta.url));
const COMPARE_EDITOR = join(here, '..', 'CompareEditor.svelte');

function readSrc(): string {
	return readFileSync(COMPARE_EDITOR, 'utf-8');
}

const CAPTURE_ATTRS = [
	'onpointerdowncapture={onEditorTouchGesture}',
	'onkeydowncapture={onEditorTouchGesture}',
	'onchangecapture={onEditorValueChange}',
	'oninputcapture={onEditorValueChange}'
];

function hasAllCaptureAttrs(region: string): boolean {
	return CAPTURE_ATTRS.every((a) => region.includes(a));
}

describe('AC-6/AC-7: der Aeusserste Editor-Wrapper (Kopf/Aktionsleiste/Tab-Leiste) traegt KEINE Gesten-Capture mehr (Fix-Loop 2)', () => {
	test('data-testid="compare-editor"-Wrapper-Tag selbst hat keine Capture-Attribute (nur der Tab-Inhalt darunter)', () => {
		const src = readSrc();
		const wrapperMatch = src.match(/<div\s+data-testid="compare-editor"[\s\S]*?>/);
		assert.ok(wrapperMatch, 'compare-editor-Wrapper-Tag nicht gefunden');
		assert.ok(
			!hasAllCaptureAttrs(wrapperMatch![0]),
			'Der AEUSSERSTE compare-editor-Wrapper darf die Capture-Listener nicht mehr tragen — sonst faengt ' +
				'jeder Tab-Leisten-/Aktionsleisten-Klick (<button>) faelschlich als Nutzergeste (Fix-Loop-2-Regress)'
		);
	});
});

describe('AC-5 (Fix-Loop 3, F002): das mobile "Ort wählen"-Sheet liegt im Gesten-Capture-Scope', () => {
	test('der <Sheet>…</Sheet>-Children-Block traegt alle 4 Capture-Listener', () => {
		const src = readSrc();
		const sheetMatch = src.match(/<Sheet\s[\s\S]*?>([\s\S]*?)<\/Sheet>/);
		assert.ok(sheetMatch, '<Sheet>…</Sheet>-Block nicht gefunden');
		assert.ok(
			hasAllCaptureAttrs(sheetMatch![1]),
			'Der Inhalt des mobilen "Ort wählen"-Sheets muss die 4 Gesten-Capture-Listener tragen — sonst wird ' +
				'ein Ort-Toggle NUR über dieses Sheet nie als Nutzergeste erkannt (userTouched bleibt false, ' +
				'kein Auto-Save, AC-5-Verstoss auf Mobile)'
		);
	});

	test('die Orte-Checkbox-Buttons (compare-step2-mobile-lib-check-…) liegen INNERHALB des Sheet-Capture-Scopes', () => {
		const src = readSrc();
		const sheetMatch = src.match(/<Sheet\s[\s\S]*?>([\s\S]*?)<\/Sheet>/);
		assert.ok(sheetMatch);
		const sheetBody = sheetMatch![1];
		assert.ok(
			sheetBody.includes('compare-step2-mobile-lib-check-'),
			'Die Orte-Checkbox-Buttons muessen Teil des Sheet-Children-Blocks sein (Containment-Voraussetzung)'
		);
		// Containment-Nachweis: die Capture-Attribute muessen VOR dem ersten
		// Checkbox-Button im Quelltext stehen (d.h. auf einem umschliessenden
		// Vorfahren, nicht auf einem spaeteren Geschwister).
		const captureIdx = sheetBody.indexOf(CAPTURE_ATTRS[0]);
		const firstCheckboxIdx = sheetBody.indexOf('compare-step2-mobile-lib-check-');
		assert.ok(
			captureIdx >= 0 && captureIdx < firstCheckboxIdx,
			'Die Capture-Listener muessen VOR dem ersten Checkbox-Button auf einem umschliessenden Element stehen'
		);
	});
});

describe('Regressionsanker: Tab-Inhalt (Desktop + Mobile) traegt weiterhin die Capture-Listener (Fix-Loop 2, unveraendert)', () => {
	test('Desktop-Tab-Panel-Wrapper traegt alle 4 Capture-Listener', () => {
		const src = readSrc();
		assert.match(
			src,
			/<!-- Tab-Panel -->[\s\S]{0,600}?onpointerdowncapture=\{onEditorTouchGesture\}[\s\S]{0,200}?onkeydowncapture=\{onEditorTouchGesture\}[\s\S]{0,200}?onchangecapture=\{onEditorValueChange\}[\s\S]{0,200}?oninputcapture=\{onEditorValueChange\}/,
			'Der Desktop-Tab-Panel-Wrapper muss weiterhin alle 4 Capture-Listener tragen'
		);
	});

	test('Mobile-Tab-Inhalt-Wrapper ("4. Tab-Inhalt") traegt alle 4 Capture-Listener', () => {
		const src = readSrc();
		assert.match(
			src,
			/<!-- 4\. Tab-Inhalt -->[\s\S]{0,400}?onpointerdowncapture=\{onEditorTouchGesture\}[\s\S]{0,200}?onkeydowncapture=\{onEditorTouchGesture\}[\s\S]{0,200}?onchangecapture=\{onEditorValueChange\}[\s\S]{0,200}?oninputcapture=\{onEditorValueChange\}/,
			'Der Mobile-Tab-Inhalt-Wrapper muss weiterhin alle 4 Capture-Listener tragen'
		);
	});
});
