// #3399 S1 (AC-1, AC-7): der Alarme-Reiter uebernimmt die Vorlagen-ID des Servers.
// Spec: docs/specs/modules/rework_3399_vorlage_aufloesung.md (AC-1, AC-7, S1).
//
// Gemessen an der GERENDERTEN Zeile „Alarm ab" der echten Komponente (SSR ueber den F7-Pruefstand).
// SSR fuehrt onMount nie aus; der Zustand „Antwort steht aus" ist also der SSR-Ausgangszustand. Den
// geladenen Zustand steuert der Testhaken `vorlageIdOverride` (Muster templatesOverride/profileOverride,
// RED-Vertrag): `undefined` = Aufloesung laeuft/ungeladen => „—"; `null` = Aufloesung gescheitert =>
// „—"; Text = vom Server aufgeloeste Vorlagen-ID (der Lader aus vorlagenIdLader.ts liefert sie
// produktiv). Die ID in den Tests kommt aus dem ECHTEN resolve_entwurf (aufgeloestVon).
//
// Alt (ROT): AlarmeTab bestimmt die ID selbst per vorlageIdFuer (ignoriert preset_name des
// Ortsvergleichs und den Haken).
//
//   cd frontend && npm test -- src/lib/components/shared/__tests__/alarme_vorlage_aufloesung_3399.test.ts

import { test, afterEach } from 'node:test';
import assert from 'node:assert/strict';
import { aufgeloestVon } from '../wetter-tab/__tests__/wetterTabDaten.ts';

const { alarmeRoute, alarmeVergleich, wizard, locale } = await import('../../alerts-tab/__tests__/f7Pruefstand.ts');

afterEach(() => locale.set('de'));

const zelle = (html: string, metric: string): string => {
	const m = new RegExp(`data-testid="alert-alarm-ab-${metric}"[^>]*>([^<]*)<`).exec(html);
	assert.ok(m, `Zelle „Alarm ab" fuer ${metric} fehlt`);
	return m![1].trim();
};

/** Vorlagen-Ampeln wie GET /api/templates, mit unterscheidbarer Vorgabe je Vorlage. */
const VORLAGEN = {
	allgemein: { template: 'allgemein', metrics: { gust: { alarm_ab: 'orange' }, temperature: { alarm_ab: 'orange' } } },
	skitouren: { template: 'skitouren', metrics: { gust: { alarm_ab: 'red' }, temperature: { alarm_ab: 'yellow' } } },
	wandern: { template: 'wandern', metrics: { gust: { alarm_ab: 'yellow' }, temperature: { alarm_ab: 'red' } } }
};
const METRIKEN = ['wind_gust', 'temperature_min'];

test('AC-1 Trip: solange die Aufloesung aussteht, steht „—" (nicht die Vorgabe von „allgemein")', () => {
	const html = alarmeRoute({ activeMetrics: METRIKEN, metricLevels: {}, templatesOverride: VORLAGEN });
	assert.equal(zelle(html, 'wind_gust'), 'Alarm ab: —');
	assert.equal(zelle(html, 'temperature_min'), 'Alarm ab: —');
});

test('AC-1 Vergleich: solange die Aufloesung aussteht, steht „—"', () => {
	const html = alarmeVergleich(wizard(), { templatesOverride: VORLAGEN });
	assert.equal(zelle(html, 'wind_gust'), 'Alarm ab: —');
});

test('AC-1 Fehler: gescheiterte Aufloesung (null) zeigt „—", kein geratenes „Nie" oder „Allgemein"', () => {
	const trip = alarmeRoute({ activeMetrics: METRIKEN, metricLevels: {}, templatesOverride: VORLAGEN, vorlageIdOverride: null });
	assert.equal(zelle(trip, 'wind_gust'), 'Alarm ab: —');
	const vergleich = alarmeVergleich(wizard(), { templatesOverride: VORLAGEN, vorlageIdOverride: null });
	assert.equal(zelle(vergleich, 'wind_gust'), 'Alarm ab: —');
});

