// TDD RED — Issue #2837 Scheibe S1 (Epic #2345), Entscheidung 7 / AC-10: die Zähler an
// den Reitern (Badge `[data-slot="segmented-badge"]` in `MTabBar`) sind bei Trip UND
// Ortsvergleich neutral (Grund `--g-paper-deep`, Schrift `--g-ink-3`, nachgerechnet
// ≈ 4,7:1), nie mehr Accent-gefüllt; die Farbe hängt NICHT an `size` (Größe und Farbe
// sind verschiedene Achsen). Spec: docs/specs/modules/rework_2837_s1_hub_kopf.md
//
// Warum am CSS-AST: Das Badge trägt keine Klasse — seine Farbe kommt allein aus den
// komponenten-eigenen (scoped) Regeln von MTabBar.svelte; im SSR-Markup sind Trip- und
// Vergleichs-Badge bereits heute identisch (`<span data-slot="segmented-badge">`). Die
// Wirkung sitzt also in der Kaskade dieser Regeln. Der Test liest sie mit dem ECHTEN
// Svelte-Compiler (parse, modern) und rechnet die Kaskade für ein Badge in einem
// NICHT aktiven Reiter nach — je Breite (Desktop / `max-width: 899px`) und je `size`
// ('md' = Trip, 'sm' = Vergleich, CompareTabs.svelte). Im echten Browser bewacht
// dieselbe Zusicherung die E2E `hub-tab-bar.spec.ts` HT-8 (getComputedStyle, Kontrast).
//
// Pflicht-Mutation (b) „Zähler wieder accent-gefüllt" ⇒ rot: an der Basisregel
// (`background: var(--g-accent)`) ebenso wie an einer neuen Varianten-Klasse.
//
// RED HEUTE: `.mtabbar :global([data-slot='segmented-badge'])` füllt mit `--g-accent`
// und `#fff` (Trip-Desktop) — neutral ist nur `size="sm"`.
//
// Pfadregel #1409: Prüfling relativ zu DIESER Datei.
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types \
//     --experimental-test-module-mocks --test src/lib/components/mobile/__tests__/mtabbar_zaehler_neutral.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import path from 'node:path';
import { parse } from 'svelte/compiler';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const DATEI = path.join(HERE, '..', 'MTabBar.svelte');
const QUELLE = readFileSync(DATEI, 'utf-8');
// eslint-disable-next-line @typescript-eslint/no-explicit-any
const AST = parse(QUELLE, { modern: true }) as any;

interface Regel {
	selektoren: string[];
	decls: Array<[string, string]>;
	media: string | null;
	ordnung: number;
}

function regeln(): Regel[] {
	const out: Regel[] = [];
	let ordnung = 0;
	// eslint-disable-next-line @typescript-eslint/no-explicit-any
	const lauf = (kinder: any[], media: string | null) => {
		for (const n of kinder) {
			if (n.type === 'Rule') {
				out.push({
					selektoren: QUELLE.slice(n.prelude.start, n.prelude.end).split(',').map((s) => s.replace(/\s+/g, ' ').trim()),
					// eslint-disable-next-line @typescript-eslint/no-explicit-any
					decls: n.block.children.filter((d: any) => d.type === 'Declaration').map((d: any) => [d.property, String(d.value).trim()]),
					media,
					ordnung: ordnung++
				});
			} else if (n.type === 'Atrule' && n.block) {
				lauf(n.block.children, `${n.name} ${n.prelude}`);
			}
		}
	};
	lauf(AST.css?.children ?? [], null);
	return out;
}

