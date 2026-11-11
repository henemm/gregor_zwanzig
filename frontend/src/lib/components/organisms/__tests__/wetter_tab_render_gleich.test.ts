// TDD RED — Issue #2913 (Einstellungen neu, Schritt 3: Bausteine), Teil 1: Pixelgleichheit.
// Spec: docs/specs/modules/feat_2913_s3_bausteine.md — AC-6, AC-7.
//
// Soll: Teil 1 ersetzt rohe Maße durch Tokens und verschiebt die Dateien, ändert aber NICHTS an dem,
// was der Browser bekommt.
//   - AC-6: Das vom Svelte-Compiler erzeugte CSS jeder der neun Komponenten ist nach Auflösung aller
//     var(--g-*) mit den Werten aus app.css (heller :root; rem mit 16px umgerechnet) zeichengleich zum
//     CSS des Referenzstands vor #2913. Ein gerundeter Wert (z. B. 12.5px -> 12px, 13px -> --g-text-sm
//     ist ok, 14px -> --g-text-sm nicht) oder ein falsch zugeordnetes Token fällt hier auf.
//   - AC-7: Der vom Svelte-Parser gelesene Markup-Baum (Elemente, Attribute, Texte, Blöcke) jeder
//     Komponente ist nach derselben Token-Auflösung gleich dem Referenzstand — keine neuen, keine
//     entfernten Elemente; gleicher Baum ⇒ gleiches Server-Render bei gleichen Props.
//
// Referenzstand: fixtures/wetter_tab_vor_2913/*.svelte.txt = die neun Dateien auf main e89f12fff
// (unverändert kopiert, Endung .txt, damit Wächter und svelte-check sie nicht als Komponenten lesen).
// Teil 2 ändert das Aussehen bewusst (Mockup); dieser Test gilt nur für Teil 1 und wird mit Teil 2
// samt Fixture-Ordner entfernt.
//
// Ersetzt die in der Spec genannte Playwright-Maßmessung (frontend/e2e/feat2913-teil1-masse.spec.ts):
// Gleiches CSS + gleicher Markup-Baum ist die Ursache gleicher berechneter Maße und deterministisch
// ohne laufenden Server prüfbar.
//
// RED heute: organisms/wetter-tab/*.svelte fehlen (Dateien liegen noch am alten Ort).
//
//   cd frontend && npm test -- src/lib/components/organisms/__tests__/wetter_tab_render_gleich.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { existsSync, readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { compile, parse } from 'svelte/compiler';

const HIER = dirname(fileURLToPath(import.meta.url));
const KOMP = join(HIER, '..', '..');
const NEU = join(KOMP, 'organisms', 'wetter-tab');
const REFERENZ = join(HIER, 'fixtures', 'wetter_tab_vor_2913');
const APP_CSS = readFileSync(join(KOMP, '..', '..', 'app.css'), 'utf8').replace(/\/\*[\s\S]*?\*\//g, '');

const NEUN = [
	'WetterTab',
	'VorlageKarte',
	'MetrikZeile',
	'GrenzenEditor',
	'WarnungenRadarKarte',
	'AmpelLeiste',
	'AlarmAbKopf',
	'NichtImBriefing',
	'AnpassenKarte'
];

/** Token-Werte des hellen Modus: erste Definition je Name in app.css (der helle :root steht vor dem Dark-Block). */
const TOKENS = new Map<string, string>();
for (const m of APP_CSS.matchAll(/(--g-[\w-]+)\s*:\s*([^;{}]+);/g)) if (!TOKENS.has(m[1])) TOKENS.set(m[1], m[2].trim());

function loeseAuf(text: string): string {
	let aus = text;
	for (let runde = 0; runde < 12; runde++) {
		const vorher = aus;
		aus = aus.replace(/var\(\s*(--[\w-]+)\s*(?:,\s*([^()]*(?:\([^()]*\))?[^()]*?))?\s*\)/g, (ganz, name: string, ersatz?: string) => {
			if (TOKENS.has(name)) return TOKENS.get(name)!;
			if (ersatz !== undefined) return ersatz.trim();
			return ganz;
		});
		if (aus === vorher) break;
	}
	return aus;
}

function normalisiere(text: string): string {
	return loeseAuf(text)
		.replace(/(-?\d*\.?\d+)rem\b/g, (_, z: string) => `${+(parseFloat(z) * 16).toFixed(4)}px`)
		.replace(/(-?\d*\.\d+)(px|em)\b/g, (_, z: string, e: string) => `${+parseFloat(z).toFixed(4)}${e}`)
		.replace(/\s+/g, ' ')
		.replace(/\s*([,:;{}()])\s*/g, '$1')
		.trim();
}

function kompiliertesCss(quelle: string, name: string): string {
	const r = compile(quelle, { filename: `${name}.svelte`, generate: 'server', css: 'external', cssHash: () => 'svelte-ref' });
	return normalisiere(r.css?.code ?? '');
}

const OHNE = new Set(['start', 'end', 'loc', 'metadata', 'name_loc']);
function markupBaum(quelle: string): string {
	const ast = parse(quelle, { modern: true }) as unknown as Record<string, unknown>;
	return normalisiere(JSON.stringify(ast.fragment, (k, v) => (OHNE.has(k) ? undefined : v)));
}

const referenz = (n: string) => readFileSync(join(REFERENZ, `${n}.svelte.txt`), 'utf8');
function neu(n: string): string {
	const p = join(NEU, `${n}.svelte`);
	assert.ok(existsSync(p), `TDD RED: organisms/wetter-tab/${n}.svelte fehlt`);
	return readFileSync(p, 'utf8');
}

describe('Referenzstand ist vollständig (Voraussetzung der Gleichheitsprüfung)', () => {
	for (const n of NEUN) {
		test(`${n}: Referenz vorhanden und mit Stil`, () => {
			assert.ok(existsSync(join(REFERENZ, `${n}.svelte.txt`)), `Referenz ${n} fehlt`);
			assert.ok(kompiliertesCss(referenz(n), n).length > 0, `Referenz ${n} ohne CSS`);
		});
	}
});

describe('AC-6: kompiliertes CSS nach Token-Auflösung gleich dem Stand vor #2913', () => {
	for (const n of NEUN) {
		test(`${n}: CSS gleich`, () => {
			assert.equal(kompiliertesCss(neu(n), n), kompiliertesCss(referenz(n), n));
		});
	}
});

describe('AC-7: Markup-Baum gleich dem Stand vor #2913 (keine neuen/entfernten Elemente)', () => {
	for (const n of NEUN) {
		test(`${n}: Markup gleich`, () => {
			assert.equal(markupBaum(neu(n)), markupBaum(referenz(n)));
		});
	}
});

describe('Selbstprüfung der Auflösung (die Messung unterscheidet wirklich)', () => {
	test('ein passendes Token wird gleich, ein gerundetes nicht', () => {
		assert.equal(normalisiere('a{gap:var(--g-s-3)}'), normalisiere('a{gap:12px}'));
		assert.notEqual(normalisiere('a{font-size:var(--g-text-sm)}'), normalisiere('a{font-size:12.5px}'));
		assert.equal(normalisiere('a{border-radius:var(--g-r-2)}'), normalisiere('a{border-radius:4px}'));
	});
});
