// Issue #3204 (Epic #2913), Spec docs/specs/modules/feat_3204_anzeige_metriken_mockup.md, AC-3:
// Der Erklärsatz einer Nur-Anzeige-Zeile (Tages-Tief/-Hoch Gehzeit, Windrichtung …) verweist auf den Abschnitt
// „Was steht wo“ statt „je Liste“, wortgleich zum Mockup Fassung 4 (why() für Nur-Anzeige-Zeilen).
// Geprüft wird, was die echte MetrikZeile im Server-Render zeigt (Eigenschaften aus /api/metrics des
// Python-Core), in Deutsch und Englisch.
//
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types --experimental-test-module-mocks --test src/lib/components/organisms/__tests__/feat3204_erklaersatz_anzeige.test.ts

import { test, describe, after } from 'node:test';
import assert from 'node:assert/strict';
import { register } from 'node:module';
import { readFileSync } from 'node:fs';
import { fileURLToPath, pathToFileURL } from 'node:url';
import path from 'node:path';
import { live, ampelModell } from '../../shared/wetter-tab/__tests__/wetterTabDaten.ts';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const FRONTEND = path.resolve(HERE, '../../../../..');
const WT = path.resolve(HERE, '..', 'wetter-tab');
const MSG = path.join(FRONTEND, 'src/lib/i18n/messages');

register(pathToFileURL(path.join(FRONTEND, 'test-svelte-ssr-hooks.mjs')).href, pathToFileURL(FRONTEND + '/').href);
const { render } = await import('svelte/server');
const { locale } = await import(pathToFileURL(path.join(FRONTEND, 'src/lib/i18n/index.ts')).href);
after(() => locale.set('de'));

const WETTER = {
	de: JSON.parse(readFileSync(path.join(MSG, 'de/wetter.json'), 'utf-8')) as Record<string, string>,
	en: JSON.parse(readFileSync(path.join(MSG, 'en/wetter.json'), 'utf-8')) as Record<string, string>
};
/** Mockup-Wortlaut (mockup-hub-fassung4.html, why() bei Nur-Anzeige). */
const MOCKUP_DE = 'Nur Anzeige: keine Ampel und kein Alarm. Roh oder Einfach stellst du unten unter „Was steht wo“ ein.';

const M = await ampelModell();
const EIG: Record<string, any> = M.eigenschaftenAusKatalog(live().metrics);
const noop = () => {};
const ladeSvelte = async (datei: string): Promise<any> => (await import(pathToFileURL(datei).href)).default;

const zeileProps = (id: string) => ({
	id,
	name: id,
	eig: EIG[id],
	eintrag: { enabled: true },
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

async function erklaersatz(id: string, sprache: 'de' | 'en'): Promise<string> {
	locale.set(sprache);
	const Z = await ladeSvelte(path.join(WT, 'MetrikZeile.svelte'));
	const h = render(Z, { props: zeileProps(id) }).body.replace(/<!--[\s\S]*?-->/g, '');
	const m = h.match(new RegExp(`data-testid="wetter-erklaersatz-${id}"[^>]*>([^<]*)<`));
	assert.ok(m, `Erklärsatz von ${id} fehlt im Render: ${h}`);
	return m![1].replace(/&amp;/g, '&').replace(/\s+/g, ' ').trim();
}

describe('#3204 AC-3: Erklärsatz der Nur-Anzeige-Zeilen verweist auf „Was steht wo“ (Mockup-Wortlaut)', () => {
	for (const id of ['temperature_day_low', 'temperature_day_high', 'wind_direction']) {
		test(`${id}: ist Nur-Anzeige (Vorbedingung aus dem Metrik-Register)`, () => {
			assert.equal(EIG[id]?.display_only, true, `${id} ist nicht display_only`);
		});

		test(`${id} DE: wortgleich zum Mockup`, async () => {
			assert.equal(await erklaersatz(id, 'de'), MOCKUP_DE);
		});

		test(`${id} EN: nennt den englischen Abschnittsnamen „${WETTER.en['wetter.wsw.titel']}“ statt „for each list“`, async () => {
			const satz = await erklaersatz(id, 'en');
			assert.ok(satz.includes(WETTER.en['wetter.wsw.titel']), `EN-Erklärsatz ohne Abschnittsnamen: ${satz}`);
			assert.ok(!/for each list/i.test(satz), `EN-Erklärsatz sagt noch „for each list“: ${satz}`);
			assert.ok(satz.startsWith('Display only: no traffic light and no alert.'), `EN-Anfang verändert: ${satz}`);
		});
	}

	test('DE-Katalog nennt den Abschnitt mit seinem Titel wetter.wsw.titel', () => {
		assert.ok(WETTER.de['wetter.erklaer.anzeige'].includes(`„${WETTER.de['wetter.wsw.titel']}“`));
		assert.ok(!WETTER.de['wetter.erklaer.anzeige'].includes('je Liste'));
	});
});
