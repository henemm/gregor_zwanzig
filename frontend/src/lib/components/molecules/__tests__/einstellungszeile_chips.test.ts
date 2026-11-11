// TDD RED — Issue #2913 (Einstellungen neu, Schritt 3: Bausteine), Teil 2.
// Spec: docs/specs/modules/feat_2913_s3_bausteine.md — AC-15, Klarstellung K-2.
//
// Vertrag (hier festgelegt, /50 baut danach; Mockup `.lrow` bzw. `.more`/`.chip`):
//   molecules/Einstellungszeile.svelte  Props: titel: string, hinweis?: string, testid?: string,
//                                       children?: Snippet (das Bedienelement).
//     -> Wurzel data-slot="einstellungszeile" (data-testid=testid), Titel-Text, Hinweis in
//        data-slot="einstellungszeile-hinweis" NUR wenn gesetzt, Bedienelement in
//        data-slot="einstellungszeile-bedienung".
//   molecules/ChipLeiste.svelte         Props: eintraege: { id: string; label: string; testid?: string }[],
//                                       onWahl: (id: string) => void.
//     -> Wurzel data-slot="chip-leiste", je Eintrag genau ein Chip aus dem Atom Btn
//        (data-slot="btn", data-testid=testid, Text=label).
//   Beide ohne rohe Controls (<button>/<input>/<select>/<textarea>) und im Barrel molecules/index.ts.
//
// Verhalten per Server-Render (svelte/server); Quell-/Barrel-Regeln als doc-compliance-test.
//
// RED heute: beide Moleküle fehlen.
//
//   cd frontend && npm test -- src/lib/components/molecules/__tests__/einstellungszeile_chips.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { register } from 'node:module';
import { existsSync, readFileSync } from 'node:fs';
import { fileURLToPath, pathToFileURL } from 'node:url';
import path from 'node:path';
import { parse } from 'svelte/compiler';

const HERE = path.dirname(fileURLToPath(import.meta.url));
// __tests__ -> molecules -> components -> lib -> src -> frontend
const FRONTEND = path.resolve(HERE, '../../../../..');
const MOLECULES = path.resolve(HERE, '..');

register(pathToFileURL(path.join(FRONTEND, 'test-svelte-ssr-hooks.mjs')).href, pathToFileURL(FRONTEND + '/').href);
const { render } = await import('svelte/server');
const { createRawSnippet } = await import('svelte');

const ZEILE = path.join(MOLECULES, 'Einstellungszeile.svelte');
const CHIPS = path.join(MOLECULES, 'ChipLeiste.svelte');

async function lade(datei: string, name: string): Promise<any> {
	assert.ok(existsSync(datei), `TDD RED: molecules/${name}.svelte fehlt`);
	return (await import(pathToFileURL(datei).href)).default;
}
const html = (k: any, props: Record<string, unknown>) => render(k, { props }).body.replace(/<!--[\s\S]*?-->/g, '');
const text = (h: string) => h.replace(/<[^>]*>/g, ' ').replace(/\s+/g, ' ').trim();

const ROH = new Set(['button', 'input', 'select', 'textarea']);
/** Rohe Controls im Markup (Svelte-AST, Kommentare zählen nicht). */
function roheControls(quelle: string): string[] {
	const aus: string[] = [];
	const lauf = (x: unknown) => {
		if (Array.isArray(x)) return x.forEach(lauf);
		if (!x || typeof x !== 'object') return;
		const n = x as Record<string, unknown>;
		if (n.type === 'RegularElement' && ROH.has(String(n.name))) aus.push(String(n.name));
		for (const [k, v] of Object.entries(n)) if (k !== 'parent') lauf(v);
	};
	lauf((parse(quelle, { modern: true }) as unknown as Record<string, unknown>).fragment);
	return aus;
}

/** Inneres HTML des Elements mit `data-slot="<slot>"` (ausbalanciert über den Tag-Namen). */
function slotInhalt(h: string, slot: string): string | null {
	const m = new RegExp(`<([a-z][a-z0-9]*)\\b[^>]*data-slot="${slot}"[^>]*>`).exec(h);
	if (!m) return null;
	const tag = m[1];
	let tiefe = 1;
	const re = new RegExp(`<${tag}\\b[^>]*>|</${tag}>`, 'g');
	re.lastIndex = m.index + m[0].length;
	for (let t = re.exec(h); t; t = re.exec(h)) {
		if (t[0].startsWith('</')) tiefe--;
		else if (!t[0].endsWith('/>')) tiefe++;
		if (tiefe === 0) return h.slice(m.index + m[0].length, t.index);
	}
	return null;
}

const probe = () => createRawSnippet(() => ({ render: () => '<span data-probe="bedienung">Probe-Schalter</span>' }));

