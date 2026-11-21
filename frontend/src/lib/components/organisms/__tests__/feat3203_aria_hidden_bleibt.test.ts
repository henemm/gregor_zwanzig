// Issue #3203 (Epic #2913), Spec docs/specs/modules/feat_3203_metrikzeilen_mockup.md, AC-6:
// Der Abgleich wird korrigiert, NICHT das Produkt. Skala-Marken, Gewitter-Stufen und der Trennpunkt „·“
// bleiben für Screenreader verborgen (aria-hidden="true"); die Segmente sprechen ihren Farbnamen (role=img).
// Wächter gegen eine Umsetzung, die stattdessen aria-hidden aus dem Produkt entfernt (grün vor und nach #3203).
//
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types --experimental-test-module-mocks --test src/lib/components/organisms/__tests__/feat3203_aria_hidden_bleibt.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { register } from 'node:module';
import { fileURLToPath, pathToFileURL } from 'node:url';
import path from 'node:path';
import { live, ampelModell } from '../../shared/wetter-tab/__tests__/wetterTabDaten.ts';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const FRONTEND = path.resolve(HERE, '../../../../..');
const WT = path.resolve(HERE, '..', 'wetter-tab');

register(pathToFileURL(path.join(FRONTEND, 'test-svelte-ssr-hooks.mjs')).href, pathToFileURL(FRONTEND + '/').href);
const { render } = await import('svelte/server');

const html = (k: any, props: Record<string, unknown>) => render(k, { props }).body.replace(/<!--[\s\S]*?-->/g, '');
const ladeSvelte = async (datei: string): Promise<any> => (await import(pathToFileURL(datei).href)).default;
const noop = () => {};

const M = await ampelModell();
const EIG: Record<string, any> = M.eigenschaftenAusKatalog(live().metrics);
const TEMP = { enabled: true, alarm_ab: 'orange', lower: { red: -10, orange: -3, yellow: 2 }, upper: { yellow: 27, orange: 30, red: 33 } };

const zeileProps = (id: string, eintrag: Record<string, unknown>) => ({
	id,
	name: id,
	eig: EIG[id],
	eintrag,
	thunder: undefined,
	offen: false,
	abweichend: false,
	vorlageLabel: 'Standard',
	fehler: [],
	onEntfernen: noop,
	onAlarmAb: noop,
	onGrenzen: noop,
	onWert: noop,
	onGewitter: noop
});

describe('#3203 AC-6: aria-hidden im Produkt bleibt (Screenreader-Ausgabe unverändert)', () => {
	test('AmpelLeiste: Skala-Marken (wt-marken) tragen aria-hidden="true" und enthalten die Zahlen', async () => {
		const A = await ladeSvelte(path.join(WT, 'AmpelLeiste.svelte'));
		const h = html(A, { id: 'temperature', eintrag: TEMP, gewitter: null });
		const marken = h.match(/<div class="wt-marken[^"]*"[^>]*>/);
		assert.ok(marken, `wt-marken fehlt: ${h}`);
		assert.match(marken![0], /\saria-hidden="true"/, 'Skala-Marken sind für Screenreader nicht mehr verborgen');
		assert.match(h, /<i\b[^>]*>-10<\/i>/, 'Skala-Zahl -10 fehlt in den Marken');
	});

	test('AmpelLeiste Gewitter: Stufen-Container trägt aria-hidden="true"', async () => {
		const A = await ladeSvelte(path.join(WT, 'AmpelLeiste.svelte'));
		const h = html(A, { id: 'thunder', eintrag: undefined, gewitter: { mittel: 'yellow', hoch: 'orange' } });
		const stufen = h.match(/<div class="wt-marken wt-marken--stufen[^"]*"[^>]*>/);
		assert.ok(stufen, 'Stufen-Container fehlt');
		assert.match(stufen![0], /\saria-hidden="true"/, 'Gewitter-Stufen sind für Screenreader nicht mehr verborgen');
	});

	test('AmpelLeiste: Segmente sprechen ihren Farbnamen (role="img" mit aria-label)', async () => {
		const A = await ladeSvelte(path.join(WT, 'AmpelLeiste.svelte'));
		const h = html(A, { id: 'temperature', eintrag: TEMP, gewitter: null });
		assert.match(h, /<span\b[^>]*role="img"[^>]*aria-label="[^"]+"/, 'Segment ohne role=img/aria-label');
	});

	test('MetrikZeile: Trennpunkt „·“ in der grün-Span trägt aria-hidden="true"', async () => {
		const Z = await ladeSvelte(path.join(WT, 'MetrikZeile.svelte'));
		const h = html(Z, zeileProps('temperature', TEMP));
		assert.match(h, /data-testid="wetter-gruen-temperature"[^>]*>\s*<span\b[^>]*aria-hidden="true"[^>]*>·<\/span>/, 'Trennpunkt ist für Screenreader nicht mehr verborgen');
	});
});
