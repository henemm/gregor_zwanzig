// Issue #2966 (Epic #2913): Haken für Script-Zustände, Abschnittskopf, Laden und Warnung im Reiter Wetter.
// Spec: docs/specs/modules/feat_2966_abgleich_haken.md (AC-1 bis AC-5).
// Ergänzt wetter_tab_abschnitt_marker.test.ts. Geprüft im Server-Render der ECHTEN Dateien. Zustände,
// die erst nach Laden oder Klick entstehen (Fehler-Phase, offenes Vorlage-Menü, Wechsel-Frage,
// Speichern-Fehler), rendert startzustandHook.mjs mit anderem `$state`-Startwert; das Markup bleibt
// das der Produktivdatei.
//
//   cd frontend && npm test -- src/lib/components/organisms/__tests__/wetter_tab_abschnitt_marker_2966.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { register } from 'node:module';
import { readFileSync } from 'node:fs';
import { fileURLToPath, pathToFileURL } from 'node:url';
import path from 'node:path';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const FRONTEND = path.resolve(HERE, '../../../../..');
const WT = path.resolve(HERE, '..', 'wetter-tab');
const SPD = path.resolve(HERE, '../../shared/weather-metrics-tab/SavePresetDialog.svelte');

register(pathToFileURL(path.join(FRONTEND, 'test-svelte-ssr-hooks.mjs')).href, pathToFileURL(FRONTEND + '/').href);
register(pathToFileURL(path.join(HERE, 'startzustandHook.mjs')).href, pathToFileURL(FRONTEND + '/').href);
const { render } = await import('svelte/server');
const { locale } = await import(pathToFileURL(path.join(FRONTEND, 'src/lib/i18n/index.ts')).href);

const KATALOG = (sprache: 'de' | 'en'): Record<string, string> =>
	JSON.parse(readFileSync(path.join(FRONTEND, 'src/lib/i18n/messages', sprache, 'wetter.json'), 'utf8'));
const DE = KATALOG('de');

