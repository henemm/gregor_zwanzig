// Issue #2792 S1a Fix-Loop (Adversary F-E): die VERDRAHTUNG des Anwendens einer
// Vorlage in `WeatherMetricsTab.svelte` als Verhalten — nicht nur der Helfer
// `ampelBeimAnwenden`. Gemessen wird ueber den ECHTEN Instanz-Skript-Pruefstand
// (`svelteInstanzPruefstand.ts`, Praezedenz
// `wetter_metriken_trip_speichert_eigene_ausblick_und_warnungswerte.test.ts`):
// die echten Funktionen `applyPreset`, `onPresetSaved` und `buildWeatherPayload`
// aus dem Quelltext, ausgefuehrt gegen einen gesaeten Trip-Mount (context=route).
//
//   1. Anwenden einer eigenen Vorlage -> Nutzlast traegt deren Ampel samt alarm_ab.
//   2. Anwenden einer eingebauten Vorlage -> Nutzlast traegt {template: <id>}.
//   3. „Als Vorlage speichern" (onPresetSaved, neue Vorlage ohne Ampel) laesst
//      die zuvor angewendete Ampel stehen statt auf „allgemein" zu fallen.
//   4. Ohne Anwenden geht keine Ampel mit (gespeicherte Ampel bleibt unberuehrt).
//
// Spec: docs/specs/modules/feat_2792_s1_profil_ampel.md §2 (AC-14)
// Pfadregel #1409: relativ zu DIESER Datei.
//
// Ausfuehren:
//   cd frontend && npm test -- \
//     src/lib/components/shared/__tests__/wetter_metriken_vorlage_anwenden_sendet_ampel.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { umgebungFuer, type Knoten } from './svelteInstanzPruefstand.ts';

const TAB = join(dirname(fileURLToPath(import.meta.url)), '..', 'WeatherMetricsTab.svelte');

const MEIN_GIPFEL = {
	id: 'p-gipfel',
	name: 'Mein Gipfel',
	is_default: false,
	created_at: '2026-11-01T10:00:00Z',
	metrics: [{ metric_id: 'wind', enabled: true, use_friendly_format: false }],
	ampel: {
		template: 'wandern',
		metrics: { wind: { upper: { yellow: 25, orange: 50, red: 70 }, alarm_ab: 'yellow' } },
	},
};
const KATALOG = {
	wind: [{ id: 'wind', label: 'Wind', default_enabled: true }],
	temperatur: [{ id: 'temperature', label: 'Temperatur', default_enabled: true }],
};

async function tab(): Promise<Knoten> {
	const { u } = await umgebungFuer(TAB, {
		context: 'route',
		untrack: (fn: () => unknown) => fn(),
		trip: { id: 't-2792', display_config: { metrics: [], preset_name: 'skitouren' } },
		createMode: false,
		catalog: KATALOG,
		catalogLoaded: true,
		templates: [{ id: 'skitouren', label: 'Skitouren', metrics: ['temperature', 'wind'] }],
		userPresets: [MEIN_GIPFEL],
		saveController: { schedule: () => {}, setDirty: () => {}, cancel: () => {}, markPristine: () => {}, setUnsavedInput: () => {} },
		flash: () => {},
		api: { put: async () => ({}), get: async () => [] },
	});
	for (const f of ['applyPreset', 'onPresetSaved', 'buildWeatherPayload']) {
		assert.strictEqual(typeof u[f], 'function', `Messaufbau kaputt: ${f} nicht herleitbar.`);
	}
	return u;
}

describe('WeatherMetricsTab: Anwenden einer Vorlage schreibt display_config.ampel (AC-14)', () => {
	test('ohne Anwenden geht keine Ampel mit', async () => {
		const u = await tab();
		assert.equal('ampel' in (u.buildWeatherPayload() as Knoten), false);
	});

	test('eigene Vorlage: Nutzlast traegt deren Ampel samt alarm_ab', async () => {
		const u = await tab();
		u.applyPreset('p-gipfel');
		const payload = u.buildWeatherPayload() as Knoten;
		assert.deepEqual(payload.ampel, MEIN_GIPFEL.ampel);
		assert.equal(payload.preset_name, 'p-gipfel');
	});

	test('eingebaute Vorlage: Nutzlast traegt nur die Vorlagen-ID', async () => {
		const u = await tab();
		u.applyPreset('p-gipfel');
		u.applyPreset('skitouren');
		assert.deepEqual((u.buildWeatherPayload() as Knoten).ampel, { template: 'skitouren' });
	});

	test('Als Vorlage speichern laesst die angewendete Ampel stehen', async () => {
		const u = await tab();
		u.applyPreset('p-gipfel');
		await u.onPresetSaved({ ...MEIN_GIPFEL, id: 'p-neu', name: 'Neu', ampel: undefined });
		const payload = u.buildWeatherPayload() as Knoten;
		assert.equal(payload.preset_name, 'p-neu');
		assert.deepEqual(payload.ampel, MEIN_GIPFEL.ampel);
	});
});
