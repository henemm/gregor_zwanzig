// TDD RED — Issue #2794 S3a, Fix-Loop teil4b, Befund B3 (Karten-Raster der Übersicht).
// Spec: docs/specs/modules/fix_2794_s3a_teil4b_befunde.md — B3, AC-6, AC-7
//
// Befund: Desktop beginnt bei 900 px Viewport, die Seitenleiste ist 220 px breit. Bei
// Viewports von etwa 900–1150 px ist das Karten-Raster nur ~600–870 px breit. Mit
// `grid-template-columns: repeat(auto-fit, minmax(280px, 1fr))` entstehen dort zwei
// Spalten ⇒ im Orts-Vergleich (drei Karten Orte, Wetter, Versand) steht die Versand-Karte
// allein in halber Breite neben einer leeren Hälfte (verletzt AC-7).
//
// Messweg (kein DOM im Projekt, kein Mock): die ECHTE Komponente wird per svelte/server
// gerendert (Desktop-Zweig — im SSR läuft kein matchMedia). Aus dem gerenderten HTML werden
// das Raster (Elternelement der Karte mit dem Versand-Knopf) und seine Karten mit ihren
// gerenderten Inline-Styles gelesen. Ein kleiner, ausdrücklich begrenzter Layout-Rechner
// bestimmt daraus für jede Rasterbreite von 560 bis 1400 px, wie die Karten in Zeilen
// umbrechen und wie breit jede Karte wird — nach den CSS-Regeln für
//   (a) Grid `repeat(auto-fit|auto-fill, minmax(Npx, 1fr))` bzw. feste `1fr …`-Spuren,
//   (b) Flex mit `flex-wrap: wrap` und `flex: <grow> <shrink> <basis>px`.
// Ein anderes Layout ⇒ Messaufbau-Fehler (nie still grün).
// Zusicherung (AC-6/AC-7): jede Zeile ist zu mindestens 90 % gefüllt — insbesondere füllt
// eine Karte, die allein in ihrer Zeile steht, die Zeile. Die echte Pixelmessung im Browser
// macht frontend/e2e/s3a2794-teil4b-staging.spec.ts (AC-6/AC-7 bei 1024/1280/1440 px).
//
// Pfadregel #1409: alles relativ zu DIESER Datei.
//
//   cd frontend && npm test -- src/lib/components/shared/hub-uebersicht/__tests__/s3a2794_teil4b_karten_raster.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { register } from 'node:module';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

process.env.TZ = 'Europe/Berlin';

const HIER = dirname(fileURLToPath(import.meta.url));
// __tests__ -> hub-uebersicht -> shared -> components -> lib -> src -> frontend
const FRONTEND = resolve(HIER, '..', '..', '..', '..', '..', '..');
const basis = pathToFileURL(FRONTEND + '/').href;
register(pathToFileURL(join(FRONTEND, 'test-env-dynamic-private-stub-hooks.mjs')).href, basis);
register(pathToFileURL(join(FRONTEND, 'test-app-environment-stub-hooks.mjs')).href, basis);
register(pathToFileURL(join(FRONTEND, 'src/lib/components/trip-new/__tests__/ssrRunesHook.mjs')).href, basis);
register(pathToFileURL(join(FRONTEND, 'test-svelte-ssr-hooks.mjs')).href, basis);
register(pathToFileURL(join(FRONTEND, 'src/lib/components/shared/__tests__/svelteTsModulHook.mjs')).href, basis);

const { render } = await import('svelte/server');
const HubUebersicht = (await import(pathToFileURL(join(HIER, '..', 'HubUebersicht.svelte')).href)).default;

// ── Fixtures ─────────────────────────────────────────────────────────────────

const TRIP = {
	id: 't-2794-b3',
	name: 'Testtrip',
	stages: [{ id: 's1', name: 'E1', date: '2099-07-01', waypoints: [] }],
	report_config: { enabled: true, morning_enabled: true, morning_time: '07:00:00' },
	display_config: {}
};

