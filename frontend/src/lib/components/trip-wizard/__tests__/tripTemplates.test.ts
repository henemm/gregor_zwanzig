// TDD RED — Unit-Tests fuer tripTemplates.ts (Issue #165, Sub-Spec epic_136_step5_templates.md).
// Erwartet: FAIL (MODULE NOT FOUND) bis tripTemplates.ts angelegt ist.
//
// Ausfuehrung:
//   cd frontend && node --experimental-strip-types --test \
//     src/lib/components/trip-wizard/__tests__/tripTemplates.test.ts

// Svelte-5-Runen-Stubs (identisch mit wizardState.test.ts)
type RuneFn = (v: unknown) => unknown;
const g = globalThis as unknown as Record<string, RuneFn>;
if (typeof g.$state !== 'function') g.$state = (v: unknown) => v;
if (typeof g.$derived !== 'function') g.$derived = (v: unknown) => v;

import { test } from 'node:test';
import assert from 'node:assert/strict';

// Dieser Import schlaegt fehl bis tripTemplates.ts existiert (TDD RED).
import { TRIP_TEMPLATES } from '../templates/tripTemplates.ts';

// --- AC-1, AC-10: Template-Liste + Karten-Inhalte ----------------------------

test('TRIP_TEMPLATES enthaelt genau 3 Vorlagen (GR20, KHW, Stubai)', () => {
	assert.equal(TRIP_TEMPLATES.length, 3);
	const ids = TRIP_TEMPLATES.map((t) => t.id);
	assert.deepEqual(ids, ['gr20', 'khw', 'stubai']);
});

test('GR20-Vorlage hat 14 Etappen', () => {
	const gr20 = TRIP_TEMPLATES.find((t) => t.id === 'gr20');
	assert.ok(gr20, 'GR20-Vorlage fehlt');
	assert.equal(gr20.stages().length, 14);
});

test('KHW-Vorlage hat 13 Etappen (volle Route ab Troblach)', () => {
	const khw = TRIP_TEMPLATES.find((t) => t.id === 'khw');
	assert.ok(khw, 'KHW-Vorlage fehlt');
	assert.equal(khw.stages().length, 13);
});

test('Stubaier-Hoehenweg-Vorlage hat 7 Etappen', () => {
	const stubai = TRIP_TEMPLATES.find((t) => t.id === 'stubai');
	assert.ok(stubai, 'Stubai-Vorlage fehlt');
	assert.equal(stubai.stages().length, 7);
});

// --- AC-6: Koordinaten-Pruefung ------------------------------------------------

test('GR20 erste Etappe heisst "Calenzana -> Ortu di u Piobbu"', () => {
	const gr20 = TRIP_TEMPLATES.find((t) => t.id === 'gr20')!;
	const first = gr20.stages()[0];
	assert.match(first.name, /Calenzana/);
	assert.match(first.name, /Ortu/);
});

test('KHW erste Etappe hat korrekte Startkoordinaten (Troblach Bhf)', () => {
	const khw = TRIP_TEMPLATES.find((t) => t.id === 'khw')!;
	const first = khw.stages()[0];
	assert.ok(first.waypoints.length >= 1, 'Waypoints fehlen');
	const start = first.waypoints[0];
	assert.ok(Math.abs(start.lat - 46.72475) < 0.0001, `lat erwartet 46.72475, got ${start.lat}`);
	assert.ok(Math.abs(start.lon - 12.22542) < 0.0001, `lon erwartet 12.22542, got ${start.lon}`);
});

test('KHW letzte Etappe endet in Noetsch im Gailtal (lat ~46.59079)', () => {
	const khw = TRIP_TEMPLATES.find((t) => t.id === 'khw')!;
	const stages = khw.stages();
	const last = stages[stages.length - 1];
	const end = last.waypoints[last.waypoints.length - 1];
	assert.ok(Math.abs(end.lat - 46.59079) < 0.001, `lat erwartet 46.59079, got ${end.lat}`);
});

test('GR20 letzte Etappe endet in Conca (lat ~41.666)', () => {
	const gr20 = TRIP_TEMPLATES.find((t) => t.id === 'gr20')!;
	const stages = gr20.stages();
	const last = stages[stages.length - 1];
	const end = last.waypoints[last.waypoints.length - 1];
	assert.ok(Math.abs(end.lat - 41.666) < 0.01, `lat erwartet ~41.666, got ${end.lat}`);
});

// --- AC-7: Aktivitaet ----------------------------------------------------------

test('Alle Vorlagen haben activity="trekking"', () => {
	for (const tpl of TRIP_TEMPLATES) {
		assert.equal(tpl.activity, 'trekking', `${tpl.id} sollte trekking haben`);
	}
});

test('Alle Vorlagen haben nicht-leeren shortcode (max 20 Zeichen)', () => {
	for (const tpl of TRIP_TEMPLATES) {
		assert.ok(tpl.shortcode.trim().length > 0, `${tpl.id} hat leeren shortcode`);
		assert.ok(tpl.shortcode.length <= 20, `${tpl.id} shortcode zu lang`);
	}
});

// --- AC-13: Factory-Funktion — frische IDs -----------------------------------

test('stages() liefert jedes Mal neue Stage-IDs (Factory-Funktion)', () => {
	for (const tpl of TRIP_TEMPLATES) {
		const ids1 = tpl.stages().map((s) => s.id);
		const ids2 = tpl.stages().map((s) => s.id);
		for (let i = 0; i < ids1.length; i++) {
			assert.notEqual(
				ids1[i],
				ids2[i],
				`${tpl.id} stages()[${i}].id ist identisch bei zwei Aufrufen`
			);
		}
	}
});

// --- Jede Etappe hat genau 2 Waypoints (Start + End) -------------------------

test('Jede Etappe jeder Vorlage hat genau 2 Waypoints', () => {
	for (const tpl of TRIP_TEMPLATES) {
		for (const stage of tpl.stages()) {
			assert.equal(
				stage.waypoints.length,
				2,
				`${tpl.id} Etappe "${stage.name}" hat ${stage.waypoints.length} statt 2 Waypoints`
			);
		}
	}
});

// --- Koordinaten im gueltigen Bereich -----------------------------------------

test('Alle Koordinaten liegen im gueltigen GPS-Bereich', () => {
	for (const tpl of TRIP_TEMPLATES) {
		for (const stage of tpl.stages()) {
			for (const wp of stage.waypoints) {
				assert.ok(wp.lat >= -90 && wp.lat <= 90, `${tpl.id} lat=${wp.lat} ausserhalb`);
				assert.ok(wp.lon >= -180 && wp.lon <= 180, `${tpl.id} lon=${wp.lon} ausserhalb`);
			}
		}
	}
});

// --- AC-9: date ist leer (recomputeStageDates setzt Datum nach Aufruf) --------

test('Alle Vorlage-Etappen haben date="" (Datum wird spaeter gesetzt)', () => {
	for (const tpl of TRIP_TEMPLATES) {
		for (const stage of tpl.stages()) {
			assert.equal(
				stage.date,
				'',
				`${tpl.id} Etappe "${stage.name}" hat date="${stage.date}" statt ""`
			);
		}
	}
});

// --- Nicht-leere Etappen-Namen ------------------------------------------------

test('Alle Etappen aller Vorlagen haben nicht-leere Namen', () => {
	for (const tpl of TRIP_TEMPLATES) {
		for (const stage of tpl.stages()) {
			assert.ok(stage.name.trim().length > 0, `${tpl.id} hat Etappe mit leerem Namen`);
		}
	}
});
