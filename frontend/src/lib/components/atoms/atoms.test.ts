// TDD RED: Issue #371 — Atoms-Schicht lib/components/atoms/ (Bridge-Ansatz)
//
// Spec: docs/specs/modules/issue_371_atoms.md
// Vorlage: docs/design-requests/issue_15_atomic_design/spec/atoms.jsx
//
// Source-Inspection-Test (kein Render, keine Mocks): prueft Datei-Existenz,
// index.ts-Re-Exporte und Schluessel-Inhalte der neuen Atome.
//
// RED vor Implementierung: atoms/-Dateien fehlen → Asserts schlagen fehl.
//
// Ausfuehrung:
//   cd frontend && node --experimental-strip-types --test src/lib/components/atoms/atoms.test.ts

import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync, existsSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const here = dirname(fileURLToPath(import.meta.url));
const read = (f: string) => readFileSync(join(here, f), 'utf-8');
const has = (f: string) => existsSync(join(here, f));

const ALL_14 = [
	'Eyebrow', 'Pill', 'Card', 'Btn', 'Input', 'Switch', 'Dot',
	'WIcon', 'ElevSparkline', 'SectionH', 'AvatarStack', 'TopoBg', 'KV', 'Segmented',
];

test('#371/#403 AC-1: alle 14 Atom-Dateien existieren in atoms/', () => {
	for (const name of ALL_14) {
		assert.ok(has(`${name}.svelte`), `atoms/${name}.svelte fehlt`);
	}
	assert.ok(has('index.ts'), 'atoms/index.ts fehlt');
});

test('#371/#403 AC-1: index.ts re-exportiert alle 14 Atome', () => {
	const idx = read('index.ts');
	for (const name of ALL_14) {
		assert.ok(new RegExp(`\\b${name}\\b`).test(idx), `index.ts exportiert ${name} nicht`);
	}
});

