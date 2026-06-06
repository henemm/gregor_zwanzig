// TDD RED — Bug #626: compareActions Toggle-Label + send-Aktion entfernen
//
// Spec: docs/specs/bugfix/bug_626_compare_menu_actions.md
//
// Prüft das Soll-Verhalten nach Fix:
//   - compareActions('active') → Label 'Pausieren' für id='pause'
//   - compareActions('paused') → Label 'Aktivieren' für id='pause'
//   - compareActions('active') enthält KEIN 'send'-Item (AC-6)
//   - compareActions('active') enthält weiterhin: edit, preview, archive, delete
//   - compareActions('draft') bleibt unverändert (setup + delete, 2 Einträge)
//
// RED-Erwartung (vor Fix):
//   - Label-Toggle-Test FAIL (immer 'Pausieren')
//   - send-Removal-Test FAIL ('send' noch vorhanden)
//
// Ausführen:
//   cd frontend && node --experimental-strip-types --test \
//     src/lib/components/compare/__tests__/bug_626_compare_menu_actions.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';

// Direkter Funktionsaufruf — kein Mock, kein DOM
const { compareActions } = await import('../subscriptionHelpers.ts');

// ── AC-2/AC-3: Toggle-Label kontextabhängig ───────────────────────────────────

describe('Bug #626 AC-2: compareActions("active") — Label "Pausieren"', () => {
	test('enthält genau ein Item mit id="pause"', () => {
		const actions = compareActions('active');
		const pauseItems = actions.filter((a: { id: string }) => a.id === 'pause');
		assert.equal(pauseItems.length, 1, 'compareActions("active") muss genau ein "pause"-Item enthalten');
	});

	test('pause-Item hat label "Pausieren" bei Status active', () => {
		const actions = compareActions('active');
		const pause = actions.find((a: { id: string }) => a.id === 'pause');
		assert.ok(pause, 'compareActions("active") muss ein "pause"-Item enthalten');
		assert.equal(
			pause!.label,
			'Pausieren',
			`compareActions("active").pause.label muss "Pausieren" sein, ist aber "${pause!.label}"`
		);
	});
});

describe('Bug #626 AC-3: compareActions("paused") — Label "Aktivieren"', () => {
	test('enthält genau ein Item mit id="pause"', () => {
		const actions = compareActions('paused');
		const pauseItems = actions.filter((a: { id: string }) => a.id === 'pause');
		assert.equal(pauseItems.length, 1, 'compareActions("paused") muss genau ein "pause"-Item enthalten');
	});

	test('pause-Item hat label "Aktivieren" bei Status paused', () => {
		const actions = compareActions('paused');
		const pause = actions.find((a: { id: string }) => a.id === 'pause');
		assert.ok(pause, 'compareActions("paused") muss ein "pause"-Item enthalten');
		assert.equal(
			pause!.label,
			'Aktivieren',
			`compareActions("paused").pause.label muss "Aktivieren" sein, ist aber "${pause!.label}"`
		);
	});
});

// ── AC-6: send-Aktion entfernt ────────────────────────────────────────────────

describe('Bug #626 AC-6: compareActions — keine "send"-Aktion mehr', () => {
	test('compareActions("active") enthält KEIN Item mit id="send"', () => {
		const actions = compareActions('active');
		const sendItem = actions.find((a: { id: string }) => a.id === 'send');
		assert.equal(
			sendItem,
			undefined,
			'compareActions("active") darf kein "send"-Item enthalten (verschoben nach #627)'
		);
	});

	test('compareActions("paused") enthält KEIN Item mit id="send"', () => {
		const actions = compareActions('paused');
		const sendItem = actions.find((a: { id: string }) => a.id === 'send');
		assert.equal(
			sendItem,
			undefined,
			'compareActions("paused") darf kein "send"-Item enthalten (verschoben nach #627)'
		);
	});
});

// ── Regressions-Schutz: edit, preview, archive, delete bleiben vorhanden ──────

describe('Bug #626 AC-7 Regression: Pflicht-Aktionen bleiben erhalten', () => {
	test('compareActions("active") enthält "edit"', () => {
		const actions = compareActions('active');
		const ids = actions.map((a: { id: string }) => a.id);
		assert.ok(ids.includes('edit'), 'compareActions("active") muss "edit" enthalten');
	});

	test('compareActions("active") enthält "preview"', () => {
		const actions = compareActions('active');
		const ids = actions.map((a: { id: string }) => a.id);
		assert.ok(ids.includes('preview'), 'compareActions("active") muss "preview" enthalten');
	});

	test('compareActions("active") enthält "archive"', () => {
		const actions = compareActions('active');
		const ids = actions.map((a: { id: string }) => a.id);
		assert.ok(ids.includes('archive'), 'compareActions("active") muss "archive" enthalten');
	});

	test('compareActions("active") enthält "delete"', () => {
		const actions = compareActions('active');
		const ids = actions.map((a: { id: string }) => a.id);
		assert.ok(ids.includes('delete'), 'compareActions("active") muss "delete" enthalten');
	});

	test('compareActions("active") liefert genau 5 Einträge (ohne send)', () => {
		const actions = compareActions('active');
		assert.equal(
			actions.length,
			5,
			`compareActions("active") muss genau 5 Aktionen liefern (pause, preview, edit, archive, delete), hat aber ${actions.length}`
		);
	});

	test('compareActions("paused") liefert genau 5 Einträge', () => {
		const actions = compareActions('paused');
		assert.equal(
			actions.length,
			5,
			`compareActions("paused") muss genau 5 Aktionen liefern, hat aber ${actions.length}`
		);
	});
});

// ── Draft bleibt unverändert ──────────────────────────────────────────────────

describe('Bug #626: compareActions("draft") unverändert', () => {
	test('compareActions("draft") liefert genau 2 Einträge', () => {
		const actions = compareActions('draft');
		assert.equal(actions.length, 2, 'compareActions("draft") muss genau 2 Aktionen liefern');
	});

	test('compareActions("draft") enthält "setup" und "delete"', () => {
		const actions = compareActions('draft');
		const ids = actions.map((a: { id: string }) => a.id);
		assert.ok(ids.includes('setup'), 'compareActions("draft") muss "setup" enthalten');
		assert.ok(ids.includes('delete'), 'compareActions("draft") muss "delete" enthalten');
	});
});
