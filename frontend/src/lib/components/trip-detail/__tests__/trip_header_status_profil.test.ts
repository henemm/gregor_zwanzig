// Issue #2837 Nachbesserung S1b (Epic #2345) — Adversary-Befunde F001/F002 an TripHeader.svelte.
// Spec: docs/specs/modules/rework_2837_s1b_status_profil.md — AC-2, AC-6, AC-7, AC-8.
//
// Echte Komponente TripHeader.svelte, serverseitig gerendert (svelte/server, Hooks aus dem
// F9-Prüfstand), OHNE die feste Uhr des Prüfstands (`mitUhr`): so ist beobachtbar, ob der
// Kopf den Status aus der Prop `now` ableitet oder aus der echten Uhr.
//
// Gefangene Mutationen:
//   F002  deriveTripStatus(trip, now) → deriveTripStatus(trip, new Date())
//         ⇒ „Status folgt now" rot (echte Uhr liegt nach den Etappen ⇒ finished).
//   F001  profileLabel = …?.label → …?.label ?? trip.activity
//         ⇒ „unbekannte Aktivität: kein Zusatz" rot („· unbekannt-xyz" erscheint).
//
// Pfadregel #1409: relativ zu DIESER Datei.
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types \
//     --experimental-test-module-mocks --test src/lib/components/trip-detail/__tests__/trip_header_status_profil.test.ts

import { test, describe, afterEach } from 'node:test';
import assert from 'node:assert/strict';
import path from 'node:path';
import { pathToFileURL } from 'node:url';
import { baum, mitTestid, einzig, text, type Knoten } from '../../shared/hub-kopf/__tests__/htmlBaum.ts';

// Der Prüfstand registriert die SSR-Hooks; Fixtures daraus.
const T = await import('./f9Pruefstand.ts');
const { render } = await import('svelte/server');
const TripHeader = (await import(pathToFileURL(path.join(T.TD, 'TripHeader.svelte')).href)).default;
const { locale, trFor } = T;

afterEach(() => locale.set('de'));

function kopf(trip: Record<string, unknown>, now: Date): Knoten {
	// eslint-disable-next-line @typescript-eslint/no-explicit-any
	const html = render(TripHeader as any, { props: { trip, now } }).body.replace(/<!--[\s\S]*?-->/g, '');
	return baum(html);
}

function schild(w: Knoten): Knoten {
	const s = mitTestid(w, 'trip-detail-status-badge');
	assert.equal(s.length, 1, `[data-testid=trip-detail-status-badge] ${s.length}× statt genau 1×`);
	return s[0];
}

describe('#2837 S1b F002 — TripHeader leitet den Status aus der Prop now ab (AC-2, AC-8)', () => {
	// Etappen 2026-07-01 … 2026-07-03; die echte Uhr liegt danach (Sitzung ≥ 2026-11).
	test('Messaufbau: die echte Uhr liegt nach den Etappen (sonst ist die Mutation unbeobachtbar)', () => {
		assert.ok(Date.now() > new Date('2026-07-04T00:00:00Z').getTime());
	});
	for (const [fall, now, erwartet] of [
		['now innerhalb der Etappen', new Date('2026-07-02T09:30:00Z'), 'active'],
		['now vor den Etappen', new Date('2026-06-01T09:30:00Z'), 'planned']
	] as const) {
		test(`${fall} ⇒ data-status „${erwartet}" und Text aus trip.status.${erwartet}`, () => {
			const s = schild(kopf(T.tripLaufend(), now));
			assert.equal(s.attrs['data-status'], erwartet, `Status ignoriert now? data-status „${s.attrs['data-status']}"`);
			assert.equal(text(s), trFor('de', `trip.status.${erwartet}`));
		});
	}
});

describe('#2837 S1b F001 — Profil-Zusatz nur für bekannte Aktivitäten (AC-6, AC-7)', () => {
	const hinterStift = (w: Knoten): Knoten | undefined => {
		const stift = einzig(w, 'trip-region-edit-toggle');
		const zeile = stift.eltern!;
		return zeile.kinder[zeile.kinder.indexOf(stift) + 1];
	};
	test('Messaufbau: bekannte Aktivität trekking ⇒ „· Trekking" hinter dem Region-Stift', () => {
		const z = hinterStift(kopf(T.tripLaufend(), T.JETZT));
		assert.equal(z && text(z), `· ${trFor('de', 'trip.aktivitaet.trekking')}`);
	});
	test('unbekannte Aktivität (nicht in der Optionsliste) ⇒ kein „·"-Zusatz, kein Rohwert', () => {
		const w = kopf(T.tripLaufend({ activity: 'unbekannt-xyz' }), T.JETZT);
		const z = hinterStift(w);
		assert.ok(!z || !text(z).startsWith('·'), `Zusatz „${z && text(z)}" hinter dem Region-Stift`);
		assert.ok(!text(w).includes('unbekannt-xyz'), 'Rohwert der Aktivität steht im Kopf');
	});
});
