// TDD RED — Issue #2913, Scheibe (c): Wetter-Reiter „Nicht im Briefing“, Warnungen, Radar, Anpassen.
// Spec: docs/specs/modules/feat_2913_scheibe_c_wetter_rest.md — AC-1, AC-2, AC-3, AC-4, AC-5, AC-6, AC-8.
//
// Vertrag (hier festgelegt, /50 baut danach):
//   NichtImBriefing      Label „Nicht im Briefing“ und <ChipLeiste> sind Geschwister in EINER waagrechten,
//                        umbrechenden Zeile (Mockup `.more`, Z.135): deren Klasse ist display:flex, flex-wrap:wrap,
//                        nie flex-direction:column. Anker wetter-nicht-im-briefing(-plus-<id>) und
//                        wetter-hinzugefuegt-meldung bleiben (K-7).
//   WarnungenRadarKarte  Schalter = Atom Switch (atoms) mit testid wetter-warnungen-schalter / wetter-radar-schalter,
//                        `tap` gesetzt, aria-label aus dem Katalog; kein rohes Control, kein .wt-switch/.wt-track/
//                        .wt-knopf. Radar-Zeile nur mit mitRadar (Orts-Briefing, AC-3).
//   AnpassenKarte        Molekül Aufklapper (testid wetter-anpassen-karte, summaryTestid wetter-anpassen-aufklappen,
//                        Titel wetter.anpassen.titel, Startzustand zu); Inhalt Einstellungszeile titel
//                        wetter.anpassen.tagesfenster, hinweis wetter.anpassen.hinweis, darin zwei UhrzeitFeld im
//                        Stundenraster: testid day-window-start-hour (ariaLabel wetter.anpassen.von) und
//                        day-window-end-hour (ariaLabel wetter.anpassen.bis), Wert `HH:00` aus tagesfenster;
//                        Ende < Start → Hinweis data-testid="day-window-wrap-hint" mit wetter.anpassen.ueber_mitternacht.
//                        Ende = Start wird über clampDayWindowEndHour (versand-tab/dayWindowClamp.ts) verhindert.
//                        DayWindowCard wird nicht mehr importiert.
//   i18n                 Neue Schlüssel wetter.anpassen.hinweis („Welche Stunden bewertet werden“) und
//                        wetter.anpassen.ueber_mitternacht in DE und EN; beide Kataloge gleiche Schlüsselmenge.
//
// Verhalten per Server-Render (svelte/server); Quellregeln (rohe Controls, Eigen-CSS, Importe, CSS der Zeile):
// doc-compliance-test
//
//   cd frontend && npm test -- src/lib/components/organisms/__tests__/wetter_tab_scheibe_c.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { register } from 'node:module';
import { existsSync, readFileSync } from 'node:fs';
import { fileURLToPath, pathToFileURL } from 'node:url';
import path from 'node:path';
import { parse } from 'svelte/compiler';

const HERE = path.dirname(fileURLToPath(import.meta.url));
// __tests__ -> organisms -> components -> lib -> src -> frontend
const FRONTEND = path.resolve(HERE, '../../../../..');
const WT = path.resolve(HERE, '..', 'wetter-tab');
const MSG = path.join(FRONTEND, 'src', 'lib', 'i18n', 'messages');

register(pathToFileURL(path.join(FRONTEND, 'test-svelte-ssr-hooks.mjs')).href, pathToFileURL(FRONTEND + '/').href);
const { render } = await import('svelte/server');

const KAT = (sprache: 'de' | 'en'): Record<string, string> => JSON.parse(readFileSync(path.join(MSG, sprache, 'wetter.json'), 'utf8'));
const DE = KAT('de');
const EN = KAT('en');

const datei = (n: string) => path.join(WT, `${n}.svelte`);
const quelle = (n: string) => readFileSync(datei(n), 'utf8');
const lade = async (n: string): Promise<any> => (await import(pathToFileURL(datei(n)).href)).default;
const html = (k: any, props: Record<string, unknown>) => render(k, { props }).body.replace(/<!--[\s\S]*?-->/g, '');
const text = (h: string) => h.replace(/<[^>]*>/g, ' ').replace(/&nbsp;/g, ' ').replace(/\s+/g, ' ').trim();
const noop = () => {};
const tagMitTestid = (h: string, id: string) => h.match(new RegExp(`<[a-z]+\\b[^>]*data-testid="${id}"[^>]*>`))?.[0] ?? null;