const PRESET = {
	id: 'cp-2794-b3',
	name: 'Testvergleich',
	location_ids: ['l1', 'l2'],
	schedule: 'daily',
	profil: 'wandern',
	hour_from: 6,
	hour_to: 18,
	empfaenger: [],
	forecast_hours: 48,
	created_at: '2026-10-01T00:00:00Z',
	display_config: {}
};
const ORTE = [
	{ rank: 1, loc: { id: 'l1', name: 'Alpha' } },
	{ rank: 2, loc: { id: 'l2', name: 'Beta' } }
];

// ── Raster aus dem gerenderten HTML ──────────────────────────────────────────

type Stil = Record<string, string>;

function stilVon(tag: string): Stil {
	const m = /\bstyle="([^"]*)"/.exec(tag);
	const stil: Stil = {};
	for (const teil of (m?.[1] ?? '').split(';')) {
		const i = teil.indexOf(':');
		if (i < 0) continue;
		stil[teil.slice(0, i).trim().toLowerCase()] = teil.slice(i + 1).trim();
	}
	return stil;
}

/** Raster-Stil und Stile seiner direkten Karten-Kinder (Elternelement der Versand-Karte). */
function raster(html: string, versandTestid: string): { raster: Stil; karten: Stil[] } {
	const body = html.replace(/<!--[\s\S]*?-->/g, '');
	const knopf = body.indexOf(`data-testid="${versandTestid}"`);
	assert.notEqual(knopf, -1, `Messaufbau: Versand-Knopf ${versandTestid} fehlt im SSR-HTML`);
	const tagRe = /<(\/?)div\b[^>]*>/g;
	const stapel: { start: number; tag: string }[] = [];
	let m: RegExpExecArray | null;
	while ((m = tagRe.exec(body)) && m.index < knopf) {
		if (m[1] === '/') stapel.pop();
		else stapel.push({ start: m.index, tag: m[0] });
	}
	const kartenIdx = stapel.map((e) => e.tag.includes('data-slot="card"')).lastIndexOf(true);
	assert.ok(kartenIdx > 0, 'Messaufbau: Versand-Knopf steht in keiner Karte');
	const eltern = stapel[kartenIdx - 1];
	// direkte div-Kinder des Rasters
	const karten: Stil[] = [];
	tagRe.lastIndex = eltern.start;
	let tiefe = 0;
	while ((m = tagRe.exec(body))) {
		if (m[1] === '/') {
			tiefe--;
			if (tiefe === 0) break;
		} else {
			tiefe++;
			if (tiefe === 2) {
				assert.ok(m[0].includes('data-slot="card"'), `Messaufbau: Raster-Kind ist keine Karte: ${m[0]}`);
				karten.push(stilVon(m[0]));
			}
		}
	}
	return { raster: stilVon(eltern.tag), karten };
}

// ── Layout-Rechner (begrenzt auf die beiden hier zulässigen Muster) ─────────

const px = (s: string | undefined, was: string): number => {
	const m = /^(-?\d+(?:\.\d+)?)px$/.exec((s ?? '').trim());
	assert.ok(m, `Messaufbau: ${was} ist kein px-Wert: „${s}"`);
	return Number(m![1]);
};

