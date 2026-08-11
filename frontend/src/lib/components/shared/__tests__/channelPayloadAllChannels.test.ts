// TDD RED — Issue #1719 Scheibe S3, AC-10 (Unit-Anteil, Serialisierung):
// "Das ist der wichtigste Test der Scheibe" (Auftrag Team-Lead-Spawn).
//
// Spec: docs/specs/modules/fix_1719_s3_aus_ist_ein_zustand.md
//   Abschnitt 4 ("Durchschreibung — und der Persistenz-Fix"), AC-10.
//   Mutations-Gegenprobe M1 ("in buildWeatherPayload wieder nur
//   activeChannel serialisieren" MUSS AC-10 rot machen, und NUR AC-10).
// Kontext: docs/context/fix-1719-s3-aus-ist-ein-zustand.md Abschnitt 10.1
//   ("Der Fund, der die Scheibe rettet").
//
// Der gemessene Defekt (heute, `mergeChannelLayoutsForSave`,
// `../weather-metrics-tab/channelMetricLayouts.ts:25-34`): die Funktion
// schreibt IMMER nur EINEN Kanal (`channel`-Parameter). `buildWeatherPayload`
// (WeatherMetricsTab.svelte:754-767) ruft sie ausschliesslich mit
// `activeChannel` auf. Steht der Nutzer im E-Mail-Reiter, waehrend SMS
// bereits einen eigenstaendigen Kanal-Override traegt (z.B. weil eine
// globale Abwahl soeben dorthin durchgeschrieben wurde), geht dieser
// SMS-Override beim Speichern NIE mit — nur der aktive Kanal (email) wird
// serialisiert, SMS bleibt auf dem alten, widerspruechlichen Server-Stand
// (neue ADR-0050-Regel-3-Verletzung, eingebaut von der Scheibe, die sie
// beheben soll).
//
// Kontrakt fuer GREEN: `mergeAllChannelLayoutsForSave` existiert in
// `../weather-metrics-tab/channelMetricLayouts.ts` heute NICHT -> Import
// wirft Modul-Resolve-Fehler, ALLE Tests dieser Datei scheitern (RED).
//
//   mergeAllChannelLayoutsForSave(
//     prevLayouts: ChannelLayouts | undefined,
//     channelBuckets: Record<ChannelId, ChannelOverride | null>,
//     buildMetrics: (override: ChannelOverride) => WeatherConfigMetric[],
//   ): ChannelLayouts
//     - fuer JEDEN Kanal mit channelBuckets[ch] !== null: next[ch] =
//       buildMetrics(channelBuckets[ch]) — NICHT nur fuer einen
//       ausgezeichneten "aktiven" Kanal
//     - fuer channelBuckets[ch] === null: next[ch] bleibt der Wert aus
//       prevLayouts unveraendert (Datenverlust-Schutz #1575 bleibt gewahrt
//       — config_merge.go ersetzt channel_layouts als GANZES)
//     - mutiert prevLayouts nicht
//
// Ausfuehren:
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types \
//     --test src/lib/components/shared/__tests__/channelPayloadAllChannels.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import type { ChannelLayouts, WeatherConfigMetric } from '$lib/types';
import type { ChannelId } from '$lib/components/shared/layout-tab/ltChannels';

const { mergeAllChannelLayoutsForSave } = await import(
	'../weather-metrics-tab/channelMetricLayouts.ts'
);
type ChannelOverride = { buckets: { primary: string[]; secondary: string[]; off: string[] }; friendlyMap: Record<string, boolean> };

const override = (primary: string[]): ChannelOverride => ({
	buckets: { primary, secondary: [], off: [] },
	friendlyMap: {}
});

const metricsFor = (o: ChannelOverride): WeatherConfigMetric[] =>
	o.buckets.primary.map((id, i) => ({ metric_id: id, enabled: true, bucket: 'primary', order: i }));

