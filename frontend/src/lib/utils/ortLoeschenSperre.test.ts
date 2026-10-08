// TDD RED: Issue #2216 — Ort-Löschen-Sperre, Aufbereitung im Frontend.
//
// Spec: docs/specs/modules/fix_2216_ort_loeschen_sperre.md (AC-4, AC-7)
//
// Zwei reine Teile, per `node --test` prüfbar:
//   1. `ortInUseHinweis(fehler)` (neues Modul `ortLoeschenSperre.ts`): deutet den
//      von `api.del` geworfenen Fehlerkörper (flach: `{error, compare_presets, status}`).
//   2. `sendComparePreset` (sendOutcome.ts): reicht `fehlende_orte` aus der
//      200-Antwort als `fehlendeOrte` durch und hängt den Hinweis an die Meldung.
//
// Module werden je Test DYNAMISCH importiert, damit heute (Modul fehlt bzw. Feld
// fehlt) jeder Test einzeln rot wird.
//
// Ausführung:
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types \
//     --test src/lib/utils/ortLoeschenSperre.test.ts

import { test } from 'node:test';
import assert from 'node:assert/strict';

async function sperre() {
	return await import('./ortLoeschenSperre.ts');
}

test('AC-4: 409 location_in_use -> Namen, Hinweis und Link je Ortsvergleich', async () => {
	const { ortInUseHinweis } = await sperre();
	const h = ortInUseHinweis({
		status: 409,
		error: 'location_in_use',
		compare_presets: [
			{ id: 'cmp-1', name: 'Wochenende Tirol' },
			{ id: 'cmp-2', name: 'Sommer Dolomiten' },
		],
	});
	assert.ok(h, 'Hinweis erwartet');
	assert.match(h.text, /Dieser Ort wird noch in diesen Ortsvergleichen verwendet/);
	assert.match(h.text, /Wochenende Tirol/);
	assert.match(h.text, /Sommer Dolomiten/);
	assert.match(h.text, /Entferne ihn dort zuerst/);
	assert.deepEqual(
		h.links.map((l: { href: string; name: string }) => [l.href, l.name]),
		[
			['/compare/cmp-1', 'Wochenende Tirol'],
			['/compare/cmp-2', 'Sommer Dolomiten'],
		],
	);
});

test('AC-4: andere Fehler (kein location_in_use) liefern keinen Hinweis -> alter Text', async () => {
	const { ortInUseHinweis } = await sperre();
	assert.equal(ortInUseHinweis({ status: 500, error: 'store_error' }), null);
	assert.equal(ortInUseHinweis({ status: 409, error: 'etwas_anderes' }), null);
	assert.equal(ortInUseHinweis(undefined), null);
	assert.equal(ortInUseHinweis(null), null);
});

test('AC-4: location_in_use mit leerer Liste -> kein Hinweis (kein leerer Satz)', async () => {
	const { ortInUseHinweis } = await sperre();
	assert.equal(ortInUseHinweis({ status: 409, error: 'location_in_use', compare_presets: [] }), null);
});

function antwort(status: number, body: unknown): typeof fetch {
	return (async () => new Response(JSON.stringify(body), { status })) as unknown as typeof fetch;
}

test('AC-7: Test-Versand mit fehlenden Orten -> fehlendeOrte + Hinweis in der Meldung', async () => {
	const { sendComparePreset } = await import('./sendOutcome.ts');
	const r = await sendComparePreset(
		'cmp-fehlt-2216',
		antwort(200, { status: 'ok', fehlende_orte: ['loc-weg'] }),
	);
	assert.equal(r.kind, 'ok');
	assert.deepEqual((r as { fehlendeOrte?: string[] }).fehlendeOrte, ['loc-weg']);
	assert.match(r.message, /Orte fehlten|fehlen/i, `Meldung nennt fehlende Orte: ${r.message}`);
});

test('AC-7: Test-Versand ohne fehlende Orte -> unveränderte (leere) ok-Meldung', async () => {
	const { sendComparePreset } = await import('./sendOutcome.ts');
	const r = await sendComparePreset('cmp-komplett-2216', antwort(200, { status: 'ok' }));
	assert.equal(r.kind, 'ok');
	assert.equal(r.message, '');
	assert.ok(!((r as { fehlendeOrte?: string[] }).fehlendeOrte?.length));
});
