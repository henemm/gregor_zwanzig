// TDD RED — Issue #3122 Scheibe B3a: Bausteine für die Einstell-Tabelle „Was steht wo“ (Atome).
// Spec: docs/specs/modules/feat_3122_was_steht_wo.md — Teil B Nr. 10/11, AC-25, AC-26 (Baustein-Anteil).
//
// Vertrag (hier festgelegt):
//   atoms/Haken.svelte            Props: zustand: 'an' | 'aus' | 'gesperrt' | 'nicht_in_email' | 'fest',
//                                 name: string (zugänglicher Name, z. B. „Wind in E-Mail“), grund?: string,
//                                 bedienbar?: boolean (Standard true), onAenderung?: (an: boolean) => void, testid?.
//     an/aus          → echtes <input type="checkbox"> mit aria-label = name; bedienbar=false ⇒ disabled.
//     gesperrt        → kein Kontrollkästchen: role="img", Name „{name}: {grund}“, Strich, Grund als sichtbarer Kurztext.
//     nicht_in_email  → kein Kontrollkästchen: role="img", Name „{name}: {grund}“, Strich, Grund nur als Name/title.
//     fest            → kein Kontrollkästchen (keine Abwahl): role="img", Name „{name}: {grund}“.
//   atoms/RohEinfachKnopf.svelte  Props: wert: 'raw' | 'simplified' | null (null = nur eine Form ⇒ nichts),
//                                 name: string, onAenderung?: (neu) => void, testid?.
//     → <button type="button"> mit aria-label „Darstellung {name}: {Form}“ und der Form als sichtbarem Text
//       (Zustand nicht nur über Farbe). Formwörter aus dem Katalog (DE/EN).
//
// Verhalten per Server-Render (svelte/server). Klick und Tastatur: frontend/e2e/einstelltabelle-bausteine.spec.ts.
//
//   cd frontend && npm test -- src/lib/components/atoms/__tests__/haken_roh_einfach.test.ts

import { test, describe, afterEach } from 'node:test';
import assert from 'node:assert/strict';
import { register } from 'node:module';
import { existsSync, readFileSync } from 'node:fs';
import { fileURLToPath, pathToFileURL } from 'node:url';
import path from 'node:path';
import { locale } from '../../../i18n/index.ts';

const HERE = path.dirname(fileURLToPath(import.meta.url));
// __tests__ -> atoms -> components -> lib -> src -> frontend
const FRONTEND = path.resolve(HERE, '../../../../..');
const ATOMS = path.resolve(HERE, '..');

register(pathToFileURL(path.join(FRONTEND, 'test-svelte-ssr-hooks.mjs')).href, pathToFileURL(FRONTEND + '/').href);
const { render } = await import('svelte/server');

async function lade(name: string): Promise<any> {
	const datei = path.join(ATOMS, `${name}.svelte`);
	assert.ok(existsSync(datei), `TDD RED: atoms/${name}.svelte fehlt`);
	return (await import(pathToFileURL(datei).href)).default;
}
const html = (k: any, props: Record<string, unknown>) => render(k, { props }).body.replace(/<!--[\s\S]*?-->/g, '');
/** Sichtbarer Text: ohne Elemente mit aria-hidden="true" (einstufig, reicht für die Atome). */
const sichtbar = (h: string) =>
	h
		.replace(/<([a-z]+)\b[^>]*aria-hidden="true"[^>]*>[\s\S]*?<\/\1>/g, ' ')
		.replace(/<[^>]*>/g, ' ')
		.replace(/\s+/g, ' ')
		.trim();
const tag = (h: string, muster: RegExp) => h.match(muster)?.[0] ?? '';

afterEach(() => locale.set('de'));

describe('Haken: an und aus sind ein echtes Kontrollkästchen', () => {
	test('an → input[type=checkbox] checked, zugänglicher Name = name, bedienbar', async () => {
		const H = await lade('Haken');
		const h = html(H, { zustand: 'an', name: 'Wind in E-Mail', testid: 'hk' });
		const input = tag(h, /<input\b[^>]*>/);
		assert.match(input, /\stype="checkbox"/);
		assert.match(input, /\saria-label="Wind in E-Mail"/);
		assert.match(input, /\schecked\b/);
		assert.doesNotMatch(input, /\sdisabled\b/);
		assert.match(h, /data-slot="haken"/);
		assert.match(h, /data-zustand="an"/);
		assert.match(h, /data-testid="hk"/);
	});
	test('aus → Kontrollkästchen ohne checked', async () => {
		const H = await lade('Haken');
		const input = tag(html(H, { zustand: 'aus', name: 'Böen in Telegram' }), /<input\b[^>]*>/);
		assert.match(input, /\stype="checkbox"/);
		assert.match(input, /\saria-label="Böen in Telegram"/);
		assert.doesNotMatch(input, /\schecked\b/);
	});
	test('nicht bedienbar (Block aus, Kurzstil) → disabled, der Haken-Zustand bleibt sichtbar', async () => {
		const H = await lade('Haken');
		const an = tag(html(H, { zustand: 'an', name: 'Wind in Telegram', bedienbar: false }), /<input\b[^>]*>/);
		assert.match(an, /\sdisabled\b/);
		assert.match(an, /\schecked\b/);
		const aus = tag(html(H, { zustand: 'aus', name: 'Wind in Telegram', bedienbar: false }), /<input\b[^>]*>/);
		assert.match(aus, /\sdisabled\b/);
		assert.doesNotMatch(aus, /\schecked\b/);
	});
});

