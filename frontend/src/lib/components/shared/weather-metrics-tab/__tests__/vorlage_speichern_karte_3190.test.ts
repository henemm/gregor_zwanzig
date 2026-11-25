// Issue #3190 (Epic #2913), Fix-Loop nach Adversary (F001-F003): geteilte Bedienlogik der Karte
// „Als eigene Vorlage speichern“ ($lib/utils/vorlageSpeichernKarte.ts) und der Auslöser im Alt-Editor.
// Spec: docs/specs/modules/feat_3190_vorlage_dialog_inline.md (AC-6, AC-7, AC-8, AC-10)
//
// Die Logik ist dieselbe, die SavePresetDialog (Escape, Fokus ins Namensfeld), VorlageKarte (Reiter Wetter)
// und WeatherMetricsTab (Alt-Editor) aufrufen; die Attrappe mit `focus()` steht für den echten Knopf bzw.
// das echte Namensfeld. Die Browser-Verdrahtung prüft das Staging-E2E s3a2794-teil3-vorlage-inline.spec.ts.
//
//   cd frontend && npm test -- src/lib/components/shared/weather-metrics-tab/__tests__/vorlage_speichern_karte_3190.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { register } from 'node:module';
import { fileURLToPath, pathToFileURL } from 'node:url';
import path from 'node:path';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const FRONTEND = path.resolve(HERE, '../../../../../..');
register(pathToFileURL(path.join(FRONTEND, 'test-svelte-ssr-hooks.mjs')).href, pathToFileURL(FRONTEND + '/').href);
const { render } = await import('svelte/server');
const K = await import(pathToFileURL(path.join(FRONTEND, 'src/lib/utils/vorlageSpeichernKarte.ts')).href);
// #3020 S1: Alt-Bausteine (fallen mit S3). Fehlen sie, scheitern nur ihre Faelle.
const alt = async (datei: string) => await import(pathToFileURL(path.resolve(HERE, datei)).href).catch(() => ({}));
const PresetBar = (await alt('../WeatherV2PresetBar.svelte')).default;
const { routeRendern } = await alt('f5Altbausteine.ts');

/** Attrappe eines fokussierbaren Elements: zählt die focus()-Aufrufe. */
function knopf() {
	const k = { fokus: 0, focus() { k.fokus += 1; } };
	return k;
}
const tag = (h: string, testid: string) => h.match(new RegExp(`<[a-z0-9]+\\b[^>]*\\sdata-testid="${testid}"[^>]*>`))?.[0] ?? '';
const attr = (t: string, name: string) => t.match(new RegExp(`\\s${name}="([^"]*)"`))?.[1] ?? null;

describe('#3190 F003/AC-6: Escape in der Karte', () => {
	test('Escape schließt, solange nicht gespeichert wird', () => {
		assert.equal(K.karteSchliesstPerTaste('Escape', false), true);
	});
	test('Escape während des Speicherns ist wirkungslos (Abbrechen ist dann gesperrt)', () => {
		assert.equal(K.karteSchliesstPerTaste('Escape', true), false);
	});
	test('andere Tasten schließen nie', () => {
		for (const taste of ['Enter', 'Tab', ' ', 'Esc']) assert.equal(K.karteSchliesstPerTaste(taste, false), false, taste);
	});
});

describe('#3190 F002/AC-7: Escape am Fenster schließt nur die offene Vorlagen-Auswahl', () => {
	test('Auswahl offen + Escape ⇒ schließen; zu oder andere Taste ⇒ nichts', () => {
		assert.equal(K.pickerSchliesstPerTaste('Escape', true), true);
		assert.equal(K.pickerSchliesstPerTaste('Escape', false), false);
		assert.equal(K.pickerSchliesstPerTaste('Enter', true), false);
	});
});

describe('#3190 F002/AC-8: Fokus ins Namensfeld beim Öffnen', () => {
	test('offen ⇒ Namensfeld bekommt den Fokus, nichts wird zurückgesetzt', () => {
		const feld = knopf();
		assert.equal(K.beiKartenWechsel(true, feld), 'fokus');
		assert.equal(feld.fokus, 1);
	});
	test('offen, Feld noch nicht da ⇒ kein Fehler, kein Zurücksetzen', () => {
		assert.equal(K.beiKartenWechsel(true, null), 'fokus');
	});
	test('geschlossen ⇒ zurücksetzen, kein Fokus', () => {
		const feld = knopf();
		assert.equal(K.beiKartenWechsel(false, feld), 'zuruecksetzen');
		assert.equal(feld.fokus, 0);
	});
});

describe('#3190 F001/AC-1/AC-6/AC-10: Auslöser schaltet um und bekommt den Fokus zurück', () => {
	test('Klick öffnet, zweiter Klick schließt', () => {
		const a = K.speicherKarteAusloeser();
		const k = knopf();
		assert.equal(a.umschalten(k, false), true);
		assert.equal(a.umschalten(k, true), false);
	});
	test('nach Abbrechen/Escape/Speichern geht der Fokus auf den zuletzt geklickten Auslöser', () => {
		const a = K.speicherKarteAusloeser();
		const k = knopf();
		a.zurueck(); // noch nie geklickt: nichts
		a.umschalten(k, false);
		a.zurueck();
		assert.equal(k.fokus, 1);
	});
	test('ohne Element (z. B. Aufruf ohne Klick) bleibt der gemerkte Auslöser', () => {
		const a = K.speicherKarteAusloeser();
		const k = knopf();
		a.umschalten(k, false);
		a.umschalten(null, true);
		a.zurueck();
		assert.equal(k.fokus, 1);
	});
});

describe('#3190 F001/AC-10: Auslöser im Alt-Editor (WeatherV2PresetBar)', () => {
	const props = (saveOpen: boolean) => ({
		selectedTemplate: 'x',
		dirty: true,
		templates: [],
		userPresets: [],
		onSelectPreset: () => {},
		onOpenSaveDialog: () => {},
		saveOpen,
		saveCardId: 'karte-1'
	});
	for (const offen of [true, false]) {
		test(`Karte ${offen ? 'offen' : 'zu'}: aria-expanded=${offen}, aria-controls zeigt auf die Karte`, () => {
			const t = tag(render(PresetBar, { props: props(offen) }).body, 'weather-preset-save-link');
			assert.ok(t, 'Auslöser fehlt');
			assert.equal(attr(t, 'aria-expanded'), String(offen));
			assert.equal(attr(t, 'aria-controls'), 'karte-1');
		});
	}
	test('WeatherMetricsTab verdrahtet Auslöser und Karte: aria-controls = id der Karte, aria-expanded=true', () => {
		const h = routeRendern({ showSavePresetDialog: true, pendingPreset: 'wandern' });
		const t = tag(h, 'weather-preset-save-link');
		assert.ok(t, `Auslöser fehlt (Profil geändert?): ${h.slice(0, 200)}`);
		assert.equal(attr(t, 'aria-expanded'), 'true');
		const id = attr(tag(h, 'save-preset-dialog'), 'id');
		assert.ok(id, 'Karte ohne id');
		assert.equal(attr(t, 'aria-controls'), id);
	});
	test('WeatherMetricsTab Karte zu: aria-expanded=false', () => {
		const t = tag(routeRendern({ pendingPreset: 'wandern' }), 'weather-preset-save-link');
		assert.ok(t, 'Auslöser fehlt');
		assert.equal(attr(t, 'aria-expanded'), 'false');
	});
});