type Knoten = Record<string, any>;
const ast = (q: string): Knoten => parse(q, { modern: true }) as unknown as Knoten;
function alle(x: unknown, pred: (n: Knoten) => boolean, aus: Knoten[] = []): Knoten[] {
	if (Array.isArray(x)) x.forEach((y) => alle(y, pred, aus));
	else if (x && typeof x === 'object') {
		const n = x as Knoten;
		if (pred(n)) aus.push(n);
		for (const [k, v] of Object.entries(n)) if (k !== 'parent') alle(v, pred, aus);
	}
	return aus;
}
const ROH = new Set(['button', 'input', 'select', 'textarea']);
const roheControls = (q: string) => alle(ast(q).fragment, (n) => n.type === 'RegularElement' && ROH.has(String(n.name))).map((n) => `<${n.name}>`);
function importVon(q: string, name: string): string | null {
	for (const s of (ast(q).instance?.content?.body ?? []) as Knoten[]) {
		if (s.type !== 'ImportDeclaration') continue;
		if ((s.specifiers as Knoten[]).some((sp) => sp.local?.name === name)) return String(s.source.value);
	}
	return null;
}
const nutzt = (q: string, name: string) => alle(ast(q).fragment, (n) => n.type === 'Component' && n.name === name).length;

// ─── AC-6: keine rohen Controls, kein Eigen-CSS ──────────────────────────────

describe('AC-6: die drei Organismen nur aus Bausteinen (doc-compliance-test)', () => {
	for (const n of ['NichtImBriefing', 'WarnungenRadarKarte', 'AnpassenKarte']) {
		test(`${n}: kein rohes <button>/<input>/<select>/<textarea>, kein audit:exempt`, () => {
			const q = quelle(n);
			assert.deepEqual(roheControls(q), [], `TDD RED: ${n} enthält rohe Controls`);
			assert.doesNotMatch(q, /audit:exempt/);
		});
	}
	test('WarnungenRadarKarte: kein Eigen-CSS .wt-switch/.wt-track/.wt-knopf', () => {
		assert.doesNotMatch(quelle('WarnungenRadarKarte'), /\.wt-(switch|track|knopf)\b/, 'TDD RED: Eigen-Schalter-CSS noch vorhanden');
	});
	test('WarnungenRadarKarte: Schalter aus dem Atom Switch', () => {
		const q = quelle('WarnungenRadarKarte');
		const von = importVon(q, 'Switch');
		assert.ok(von, 'TDD RED: WarnungenRadarKarte importiert Switch nicht');
		assert.match(von!, /^\$lib\/components\/atoms(\/Switch\.svelte)?$/);
		assert.ok(nutzt(q, 'Switch') > 0);
	});
	test('AnpassenKarte: Aufklapper + Einstellungszeile + UhrzeitFeld aus molecules, Clamp aus dayWindowClamp, kein DayWindowCard', () => {
		const q = quelle('AnpassenKarte');
		for (const [name, re] of [
			['Aufklapper', /^\$lib\/components\/molecules(\/Aufklapper\.svelte)?$/],
			['Einstellungszeile', /^\$lib\/components\/molecules(\/Einstellungszeile\.svelte)?$/],
			['UhrzeitFeld', /^\$lib\/components\/molecules(\/UhrzeitFeld\.svelte)?$/]
		] as const) {
			const von = importVon(q, name);
			assert.ok(von, `TDD RED: AnpassenKarte importiert ${name} nicht`);
			assert.match(von!, re);
		}
		assert.ok(nutzt(q, 'Aufklapper') === 1, 'genau ein <Aufklapper>');
		assert.ok(nutzt(q, 'UhrzeitFeld') === 2, 'genau zwei <UhrzeitFeld>');
		assert.match(importVon(q, 'clampDayWindowEndHour') ?? '', /versand-tab\/dayWindowClamp(\.ts)?$/, 'TDD RED: Clamp nicht aus dayWindowClamp');
		assert.equal(importVon(q, 'DayWindowCard'), null, 'TDD RED: DayWindowCard noch importiert');
	});
});

// ─── AC-1: Nicht im Briefing in einer Zeile ──────────────────────────────────

