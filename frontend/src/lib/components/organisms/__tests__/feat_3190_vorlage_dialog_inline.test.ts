// TDD RED — Issue #3190 (Epic #2913): „Als eigene Vorlage speichern“ als Inline-Karte nach Mockup.
// Spec: docs/specs/modules/feat_3190_vorlage_dialog_inline.md (AC-1, AC-2, AC-3, AC-4, AC-8, AC-10).
// Soll-Bild: docs/context/einstellungen_neu/seiten/mockup-hub-fassung4.html Z.485-505.
//
// Server-Render der ECHTEN Dateien SavePresetDialog, VorlageKarte und WeatherMetricsTab (Muster
// wetter_tab_abschnitt_marker_2966.test.ts). Zustände nach Klick (Karte offen, Namensfehler) setzt
// startzustandHook.mjs als anderen `$state`-Startwert; das Markup bleibt das der Produktivdatei.
// Fokus, Escape und Umschalten im Browser: frontend/e2e/s3a2794-teil3-vorlage-inline.spec.ts (Staging).
//
//   cd frontend && npm test -- src/lib/components/organisms/__tests__/feat_3190_vorlage_dialog_inline.test.ts

import { test, describe, after } from 'node:test';
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
after(() => locale.set('de'));

const KATALOG = (sprache: 'de' | 'en'): Record<string, string> =>
	JSON.parse(readFileSync(path.join(FRONTEND, 'src/lib/i18n/messages', sprache, 'wetter.json'), 'utf8'));
const DE = KATALOG('de');
const EN = KATALOG('en');

