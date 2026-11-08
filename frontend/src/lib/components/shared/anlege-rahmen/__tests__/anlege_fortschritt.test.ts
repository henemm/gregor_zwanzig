// TDD RED — Issue #2837 Scheibe S2b (Epic #2345, ADR-0110): EIN Fortschrittsbalken-Baustein
// `shared/anlege-rahmen/AnlegeFortschritt.svelte` für /trips/new und /compare/new, Computer
// (`variante="desktop"`) und Handy (`variante="mobil"`).
// Spec: docs/specs/modules/rework_2837_s2b_anlege_fortschritt.md — Entscheidungen 1–3,
//   Implementation Details 1, AC-3 (Unit-Anteil), AC-6, AC-7, AC-9; Mutationen aus dem Test Plan.
//
// Echte Komponente, serverseitig gerendert (svelte/server, Hooks über infoboxSsr.ts) — kein
// Mock, kein Datei-Grep. Gelesen wird der Element-Baum des SSR-Outputs (htmlBaum.ts). Die
// berechneten Farben im Browser prüft die E2E frontend/e2e/anlege-rahmen-paritaet.spec.ts (AR-19 ff.).
//
// Vertrag (von RED festgelegt):
//   Props: steps: readonly string[] (wie PROGRESS_STEPS), done: number (= Ergebnis von
//   `progressCount`, also eine ZAHL, kein Set — beide Editoren liefern heute eine Zahl:
//   Trip `progressN`, Vergleich `doneCount`), aktiv?: string (id des aktiven Schritts, OHNE
//   Optik), variante: 'desktop' | 'mobil', testidPrefix: string.
//   Segment i ist erledigt ⇔ i < done (Spec AC-1 „die ersten erledigten in Akzentfarbe").
//   Markup: Container `<div data-testid={testidPrefix}>`; darin je Schritt ein Segment
//   `data-testid="${testidPrefix}-segment"` mit `data-done="true|false"`; Farbe als INLINE-Stil
//   `background: var(--g-accent)` (erledigt) bzw. `background: var(--g-rule)` (offen); Breite
//   Computer `width: 24px`, Handy `flex: 1`. Zähler `<span class="mono">` ist LETZTES Kind des
//   Containers (Regex-Auslese in compare_new_lock_engine_wirkstelle.test.ts).
//   `aktiv` ändert kein Attribut außer optional `aria-current` (keine Klasse, kein Stil).
//   Zählertext: Computer `trip.anlegen.nichts_eingerichtet` (0) bzw. `trip.anlegen.abschnitte`
//   {n, gesamt}; Handy „n/gesamt".
//
// RED HEUTE: der Baustein existiert nicht (Import erst in `lade()`, damit jeder Test einzeln
// mit eigener Meldung scheitert).
//
// Pfadregel #1409: Prüfling relativ zu DIESER Datei.
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types \
//     --experimental-test-module-mocks --test src/lib/components/shared/anlege-rahmen/__tests__/anlege_fortschritt.test.ts

import { test, describe, afterEach } from 'node:test';
import assert from 'node:assert/strict';
import { fileURLToPath, pathToFileURL } from 'node:url';
import path from 'node:path';
import { renderKomponente, FRONTEND } from '../../__tests__/infoboxSsr.ts';
import { baum, alle, einzig, liegtIn, text, klassen, type Knoten } from '../../hub-kopf/__tests__/htmlBaum.ts';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const PRUEFLING = path.join(HERE, '..', 'AnlegeFortschritt.svelte');

const { locale, trFor } = await import(pathToFileURL(path.join(FRONTEND, 'src/lib/i18n/index.ts')).href);

async function lade(): Promise<unknown> {
	return (await import(pathToFileURL(PRUEFLING).href)).default;
}

afterEach(() => locale.set('de'));

type Variante = 'desktop' | 'mobil';
type Lang = 'de' | 'en';
/** Fester Wert (Spec AN-2: fünf Pflicht-Schritte), nicht aus dem Produkt. */
const STEPS = ['route', 'etappen', 'wetter-metriken', 'wertebereiche', 'alarme'] as const;
const PREFIX: Record<Variante, string> = { desktop: 'trip-new-progress', mobil: 'tn-mobile-progress' };

