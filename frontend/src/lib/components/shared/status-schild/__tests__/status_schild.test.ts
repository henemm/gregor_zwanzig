// TDD RED — Issue #2837 Nachbesserung S1b (Epic #2345): EIN Status-Schild für Trip und
// Ortsvergleich (`shared/status-schild/StatusSchild.svelte`).
// Spec: docs/specs/modules/rework_2837_s1b_status_profil.md — AC-2, AC-4, AC-5, AC-8, AC-11
// (Baustein-Anteil). Die Wirkung an BEIDEN Seiten prüft
// shared/hub-kopf/__tests__/hub_kopf_seiten_paritaet.test.ts (Block „#2837 S1b"), die
// berechneten Farben im echten Browser frontend/e2e/hub-kopf-paritaet-compare-trip.spec.ts.
//
// Übernimmt die Zusicherungen aus trip-detail/TripStatusBadge.atomic.test.ts (#389: active →
// accent statt success, outlined, accent-deep) — hier am GERENDERTEN Schild statt am Quelltext.
//
// Echte Komponente, serverseitig gerendert (svelte/server, Hooks frontend/test-svelte-ssr-hooks.mjs);
// kein Mock. Die Farbe ergibt sich aus der echten Kaskade von frontend/src/app.css für die
// Attribute, die das gerenderte Schild trägt (Attribut-Selektoren der Pill-Regeln, Spezifität +
// Reihenfolge), Tokens aus :root aufgelöst, Kontrast nach WCAG gerechnet.
//
// Pflicht-Mutation (Spec Test Plan): Pausiert-Textfarbe wieder `--g-warning` ⇒ „AC-4 …" rot.
//
// RED HEUTE: `shared/status-schild/StatusSchild.svelte` existiert nicht (Import in `lade()`,
// jeder Test scheitert einzeln); app.css färbt umrandet-warning mit --g-warning (2,77 : 1).
//
// Pfadregel #1409: Prüfling relativ zu DIESER Datei.
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types \
//     --experimental-test-module-mocks --test src/lib/components/shared/status-schild/__tests__/status_schild.test.ts

import { test, describe, afterEach } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { register } from 'node:module';
import { fileURLToPath, pathToFileURL } from 'node:url';
import path from 'node:path';
import { baum, alle, text, type Knoten } from '../../hub-kopf/__tests__/htmlBaum.ts';

const HERE = path.dirname(fileURLToPath(import.meta.url));
// __tests__ -> status-schild -> shared -> components -> lib -> src -> frontend
const FRONTEND = path.resolve(HERE, '../../../../../..');

register(pathToFileURL(path.join(FRONTEND, 'test-svelte-ssr-hooks.mjs')).href, pathToFileURL(FRONTEND + '/').href);

const { render } = await import('svelte/server');
const { locale, trFor } = await import(pathToFileURL(path.join(FRONTEND, 'src/lib/i18n/index.ts')).href);

const PRUEFLING = path.join(HERE, '..', 'StatusSchild.svelte');
async function lade(): Promise<unknown> {
	return (await import(pathToFileURL(PRUEFLING).href)).default;
}

afterEach(() => locale.set('de'));

type Zustand = 'draft' | 'planned' | 'active' | 'paused' | 'finished' | 'archived';
const ZUSTAENDE: Zustand[] = ['draft', 'planned', 'active', 'paused', 'finished', 'archived'];

/** Spec „Implementation Details": Zustand ⇒ Tone und erwartete Textfarbe (Hex). */
const ERWARTET: Record<Zustand, { tone: string; farbe: string }> = {
	draft: { tone: 'default', farbe: '#5c5a52' },
	planned: { tone: 'info', farbe: '#2c5a8c' },
	active: { tone: 'accent', farbe: '#8c3e1a' },
	paused: { tone: 'warning', farbe: '#8a6210' },
	finished: { tone: 'default', farbe: '#5c5a52' },
	archived: { tone: 'default', farbe: '#5c5a52' }
};

async function schild(status: Zustand, extra: Record<string, unknown> = {}): Promise<Knoten> {
	const Komponente = await lade();
	// eslint-disable-next-line @typescript-eslint/no-explicit-any
	const html = render(Komponente as any, { props: { status, ...extra } }).body;
	const pills = alle(baum(html), (n) => n.attrs['data-slot'] === 'pill');
	assert.equal(pills.length, 1, `genau ein Pill-Element erwartet, gefunden ${pills.length}: ${html}`);
	return pills[0];
}

describe('#2837 S1b StatusSchild — Baustein (AC-2, AC-8, AC-11)', () => {
	for (const lang of ['de', 'en'] as const) {
		for (const z of ZUSTAENDE) {
			test(`AC-2/AC-11 (${lang}, ${z}): Pill umrandet, Tone „${ERWARTET[z].tone}", data-status, Text aus trip.status.${z}`, async () => {
				locale.set(lang);
				const p = await schild(z);
				assert.equal(p.attrs['data-tone'], ERWARTET[z].tone, `Tone für ${z}`);
				assert.ok('data-outlined' in p.attrs, `${z}: Schild nicht umrandet (data-outlined fehlt) — gefüllt?`);
				assert.equal(p.attrs['data-status'], z, `${z}: data-status fehlt oder falsch`);
				assert.equal(text(p), trFor(lang, `trip.status.${z}`), `${z} (${lang}): Text nicht aus dem Katalog trip.status.*`);
				assert.ok(!('style' in p.attrs), `${z}: Inline-Stil am Schild (Altlast #488 — Farbe gehört dem Pill-Atom)`);
			});
		}
	}

	test('#389 übernommen: aktiv ist accent, nie success (Regressionswächter)', async () => {
		const p = await schild('active');
		assert.notEqual(p.attrs['data-tone'], 'success');
		assert.equal(p.attrs['data-tone'], 'accent');
	});

	test('AC-8: Prop testid landet als data-testid am Schild', async () => {
		const p = await schild('paused', { testid: 'trip-detail-status-badge' });
		assert.equal(p.attrs['data-testid'], 'trip-detail-status-badge');
	});

	test('AC-3: Entwurf heißt auf Deutsch „Entwurf", nie „draft"', async () => {
		locale.set('de');
		const p = await schild('draft');
		assert.equal(text(p), 'Entwurf');
		assert.ok(!/draft/i.test(text(p)));
	});
});