describe('Haken: Strich statt Haken', () => {
	test('gesperrt → kein Kontrollkästchen, role=img mit Name und Grund, Grund als sichtbarer Kurztext', async () => {
		const H = await lade('Haken');
		const h = html(H, { zustand: 'gesperrt', name: 'Sonnenstunden im Stundenverlauf', grund: 'kein Stundenwert' });
		assert.doesNotMatch(h, /<input\b/);
		const w = tag(h, /<[a-z]+\b[^>]*role="img"[^>]*>/);
		assert.match(w, /\saria-label="Sonnenstunden im Stundenverlauf: kein Stundenwert"/);
		assert.match(h, /data-zustand="gesperrt"/);
		assert.equal(sichtbar(h), 'kein Stundenwert');
		assert.match(h, /aria-hidden="true"[^>]*>\s*–\s*</, 'der Strich ist reine Optik (aria-hidden)');
	});
	test('nicht in der E-Mail → Strich, Grund als zugänglicher Name und title, kein sichtbarer Text', async () => {
		const H = await lade('Haken');
		const h = html(H, { zustand: 'nicht_in_email', name: 'Wind im 3-Tages-Ausblick', grund: 'nicht in der E-Mail' });
		assert.doesNotMatch(h, /<input\b/);
		const w = tag(h, /<[a-z]+\b[^>]*role="img"[^>]*>/);
		assert.match(w, /\saria-label="Wind im 3-Tages-Ausblick: nicht in der E-Mail"/);
		assert.match(w, /\stitle="nicht in der E-Mail"/);
		assert.equal(sichtbar(h), '');
		assert.match(h, /aria-hidden="true"[^>]*>\s*–\s*</);
	});
	test('fest (ohne Abwahl) → kein Kontrollkästchen, role=img mit Name und Grund', async () => {
		const H = await lade('Haken');
		const h = html(H, { zustand: 'fest', name: 'Amtliche Warnungen in SMS', grund: 'immer dabei' });
		assert.doesNotMatch(h, /<input\b/);
		const w = tag(h, /<[a-z]+\b[^>]*role="img"[^>]*>/);
		assert.match(w, /\saria-label="Amtliche Warnungen in SMS: immer dabei"/);
		assert.match(h, /data-zustand="fest"/);
		assert.equal(sichtbar(h), '');
	});
});

describe('RohEinfachKnopf: Zustand als Text, nicht nur als Farbe', () => {
	test('raw → button mit „Roh“ sichtbar und im zugänglichen Namen', async () => {
		const K = await lade('RohEinfachKnopf');
		const h = html(K, { wert: 'raw', name: 'Wind in E-Mail', testid: 'rek' });
		const b = tag(h, /<button\b[^>]*>/);
		assert.match(b, /\stype="button"/);
		assert.match(b, /\saria-label="Darstellung Wind in E-Mail: Roh"/);
		assert.match(b, /\sdata-wert="raw"/);
		assert.match(b, /\sdata-testid="rek"/);
		assert.match(sichtbar(h), /Roh/);
		assert.doesNotMatch(sichtbar(h), /Einf/);
	});
	test('simplified → „Einfach“ sichtbar und im zugänglichen Namen', async () => {
		const K = await lade('RohEinfachKnopf');
		const h = html(K, { wert: 'simplified', name: 'Bewölkung im Stundenverlauf' });
		assert.match(tag(h, /<button\b[^>]*>/), /\saria-label="Darstellung Bewölkung im Stundenverlauf: Einfach"/);
		assert.match(sichtbar(h), /Einfach/);
		assert.doesNotMatch(sichtbar(h), /Roh/);
	});
	test('null (die Stelle hat nur eine Form) → der Knopf erscheint nicht', async () => {
		const K = await lade('RohEinfachKnopf');
		assert.doesNotMatch(html(K, { wert: null, name: 'Temperatur in E-Mail' }), /<button\b/);
	});
	test('Englisch: Formwörter und Name aus dem Katalog', async () => {
		const K = await lade('RohEinfachKnopf');
		locale.set('en');
		const h = html(K, { wert: 'simplified', name: 'Wind in email' });
		assert.match(tag(h, /<button\b[^>]*>/), /\saria-label="Format of Wind in email: Simple"/);
		assert.match(sichtbar(h), /Simple/);
	});
});

describe('Barrel atoms/index.ts', () => {
	const barrel = readFileSync(path.join(ATOMS, 'index.ts'), 'utf8').replace(/\/\/.*$/gm, '');
	for (const n of ['Haken', 'RohEinfachKnopf']) {
		test(`${n} im Barrel`, () => {
			assert.match(barrel, new RegExp(`export\\s*\\{\\s*default\\s+as\\s+${n}\\s*\\}\\s*from\\s*['"]\\./${n}\\.svelte['"]`), `TDD RED: ${n} fehlt im Barrel atoms/index.ts`);
		});
	}
});