const datei = (n: string) => path.join(WT, `${n}.svelte`);
async function lade(file: string, start: [string, string][] = []): Promise<any> {
	const abfrage = start.length ? `?start=${encodeURIComponent(JSON.stringify(start))}` : '';
	return (await import(pathToFileURL(file).href + abfrage)).default;
}
const html = (k: any, props: Record<string, unknown>) => render(k, { props }).body.replace(/<!--[\s\S]*?-->/g, '').trim();
const noop = () => {};
const ersterTag = (h: string) => h.match(/^<[a-z]+\b[^>]*>/)?.[0] ?? '';
const markerZahl = (h: string) => (h.match(/\sdata-abschnitt="/g) ?? []).length;
const textVon = (h: string) =>
	h
		.replace(/<[^>]*>/g, ' ')
		.replace(/&nbsp;/g, ' ')
		.replace(/&amp;/g, '&')
		.replace(/\s+/g, ' ')
		.trim();

/** Element (samt Inhalt) ab dem ersten öffnenden Tag, der auf `re` passt, bis zum passenden Schluss-Tag. */
function elementAb(h: string, re: RegExp): string | null {
	const m = h.match(re);
	if (!m || m.index === undefined) return null;
	const name = m[0].match(/^<([a-z0-9]+)/)![1];
	if (/\/>$/.test(m[0])) return m[0];
	const zaehler = new RegExp(`<${name}\\b[^>]*?(/?)>|</${name}>`, 'g');
	zaehler.lastIndex = m.index + m[0].length;
	let tiefe = 1;
	for (let x = zaehler.exec(h); x; x = zaehler.exec(h)) {
		if (x[0].startsWith('</')) tiefe -= 1;
		else if (x[1] !== '/') tiefe += 1;
		if (tiefe === 0) return h.slice(m.index, x.index + x[0].length);
	}
	return null;
}
const bereich = (h: string, abschnitt: string) => elementAb(h, new RegExp(`<[a-z0-9]+\\b[^>]*\\sdata-abschnitt="${abschnitt}"[^>]*>`));

/** Markup ohne Teilbäume mit aria-hidden="true" (das, was Hilfstechnik wahrnimmt). */
function ohneAriaHidden(h: string): string {
	let rest = h;
	for (;;) {
		const el = elementAb(rest, /<[a-z0-9]+\b[^>]*\saria-hidden="true"[^>]*>/);
		if (!el) return rest;
		rest = rest.replace(el, '');
	}
}
/** Wie oft Hilfstechnik den Satz vorliest: sichtbarer Text plus aria-label, ohne aria-hidden-Teilbäume. */
function vorlesungen(h: string, satz: string): number {
	const sichtbar = ohneAriaHidden(h);
	const labels = [...sichtbar.matchAll(/\saria-label="([^"]*)"/g)].filter((m) => m[1] === satz).length;
	return textVon(sichtbar).split(satz).length - 1 + labels;
}

const START_LAEDT = "$state<'laedt' | 'fehler' | 'bereit'>('laedt')";
const inhaltProps = { context: 'route', trip: { id: 't1', name: 'Trip', stages: [] } };

describe('#2966 AC-1: Abschnittskopf trägt den Haken', () => {
	test('WetterTabInhalt: data-abschnitt="abschnittskopf" umschließt Titel und Erklärsatz', async () => {
		locale.set('de');
		const h = html(await lade(datei('WetterTabInhalt')), inhaltProps);
		const kopf = bereich(h, 'abschnittskopf');
		assert.ok(kopf, 'kein Element mit data-abschnitt="abschnittskopf"');
		assert.match(kopf!, /data-testid="wetter-tab-titel"/);
		assert.match(kopf!, /data-testid="wetter-tab-erklaer"/);
		assert.equal(textVon(kopf!), `${DE['wetter.kopf.titel']} ${DE['wetter.kopf.erklaerung']}`);
		assert.doesNotMatch(kopf!, /data-testid="wetter-tab-laden"/, 'Kopf darf die Lade-Karte nicht umschließen');
	});
});

describe('#2966 AC-2: Laden-Text sichtbar und genau einmal vorgelesen', () => {
	test('Bereich „laden“: Text ohne aria-hidden in role="status", Skelett im aria-hidden-Wrapper', async () => {
		locale.set('de');
		const h = html(await lade(datei('WetterTabInhalt')), inhaltProps);
		const laden = bereich(h, 'laden');
		assert.ok(laden, 'Bereich laden fehlt im SSR-Startzustand');
		assert.match(laden!, /data-testid="wetter-tab-laden"/, 'testid wetter-tab-laden bleibt');
		const satz = DE['wetter.kopf.laden'];
		assert.ok(textVon(ohneAriaHidden(laden!)).includes(satz), `„${satz}“ ist nicht sichtbar (liegt in aria-hidden)`);
		const status = elementAb(ohneAriaHidden(laden!), /<[a-z0-9]+\b[^>]*\srole="status"[^>]*>/);
		assert.ok(status, 'kein wahrnehmbares role="status" im Bereich laden');
		assert.ok(textVon(status!).includes(satz), 'der role="status"-Bereich trägt den Laden-Text nicht als Text');
		assert.ok(elementAb(laden!, /<div\b[^>]*\sdata-slot="skelett"[^>]*>/), 'Skelett fehlt');
		assert.ok(!ohneAriaHidden(laden!).includes('data-slot="skelett"'), 'Skelett liegt nicht in einem aria-hidden-Wrapper');
		assert.equal(vorlesungen(laden!, satz), 1, 'Laden-Text wird nicht genau einmal vorgelesen');
	});
});

describe('#2966 AC-3: Warnung aus zwei Absätzen, DE-Wortlaut unverändert, EN gleich gebaut', () => {
	for (const sprache of ['de', 'en'] as const) {
		test(`Fehler-Phase (${sprache}): zwei <p> im Bereich warnung, Satz 1 | Sätze 2 und 3`, async () => {
			locale.set(sprache);
			try {
				const K = KATALOG(sprache);
				const W = await lade(datei('WetterTabInhalt'), [[START_LAEDT, START_LAEDT.replace("('laedt')", "('fehler')")]]);
				const warnung = bereich(html(W, inhaltProps), 'warnung');
				assert.ok(warnung, 'Bereich warnung fehlt in der Fehler-Phase');
				const absaetze = [...warnung!.matchAll(/<p\b[^>]*>([\s\S]*?)<\/p>/g)].map((m) => textVon(m[1]));
				assert.equal(absaetze.length, 2, `erwartet zwei Absätze, gefunden ${absaetze.length}: ${JSON.stringify(absaetze)}`);
				assert.ok(K['wetter.kopf.fehler_verbindung'], `Katalogschlüssel wetter.kopf.fehler_verbindung fehlt (${sprache})`);
				assert.equal(absaetze[0], K['wetter.kopf.fehler']);
				assert.equal(absaetze[1], K['wetter.kopf.fehler_verbindung']);
				if (sprache === 'de') {
					assert.equal(absaetze[0], 'Die Metriken konnten nicht geladen werden.');
					assert.equal(absaetze[1], 'Die Verbindung zum Server ist abgebrochen. Deine Einstellungen sind gespeichert und gehen nicht verloren.');
				} else {
					assert.notEqual(absaetze[1], 'Die Verbindung zum Server ist abgebrochen. Deine Einstellungen sind gespeichert und gehen nicht verloren.');
				}
				assert.match(warnung!, /data-testid="wetter-tab-erneut-laden"/, 'Erneut laden bleibt im Bereich warnung');
			} finally {
				locale.set('de');
			}
		});
	}
});

const EIG = { id: 'wind', group: 'wind', alertable: true, is_precursor: false, allowed_sides: 'upper', display_only: false, unit: 'km/h' };
const zeileProps = (offen: boolean) => ({
	id: 'wind',
	name: 'Wind',
	eig: EIG,
	eintrag: { alarm_ab: 'orange', upper: { yellow: 30, orange: 50, red: 70 } },
	thunder: undefined,
	offen,
	abweichend: false,
	vorlageLabel: 'Standard',
	fehler: [],
	onEntfernen: noop,
	onAlarmAb: noop,
	onGrenzen: noop,
	onWert: noop,
	onGewitter: noop
});

describe('#2966 AC-4: Grenzen-Haken nur an der geöffneten Metrikzeile', () => {
	test('MetrikZeile offen: Wurzel trägt data-abschnitt="grenzen-wind" und umschließt „Fertig“ und den Editor', async () => {
		locale.set('de');
		const h = html(await lade(datei('MetrikZeile')), zeileProps(true));
		assert.match(ersterTag(h), /\sdata-abschnitt="grenzen-wind"/, 'Haken fehlt an der Wurzel der offenen Zeile');
		assert.match(ersterTag(h), /data-testid="wetter-zeile-wind"/, 'Haken steht nicht an der Zeilen-Wurzel');
		assert.equal(markerZahl(h), 1, 'genau ein Abschnitts-Marker');
		const g = bereich(h, 'grenzen-wind')!;
		const knopf = elementAb(g, /<button\b[^>]*data-testid="wetter-grenzen-aendern-wind"[^>]*>/);
		assert.ok(knopf, 'Knopf „Fertig“ liegt nicht im Bereich');
		assert.equal(textVon(knopf!), DE['wetter.grenzen.fertig']);
		assert.match(g, /data-testid="wetter-grenze-wind-upper-/, 'Grenzen-Felder liegen nicht im Bereich');
	});
	test('MetrikZeile zu: kein Abschnitts-Haken', async () => {
		const h = html(await lade(datei('MetrikZeile')), zeileProps(false));
		assert.equal(markerZahl(h), 0, 'geschlossene Zeile darf keinen Haken tragen');
		assert.match(h, /data-testid="wetter-grenzen-aendern-wind"/, 'testid wetter-grenzen-aendern-wind bleibt');
	});
});

const LISTE = [
	{ id: 'standard', label: 'Standard', anzahl: 3, stichworte: ['wind'] },
	{ id: 'alpin', label: 'Alpin', anzahl: 2, stichworte: [] }
];
const vorlageProps = {
	context: 'route',
	vorlageId: 'standard',
	liste: LISTE,
	eigene: [{ id: 'e1', name: 'Meine', ampel: {} }],
	abweichungen: 1,
	metrikName: (id: string) => id,
	aboAmpel: {},
	onUebernehmen: noop,
	onEigene: noop,
	onZuruecksetzen: noop,
	onGespeichert: noop
};
const PICKER = 'let pickerOffen = $state(false);';
const WAHL = 'let wahl = $state<{ id: string; name: string; eigen: boolean } | null>(null);';
const ERR = 'let error: string | null = $state(null);';
const dialogProps = (open: boolean, kind = 'route') => ({ open, kind, ampel: {}, onClose: noop, onSaved: noop });

describe('#2966 AC-5: Vorlage-Haken (Menü, Wechsel-Frage, Speichern-Dialog, Namensfehler)', () => {
	test('VorlageKarte zu: keiner der Vorlage-Dialog-Haken, testids bleiben', async () => {
		const h = html(await lade(datei('VorlageKarte')), vorlageProps);
		for (const a of ['vorlage-auswahl', 'vorlage-bestaetigung', 'vorlage-speichern', 'vorlage-speichern-fehler']) {
			assert.equal(bereich(h, a), null, `${a} darf im geschlossenen Zustand nicht erscheinen`);
		}
		assert.match(h, /data-testid="wetter-vorlage-picker"/);
		assert.match(h, /data-testid="wetter-vorlage-als-eigene"/);
	});
	test('Menü offen: data-abschnitt="vorlage-auswahl" umschließt Systemvorlagen und Eigene, nicht den Picker-Knopf', async () => {
		locale.set('de');
		const V = await lade(datei('VorlageKarte'), [[PICKER, PICKER.replace('(false)', '(true)')]]);
		const h = html(V, vorlageProps);
		const menue = bereich(h, 'vorlage-auswahl');
		assert.ok(menue, 'Haken vorlage-auswahl fehlt im offenen Menü');
		for (const id of ['wetter-vorlage-option-standard', 'wetter-vorlage-option-alpin', 'wetter-vorlage-eigene', 'wetter-vorlage-eigene-e1']) {
			assert.match(menue!, new RegExp(`data-testid="${id}"`), `${id} liegt nicht im Bereich vorlage-auswahl`);
		}
		assert.doesNotMatch(menue!, /data-testid="wetter-vorlage-picker"/, 'der Picker-Knopf gehört nicht ins Menü');
		assert.equal(bereich(h, 'vorlage-bestaetigung'), null, 'ohne Wahl keine Wechsel-Frage');
	});
	test('Wechsel-Frage: data-abschnitt="vorlage-bestaetigung" am alertdialog mit Übernehmen und Abbrechen', async () => {
		locale.set('de');
		const V = await lade(datei('VorlageKarte'), [
			[PICKER, PICKER.replace('(false)', '(true)')],
			[WAHL, WAHL.replace('(null)', "({ id: 'alpin', name: 'Alpin', eigen: false })")]
		]);
		const frage = bereich(html(V, vorlageProps), 'vorlage-bestaetigung');
		assert.ok(frage, 'Haken vorlage-bestaetigung fehlt an der Wechsel-Frage');
		assert.match(ersterTag(frage!), /role="alertdialog"/, 'Haken steht nicht am alertdialog');
		assert.match(ersterTag(frage!), /data-testid="wetter-vorlage-wechsel-dialog"/, 'testid wetter-vorlage-wechsel-dialog bleibt am selben Element');
		assert.match(frage!, /data-testid="wetter-vorlage-wechsel-uebernehmen"/);
		assert.match(frage!, /data-testid="wetter-vorlage-wechsel-abbrechen"/);
	});
	test('SavePresetDialog offen: data-abschnitt="vorlage-speichern" am Dialog, zu: kein Haken', async () => {
		locale.set('de');
		const D = await lade(SPD);
		for (const kind of ['route', 'vergleich']) {
			const h = html(D, dialogProps(true, kind));
			const dlg = bereich(h, 'vorlage-speichern');
			assert.ok(dlg, `Haken vorlage-speichern fehlt am offenen Dialog (${kind})`);
			assert.match(ersterTag(dlg!), /data-testid="save-preset-dialog"/, 'Haken steht nicht am Dialog (save-preset-dialog)');
			assert.match(dlg!, /data-testid="save-preset-name"/);
			assert.match(dlg!, /data-testid="save-preset-submit"/);
			assert.equal(bereich(h, 'vorlage-speichern-fehler'), null, 'ohne Fehler kein Fehler-Haken');
		}
		assert.equal(markerZahl(html(D, dialogProps(false))), 0, 'geschlossener Dialog ohne Haken');
	});
	test('SavePresetDialog mit Namensfehler: data-abschnitt="vorlage-speichern-fehler" an save-preset-error', async () => {
		locale.set('de');
		const D = await lade(SPD, [[ERR, ERR.replace('$state(null)', `$state(${JSON.stringify(DE['wetter.dialog.name_pflicht'])})`)]]);
		const f = bereich(html(D, dialogProps(true, 'vergleich')), 'vorlage-speichern-fehler');
		assert.ok(f, 'Haken vorlage-speichern-fehler fehlt');
		assert.match(ersterTag(f!), /data-testid="save-preset-error"/, 'Haken steht nicht an save-preset-error');
		assert.match(ersterTag(f!), /role="alert"/);
		assert.equal(textVon(f!), DE['wetter.dialog.name_pflicht']);
	});
});
