// TDD RED — Issue #3122 Scheibe B3a: Molekül Einstell-Tabelle „Was steht wo“.
// Spec: docs/specs/modules/feat_3122_was_steht_wo.md — Teil B Nr. 10/11; AC-22, AC-25, AC-26, AC-28 (Baustein-Anteil).
//
// Vertrag (hier festgelegt):
//   molecules/EinstellTabelle.svelte  Props:
//     metrikTitel: string                         Kopf der Namensspalte („Metrik“)
//     stellen: EinstellStelle[]                   { id, titel, titelKurz?, unterzeile?, abgesetzt?, schmal?, bedienbar?,
//                                                   zellenName: (metrik: string) => string }
//     metriken: EinstellMetrik[]                  { id, name, zellen: Record<stelleId, EinstellZelle> }
//       EinstellZelle                             { zustand: 'on' | 'off' | 'locked' | 'not_in_email', grund?,
//                                                   format?: 'raw' | 'simplified' | null, beispiel?,
//                                                   marke?: { text, ton: 'warn' | 'leise' } }
//     festeZeile?: { name, hinweis?, grund, stellen: string[] }   feste Zeile ohne Abwahl, an erster Stelle
//     onHaken?({ metrik, stelle, an }) · onFormat?({ metrik, stelle, format }) · onReihenfolge?(ids)
//     testid?
//   Markup: Wurzel data-slot="einstell-tabelle" data-stellen="<n>"; Kopf data-slot="et-kopf" mit
//   data-slot="et-kopf-stelle" data-stelle; feste Zeile data-slot="et-fest"; Metrik-Zeile data-slot="et-zeile"
//   data-metrik; Zelle data-slot="et-zelle" data-stelle data-zustand; Beispielwert data-slot="et-beispiel";
//   Marke data-slot="et-marke" data-ton. Sortierung über shared/dnd/SortableList (kein eigener Sortier-Code).
//
// Verhalten per Server-Render (svelte/server). Ereignisse, Ziehen, Tastatur, 390 px und Kontrast:
// frontend/e2e/einstelltabelle-bausteine.spec.ts.
//
//   cd frontend && npm test -- src/lib/components/molecules/__tests__/einstell_tabelle.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { register } from 'node:module';
import { existsSync, readFileSync } from 'node:fs';
import { fileURLToPath, pathToFileURL } from 'node:url';
import path from 'node:path';

const HERE = path.dirname(fileURLToPath(import.meta.url));
// __tests__ -> molecules -> components -> lib -> src -> frontend
const FRONTEND = path.resolve(HERE, '../../../../..');
const MOLECULES = path.resolve(HERE, '..');
const DATEI = path.join(MOLECULES, 'EinstellTabelle.svelte');

register(pathToFileURL(path.join(FRONTEND, 'test-svelte-ssr-hooks.mjs')).href, pathToFileURL(FRONTEND + '/').href);
const { render } = await import('svelte/server');

async function lade(): Promise<any> {
	assert.ok(existsSync(DATEI), 'TDD RED: molecules/EinstellTabelle.svelte fehlt');
	return (await import(pathToFileURL(DATEI).href)).default;
}
const html = (k: any, props: Record<string, unknown>) => render(k, { props }).body.replace(/<!--[\s\S]*?-->/g, '');
const text = (h: string) => h.replace(/<[^>]*>/g, ' ').replace(/\s+/g, ' ').trim();

