// Kern-Test — Issue #1269 Fix-Loop 2 (Adversary F001, Staging-Fund): das
// bloße Anklicken des Compare-Layout-Tabs löste einen echten
// PUT /api/compare/presets/{id} aus, weil die Mount-Kanonisierung des
// Buckets->ChannelLayouts-Roundtrips (CompareEditor.svelte `ltBuildLayouts()`)
// als Nutzeränderung gezählt wurde (`dirty` flippte true). Auf Staging
// reproduziert (3x), von der statischen Code-Prüfung übersehen — dieser Test
// bildet genau den Layout-Mount-Fall im Kern ab, damit der Regress künftig
// schon hier auffällt statt erst auf Staging.
//
// Spec: docs/specs/modules/issue_1269_save_status_lie.md
//   § Acceptance Criteria AC-1/AC-2/AC-7
//
// Reine Verhaltenstests (echter Funktionsaufruf, KEIN Mock, KEINE
// Datei-Inhalt-Prüfung).
//
// Ausführen:
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types --test \
//     src/lib/components/shared/layout-tab/__tests__/channelLayoutsDirty.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import type { ChannelLayouts } from '$lib/types';

import { channelLayoutsChangedByUser } from '../channelLayoutsDirty.ts';

describe('AC-1/AC-2: Layout-Mount-Kanonisierung (Buckets -> ChannelLayouts-Roundtrip) ist KEINE Nutzeränderung', () => {
	test('rohe geladene Layouts (nur aktive Metriken, ohne "off"-Einträge) vs. Roundtrip-Form (voller Katalog materialisiert) → false', () => {
		// So liegt ein bereits gespeicherter Preset typischerweise vor: nur die
		// tatsächlich aktiven Metriken sind im Array, in Bucket-Reihenfolge.
		const baseline: ChannelLayouts = {
			email: [
				{ metric_id: 'temperature', enabled: true, bucket: 'primary', order: 0, use_friendly_format: true },
				{ metric_id: 'wind', enabled: true, bucket: 'primary', order: 1, use_friendly_format: true }
			]
		};

		// So sieht dieselbe Konfiguration NACH dem Buckets->ChannelLayouts-
		// Roundtrip aus (CompareEditor.svelte `ltBuildLayouts()`, via
		// buildWeatherConfigMetrics): der GESAMTE Katalog wird materialisiert,
		// inkl. deaktivierter ("off") Metriken mit eigenen (bedeutungslosen)
		// order-Werten und Default-Horizonten — OHNE dass der Nutzer etwas
		// angefasst hat.
		const mountRoundtrip: ChannelLayouts = {
			email: [
				{
					metric_id: 'temperature',
					enabled: true,
					bucket: 'primary',
					order: 0,
					use_friendly_format: true,
					horizons: { today: true, tomorrow: true, day_after: true }
				},
				{
					metric_id: 'wind',
					enabled: true,
					bucket: 'primary',
					order: 1,
					use_friendly_format: true,
					horizons: { today: true, tomorrow: true, day_after: true }
				},
				// "off"-Metriken (enabled:false; kein "off"-Bucket-Literal im Typ —
				// deaktivierte Metriken tragen den zuletzt bekannten/irrelevanten
				// bucket-Wert): voller Katalog materialisiert, eigene order-Zählung —
				// reine Roundtrip-Kanonisierung, keine Nutzerabsicht.
				{
					metric_id: 'humidity',
					enabled: false,
					bucket: 'primary',
					order: 0,
					use_friendly_format: true,
					horizons: { today: true, tomorrow: true, day_after: true }
				},
				{
					metric_id: 'pressure',
					enabled: false,
					bucket: 'primary',
					order: 1,
					use_friendly_format: true,
					horizons: { today: true, tomorrow: true, day_after: true }
				}
			]
		};

		assert.equal(
			channelLayoutsChangedByUser(baseline, mountRoundtrip),
			false,
			'AC-1/AC-2: der reine Buckets->ChannelLayouts-Roundtrip (Materialisierung deaktivierter Metriken, ' +
				'Default-Horizonte) beim Layout-Tab-Mount darf NICHT als Nutzeränderung zählen — sonst löst das ' +
				'bloße Öffnen des Tabs einen echten PUT aus (Staging-Fund Fix-Loop 2)'
		);
	});

	test('identische, bereits kanonisierte Layouts gegen sich selbst → false (triviale Gegenprobe)', () => {
		const layouts: ChannelLayouts = {
			email: [{ metric_id: 'temperature', enabled: true, bucket: 'primary', order: 0 }]
		};
		assert.equal(channelLayoutsChangedByUser(layouts, { email: [...(layouts.email ?? [])] }), false);
	});

	test('beide Seiten leer/undefined → false', () => {
		assert.equal(channelLayoutsChangedByUser(undefined, undefined), false);
		assert.equal(channelLayoutsChangedByUser(null, null), false);
	});
});

describe('Gegenprobe: eine ECHTE Layout-Änderung bleibt "dirty" (darf NICHT durch die Kanonisierung verschluckt werden)', () => {
	test('Metrik von primary nach secondary verschoben (echte Nutzeränderung) → true', () => {
		const baseline: ChannelLayouts = {
			email: [{ metric_id: 'temperature', enabled: true, bucket: 'primary', order: 0 }]
		};
		const afterUserEdit: ChannelLayouts = {
			email: [{ metric_id: 'temperature', enabled: true, bucket: 'secondary', order: 0 }]
		};
		assert.equal(
			channelLayoutsChangedByUser(baseline, afterUserEdit),
			true,
			'ein tatsächlich verschobener Bucket ist eine echte Nutzeränderung und MUSS weiterhin "dirty" auslösen'
		);
	});

	test('vorher deaktivierte Metrik wird vom Nutzer aktiviert → true', () => {
		const baseline: ChannelLayouts = {
			email: [{ metric_id: 'temperature', enabled: true, bucket: 'primary', order: 0 }]
		};
		const afterUserEdit: ChannelLayouts = {
			email: [
				{ metric_id: 'temperature', enabled: true, bucket: 'primary', order: 0 },
				{ metric_id: 'humidity', enabled: true, bucket: 'primary', order: 1 }
			]
		};
		assert.equal(channelLayoutsChangedByUser(baseline, afterUserEdit), true);
	});

	test('Reihenfolge zweier aktiver Metriken vertauscht → true', () => {
		const baseline: ChannelLayouts = {
			email: [
				{ metric_id: 'temperature', enabled: true, bucket: 'primary', order: 0 },
				{ metric_id: 'wind', enabled: true, bucket: 'primary', order: 1 }
			]
		};
		const afterUserEdit: ChannelLayouts = {
			email: [
				{ metric_id: 'wind', enabled: true, bucket: 'primary', order: 0 },
				{ metric_id: 'temperature', enabled: true, bucket: 'primary', order: 1 }
			]
		};
		assert.equal(channelLayoutsChangedByUser(baseline, afterUserEdit), true);
	});
});
