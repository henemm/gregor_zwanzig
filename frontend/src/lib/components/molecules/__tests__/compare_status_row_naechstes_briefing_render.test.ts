// TDD RED — Issue #1969 (Nächstes Briefing), AC-23 / AC-24 / AC-25 (Vergleichsliste).
// SPEC: docs/specs/modules/feat_1969_naechstes_briefing.md
//
// CompareStatusRow.svelte bekommt den Backend-Wert als neue Prop
// `nextBriefing?: NextBriefing | null` und zeigt ihn über formatNextBriefing —
// keine eigene Rechnung (deriveNextSend) mehr.
//
// AC-24-Gegenprobe: send_time 07:30, Backend local_time 07:00; Prozess-Zone
// America/Los_Angeles. Eine Frontend-Rechnung zeigte 07:30 bzw. eine LA-Zeit.
//
// Echter SSR-Render (svelte/server).
//
// Ausführen:
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types \
//     --experimental-test-module-mocks --test \
//     src/lib/components/molecules/__tests__/compare_status_row_naechstes_briefing_render.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { register } from 'node:module';
import { fileURLToPath, pathToFileURL } from 'node:url';
import path from 'node:path';

process.env.TZ = 'America/Los_Angeles';

const HERE = path.dirname(fileURLToPath(import.meta.url));
// __tests__ -> molecules -> components -> lib -> src -> frontend
const FRONTEND = path.resolve(HERE, '../../../../..');
register(pathToFileURL(path.join(FRONTEND, 'test-svelte-ssr-hooks.mjs')).href, pathToFileURL(FRONTEND + '/').href);

const { render } = await import('svelte/server');
const CompareStatusRow = (await import(pathToFileURL(path.join(FRONTEND, 'src/lib/components/molecules/CompareStatusRow.svelte')).href)).default;

const PRESET = {
	id: 'cp-1969',
	name: 'Vergleich 07:30',
	location_ids: ['l1', 'l2'],
	schedule: 'daily',
	morning_enabled: true,
	morning_time: '07:30:00',
	evening_enabled: false,
	created_at: '2026-01-01T00:00:00Z'
};

const text = (props: Record<string, unknown>) =>
	render(CompareStatusRow, { props })
		.body.replace(/<!--[\s\S]*?-->/g, '')
		.replace(/<[^>]*>/g, ' ')
		.replace(/\s+/g, ' ');

describe('AC-23/AC-24: CompareStatusRow zeigt den Backend-Wert', () => {
	test('Backend 07:00 (CEST) → „Do 07:00 (CEST)", nie 07:30, nie Browser-Zone', () => {
		const t = text({
			preset: PRESET,
			nextBriefing: {
				at: '2026-10-22T07:00:00+02:00',
				local_date: '2026-10-22',
				local_time: '07:00',
				tz: 'Europe/Paris',
				tz_abbr: 'CEST',
				slot: 'morning'
			}
		});
		assert.ok(t.includes('Do 07:00 (CEST)'), `Backend-Zeit fehlt: ${t}`);
		assert.ok(!t.includes('07:30'), `Minuten-Fiktion sichtbar: ${t}`);
		assert.ok(!t.includes('22:00'), `Browser-Zone sichtbar: ${t}`);
	});

	test('AC-25: Backend 19:00 → Anzeige 19:00, keine fest verdrahtete 06:00/18:00', () => {
		const t = text({
			preset: { ...PRESET, morning_time: undefined },
			nextBriefing: {
				at: '2026-10-22T19:00:00+02:00',
				local_date: '2026-10-22',
				local_time: '19:00',
				tz: 'Europe/Paris',
				tz_abbr: 'CEST',
				slot: 'evening'
			}
		});
		assert.ok(t.includes('Do 19:00 (CEST)'), t);
		assert.ok(!t.includes('06:00') && !t.includes('18:00'), t);
	});

	test('manual → „nur manueller Versand"', () => {
		const t = text({ preset: { ...PRESET, schedule: 'manual' }, nextBriefing: { at: null, reason: 'manual' } });
		assert.ok(t.includes('nur manueller Versand'), t);
	});

	test('nicht geladen → „—", keine eigene Rechnung', () => {
		const t = text({ preset: PRESET });
		assert.ok(t.includes('—'), t);
		assert.doesNotMatch(t, /\d{1,2}:\d{2}/, `erfundene Zeit: ${t}`);
	});
});
