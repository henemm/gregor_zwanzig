// TDD GREEN (Fix-Loop 1) — Bug #2454, Findings F001 (moveMetric-Verdrahtung/
// Global-Abwahl-Durchschreibung) + F002 (channelOverrideFromMetrics am
// Wirkort). Adversary-Verdict: BROKEN.
//
// F002: kein Test rief `channelOverrideFromMetrics()` bisher mit einem
// Kanal-Layout auf, das bereits einen aktiven Elter UND ein fehlendes Kind
// enthaelt (`wind_chill_kanal_mitnahme_speicherpfad.test.ts` startete mit
// einem LEEREN Kanal-Layout). Diese Datei deckt das direkt ab.
//
// F001 (Toggle-Teil): `WeatherMetricsTab.svelte::onToggleMetric()` +
// die Global-Abwahl-Durchschreibung in Kanal-Overrides sind jetzt EINE
// geteilte, exportierte Funktion `toggleGlobalMetric()` in
// channelMetricLayouts.ts. Diese Datei bewacht die Funktion direkt.
//
// Mutations-Gegenprobe (Fix-Loop 1, manuell): `deriveMissingChildMetrics`-
// Aufruf in `channelOverrideFromMetrics()` durch `metrics` ersetzt -> Test 1
// unten wird rot. `toggleGlobalMetric()`s Kind-Mitnahme (moveWithDerivedChildren
// -> move) ersetzt -> Test 4 wird rot. Global-Abwahl-Durchschreibung entfernt
// -> Test 5 wird rot.
//
// Ausfuehrung:
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types \
//     --experimental-test-module-mocks --test \
//     src/lib/components/shared/weather-metrics-tab/__tests__/bug_2454_channel_ableitung_und_toggle.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import path from 'node:path';

import { channelOverrideFromMetrics, toggleGlobalMetric, type ChannelOverride } from '../channelMetricLayouts.ts';
import type { Buckets } from '../../../trip-detail/metricsEditor.ts';
import type { ChannelId } from '../../layout-tab/ltChannels.ts';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const catalogIds: string[] = (() => {
	const raw = JSON.parse(
		readFileSync(path.join(__dirname, 'fixtures', 'metric_catalog_selectable.json'), 'utf-8'),
	) as Record<string, Array<{ id: string }>>;
	return Object.values(raw).flatMap((group) => group.map((m) => m.id));
})();

const KINDER = ['wind_chill_day_low', 'wind_chill_day_high', 'wind_chill_night'];

describe('Bug #2454 F002: channelOverrideFromMetrics() leitet fehlende Kanal-Kinder ab', () => {
	test('Kanal-Elter aktiv, Kind fehlt -> Kind erscheint aktiv im Elter-Bucket des Kanals', () => {
		const layout = [{ metric_id: 'wind_chill', enabled: true, order: 0 } as never];
		const override = channelOverrideFromMetrics(layout, catalogIds, {});
		for (const kind of KINDER) {
			assert.ok(
				override.buckets.primary.includes(kind),
				`F002: ${kind} fehlt in channelOverrideFromMetrics()-Ergebnis, obwohl der Kanal-Elter aktiv ist.\n` +
				`primary: ${JSON.stringify(override.buckets.primary)}`,
			);
			assert.ok(!override.buckets.off.includes(kind), `F002: ${kind} darf nicht gleichzeitig in off stehen`);
		}
	});

	test('Kanal-Elter selbst AUS (obwohl global an) -> Kind bleibt aus, auch im Kanal-Layout', () => {
		const layout = [{ metric_id: 'wind_chill', enabled: false, order: 0 } as never];
		const override = channelOverrideFromMetrics(layout, catalogIds, {});
		for (const kind of KINDER) {
			assert.ok(!override.buckets.primary.includes(kind), `F002: ${kind} darf nicht aktiv sein, der Kanal-Elter ist selbst aus`);
			assert.ok(override.buckets.off.includes(kind), `F002: ${kind} muss in off stehen`);
		}
	});

	test('explizites Kind-false im Kanal-Layout bleibt trotz aktivem Elter aus', () => {
		const layout = [
			{ metric_id: 'wind_chill', enabled: true, order: 0 } as never,
			{ metric_id: 'wind_chill_day_low', enabled: false } as never,
		];
		const override = channelOverrideFromMetrics(layout, catalogIds, {});
		assert.ok(!override.buckets.primary.includes('wind_chill_day_low'), 'DEC-6: expliziter Kanal-Eintrag darf nicht ueberschrieben werden');
		assert.ok(override.buckets.primary.includes('wind_chill_day_high'), 'Geschwister-Kind bleibt aktiv');
	});
});

