// Issue #2422 S2a Fix-Loop 1 -- Adversary-Funde F003 (Bestand-Auswahl
// unbewacht) + F004 (sms_threshold-Bereinigung unbewacht).
//
// SPEC: docs/specs/modules/fix_2422_s2a_editor_gleich_gespeichert.md (K8-Fix)
// PROTOKOLL: docs/artifacts/fix-2422-s2-editor-gleich-gespeichert/adversary-dialog.md
// (Mutation M5: bestand/channel in WeatherMetricsTab.svelte nicht
// durchreichen -- KEIN Test wurde rot. Mutation M6: sms_threshold-Entfernung
// rueckgaengig -- KEIN Test wurde rot.)
//
// Diese Datei testet `buildGlobalMetricsForSave`/`buildChannelMetricsForSave`
// (weatherMetricsSavePayload.ts) DIREKT -- reine Funktionen, kein
// Svelte-Rendering noetig. Damit ist die Bestand-Auswahl (welche Liste geht
// in den Merge ein) UND die Threshold-Bereinigung jetzt dort bewacht, wo sie
// TATSAECHLICH ausgefuehrt wird (nicht nur an der Helferfunktion
// buildWeatherConfigMetrics, die selbst keine Auswahl trifft).
//
// Lauf:
//     cd frontend && npm test -- \
//       src/lib/components/shared/weather-metrics-tab/__tests__/speichern_waehlt_richtigen_bestand.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';

import {
	buildGlobalMetricsForSave, buildChannelMetricsForSave, type DisplayConfigBestand,
} from '../weatherMetricsSavePayload.ts';
import type { ChannelOverride } from '../channelMetricLayouts.ts';

// Minimaler Katalog -- eine Metrik reicht fuer diese Zusicherungen.
const catalog = {
	temperature: [{ id: 'wind', label: 'Wind', unit: 'km/h', category: 'temperature', default_enabled: true, has_friendly_format: false }],
};

describe('F003: Bestand-Auswahl (welche Liste geht in den Merge ein)', () => {
	test('buildGlobalMetricsForSave verwendet displayConfig.metrics -- NICHT einen Kanal-Bestand', () => {
		const displayConfig: DisplayConfigBestand = {
			metrics: [{ metric_id: 'wind', _marker: 'global' } as unknown as { metric_id: string }],
			channel_layouts: {
				email: [{ metric_id: 'wind', _marker: 'email' } as unknown as { metric_id: string }],
			},
		};
		const buckets = { primary: ['wind'], secondary: [], off: [] };
		const out = buildGlobalMetricsForSave(displayConfig, buckets, {}, {}, catalog, {}, []);
		const wind = out.find((m) => m.metric_id === 'wind') as unknown as Record<string, unknown>;
		assert.ok(wind, 'wind-Eintrag fehlt');
		assert.equal(
			wind._marker, 'global',
			`Erwartet den GLOBALEN Bestand (_marker='global'), erhalten: ${JSON.stringify(wind._marker)} -- ` +
				'Mutation "falscher/fehlender Bestand" (Adversary M5) muss diesen Test roten.',
		);
	});

	test('buildGlobalMetricsForSave OHNE bestand-Uebergabe verliert Bestandsfelder (Vakuum-Gegenprobe)', () => {
		// Belegt, dass der Test oben tatsaechlich etwas prueft: fehlt der
		// Bestand komplett (leeres displayConfig), darf `_marker` nirgends
		// auftauchen -- das ist der Zustand, den Mutation M5 erzeugen wuerde.
		const buckets = { primary: ['wind'], secondary: [], off: [] };
		const out = buildGlobalMetricsForSave({}, buckets, {}, {}, catalog, {}, []);
		const wind = out.find((m) => m.metric_id === 'wind') as unknown as Record<string, unknown>;
		assert.equal(wind._marker, undefined, 'Ohne Bestand darf kein _marker auftauchen.');
	});

	test('buildChannelMetricsForSave: sms-Aufruf verwendet den SMS-Bestand, nicht email/telegram', () => {
		const displayConfig: DisplayConfigBestand = {
			channel_layouts: {
				email: [{ metric_id: 'wind', _marker: 'email' } as unknown as { metric_id: string }],
				telegram: [{ metric_id: 'wind', _marker: 'telegram' } as unknown as { metric_id: string }],
				sms: [{ metric_id: 'wind', _marker: 'sms' } as unknown as { metric_id: string }],
			},
		};
		const override: ChannelOverride = { buckets: { primary: ['wind'], secondary: [], off: [] }, friendlyMap: {} };

		for (const [channel, erwarteterMarker] of [['email', 'email'], ['telegram', 'telegram'], ['sms', 'sms']] as const) {
			const out = buildChannelMetricsForSave(displayConfig, channel, override, {}, catalog);
			const wind = out.find((m) => m.metric_id === 'wind') as unknown as Record<string, unknown>;
			assert.equal(
				wind._marker, erwarteterMarker,
				`Kanal ${channel}: erwartet Bestand-Marker '${erwarteterMarker}', erhalten ` +
					`${JSON.stringify(wind._marker)} -- eine Kanal-Verwechslung (Adversary M5: "falscher ` +
					`Kanal-Bestand") muss hier auffliegen.`,
			);
		}
	});

	test('buildChannelMetricsForSave OHNE Bestand fuer den angefragten Kanal bleibt _marker-frei', () => {
		const displayConfig: DisplayConfigBestand = {
			channel_layouts: { email: [{ metric_id: 'wind', _marker: 'email' } as unknown as { metric_id: string }] },
		};
		const override: ChannelOverride = { buckets: { primary: ['wind'], secondary: [], off: [] }, friendlyMap: {} };
		const out = buildChannelMetricsForSave(displayConfig, 'sms', override, {}, catalog);
		const wind = out.find((m) => m.metric_id === 'wind') as unknown as Record<string, unknown>;
		assert.equal(wind._marker, undefined, 'sms hat keinen eigenen Bestand -- kein _marker erwartet.');
	});
});