async function lade(file: string, start: [string, string][] = []): Promise<any> {
	const abfrage = start.length ? `?start=${encodeURIComponent(JSON.stringify(start))}` : '';
	return (await import(pathToFileURL(file).href + abfrage)).default;
}
const html = (k: any, props: Record<string, unknown>) => render(k, { props }).body.replace(/<!--[\s\S]*?-->/g, '').trim();
const noop = () => {};
const ent = (s: string) => s.replace(/&amp;/g, '&').replace(/&quot;/g, '"').replace(/&#39;/g, "'").replace(/&nbsp;/g, ' ');
const textVon = (h: string) => ent(h.replace(/<[^>]*>/g, ' ')).replace(/\s+/g, ' ').trim();

/** Element (samt Inhalt) ab dem ersten öffnenden Tag, der auf `re` passt, bis zum passenden Schluss-Tag. */
function elementAb(h: string, re: RegExp): string | null {
	const m = h.match(re);
	if (!m || m.index === undefined) return null;
	const name = m[0].match(/^<([a-z0-9]+)/)![1];
	if (/\/>$/.test(m[0]) || ['input', 'br', 'img', 'hr'].includes(name)) return m[0];
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
const offenerTag = (h: string, testid: string) => h.match(new RegExp(`<[a-z0-9]+\\b[^>]*\\sdata-testid="${testid}"[^>]*>`))?.[0] ?? '';
const attr = (tag: string, name: string) => tag.match(new RegExp(`\\s${name}="([^"]*)"`))?.[1] ?? null;
const pos = (h: string, testid: string) => h.search(new RegExp(`\\sdata-testid="${testid}"`));

const ERR = 'let error: string | null = $state(null);';
const DIALOG_OFFEN = 'let dialogOffen = $state(false);';
const dialogProps = (kind: string) => ({ open: true, kind, ampel: {}, onClose: noop, onSaved: noop });
const LISTE = [{ id: 'standard', label: 'Standard', metrics: [] }];
const vorlageProps = (context: string) => ({
	context,
	vorlageId: 'standard',
	liste: LISTE,
	eigene: [],
	abweichungen: 0,
	metrikName: (id: string) => id,
	aboAmpel: {},
	onUebernehmen: noop,
	onEigene: noop,
	onZuruecksetzen: noop,
	onGespeichert: noop
});

/** Die Karte (Wurzel mit data-testid="save-preset-dialog") samt Inhalt. */
function karte(h: string): string {
	const k = elementAb(h, /<[a-z0-9]+\b[^>]*\sdata-testid="save-preset-dialog"[^>]*>/);
	assert.ok(k, `Karte save-preset-dialog fehlt: ${h.slice(0, 400)}`);
	return k!;
}

// ---------------------------------------------------------------------------------------------------------------
// AC-1 / AC-8: Inline-Karte statt Overlay
// ---------------------------------------------------------------------------------------------------------------
describe('#3190 AC-1/AC-8: Inline-Karte statt modalem Overlay', () => {
	for (const kind of ['route', 'vergleich']) {
		test(`${kind}: kein role=dialog, kein aria-modal, kein Scrim, kein ×, kein tabindex=-1`, async () => {
			locale.set('de');
			const h = html(await lade(SPD), dialogProps(kind));
			assert.doesNotMatch(h, /\srole="dialog"/, 'Karte ist kein modaler Dialog');
			assert.doesNotMatch(h, /\saria-modal=/, 'kein aria-modal');
			assert.doesNotMatch(h, /scrim/i, 'kein abdunkelnder Hintergrund (Scrim)');
			assert.doesNotMatch(h, /\stabindex="-1"/, 'kein tabindex=-1 an der Karte');
			assert.doesNotMatch(h, />\s*×\s*</, 'kein Schließen-Kreuz');
			assert.doesNotMatch(h, /\saria-label="Schließen"/, 'kein Schließen-Knopf');
			assert.ok(h.startsWith('<div'), `Karte ist die Wurzel (kein Hüll-Element davor): ${h.slice(0, 120)}`);
		});
		test(`${kind}: Wurzel div.wt-karte mit role=group, aria-labelledby auf den Titel, Testid und Abschnitt`, async () => {
			locale.set('de');
			const h = html(await lade(SPD), dialogProps(kind));
			const wurzel = offenerTag(h, 'save-preset-dialog');
			assert.match(wurzel, /^<div\b/, 'Wurzel ist ein div');
			assert.match(attr(wurzel, 'class') ?? '', /(^|\s)wt-karte(\s|$)/, 'Karten-Optik über wt-karte');
			assert.equal(attr(wurzel, 'role'), 'group');
			assert.equal(attr(wurzel, 'data-abschnitt'), 'vorlage-speichern');
			const id = attr(wurzel, 'aria-labelledby');
			assert.ok(id, 'aria-labelledby fehlt');
			const titel = h.match(new RegExp(`<([a-z0-9]+)\\b[^>]*\\sid="${id}"[^>]*>([\\s\\S]*?)</\\1>`));
			assert.ok(titel, `Titel-Element mit id="${id}" fehlt`);
			assert.equal(titel![1], 'b', 'Titel ist <b> (Mockup)');
			assert.equal(textVon(titel![2]), DE['wetter.dialog.titel']);
		});
	}
	test('geschlossen: nichts gerendert', async () => {
		const h = html(await lade(SPD), { ...dialogProps('route'), open: false });
		assert.equal(h, '');
	});
});

// ---------------------------------------------------------------------------------------------------------------
// Bedienelemente: einzeiliges Input-Atom, Haken mit Beschriftung, Btn-Atome
// ---------------------------------------------------------------------------------------------------------------
describe('#3190 AC-2/AC-8: Felder und Ankreuzfeld aus Bausteinen', () => {
	for (const [kind, schluessel] of [
		['route', 'wetter.dialog.standard_route'],
		['vergleich', 'wetter.dialog.standard_vergleich']
	] as const) {
		for (const [sprache, kat] of [
			['de', DE],
			['en', EN]
		] as const) {
			test(`${kind}/${sprache}: kein <textarea>, kein role=switch; Ankreuzfeld mit sichtbarem Text im <label>`, async () => {
				locale.set(sprache);
				const k = karte(html(await lade(SPD), dialogProps(kind)));
				assert.doesNotMatch(k, /<textarea\b/, 'Beschreibung ist einzeilig');
				assert.doesNotMatch(k, /\srole="switch"/, 'Schalter wird Ankreuzfeld');
				const std = elementAb(k, /<[a-z0-9]+\b[^>]*\sdata-testid="save-preset-is-default"[^>]*>/);
				assert.ok(std, 'save-preset-is-default fehlt');
				assert.match(std!, /^<label\b/, 'testid sitzt am beschrifteten <label> (ganzer Text klickbar)');
				assert.equal((std!.match(/<label\b/g) ?? []).length, 1, 'kein verschachteltes <label>');
				assert.match(std!, /<input\b[^>]*\stype="checkbox"/, 'echtes Kontrollkästchen aus dem Haken-Atom');
				assert.match(std!, /\sdata-slot="haken"/, 'Ankreuzfeld kommt aus dem Haken-Atom');
				assert.equal(textVon(std!), kat[schluessel], 'Beschriftung am Ankreuzfeld je Kontext');
			});
		}
	}
	test('Name und Beschreibung: <input>, Beschreibung maxlength=120, beide mit <label for>', async () => {
		locale.set('de');
		const k = karte(html(await lade(SPD), dialogProps('route')));
		for (const [testid, beschriftung] of [
			['save-preset-name', DE['wetter.dialog.name']],
			['save-preset-description', DE['wetter.dialog.beschreibung']]
		]) {
			const feld = offenerTag(k, testid);
			assert.match(feld, /^<input\b/, `${testid} ist ein einzeiliges <input>`);
			const id = attr(feld, 'id');
			assert.ok(id, `${testid} ohne id (für <label for>)`);
			const label = k.match(new RegExp(`<label\\b[^>]*\\sfor="${id}"[^>]*>([\\s\\S]*?)</label>`));
			assert.ok(label, `<label for="${id}"> fehlt`);
			assert.equal(textVon(label![1]), beschriftung);
		}
		assert.equal(attr(offenerTag(k, 'save-preset-description'), 'maxlength'), '120');
	});
	test('Knöpfe sind Btn-Atome: Speichern accent, Abbrechen ghost, beide size=tap', async () => {
		locale.set('de');
		const k = karte(html(await lade(SPD), dialogProps('route')));
		const knoepfe = k.match(/<button\b[^>]*>[\s\S]*?<\/button>/g) ?? [];
		const speichern = knoepfe.find((b) => /\sdata-testid="save-preset-submit"/.test(b));
		const abbrechen = knoepfe.find((b) => textVon(b) === 'Abbrechen');
		assert.ok(speichern && abbrechen, `Knöpfe fehlen: ${JSON.stringify(knoepfe)}`);
		for (const [b, variante] of [
			[speichern!, 'accent'],
			[abbrechen!, 'ghost']
		] as const) {
			assert.match(b, /\sdata-slot="btn"/, 'kein Btn-Atom');
			assert.match(b, new RegExp(`\\sdata-variant="${variante}"`));
			assert.match(b, /\sdata-size="tap"/, 'Touch-Ziel ≥ 44px über size=tap');
		}
	});
});

// ---------------------------------------------------------------------------------------------------------------
// AC-3 / AC-4: Reihenfolge, Fehlerzeile direkt unter Name
// ---------------------------------------------------------------------------------------------------------------
describe('#3190 AC-3/AC-4: Reihenfolge nach Mockup', () => {
	test('Titel, Name, Beschreibung, Ankreuzfeld, Hinweis, Speichern, Abbrechen', async () => {
		locale.set('de');
		const k = karte(html(await lade(SPD), dialogProps('route')));
		const titel = k.indexOf(`>${DE['wetter.dialog.titel']}<`);
		const folge = [
			titel,
			pos(k, 'save-preset-name'),
			pos(k, 'save-preset-description'),
			pos(k, 'save-preset-is-default'),
			pos(k, 'save-preset-hinweis'),
			pos(k, 'save-preset-submit'),
			k.search(/>\s*Abbrechen\s*</)
		];
		assert.ok(folge.every((p) => p > -1), `Element fehlt: ${JSON.stringify(folge)}`);
		for (let i = 1; i < folge.length; i += 1) assert.ok(folge[i - 1] < folge[i], `Reihenfolge verletzt an Stelle ${i}: ${JSON.stringify(folge)}`);
	});
	test('Namensfehler: Fehlerzeile direkt unter Name, vor der Beschreibung; Feld mit aria-invalid und aria-describedby', async () => {
		locale.set('de');
		const D = await lade(SPD, [[ERR, ERR.replace('$state(null)', `$state(${JSON.stringify(DE['wetter.dialog.name_pflicht'])})`)]]);
		const k = karte(html(D, dialogProps('vergleich')));
		const name = pos(k, 'save-preset-name');
		const fehler = pos(k, 'save-preset-error');
		const beschreibung = pos(k, 'save-preset-description');
		assert.ok(name > -1 && fehler > -1 && beschreibung > -1);
		assert.ok(name < fehler && fehler < beschreibung, `Fehlerzeile gehört zwischen Name und Beschreibung: ${JSON.stringify({ name, fehler, beschreibung })}`);
		const fTag = offenerTag(k, 'save-preset-error');
		assert.equal(attr(fTag, 'role'), 'alert');
		assert.equal(attr(fTag, 'data-abschnitt'), 'vorlage-speichern-fehler');
		const fid = attr(fTag, 'id');
		assert.ok(fid, 'Fehlerzeile ohne id');
		const feld = offenerTag(k, 'save-preset-name');
		assert.equal(attr(feld, 'aria-invalid'), 'true');
		assert.equal(attr(feld, 'aria-describedby'), fid, 'Namensfeld verweist auf die Fehlerzeile');
		assert.equal(textVon(elementAb(k, /<[a-z0-9]+\b[^>]*\sdata-testid="save-preset-error"[^>]*>/)!), DE['wetter.dialog.name_pflicht']);
	});
});

// ---------------------------------------------------------------------------------------------------------------
// AC-1: Platz unter der Vorlage-Karte, Auslöser als Umschalter (Trip und Orts-Vergleich)
// ---------------------------------------------------------------------------------------------------------------
describe('#3190 AC-1: Auslöser schaltet um und zeigt auf die Karte', () => {
	for (const context of ['route', 'vergleich']) {
		test(`${context} offen: Karte steht direkt nach der Vorlage-Karte; Auslöser aria-expanded=true, aria-controls = id der Karte`, async () => {
			locale.set('de');
			const V = await lade(path.join(WT, 'VorlageKarte.svelte'), [[DIALOG_OFFEN, DIALOG_OFFEN.replace('(false)', '(true)')]]);
			const h = html(V, vorlageProps(context));
			const vorlage = elementAb(h, /<div\b[^>]*\sdata-abschnitt="vorlage"[^>]*>/);
			assert.ok(vorlage, 'Vorlage-Karte fehlt');
			const nach = h.slice(h.indexOf(vorlage!) + vorlage!.length).trim();
			assert.match(nach, /^<div\b[^>]*\sdata-testid="save-preset-dialog"/, 'Karte folgt direkt der Vorlage-Karte');
			const ausloeser = offenerTag(h, 'wetter-vorlage-als-eigene');
			assert.equal(attr(ausloeser, 'aria-expanded'), 'true');
			const ziel = attr(ausloeser, 'aria-controls');
			assert.ok(ziel, 'aria-controls fehlt am Auslöser');
			assert.equal(attr(offenerTag(h, 'save-preset-dialog'), 'id'), ziel, 'aria-controls zeigt nicht auf die Karte');
		});
		test(`${context} zu: Auslöser aria-expanded=false, keine Karte`, async () => {
			locale.set('de');
			const h = html(await lade(path.join(WT, 'VorlageKarte.svelte')), vorlageProps(context));
			assert.equal(attr(offenerTag(h, 'wetter-vorlage-als-eigene'), 'aria-expanded'), 'false');
			assert.equal(pos(h, 'save-preset-dialog'), -1);
		});
	}
});

// #3297/#3020: AC-10 (Alt-Editor WeatherMetricsTab, weatherMetricsTabSections) entfaellt — beide Dateien geloescht.
