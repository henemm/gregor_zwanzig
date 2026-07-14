// TDD RED — Issue #1256 Scheibe 3: Hub-Header-Kebab auf Lifecycle umstellen.
//
// Spec: docs/specs/modules/issue_1256_compare_ui_rewire.md § Scheibe 3 (AC-5)
//
// Verifizierte Ausgangslage (Spec-Phase): `CompareKebab.svelte:27` speist sich
// AUSSCHLIESSLICH aus `compareActions(status)` — sowohl Liste als auch
// Hub-Header nutzen dieselbe Funktion. Der JSX-Soll kennt zwei getrennte
// Aktionsmengen: `compareActions` (Liste) und `CHub_lifecycleActions`
// (`screen-compare-detail.jsx:27-33`, NUR Hub-Header). Diese Datei testet die
// neue, noch nicht existierende `compareLifecycleActions()` — der Import
// schlägt heute fehl (RED), bis Phase 6 sie in subscriptionHelpers.ts ergänzt.
//
// Soll-Kontrakt (JSX Z.27-33):
//   draft  → [{ id: 'trash', label: 'Entwurf löschen', danger: true }]           (1 Eintrag)
//   active → [{ id: 'pause',  label: 'Pausieren' },
//             { id: 'archive', label: 'Archivieren' },
//             { id: 'trash',   label: 'Löschen', danger: true }]                (3 Einträge)
//   paused → [{ id: 'resume', label: 'Aktivieren' },
//             { id: 'archive', label: 'Archivieren' },
//             { id: 'trash',   label: 'Löschen', danger: true }]                (3 Einträge)
//
// Reine Verhaltenstests (echter Funktionsaufruf, KEIN Mock, KEINE
// Datei-Inhalt-Prüfung).
//
// Ausführen:
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types --test \
//     src/lib/components/compare/__tests__/compare_hub_lifecycle_actions.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';

// Direkter Funktionsaufruf — kein Mock, kein DOM.
const { compareLifecycleActions, compareActions } = await import('../subscriptionHelpers.ts');

describe('AC-5: compareLifecycleActions("active") — 3 Einträge (pause, archive, trash)', () => {
	test('liefert genau 3 Einträge', () => {
		const actions = compareLifecycleActions('active');
		assert.equal(
			actions.length,
			3,
			`compareLifecycleActions("active") muss genau 3 Aktionen liefern (Pausieren, Archivieren, Löschen), hat aber ${actions.length}`
		);
	});

	test('erster Eintrag ist "pause" mit Label "Pausieren"', () => {
		const actions = compareLifecycleActions('active');
		assert.equal(actions[0]?.id, 'pause', 'erster Eintrag muss id="pause" haben');
		assert.equal(actions[0]?.label, 'Pausieren', 'Label muss "Pausieren" sein bei Status active');
	});

	test('enthält "archive" mit Label "Archivieren"', () => {
		const actions = compareLifecycleActions('active');
		const archive = actions.find((a: { id: string }) => a.id === 'archive');
		assert.ok(archive, 'compareLifecycleActions("active") muss ein "archive"-Item enthalten');
		assert.equal(archive!.label, 'Archivieren');
	});

	test('enthält "trash" mit Label "Löschen" und danger=true', () => {
		const actions = compareLifecycleActions('active');
		const trash = actions.find((a: { id: string }) => a.id === 'trash');
		assert.ok(trash, 'compareLifecycleActions("active") muss ein "trash"-Item enthalten');
		assert.equal(trash!.label, 'Löschen');
		assert.equal(trash!.danger, true, '"trash" muss danger=true tragen (destruktive Aktion)');
	});
});

describe('AC-5: compareLifecycleActions("paused") — 3 Einträge (resume, archive, trash)', () => {
	test('liefert genau 3 Einträge', () => {
		const actions = compareLifecycleActions('paused');
		assert.equal(actions.length, 3);
	});

	test('erster Eintrag ist "resume" mit Label "Aktivieren"', () => {
		const actions = compareLifecycleActions('paused');
		assert.equal(actions[0]?.id, 'resume', 'erster Eintrag muss id="resume" haben bei Status paused');
		assert.equal(actions[0]?.label, 'Aktivieren');
	});

	test('enthält weiterhin "archive" und "trash"', () => {
		const actions = compareLifecycleActions('paused');
		const ids = actions.map((a: { id: string }) => a.id);
		assert.ok(ids.includes('archive'), 'muss "archive" enthalten');
		assert.ok(ids.includes('trash'), 'muss "trash" enthalten');
	});
});

describe('AC-5: compareLifecycleActions("draft") — genau 1 Eintrag (trash)', () => {
	test('liefert genau 1 Eintrag', () => {
		const actions = compareLifecycleActions('draft');
		assert.equal(
			actions.length,
			1,
			`compareLifecycleActions("draft") muss genau 1 Aktion liefern, hat aber ${actions.length}`
		);
	});

	test('einziger Eintrag ist "trash" mit Label "Entwurf löschen" und danger=true', () => {
		const actions = compareLifecycleActions('draft');
		assert.equal(actions[0]?.id, 'trash');
		assert.equal(actions[0]?.label, 'Entwurf löschen');
		assert.equal(actions[0]?.danger, true);
	});

	test('enthält KEIN "archive" bei draft (Archivieren nur für active/paused)', () => {
		const actions = compareLifecycleActions('draft');
		const ids = actions.map((a: { id: string }) => a.id);
		assert.ok(!ids.includes('archive'), 'draft darf kein "archive"-Item haben');
	});
});

describe('AC-5: Trennschärfe Hub-Lifecycle vs. Listen-Kebab (KL-7-Auflösung)', () => {
	test('compareLifecycleActions("active") enthält KEIN "edit"/"preview"/"send" (bleiben Listen-/Tab-exklusiv)', () => {
		const actions = compareLifecycleActions('active');
		const ids = actions.map((a: { id: string }) => a.id);
		assert.ok(!ids.includes('edit'), 'Hub-Lifecycle darf kein "edit" enthalten — Bearbeiten läuft über Tabs');
		assert.ok(!ids.includes('preview'), 'Hub-Lifecycle darf kein "preview" enthalten — eigene Primäraktion/Tab');
		assert.ok(!ids.includes('send'), 'Hub-Lifecycle darf kein "send" enthalten — eigene Primäraktion');
	});

	test('compareActions("active") (Listen-Kebab) enthält weiterhin KEIN "archive" (Regressionsanker #1256 S1)', () => {
		// Referenziert den bereits in Scheibe 1 abgesicherten Vertrag
		// (bug_626_compare_menu_actions.test.ts) — hier nur als Kontrastprobe zur
		// neuen Lifecycle-Liste, keine Duplikation der vollständigen Suite.
		const listActions = compareActions('active');
		const ids = listActions.map((a: { id: string }) => a.id);
		assert.ok(!ids.includes('archive'), 'Listen-Kebab darf "archive" weiterhin nicht enthalten');
	});

	test('"archive" ist NUR in compareLifecycleActions, nicht in compareActions vorhanden — genau EINE Oberfläche', () => {
		const lifecycleIds = compareLifecycleActions('active').map((a: { id: string }) => a.id);
		const listIds = compareActions('active').map((a: { id: string }) => a.id);
		assert.ok(lifecycleIds.includes('archive'), 'compareLifecycleActions muss "archive" enthalten');
		assert.ok(!listIds.includes('archive'), 'compareActions darf "archive" nicht enthalten');
	});
});