/** Inline-Stil → Map (Deklarationen normalisiert). */
function stil(k: Knoten): Record<string, string> {
	const out: Record<string, string> = {};
	for (const d of (k.attrs.style ?? '').split(';')) {
		const i = d.indexOf(':');
		if (i > 0) out[d.slice(0, i).trim().toLowerCase()] = d.slice(i + 1).trim().replace(/\s+/g, ' ');
	}
	return out;
}

async function render_(p: { done: number; variante: Variante; aktiv?: string; testidPrefix?: string }) {
	const Komponente = await lade();
	const testidPrefix = p.testidPrefix ?? PREFIX[p.variante];
	const html = renderKomponente(Komponente, { steps: STEPS, ...p, testidPrefix });
	const wurzel = baum(html);
	const container = einzig(wurzel, testidPrefix);
	const segmente = alle(wurzel, (n) => n.attrs['data-testid'] === `${testidPrefix}-segment`);
	return { html, wurzel, container, segmente };
}

function zaehler(container: Knoten): Knoten {
	const letztes = container.kinder[container.kinder.length - 1];
	assert.ok(letztes, 'Container hat keine Kinder');
	assert.equal(letztes.tag, 'span', `letztes Kind des Containers ist <${letztes.tag}>, erwartet <span class="mono">`);
	assert.deepEqual(klassen(letztes), ['mono'], `Zähler hat class="${letztes.attrs.class}" (erwartet genau "mono")`);
	return letztes;
}

const sollText = (variante: Variante, n: number, lang: Lang) =>
	variante === 'mobil'
		? `${n}/${STEPS.length}`
		: n === 0
			? trFor(lang, 'trip.anlegen.nichts_eingerichtet')
			: trFor(lang, 'trip.anlegen.abschnitte', { n, gesamt: STEPS.length });

