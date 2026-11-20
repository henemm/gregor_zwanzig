// TDD RED (Nacharbeit): Issue #3197 — Tempo je Etappe in der MOBILEN Etappen-Liste (DoD „Desktop und mobil").
// Spec: docs/specs/modules/feat_3197_tempo_je_etappe.md — AC-1, AC-2, AC-4, AC-7, AC-10
//
// Gemessen am Wirkort, ECHTE Komponenten, kein Mock: EditStagesPanelNew serverseitig gerendert im
// Mobil-Zweig (isMobileViewport per F8-Variante) mit den Etappen der Falltabelle
// tests/fixtures/naismith_dav_paritaet.json → etappen_ueberschreibung (S1 Trip-Tempo, S2 3 km/h)
// plus Pausentag S3.
//
// ── VERTRAG ─────────────────────────────────────────────────────────────────────────────
// StageCardM zeigt je Etappe mit Wegpunkten „Gehzeit h:mm" (aus etappenZeile, gleiche Rechnung wie
//   Desktop), bei eigenem Tempo das Kennzeichen trip.tempo.eigenes_tempo und einen Knopf
//   [data-testid="mobile-etappen-tempo-aendern"] (Text trip.hub.tempo_aendern). Pausentag: nichts davon.
// Offene Etappen-Tempo-Karte = derselbe Panel-Zustand `tempoEtappeId` wie Desktop; in der Karte der
//   Etappe steht TempoKarteInhalt mit nurGrundtempo (Grundtempo-Feld mit dem Etappenwert, Knopf
//   tempo-trip-verwenden, keine Fortbewegungs-Chips).
// ─────────────────────────────────────────────────────────────────────────────────────
//
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types \
//     --experimental-test-module-mocks --test src/lib/components/trip-detail/__tests__/tempo_je_etappe_3197_mobil.test.ts

import { test, describe, afterEach } from 'node:test';
import assert from 'node:assert/strict';
import path from 'node:path';
import { readFileSync } from 'node:fs';
import { pathToFileURL } from 'node:url';

const T = await import('./f9Pruefstand.ts');
const { render } = await import('svelte/server');
const { baum, alle, text: rohText } = await import('../../shared/hub-kopf/__tests__/htmlBaum.ts');
type Knoten = Record<string, any>; // eslint-disable-line @typescript-eslint/no-explicit-any

const PANEL = path.join(T.KOMP, 'edit', 'EditStagesPanelNew.svelte');
const { locale, trFor } = T;
afterEach(() => locale.set('de'));

const TABELLE = JSON.parse(readFileSync(path.resolve(T.FRONTEND, '..', 'tests', 'fixtures', 'naismith_dav_paritaet.json'), 'utf-8'));
const UE = TABELLE.etappen_ueberschreibung;
const TRIP_TEMPO = UE.tempo;
const PAUSE = { id: 'S3', name: 'Ruhetag', date: '2026-07-03', waypoints: [] };
const etappen = () => [...structuredClone(UE.stages), structuredClone(PAUSE)];

const MOBIL: [string, string] = ['let isMobileViewport = $state(false);', 'let isMobileViewport = $state(true);'];
const variante = async (ersetzungen: [string, string][]) =>
	(await import(`${pathToFileURL(PANEL).href}?f8variante=${Buffer.from(JSON.stringify(ersetzungen)).toString('base64url')}`)).default;
const entity = (s: string) => s.replace(/&amp;/g, '&').replace(/&nbsp;/g, ' ').replace(/&lt;/g, '<').replace(/&gt;/g, '>').replace(/&quot;/g, '"').replace(/&#39;/g, "'");
const text = (k: Knoten) => entity(rohText(k as never)).replace(/\s+/g, ' ').trim();
const mitTestid = (b: Knoten, id: string): Knoten[] => alle(b as never, (n: Knoten) => n.attrs['data-testid'] === id);

async function karten(lang: 'de' | 'en', extra: [string, string][] = []): Promise<Knoten[]> {
	const K = await variante([MOBIL, ...extra]);
	locale.set(lang);
	try {
		const b = baum(render(K, { props: { stages: etappen(), tripId: 't', showSave: false, tempo: TRIP_TEMPO } }).body.replace(/<!--[\s\S]*?-->/g, ''));
		const k = mitTestid(b, 'stage-cardm');
		assert.equal(k.length, 3, `Messaufbau: ${k.length} mobile Karten`);
		return k;
	} finally {
		locale.set('de');
	}
}

describe('#3197 mobil: Gehzeit, Kennzeichen und „Tempo ändern" in StageCardM', () => {
	for (const lang of ['de', 'en'] as const) {
		test(`${lang}: S1 Gehzeit 4:12, S2 eigenes Tempo 5:36, Knopf nur mit Wegpunkten`, async () => {
			const [k1, k2, k3] = await karten(lang);
			const gz = (d: string) => trFor(lang, 'trip.hub.etappe_gehzeit', { dauer: d });
			assert.ok(text(k1).includes(gz('4:12')), `S1: ${text(k1)}`);
			assert.ok(text(k2).includes(gz('5:36')) && !text(k2).includes(gz('4:12')), `S2 rechnet nicht mit eigenem Tempo: ${text(k2)}`);
			const gzWort = gz('§').replace('§', '').trim();
			assert.ok(gzWort.length > 0 && !text(k3).includes(gzWort), `Pausentag zeigt Gehzeit: ${text(k3)}`);
			const marke = trFor(lang, 'trip.tempo.eigenes_tempo');
			assert.ok(text(k2).includes(marke), `S2 nicht gekennzeichnet: ${text(k2)}`);
			assert.ok(!text(k1).includes(marke), `S1 fälschlich gekennzeichnet`);
			const knopfText = trFor(lang, 'trip.hub.tempo_aendern');
			for (const [i, k] of [k1, k2].entries()) {
				const kn = mitTestid(k, 'mobile-etappen-tempo-aendern');
				assert.equal(kn.length, 1, `Karte ${i + 1}: Knopf „Tempo ändern" fehlt`);
				assert.equal(kn[0].tag, 'button');
				assert.equal(text(kn[0]), knopfText);
			}
			assert.equal(mitTestid(k3, 'mobile-etappen-tempo-aendern').length, 0, 'Pausentag zeigt „Tempo ändern"');
		});
	}

	test('offene Etappen-Tempo-Karte (gleicher Panel-Zustand wie Desktop): nurGrundtempo mit Etappenwert 3', async () => {
		const [k1, k2] = await karten('de', [['let tempoEtappeId = $state<string | null>(null);', "let tempoEtappeId = $state<string | null>('S2');"]]);
		assert.equal(mitTestid(k1, 'tempo-karte').length, 0, 'S1 zeigt fremde Tempo-Karte');
		const [karte] = mitTestid(k2, 'tempo-karte');
		assert.ok(karte, 'S2: Tempo-Karte fehlt');
		for (const f of ['fuss', 'rad', 'mtb', 'ski']) assert.equal(mitTestid(karte, `tempo-fortbewegung-${f}`).length, 0, `Chip ${f} sichtbar`);
		assert.equal(mitTestid(karte, 'tempo-grundtempo')[0]?.attrs.value, '3');
		const zurueck = mitTestid(karte, 'tempo-trip-verwenden');
		assert.equal(zurueck.length, 1, 'Knopf „Trip-Tempo verwenden" fehlt');
		assert.equal(text(zurueck[0]), 'Trip-Tempo verwenden');
		assert.equal(mitTestid(k2, 'mobile-etappen-tempo-aendern')[0].attrs['aria-expanded'], 'true');
	});
});