test('AC-1 Trip: die Vorgabe stammt aus der Vorlage, die der Server aufloest', () => {
	const trip = { id: 't1', name: 'T', stages: [], alert_rules: [], display_config: { preset_name: 'skitouren' } };
	const id = aufgeloestVon(trip).vorlage_id;
	assert.equal(id, 'skitouren');
	const html = alarmeRoute({ trip, activeMetrics: METRIKEN, metricLevels: {}, templatesOverride: VORLAGEN, vorlageIdOverride: id });
	assert.equal(zelle(html, 'wind_gust'), 'Alarm ab: Rot');
	assert.equal(zelle(html, 'temperature_min'), 'Alarm ab: Gelb');
});

test('AC-1/AC-9 Vergleich: preset_name gilt (der Server rangiert ihn), die alte Frontend-Rangfolge ignorierte ihn', () => {
	const preset = { id: 'v1', name: 'V', location_ids: ['l1'], display_config: { preset_name: 'wandern' } };
	const id = aufgeloestVon(preset).vorlage_id;
	assert.equal(id, 'wandern');
	const html = alarmeVergleich(wizard(), { preset, templatesOverride: VORLAGEN, vorlageIdOverride: id });
	assert.equal(zelle(html, 'wind_gust'), 'Alarm ab: Gelb', 'Vorgabe der Server-Vorlage „wandern", nicht „allgemein" (Orange)');
	assert.equal(zelle(html, 'temperature_min'), 'Alarm ab: Rot');
});

test('AC-1 EN: dieselbe Zeile in der Nutzersprache, „—" bis zur Antwort', () => {
	locale.set('en');
	const wartet = alarmeRoute({ activeMetrics: METRIKEN, metricLevels: {}, templatesOverride: VORLAGEN });
	assert.equal(zelle(wartet, 'wind_gust'), 'Alert from: —');
	const geladen = alarmeRoute({ activeMetrics: METRIKEN, metricLevels: {}, templatesOverride: VORLAGEN, vorlageIdOverride: 'skitouren' });
	assert.equal(zelle(geladen, 'wind_gust'), 'Alert from: Red');
});

test('AC-7: die Vorgabe ist der Wert der Vorlage, nie der Abo-abweichende der aufgeloesten Ampel', () => {
	// Ortsvergleich: Vorlage „wandern" per preset_name; die Abo-Ampel ueberschreibt NUR Boeen (rot).
	const preset = {
		id: 'v2',
		name: 'V2',
		location_ids: ['l1'],
		display_config: { preset_name: 'wandern', ampel: { metrics: { gust: { alarm_ab: 'red' } } } }
	};
	const aufgeloest = aufgeloestVon(preset);
	assert.equal(aufgeloest.vorlage_id, 'wandern');
	assert.equal(aufgeloest.ampel.metrics.gust.alarm_ab, 'red', 'Kontrolle: die aufgeloeste Ampel enthaelt die Abo-Abweichung');
	const html = alarmeVergleich(wizard(), { preset, templatesOverride: VORLAGEN, vorlageIdOverride: aufgeloest.vorlage_id });
	// Boeen: der Abo-Wert gilt (wie bisher), Temperatur ohne Abo-Wert: Vorgabe der Vorlage „wandern" (Rot), nicht Orange
	assert.equal(zelle(html, 'wind_gust'), 'Alarm ab: Rot');
	assert.equal(zelle(html, 'temperature_min'), 'Alarm ab: Rot', 'Vorgabe aus /api/templates „wandern"');
	// Abo ohne eigene Ampel-Abweichung: die Vorgabe ist exakt der Vorlagenwert
	const ohne = alarmeVergleich(wizard(), {
		preset: { ...preset, display_config: { preset_name: 'wandern' } },
		templatesOverride: VORLAGEN,
		vorlageIdOverride: 'wandern'
	});
	assert.equal(zelle(ohne, 'wind_gust'), 'Alarm ab: Gelb', 'Vorlagenwert Boeen „wandern" (Gelb), ohne Abo-Abweichung');
});
