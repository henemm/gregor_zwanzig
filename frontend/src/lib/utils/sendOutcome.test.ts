// TDD RED — Issue #2124 AC-2, AC-3, AC-4: geteiltes Versand-Ergebnis- und
// Laufzustands-Modul für ALLE Versand-Auslöser (Trip + Ortsvergleich).
//
// Spec: docs/specs/modules/fix_2124_versand_nginx_timeout.md (§4, AC-2..AC-4)
//
// Vertrag, den `./sendOutcome.ts` exakt so exportieren muss:
//
//   export type SendOutcomeKind = 'ok' | 'already_running' | 'unclear' | 'rejected' | 'failed';
//   export type SendResponseInput =
//     | { status: number; detail?: string | null }   // HTTP-Antwort (detail = Backend-`detail`, falls vorhanden)
//     | { networkError: true };                       // fetch hat geworfen (kein HTTP-Status)
//   export function classifySendResponse(input: SendResponseInput): { kind: SendOutcomeKind; message: string };
//
//   export const SEND_UNCLEAR_MESSAGE =
//     'Ergebnis unklar — Versand kann noch laufen, nicht erneut senden';
//
//   export function beginSend(key: string): boolean; // false, wenn für key schon ein Versand läuft
//   export function endSend(key: string): void;
//   export function isSending(key: string): boolean;  // für gesperrte Auslöser (Dialog nach Wieder-Öffnen)
//
// Schlüssel-Konvention: `trip:<tripId>` bzw. `compare:<presetId>`.
//
// Erwartung je Eingang (Tabelle aus der Spec):
//   2xx                         -> ok
//   409                         -> already_running, message „Versand läuft bereits"
//   502 / 503 / 504 / Netzfehler -> unclear, message === SEND_UNCLEAR_MESSAGE (nie „fehlgeschlagen")
//   übrige 4xx                  -> rejected, message = Backend-detail
//   übrige 5xx                  -> failed, generische Meldung („fehlgeschlagen")
//
// Das Modul wird je Test DYNAMISCH importiert, damit heute (Modul fehlt) jeder
// Test einzeln rot wird statt die ganze Datei an einem Import scheitern zu lassen.
//
// Ausführung:
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types \
//     --experimental-test-module-mocks --test src/lib/utils/sendOutcome.test.ts

import { test } from 'node:test';
import assert from 'node:assert/strict';

const UNCLEAR = 'Ergebnis unklar — Versand kann noch laufen, nicht erneut senden';

async function mod() {
	return await import('./sendOutcome.ts');
}

// ---------------------------------------------------------------------------
// AC-2: Klassifikation
// ---------------------------------------------------------------------------

test('AC-2: 200 ist ok (tatsächliches Ergebnis, keine Fehlermeldung)', async () => {
	const { classifySendResponse } = await mod();
	assert.equal(classifySendResponse({ status: 200 }).kind, 'ok');
	assert.equal(classifySendResponse({ status: 204 }).kind, 'ok');
});

test('AC-2: 409 ist already_running mit „Versand läuft bereits"', async () => {
	const { classifySendResponse } = await mod();
	const r = classifySendResponse({ status: 409, detail: 'Versand für evening läuft bereits — bitte warten' });
	assert.equal(r.kind, 'already_running');
	assert.match(r.message, /Versand läuft bereits/);
});

for (const status of [502, 503, 504]) {
	test(`AC-2: ${status} ist unclear — „Ergebnis unklar", nie „fehlgeschlagen"`, async () => {
		const { classifySendResponse, SEND_UNCLEAR_MESSAGE } = await mod();
		assert.equal(SEND_UNCLEAR_MESSAGE, UNCLEAR);
		const r = classifySendResponse({ status, detail: null });
		assert.equal(r.kind, 'unclear');
		assert.equal(r.message, UNCLEAR);
		assert.doesNotMatch(r.message, /fehlgeschlagen/i);
	});
}

test('AC-2: Netzfehler ({ networkError: true }) ist unclear', async () => {
	const { classifySendResponse } = await mod();
	const r = classifySendResponse({ networkError: true });
	assert.equal(r.kind, 'unclear');
	assert.equal(r.message, UNCLEAR);
});

test('AC-2: 422 ist rejected und zeigt die Backend-detail-Meldung', async () => {
	const { classifySendResponse } = await mod();
	const r = classifySendResponse({ status: 422, detail: 'SMTP not configured for this user' });
	assert.equal(r.kind, 'rejected');
	assert.equal(r.message, 'SMTP not configured for this user');
});

test('AC-2: 500 ist failed mit generischer Meldung ohne Rohtext', async () => {
	const { classifySendResponse } = await mod();
	const r = classifySendResponse({ status: 500, detail: 'Traceback: KeyError secret' });
	assert.equal(r.kind, 'failed');
	assert.match(r.message, /fehlgeschlagen/);
	assert.doesNotMatch(r.message, /Traceback|KeyError|secret/);
});

