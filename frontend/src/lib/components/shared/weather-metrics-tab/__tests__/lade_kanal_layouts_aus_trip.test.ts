// Issue #3047 Runde 8 (Paket r8fe, Testluecke T1) — Mutation M39 der
// Abnahme 7b („SMS-Layout beim Laden ignorieren“) ueberlebte alle Tests, weil
// nur der Test-Nachbau `_editor_kette.ts` geprueft wurde, nicht der Ladeweg
// des Editors. Der Ladeweg `WeatherMetricsTab.svelte::initFromTrip()` baut die
// Kanal-Eintraege jetzt ueber `channelOverridesFromSaved()` (eine Funktion,
// die Komponente UND Nachbau aufrufen). Diese Datei prueft genau diese
// Funktion mit gespeicherten Trip-Konfigurationen zweier Nutzer.
//
//   cd frontend && npm test -- src/lib/components/shared/weather-metrics-tab/__tests__/lade_kanal_layouts_aus_trip.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { channelOverridesFromSaved } from '../channelMetricLayouts.ts';

const KATALOG_IDS = ['temperature', 'wind', 'gust', 'precipitation', 'cloud_total', 'humidity'];
const GLOBAL_FRIENDLY = Object.fromEntries(KATALOG_IDS.map((id) => [id, true]));

// (Groessen ohne abgeleitete Kinder, damit die Folge exakt pruefbar ist.)
// Nutzer A: eigene SMS-Liste (Folge ungleich Katalog, Roh bei Wind), eigene Telegram-Liste.
const NUTZER_A = {
	sms: [
		{ metric_id: 'precipitation', enabled: true, order: 0 },
		{ metric_id: 'wind', enabled: true, order: 1, use_friendly_format: false },
		{ metric_id: 'cloud_total', enabled: true, order: 2 },
		{ metric_id: 'gust', enabled: false, order: 3 }
	],
	telegram: [
		{ metric_id: 'humidity', enabled: true, order: 0 },
		{ metric_id: 'gust', enabled: true, order: 1 }
	]
};
// Nutzer B: nur eine SMS-Liste, andere Folge.
const NUTZER_B = {
	sms: [
		{ metric_id: 'cloud_total', enabled: true, order: 0 },
		{ metric_id: 'gust', enabled: true, order: 1 }
	]
};

describe('T1: Editor-Ladeweg uebernimmt jedes gespeicherte Kanal-Layout (auch SMS)', () => {
	test('Nutzer A: SMS-Reiter zeigt gespeicherte Auswahl, Folge und Roh/Einfach', () => {
		const cb = channelOverridesFromSaved(NUTZER_A as never, KATALOG_IDS, GLOBAL_FRIENDLY);
		assert.ok(cb.sms, 'SMS-Layout beim Laden verworfen (M39)');
		assert.deepEqual(cb.sms!.buckets.primary, ['precipitation', 'wind', 'cloud_total']);
		assert.ok(cb.sms!.buckets.off.includes('gust'));
		assert.equal(cb.sms!.friendlyMap.wind, false);
		assert.deepEqual(cb.telegram!.buckets.primary, ['humidity', 'gust']);
		assert.equal(cb.email, null, 'nie editierter Reiter bleibt ohne eigenen Eintrag');
	});
	test('Nutzer B: eigene SMS-Liste, keine Werte von Nutzer A', () => {
		const a = channelOverridesFromSaved(NUTZER_A as never, KATALOG_IDS, GLOBAL_FRIENDLY);
		const b = channelOverridesFromSaved(NUTZER_B as never, KATALOG_IDS, GLOBAL_FRIENDLY);
		assert.deepEqual(b.sms!.buckets.primary, ['cloud_total', 'gust']);
		assert.equal(b.telegram, null);
		assert.equal(b.sms!.friendlyMap.wind, true, 'Roh-Einstellung von Nutzer A uebertragen');
		assert.deepEqual(a.sms!.buckets.primary, ['precipitation', 'wind', 'cloud_total']);
	});
	test('ohne channel_layouts: alle drei Reiter ohne eigenen Eintrag', () => {
		assert.deepEqual(channelOverridesFromSaved(undefined, KATALOG_IDS, GLOBAL_FRIENDLY), { email: null, telegram: null, sms: null });
	});
});
