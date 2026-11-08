// #2793 S2b (Spec feat_2793_s2_alarm_stufenwechsel.md §1 D4, §6, AC-19),
// Fix-Loop 3 nach Adversary F202/F203: zwei Anzeige-Rueckfaelle des nur
// lesbaren Reiters, gemessen an der GERENDERTEN Zeile des echten geteilten
// Reiters (shared/AlarmeTab.svelte, SSR ueber den F7-Pruefstand), nicht an der
// Hilfsfunktion:
//   F202 — D4-Zeile (Nullgradgrenze) ohne gespeicherten Eintrag zeigt
//          „Standard" (wie heute, Spec §1: „ohne Eintrag ‚standard‘").
//   F203 — Orts-Vergleich ohne `ampel.template` mit Profil `summer_trekking`
//          zeigt die Vorgabe der Vorlage „alpen-trekking" (wie Python
//          `app.ampel._PROFIL_ZU_VORLAGE`), nicht die von „allgemein".
//
// Pfadregel #1409: alle Pfade relativ zu DIESER Datei (ueber f7Pruefstand.ts).
//
//   cd frontend && npm test -- src/lib/components/alerts-tab/__tests__/alarm_ab_d4_rueckfall_und_profil_vorlage_render.test.ts

import { test, afterEach } from 'node:test';
import assert from 'node:assert/strict';

const { alarmeRoute, alarmeVergleich, wizard, locale, VORLAGEN_ALLGEMEIN } = await import('./f7Pruefstand.ts');

afterEach(() => locale.set('de'));

const zelle = (html: string, metric: string): string => {
	const m = new RegExp(`data-testid="alert-alarm-ab-${metric}"[^>]*>([^<]*)<`).exec(html);
	assert.ok(m, `Zelle „Alarm ab" fuer ${metric} fehlt: ${html}`);
	return m![1].trim();
};

test('F202 Trip: Nullgradgrenze ohne gespeicherte Stufe zeigt „Standard", nicht „Aus"', () => {
	const html = alarmeRoute({
		activeMetrics: ['freezing_level', 'thunder_onset'],
		metricLevels: { thunder_onset: 'off' }
	});
	assert.equal(zelle(html, 'freezing_level'), 'Standard', 'ohne Eintrag gilt „standard" (D4, wie heute)');
	assert.equal(zelle(html, 'thunder_onset'), 'Aus', 'Kontrolle: ein gespeichertes „off" bleibt „Aus"');
});

test('F202 EN: derselbe Rueckfall in der Nutzersprache', () => {
	locale.set('en');
	const html = alarmeRoute({ activeMetrics: ['freezing_level'], metricLevels: {} });
	assert.equal(zelle(html, 'freezing_level'), 'Standard');
});

// Vorlagen-Antwort mit unterscheidbarer Vorgabe fuer Boeen: allgemein orange,
// alpen-trekking rot.
const VORLAGEN = {
	...VORLAGEN_ALLGEMEIN,
	'alpen-trekking': { template: 'alpen-trekking', metrics: { gust: { alarm_ab: 'red' } } }
};

test('F203 Vergleich: Profil summer_trekking ohne ampel.template zeigt die Vorgabe von „alpen-trekking"', () => {
	const preset = { id: 'v-st', name: 'Hochtour', location_ids: ['l1'], profil: 'summer_trekking' };
	const html = alarmeVergleich(wizard(), { preset, templatesOverride: VORLAGEN });
	assert.equal(zelle(html, 'wind_gust'), 'Alarm ab: Rot', 'summer_trekking -> alpen-trekking (wie Python)');

	// Kontrolle: ohne Profil faellt dieselbe Zeile auf „allgemein" (Orange) —
	// die beiden Vorlagen sind also unterscheidbar.
	const ohne = alarmeVergleich(wizard(), { preset: { ...preset, profil: undefined }, templatesOverride: VORLAGEN });
	assert.equal(zelle(ohne, 'wind_gust'), 'Alarm ab: Orange');
});

// Fix-Loop 4, F305 (Spec §6 / AC-19): die Vorlage ist geladen, hat fuer Boeen
// aber KEINE `alarm_ab`-Zeile. Python (`app.ampel`) liest dann „never" — die
// Anzeige muss dasselbe sagen („Nie"), nicht den Strich, der allein
// „Vorlage noch nicht geladen" bedeutet.
const VORLAGE_OHNE_BOEEN = { allgemein: { template: 'allgemein', metrics: {} } };

test('F305 Vergleich: Vorlage ohne Boeen-Zeile zeigt „Alarm ab: Nie", nicht den Strich', () => {
	const html = alarmeVergleich(wizard(), { templatesOverride: VORLAGE_OHNE_BOEEN });
	assert.equal(zelle(html, 'wind_gust'), 'Alarm ab: Nie', 'geladene Vorlage ohne Zeile = Nie');

	// Kontrolle: ist die Vorlage NICHT geladen (leere Antwort), bleibt es beim
	// Strich — beide Zustaende sind an der Zeile unterscheidbar.
	const ungeladen = alarmeVergleich(wizard(), { templatesOverride: {} });
	assert.notEqual(zelle(ungeladen, 'wind_gust'), 'Alarm ab: Nie', 'ungeladen darf nicht „Nie" raten');
});

test('F305 Trip EN: derselbe Rueckfall in der Nutzersprache', () => {
	locale.set('en');
	const html = alarmeRoute({ activeMetrics: ['wind_gust'], templatesOverride: VORLAGE_OHNE_BOEEN });
	assert.equal(zelle(html, 'wind_gust'), 'Alert from: Never');
});
