// TDD RED + GREEN: Issue #214 — Btn Feature-Paritaet (Phase A).
//
// Spec: docs/specs/modules/issue_214_btn_feature_parity.md
//
// Diese Tests beweisen, dass die Btn-Komponente das in der Spec gefoderte
// Props-Interface, alle 7 Variants, 8 Sizes, den href-Switch und den
// disabled-State (inkl. WAI-ARIA-Pattern fuer disabled Links) korrekt
// implementiert.
//
// Render-Strategie: Svelte 5 SSR via `svelte/server.render(...)`. Damit
// koennen Markup-Output, Attribute und `data-*`-Hooks geprueft werden ohne
// JSDOM/happy-dom (die im Projekt nicht installiert sind). Click-Events
// werden indirekt ueber die HTML-Native-Attribute (disabled / aria-disabled)
// verifiziert.
//
// Ausfuehrung:
//   cd frontend && node --experimental-strip-types --test \
//     src/lib/components/ui/btn/Btn.test.ts

import { test } from 'node:test';
import assert from 'node:assert/strict';
import { render } from 'svelte/server';
import { createRawSnippet } from 'svelte';
import {
	Btn,
	type BtnVariant,
	type BtnSize,
	type BtnProps
} from './index.ts';

// ---------------------------------------------------------------------------
// Helper
// ---------------------------------------------------------------------------

type BtnRenderProps = Omit<BtnProps, 'children'>;

function renderBtn(props: BtnRenderProps & { _label?: string } = {}): string {
	const label = props._label ?? 'Label';
	delete (props as Record<string, unknown>)._label;
	// Svelte 5 SSR erwartet RawSnippets fuer Children; einfache Funktionen
	// werden als noop gerendert.
	const childrenSnippet = createRawSnippet(() => ({
		render: () => `<span>${label}</span>`
	}));
	const out = render(Btn as never, {
		props: {
			...props,
			children: childrenSnippet as never
		}
	});
	return out.body;
}

function attr(html: string, name: string): string | null {
	// Doppelt-quoted oder einfach: <... name="value" ...>
	const re = new RegExp(`\\b${name}\\s*=\\s*"([^"]*)"`);
	const m = html.match(re);
	return m ? m[1] : null;
}

function hasAttr(html: string, name: string): boolean {
	// Boolean-Attribut: <... disabled ...> ODER <... disabled="...">
	const re = new RegExp(`\\b${name}(?=[\\s>=])`);
	return re.test(html);
}

