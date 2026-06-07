// TDD RED — Issue #627: "Briefing jetzt senden" wieder im Kebab-Menü.
//
// Spec: docs/specs/modules/issue_627_631_compare_send_rhythm.md (AC-5)
//
// SOLL-Verhalten nach Fix:
//   - compareActions('active') enthält wieder ein Item
//     { id: 'send', label: 'Briefing jetzt senden' } (oben, vor 'preview').
//
// RED-Erwartung (vor Fix): das 'send'-Item wurde in #626 entfernt
//   (compareActions hat aktuell kein 'send') → Test schlägt fehl.
//
// Ausführen:
//   cd frontend && node --experimental-strip-types --test \
//     src/lib/components/compare/__tests__/issue_627_send_action.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';

const { compareActions } = await import('../subscriptionHelpers.ts');

describe('Issue #627 AC-5: compareActions enthält "send"-Aktion', () => {
	test('compareActions("active") enthält ein Item mit id="send"', () => {
		const actions = compareActions('active');
		const send = actions.find((a: { id: string }) => a.id === 'send');
		assert.ok(
			send,
			'compareActions("active") muss ein "send"-Item enthalten (Briefing-Sofortversand, #627)'
		);
	});

	test('send-Item trägt Label "Briefing jetzt senden"', () => {
		const actions = compareActions('active');
		const send = actions.find((a: { id: string }) => a.id === 'send');
		assert.ok(send, 'compareActions("active") muss ein "send"-Item enthalten');
		assert.equal(
			send!.label,
			'Briefing jetzt senden',
			`send-Label muss "Briefing jetzt senden" sein, ist aber "${send!.label}"`
		);
	});

	test('send steht vor preview im Menü (oben einsortiert)', () => {
		const actions = compareActions('active');
		const ids = actions.map((a: { id: string }) => a.id);
		const sendIdx = ids.indexOf('send');
		const previewIdx = ids.indexOf('preview');
		assert.ok(sendIdx >= 0, 'send muss vorhanden sein');
		assert.ok(previewIdx >= 0, 'preview muss vorhanden sein');
		assert.ok(
			sendIdx < previewIdx,
			`send (${sendIdx}) muss vor preview (${previewIdx}) stehen`
		);
	});

	test('send-Item ist auch bei status "paused" verfügbar (Sofortversand ignoriert Zeitplan)', () => {
		const actions = compareActions('paused');
		const send = actions.find((a: { id: string }) => a.id === 'send');
		assert.ok(
			send,
			'compareActions("paused") muss ein "send"-Item enthalten (AC-3: pausiert trotzdem sendbar)'
		);
	});
});
