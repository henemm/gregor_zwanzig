// TDD GREEN (Fix-Loop 1) — Bug #2454, AC-3(a): Nutzer aktiviert "Gefuehlte
// Temperatur" GLOBAL und zusaetzlich im SMS-Kanal-Reiter und speichert -- die
// drei Kind-Groessen (FD/FL/FN) duerfen dabei nicht mehr eingefroren werden.
//
// Spec: docs/specs/bugfix/bug_2454_kurzform_gefuehlte_temperatur.md AC-3.
//
// Fix-Loop 1 (Adversary-Finding F001): Schritt 1 (globale Einwahl) ruft jetzt
// `toggleGlobalMetric()` (channelMetricLayouts.ts) auf -- DIESELBE Funktion,
// die `WeatherMetricsTab.svelte::onToggleMetric()` am echten Wirkort
// verwendet, statt die rohe `moveWithDerivedChildren()` direkt zu rufen.
// Schritt 2 (Kanal-eigene Einwahl im SMS-Reiter) bleibt bei
// `moveWithDerivedChildren()` direkt -- exakt das, was
// `onRestoreMetric()`/`onRemove()` am Kanal-Override aufrufen.
//
// Bewusste Abweichung von der Spec-Formulierung "Vergleich gegen eine
// eingecheckte Erwartungsdatei": ein vollstaendiger Deep-Equal gegen eine von
// Hand getippte ~29-Metriken-Payload waere bei jeder irrelevanten
// Katalogaenderung falsch-rot (Review-Hinweis). Stattdessen gezielte
// Assertions auf genau die drei betroffenen Kind-IDs, global UND im
// SMS-Kanal-Layout -- misst dieselbe Zusicherung, ohne die Bruechigkeit
// eines vollen Snapshot-Vergleichs.
//
// Ausfuehrung:
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types \
//     --experimental-test-module-mocks --test \
//     src/lib/components/shared/weather-metrics-tab/__tests__/wind_chill_kanal_mitnahme_speicherpfad.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import path from 'node:path';

import {
	baueSpeichernPayload,
	ladeInEditorState,
	type EditorState,
	type GoldenTrip,
	type MinimalCatalog,
} from './_editor_kette.ts';
import type { Buckets } from '../../../trip-detail/metricsEditor.ts';
import type { ChannelOverride } from '../channelMetricLayouts.ts';

const __dirname = path.dirname(fileURLToPath(import.meta.url));

const catalog: MinimalCatalog = JSON.parse(
	readFileSync(path.join(__dirname, 'fixtures', 'metric_catalog_selectable.json'), 'utf-8'),
);

// Leerer Bestand (kein wind_chill aktiv, weder global noch im SMS-Kanal) --
// SMS-Kanal-Layout existiert bereits (leer), damit der Kanal-Toggle-Pfad
// wirklich durchlaufen wird statt bloss eine tiefe Kopie der globalen
// Auswahl zu sein (Review-Hinweis).
const golden: GoldenTrip = {
	display_config: {
		metrics: [],
		channel_layouts: { sms: [] },
	},
};

async function requireToggleGlobalMetric(): Promise<
	(
		buckets: Buckets,
		channelBuckets: Record<'email' | 'telegram' | 'sms', ChannelOverride | null>,
		id: string,
		wasOn: boolean,
	) => { buckets: Buckets; channelBuckets: Record<'email' | 'telegram' | 'sms', ChannelOverride | null> }
> {
	const mod = (await import('../channelMetricLayouts.ts')) as Record<string, unknown>;
	const fn = mod.toggleGlobalMetric;
	assert.equal(
		typeof fn, 'function',
		`Bug #2454 AC-3: 'toggleGlobalMetric' fehlt in channelMetricLayouts.ts -- ` +
		`ohne diese Funktion friert ein Save die neu gewaehlten Kinder sofort wieder ein.`,
	);
	return fn as never;
}

async function requireMoveWithDerivedChildren(): Promise<
	(b: Buckets, id: string, from: keyof Buckets, to: keyof Buckets) => Buckets
