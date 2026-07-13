// Bug #626: compareActions Toggle-Label (+ #627: "send" wieder aufgenommen)
//
// Spec: docs/specs/bugfix/bug_626_compare_menu_actions.md
//
// Issue #1256 Scheibe 1 (2026-07-13): 'archive' aus dem Listen-Kebab entfernt
// (Soll molecules.jsx:1018-1027) — Archivieren ist ab Scheibe 3 exklusiv Teil
// der Hub-Header-Lifecycle-Liste. Erwartungen hier auf 5 statt 6 Einträge
// nachgezogen (Spec Scheibe-1-Dateiliste).
//
// Prüft das aktuelle Soll-Verhalten:
//   - compareActions('active') → Label 'Pausieren' für id='pause'
//   - compareActions('paused') → Label 'Aktivieren' für id='pause'
//   - compareActions('active'/'paused') enthält 'send'-Item (#627, Einzel-Sofortversand)
//   - compareActions('active') enthält weiterhin: edit, preview, delete — NICHT mehr archive
//   - compareActions('draft') bleibt unverändert (setup + delete, 2 Einträge)
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

// ── #627 (closed): "send" wieder aufgenommen ──────────────────────────────────
// Ursprünglich entfernte #626 die "send"-Aktion; #627 hat sie als echten
// Einzel-Sofortversand wieder eingeführt (siehe subscriptionHelpers.ts:215,219).

describe('#627: compareActions — "send"-Aktion wieder vorhanden', () => {
	test('compareActions("active") enthält genau ein Item mit id="send"', () => {
		const actions = compareActions('active');
		const sendItems = actions.filter((a: { id: string }) => a.id === 'send');
		assert.equal(
			sendItems.length,
			1,
			'compareActions("active") muss ein "send"-Item enthalten (#627)'
		);
	});

	test('compareActions("paused") enthält genau ein Item mit id="send"', () => {
		const actions = compareActions('paused');
		const sendItems = actions.filter((a: { id: string }) => a.id === 'send');
		assert.equal(
			sendItems.length,
			1,
			'compareActions("paused") muss ein "send"-Item enthalten (#627)'
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

	test('compareActions("active") enthält "delete"', () => {
		const actions = compareActions('active');
		const ids = actions.map((a: { id: string }) => a.id);
		assert.ok(ids.includes('delete'), 'compareActions("active") muss "delete" enthalten');
	});

	// Issue #1256 Scheibe 1: 'archive' entfernt (wandert in Hub-Lifecycle-Kebab, Scheibe 3)
	test('compareActions("active") enthält KEIN "archive" mehr', () => {
		const actions = compareActions('active');
		const ids = actions.map((a: { id: string }) => a.id);
		assert.ok(!ids.includes('archive'), 'compareActions("active") darf "archive" nicht mehr enthalten (#1256 Scheibe 1)');
	});

	// #627: "send" wieder aufgenommen; #1256 Scheibe 1: 'archive' entfernt
	// -> 5 statt 6 Einträge (pause, send, preview, edit, delete)
	test('compareActions("active") liefert genau 5 Einträge', () => {
		const actions = compareActions('active');
		assert.equal(
			actions.length,
			5,
			`compareActions("active") muss genau 5 Aktionen liefern (pause, send, preview, edit, delete), hat aber ${actions.length}`
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