// ── Kaskade aus app.css für die Attribute des gerenderten Schilds ─────────────────────────────

const CSS = readFileSync(path.join(FRONTEND, 'src/app.css'), 'utf-8').replace(/\/\*[\s\S]*?\*\//g, '');

/** Letzte Definition jedes --g-Tokens in :root (Hex-Werte). Gemessen wird der Hellmodus:
 *  der Dark-Block `:root[data-theme="dark"]` (#2400) zählt hier nicht mit. */
const HELL_CSS = CSS.replace(/:root\[data-theme=(["'])dark\1\]\s*\{[^{}]*\}/g, '');
const TOKENS: Record<string, string> = {};
for (const m of HELL_CSS.matchAll(/(--g-[a-z0-9-]+)\s*:\s*([^;]+);/g)) TOKENS[m[1]] = m[2].trim();

type Regel = { attrs: Array<[string, string | null]>; spez: number; nr: number; decl: Record<string, string> };
const REGELN: Regel[] = [];
{
	let nr = 0;
	for (const m of CSS.matchAll(/([^{}]+)\{([^{}]*)\}/g)) {
		const decl: Record<string, string> = {};
		for (const d of m[2].split(';')) {
			const i = d.indexOf(':');
			if (i > 0) decl[d.slice(0, i).trim()] = d.slice(i + 1).trim();
		}
		for (const sel of m[1].split(',').map((s) => s.trim())) {
			// nur reine Attribut-Verbindungen an der Pill (z. B. [data-slot="pill"][data-outlined][data-tone="warning"])
			if (!/^(\[[^\]]+\])+$/.test(sel) || !sel.includes('[data-slot="pill"]')) continue;
			const attrs = [...sel.matchAll(/\[([a-z-]+)(?:="([^"]*)")?\]/g)].map((a) => [a[1], a[2] ?? null] as [string, string | null]);
			REGELN.push({ attrs, spez: attrs.length, nr: nr++, decl });
		}
	}
}

/** Gewinnender Wert einer Eigenschaft für ein Element (Spezifität, dann Reihenfolge). */
function wert(el: Knoten, eigenschaft: string): string | undefined {
	const passend = REGELN.filter(
		(r) => eigenschaft in r.decl && r.attrs.every(([a, v]) => a in el.attrs && (v === null || el.attrs[a] === v))
	).sort((a, b) => a.spez - b.spez || a.nr - b.nr);
	return passend.at(-1)?.decl[eigenschaft];
}
const aufloesen = (v: string | undefined): string | undefined => {
	let x = v;
	for (let i = 0; i < 5 && x && /var\(/.test(x); i++) x = x.replace(/var\((--[a-z0-9-]+)\)/g, (_, t) => TOKENS[t] ?? `var(${t})`);
	return x?.toLowerCase();
};
function kontrast(a: string, b: string): number {
	const lum = (hex: string) => {
		const h = hex.replace('#', '');
		const [r, g, bl] = [0, 2, 4].map((i) => parseInt(h.slice(i, i + 2), 16) / 255).map((s) => (s <= 0.03928 ? s / 12.92 : ((s + 0.055) / 1.055) ** 2.4));
		return 0.2126 * r + 0.7152 * g + 0.0722 * bl;
	};
	const [x, y] = [lum(a), lum(b)].sort((m, n) => n - m);
	return (x + 0.05) / (y + 0.05);
}

describe('#2837 S1b StatusSchild — Farbe aus der echten app.css-Kaskade (AC-2, AC-4, AC-5)', () => {
	test('Messaufbau: Papier- und Karten-Token sind Hex-Farben', () => {
		assert.match(TOKENS['--g-paper'] ?? '', /^#[0-9a-f]{6}$/i);
		assert.match(TOKENS['--g-card'] ?? '', /^#[0-9a-f]{6}$/i);
		assert.ok(REGELN.length > 5, 'Messaufbau: keine Pill-Regeln in app.css gefunden');
	});

	for (const z of ZUSTAENDE) {
		test(`AC-2/AC-4/AC-5 (${z}): Schrift ${ERWARTET[z].farbe}, Grund transparent, Rand currentColor, Kontrast ≥ 4,5 auf Papier und Karte`, async () => {
			const p = await schild(z);
			const farbe = aufloesen(wert(p, 'color'));
			assert.equal(farbe, ERWARTET[z].farbe, `${z}: Schriftfarbe ${farbe} (erwartet ${ERWARTET[z].farbe}) — Mutation „Pausiert wieder --g-warning"?`);
			assert.equal(aufloesen(wert(p, 'background')), 'transparent', `${z}: Schild ist gefüllt statt umrandet`);
			assert.match(wert(p, 'border') ?? '', /currentcolor/i, `${z}: Rand nicht in Schriftfarbe`);
			for (const grund of ['--g-paper', '--g-card']) {
				const k = kontrast(farbe!, TOKENS[grund]);
				assert.ok(k >= 4.5, `${z}: Kontrast ${k.toFixed(2)} : 1 auf ${grund} < 4,5 (WCAG-AA)`);
			}
		});
	}
});