const persistedEmail: WeatherConfigMetric[] = [
	{ metric_id: 'temperature', enabled: true, bucket: 'primary', order: 0 },
	{ metric_id: 'wind', enabled: true, bucket: 'primary', order: 1 }
];
const persistedTelegram: WeatherConfigMetric[] = [
	{ metric_id: 'gust', enabled: true, bucket: 'primary', order: 0 }
];

describe('AC-10 (Persistenz-Fix): buildWeatherPayload muss ALLE nicht-null Kanal-Overrides serialisieren', () => {
	test('Nutzer steht im E-Mail-Reiter (email-Override ist null), SMS traegt einen eigenstaendigen Override -> SMS geht mit', () => {
		const prevLayouts: ChannelLayouts = { email: persistedEmail, telegram: persistedTelegram };
		const channelBuckets: Record<ChannelId, ChannelOverride | null> = {
			email: null,
			telegram: null,
			sms: override(['precipitation'])
		};

		const next = mergeAllChannelLayoutsForSave(prevLayouts, channelBuckets, metricsFor);

		assert.deepEqual(
			next.sms?.map((m) => m.metric_id),
			['precipitation'],
			'AC-10 FAIL: der SMS-Override muss serialisiert werden, obwohl der Nutzer im E-Mail-Reiter steht ' +
				'(M1: "wieder nur activeChannel serialisieren" waere hier email, SMS ginge verloren)'
		);
		assert.deepEqual(
			next.email,
			persistedEmail,
			'AC-10 FAIL: der unveraenderte email-Override (null) darf den gespeicherten Server-Stand nicht verlieren'
		);
		assert.deepEqual(
			next.telegram,
			persistedTelegram,
			'AC-10 FAIL: der unveraenderte telegram-Override (null) darf den gespeicherten Server-Stand nicht verlieren'
		);
	});

	test('ZWEI gleichzeitig eigenstaendige Kanaele (email UND sms) werden BEIDE serialisiert, nicht nur einer', () => {
		const channelBuckets: Record<ChannelId, ChannelOverride | null> = {
			email: override(['temperature']),
			telegram: null,
			sms: override(['precipitation', 'wind'])
		};

		const next = mergeAllChannelLayoutsForSave(undefined, channelBuckets, metricsFor);

		assert.deepEqual(
			next.email?.map((m) => m.metric_id),
			['temperature'],
			'AC-10 FAIL: email-Override fehlt im Ergebnis — ein "nur den aktiven Kanal"-Bug wuerde ' +
				'genau einen der beiden gleichzeitig editierten Kanaele unterschlagen'
		);
		assert.deepEqual(
			next.sms?.map((m) => m.metric_id),
			['precipitation', 'wind'],
			'AC-10 FAIL: sms-Override fehlt im Ergebnis'
		);
		assert.equal(next.telegram, undefined, 'kein Eintrag ohne vorherigen Stand und ohne Override');
	});

	test('kein Kanal wurde je editiert (alle null) -> das Ergebnis entspricht unveraendert prevLayouts', () => {
		const prevLayouts: ChannelLayouts = { email: persistedEmail };
		const channelBuckets: Record<ChannelId, ChannelOverride | null> = {
			email: null,
			telegram: null,
			sms: null
		};

		const next = mergeAllChannelLayoutsForSave(prevLayouts, channelBuckets, metricsFor);

		assert.deepEqual(next, { email: persistedEmail });
	});

	test('mutiert prevLayouts nicht', () => {
		const prevLayouts: ChannelLayouts = { email: persistedEmail };
		const channelBuckets: Record<ChannelId, ChannelOverride | null> = {
			email: null,
			telegram: null,
			sms: override(['precipitation'])
		};

		mergeAllChannelLayoutsForSave(prevLayouts, channelBuckets, metricsFor);

		assert.deepEqual(
			prevLayouts,
			{ email: persistedEmail },
			'AC-10 FAIL: mergeAllChannelLayoutsForSave mutiert den uebergebenen Vorstand'
		);
	});
});
