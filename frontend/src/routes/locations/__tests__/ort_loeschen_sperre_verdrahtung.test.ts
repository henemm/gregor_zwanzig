// Issue #2216 (Adversary F002) — Verdrahtung der Ort-Loeschen-Sperre auf der Seite.
// `ortInUseHinweis` selbst ist in ortLoeschenSperre.test.ts gemessen; hier wird
// gemessen, dass `handleDelete` der ECHTEN Seite den 409 in den Hinweis `inUse`
// uebersetzt (statt in die Fehlerzeile) und den Ort dabei NICHT aus der Liste nimmt.
//
// Ausfuehren: cd frontend && npm test -- src/routes/locations/__tests__/ort_loeschen_sperre_verdrahtung.test.ts

import { test } from 'node:test';
import assert from 'node:assert/strict';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { umgebungFuer } from '../../../lib/components/shared/__tests__/svelteInstanzPruefstand.ts';

const SEITE = resolve(dirname(fileURLToPath(import.meta.url)), '../+page.svelte');
const ORT = { id: 'loc-x', name: 'Ort X' };

async function seite(del: () => Promise<unknown>) {
	const { u } = await umgebungFuer(SEITE, {
		data: { locations: [ORT] },
		api: { del }
	});
	u.deleteTarget = ORT;
	return u;
}

test('409 location_in_use -> Hinweis gesetzt, keine Fehlerzeile, Ort bleibt in der Liste', async () => {
	const u = await seite(async () => {
		throw { status: 409, error: 'location_in_use', compare_presets: [{ id: 'cmp-1', name: 'Mein Vergleich' }] };
	});
	await u.handleDelete();
	assert.ok(u.inUse, 'inUse muss gesetzt sein');
	assert.match(String(u.inUse.text), /Mein Vergleich|Ortsvergleich/);
	assert.equal(u.inUse.links[0].href.includes('cmp-1'), true);
	assert.equal(u.error, null);
	assert.equal(u.locations.length, 1);
});

test('anderer Fehler -> Fehlerzeile, kein Hinweis', async () => {
	const u = await seite(async () => {
		throw { status: 500, error: 'store_error' };
	});
	await u.handleDelete();
	assert.equal(u.inUse, null);
	assert.equal(u.error, 'store_error');
});

test('Erfolg -> Ort aus der Liste entfernt', async () => {
	const u = await seite(async () => undefined);
	await u.handleDelete();
	assert.equal(u.locations.length, 0);
	assert.equal(u.inUse, null);
});
