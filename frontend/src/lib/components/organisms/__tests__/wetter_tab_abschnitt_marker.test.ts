// Issue #2913, Scheibe (c), Fix-Loop nach Staging-E2E: Abschnitts-Marker für den Elementlisten-Abgleich.
// frontend/e2e/elementliste-abgleich.staging.spec.ts sucht `[data-abschnitt="<name>"]`; die Elementliste
// (docs/context/einstellungen_neu/elementliste.json) nennt für den Reiter „wetter“ die Abschnitte
// `metriken`, `warnungen-radar` und `anpassen`.
//
//   WarnungenRadarKarte / AnpassenKarte: Server-Render, das äußerste Element trägt den Marker.
//   WetterTabInhalt: die Metrik-Karte erscheint erst nach dem Laden (onMount, im Server-Render nicht
//   erreichbar); geprüft wird am Template-Baum, dass genau das Element mit AlarmAbKopf, den Metrik-Gruppen
//   und NichtImBriefing den Marker trägt (doc-compliance-test).
//
//   cd frontend && npm test -- src/lib/components/organisms/__tests__/wetter_tab_abschnitt_marker.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { register } from 'node:module';
import { readFileSync } from 'node:fs';
import { fileURLToPath, pathToFileURL } from 'node:url';
import path from 'node:path';
import { parse } from 'svelte/compiler';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const FRONTEND = path.resolve(HERE, '../../../../..');
const WT = path.resolve(HERE, '..', 'wetter-tab');

register(pathToFileURL(path.join(FRONTEND, 'test-svelte-ssr-hooks.mjs')).href, pathToFileURL(FRONTEND + '/').href);
const { render } = await import('svelte/server');

const datei = (n: string) => path.join(WT, `${n}.svelte`);
const lade = async (n: string): Promise<any> => (await import(pathToFileURL(datei(n)).href)).default;
const html = (k: any, props: Record<string, unknown>) => render(k, { props }).body.replace(/<!--[\s\S]*?-->/g, '').trim();
const noop = () => {};
const ersterTag = (h: string) => h.match(/^<[a-z]+\b[^>]*>/)?.[0] ?? '';
const markerZahl = (h: string) => (h.match(/\sdata-abschnitt="/g) ?? []).length;

type Knoten = Record<string, any>;
function alle(x: unknown, pred: (n: Knoten) => boolean, aus: Knoten[] = []): Knoten[] {
	if (Array.isArray(x)) x.forEach((y) => alle(y, pred, aus));
	else if (x && typeof x === 'object') {
		const n = x as Knoten;
		if (pred(n)) aus.push(n);
		for (const [k, v] of Object.entries(n)) if (k !== 'parent') alle(v, pred, aus);
	}
	return aus;
}
const statischerWert = (el: Knoten, name: string): string | null => {
	const a = (el.attributes as Knoten[]).find((x) => x.type === 'Attribute' && x.name === name);
	if (!a || !Array.isArray(a.value) || a.value.length !== 1 || a.value[0].type !== 'Text') return null;
	return String(a.value[0].data);
};

describe('Abschnitts-Marker des Wetter-Reiters (Elementlisten-Abgleich)', () => {
	test('WarnungenRadarKarte: äußerstes Element trägt data-abschnitt="warnungen-radar"', async () => {
		const K = await lade('WarnungenRadarKarte');
		for (const mitRadar of [false, true]) {
			const h = html(K, { warnungenAn: true, radarAn: false, mitRadar, onWarnungen: noop, onRadar: noop });
			assert.match(ersterTag(h), /\sdata-abschnitt="warnungen-radar"/, `mitRadar=${mitRadar}: Marker fehlt am Wurzelelement`);
			assert.equal(markerZahl(h), 1, 'genau ein Abschnitts-Marker');
			assert.match(h, /data-testid="wetter-warnungen-schalter"/, 'Marker umschließt den Warnungen-Schalter');
		}
	});

	test('AnpassenKarte: äußerstes Element trägt data-abschnitt="anpassen" und umschließt den Aufklapper', async () => {
		const A = await lade('AnpassenKarte');
		const h = html(A, { tagesfenster: { start: 6, end: 20 }, onStart: noop, onEnde: noop });
		assert.match(ersterTag(h), /\sdata-abschnitt="anpassen"/, 'Marker fehlt am Wurzelelement');
		assert.equal(markerZahl(h), 1, 'genau ein Abschnitts-Marker');
		assert.match(h, /data-testid="wetter-anpassen-karte"/);
	});

	// doc-compliance-test: Metrik-Karte nur nach dem Laden sichtbar, im Server-Render nicht erreichbar.
	test('WetterTabInhalt: die Metrik-Karte (AlarmAbKopf, Gruppen, NichtImBriefing) trägt data-abschnitt="metriken"', () => {
		const a = parse(readFileSync(datei('WetterTabInhalt'), 'utf8'), { modern: true }) as unknown as Knoten;
		// feat_2913_abgleich_ganzseite AC-13: wt-laden/wt-fehler tragen zusätzlich `laden`/`warnung`;
		// `metriken` steht weiterhin an genau einem Element.
		const markiert = alle(a.fragment, (n) => n.type === 'RegularElement' && statischerWert(n, 'data-abschnitt') === 'metriken');
		assert.equal(markiert.length, 1, 'genau ein Element mit data-abschnitt="metriken" im Organismus');
		const el = markiert[0];
		assert.equal(statischerWert(el, 'data-abschnitt'), 'metriken');
		const kinder = (el.fragment?.nodes ?? []) as Knoten[];
		const direkt = (name: string) => kinder.some((c) => c.type === 'Component' && c.name === name);
		assert.ok(direkt('AlarmAbKopf'), 'AlarmAbKopf liegt nicht direkt im markierten Element');
		assert.ok(direkt('NichtImBriefing'), 'NichtImBriefing liegt nicht direkt im markierten Element');
		assert.ok(alle(el.fragment, (n) => n.type === 'Component' && n.name === 'MetrikZeile').length > 0, 'keine MetrikZeile im markierten Element');
		const drin = (name: string) => alle(el.fragment, (n) => n.type === 'Component' && n.name === name).length;
		assert.equal(drin('WarnungenRadarKarte'), 0, 'Warnungen/Radar gehört nicht in den Abschnitt metriken');
		assert.equal(drin('AnpassenKarte'), 0, 'Anpassen gehört nicht in den Abschnitt metriken');
	});
});