type Element = { auf: string; innen: string; index: number };
/** Alle Elemente, deren öffnendes Tag `merkmal` enthält (ausbalanciert über den Tag-Namen). */
function elemente(h: string, merkmal: string): Element[] {
	const aus: Element[] = [];
	const auf = /<([a-z][a-z0-9]*)\b[^>]*>/g;
	for (let m = auf.exec(h); m; m = auf.exec(h)) {
		if (!m[0].includes(merkmal)) continue;
		const name = m[1];
		const re = new RegExp(`<${name}\\b[^>]*>|</${name}>`, 'g');
		re.lastIndex = m.index + m[0].length;
		let tiefe = 1;
		for (let t = re.exec(h); t; t = re.exec(h)) {
			if (t[0].startsWith('</')) tiefe--;
			else if (!t[0].endsWith('/>')) tiefe++;
			if (tiefe === 0) {
				aus.push({ auf: m[0], innen: h.slice(m.index + m[0].length, t.index), index: m.index });
				break;
			}
		}
	}
	return aus;
}
const eins = (h: string, merkmal: string): Element => {
	const e = elemente(h, merkmal);
	assert.equal(e.length, 1, `erwartet genau ein Element mit ${merkmal}, gefunden ${e.length}`);
	return e[0];
};
const attr = (auf: string, name: string) => auf.match(new RegExp(`\\s${name}="([^"]*)"`))?.[1] ?? null;
const zeile = (h: string, metrik: string) => eins(h, `data-metrik="${metrik}"`);
const zelle = (h: string, metrik: string, stelle: string) => eins(zeile(h, metrik).innen, `data-stelle="${stelle}"`);

const inS = (stelle: string) => (m: string) => `${m} in ${stelle}`;
const TRIP_STELLEN = [
	{ id: 'email', titel: 'E-Mail', unterzeile: 'Stundentabelle', zellenName: inS('E-Mail') },
	{ id: 'telegram', titel: 'Telegram', unterzeile: 'Nachricht', zellenName: inS('Telegram') },
	{ id: 'sms', titel: 'SMS', unterzeile: 'und Premium-SMS', zellenName: inS('SMS') },
	{ id: 'outlook', titel: '3-Tages-Ausblick', titelKurz: 'Ausbl.', unterzeile: 'E-Mail und Telegram', abgesetzt: true, schmal: true, zellenName: (m: string) => `${m} im 3-Tages-Ausblick` }
];
const ORTE_STELLEN = [
	{ ...TRIP_STELLEN[0], unterzeile: 'Übersicht' },
	{ ...TRIP_STELLEN[1], titelKurz: 'Telegr.' },
	TRIP_STELLEN[2],
	{ id: 'hourly', titel: 'Stundenverlauf', titelKurz: 'Std.', unterzeile: 'nur E-Mail', abgesetzt: true, schmal: true, zellenName: (m: string) => `${m} im Stundenverlauf` },
	TRIP_STELLEN[3]
];
const an = (extra: Record<string, unknown> = {}) => ({ zustand: 'on', ...extra });
const METRIKEN = [
	{
		id: 'temperature',
		name: 'Temperatur',
		zellen: { email: an({ beispiel: '13°C / 4°C' }), telegram: an({ beispiel: 'Temp max 13°C' }), sms: an({ beispiel: 'D 13C L 4C' }), hourly: an(), outlook: an() }
	},
	{
		id: 'wind',
		name: 'Wind',
		zellen: {
			email: an({ format: 'raw', beispiel: '30 km/h' }),
			telegram: { zustand: 'off', format: 'raw', beispiel: 'Wind 30 km/h' },
			sms: an({ beispiel: 'W 30 km/h', marke: { text: 'passt nicht mehr', ton: 'warn' } }),
			hourly: an({ format: 'simplified' }),
			outlook: an({ format: 'raw' })
		}
	},
	{
		id: 'sunshine',
		name: 'Sonnenstunden',
		zellen: {
			email: { zustand: 'off', format: 'simplified' },
			telegram: an({ format: 'simplified', beispiel: 'Sonne 3.0h', marke: { text: 'nur Tageswert', ton: 'leise' } }),
			sms: an({ beispiel: 'SU 3.0h' }),
			hourly: { zustand: 'locked', grund: 'kein Stundenwert' },
			outlook: { zustand: 'not_in_email', grund: 'nicht in der E-Mail' }
		}
	}
];
const FEST = { name: 'Amtliche Warnungen', hinweis: 'immer dabei: in E-Mail und Telegram zuerst, in der SMS am Ende', grund: 'immer dabei', stellen: ['email', 'telegram', 'sms'] };
const props = (extra: Record<string, unknown> = {}) => ({ metrikTitel: 'Metrik', stellen: ORTE_STELLEN, metriken: METRIKEN, festeZeile: FEST, testid: 'et', ...extra });

