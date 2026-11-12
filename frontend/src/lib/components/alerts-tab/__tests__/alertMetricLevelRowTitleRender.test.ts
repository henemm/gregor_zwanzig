// #2793 S2b (Spec feat_2793_s2_alarm_stufenwechsel.md §6, AC-19): die Tabelle
// „Alarm-Empfindlichkeit" ist bis S3a NUR LESBAR. Diese Datei rendert die
// echten Svelte-Komponenten serverseitig (svelte/server `render()`, Hooks:
// frontend/test-svelte-ssr-hooks.mjs) und prueft am erzeugten HTML.
//
// Vorher (#1592 C3 F001) bewachte sie das `title`-Attribut der CAPE-
// Schwellwert-Zelle. Diese Δ-Spalte entfaellt mit S2b (die Alarme folgen der
// Ampel); die Zusicherungen „CAPE-title" / „wind_gust ohne title" werden zu
// „keine Schwellwert-Zelle mehr" (unten, F001-Nachfolge).
//
// Pfadregel #1409: alle Pfade relativ zu DIESER Datei.
//
//   cd frontend && npm test -- src/lib/components/alerts-tab/__tests__/alertMetricLevelRowTitleRender.test.ts

import { test, afterEach } from 'node:test';
import assert from 'node:assert/strict';
import { register } from 'node:module';
import { fileURLToPath, pathToFileURL } from 'node:url';
import path from 'node:path';

const HERE = path.dirname(fileURLToPath(import.meta.url));
// __tests__ -> alerts-tab -> components -> lib -> src -> frontend
const FRONTEND = path.resolve(HERE, '../../../../..');

register(
	pathToFileURL(path.join(FRONTEND, 'test-svelte-ssr-hooks.mjs')).href,
	pathToFileURL(FRONTEND + '/').href
);

const { render } = await import('svelte/server');
const { locale } = await import(pathToFileURL(path.join(FRONTEND, 'src/lib/i18n/index.ts')).href);
const komp = async (rel: string) =>
	(await import(pathToFileURL(path.join(FRONTEND, 'src/lib/components/alerts-tab', rel)).href)).default;
const AlertMetricLevelTable = await komp('AlertMetricLevelTable.svelte');
const { alarmAbZeile, vorlageIdFuer } = await import(
	pathToFileURL(path.join(FRONTEND, 'src/lib/components/alerts-tab/alarmAbAnzeige.ts')).href
);

afterEach(() => locale.set('de'));

const VORLAGEN = {
	allgemein: { template: 'allgemein', metrics: { gust: { alarm_ab: 'orange' }, temperature: { alarm_ab: 'orange' } } },
	skitouren: { template: 'skitouren', metrics: { gust: { alarm_ab: 'red' }, temperature: { alarm_ab: 'yellow' } } }
};

function tabelle(props: Record<string, unknown>): string {
	return render(AlertMetricLevelTable, { props }).body;
}
const zelle = (html: string, metric: string): string => {
	const m = new RegExp(`data-testid="alert-alarm-ab-${metric}"[^>]*>([^<]*)<`).exec(html);
	assert.ok(m, `Zelle „Alarm ab" fuer ${metric} fehlt`);
	return m![1].trim();
};

test('Trip und Vergleich: je Zeile „Alarm ab" aus der Abo-Ampel, sonst aus der Vorlage (DE)', () => {
	const html = tabelle({
		activeMetrics: ['wind_gust', 'temperature_min', 'humidity', 'freezing_level', 'cape'],
		levels: { wind_gust: 'sensibel', freezing_level: 'entspannt' },
		aboAmpel: { template: 'allgemein', metrics: { gust: { alarm_ab: 'yellow' } } },
		vorlage: VORLAGEN.allgemein
	});
	assert.equal(zelle(html, 'wind_gust'), 'Alarm ab: Gelb', 'Abo-Wert geht vor (nicht die Altstufe „sensibel")');
	assert.equal(zelle(html, 'temperature_min'), 'Alarm ab: Orange', 'Vorgabe der Vorlage');
	assert.equal(zelle(html, 'humidity'), 'kein Alarm (Vorbote)');
	assert.equal(zelle(html, 'freezing_level'), 'Entspannt', 'D4 zeigt die heutige Stufe');
	assert.equal(zelle(html, 'cape'), 'Alarm ab: Nie', 'CAPE alarmiert nicht mehr eigenstaendig (P1)');
	assert.ok(
		html.includes('Alarme folgen jetzt der Ampel. ‚Alarm ab‘ stellst du im Reiter Wetter ein.'),
		'Hinweis oben fehlt'
	);
});

test('nur lesbar: keine Stufen-Knoepfe, keine Schnellwahl, keine Δ-Schwellwert-Zelle', () => {
	const html = tabelle({ activeMetrics: ['wind_gust', 'cape'], levels: {}, vorlage: VORLAGEN.allgemein });
	// Einziger Knopf bleibt das ⓘ an der CAPE-Zeile (BegriffErklaerung).
	assert.equal((html.match(/<button/g) ?? []).length, 1, 'nur das ⓘ darf ein Knopf sein');
	for (const verboten of ['data-testid="alert-quickset', 'data-testid="alert-level-', 'data-testid="alert-threshold-'])
		assert.equal(html.includes(verboten), false, `steht noch: ${verboten}`);
});

test('EN: Hinweis und Stufen aus dem Katalog, Protokoll-Kennung bleibt gleich', () => {
	locale.set('en');
	const html = tabelle({ activeMetrics: ['wind_gust', 'humidity'], levels: {}, vorlage: VORLAGEN.allgemein });
	assert.equal(zelle(html, 'wind_gust'), 'Alert from: Orange');
	assert.equal(zelle(html, 'humidity'), 'no alert (precursor)');
	assert.ok(html.includes('Alerts now follow the traffic light. You set ‘Alert from’ in the Weather tab.'), html);
	assert.ok(html.includes('data-alarm-ab="orange"'), 'Kennung ist Protokoll-Token, sprachunabhaengig');
});

test('Vorlage noch nicht geladen: kein geratenes „Nie", sondern „—"', () => {
	const html = tabelle({ activeMetrics: ['wind_gust'], levels: {}, aboAmpel: null, vorlage: null });
	assert.equal(zelle(html, 'wind_gust'), 'Alarm ab: —');
});

test('Vorlagen-Rueckfall wie Python: ampel.template -> preset_name -> profil -> allgemein (zwei Abos, zwei Ergebnisse)', () => {
	assert.equal(vorlageIdFuer({ template: 'skitouren' }, 'wandern', null, VORLAGEN), 'skitouren');
	assert.equal(vorlageIdFuer(null, 'skitouren', null, VORLAGEN), 'skitouren');
	assert.equal(vorlageIdFuer(null, null, 'SKITOUREN', VORLAGEN), 'skitouren');
	assert.equal(vorlageIdFuer(null, null, null, VORLAGEN), 'allgemein');
	assert.equal(vorlageIdFuer({ template: 'gibtsnicht' }, null, null, VORLAGEN), 'allgemein');
	const a = alarmAbZeile('wind_gust', null, VORLAGEN.allgemein, {});
	const b = alarmAbZeile('wind_gust', null, VORLAGEN.skitouren, {});
	assert.deepEqual([a, b], [{ art: 'ampel', stufe: 'orange' }, { art: 'ampel', stufe: 'red' }]);
});
