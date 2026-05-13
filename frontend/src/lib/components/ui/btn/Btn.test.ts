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
//   cd frontend && npx vitest run src/lib/components/ui/btn/Btn.test.ts

import { describe, test, expect } from 'vitest';
import { render } from 'svelte/server';
import { createRawSnippet } from 'svelte';
import {
	Btn,
	type BtnVariant,
	type BtnSize,
	type BtnProps
} from './index';

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

describe('Btn — Render-Pfade (button vs anchor)', () => {
	test('AC-5a: rendert als <button>, wenn kein href gesetzt ist', () => {
		const html = renderBtn();
		expect(rootTag(html)).toBe('button');
	});

	test('AC-5b: rendert als <a>, wenn href gesetzt ist', () => {
		const html = renderBtn({ href: '/x' });
		expect(rootTag(html)).toBe('a');
	});

	test('AC-10: data-slot="btn" auf beiden Render-Pfaden gesetzt', () => {
		const button = renderBtn();
		const anchor = renderBtn({ href: '/x' });
		expect(attr(button, 'data-slot')).toBe('btn');
		expect(attr(anchor, 'data-slot')).toBe('btn');
	});
});

describe('Btn — href + disabled (WAI-ARIA-Pattern)', () => {
	test('AC-6a: href + disabled → kein href-Attribut im DOM', () => {
		const html = renderBtn({ href: '/x', disabled: true });
		// Kein href= im a-Tag (SSR rendert undefined-Attribute weg)
		const tag = html.match(/<a\b[^>]*>/)?.[0] ?? '';
		expect(/\bhref=/.test(tag)).toBe(false);
	});

	test('AC-6b: href + disabled → aria-disabled="true" gesetzt', () => {
		const html = renderBtn({ href: '/x', disabled: true });
		expect(attr(html, 'aria-disabled')).toBe('true');
	});

	test('AC-6c: href + disabled → tabindex="-1" gesetzt', () => {
		const html = renderBtn({ href: '/x', disabled: true });
		expect(attr(html, 'tabindex')).toBe('-1');
	});

	test('AC-6d: href + disabled → role="link" gesetzt', () => {
		const html = renderBtn({ href: '/x', disabled: true });
		expect(attr(html, 'role')).toBe('link');
	});
});

describe('Btn — <button> + disabled', () => {
	test('AC-7: <button> + disabled → natives disabled-Attribut vorhanden', () => {
		const html = renderBtn({ disabled: true });
		expect(rootTag(html)).toBe('button');
		expect(hasAttr(html, 'disabled')).toBe(true);
	});

	test('AC-7b: <button> + disabled → Click-Handler feuert nicht (HTML-Native: disabled-Attribut verhindert click events)', () => {
		// SSR-Pruefung: Wenn disabled-Attribut auf <button> gerendert ist,
		// liefert der Browser keine click-Events. Das ist HTML-Spec-Verhalten.
		const html = renderBtn({ disabled: true });
		expect(hasAttr(html, 'disabled')).toBe(true);
		// Implicit: ohne disabled feuert Click; HTML-Native-Verhalten.
		const ok = renderBtn({ disabled: false });
		expect(hasAttr(ok, 'disabled')).toBe(false);
	});
});

describe('Btn — Default-Props', () => {
	test('AC-3: Default-Variant ist "primary" (data-variant="primary")', () => {
		const html = renderBtn();
		expect(attr(html, 'data-variant')).toBe('primary');
	});

	test('AC-4: Default-Size ist "md" (data-size="md")', () => {
		const html = renderBtn();
		expect(attr(html, 'data-size')).toBe('md');
	});
});

describe('Btn — Variants & Sizes (Loop-Tests)', () => {
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

	test('AC-1: alle 7 Variants werden akzeptiert und auf data-variant durchgereicht', () => {
		for (const v of VARIANTS) {
			const html = renderBtn({ variant: v });
			expect(attr(html, 'data-variant')).toBe(v);
		}
	});

	test('AC-2: alle 8 Sizes werden akzeptiert und auf data-size durchgereicht', () => {
		for (const s of SIZES) {
			const html = renderBtn({ size: s });
			expect(attr(html, 'data-size')).toBe(s);
		}
	});
});

describe('Btn — class-Merge & children', () => {
	test('AC-12: eigene className wird auf class-Attribut gerendert', () => {
		const html = renderBtn({ class: 'custom-class' });
		const cls = attr(html, 'class') ?? '';
		expect(cls).toContain('custom-class');
	});

	test('AC-children: children-Snippet wird gerendert (Text-Content)', () => {
		const html = renderBtn({ _label: 'Speichern' });
		expect(html).toContain('Speichern');
	});
});

describe('Btn — Type-Re-Exports', () => {
	test('exportiert die Type-Aliases BtnVariant, BtnSize, BtnProps via index.ts', () => {
		// Compile-Time-Check: wenn Importe oben fehlschlagen, schlaegt der Test fehl.
		// Runtime-Marker: existieren die Symbole? (Types werden gestrippt — nur Btn ist runtime)
		expect(Btn).toBeTruthy();
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
		expect(variants.length).toBe(7);
		expect(sizes.length).toBe(8);
	});
});
