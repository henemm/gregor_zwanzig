// Issue #1756 — AC-7: HTTP 409 ("already_in_progress") ist unterscheidbar von
// der generischen 5xx-Serverfehler-Meldung, OHNE automatischen Retry/Poll.
// Issue #2124: die Logik von handleTestBriefing() liegt jetzt im geteilten
// Modul `$lib/utils/sendOutcome` (sendTripBriefing) — dieser Test prüft das
// VERHALTEN dort statt den Quelltext der Seite (der frühere Quelltext-Grep auf
// `+page.svelte` ist entfallen).

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { sendTripBriefing } from '../../../../lib/utils/sendOutcome.ts';

function fetchMit(status: number, body: unknown) {
	const z = { aufrufe: 0 };
	const fn: typeof fetch = async () => {
		z.aufrufe += 1;
		return new Response(JSON.stringify(body), { status });
	};
	return { fn, z };
}

describe('AC-7: 409 "already_in_progress" ist unterscheidbar von 5xx, kein Retry', () => {
	test('409 zeigt „Versand läuft bereits" (nicht die Serverfehler-Meldung)', async () => {
		const h = fetchMit(409, { detail: 'Versand für morning läuft bereits — bitte warten' });
		const r = await sendTripBriefing('lock-409', 'morning', h.fn);
		assert.equal(r.kind, 'already_running');
		assert.match(r.message, /Versand läuft bereits/);
		assert.doesNotMatch(r.message, /Serverfehler/);
		assert.equal(h.z.aufrufe, 1, 'genau EIN fetch, kein automatischer Retry');
	});

	test('500 zeigt den rohen detail-Text NICHT', async () => {
		const h = fetchMit(500, { detail: 'Traceback: KeyError secret' });
		const r = await sendTripBriefing('lock-500', 'morning', h.fn);
		assert.equal(r.kind, 'failed');
		assert.doesNotMatch(r.message, /Traceback|KeyError|secret/);
		assert.equal(h.z.aufrufe, 1);
	});
});
