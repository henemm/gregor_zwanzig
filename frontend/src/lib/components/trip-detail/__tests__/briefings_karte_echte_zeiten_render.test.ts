// TDD RED — Issue #1969 (Nächstes Briefing), AC-20.
// SPEC: docs/specs/modules/feat_1969_naechstes_briefing.md
//
// Die Karte „Briefings laufen" in HubOverview.svelte zeigt heute fest
// 06:00/18:00. Soll: die echten Slot-Stunden (HH:00) des Trips und die Zone aus
// dem Backend-Wert. HubOverview bekommt dazu die neue, optionale Prop
// `nextBriefing?: NextBriefing | null` (aus GET /api/next-briefings?trip_id=,
// geladen in trips/[id]/+page.server.ts bzw. vom Hub durchgereicht).
//
// Hinweis zum Fixture: NextBriefing trägt nur EINEN Slot (den nächsten). Die
// zweite Stunde stammt aus trip.report_config (nur Stunde, wie der Scheduler,
// `_slot_stunde` nutzt nur `.hour`). Der Test erfindet kein Zwei-Slot-Feld.
//
// Echter SSR-Render (svelte/server), Prozess-Zone ≠ Trip-Zone.
//
// Ausführen:
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types \
//     --experimental-test-module-mocks --test \
//     src/lib/components/trip-detail/__tests__/briefings_karte_echte_zeiten_render.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { register } from 'node:module';
import { fileURLToPath, pathToFileURL } from 'node:url';
import path from 'node:path';

process.env.TZ = 'America/Los_Angeles';

const HERE = path.dirname(fileURLToPath(import.meta.url));
// __tests__ -> trip-detail -> components -> lib -> src -> frontend
const FRONTEND = path.resolve(HERE, '../../../../..');
register(pathToFileURL(path.join(FRONTEND, 'test-env-dynamic-private-stub-hooks.mjs')).href, pathToFileURL(FRONTEND + '/').href);
register(pathToFileURL(path.join(FRONTEND, 'test-app-environment-stub-hooks.mjs')).href, pathToFileURL(FRONTEND + '/').href);
register(pathToFileURL(path.join(FRONTEND, 'test-svelte-ssr-hooks.mjs')).href, pathToFileURL(FRONTEND + '/').href);

const { render } = await import('svelte/server');
const HubOverview = (await import(pathToFileURL(path.join(FRONTEND, 'src/lib/components/trip-detail/HubOverview.svelte')).href)).default;

function trip(morning: string, evening: string) {
	return {
		id: 't-1969',
		name: 'Testtrip',
		stages: [{ id: 's1', name: 'E1', date: '2026-10-22', waypoints: [] }],
		report_config: {
			enabled: true,
			morning_enabled: true,
			evening_enabled: true,
			morning_time: morning,
			evening_time: evening
		},
		display_config: {}
	};
}

const nb = (local_time: string, slot: 'morning' | 'evening') => ({
	at: `2026-10-22T${local_time}:00+02:00`,
	local_date: '2026-10-22',
	local_time,
	tz: 'Europe/Paris',
	tz_abbr: 'CEST',
	slot
});

/** Text der Karte „Briefings laufen" (bis zum Sprung „Zeitplan bearbeiten"). */
function karte(props: Record<string, unknown>): string {
	const html = render(HubOverview, { props }).body.replace(/<!--[\s\S]*?-->/g, '');
	const a = html.indexOf('Briefings laufen');
	assert.notEqual(a, -1, 'Messaufbau: Karte „Briefings laufen" fehlt');
	const b = html.indexOf('Zeitplan bearbeiten', a);
	assert.notEqual(b, -1, 'Messaufbau: „Zeitplan bearbeiten" fehlt');
	return html.slice(a, b).replace(/<[^>]*>/g, ' ').replace(/\s+/g, ' ');
}

describe('AC-20: Karte „Briefings laufen" zeigt echte Zeiten statt 06:00/18:00', () => {
	test('Trip 08:00/20:00 + Backend 08:00 (CEST) → 08:00 und 20:00, nie 06:00/18:00', () => {
		const k = karte({ trip: trip('08:00:00', '20:00:00'), nextBriefing: nb('08:00', 'morning') });
		assert.ok(k.includes('08:00'), `08:00 fehlt: ${k}`);
		assert.ok(k.includes('20:00'), `20:00 fehlt: ${k}`);
		assert.ok(!k.includes('06:00'), `fest verdrahtetes 06:00 sichtbar: ${k}`);
		assert.ok(!k.includes('18:00'), `fest verdrahtetes 18:00 sichtbar: ${k}`);
	});

	test('Zonenkürzel stammt aus dem Backend-Wert (CEST), nicht aus der Browser-Zone', () => {
		const k = karte({ trip: trip('08:00:00', '20:00:00'), nextBriefing: nb('08:00', 'morning') });
		assert.ok(k.includes('CEST'), `Zonenkürzel fehlt: ${k}`);
		assert.ok(!/\bP[DS]T\b/.test(k), `Browser-Zone sichtbar: ${k}`);
	});

	test('Trip mit Morgen 07:00 → nie „06:00"', () => {
		const k = karte({ trip: trip('07:00:00', '18:00:00'), nextBriefing: nb('07:00', 'morning') });
		assert.ok(k.includes('07:00'), `07:00 fehlt: ${k}`);
		assert.ok(!k.includes('06:00'), `06:00 sichtbar: ${k}`);
	});

	test('Minuten werden wie im Versand ignoriert: 07:30 → 07:00', () => {
		const k = karte({ trip: trip('07:30:00', '18:00:00'), nextBriefing: nb('07:00', 'morning') });
		assert.ok(k.includes('07:00'), `07:00 fehlt: ${k}`);
		assert.ok(!k.includes('07:30'), `Minuten-Fiktion 07:30 sichtbar: ${k}`);
	});

	test('ohne Backend-Wert (nicht geladen) keine erfundenen 06:00', () => {
		const k = karte({ trip: trip('08:00:00', '20:00:00') });
		assert.ok(!k.includes('06:00'), `06:00 sichtbar: ${k}`);
	});
});