describe('AC-1: „Nicht im Briefing“ als eine waagrechte Zeile', () => {
	const METRIKEN = [
		{ id: 'wind', name: 'Wind' },
		{ id: 'gust', name: 'Böen' }
	];
	// doc-compliance-test: Layout ist CSS, im Server-Render nicht messbar.
	test('Label und ChipLeiste sind Geschwister in einer flex-Zeile mit Umbruch, nicht gestapelt', () => {
		const q = quelle('NichtImBriefing');
		const a = ast(q);
		const eltern = alle(a.fragment, (n) => n.type === 'RegularElement' && (n.fragment?.nodes ?? []).some((c: Knoten) => c.type === 'Component' && c.name === 'ChipLeiste'));
		assert.equal(eltern.length, 1, 'ChipLeiste nicht genau einmal direkt in einem Element');
		const e = eltern[0];
		const labelGeschwister = (e.fragment.nodes as Knoten[]).some(
			(c) => c.type === 'RegularElement' && q.slice(c.start, c.end).includes("'wetter.nicht_im_briefing.titel'")
		);
		assert.ok(labelGeschwister, 'Label „Nicht im Briefing“ ist kein Geschwister der ChipLeiste');
		const klasse = (e.attributes as Knoten[]).find((x) => x.name === 'class');
		const kl = klasse ? q.slice(klasse.start, klasse.end).match(/class="([^"]+)"/)?.[1]?.split(/\s+/)[0] : undefined;
		assert.ok(kl, 'Zeilen-Element ohne statische Klasse');
		const css = String(a.css?.content?.styles ?? '').replace(/\/\*[\s\S]*?\*\//g, '');
		const rumpf = [...css.matchAll(/([^{}]+)\{([^{}]*)\}/g)]
			.filter((m) => m[1].split(',').some((s) => s.trim() === `.${kl}`))
			.map((m) => m[2])
			.join(';');
		assert.match(rumpf, /display:\s*flex/, `.${kl} ist keine flex-Zeile`);
		assert.match(rumpf, /flex-wrap:\s*wrap/, `TDD RED: .${kl} bricht nicht um`);
		assert.doesNotMatch(rumpf, /flex-direction:\s*column/, `TDD RED: .${kl} stapelt Label und Chips untereinander`);
	});
	test('SSR: Anker, Label aus dem Katalog, Chips und Meldung bleiben (K-7)', async () => {
		const N = await lade('NichtImBriefing');
		const h = html(N, { metriken: METRIKEN, hinzugefuegt: 'Wind', onHinzufuegen: noop });
		assert.ok(tagMitTestid(h, 'wetter-nicht-im-briefing'));
		for (const m of METRIKEN) assert.ok(tagMitTestid(h, `wetter-nicht-im-briefing-plus-${m.id}`));
		assert.ok(tagMitTestid(h, 'wetter-hinzugefuegt-meldung'));
		assert.ok(text(h).startsWith(DE['wetter.nicht_im_briefing.titel']));
	});
});

// ─── AC-2/AC-3: Warnungen und Radar ──────────────────────────────────────────

describe('AC-2/AC-3: Karte Warnungen/Radar mit Switch-Atom', () => {
	const props = (mitRadar: boolean) => ({ warnungenAn: true, radarAn: false, mitRadar, onWarnungen: noop, onRadar: noop });
	test('SSR: Warnungen-Schalter ist das Atom (role=switch, aria-checked, 36×20, data-tap, aria-label)', async () => {
		const K = await lade('WarnungenRadarKarte');
		const tag = tagMitTestid(html(K, props(false)), 'wetter-warnungen-schalter');
		assert.ok(tag, 'Anker wetter-warnungen-schalter fehlt');
		assert.match(tag!, /^<span\b/, 'TDD RED: Schalter ist nicht das Switch-Atom');
		assert.match(tag!, /\srole="switch"/);
		assert.match(tag!, /\saria-checked="true"/);
		assert.match(tag!, /\sdata-tap="true"/, 'TDD RED: keine Tapfläche');
		assert.match(tag!, /width:\s*36px/);
		assert.match(tag!, /height:\s*20px/);
		assert.match(tag!, new RegExp(`\\saria-label="${DE['wetter.warnungen.titel']}"`));
	});
	test('SSR Orts-Briefing (mitRadar): Radar-Schalter als Atom mit aria-checked="false"', async () => {
		const K = await lade('WarnungenRadarKarte');
		const h = html(K, props(true));
		const tag = tagMitTestid(h, 'wetter-radar-schalter');
		assert.ok(tag, 'Anker wetter-radar-schalter fehlt');
		assert.match(tag!, /^<span\b/, 'TDD RED: Radar-Schalter ist nicht das Switch-Atom');
		assert.match(tag!, /\saria-checked="false"/);
		assert.match(tag!, /\sdata-tap="true"/);
		assert.match(text(h), new RegExp(DE['wetter.radar.titel']));
	});
	test('SSR Trip (ohne mitRadar): keine Radar-Zeile, kein Radar-Schalter', async () => {
		const K = await lade('WarnungenRadarKarte');
		const h = html(K, props(false));
		assert.equal(tagMitTestid(h, 'wetter-radar-schalter'), null);
		assert.doesNotMatch(text(h), new RegExp(DE['wetter.radar.titel']));
	});
});

// ─── AC-4/AC-5: Anpassen mit Tagesfenster ────────────────────────────────────