describe('Spalten kommen als Props: vier (Trip) und fünf (Orte)', () => {
	for (const [name, stellen] of [['Trip', TRIP_STELLEN], ['Orte', ORTE_STELLEN]] as const) {
		test(`${name}: ${stellen.length} Spaltenköpfe mit Titel und Unterzeile in Prop-Reihenfolge`, async () => {
			const h = html(await lade(), props({ stellen }));
			const wurzel = eins(h, 'data-slot="einstell-tabelle"');
			assert.equal(attr(wurzel.auf, 'data-stellen'), String(stellen.length));
			assert.equal(attr(wurzel.auf, 'data-testid'), 'et');
			const kopf = eins(h, 'data-slot="et-kopf"');
			assert.ok(text(kopf.innen).startsWith('Metrik'), 'Kopf der Namensspalte fehlt');
			const koepfe = elemente(kopf.innen, 'data-slot="et-kopf-stelle"');
			assert.deepEqual(koepfe.map((k) => attr(k.auf, 'data-stelle')), stellen.map((s) => s.id));
			koepfe.forEach((k, i) => {
				assert.ok(text(k.innen).includes(stellen[i].titel), `Titel ${stellen[i].titel} fehlt`);
				assert.ok(text(k.innen).includes(stellen[i].unterzeile!), `Unterzeile ${stellen[i].unterzeile} fehlt`);
			});
			for (const m of METRIKEN) {
				const zellen = elemente(zeile(h, m.id).innen, 'data-slot="et-zelle"');
				assert.deepEqual(zellen.map((z) => attr(z.auf, 'data-stelle')), stellen.map((s) => s.id), `Zeile ${m.id}: eine Zelle je Stelle`);
			}
		});
	}
	test('Kurztitel fürs Handy steht zusätzlich im Kopf, wenn gesetzt', async () => {
		const kopf = eins(html(await lade(), props()), 'data-slot="et-kopf"');
		assert.ok(text(eins(kopf.innen, 'data-stelle="hourly"').innen).includes('Std.'));
		assert.ok(text(eins(kopf.innen, 'data-stelle="telegram"').innen).includes('Telegr.'));
	});
});

describe('Feste Zeile: an erster Stelle, ohne Griff, ohne Abwahl', () => {
	test('steht vor der ersten Metrik-Zeile, zeigt Name und Hinweis', async () => {
		const h = html(await lade(), props());
		const fest = eins(h, 'data-slot="et-fest"');
		assert.ok(fest.index < zeile(h, METRIKEN[0].id).index, 'feste Zeile steht nicht vor den Metriken');
		assert.ok(text(fest.innen).includes('Amtliche Warnungen'));
		assert.ok(text(fest.innen).includes(FEST.hinweis));
	});
	test('kein Griff, kein Kontrollkästchen; fester Haken genau in den genannten Stellen', async () => {
		const fest = eins(html(await lade(), props()), 'data-slot="et-fest"');
		assert.doesNotMatch(fest.innen, /data-testid="drag-handle"/);
		assert.doesNotMatch(fest.innen, /<input\b/);
		const feste = elemente(fest.innen, 'data-zustand="fest"');
		assert.deepEqual(feste.map((f) => attr(f.auf, 'aria-label')), ['Amtliche Warnungen in E-Mail: immer dabei', 'Amtliche Warnungen in Telegram: immer dabei', 'Amtliche Warnungen in SMS: immer dabei']);
		assert.equal(elemente(fest.innen, 'data-slot="et-zelle"').length, ORTE_STELLEN.length, 'auch leere Zellen halten die Spalte');
	});
	test('ohne festeZeile gibt es die Zeile nicht', async () => {
		assert.doesNotMatch(html(await lade(), props({ festeZeile: undefined })), /data-slot="et-fest"/);
	});
});