const REGELN = regeln();
const istBadge = (sel: string) => /segmented-badge/.test(sel);
/** Aktiv-Zustand des REITERS (transluzentes Badge im aktiven Pill) — nicht Gegenstand. */
const nurAktiv = (sel: string) => /data-state='active'|data-state="active"|data-active='true'|data-active="true"/.test(sel);
/** Klassen am .mtabbar-Kopf des Selektors (z. B. ['sm']). */
const kopfKlassen = (sel: string): string[] => {
	const m = /^\.mtabbar((?:\.[a-zA-Z0-9_-]+)*)/.exec(sel);
	return m ? m[1].split('.').filter(Boolean) : [];
};
const spezifitaet = (sel: string): number =>
	(sel.replace(/:global\(([^)]*)\)/g, '$1').match(/\.[a-zA-Z]/g) ?? []).length + (sel.match(/\[/g) ?? []).length;

/** Kaskade für ein Badge in einem NICHT aktiven Reiter: Eigenschaft → Wert (#2845: keine Variantenachse mehr). */
function badgeStil(mobil: boolean): Record<string, string> {
	const treffer: Array<{ spez: number; ordnung: number; decls: Array<[string, string]> }> = [];
	for (const r of REGELN) {
		if (r.media !== null && !(mobil && /max-width:\s*899px/.test(r.media))) continue;
		for (const sel of r.selektoren) {
			if (!istBadge(sel) || nurAktiv(sel)) continue;
			if (kopfKlassen(sel).length > 0) continue; // Varianten-Klasse: eigener Wächter-Test unten
			treffer.push({ spez: spezifitaet(sel), ordnung: r.ordnung, decls: r.decls });
		}
	}
	treffer.sort((a, b) => a.spez - b.spez || a.ordnung - b.ordnung);
	const stil: Record<string, string> = {};
	for (const t of treffer) for (const [p, v] of t.decls) stil[p === 'background-color' ? 'background' : p] = v;
	return stil;
}

describe('#2837 S1 AC-10 — Reiter-Zähler neutral (#2845: eine Optik, keine Variantenachse)', () => {
	for (const mobil of [false, true]) {
		const breite = mobil ? 'Mobil (≤899 px)' : 'Desktop';
		test(`${breite}: Badge-Grund --g-paper-deep, Schrift --g-ink-3`, () => {
			const s = badgeStil(mobil);
			assert.equal(s.background, 'var(--g-paper-deep)', `Badge-Grund ist „${s.background}" — Zähler müssen neutral sein (Mutation b)`);
			assert.equal(s.color, 'var(--g-ink-3)', `Badge-Schrift ist „${s.color}"`);
		});
	}

	test('keine Badge-Regel (außer im aktiven Reiter) füllt mit --g-accent oder weißer Schrift — auch keine Varianten-Klasse', () => {
		const verstoesse: string[] = [];
		for (const r of REGELN)
			for (const sel of r.selektoren) {
				if (!istBadge(sel) || nurAktiv(sel)) continue;
				for (const [p, v] of r.decls) {
					if (/^background/.test(p) && /--g-accent/.test(v)) verstoesse.push(`${sel} { ${p}: ${v} }`);
					if (p === 'color' && /^(#fff(fff)?|white|var\(--g-paper\))$/i.test(v)) verstoesse.push(`${sel} { ${p}: ${v} }`);
				}
			}
		assert.deepEqual(verstoesse, []);
	});

	test('Accent bleibt der Unterstrich des aktiven Reiters (Desktop)', () => {
		const unterstrich = REGELN.filter((r) => r.media === null).some((r) =>
			r.selektoren.some((s) => /data-state='active'/.test(s) && !istBadge(s)) && r.decls.some(([p, v]) => p === 'border-bottom-color' && v === 'var(--g-accent)')
		);
		assert.ok(unterstrich, 'der aktive Reiter ist nicht mehr Accent-unterstrichen');
	});
});

describe('#2845 AC-7 — MTabBar hat keinen Schalter für die Desktop-Optik', () => {
	test('kein Selektor der <style>-Regeln trägt eine Varianten-Klasse am .mtabbar-Kopf', () => {
		const verstoesse: string[] = [];
		for (const r of REGELN) for (const sel of r.selektoren) if (kopfKlassen(sel).length > 0) verstoesse.push(sel);
		assert.deepEqual(verstoesse, [], 'Varianten-Klasse am .mtabbar-Kopf (z. B. .mtabbar.sm) — Rückfall ins Pendant');
	});
	test('Props deklariert kein Feld `size` (AST der Typdeklaration)', () => {
		const felder: string[] = [];
		// eslint-disable-next-line @typescript-eslint/no-explicit-any
		const lauf = (n: any) => {
			if (!n || typeof n !== 'object') return;
			if (n.type === 'TSInterfaceDeclaration' && n.id?.name === 'Props')
				// eslint-disable-next-line @typescript-eslint/no-explicit-any
				for (const m of n.body.body) if (m.key?.name) felder.push(m.key.name);
			for (const k of Object.keys(n)) {
				const v = n[k];
				if (Array.isArray(v)) v.forEach(lauf);
				else if (v && typeof v === 'object') lauf(v);
			}
		};
		lauf(AST.instance);
		assert.ok(felder.includes('items'), `Props nicht gefunden (Felder: ${felder.join(',')})`);
		assert.ok(!felder.includes('size'), 'Props deklariert noch `size`');
	});
});