describe('AC-4/AC-5: Karte „Anpassen“ als Aufklapper mit Tagesfenster im Stundenraster', () => {
	const props = (start: number, end: number) => ({ tagesfenster: { start, end }, onStart: noop, onEnde: noop });

	test('SSR: Aufklapper zu, Anker erhalten, Titel aus dem Katalog, Zeichen „＋“', async () => {
		const A = await lade('AnpassenKarte');
		const h = html(A, props(6, 20));
		const karte = tagMitTestid(h, 'wetter-anpassen-karte');
		assert.ok(karte, 'Anker wetter-anpassen-karte fehlt');
		assert.match(karte!, /^<details\b/, 'TDD RED: Anpassen ist kein Aufklapper (details)');
		assert.doesNotMatch(karte!, /\sopen\b/);
		const sum = h.match(/<summary\b[^>]*data-testid="wetter-anpassen-aufklappen"[^>]*>([\s\S]*?)<\/summary>/);
		assert.ok(sum, 'TDD RED: kein <summary> mit Anker wetter-anpassen-aufklappen');
		assert.match(sum![0], /aria-expanded="false"/);
		assert.match(text(sum![1]), new RegExp(DE['wetter.anpassen.titel']));
		assert.match(sum![1], /＋/);
	});
	test('SSR: Zeile „Tagesfenster“ mit Hinweis „Welche Stunden bewertet werden“', async () => {
		const A = await lade('AnpassenKarte');
		const h = html(A, props(6, 20));
		assert.match(h, /data-slot="einstellungszeile"/, 'TDD RED: keine Einstellungszeile');
		assert.equal(DE['wetter.anpassen.hinweis'], 'Welche Stunden bewertet werden', 'TDD RED: Katalogtext wetter.anpassen.hinweis fehlt');
		const hinweis = h.match(/<small\b[^>]*data-slot="einstellungszeile-hinweis"[^>]*>([\s\S]*?)<\/small>/);
		assert.ok(hinweis, 'Hinweis fehlt');
		assert.equal(text(hinweis![1]), DE['wetter.anpassen.hinweis']);
		assert.match(text(h), new RegExp(DE['wetter.anpassen.tagesfenster']));
	});
	test('SSR: zwei Uhrzeitfelder von/bis im Stundenraster mit 06:00 und 20:00, kein Select', async () => {
		const A = await lade('AnpassenKarte');
		const h = html(A, props(6, 20));
		assert.doesNotMatch(h, /<select\b/);
		for (const [id, label, wert] of [
			['day-window-start-hour', DE['wetter.anpassen.von'], '06:00'],
			['day-window-end-hour', DE['wetter.anpassen.bis'], '20:00']
		]) {
			const m = h.match(new RegExp(`(<div\\b[^>]*data-testid="${id}"[^>]*>)([\\s\\S]*?)</div>\\s*</div>`));
			assert.ok(m, `TDD RED: Uhrzeitfeld ${id} fehlt`);
			assert.match(m![1], /data-slot="uhrzeit-feld"/, `${id} ist nicht das UhrzeitFeld`);
			assert.match(m![1], /data-stundenraster="true"/, `TDD RED: ${id} nicht im Stundenraster`);
			assert.match(m![2], new RegExp(`aria-label="${label}"`), `${id} ohne aria-label „${label}“`);
			assert.match(text(m![2]).replace(/\s/g, ''), new RegExp(wert), `${id} zeigt nicht ${wert}`);
		}
	});
	test('SSR: Fenster über Mitternacht (22–6) zeigt den Hinweis, 6–20 nicht', async () => {
		const A = await lade('AnpassenKarte');
		assert.ok(DE['wetter.anpassen.ueber_mitternacht'], 'TDD RED: Katalogtext wetter.anpassen.ueber_mitternacht fehlt');
		const nacht = html(A, props(22, 6));
		const m = nacht.match(/<[a-z]+\b[^>]*data-testid="day-window-wrap-hint"[^>]*>([\s\S]*?)<\/[a-z]+>/);
		assert.ok(m, 'TDD RED: kein Über-Mitternacht-Hinweis');
		assert.equal(text(m![1]), DE['wetter.anpassen.ueber_mitternacht']);
		assert.equal(tagMitTestid(html(A, props(6, 20)), 'day-window-wrap-hint'), null);
	});
});

// ─── AC-8: Katalog DE/EN ─────────────────────────────────────────────────────

describe('AC-8: neue Katalogtexte in DE und EN', () => {
	for (const k of ['wetter.anpassen.hinweis', 'wetter.anpassen.ueber_mitternacht']) {
		test(`${k} in DE und EN, nicht leer, unterschiedlich`, () => {
			assert.ok(DE[k]?.trim(), `TDD RED: ${k} fehlt in DE`);
			assert.ok(EN[k]?.trim(), `TDD RED: ${k} fehlt in EN`);
			assert.notEqual(DE[k], EN[k], `${k}: EN ist nicht übersetzt`);
		});
	}
	test('DE und EN haben dieselbe Schlüsselmenge', () => {
		assert.deepEqual(Object.keys(EN).sort(), Object.keys(DE).sort());
	});
});