describe('Metrik-Zeilen: Griff, Name, je Stelle eine Zelle', () => {
	test('Reihenfolge wie die Prop, jede Zeile mit Griff, dessen Name die Metrik nennt', async () => {
		const h = html(await lade(), props());
		const zeilen = elemente(h, 'data-slot="et-zeile"');
		assert.deepEqual(zeilen.map((z) => attr(z.auf, 'data-metrik')), METRIKEN.map((m) => m.id));
		zeilen.forEach((z, i) => {
			const griff = eins(z.innen, 'data-testid="drag-handle"');
			assert.ok(attr(griff.auf, 'aria-label')?.includes(METRIKEN[i].name), `Griff ${METRIKEN[i].id} ohne Metrik-Namen`);
			assert.ok(text(z.innen).includes(METRIKEN[i].name));
		});
	});
	test('Haken: Name aus zellenName, Zustand an/aus', async () => {
		const h = html(await lade(), props());
		const mail = zelle(h, 'wind', 'email');
		assert.equal(attr(mail.auf, 'data-zustand'), 'on');
		assert.match(mail.innen, /<input\b[^>]*aria-label="Wind in E-Mail"[^>]*>/);
		assert.match(mail.innen.match(/<input\b[^>]*>/)![0], /\schecked\b/);
		const tg = zelle(h, 'wind', 'telegram');
		assert.equal(attr(tg.auf, 'data-zustand'), 'off');
		assert.doesNotMatch(tg.innen.match(/<input\b[^>]*>/)![0], /\schecked\b/);
		assert.match(zelle(h, 'wind', 'outlook').innen, /aria-label="Wind im 3-Tages-Ausblick"/);
	});
	test('Beispielwert nur bei gesetztem Haken', async () => {
		const h = html(await lade(), props());
		assert.equal(text(eins(zelle(h, 'wind', 'email').innen, 'data-slot="et-beispiel"').innen), '30 km/h');
		assert.doesNotMatch(zelle(h, 'wind', 'telegram').innen, /Wind 30 km\/h/);
	});
	test('Roh/Einfach-Knopf nur bei gesetztem Haken und zwei Formen', async () => {
		const h = html(await lade(), props());
		assert.match(zelle(h, 'wind', 'email').innen, /<button\b[^>]*aria-label="Darstellung Wind in E-Mail: Roh"/);
		assert.match(zelle(h, 'wind', 'hourly').innen, /<button\b[^>]*aria-label="Darstellung Wind im Stundenverlauf: Einfach"/);
		assert.doesNotMatch(zelle(h, 'wind', 'telegram').innen, /<button\b/, 'Haken aus ⇒ kein Knopf');
		assert.doesNotMatch(zelle(h, 'wind', 'sms').innen, /<button\b/, 'nur eine Form ⇒ kein Knopf');
		assert.doesNotMatch(zelle(h, 'temperature', 'email').innen, /<button\b/);
		assert.doesNotMatch(zelle(h, 'sunshine', 'email').innen, /<button\b/, 'Haken aus ⇒ kein Knopf');
	});
	test('Marken erscheinen in ihrer Zelle mit Ton', async () => {
		const h = html(await lade(), props());
		const warn = eins(zelle(h, 'wind', 'sms').innen, 'data-slot="et-marke"');
		assert.equal(text(warn.innen), 'passt nicht mehr');
		assert.equal(attr(warn.auf, 'data-ton'), 'warn');
		const leise = eins(zelle(h, 'sunshine', 'telegram').innen, 'data-slot="et-marke"');
		assert.equal(text(leise.innen), 'nur Tageswert');
		assert.equal(attr(leise.auf, 'data-ton'), 'leise');
		assert.doesNotMatch(zelle(h, 'wind', 'email').innen, /data-slot="et-marke"/);
	});
	test('gesperrt und nicht in der E-Mail: Strich mit Grund statt Kontrollkästchen', async () => {
		const h = html(await lade(), props());
		const gesperrt = zelle(h, 'sunshine', 'hourly');
		assert.equal(attr(gesperrt.auf, 'data-zustand'), 'locked');
		assert.doesNotMatch(gesperrt.innen, /<input\b|<button\b/);
		assert.match(gesperrt.innen, /role="img"[^>]*aria-label="Sonnenstunden im Stundenverlauf: kein Stundenwert"|aria-label="Sonnenstunden im Stundenverlauf: kein Stundenwert"[^>]*role="img"/);
		assert.ok(text(gesperrt.innen).includes('kein Stundenwert'));
		const ohneMail = zelle(h, 'sunshine', 'outlook');
		assert.equal(attr(ohneMail.auf, 'data-zustand'), 'not_in_email');
		assert.doesNotMatch(ohneMail.innen, /<input\b|<button\b/);
		assert.match(ohneMail.innen, /aria-label="Sonnenstunden im 3-Tages-Ausblick: nicht in der E-Mail"/);
	});
});