describe('F004: sms_threshold-Bereinigung (kein stiller Altwert, kein verlorener Neuwert)', () => {
	const SMS_THRESHOLD_METRIC_IDS = ['wind'];

	test('geleerter Editor-Wert entfernt einen alten Bestands-sms_threshold', () => {
		const displayConfig: DisplayConfigBestand = {
			metrics: [{ metric_id: 'wind', sms_threshold: 42 } as unknown as { metric_id: string }],
		};
		const buckets = { primary: ['wind'], secondary: [], off: [] };
		// smsThresholds['wind'] fehlt (== Editor-Feld leer) -> Altwert muss weg.
		const out = buildGlobalMetricsForSave(displayConfig, buckets, {}, {}, catalog, {}, SMS_THRESHOLD_METRIC_IDS);
		const wind = out.find((m) => m.metric_id === 'wind') as unknown as Record<string, unknown>;
		assert.equal(
			wind.sms_threshold, undefined,
			`Ein geleerter Editor-Wert darf den Bestands-Altwert (42) NICHT wiederbeleben -- ` +
				`gefunden: ${JSON.stringify(wind.sms_threshold)} (Adversary M6).`,
		);
	});

	test('ungueltiger Editor-Wert (leerer String) entfernt ebenfalls den Bestands-Altwert', () => {
		const displayConfig: DisplayConfigBestand = {
			metrics: [{ metric_id: 'wind', sms_threshold: 42 } as unknown as { metric_id: string }],
		};
		const buckets = { primary: ['wind'], secondary: [], off: [] };
		const out = buildGlobalMetricsForSave(
			displayConfig, buckets, {}, {}, catalog, { wind: '' }, SMS_THRESHOLD_METRIC_IDS,
		);
		const wind = out.find((m) => m.metric_id === 'wind') as unknown as Record<string, unknown>;
		assert.equal(wind.sms_threshold, undefined);
	});

	test('gesetzter Editor-Wert ueberschreibt/ersetzt den Bestands-Altwert', () => {
		const displayConfig: DisplayConfigBestand = {
			metrics: [{ metric_id: 'wind', sms_threshold: 42 } as unknown as { metric_id: string }],
		};
		const buckets = { primary: ['wind'], secondary: [], off: [] };
		const out = buildGlobalMetricsForSave(
			displayConfig, buckets, {}, {}, catalog, { wind: '15' }, SMS_THRESHOLD_METRIC_IDS,
		);
		const wind = out.find((m) => m.metric_id === 'wind') as unknown as Record<string, unknown>;
		assert.equal(wind.sms_threshold, 15, `Erwartet den neuen Editor-Wert 15, erhalten ${JSON.stringify(wind.sms_threshold)}.`);
	});

	test('gesetzter Editor-Wert ohne Bestand wird trotzdem uebernommen', () => {
		const buckets = { primary: ['wind'], secondary: [], off: [] };
		const out = buildGlobalMetricsForSave({}, buckets, {}, {}, catalog, { wind: '7' }, SMS_THRESHOLD_METRIC_IDS);
		const wind = out.find((m) => m.metric_id === 'wind') as unknown as Record<string, unknown>;
		assert.equal(wind.sms_threshold, 7);
	});
});
