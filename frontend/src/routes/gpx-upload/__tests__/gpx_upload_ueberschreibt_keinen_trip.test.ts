// Issue #2612 (Epic #2138): Ein GPX-Upload darf keinen gleichnamigen eigenen Trip
// ueberschreiben. POST /api/trips ist ein Upsert; eine aus dem Namen abgeleitete
// Kennung ("GR20" -> "gr20") ersetzte still den bestehenden Trip samt Etappen.
// Geprueft wird die echte Nutzlast-Funktion der Seite (baueGpxTrip) und der echte
// Namens-Pruefhelfer (gpxNameFehler) — kein Mock.
// Spec: docs/specs/fast/fix-2612-gpx-upload-id.md
//
//   cd frontend && npm test -- src/routes/gpx-upload/__tests__/gpx_upload_ueberschreibt_keinen_trip.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { pathToFileURL, fileURLToPath } from 'node:url';
import path from 'node:path';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const gpxTrip = () => import(pathToFileURL(path.join(HERE, '..', 'gpxTrip.ts')).href);

const ETAPPE = {
	name: 'Calenzana – Ortu di u Piobbu',
	date: '2026-06-01',
	waypoints: [{ id: 'G1', name: 'Calenzana', lat: 42.50812, lon: 8.85543, elevation_m: 275 }]
};

describe('AC-2: gleicher Trip-Name ergibt verschiedene, nicht aus dem Namen abgeleitete Kennungen', () => {
	test('zwei Uploads „GR20" tragen zwei verschiedene 8-Zeichen-Kennungen', async () => {
		const { baueGpxTrip } = await gpxTrip();
		const a = baueGpxTrip('GR20', ETAPPE);
		const b = baueGpxTrip('GR20', ETAPPE);
		assert.notEqual(a.id, b.id, 'zweiter Upload mit gleichem Namen wuerde den ersten Trip per Upsert ersetzen');
		for (const t of [a, b]) {
			assert.equal(t.id.length, 8, `Kennung „${t.id}" hat nicht die Form des normalen Anlegens (newId, 8 Zeichen)`);
			assert.notEqual(t.id, 'gr20', 'Kennung ist aus dem Namen abgeleitet');
			assert.equal(t.stages[0].id, t.id + '-t1');
		}
	});

	test('Kennung ist auch bei laengeren Namen kein Namens-Slug', async () => {
		const { baueGpxTrip } = await gpxTrip();
		const t = baueGpxTrip('Mein Trip GR20 Sued', ETAPPE);
		assert.ok(!t.id.includes('mein'), `Kennung „${t.id}" enthaelt den Namen`);
		assert.equal(t.id.length, 8);
	});

	test('Nutzlast sonst unveraendert: Name exakt, genau eine Etappe aus dem GPX', async () => {
		const { baueGpxTrip } = await gpxTrip();
		const t = baueGpxTrip('  GR20 Süd  ', ETAPPE);
		assert.equal(t.name, '  GR20 Süd  ');
		assert.equal(t.stages.length, 1);
		assert.equal(t.stages[0].name, ETAPPE.name);
		assert.equal(t.stages[0].date, ETAPPE.date);
		assert.deepEqual(t.stages[0].waypoints, ETAPPE.waypoints);
	});
});

describe('AC-3: ungueltiger Trip-Name meldet weiterhin den Namenshinweis', () => {
	test('leer, nur Leerzeichen, nur Sonderzeichen -> layout.gpx.fehler_name; gueltiger Name -> null', async () => {
		const m = await gpxTrip();
		assert.equal(typeof m.gpxNameFehler, 'function', 'gpxNameFehler fehlt in gpxTrip.ts');
		for (const name of ['', '   ', '—!?', '!!!']) assert.equal(m.gpxNameFehler(name), 'layout.gpx.fehler_name', `Name „${name}"`);
		for (const name of ['GR20 Süd', 'a', '7']) assert.equal(m.gpxNameFehler(name), null, `Name „${name}"`);
	});
});
