// TDD RED — Issue #1575 Scheibe 3, AC-3 (Shallow-Merge-Datenverlust-Schutz)
// und AC-2 (Copy-on-write beim ersten Kanal-Edit).
//
// Spec: docs/specs/modules/fix_1575_channel_metric_selection.md
//   § Teil 2 ("Save-Payload", "Copy-on-write"), § AC-2, § AC-3
// Kontext: docs/context/fix-1575-channel-metric-selection.md
//   § "🔴 Neuer Fund: Shallow-Merge-Datenverlust-Risiko"
//
// Befund: `internal/handler/config_merge.go:11-22` mergt `display_config` nur
// SHALLOW auf oberster Schluesselebene. Sendet der Editor beim Speichern im
// SMS-Reiter nur `channel_layouts: { sms: [...] }`, ERSETZT das den kompletten
// `channel_layouts`-Wert — bereits gespeicherte `email`/`telegram`-Eintraege
// gehen lautlos verloren (neuer BUG-DATALOSS-GR221-Fall).
//
// Das Modul `../weather-metrics-tab/channelMetricLayouts.ts` existiert noch
// NICHT → der Import wirft einen Modul-Resolve-Fehler und ALLE Tests dieser
// Datei scheitern (RED). Muster: shared/__tests__/reportConfigDirty.test.ts.
//
// Kontrakt fuer GREEN (reine Funktionen, kein Svelte-State, kein DOM):
//
//   mergeChannelLayoutsForSave(
//     prevLayouts: ChannelLayouts | undefined,
//     channel: ChannelId,
//     metrics: WeatherConfigMetric[] | null,
//   ): ChannelLayouts
//     - `metrics === null` (Kanal nie editiert, copy-on-write nicht ausgeloest)
//       → `prevLayouts` inhaltlich unveraendert zurueck
//     - sonst: alle bisherigen Kanal-Eintraege bleiben erhalten, NUR `channel`
//       wird ersetzt
//     - mutiert `prevLayouts` nicht
//
//   startChannelOverride(
//     buckets: Buckets,
//     friendlyMap: Record<string, boolean>,
//   ): { buckets: Buckets; friendlyMap: Record<string, boolean> }
//     - liefert eine tiefe KOPIE der globalen Auswahl als Startpunkt (AC-2:
//       "Startpunkt ist die globale Auswahl, nicht leer")
//     - spaetere Aenderungen an der Kopie duerfen die globale Struktur nicht
//       beruehren
//
// Liegt die Logik in GREEN stattdessen in `trip-detail/metricsEditor.ts`,
// wird hier nur der Import-Pfad angepasst — der Kontrakt bleibt derselbe.
//
// Ausfuehren:
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types \
//     --test src/lib/components/shared/__tests__/channelMetricLayouts.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import type { ChannelLayouts, WeatherConfigMetric } from '$lib/types';

const { mergeChannelLayoutsForSave, startChannelOverride } = await import(
	'../weather-metrics-tab/channelMetricLayouts.ts'
);

const metric = (metric_id: string, order: number): WeatherConfigMetric => ({
	metric_id,
	enabled: true,
	use_friendly_format: true,
	bucket: 'primary',
	order
});

const emailLayout: WeatherConfigMetric[] = [metric('temperature', 0), metric('wind', 1)];
const telegramLayout: WeatherConfigMetric[] = [metric('gust', 0)];
const smsLayout: WeatherConfigMetric[] = [metric('precipitation', 0)];