// ---------------------------------------------------------------------------
// AC-3: Laufzustand je Schlüssel
// ---------------------------------------------------------------------------

test('AC-3: zweites beginSend für denselben Schlüssel liefert false', async () => {
	const { beginSend, endSend } = await mod();
	const key = 'trip:ac3-gleich';
	try {
		assert.equal(beginSend(key), true, 'erster Versand muss starten dürfen');
		assert.equal(beginSend(key), false, 'zweiter Versand während des ersten muss gesperrt sein');
	} finally {
		endSend(key);
	}
});

test('AC-3: nach endSend ist ein bewusster neuer Versand wieder möglich', async () => {
	const { beginSend, endSend, isSending } = await mod();
	const key = 'compare:ac3-wieder';
	assert.equal(beginSend(key), true);
	assert.equal(isSending(key), true);
	endSend(key);
	assert.equal(isSending(key), false);
	assert.equal(beginSend(key), true, 'nach Abschluss muss ein neuer Versand erlaubt sein');
	endSend(key);
});

test('AC-3: verschiedene Schlüssel blockieren einander nicht (auch Trip vs. Compare mit gleicher ID)', async () => {
	const { beginSend, endSend } = await mod();
	try {
		assert.equal(beginSend('trip:ac3-a'), true);
		assert.equal(beginSend('trip:ac3-b'), true, 'anderer Trip darf parallel senden');
		assert.equal(beginSend('compare:ac3-a'), true, 'Ortsvergleich mit gleicher ID ist ein anderer Schlüssel');
	} finally {
		endSend('trip:ac3-a');
		endSend('trip:ac3-b');
		endSend('compare:ac3-a');
	}
});

// ---------------------------------------------------------------------------
// AC-4: Zustand liegt im Modul, nicht in der Dialog-Instanz
// ---------------------------------------------------------------------------

/** Minimale „Dialog-Instanz": eigener lokaler Zustand, Auslöser über das geteilte Modul. */
function dialogInstanz(m: Awaited<ReturnType<typeof mod>>, tripId: string) {
	let offen = true;
	return {
		ausloeserGesperrt: () => m.isSending(`trip:${tripId}`),
		senden: () => m.beginSend(`trip:${tripId}`),
		schliessen: () => {
			offen = false;
		},
		get offen() {
			return offen;
		}
	};
}

test('AC-4: Dialog schließen + neu öffnen — Auslöser bleibt gesperrt, bis der erste Versand endet', async () => {
	const m1 = await mod();
	const tripId = 'ac4-dialog';
	const ersterDialog = dialogInstanz(m1, tripId);
	assert.equal(ersterDialog.senden(), true, 'erster Versand startet');
	ersterDialog.schliessen();
	assert.equal(ersterDialog.offen, false, 'Dialog bleibt während des Laufs schließbar');

	// Neu geöffneter Dialog = neue Instanz, eigener Import des Moduls.
	const m2 = await mod();
	const zweiterDialog = dialogInstanz(m2, tripId);
	try {
		assert.equal(zweiterDialog.ausloeserGesperrt(), true, 'neue Dialog-Instanz muss den laufenden Versand sehen');
		assert.equal(zweiterDialog.senden(), false, 'zweiter Versand für denselben Trip muss gesperrt sein');
	} finally {
		m1.endSend(`trip:${tripId}`);
	}
	assert.equal(zweiterDialog.ausloeserGesperrt(), false, 'nach Abschluss ist der Auslöser wieder frei');
	assert.equal(zweiterDialog.senden(), true);
	m2.endSend(`trip:${tripId}`);
});

// ---------------------------------------------------------------------------
// #2216 AC-7: sendComparePreset reicht fehlende_orte durch
// ---------------------------------------------------------------------------

function antwort(status: number, body: unknown): typeof fetch {
	return (async () => new Response(JSON.stringify(body), { status })) as unknown as typeof fetch;
}

test('AC-7: Test-Versand mit fehlenden Orten -> fehlendeOrte + Hinweis in der Meldung', async () => {
	const { sendComparePreset } = await mod();
	const r = await sendComparePreset(
		'cmp-fehlt-2216',
		antwort(200, { status: 'ok', fehlende_orte: ['loc-weg'] }),
	);
	assert.equal(r.kind, 'ok');
	assert.deepEqual((r as { fehlendeOrte?: string[] }).fehlendeOrte, ['loc-weg']);
	assert.match(r.message, /Orte fehlten|fehlen/i, `Meldung nennt fehlende Orte: ${r.message}`);
});

test('AC-7: Test-Versand ohne fehlende Orte -> unveränderte (leere) ok-Meldung', async () => {
	const { sendComparePreset } = await mod();
	const r = await sendComparePreset('cmp-komplett-2216', antwort(200, { status: 'ok' }));
	assert.equal(r.kind, 'ok');
	assert.equal(r.message, '');
	assert.ok(!((r as { fehlendeOrte?: string[] }).fehlendeOrte?.length));
});