describe('Nicht bedienbare Spalte (Block aus, Telegram-Kurzstil)', () => {
	test('alle Haken der Spalte gesperrt für Eingaben, kein Knopf, kein Beispielwert, keine Marke; andere Spalten unberührt', async () => {
		const stellen = ORTE_STELLEN.map((s) => (s.id === 'telegram' ? { ...s, bedienbar: false, unterzeile: 'Kurzstil: wie SMS' } : s));
		const h = html(await lade(), props({ stellen }));
		assert.ok(text(eins(eins(h, 'data-slot="et-kopf"').innen, 'data-stelle="telegram"').innen).includes('Kurzstil: wie SMS'));
		for (const m of METRIKEN) {
			const z = zelle(h, m.id, 'telegram');
			assert.equal(attr(z.auf, 'data-bedienbar'), 'false');
			assert.match(z.innen.match(/<input\b[^>]*>/)![0], /\sdisabled\b/, `${m.id}: Haken nicht gesperrt`);
			assert.doesNotMatch(z.innen, /<button\b/);
			assert.doesNotMatch(z.innen, /data-slot="et-beispiel"|data-slot="et-marke"/);
		}
		assert.match(zelle(h, 'sunshine', 'telegram').innen.match(/<input\b[^>]*>/)![0], /\schecked\b/, 'der Haken-Zustand bleibt sichtbar');
		assert.doesNotMatch(zelle(h, 'wind', 'email').innen.match(/<input\b[^>]*>/)![0], /\sdisabled\b/);
		assert.match(zelle(h, 'wind', 'email').innen, /<button\b/);
	});
});

