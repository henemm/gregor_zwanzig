// Issue #2359 AC-9 — 409 id_conflict kommt als deutsche Meldung beim Nutzer an
// und loest KEIN Konflikt-Banner aus (das ist 412 vorbehalten).
// Spec: docs/specs/modules/id_eindeutigkeit_trip_vergleich_2359.md
//
// Der Ersatz fuer `globalThis.fetch` antwortet mit dem festgelegten
// Server-Vertrag (echte `Response`, Status, JSON-Rumpf) — er ist Gegenspieler,
// kein Spiegel: geprueft wird, was `api.ts` daraus macht. Die Meldung wird wie
// im GPX-Upload (`+page.svelte`, Speicherfehler) als `detail ?? error`
// gebildet.

import { test, describe, beforeEach, afterEach } from 'node:test';
import assert from 'node:assert/strict';

import { api } from '../api.ts';
import { clearEtagRegistry, istKonflikt } from '../etagRegistry.ts';

const DETAIL = 'Ein Ortsvergleich trägt bereits diese Kennung — bitte anderen Namen wählen.';

const originalFetch = globalThis.fetch;

function antworte(status: number, body: Record<string, unknown>) {
	globalThis.fetch = (async () =>
		new Response(JSON.stringify(body), {
			status,
			headers: { 'Content-Type': 'application/json' }
		})) as typeof fetch;
}

/** Meldung exakt wie im GPX-Upload-Speicherpfad gebildet. */
function meldung(e: unknown): string | undefined {
	return (e as { detail?: string })?.detail ?? (e as { error?: string })?.error;
}

async function fange(p: Promise<unknown>): Promise<unknown> {
	try {
		await p;
	} catch (e) {
		return e;
	}
	assert.fail('Anfrage haette mit einem Fehler enden muessen');
}

beforeEach(() => clearEtagRegistry());
afterEach(() => {
	globalThis.fetch = originalFetch;
	clearEtagRegistry();
});

describe('AC-9: 409 id_conflict beim Trip-Anlegen', () => {
	test('POST /api/trips mit 409 liefert den deutschen detail-Text als Meldung', async () => {
		antworte(409, { error: 'id_conflict', detail: DETAIL });

		const e = await fange(api.post('/api/trips', { id: 'zillertal', name: 'Zillertal' }));

		assert.equal((e as { status?: number }).status, 409);
		assert.equal((e as { error?: string }).error, 'id_conflict');
		assert.equal(meldung(e), DETAIL, 'der Nutzer muss den deutschen Text sehen, nicht den Code');
	});

	test('409 auf einem Ressourcenpfad markiert KEINEN Konflikt', async () => {
		antworte(409, { error: 'id_conflict', detail: DETAIL });

		const e = await fange(api.put('/api/trips/zillertal', { name: 'Zillertal' }));

		assert.equal((e as { status?: number }).status, 409);
		assert.equal(meldung(e), DETAIL);
		assert.equal(istKonflikt('zillertal'), false, '409 darf kein Konflikt-Banner ausloesen');
	});

	test('Kontrolle: 412 auf demselben Pfad markiert den Konflikt', async () => {
		antworte(412, { error: 'precondition_failed', detail: 'veraltet' });

		await fange(api.put('/api/trips/zillertal', { name: 'Zillertal' }));

		assert.equal(istKonflikt('zillertal'), true, 'Beobachtungskanal: 412 muss den Konflikt markieren');
	});
});