for (const variante of ['desktop', 'mobil'] as const) {
	describe(`#2837 S2b AnlegeFortschritt (${variante}) — Segmente und Farbregel`, () => {
		test(`${variante}: 5 Segmente ${PREFIX[variante]}-segment im Container ${PREFIX[variante]}`, async () => {
			const { container, segmente } = await render_({ done: 2, variante });
			assert.equal(segmente.length, STEPS.length, `erwartet ${STEPS.length} Segmente, gefunden ${segmente.length}`);
			for (const s of segmente) assert.ok(liegtIn(s, container), 'Segment liegt nicht im Testid-Container');
		});

		for (const done of [0, 2, 5]) {
			test(`${variante}, done=${done}: genau die ersten ${done} Segmente data-done="true", der Rest "false"`, async () => {
				const { segmente } = await render_({ done, variante });
				assert.deepEqual(
					segmente.map((s) => s.attrs['data-done']),
					STEPS.map((_, i) => (i < done ? 'true' : 'false'))
				);
			});

			test(`${variante}, done=${done}: erledigt ⇒ background var(--g-accent), offen ⇒ var(--g-rule)`, async () => {
				const { segmente } = await render_({ done, variante, aktiv: STEPS[Math.min(done, STEPS.length - 1)] });
				segmente.forEach((s, i) => {
					const soll = i < done ? 'var(--g-accent)' : 'var(--g-rule)';
					assert.equal(stil(s).background, soll, `Segment ${i}: background „${stil(s).background}" (erwartet ${soll})`);
				});
			});
		}

		test(`AC-3 ${variante}: das aktive offene Segment sieht aus wie jedes andere offene (keine Tönung)`, async () => {
			// done=1, aktiv = Schritt 2 (offen); Schritte 3–5 sind ebenfalls offen.
			const { segmente } = await render_({ done: 1, variante, aktiv: STEPS[1] });
			const offen = segmente.slice(1).map((s) => `${s.attrs.class ?? ''}|${s.attrs.style ?? ''}`);
			assert.equal(new Set(offen).size, 1, `offene Segmente unterscheiden sich (aktives getönt?): ${JSON.stringify(offen)}`);
		});

		test(`AC-3 ${variante}: aktiv ändert weder Klasse noch Stil irgendeines Elements`, async () => {
			const optik = (w: Knoten) => alle(w, () => true).map((n) => `${n.tag}|${n.attrs.class ?? ''}|${n.attrs.style ?? ''}`);
			const ohne = await render_({ done: 1, variante });
			for (const aktiv of STEPS) {
				const mit = await render_({ done: 1, variante, aktiv });
				assert.deepEqual(optik(mit.wurzel), optik(ohne.wurzel), `aktiv=${aktiv} verändert die Optik`);
			}
		});

		test(`AC-3 ${variante}: kein --g-accent-soft und kein #bcd im Output`, async () => {
			for (const aktiv of STEPS) {
				const { html } = await render_({ done: 1, variante, aktiv });
				assert.ok(!html.includes('--g-accent-soft'), `aktiv=${aktiv}: --g-accent-soft im Balken`);
				assert.ok(!/#bcd\b/i.test(html), `aktiv=${aktiv}: Rückfallwert #bcd im Balken`);
			}
		});

		test(`Entscheidung 3 ${variante}: Segmentbreite ${variante === 'desktop' ? 'fest 24px' : 'flexibel (flex: 1)'}`, async () => {
			const { segmente } = await render_({ done: 2, variante });
			for (const s of segmente) {
				if (variante === 'desktop') assert.equal(stil(s).width, '24px', `Desktop-Segment ohne width 24px: „${s.attrs.style}"`);
				else assert.match(stil(s).flex ?? '', /^1\b/, `Handy-Segment ohne flex: 1: „${s.attrs.style}"`);
			}
		});

		test(`AC-9 ${variante}: Container ist <div>, Zähler <span class="mono"> ist sein letztes Kind`, async () => {
			const { container } = await render_({ done: 2, variante });
			assert.equal(container.tag, 'div', 'Container muss <div> sein (Regex-Auslese erwartet </span></div>)');
			zaehler(container);
		});

		for (const lang of ['de', 'en'] as const) {
			for (const done of [0, 3]) {
				test(`AC-6/AC-7 ${variante}, ${lang}, done=${done}: Zählertext „${sollText(variante, done, lang)}"`, async () => {
					locale.set(lang);
					const { container } = await render_({ done, variante });
					assert.equal(text(zaehler(container)), sollText(variante, done, lang));
				});
			}
		}
	});
}

describe('#2837 S2b Entscheidung 1/3 — ein Markup, variante wählt nur Breite und Zählertext', () => {
	test('desktop und mobil: gleiche Elementfolge, Klassen, data-done und Farbe; Unterschied nur width/flex und Zähler', async () => {
		const geruest = (w: Knoten) =>
			alle(w, () => true).map((n) => {
				const s = stil(n);
				delete s.width;
				delete s.flex;
				delete s['flex-shrink'];
				return `${n.tag}|${n.attrs.class ?? ''}|${n.attrs['data-testid'] ?? ''}|${n.attrs['data-done'] ?? ''}|${s.background ?? ''}`;
			});
		const d = await render_({ done: 2, variante: 'desktop', testidPrefix: 'x' });
		const m = await render_({ done: 2, variante: 'mobil', testidPrefix: 'x' });
		assert.deepEqual(geruest(m.wurzel), geruest(d.wurzel));
		assert.notEqual(text(zaehler(d.container)), text(zaehler(m.container)), 'Zählertext Computer = Handy (Handy muss „n/5" zeigen)');
	});

	test('testidPrefix bestimmt Container- und Segment-Testid (compare-editor-progress / cm-mobile-progress)', async () => {
		for (const [variante, prefix] of [['desktop', 'compare-editor-progress'], ['mobil', 'cm-mobile-progress']] as const) {
			const { segmente, html } = await render_({ done: 1, variante, testidPrefix: prefix });
			assert.equal(segmente.length, STEPS.length, `${prefix}-segment: ${segmente.length}× statt ${STEPS.length}×`);
			assert.ok(!html.includes('trip-new-progress') && !html.includes('tn-mobile-progress'), 'fremdes Testid-Präfix im Output');
		}
	});
});
