// TDD RED: Issue #374 — Showcase-Route /_design-system
//
// Spec: docs/specs/modules/issue_374_showcase.md
// Vorlage: docs/design-requests/issue_15_atomic_design/spec/screen-design-system.jsx
//
// Source-Inspection-Test (kein Render, keine Mocks): Route existiert, importiert
// alle vier Schichten, zeigt die 6 Sektionen, nutzt MobileShell, README-Abschnitt.
//
// RED vor Implementierung: +page.svelte fehlt → Asserts schlagen fehl.
//
// Ausfuehrung:
//   cd frontend && node --experimental-strip-types --test src/routes/_design-system/showcase.test.ts

import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync, existsSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';
import { parse } from 'svelte/compiler';

const here = dirname(fileURLToPath(import.meta.url));
const page = join(here, '+page.svelte');
const readPage = () => readFileSync(page, 'utf-8');

test('#374 AC-1: Route +page.svelte existiert + importiert alle 4 Schichten', () => {
	assert.ok(existsSync(page), 'routes/_design-system/+page.svelte fehlt');
	const src = readPage();
	assert.ok(/\$lib\/brand/.test(src), 'Import aus $lib/brand fehlt');
	assert.ok(/\$lib\/components\/atoms/.test(src), 'Import aus $lib/components/atoms fehlt');
	assert.ok(/\$lib\/components\/molecules/.test(src), 'Import aus $lib/components/molecules fehlt');
	assert.ok(/\$lib\/components\/mobile/.test(src), 'Import aus $lib/components/mobile fehlt');
});

