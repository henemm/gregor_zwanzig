// TDD RED — Issue #1969 (Nächstes Briefing), AC-23 / AC-24 (Startseite).
// SPEC: docs/specs/modules/feat_1969_naechstes_briefing.md
//
// Die Startseiten-Helfer in routes/_home/cockpitHelpers.ts lesen den
// Backend-Wert `NextBriefing` statt selbst zu rechnen:
//   homeCompareTimeline(preset, nextBriefing)            — vorher (preset, now: Date)
//   plannedBriefings(rc, sentLog, tripId, nextBriefing)  — neuer 4. Parameter
//
// AC-24-Gegenprobe: Der Ortsvergleich hat send_time 07:30, das Backend sagt
// local_time "07:00". Würde noch eine Frontend-Rechnung greifen (deriveNextSend,
// Browser-Zone, Minuten), erschiene 07:30 bzw. eine Los-Angeles-Zeit — rot.
//
// Ausführen:
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types \
//     --experimental-test-module-mocks --test \
//     src/routes/_home/__tests__/naechster_versand_aus_backend.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { fileURLToPath, pathToFileURL } from 'node:url';
import path from 'node:path';

process.env.TZ = 'America/Los_Angeles';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const { homeCompareTimeline, plannedBriefings } = await import(pathToFileURL(path.join(HERE, '..', 'cockpitHelpers.ts')).href);

const PRESET = {
	id: 'cp-1969',
	name: 'Vergleich 07:30',
	location_ids: ['l1', 'l2', 'l3'],
	schedule: 'daily',
	morning_enabled: true,
	morning_time: '07:30:00',
	evening_enabled: false,
	created_at: '2026-01-01T00:00:00Z'
};

// Do 22.10.2026, 07:00 Europe/Paris (CEST) = Mi 21.10. 22:00 in Los Angeles.
const NB_07 = {
	at: '2026-10-22T07:00:00+02:00',
	local_date: '2026-10-22',
	local_time: '07:00',
	tz: 'Europe/Paris',
	tz_abbr: 'CEST',
	slot: 'morning'
};

describe('AC-23/AC-24: homeCompareTimeline liest den Backend-Wert', () => {
	test('send_time 07:30 + Backend 07:00 (CEST) → „Nächster · …" zeigt Do 07:00 (CEST)', () => {
		const rows = homeCompareTimeline(PRESET, NB_07);
		const next = rows.find((r: { when: string }) => r.when.startsWith('Nächster · '));
		assert.ok(next, `keine Nächster-Zeile: ${JSON.stringify(rows)}`);
		assert.ok(next.when.includes('Do 07:00 (CEST)'), `Backend-Zeit fehlt: ${next.when}`);
		assert.ok(!next.when.includes('07:30'), `Minuten-Fiktion 07:30 sichtbar: ${next.when}`);
		assert.ok(!next.when.includes('22:00'), `Browser-Zone sichtbar: ${next.when}`);
		assert.equal(next.status, 'planned');
	});

	test('Backend sagt „kein Termin" (pausiert) bei daily-Preset → keine selbst errechnete Nächster-Zeile', () => {
		// daily + Slot 07:30 wäre für eine Frontend-Rechnung „berechenbar" — das
		// Backend weiß es besser (Pause, end_date, archiviert) und gewinnt.
		const rows = homeCompareTimeline(PRESET, { at: null, reason: 'paused', paused_until: '2026-10-28' });
		assert.ok(rows.every((r: { when: string }) => !r.when.startsWith('Nächster')), JSON.stringify(rows));
	});

	test('Backend-Wert fehlt (nicht geladen) → keine Nächster-Zeile, keine eigene Rechnung', () => {
		const rows = homeCompareTimeline(PRESET, undefined);
		assert.ok(rows.every((r: { when: string }) => !r.when.startsWith('Nächster')), JSON.stringify(rows));
	});
});

describe('AC-23/AC-24: plannedBriefings (Trip-Hero „Was geht raus") nimmt den Backend-Wert', () => {
	const RC = {
		enabled: true,
		morning_enabled: true,
		evening_enabled: true,
		morning_time: '07:30:00',
		evening_time: '18:00:00',
		send_email: true
	};

	test('Zeile des Backend-Slots zeigt local_time + Kürzel aus dem Backend', () => {
		const rows = plannedBriefings(RC, [], 't-1', NB_07);
		const morgen = rows.find((r: { kind: string }) => r.kind === 'morgen');
		assert.ok(morgen, JSON.stringify(rows));
		assert.ok(morgen.when.startsWith('07:00'), `Backend-Zeit fehlt: ${morgen.when}`);
		assert.ok(morgen.when.includes('CEST'), `Zonenkürzel fehlt: ${morgen.when}`);
	});

	test('mit Backend-Wert keine Minuten-Fiktion in irgendeiner Zeile (Versand = HH:00)', () => {
		const rows = plannedBriefings(RC, [], 't-1', NB_07);
		assert.ok(rows.length > 0);
		for (const r of rows as Array<{ when: string }>) {
			assert.match(r.when, /^\d{2}:00\b/, `Zeile zeigt Minuten ≠ 00: ${r.when}`);
		}
	});
});
