// Issue #2660 (i18n F11, Adversary-Finding F001) — die TS-Hilfsmodule bauen
// ihre Anzeigetexte bei JEDEM Aufruf in der dann gueltigen Sprache: dasselbe
// geladene Modul liefert unter `de` die Golden-Literale (wortgleich zum Stand
// vor der Umstellung) und nach `locale.set('en')` ohne Neuladen die englischen
// Katalogtexte (trFor). Eine Verfaelschung `tr(...)` -> `trFor('de', ...)` macht
// jeden en-Teil rot.
// Spec: docs/specs/modules/i18n_f11_bausteine_ts_2660.md
//
//   cd frontend && npm test -- src/lib/utils/__tests__/hilfstexte_sprache.test.ts

import { test, describe, afterEach } from 'node:test';
import assert from 'node:assert/strict';
import { computeHorizonSummary } from '../horizonHelpers.ts';
import { riskToPill } from '../stageRisk.ts';
import { setupStepTrip, setupStepCompare } from '../cockpitHelpers568.ts';
import { getPresetLabel } from '../rightColumn.ts';
import { profileSignature } from '../profileSignature.ts';
import { locale, trFor } from '../../i18n/index.ts';
import type { ComparePreset, Trip } from '../../types.ts';

afterEach(() => locale.set('de'));

const h = (today: boolean, tomorrow: boolean, day_after: boolean) => ({
	metric_id: `m-${today}${tomorrow}${day_after}`,
	horizons: { today, tomorrow, day_after }
});
const HORIZONTE = [h(true, true, true), h(true, true, false), h(true, false, false), h(false, true, true), h(false, false, true)];
const tripMitProfil = (profile: string) => ({ id: 't', name: 'T', stages: [], aggregation: { profile } }) as unknown as Trip;
const TRIP = { id: 't1', name: 'T', stages: [] } as unknown as Trip;
const PRESET = { id: 'c1', name: 'C', location_ids: [] } as unknown as ComparePreset;
const labels = (steps: { label: string }[]) => steps.map((s) => s.label);

describe('F001: Hilfstexte folgen der Sprache zum Aufrufzeitpunkt (de -> en ohne Neuladen)', () => {
	test('computeHorizonSummary', () => {
		locale.set('de');
		assert.equal(
			computeHorizonSummary(HORIZONTE),
			'1 alle drei Tage · 1 nur heute + morgen · 1 nur heute · 1 nur morgen + übermorgen · 1 sonstige Kombinationen'
		);
		locale.set('en');
		const p = { anzahl: 1 };
		assert.equal(
			computeHorizonSummary(HORIZONTE),
			[
				trFor('en', 'bausteine.horizont.alle_drei', p),
				trFor('en', 'bausteine.horizont.nur_heute_morgen', p),
				trFor('en', 'bausteine.horizont.nur_heute', p),
				trFor('en', 'bausteine.horizont.nur_morgen_uebermorgen', p),
				trFor('en', 'bausteine.horizont.sonstige', p)
			].join(' · ')
		);
		assert.doesNotMatch(computeHorizonSummary(HORIZONTE), /[äöü]|heute|morgen|sonstige/);
	});

	test('stageRisk: riskToPill', () => {
		locale.set('de');
		assert.deepEqual(['red', 'yellow', 'green'].map((r) => riskToPill(r as 'red').label), ['Risiko', 'Achten', 'OK']);
		locale.set('en');
		assert.equal(riskToPill('red').label, trFor('en', 'bausteine.risiko.rot'));
		assert.equal(riskToPill('yellow').label, trFor('en', 'bausteine.risiko.gelb'));
		assert.equal(riskToPill('green').label, trFor('en', 'bausteine.risiko.gruen'));
		assert.notEqual(riskToPill('red').label, 'Risiko');
		assert.equal(riskToPill(null).label, '—');
	});

	test('cockpitHelpers568: beide Checklisten (Trip und Ortsvergleich)', () => {
		locale.set('de');
		assert.deepEqual(labels(setupStepTrip(TRIP)), ['Route', 'Etappen', 'Wetter', 'Layout', 'Reports']);
		assert.deepEqual(labels(setupStepCompare(PRESET)), ['Vergleich', 'Orte', 'Wertebereiche', 'Layout', 'Versand']);
		locale.set('en');
		const en = (k: string) => trFor('en', `bausteine.checkliste.${k}` as never);
		assert.deepEqual(labels(setupStepTrip(TRIP)), ['route', 'etappen', 'wetter', 'layout', 'reports'].map(en));
		assert.deepEqual(labels(setupStepCompare(PRESET)), ['vergleich', 'orte', 'wertebereiche', 'layout', 'versand'].map(en));
		assert.notDeepEqual(labels(setupStepTrip(TRIP)), ['Route', 'Etappen', 'Wetter', 'Layout', 'Reports']);
		assert.notDeepEqual(labels(setupStepCompare(PRESET)), ['Vergleich', 'Orte', 'Wertebereiche', 'Layout', 'Versand']);
	});

	test('rightColumn: Profil-Standard-Beschriftungen', () => {
		const faelle = [
			['wintersport', 'Wintersport-Standard', 'bausteine.profil.standard_wintersport'],
			['wandern', 'Wandern-Standard', 'bausteine.profil.standard_wandern'],
			['summer_trekking', 'Sommer-Trekking-Standard', 'bausteine.profil.standard_summer_trekking'],
			['allgemein', 'Standard-Metriken', 'bausteine.profil.standard_metriken'],
			['unbekannt', 'Standard-Metriken', 'bausteine.profil.standard_metriken']
		] as const;
		locale.set('de');
		for (const [profil, golden] of faelle) assert.equal(getPresetLabel(tripMitProfil(profil)), golden, profil);
		locale.set('en');
		for (const [profil, golden, key] of faelle) {
			assert.equal(getPresetLabel(tripMitProfil(profil)), trFor('en', key), profil);
			assert.notEqual(getPresetLabel(tripMitProfil(profil)), golden, profil);
		}
	});

	test('profileSignature: Eyebrow', () => {
		const faelle = [
			['wintersport', 'Wintersport', 'bausteine.profil.wintersport'],
			['wandern', 'Wandern', 'bausteine.profil.wandern'],
			['summer_trekking', 'Sommer-Trekking', 'bausteine.profil.summer_trekking'],
			['allgemein', 'Allgemein', 'bausteine.profil.allgemein'],
			[null, 'Allgemein', 'bausteine.profil.allgemein']
		] as const;
		locale.set('de');
		for (const [profil, golden] of faelle) assert.equal(profileSignature(profil).eyebrow, golden, String(profil));
		locale.set('en');
		for (const [profil, golden, key] of faelle) {
			assert.equal(profileSignature(profil).eyebrow, trFor('en', key), String(profil));
			assert.notEqual(profileSignature(profil).eyebrow, golden, String(profil));
		}
		assert.equal(profileSignature('wandern').icon, '\u{1F97E}');
	});
});