test('#374 AC-2: 6 Sektionen Brand/Typografie/Farben/Bausteine/Molecules/Voice', () => {
	const src = readPage();
	for (const s of ['Brand', 'Typografie', 'Farben', 'Bausteine', 'Molecules', 'Voice']) {
		assert.ok(src.includes(s), `Sektion "${s}" fehlt`);
	}
	// Organisms/Templates NICHT in #374 (Out of Scope, Epic #368)
	assert.ok(!/Section[^>]*Organisms/.test(src) && !/title=["']Organisms["']/.test(src), 'Organisms-Sektion gehört NICHT in #374');
});

test('#374 AC-2: gezeigte Pflicht-Varianten (Switch-Tones, Btn quiet, Pill ghost, Stat, AlertRow)', () => {
	const src = readPage();
	assert.ok(/Switch/.test(src) && /Btn/.test(src) && /Pill/.test(src), 'Atom-Varianten fehlen');
	assert.ok(/Stat/.test(src) && /AlertRow/.test(src) && /ChannelRow/.test(src), 'Molecule-Varianten fehlen');
});

test('#374 AC-3: Mobile-Demo nutzt MobileShell + Mobile-Primitive', () => {
	const src = readPage();
	assert.ok(/MobileShell/.test(src), 'MobileShell in Mobile-Demo fehlt');
	assert.ok(/MBtn|MSwitch|Sheet|Toast/.test(src), 'Mobile-Primitive in Demo fehlen');
});

test('#374 AC-4: Token-basiert (kein nackter Hex außer in Farben-Swatch-Labels)', () => {
	const src = readPage();
	assert.ok(/var\(--g-/.test(src), 'Route nutzt keine --g-*-Tokens');
});

test('#374 AC-5: Frontend-Doku "Atomic-Design-Disziplin"', () => {
	const candidates = [
		join(here, '../../../README.md'),
		join(here, '../../../CLAUDE.md'),
	];
	const found = candidates.filter(existsSync).map(p => readFileSync(p, 'utf-8')).join('\n');
	assert.ok(/Atomic-Design-Disziplin/.test(found), 'README/CLAUDE.md: Abschnitt "Atomic-Design-Disziplin" fehlt');
});

// ─── Issue #2913 Teil 2 (Workflow feature-2913-teil2), Spec feat_2913_s3_bausteine.md AC-20 ───────────────
// Soll: Der Showcase zeigt jedes neue Atom bzw. jede neue Atom-Variante — Skelett, Input mit Ampel-Unterkante
// (Prop `ampel`), Segmented mit Farbpunkt (Option/Item `farbe`) — und die vier Ampel-Tokens --g-ampel-*.
// Messweise: Svelte-AST der Seite (Importe aus dem Atom-Barrel, Komponenten-Verwendung mit Prop):
// doc-compliance-test
// RED heute: weder Skelett noch Segmented noch ampel/farbe noch --g-ampel-* im Showcase.

type K2913 = Record<string, any>;
function ast2913(): K2913 {
	return parse(readPage(), { modern: true }) as unknown as K2913;
}
function atomImporte2913(): string[] {
	const namen: string[] = [];
	for (const s of (ast2913().instance?.content?.body ?? []) as K2913[]) {
		if (s.type === 'ImportDeclaration' && /^\$lib\/components\/atoms(\/|$)/.test(String(s.source.value))) {
			for (const sp of s.specifiers as K2913[]) namen.push(String(sp.local?.name));
		}
	}
	return namen;
}
/** Alle Verwendungen <Name …> im Markup. */
function komponenten2913(name: string): K2913[] {
	const aus: K2913[] = [];
	const lauf = (x: unknown) => {
		if (Array.isArray(x)) return x.forEach(lauf);
		if (!x || typeof x !== 'object') return;
		const n = x as K2913;
		if (n.type === 'Component' && n.name === name) aus.push(n);
		for (const [k, v] of Object.entries(n)) if (k !== 'parent') lauf(v);
	};
	lauf(ast2913().fragment);
	return aus;
}
const attributQuelle2913 = (n: K2913, attr: string): string | null => {
	const a = (n.attributes as K2913[]).find((x) => x.type === 'Attribute' && x.name === attr);
	return a ? readPage().slice(a.start, a.end) : null;
};

test('#2913 AC-20: Skelett aus dem Atom-Barrel importiert und gezeigt', () => {
	assert.ok(atomImporte2913().includes('Skelett'), 'TDD RED: Showcase importiert Skelett nicht aus $lib/components/atoms');
	assert.ok(komponenten2913('Skelett').length > 0, 'TDD RED: Showcase zeigt <Skelett> nicht');
});

test('#2913 AC-20: Input mit Ampel-Unterkante (alle vier Farben)', () => {
	const werte = komponenten2913('Input')
		.map((n) => attributQuelle2913(n, 'ampel'))
		.filter((q): q is string => q !== null)
		.join(' ');
	const fehlt = ['green', 'yellow', 'orange', 'red'].filter((f) => !werte.includes(f));
	assert.deepEqual(fehlt, [], `TDD RED: <Input ampel=…> fehlt im Showcase für: ${fehlt.join(', ')}`);
});

test('#2913 AC-20: Segmented mit Farbpunkt (farbe in items/options)', () => {
	assert.ok(atomImporte2913().includes('Segmented'), 'TDD RED: Showcase importiert Segmented nicht aus $lib/components/atoms');
	const seg = komponenten2913('Segmented');
	assert.ok(seg.length > 0, 'TDD RED: Showcase zeigt <Segmented> nicht');
	const mitFarbe = seg.some((n) => /\bfarbe\b/.test(`${attributQuelle2913(n, 'items') ?? ''} ${attributQuelle2913(n, 'options') ?? ''}`));
	const lokaleListe = /\bfarbe\s*:/.test(readPage());
	assert.ok(mitFarbe || lokaleListe, 'TDD RED: kein Segmented mit Option/Item `farbe` im Showcase');
});

test('#2913 AC-20: die vier Ampel-Tokens --g-ampel-* sind im Showcase zu sehen', () => {
	const src = readPage();
	const fehlt = ['gruen', 'gelb', 'orange', 'rot'].filter((t) => !src.includes(`--g-ampel-${t}`));
	assert.deepEqual(fehlt, [], `TDD RED: Showcase ohne --g-ampel-${fehlt.join('/')}`);
});