test('#371 AC-2: Switch — role=switch, aria-checked, data-testid, 5 tones, lg≥44px', () => {
	const sw = read('Switch.svelte');
	assert.ok(/role=["']switch["']/.test(sw), 'Switch role="switch" fehlt');
	assert.ok(/aria-checked/.test(sw), 'Switch aria-checked fehlt');
	assert.ok(/data-testid=["']switch["']/.test(sw), 'Switch data-testid="switch" fehlt');
	for (const tone of ['good', 'accent', 'info', 'warn', 'bad']) {
		assert.ok(sw.includes(tone), `Switch tone "${tone}" fehlt`);
	}
	// lg-Groesse trifft 44px Touch-Mindestmass
	assert.ok(/44/.test(sw), 'Switch lg-Groesse (44px) fehlt');
});

test('#371 AC-3: Input size=lg → 16px (kein iOS-Zoom), data-testid, data-error', () => {
	// Input ist Compound-Primitive (ui/input); atoms/Input wrappt es.
	// 16px-Garantie + Testhooks muessen erreichbar sein (Wrapper oder ui/input).
	const candidates = [
		join(here, 'Input.svelte'),
		join(here, '../ui/input/input.svelte'),
	];
	const found = candidates.filter(existsSync).map(p => readFileSync(p, 'utf-8')).join('\n');
	assert.ok(found.length > 0, 'Input-Quelle nicht gefunden');
	assert.ok(/16px|font-size:\s*16|fs:\s*16/.test(found), 'Input lg 16px (iOS-Zoom-Schutz) fehlt');
	assert.ok(/data-testid=["']input["']/.test(found), 'Input data-testid="input" fehlt');
	assert.ok(/data-error/.test(found), 'Input data-error fehlt');
});

test('#371 AC-6: neue Atome SectionH / AvatarStack / KV vorhanden mit Kern-Props', () => {
	const sh = read('SectionH.svelte');
	for (const p of ['eyebrow', 'title', 'kicker', 'right']) {
		assert.ok(sh.includes(p), `SectionH Prop "${p}" fehlt`);
	}
	const av = read('AvatarStack.svelte');
	assert.ok(/users/.test(av), 'AvatarStack Prop "users" fehlt');
	const kv = read('KV.svelte');
	assert.ok(/label/.test(kv) && /value/.test(kv), 'KV Props label/value fehlen');
});

test('#371 AC-5: ui/Pill ghost-Tone + Sandbox-Aliase, ui/Btn quiet-Variante (additiv)', () => {
	const css = readFileSync(join(here, '../../../app.css'), 'utf-8');
	const pill = readFileSync(join(here, '../ui/pill/Pill.svelte'), 'utf-8');
	const btn = readFileSync(join(here, '../ui/btn/Btn.svelte'), 'utf-8');
	// Pill ghost-Tone in CSS + Sandbox-Alias-Mapping in der Komponente
	assert.ok(/\[data-slot="pill"\]\[data-tone="ghost"\]/.test(css), 'app.css: pill ghost-Tone fehlt');
	assert.ok(/neutral/.test(pill) && /good/.test(pill) && /warn/.test(pill) && /bad/.test(pill), 'Pill Sandbox-Tone-Aliase fehlen');
	// Btn quiet-Variante in CSS + Type
	assert.ok(/\[data-slot="btn"\]\[data-variant="quiet"\]/.test(css), 'app.css: btn quiet-Variante fehlt');
	assert.ok(/quiet/.test(btn), 'Btn quiet im Variant-Type fehlt');
	// Bestehende Tone-/Variant-Namen unveraendert (backward-compat)
	assert.ok(/default/.test(pill) && /accent/.test(pill), 'Pill bestehende Tones gebrochen');
	assert.ok(/primary/.test(btn) && /ghost/.test(btn), 'Btn bestehende Variants gebrochen');
});

test('#371 AC-5: ui/Eyebrow color hat KEINEN Token-Default (kein Inline-Override bestehender Aufrufer)', () => {
	const eb = readFileSync(join(here, '../ui/eyebrow/Eyebrow.svelte'), 'utf-8');
	// F001-Regression: color = 'var(--g-ink-3)' als Default würde via inline style
	// die CSS-Regel (--g-ink-faint) fuer ALLE bestehenden Eyebrows ueberschreiben.
	assert.ok(!/color\s*=\s*['"]var\(--g-ink-3\)['"]/.test(eb), 'Eyebrow color-Default ueberschreibt bestehende Aufrufer (F001)');
	assert.ok(/color\s*=\s*undefined/.test(eb), 'Eyebrow color sollte Default undefined sein (CSS-Regel gewinnt)');
});

test('#371 AC-4: Atome SSR-fest — kein ungeschuetzter window.*-Zugriff', () => {
	for (const name of ['Switch', 'SectionH', 'AvatarStack', 'KV']) {
		if (!has(`${name}.svelte`)) continue;
		const src = read(`${name}.svelte`);
		// window.* nur erlaubt innerhalb eines browser/onMount-Guards
		const hasRawWindow = /\bwindow\./.test(src);
		const hasGuard = /browser|onMount/.test(src);
		assert.ok(!hasRawWindow || hasGuard, `${name}: ungeschuetzter window.*-Zugriff (nicht SSR-fest)`);
	}
});

// ── Bug #420 — atoms/Card.svelte: padding + accent Props ─────────────────────

test('#420 AC-1/AC-5/AC-7: Card deklariert padding+accent als explizite Props, kein ui/card-Import', () => {
	const card = read('Card.svelte');
	// AC-5: padding-Prop mit Default 20
	assert.ok(/padding.*=.*20|padding\s*\?\s*20/.test(card), 'Card: padding-Prop mit Default 20 fehlt');
	// AC-7: accent-Prop mit Default false
	assert.ok(/accent.*=.*false|accent\s*\?\s*false/.test(card), 'Card: accent-Prop mit Default false fehlt');
	// AC-7: keine Delegation an ui/card mehr
	assert.ok(!/import.*ui\/card/.test(card), 'Card delegiert noch an ui/card — eigenstaendige Implementierung fehlt (AC-7)');
});

test('#420 AC-3/AC-4: Card border-left nutzt --g-accent (accent=true) vs --g-rule (accent=false)', () => {
	const card = read('Card.svelte');
	assert.ok(/--g-accent/.test(card), 'Card: --g-accent fuer accent-border fehlt (AC-3)');
	assert.ok(/--g-rule/.test(card), 'Card: --g-rule fuer Standard-border fehlt (AC-4)');
	assert.ok(/3px\s+solid/.test(card), 'Card: accent-border-Breite 3px solid fehlt (AC-3)');
});

test('#420 AC-1/AC-2: Card setzt padding als Inline-Style (kein Tailwind py-*)', () => {
	const card = read('Card.svelte');
	// Inline-Style-Direktive oder style-Binding fuer padding
	assert.ok(/style:padding|style="[^"]*padding/.test(card), 'Card: padding als Inline-Style fehlt (AC-1/AC-2)');
	// Kein hardcodiertes Tailwind py-4 mehr auf dem Root-Element
	assert.ok(!/\bpy-4\b/.test(card), 'Card: hardcodiertes Tailwind py-4 noch vorhanden (blockiert padding=0, AC-2)');
});

test('#420 AC-6: +page.svelte Workaround entfernt — kein !p-0 und kein inline border-left auf Card', () => {
	const page = readFileSync(join(here, '../../../routes/+page.svelte'), 'utf-8');
	assert.ok(!/<Card[^>]*!p-0/.test(page), '+page.svelte: !p-0-Workaround auf Card noch vorhanden (AC-6)');
	assert.ok(!/<Card[^>]*border-left:\s*3px\s+solid\s+var\(--g-accent\)/.test(page),
		'+page.svelte: border-left-Workaround auf Card noch vorhanden (AC-6)');
});
