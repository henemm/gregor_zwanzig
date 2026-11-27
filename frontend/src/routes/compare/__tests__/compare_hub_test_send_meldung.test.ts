// Issue #2216 (Adversary F003) — Ortsvergleich-Hub: bei Erfolg zeigt die Rückmeldung die Meldung des
// Versands (z. B. Hinweis auf fehlende Orte), nicht nur den festen Standardtext. Gemessen an der ECHTEN
// Seite (`+page.svelte`).
// #3440: umgestellt auf das Menü „Test schicken ▾“ — `handleTest({kanal, berichtsart})`, Standardtext ist
// die Einzel-Rückmeldung „Briefing an {Kanal} geschickt · {Ziel} · {hh:mm}“ (feat_3440 AC-11/AC-12).
//
// Ausfuehren: cd frontend && npm test -- src/routes/compare/__tests__/compare_hub_test_send_meldung.test.ts

import { test } from 'node:test';
import assert from 'node:assert/strict';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { umgebungFuer } from '../../../lib/components/shared/__tests__/svelteInstanzPruefstand.ts';

const SEITE = resolve(dirname(fileURLToPath(import.meta.url)), '../[id]/+page.svelte');
const PROFIL = { mail_to: 'wanderer@example.com', email_verified: true, telegram_chat_id: '42' };
const TELEGRAM = { kanal: 'telegram', berichtsart: 'morning' } as const;

async function hub(ergebnis: unknown) {
	const { u } = await umgebungFuer(SEITE, {
		data: { profile: PROFIL },
		currentPreset: { id: 'cmp-1' },
		sendSubscription: async () => ergebnis
	});
	return u;
}

test('ok mit Meldung -> Rückmeldung nennt zusätzlich die Meldung des Versands', async () => {
	const u = await hub({ kind: 'ok', message: 'Gesendet. 1 Ort fehlt: Alt-Ort' });
	await u.handleTest(TELEGRAM);
	assert.equal(u.sendStatus, 'ok');
	assert.match(u.sendMsg, /^Briefing an Telegram geschickt · verbunden · \d{2}:\d{2} · Gesendet\. 1 Ort fehlt: Alt-Ort$/);
	assert.equal(u.isSending, false);
});

test('ok ohne Meldung -> Standardtext ist die Einzel-Rückmeldung', async () => {
	const u = await hub({ kind: 'ok', message: '' });
	await u.handleTest(TELEGRAM);
	assert.equal(u.sendStatus, 'ok');
	assert.match(u.sendMsg, /^Briefing an Telegram geschickt · verbunden · \d{2}:\d{2}$/);
});

test('Fehler -> Fehlermeldung (rot, test-schicken-fehler)', async () => {
	const u = await hub({ kind: 'error', message: 'Versand fehlgeschlagen' });
	await u.handleTest(TELEGRAM);
	assert.equal(u.sendStatus, 'error');
	assert.equal(u.sendMsg, 'Versand fehlgeschlagen');
});