function leererChannelBuckets(): Record<ChannelId, ChannelOverride | null> {
	return { email: null, telegram: null, sms: null };
}

describe('Bug #2454 F001: toggleGlobalMetric() -- Wirkort von onToggleMetric()', () => {
	test('Einwahl (off->primary): wind_chill nimmt seine im off-Bucket wartenden Kinder mit', () => {
		const buckets: Buckets = {
			primary: [],
			secondary: [],
			off: ['wind_chill', ...KINDER],
		};
		const result = toggleGlobalMetric(buckets, leererChannelBuckets(), 'wind_chill', false);
		for (const id of ['wind_chill', ...KINDER]) {
			assert.ok(result.buckets.primary.includes(id), `${id} muss nach der Einwahl in primary stehen`);
		}
	});

	test('No-Op (from === to): liefert dieselben Referenzen unveraendert zurueck', () => {
		const buckets: Buckets = { primary: ['wind'], secondary: [], off: [] };
		const channelBuckets = leererChannelBuckets();
		// wasOn=false bei bereits aktivem 'wind' -> from='primary', to='primary' -> No-Op.
		const result = toggleGlobalMetric(buckets, channelBuckets, 'wind', false);
		assert.equal(result.buckets, buckets, 'No-Op muss dieselbe Buckets-Referenz liefern');
		assert.equal(result.channelBuckets, channelBuckets, 'No-Op muss dieselbe channelBuckets-Referenz liefern');
	});

	test('globale Abwahl (primary->off) schreibt die Kind-Mitnahme in einen aktiven SMS-Kanal-Override durch', () => {
		const buckets: Buckets = { primary: ['wind_chill', ...KINDER], secondary: [], off: [] };
		const channelBuckets: Record<ChannelId, ChannelOverride | null> = {
			email: null,
			telegram: null,
			sms: { buckets: { primary: ['wind_chill', ...KINDER], secondary: [], off: [] }, friendlyMap: {} },
		};
		const result = toggleGlobalMetric(buckets, channelBuckets, 'wind_chill', true);

		for (const id of ['wind_chill', ...KINDER]) {
			assert.ok(!result.buckets.primary.includes(id), `${id} muss global abgewaehlt sein`);
			const smsOverride = result.channelBuckets.sms as ChannelOverride;
			assert.ok(
				smsOverride.buckets.off.includes(id),
				`Bug #2454 Abschnitt 2: ${id} muss auch im SMS-Kanal-Override in 'off' landen (Durchschreibung), ` +
				`sonst bleibt die Kind-Zeile im Kanal aktiv stehen, waehrend der Elter global abgewaehlt ist.`,
			);
			assert.ok(!smsOverride.buckets.primary.includes(id));
		}
	});

	test('globale Abwahl laesst einen Kanal-Override unangetastet, der den Elter nicht aktiv fuehrt', () => {
		const buckets: Buckets = { primary: ['wind_chill'], secondary: [], off: [] };
		const smsOverride: ChannelOverride = { buckets: { primary: ['wind'], secondary: [], off: ['wind_chill'] }, friendlyMap: {} };
		const channelBuckets: Record<ChannelId, ChannelOverride | null> = { email: null, telegram: null, sms: smsOverride };
		const result = toggleGlobalMetric(buckets, channelBuckets, 'wind_chill', true);
		assert.equal(result.channelBuckets.sms, smsOverride, 'ein Kanal-Override ohne den Elter in primary bleibt unveraendert (dieselbe Referenz)');
	});
});
