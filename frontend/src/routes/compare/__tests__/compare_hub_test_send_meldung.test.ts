// Issue #2216 (Adversary F003) — Ortsvergleich-Hub: `handleTestSend` zeigt bei
// Erfolg die Meldung des Versands (z. B. Hinweis auf fehlende Orte), nicht nur
// den festen Standardtext. Gemessen an der ECHTEN Seite (`+page.svelte`).
//
// Ausfuehren: cd frontend && npm test -- src/routes/compare/__tests__/compare_hub_test_send_meldung.test.ts

import { test } from 'node:test';
import assert from 'node:assert/strict';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { umgebungFuer } from '../../../lib/components/shared/__tests__/svelteInstanzPruefstand.ts';

const SEITE = resolve(dirname(fileURLToPath(import.meta.url)), '../[id]/+page.svelte');

async function hub(ergebnis: unknown) {
	const { u } = await umgebungFuer(SEITE, {
		data: {},
		currentPreset: { id: 'cmp-1' },
		sendComparePreset: async () => ergebnis
	});
	return u;
}

test('ok mit Meldung -> Meldung des Versands wird angezeigt', async () => {
	const u = await hub({ kind: 'ok', message: 'Gesendet. 1 Ort fehlt: Alt-Ort' });
	await u.handleTestSend();
	assert.equal(u.sendMsg, 'Gesendet. 1 Ort fehlt: Alt-Ort');
	assert.equal(u.isSending, false);
});

test('ok ohne Meldung -> Standardtext', async () => {
	const u = await hub({ kind: 'ok', message: '' });
	await u.handleTestSend();
	assert.equal(u.sendMsg, 'Test-Briefing gesendet');
});

test('Fehler -> Fehlermeldung', async () => {
	const u = await hub({ kind: 'error', message: 'Versand fehlgeschlagen' });
	await u.handleTestSend();
	assert.equal(u.sendMsg, 'Versand fehlgeschlagen');
});