describe('Aufbau: Sortierung über SortableList, kein eigener Sortier-Code', () => {
	test('die Metrik-Zeilen liegen als Einträge in der Zone des geteilten Sortier-Bausteins, die feste Zeile nicht', async () => {
		const h = html(await lade(), props());
		const zone = eins(h, 'class="sortable-zone');
		assert.ok(attr(zone.auf, 'aria-label'), 'Zone ohne Beschriftung');
		const eintraege = elemente(zone.innen, 'class="sortable-item');
		assert.equal(eintraege.length, METRIKEN.length);
		eintraege.forEach((e, i) => {
			assert.equal(attr(eins(e.innen, 'data-slot="et-zeile"').auf, 'data-metrik'), METRIKEN[i].id);
			assert.ok(attr(e.auf, 'aria-label')?.includes(METRIKEN[i].name), 'Eintrag ohne Metrik-Namen für die Ansage');
		});
		assert.doesNotMatch(zone.innen, /data-slot="et-fest"/);
	});
	test('im Barrel molecules/index.ts', () => {
		const barrel = readFileSync(path.join(MOLECULES, 'index.ts'), 'utf8').replace(/\/\/.*$/gm, '');
		assert.match(barrel, /export\s*\{\s*default\s+as\s+EinstellTabelle\s*\}\s*from\s*['"]\.\/EinstellTabelle\.svelte['"]/);
	});
});

// Issue #3122 B3b: Ampelpunkt der HTML-Mail in der Zelle (Antwort-Feld `ampel`), Farbe als Wort für Screenreader.
describe('B3b: Ampelpunkt', () => {
	test('nur bei gesetztem Haken und bedienbarer Spalte, mit Farbe und Namen', async () => {
		const mit = (zustand: string) => [
			{ id: 'gust', name: 'Böen', zellen: { email: { zustand, format: 'simplified', ampel: { farbe: 'yellow', name: 'gelb' } } } }
		];
		const h = html(await lade(), props({ stellen: [TRIP_STELLEN[0]], metriken: mit('on') }));
		const punkt = eins(zelle(h, 'gust', 'email').innen, 'data-slot="et-ampel"');
		assert.equal(attr(punkt.auf, 'data-farbe'), 'yellow');
		assert.equal(attr(punkt.auf, 'aria-label'), 'gelb');
		const aus = html(await lade(), props({ stellen: [TRIP_STELLEN[0]], metriken: mit('off') }));
		assert.equal(elemente(zelle(aus, 'gust', 'email').innen, 'data-slot="et-ampel"').length, 0);
		const ruht = html(await lade(), props({ stellen: [{ ...TRIP_STELLEN[0], bedienbar: false }], metriken: mit('on') }));
		assert.equal(elemente(zelle(ruht, 'gust', 'email').innen, 'data-slot="et-ampel"').length, 0);
	});
});

// Issue #3283 B2/B1 (Spec docs/specs/modules/fix_3283_was_steht_wo_optik.md, AC-1/AC-2): schmale Zusatzspalten
// (Stundenverlauf, Ausblick) zeigen nur Haken und Roh/Einfach, keinen Beispielwert; Raster 150 px/118 px aus Tokens.
describe('#3283: schmale Zusatzspalten ohne Beispielwert, Raster nach Soll-Bild', () => {
	const MIT_ZUSATZ = [
		{
			id: 'gust',
			name: 'Böen',
			zellen: {
				email: an({ format: 'raw', beispiel: 'Gust 38' }),
				telegram: an({ format: 'raw', beispiel: 'G 26-59@15' }),
				sms: an({ beispiel: 'G32@6(59@15)' }),
				hourly: an({ format: 'raw', beispiel: '28' }),
				outlook: an({ format: 'raw', beispiel: '85 km/h' })
			}
		}
	];
	test('Stundenverlauf und Ausblick (schmal): kein et-beispiel, Knopf bleibt; Kanalspalten zeigen ihn', async () => {
		const h = html(await lade(), props({ metriken: MIT_ZUSATZ }));
		for (const stelle of ['hourly', 'outlook']) {
			assert.equal(elemente(zelle(h, 'gust', stelle).innen, 'data-slot="et-beispiel"').length, 0, `${stelle}: Beispielwert in schmaler Spalte`);
			assert.match(zelle(h, 'gust', stelle).innen, /<button\b/, `${stelle}: Roh/Einfach fehlt`);
		}
		for (const [stelle, wert] of [['email', 'Gust 38'], ['telegram', 'G 26-59@15'], ['sms', 'G32@6(59@15)']])
			assert.equal(text(eins(zelle(h, 'gust', stelle).innen, 'data-slot="et-beispiel"').innen), wert);
	});
	test('Raster: Kanalspalten minmax(150px, 1fr), schmale Spalten 118px, nur über Tokens', async () => {
		const h = html(await lade(), props());
		const stil = attr(eins(h, 'data-slot="et-kopf"').auf, 'style') ?? '';
		const spalten = stil.replace(/^.*grid-template-columns:\s*/, '').replace(/;.*$/, '').trim();
		const kanal = 'minmax(var(--g-size-150px), 1fr)';
		assert.equal(spalten, ['var(--g-size-22px)', 'minmax(var(--g-size-130px), 0.9fr)', kanal, kanal, kanal, 'var(--g-size-118px)', 'var(--g-size-118px)'].join(' '));
	});
});