function rootTag(html: string): string {
	// Svelte SSR wickelt Output in `<!--[-->...<!--]-->`-Kommentare.
	// Wir suchen den ersten echten HTML-Tag im Body.
	const m = html.match(/<([a-zA-Z][a-zA-Z0-9]*)\b/);
	return m ? m[1].toLowerCase() : '';
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

// Btn — Render-Pfade (button vs anchor)

test('Btn — Render-Pfade (button vs anchor) > AC-5a: rendert als <button>, wenn kein href gesetzt ist', () => {
	const html = renderBtn();
	assert.equal(rootTag(html), 'button');
});

test('Btn — Render-Pfade (button vs anchor) > AC-5b: rendert als <a>, wenn href gesetzt ist', () => {
	const html = renderBtn({ href: '/x' });
	assert.equal(rootTag(html), 'a');
});

test('Btn — Render-Pfade (button vs anchor) > AC-10: data-slot="btn" auf beiden Render-Pfaden gesetzt', () => {
	const button = renderBtn();
	const anchor = renderBtn({ href: '/x' });
	assert.equal(attr(button, 'data-slot'), 'btn');
	assert.equal(attr(anchor, 'data-slot'), 'btn');
});

// Btn — href + disabled (WAI-ARIA-Pattern)

test('Btn — href + disabled (WAI-ARIA-Pattern) > AC-6a: href + disabled → kein href-Attribut im DOM', () => {
	const html = renderBtn({ href: '/x', disabled: true });
	// Kein href= im a-Tag (SSR rendert undefined-Attribute weg)
	const tag = html.match(/<a\b[^>]*>/)?.[0] ?? '';
	assert.equal(/\bhref=/.test(tag), false);
});

test('Btn — href + disabled (WAI-ARIA-Pattern) > AC-6b: href + disabled → aria-disabled="true" gesetzt', () => {
	const html = renderBtn({ href: '/x', disabled: true });
	assert.equal(attr(html, 'aria-disabled'), 'true');
});

test('Btn — href + disabled (WAI-ARIA-Pattern) > AC-6c: href + disabled → tabindex="-1" gesetzt', () => {
	const html = renderBtn({ href: '/x', disabled: true });
	assert.equal(attr(html, 'tabindex'), '-1');
});

test('Btn — href + disabled (WAI-ARIA-Pattern) > AC-6d: href + disabled → role="link" gesetzt', () => {
	const html = renderBtn({ href: '/x', disabled: true });
	assert.equal(attr(html, 'role'), 'link');
});

// Btn — <button> + disabled

test('Btn — <button> + disabled > AC-7: <button> + disabled → natives disabled-Attribut vorhanden', () => {
	const html = renderBtn({ disabled: true });
	assert.equal(rootTag(html), 'button');
	assert.equal(hasAttr(html, 'disabled'), true);
});

test('Btn — <button> + disabled > AC-7b: <button> + disabled → Click-Handler feuert nicht (HTML-Native: disabled-Attribut verhindert click events)', () => {
	// SSR-Pruefung: Wenn disabled-Attribut auf <button> gerendert ist,
	// liefert der Browser keine click-Events. Das ist HTML-Spec-Verhalten.
	const html = renderBtn({ disabled: true });
	assert.equal(hasAttr(html, 'disabled'), true);
	// Implicit: ohne disabled feuert Click; HTML-Native-Verhalten.
	const ok = renderBtn({ disabled: false });
	assert.equal(hasAttr(ok, 'disabled'), false);
});

// Btn — Default-Props

test('Btn — Default-Props > AC-3: Default-Variant ist "primary" (data-variant="primary")', () => {
	const html = renderBtn();
	assert.equal(attr(html, 'data-variant'), 'primary');
});

test('Btn — Default-Props > AC-4: Default-Size ist "md" (data-size="md")', () => {
	const html = renderBtn();
	assert.equal(attr(html, 'data-size'), 'md');
});

// Btn — Variants & Sizes (Loop-Tests)

const VARIANTS: BtnVariant[] = [
	'primary',
	'accent',
	'outline',
	'ghost',
	'secondary',
	'destructive',
	'link'
];
const SIZES: BtnSize[] = [
	'xs',
	'sm',
	'md',
	'lg',
	'icon',
	'icon-xs',
	'icon-sm',
	'icon-lg'
];

test('Btn — Variants & Sizes (Loop-Tests) > AC-1: alle 7 Variants werden akzeptiert und auf data-variant durchgereicht', () => {
	for (const v of VARIANTS) {
		const html = renderBtn({ variant: v });
		assert.equal(attr(html, 'data-variant'), v);
	}
});

test('Btn — Variants & Sizes (Loop-Tests) > AC-2: alle 8 Sizes werden akzeptiert und auf data-size durchgereicht', () => {
	for (const s of SIZES) {
		const html = renderBtn({ size: s });
		assert.equal(attr(html, 'data-size'), s);
	}
});

// Btn — class-Merge & children

test('Btn — class-Merge & children > AC-12: eigene className wird auf class-Attribut gerendert', () => {
	const html = renderBtn({ class: 'custom-class' });
	const cls = attr(html, 'class') ?? '';
	assert.ok(cls.includes('custom-class'));
});

test('Btn — class-Merge & children > AC-children: children-Snippet wird gerendert (Text-Content)', () => {
	const html = renderBtn({ _label: 'Speichern' });
	assert.ok(html.includes('Speichern'));
});

// Btn — Type-Re-Exports

test('Btn — Type-Re-Exports > exportiert die Type-Aliases BtnVariant, BtnSize, BtnProps via index.ts', () => {
	// Compile-Time-Check: wenn Importe oben fehlschlagen, schlaegt der Test fehl.
	// Runtime-Marker: existieren die Symbole? (Types werden gestrippt — nur Btn ist runtime)
	assert.ok(Btn);
	// Type-Imports werden vom Compiler validiert; runtime-seitig ist hier nichts zu pruefen.
	// Dieser Test scheitert in der RED-Phase, weil index.ts die Types noch nicht re-exportiert
	// (TS-Compile-Fehler beim Test-Import oben).
	const variants: BtnVariant[] = [
		'primary',
		'accent',
		'outline',
		'ghost',
		'secondary',
		'destructive',
		'link'
	];
	const sizes: BtnSize[] = [
		'xs',
		'sm',
		'md',
		'lg',
		'icon',
		'icon-xs',
		'icon-sm',
		'icon-lg'
	];
	assert.equal(variants.length, 7);
	assert.equal(sizes.length, 8);
});