describe('AC-15: molecules/Einstellungszeile', () => {
	test('SSR: Titel, Hinweis und Bedienelement im Bereich einstellungszeile-bedienung', async () => {
		const Z = await lade(ZEILE, 'Einstellungszeile');
		const h = html(Z, { titel: 'Amtliche Warnungen', hinweis: 'Meldet Warnungen des Wetterdienstes', testid: 'zeile-probe', children: probe() });
		assert.match(h, /data-slot="einstellungszeile"/);
		assert.match(h, /data-testid="zeile-probe"/);
		assert.ok(text(h).includes('Amtliche Warnungen'), 'Titel fehlt');
		const hinweis = slotInhalt(h, 'einstellungszeile-hinweis');
		assert.ok(hinweis !== null, 'kein Hinweis-Bereich trotz hinweis');
		assert.equal(text(hinweis!), 'Meldet Warnungen des Wetterdienstes');
		const bedienung = slotInhalt(h, 'einstellungszeile-bedienung');
		assert.ok(bedienung !== null, 'kein Bereich data-slot="einstellungszeile-bedienung"');
		assert.match(bedienung!, /data-probe="bedienung"/, 'Bedienelement nicht im Bedien-Bereich');
	});
	test('SSR ohne hinweis: kein Hinweis-Element', async () => {
		const Z = await lade(ZEILE, 'Einstellungszeile');
		const h = html(Z, { titel: 'Radar-Regen', children: probe() });
		assert.ok(text(h).includes('Radar-Regen'));
		assert.doesNotMatch(h, /einstellungszeile-hinweis/);
		assert.match(slotInhalt(h, 'einstellungszeile-bedienung') ?? '', /data-probe="bedienung"/);
	});
	test('Quelle ohne rohe Controls', () => {
		assert.ok(existsSync(ZEILE), 'TDD RED: molecules/Einstellungszeile.svelte fehlt');
		assert.deepEqual(roheControls(readFileSync(ZEILE, 'utf8')), []);
	});
});

describe('AC-15/K-2: molecules/ChipLeiste', () => {
	const EINTRAEGE = [
		{ id: 'wind', label: '+ Wind', testid: 'chip-wind' },
		{ id: 'gust', label: '+ Böen', testid: 'chip-gust' },
		{ id: 'uv', label: '+ UV-Index', testid: 'chip-uv' }
	];
	test('SSR: je Eintrag genau ein Chip aus Btn mit Text und Testid', async () => {
		const C = await lade(CHIPS, 'ChipLeiste');
		const h = html(C, { eintraege: EINTRAEGE, onWahl: () => {} });
		assert.match(h, /data-slot="chip-leiste"/);
		const chips = [...h.matchAll(/<button\b[^>]*data-slot="btn"[^>]*>([\s\S]*?)<\/button>/g)];
		assert.equal(chips.length, EINTRAEGE.length, `erwartet ${EINTRAEGE.length} Btn-Chips, gefunden ${chips.length}`);
		EINTRAEGE.forEach((e, i) => {
			assert.match(chips[i][0], new RegExp(`data-testid="${e.testid}"`));
			assert.equal(text(chips[i][1]), e.label);
		});
	});
	test('SSR: leere Liste ergibt keinen Chip', async () => {
		const C = await lade(CHIPS, 'ChipLeiste');
		assert.doesNotMatch(html(C, { eintraege: [], onWahl: () => {} }), /data-slot="btn"/);
	});
	test('Quelle ohne rohe Controls, Chip aus dem Atom Btn', () => {
		assert.ok(existsSync(CHIPS), 'TDD RED: molecules/ChipLeiste.svelte fehlt');
		const q = readFileSync(CHIPS, 'utf8');
		assert.deepEqual(roheControls(q), []);
		assert.match(q, /import\s*\{[^}]*\bBtn\b[^}]*\}\s*from\s*['"]\$lib\/components\/atoms['"]|import\s+Btn\s+from\s*['"][^'"]*atoms\/Btn\.svelte['"]/, 'ChipLeiste importiert Btn nicht aus atoms');
	});
});

describe('AC-15: Barrel molecules/index.ts', () => {
	const barrel = readFileSync(path.join(MOLECULES, 'index.ts'), 'utf8').replace(/\/\/.*$/gm, '');
	for (const n of ['Einstellungszeile', 'ChipLeiste']) {
		test(`${n} im Barrel`, () => {
			assert.match(barrel, new RegExp(`export\\s*\\{\\s*default\\s+as\\s+${n}\\s*\\}\\s*from\\s*['"]\\./${n}\\.svelte['"]`), `TDD RED: ${n} fehlt im Barrel molecules/index.ts`);
		});
	}
});