/** Breiten der Karten je Zeile bei Rasterbreite `w`. */
function zeilen(r: Stil, karten: Stil[], w: number): number[][] {
	const gap = px(r['column-gap'] ?? r['gap'], 'gap');
	const n = karten.length;
	if (r['display'] === 'grid') {
		const spuren = r['grid-template-columns'] ?? '';
		const auto = /^repeat\(\s*(auto-fit|auto-fill)\s*,\s*minmax\(\s*(\d+)px\s*,\s*1fr\s*\)\s*\)$/.exec(spuren);
		let spalten: number;
		let belegt: number;
		if (auto) {
			const min = Number(auto[2]);
			spalten = Math.max(1, Math.floor((w + gap) / (min + gap)));
			// auto-fit: leere Spuren fallen weg, die belegten teilen sich die Breite.
			belegt = auto[1] === 'auto-fit' ? Math.min(spalten, n) : spalten;
		} else {
			const fest = spuren.split(/\s+/).filter(Boolean);
			assert.ok(fest.length > 0 && fest.every((s) => s === '1fr'), `Messaufbau: unbekannte Grid-Spuren „${spuren}"`);
			spalten = belegt = fest.length;
		}
		const breite = (w - gap * (belegt - 1)) / belegt;
		const out: number[][] = [];
		for (let i = 0; i < n; i += spalten) out.push(karten.slice(i, i + spalten).map(() => breite));
		return out;
	}
	if (r['display'] === 'flex') {
		assert.equal(r['flex-wrap'], 'wrap', 'Messaufbau: Flex-Raster ohne flex-wrap: wrap');
		assert.ok(!r['flex-direction'] || r['flex-direction'] === 'row', 'Messaufbau: Flex-Raster nicht zeilenweise');
		const items = karten.map((k, i) => {
			const f = (k['flex'] ?? '').split(/\s+/);
			assert.equal(f.length, 3, `Messaufbau: Karte ${i} ohne „flex: <grow> <shrink> <basis>px" (${k['flex']})`);
			assert.ok(!k['max-width'], `Messaufbau: Karte ${i} hat max-width — nicht modelliert`);
			return { grow: Number(f[0]), basis: px(f[2], `flex-basis Karte ${i}`) };
		});
		const out: number[][] = [];
		let zeile: typeof items = [];
		let summe = 0;
		const schliesse = () => {
			const frei = w - summe - gap * (zeile.length - 1);
			const wachstum = zeile.reduce((a, b) => a + b.grow, 0);
			out.push(zeile.map((it) => it.basis + (wachstum > 0 && frei > 0 ? (frei * it.grow) / wachstum : 0)));
		};
		for (const it of items) {
			if (zeile.length && summe + gap * zeile.length + it.basis > w) {
				schliesse();
				zeile = [];
				summe = 0;
			}
			zeile.push(it);
			summe += it.basis;
		}
		if (zeile.length) schliesse();
		return out;
	}
	assert.fail(`Messaufbau: unbekanntes Raster-Layout „display: ${r['display']}"`);
}

/** Desktop-Rasterbreiten: Viewport 900 px (minus Seitenleiste/Ränder) bis breit. */
const BREITEN = Array.from({ length: (1400 - 560) / 10 + 1 }, (_, i) => 560 + i * 10);

function pruefeFuellung(html: string, versandTestid: string, erwarteteKarten: number) {
	const { raster: r, karten } = raster(html, versandTestid);
	assert.equal(karten.length, erwarteteKarten, `Messaufbau: ${karten.length} statt ${erwarteteKarten} Karten im Raster`);
	const fehler: string[] = [];
	for (const w of BREITEN) {
		for (const [i, z] of zeilen(r, karten, w).entries()) {
			const gap = px(r['column-gap'] ?? r['gap'], 'gap');
			const belegt = z.reduce((a, b) => a + b, 0) + gap * (z.length - 1);
			if (belegt / w < 0.9) fehler.push(`Raster ${w} px, Zeile ${i + 1}: ${z.length} Karte(n) belegen ${Math.round(belegt)} px`);
		}
	}
	assert.deepEqual(fehler, [], `Zeilen mit leerer Fläche (Raster-Stil ${JSON.stringify(r)}):\n${fehler.slice(0, 8).join('\n')}`);
}

// ── Zusicherungen ────────────────────────────────────────────────────────────

describe('#2794 B3: Karten-Raster der Übersicht füllt jede Zeile (Desktop)', () => {
	test('AC-7 Orts-Vergleich: drei Karten — keine Karte allein in halber Breite, bei keiner Rasterbreite 560–1400 px', () => {
		const html = render(HubUebersicht, { props: { context: 'vergleich', preset: PRESET, orte: ORTE } }).body;
		pruefeFuellung(html, 'compare-hub-versand-edit', 3);
	});

	test('AC-6 Trip: die Versand-Karte füllt die Zeile, bei jeder Rasterbreite 560–1400 px', () => {
		const html = render(HubUebersicht, { props: { context: 'route', trip: TRIP } }).body;
		pruefeFuellung(html, 'hub-uebersicht-versand-edit', 1);
	});

	test('Gegenprobe des Rechners: `1fr 1fr` mit einer Karte ist rot (halbe Breite)', () => {
		const r = { display: 'grid', 'grid-template-columns': '1fr 1fr', gap: '16px' };
		const breiten = zeilen(r, [{}], 800);
		assert.ok(breiten[0][0] / 800 < 0.9, 'Rechner erkennt die halbe Breite nicht');
	});
});
