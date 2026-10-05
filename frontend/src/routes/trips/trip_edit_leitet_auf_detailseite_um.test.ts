// Issue #2277 S3 (AC-8): /trips/<id>/edit leitet nach dem Rueckbau von
// TripEditView weiterhin per HTTP 307 auf die Trip-Detailseite um — keine
// Fehlerseite, kein Import auf geloeschte Dateien.
//
// Spec: docs/specs/modules/feat_2277_s3_reiter_angleichung_rueckbau.md (AC-8)
//
// Charakterisierungstest (darf im RED gruen ankommen): er bewacht, dass der
// Rueckbau den Redirect NICHT mitnimmt. Er ruft die ECHTE load-Funktion der
// Route auf; `redirect()` aus @sveltejs/kit wirft ein Redirect-Objekt mit
// `status`/`location`.
//
// Ausfuehren:
//   cd frontend && npm test -- src/routes/trips/trip_edit_leitet_auf_detailseite_um.test.ts

import { test } from 'node:test';
import assert from 'node:assert/strict';
import { existsSync } from 'node:fs';
import { fileURLToPath } from 'node:url';

const ROUTE = fileURLToPath(new URL('./[id]/edit/+page.server.ts', import.meta.url));

async function ladeUndFangeRedirect(id: string, search = ''): Promise<{ status: number; location: string }> {
	assert.ok(existsSync(ROUTE), 'AC-8 FAIL: routes/trips/[id]/edit/+page.server.ts existiert nicht mehr.');
	const { load } = (await import(ROUTE)) as {
		load: (e: { params: { id: string }; url: URL }) => unknown;
	};
	try {
		await load({ params: { id }, url: new URL(`https://x.invalid/trips/${id}/edit${search}`) });
	} catch (e) {
		const r = e as { status?: number; location?: string };
		assert.equal(typeof r.status, 'number', `AC-8 FAIL: load wirft keinen Redirect, sondern ${String(e)}`);
		return { status: r.status!, location: r.location! };
	}
	assert.fail('AC-8 FAIL: /trips/<id>/edit leitet nicht mehr um (load wirft keinen Redirect).');
}

test('AC-8: /trips/<id>/edit → 307 auf /trips/<id>', async () => {
	const r = await ladeUndFangeRedirect('khw-2026');
	assert.equal(r.status, 307, 'AC-8 FAIL: Redirect-Status ist nicht 307.');
	assert.equal(r.location, '/trips/khw-2026', 'AC-8 FAIL: Redirect zeigt nicht auf die Trip-Detailseite.');
});

test('AC-8: ?tab= wird an die Detailseite durchgereicht', async () => {
	const r = await ladeUndFangeRedirect('khw-2026', '?tab=wertebereiche');
	assert.equal(r.status, 307);
	assert.equal(r.location, '/trips/khw-2026?tab=wertebereiche');
});
