// Issue #2346 S2 Fix-Loop (Adversary F001/F002, AC-1/AC-18) — die Startseite verdrahtet den
// naechsten Versand dort, wo er WIRKT: jede Trip-Kachel liest ihren Eintrag aus
// `nextBriefings.trips` (nie aus `compare`), traegt kind "trip" und zeigt bei `at === null`
// den Trip-Grund. Gerendert wird die echte Startseite (svelte/server) mit `data.nextBriefings`.
//
// Gift-Eintrag: `compare` enthaelt dieselbe Trip-ID mit anderer Uhrzeit — liest die Seite die
// falsche Map, erscheint 09:00 statt 08:00. Alle Pruefungen laufen im Teilbaum der Kachel,
// weil Hero/Zeilen der Seite ebenfalls Versandzeiten zeigen.
//
// Ausfuehren:
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types \
//     --experimental-test-module-mocks --test src/routes/__tests__/startseite_kachel_versand_verdrahtung.test.ts

import { test, describe, before } from 'node:test';
import assert from 'node:assert/strict';
import { renderStartseite, aktiverVergleich, kuenftigerTrip, teilbaum, sichtbar } from './onboardingSsr.ts';

const NB = (local_time: string) => ({
	at: `2026-10-22T${local_time}:00+02:00`,
	local_date: '2026-10-22',
	local_time,
	tz: 'Europe/Paris',
	tz_abbr: 'CEST',
	slot: 'morning'
});

function kachel(html: string, id: string): string {
	const k = teilbaum(html, `subscription-card-${id}`);
	assert.ok(k, `Messaufbau: Kachel ${id} fehlt auf der Startseite`);
	return k;
}

// (Kein laufender Trip: Compare-Modus mit p1 als Hero; t2/t3 sind die weiteren Trip-Kacheln.)
describe('F001/AC-18: Trip-Kachel der Startseite liest den naechsten Versand aus nextBriefings.trips', () => {
	// F004: Render im before()-Hook — ein Wurf beim Rendern macht die Tests rot (Exit != 0),
	// statt im describe()-Rumpf still unterzugehen.
	let html = '';
	before(() => {
		html = renderStartseite({
			trips: [kuenftigerTrip('t2'), kuenftigerTrip('t3')],
			presets: [aktiverVergleich('p1')],
			nextBriefings: {
				trips: { t2: NB('08:00'), t3: { at: null, reason: 'ended' } },
				compare: { t2: NB('09:00'), t3: NB('10:00'), p1: NB('07:00') }
			}
		});
	});

	test('Wert aus `trips`, nicht aus dem gleichnamigen `compare`-Eintrag', () => {
		const k = kachel(html, 't2');
		const feld = /data-field="next-send"[^>]*>([^<]*)</.exec(k)?.[1] ?? '';
		assert.match(feld, /Do 08:00 \(CEST\)/, `naechster Versand: ${sichtbar(k)}`);
		assert.doesNotMatch(k, /09:00/, 'Wert aus der Vergleichs-Map gelesen');
	});

	test('die Kachel traegt kind "trip" und verlinkt auf den Trip-Hub', () => {
		const k = kachel(html, 't2');
		assert.match(k, /data-kind="trip"/);
		assert.match(k, /<a[^>]*href="\/trips\/t2"/);
	});

	test('at === null mit Grund "ended": "Trip beendet" (nie "Ortsvergleich beendet")', () => {
		const t = sichtbar(kachel(html, 't3'));
		assert.match(t, /Trip beendet/, t);
		assert.doesNotMatch(t, /Ortsvergleich beendet|10:00/, t);
	});
});

// Trip mit heutiger Etappe => Hero-Modus "trip" (kuenftigerTrip liegt 20 Tage voraus).
function heuteTrip(id: string): Record<string, unknown> {
	const h = new Date();
	const iso = `${h.getFullYear()}-${String(h.getMonth() + 1).padStart(2, '0')}-${String(h.getDate()).padStart(2, '0')}`;
	return { id, name: 'Heute-Trip', stages: [{ id: `${id}-s1`, name: 'E1', date: iso, waypoints: [] }], display_config: {} };
}

// Gift: `trips` enthaelt dieselbe Vergleichs-ID mit 09:00 — liest die Seite die falsche Map
// (oder gar keine), erscheint 09:00 bzw. "—" statt 07:00.
function pruefeVergleichsKachel(html: string, id: string) {
	const k = kachel(html, id);
	assert.match(k, /data-kind="vergleich"/);
	const feld = /data-field="next-send"[^>]*>([^<]*)</.exec(k)?.[1] ?? '';
	assert.match(feld, /Do 07:00 \(CEST\)/, `naechster Versand: ${sichtbar(k)}`);
	assert.doesNotMatch(k, /09:00/, 'Wert aus der Trip-Map gelesen');
}

describe('AC-1/AC-18: Vergleiche erscheinen als Startseiten-Kachel mit Versand aus nextBriefings.compare', () => {
	test('Trip-Modus: nebenher laufender Vergleich ist eine Kachel kind "vergleich"', () => {
		const html = renderStartseite({
			trips: [heuteTrip('t1')],
			presets: [aktiverVergleich('p1')],
			nextBriefings: { trips: { t1: NB('08:00'), p1: NB('09:00') }, compare: { p1: NB('07:00') } }
		});
		assert.ok(sichtbar(html).includes('Was geht raus'), 'Messaufbau: Trip-Hero fehlt');
		pruefeVergleichsKachel(html, 'p1');
	});

	test('Compare-Modus: der zweite Vergleich (erster ist Hero) ist eine Kachel kind "vergleich"', () => {
		const html = renderStartseite({
			trips: [],
			presets: [aktiverVergleich('p1'), aktiverVergleich('p2')],
			nextBriefings: { trips: { p2: NB('09:00') }, compare: { p1: NB('06:00'), p2: NB('07:00') } }
		});
		pruefeVergleichsKachel(html, 'p2');
	});

	// fix-1452 AC-8 am Wirkort: Kanal-Chips zeigen das Label, nie die rohe empfaenger-Adresse;
	// Telegram nur bei send_telegram.
	test('Kanal-Chips der Vergleichs-Kachel: "Email" statt Adresse, Telegram nur mit Opt-in', () => {
		const ADRESSE = 'henning@henemm.com';
		const mit = (extra: Record<string, unknown>) =>
			kachel(
				renderStartseite({ trips: [heuteTrip('t1')], presets: [{ ...aktiverVergleich('p1'), empfaenger: [ADRESSE], ...extra }], nextBriefings: null }),
				'p1'
			);
		const ohne = mit({});
		const kanaele = (h: string) => [...h.matchAll(/data-channel="([^"]+)"/g)].map((m) => m[1]);
		assert.ok(!sichtbar(ohne).includes(ADRESSE), sichtbar(ohne));
		assert.ok(kanaele(ohne).includes('Email'), JSON.stringify(kanaele(ohne)));
		assert.ok(!kanaele(ohne).includes('Telegram'), JSON.stringify(kanaele(ohne)));
		assert.ok(kanaele(mit({ send_telegram: true })).includes('Telegram'));
	});
});
