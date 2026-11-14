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
// #2980 Fix-Loop Bildabgleich (Spec feat_2913_c2_seitenkopf.md AC-21/AC-22, ADR-0118, Mockup
// Z. 41–43 und 326): das Schild ist jetzt GEFÜLLT ohne Rahmen — aktiv = good (--g-good auf
// hellgrün), alle anderen Zustände neutral (--g-ink-3 auf --g-paper-deep). Die Zusicherungen
// „umrandet, Tone accent/info/warning/default“ (#389, S1b) sind damit bewusst abgelöst; gemessen
// wird die Kaskade (hub-kopf/__tests__/cssKaskade.ts: app.css + kompiliertes Komponenten-CSS) am
// gerenderten Schild, unabhängig davon, über welchen Tone/welche Regel die Umsetzung den Ton erreicht.
//
// Pfadregel #1409: Prüfling relativ zu DIESER Datei.
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types \
//     --experimental-test-module-mocks --test src/lib/components/shared/status-schild/__tests__/status_schild.test.ts

import { test, describe, afterEach } from 'node:test';
import assert from 'node:assert/strict';
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

/** #2980 AC-21 (Mockup Z. 326): aktiv = good, alles andere neutral. */
const TON: Record<Zustand, 'good' | 'neutral'> = {
	draft: 'neutral',
	planned: 'neutral',
	active: 'good',
	paused: 'neutral',
	finished: 'neutral',
	archived: 'neutral'
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
			test(`AC-2/AC-11 (${lang}, ${z}): Pill gefüllt (ohne data-outlined, #2980 AC-21), data-status, Text aus trip.status.${z}`, async () => {
				locale.set(lang);
				const p = await schild(z);
				assert.ok(!('data-outlined' in p.attrs), `${z}: Schild noch umrandet (data-outlined) — #2980 AC-21: gefüllt ohne Rahmen`);
				assert.equal(p.attrs['data-status'], z, `${z}: data-status fehlt oder falsch`);
				assert.equal(text(p), trFor(lang, `trip.status.${z}`), `${z} (${lang}): Text nicht aus dem Katalog trip.status.*`);
				assert.ok(!('style' in p.attrs), `${z}: Inline-Stil am Schild (Altlast #488 — Farbe gehört dem Pill-Atom)`);
			});
		}
	}

	test('#389 abgelöst durch #2980 AC-21: aktiv ist kein Accent-Schild mehr (good-Ton, Farbe siehe Kaskade unten)', async () => {
		const p = await schild('active');
		assert.notEqual(p.attrs['data-tone'], 'accent', 'aktiv trägt noch Tone accent (Mockup: good)');
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

// ── Kaskade (cssKaskade.ts) für das gerenderte Schild, Hell und Dunkel (#2980 AC-21/AC-22) ─────
// doc-compliance-test (liest CSS-Quellen als Daten; Verhalten = Kaskade am gerenderten Markup)

const K = await import('../../hub-kopf/__tests__/cssKaskade.ts');
const Q = await K.ladeQuellen(FRONTEND);
const GOOD_RGB = [61, 107, 58];

describe('#2980 StatusSchild — gefüllt ohne Rahmen, Ton nach Mockup, Kontrast (AC-21, AC-22)', () => {
	for (const theme of ['hell', 'dunkel'] as const) {
		for (const z of ZUSTAENDE) {
			test(`AC-21/AC-22 (${theme}, ${z}): ${TON[z]} — Mono 11 px uppercase, kein Rahmen, Kontrast ≥ 4,5`, async () => {
				const ctx = { ...K.DESKTOP, theme };
				const p = await schild(z);
				const st = (prop: string) => K.stil(Q, p, prop, ctx);
				const her = (prop: string) => K.herkunft(Q, p, prop, ctx);
				for (const seite of ['top', 'right', 'bottom', 'left']) {
					const stil = st(`border-${seite}-style`) ?? 'none';
					const breite = st(`border-${seite}-width`);
					assert.ok(stil === 'none' || breite === '0' || breite === '0px', `${z}: Rahmen ${seite} ${breite} ${stil} — ${her(`border-${seite}-style`)}`);
				}
				assert.equal(st('font-family'), K.token(Q, '--g-font-mono', theme), `${z}: Schrift nicht Mono — ${her('font-family')}`);
				assert.equal(st('font-size'), '11px', `${z}: Schriftgröße — ${her('font-size')}`);
				assert.equal(st('text-transform'), 'uppercase', `${z}: Großschreibung nicht per CSS — ${her('text-transform')}`);
				const vg = st('color');
				const hg = st('background-color') ?? 'transparent';
				if (TON[z] === 'good') {
					assert.equal(vg, K.token(Q, '--g-good', theme), `${z}: Schrift ${vg} statt --g-good — ${her('color')}`);
					const f = K.farbe(hg);
					assert.ok(f && f[0] === GOOD_RGB[0] && f[1] === GOOD_RGB[1] && f[2] === GOOD_RGB[2] && f[3] > 0 && f[3] <= 0.2, `${z}: Grund ${hg} statt hellgrün — ${her('background-color')}`);
				} else {
					const erlaubt = theme === 'hell' ? [K.token(Q, '--g-ink-3', theme)] : [K.token(Q, '--g-ink-3', theme), K.token(Q, '--g-ink-2', theme)];
					assert.ok(erlaubt.includes(vg!), `${z}: Schrift ${vg} statt --g-ink-3 — ${her('color')}`);
					assert.equal(hg, K.token(Q, '--g-paper-deep', theme), `${z}: Grund ${hg} statt --g-paper-deep — ${her('background-color')}`);
				}
				const papier = K.farbe(K.token(Q, '--g-paper', theme))!;
				const grund = K.ueber(K.farbe(hg)!, papier);
				const k = K.kontrast(K.ueber(K.farbe(vg)!, grund), grund);
				assert.ok(k >= 4.5, `${z} (${theme}): Kontrast ${k.toFixed(2)} : 1 < 4,5 (WCAG-AA)`);
			});
		}
	}
});