describe('AC-3: Speichern in einem Kanal laesst die anderen Kanaele unveraendert', () => {
	test('SMS-Edit erhaelt die gespeicherten email-/telegram-Eintraege', () => {
		const prev: ChannelLayouts = { email: emailLayout, telegram: telegramLayout };

		const next = mergeChannelLayoutsForSave(prev, 'sms', smsLayout);

		assert.deepEqual(
			next.email,
			emailLayout,
			'AC-3 FAIL: der gespeicherte email-Eintrag ueberlebt ein SMS-Edit nicht — ' +
				'config_merge.go ersetzt channel_layouts komplett (BUG-DATALOSS-GR221-Muster)'
		);
		assert.deepEqual(
			next.telegram,
			telegramLayout,
			'AC-3 FAIL: der gespeicherte telegram-Eintrag ueberlebt ein SMS-Edit nicht'
		);
		assert.deepEqual(next.sms, smsLayout, 'AC-3 FAIL: der SMS-Eintrag wurde nicht geschrieben');
	});

	test('ein bereits vorhandener Eintrag desselben Kanals wird ersetzt, nicht angehaengt', () => {
		const prev: ChannelLayouts = { email: emailLayout, sms: [metric('thunder', 0)] };

		const next = mergeChannelLayoutsForSave(prev, 'sms', smsLayout);

		assert.deepEqual(
			next.sms,
			smsLayout,
			'AC-3 FAIL: der neue SMS-Stand ersetzt den alten nicht'
		);
		assert.deepEqual(next.email, emailLayout, 'AC-3 FAIL: email wurde beim SMS-Edit veraendert');
	});

	test('nie editierter Kanal (metrics === null) schreibt keinen eigenen Eintrag', () => {
		const prev: ChannelLayouts = { email: emailLayout };

		const next = mergeChannelLayoutsForSave(prev, 'sms', null);

		assert.equal(
			next.sms,
			undefined,
			'AC-3/Copy-on-write FAIL: ein nie editierter Kanal darf keinen eigenen ' +
				'(womoeglich leeren) Eintrag bekommen — sonst faellt die Backend-Kaskade ' +
				'nicht mehr auf die globale Auswahl zurueck'
		);
		assert.deepEqual(next.email, emailLayout, 'AC-3 FAIL: email ging beim Nicht-Edit verloren');
	});

	test('ohne bisherigen Stand (undefined) entsteht ein Objekt mit nur diesem Kanal', () => {
		const next = mergeChannelLayoutsForSave(undefined, 'telegram', telegramLayout);

		assert.deepEqual(next, { telegram: telegramLayout });
	});

	test('der bisherige Stand wird nicht mutiert', () => {
		const prev: ChannelLayouts = { email: emailLayout };

		mergeChannelLayoutsForSave(prev, 'sms', smsLayout);

		assert.equal(
			prev.sms,
			undefined,
			'AC-3 FAIL: mergeChannelLayoutsForSave mutiert den uebergebenen Vorstand — ' +
				'der Vorstand ist die aktuellste bekannte Serverantwort und muss unberuehrt bleiben'
		);
	});
});

describe('AC-2: erster Kanal-Edit startet als Kopie der globalen Auswahl', () => {
	const globalBuckets = {
		primary: ['temperature', 'wind'],
		secondary: ['gust'],
		off: ['thunder']
	};
	const globalFriendly: Record<string, boolean> = { temperature: true, wind: false };

	test('startet inhaltlich mit der globalen Auswahl, nicht leer', () => {
		const override = startChannelOverride(globalBuckets, globalFriendly);

		assert.deepEqual(
			override.buckets,
			globalBuckets,
			'AC-2 FAIL: der erste Edit unter einem Kanal muss mit der globalen Auswahl ' +
				'starten (PO-Entscheidung 2026-08-08), nicht mit einer leeren Liste'
		);
		assert.deepEqual(override.friendlyMap, globalFriendly);
	});

	test('ist eine tiefe Kopie — Aenderungen schlagen nicht auf die globale Auswahl durch', () => {
		const override = startChannelOverride(globalBuckets, globalFriendly);

		override.buckets.primary.push('precipitation');
		override.buckets.off.length = 0;
		override.friendlyMap.temperature = false;

		assert.deepEqual(
			globalBuckets.primary,
			['temperature', 'wind'],
			'AC-2 FAIL: der Kanal-Override teilt sein Array mit der globalen Auswahl — ' +
				'ein SMS-Edit wuerde damit auch Email/Telegram veraendern'
		);
		assert.deepEqual(globalBuckets.off, ['thunder'], 'AC-2 FAIL: off-Bucket wird geteilt');
		assert.equal(
			globalFriendly.temperature,
			true,
			'AC-2 FAIL: friendlyMap wird zwischen Kanal und globaler Auswahl geteilt'
		);
	});
});