> {
	const mod = (await import('../../../trip-detail/metricsEditor.ts')) as Record<string, unknown>;
	const fn = mod.moveWithDerivedChildren;
	assert.equal(
		typeof fn, 'function',
		`Bug #2454 AC-3: 'moveWithDerivedChildren' fehlt in metricsEditor.ts -- ` +
		`ohne diese Funktion friert ein Save die neu gewaehlten Kinder sofort wieder ein.`,
	);
	return fn as (b: Buckets, id: string, from: keyof Buckets, to: keyof Buckets) => Buckets;
}

const KINDER = ['wind_chill_day_low', 'wind_chill_day_high', 'wind_chill_night'];

describe('AC-3(a): wind_chill global UND im SMS-Reiter einschalten und speichern -- Kinder duerfen nicht eingefroren werden', () => {
	test('Speicher-Payload enthaelt die drei wind_chill-Kinder mit enabled:true, global UND in channel_layouts.sms', async () => {
		const toggleGlobalMetric = await requireToggleGlobalMetric();
		const moveWithDerivedChildren = await requireMoveWithDerivedChildren();

		const state: EditorState = ladeInEditorState(golden, catalog);
		assert.ok(!state.buckets.primary.includes('wind_chill'), 'Vorbedingung: wind_chill ist zu Beginn global aus');
		assert.ok(state.channelBuckets.sms !== null, 'Vorbedingung: SMS-Kanal hat bereits ein (leeres) Layout');

		// Schritt 1: Nutzer schaltet wind_chill GLOBAL ein -- ueber DIESELBE
		// Funktion, die WeatherMetricsTab.svelte::onToggleMetric() am echten
		// Wirkort aufruft (Fix-Loop 1, Finding F001).
		const nachToggle = toggleGlobalMetric(state.buckets, state.channelBuckets, 'wind_chill', false);

		// Schritt 2: Nutzer schaltet wind_chill zusaetzlich im SMS-Reiter ein
		// (ADR-0050-Praezondition: global bereits aktiv, s.o.) -- exakt das, was
		// onRestoreMetric() am Kanal-Override aufruft.
		const smsOverrideVorher = nachToggle.channelBuckets.sms as ChannelOverride;
		const neueSmsBuckets = moveWithDerivedChildren(smsOverrideVorher.buckets, 'wind_chill', 'off', 'primary');

		const neuerState: EditorState = {
			...state,
			buckets: nachToggle.buckets,
			channelBuckets: {
				...nachToggle.channelBuckets,
				sms: { buckets: neueSmsBuckets, friendlyMap: smsOverrideVorher.friendlyMap },
			},
		};

		const payload = baueSpeichernPayload(golden, neuerState, catalog);

		// --- global ---
		for (const kindId of KINDER) {
			const eintrag = payload.metrics.find((m) => m.metric_id === kindId);
			assert.ok(eintrag, `AC-3: ${kindId} fehlt in der globalen Speicher-Payload.`);
			assert.equal(
				eintrag!.enabled, true,
				`AC-3: ${kindId} muss global enabled:true sein, sonst bleibt die Kurzform ohne FD/FL/FN ` +
				`(Payload: ${JSON.stringify(eintrag)}).`,
			);
		}

		// --- SMS-Kanal ---
		const smsListe = payload.channel_layouts.sms;
		assert.ok(smsListe, 'AC-3: payload.channel_layouts.sms fehlt.');
		for (const kindId of KINDER) {
			const eintrag = smsListe.find((m) => m.metric_id === kindId);
			assert.ok(eintrag, `AC-3: ${kindId} fehlt in channel_layouts.sms der Speicher-Payload.`);
			assert.equal(
				eintrag!.enabled, true,
				`AC-3: ${kindId} muss in channel_layouts.sms enabled:true sein (die Wahl wirkt sonst still ins Leere, ` +
				`genau der PO-Befund auf KHW 403).\nchannel_layouts.sms: ${JSON.stringify(smsListe)}`,
			);
		}
	});
});
