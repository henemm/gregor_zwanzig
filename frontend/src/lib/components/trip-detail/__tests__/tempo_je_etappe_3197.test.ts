// TDD RED: Issue #3197 (Workflow feat-3197-tempo-je-etappe) — Tempo je Etappe im Reiter Etappen.
// Spec: docs/specs/modules/feat_3197_tempo_je_etappe.md — AC-1, AC-2, AC-6, AC-7, AC-10
//
// Gemessen am Wirkort, ECHTE Komponenten, kein Mock:
//   - EditStagesPanelNew serverseitig gerendert (Hub-Liste, aufgeklappter Editor, Handy-Karte
//     StageCardM über den F8-Hook als `$state`-Startwert) mit den Etappen der Falltabelle
//     tests/fixtures/naismith_dav_paritaet.json → etappen_ueberschreibung (S1 folgt dem Trip
//     zu Fuß 4 km/h, S2 trägt grundtempo_kmh 3).
//   - Das ECHTE Instanz-Skript des Panels (svelteInstanzPruefstand): `tempoAendern` mit neuer
//     Fortbewegung verwirft alle Etappen-Überschreibungen und merkt sich die Zahl für den Hinweis.
//   - TempoKarteInhalt mit Prop `nurGrundtempo` (Karte „Tempo ändern" einer Etappe).
//
// ── VERTRAG für den Developer (von RED festgelegt) ──────────────────────────────────────
// Etappen-Listenzeile (Hub, listeZuerst): je Etappe mit Wegpunkten ein Knopf
//   [data-testid="etappen-tempo-aendern"] mit Text aus trip.hub.tempo_aendern; Pausentag: keiner.
//   Etappe mit eigenem Tempo zeigt in ihrer Zeile den Katalogtext trip.tempo.eigenes_tempo.
// Panel-Instanz: `let zurueckgesetztAnzahl = $state(0)`; tempoAendern(neu) mit anderer Fortbewegung
//   setzt `stages` auf verwirfEtappenTempo(stages).stages und zurueckgesetztAnzahl auf deren anzahl;
//   gleiche Fortbewegung (nur Grundtempo) lässt Etappen-Überschreibungen stehen. Der Hinweis
//   (trip.tempo.etappen_zurueckgesetzt.one/.other via $tn) erscheint nur bei anzahl > 0.
// TempoKarteInhalt: Prop `nurGrundtempo?: boolean` blendet die Fortbewegungs-Chips aus, zeigt das
//   Grundtempo-Feld (tempo-grundtempo) und den Knopf [data-testid="tempo-trip-verwenden"] mit Text
//   trip.tempo.trip_tempo_verwenden (Rückruf-Prop `ontriptempo?: () => void`). Ohne nurGrundtempo:
//   kein solcher Knopf, Hinweis „… je Etappe überschreibbar …".
// ─────────────────────────────────────────────────────────────────────────────────────
//
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types \
//     --experimental-test-module-mocks --test src/lib/components/trip-detail/__tests__/tempo_je_etappe_3197.test.ts

import { test, describe, afterEach } from 'node:test';
import assert from 'node:assert/strict';
import path from 'node:path';
import { readFileSync } from 'node:fs';
import { pathToFileURL } from 'node:url';

const T = await import('./f9Pruefstand.ts');
const { render } = await import('svelte/server');
const { createRawSnippet } = await import('svelte');
const P = await import('../../shared/__tests__/svelteInstanzPruefstand.ts');
const { baum, alle, text: rohText } = await import('../../shared/hub-kopf/__tests__/htmlBaum.ts');
type Knoten = Record<string, any>; // eslint-disable-line @typescript-eslint/no-explicit-any

const PANEL = path.join(T.KOMP, 'edit', 'EditStagesPanelNew.svelte');
const TEMPO_INHALT = path.join(T.KOMP, 'organisms', 'tempo-karte', 'TempoKarteInhalt.svelte');
const { locale, trFor } = T;
afterEach(() => locale.set('de'));

const TABELLE = JSON.parse(readFileSync(path.resolve(T.FRONTEND, '..', 'tests', 'fixtures', 'naismith_dav_paritaet.json'), 'utf-8'));
const UE = TABELLE.etappen_ueberschreibung;
const TRIP_TEMPO = UE.tempo;
const PAUSE = { id: 'S3', name: 'Ruhetag', date: '2026-07-03', waypoints: [] };
const etappen = () => [...structuredClone(UE.stages), structuredClone(PAUSE)];

const variante = async (ersetzungen: [string, string][]) =>
	(await import(`${pathToFileURL(PANEL).href}?f8variante=${Buffer.from(JSON.stringify(ersetzungen)).toString('base64url')}`)).default;
const kopf = () => createRawSnippet(() => ({ render: () => '<div data-testid="probe-kopf">Etappen</div>' }));
const entity = (s: string) => s.replace(/&amp;/g, '&').replace(/&nbsp;/g, ' ').replace(/&lt;/g, '<').replace(/&gt;/g, '>').replace(/&quot;/g, '"').replace(/&#39;/g, "'");
const text = (k: Knoten) => entity(rohText(k as never)).replace(/\s+/g, ' ').trim();
const mitTestid = (b: Knoten, id: string) => alle(b as never, (n: Knoten) => n.attrs['data-testid'] === id);

async function panelBaum(lang: 'de' | 'en', start: [string, string][] = [], extra: Record<string, unknown> = {}): Promise<Knoten> {
	const K = await variante(start);
	locale.set(lang);
	try {
		return baum(render(K, { props: { stages: etappen(), tripId: 't', showSave: false, tempo: TRIP_TEMPO, kopf: kopf(), listeZuerst: true, ...extra } }).body);
	} finally {
		locale.set('de');
	}
}

/** Text des Abschnitts ab [data-testid=testid] im rohen HTML (wie tempo_panel_3196_fixloop3). */
function abschnitt(h: string, testid: string): string {
	const i = h.indexOf(`data-testid="${testid}"`);
	assert.ok(i >= 0, `[data-testid=${testid}] fehlt`);
	return h.slice(i, i + 4000).replace(/<[^>]+>/g, ' ').replace(/\s+/g, ' ');
}

// ═══ Hub-Liste: Gehzeit, Kennzeichen, Knopf (AC-1, AC-2, AC-7, AC-10) ═══════════════════
describe('#3197 Etappen-Liste im Hub', () => {
	for (const lang of ['de', 'en'] as const) {
		test(`${lang}: S1 Gehzeit 4:12, S2 eigenes Tempo 5:36, Knopf „Tempo ändern" nur mit Wegpunkten`, async () => {
			const b = await panelBaum(lang);
			const zeilen = mitTestid(b, 'etappen-liste-zeile');
			assert.equal(zeilen.length, 3, `Messaufbau: ${zeilen.length} Zeilen`);
			const [z1, z2, z3] = zeilen.map(text);
			const gz = (d: string) => trFor(lang, 'trip.hub.etappe_gehzeit', { dauer: d });
			assert.ok(z1.includes(gz('4:12')), `S1: ${z1}`);
			assert.ok(z2.includes(gz('5:36')) && !z2.includes(gz('4:12')), `S2 rechnet nicht mit eigenem Tempo: ${z2}`);
			const knopfText = trFor(lang, 'trip.hub.tempo_aendern');
			for (const [i, zk] of zeilen.slice(0, 2).entries()) {
				const k = mitTestid(zk, 'etappen-tempo-aendern');
				assert.equal(k.length, 1, `Zeile ${i + 1}: Knopf „Tempo ändern" fehlt`);
				assert.equal(k[0].tag, 'button');
				assert.equal(text(k[0]), knopfText);
			}
			assert.equal(mitTestid(zeilen[2], 'etappen-tempo-aendern').length, 0, 'Pausentag zeigt „Tempo ändern"');
			assert.ok(!z3.includes(knopfText), `Pausentag: ${z3}`);
			const marke = trFor(lang, 'trip.tempo.eigenes_tempo');
			assert.ok(marke && !marke.startsWith('trip.'), `Katalog ${lang}: trip.tempo.eigenes_tempo fehlt`);
			assert.ok(z2.includes(marke), `S2 nicht als eigenes Tempo gekennzeichnet: ${z2}`);
			assert.ok(!z1.includes(marke), `S1 fälschlich gekennzeichnet: ${z1}`);
		});
	}

	test('AC-2: aufgeklappter Editor von S2 zeigt 11:20/13:36, S1 10:30/12:12', async () => {
		for (const [id, soll, falsch] of [['S2', ['11:20', '13:36'], ['10:30', '12:12']], ['S1', ['10:30', '12:12'], ['11:20', '13:36']]] as const) {
			const K = await variante([['let offeneEtappeId = $state<string | null>(null);', `let offeneEtappeId = $state<string | null>('${id}');`]]);
			const h = render(K, { props: { stages: etappen(), tripId: 't', showSave: false, tempo: TRIP_TEMPO, kopf: kopf(), listeZuerst: true } }).body.replace(/<[^>]+>/g, ' ');
			for (const z of soll) assert.ok(h.includes(z), `${id}: Editor ohne ${z}`);
			for (const z of falsch) assert.ok(!h.includes(z), `${id}: Editor zeigt ${z}`);
		}
	});

	test('Mobil (StageCardM): S2 aufgeklappt rechnet mit eigenem Tempo 11:20/13:36', async () => {
		const K = await variante([
			['let isMobileViewport = $state(false);', 'let isMobileViewport = $state(true);'],
			['let expandedStageId = $state<string | null>(null);', "let expandedStageId = $state<string | null>('S2');"]
		]);
		const h = render(K, { props: { stages: etappen(), tripId: 't', showSave: false, tempo: TRIP_TEMPO } }).body.replace(/<!--[\s\S]*?-->/g, '');
		const t = abschnitt(h, 'stage-cardm-wp-rows');
		for (const z of ['11:20', '13:36']) assert.ok(t.includes(z), `StageCardM S2 ohne ${z}: ${t.slice(0, 300)}`);
		for (const z of ['10:30', '12:12']) assert.ok(!t.includes(z), `StageCardM S2 zeigt Trip-Zeit ${z}`);
	});
});

// ═══ Fortbewegungswechsel im Panel verwirft Überschreibungen (AC-6) ═════════════════════
describe('#3197 AC-6: tempoAendern im echten Panel-Skript', () => {
	async function panel(stages: unknown[]) {
		const gespeichert: number[] = [];
		const { u } = await P.umgebungFuer(PANEL, {
			stages,
			tripId: 't',
			showSave: false,
			tempo: { ...TRIP_TEMPO },
			scheduleSave: () => gespeichert.push(1)
		});
		assert.equal(typeof u.tempoAendern, 'function', 'Messaufbau: tempoAendern nicht herleitbar');
		return { u, gespeichert };
	}
	const zwei = () => {
		const s = etappen();
		s[0] = { ...s[0], grundtempo_kmh: 5 };
		return s;
	};

	test('zwei überschriebene Etappen, Wechsel zu Fuß → Rad: Felder weg, Hinweiszahl 2, übrige Felder bleiben', async () => {
		const p = await panel(zwei());
		assert.equal(p.u.zurueckgesetztAnzahl, 0, 'TDD RED: $state zurueckgesetztAnzahl fehlt oder startet nicht bei 0');
		p.u.tempoAendern({ fortbewegung: 'rad', grundtempo_kmh: 20 });
		assert.equal(p.u.stages.length, 3);
		for (const s of p.u.stages) assert.ok(!('grundtempo_kmh' in s), `${s.id}: Etappen-Tempo nicht verworfen`);
		assert.deepEqual(p.u.stages.map((s: Knoten) => s.waypoints.length), [3, 3, 0], 'Wegpunkte verändert');
		assert.equal(p.u.zurueckgesetztAnzahl, 2, 'Hinweis nennt nicht 2 Etappen');
		assert.ok(p.gespeichert.length >= 1, 'Wechsel löst kein Speichern aus');
	});

	test('nur Grundtempo geändert (gleiche Fortbewegung): Überschreibungen bleiben, kein Hinweis', async () => {
		const p = await panel(zwei());
		p.u.tempoAendern({ fortbewegung: 'fuss', grundtempo_kmh: 5 });
		assert.deepEqual(p.u.stages.map((s: Knoten) => s.grundtempo_kmh), [5, 3, undefined]);
		assert.equal(p.u.zurueckgesetztAnzahl, 0);
	});

	test('Wechsel ohne betroffene Etappe: kein Hinweis (anzahl 0)', async () => {
		const p = await panel(etappen().map(({ grundtempo_kmh: _x, ...s }: Knoten) => s));
		p.u.tempoAendern({ fortbewegung: 'mtb', grundtempo_kmh: 12 });
		assert.equal(p.u.zurueckgesetztAnzahl, 0);
	});
});

// ═══ TempoKarteInhalt mit nurGrundtempo (AC-4, AC-10) ═══════════════════════════════════
describe('#3197 TempoKarteInhalt nurGrundtempo', () => {
	const html = async (props: Record<string, unknown>, lang: 'de' | 'en' = 'de') => {
		const K = (await import(pathToFileURL(TEMPO_INHALT).href)).default;
		locale.set(lang);
		try {
			return baum(render(K, { props }).body);
		} finally {
			locale.set('de');
		}
	};

	for (const lang of ['de', 'en'] as const) {
		test(`${lang}: nur Grundtempo-Feld und „Trip-Tempo verwenden", keine Fortbewegung`, async () => {
			const b = await html({ tempo: { fortbewegung: 'fuss', grundtempo_kmh: 3 }, nurGrundtempo: true, ontriptempo: () => {} }, lang);
			for (const f of ['fuss', 'rad', 'mtb', 'ski']) assert.equal(mitTestid(b, `tempo-fortbewegung-${f}`).length, 0, `Chip ${f} sichtbar`);
			const [feld] = mitTestid(b, 'tempo-grundtempo');
			assert.ok(feld, 'Grundtempo-Feld fehlt');
			assert.equal(feld.attrs.value, '3');
			const knopf = mitTestid(b, 'tempo-trip-verwenden');
			assert.equal(knopf.length, 1, 'Knopf „Trip-Tempo verwenden" fehlt');
			assert.equal(knopf[0].tag, 'button');
			const soll = trFor(lang, 'trip.tempo.trip_tempo_verwenden');
			assert.ok(!soll.startsWith('trip.'), `Katalog ${lang}: trip.tempo.trip_tempo_verwenden fehlt`);
			assert.equal(text(knopf[0]), soll);
		});
	}

	test('Trip-Karte (ohne nurGrundtempo): Fortbewegung da, kein „Trip-Tempo verwenden", Hinweis überschreibbar', async () => {
		const b = await html({ tempo: { fortbewegung: 'fuss', grundtempo_kmh: 4 } });
		assert.equal(mitTestid(b, 'tempo-fortbewegung-fuss').length, 1);
		assert.equal(mitTestid(b, 'tempo-trip-verwenden').length, 0);
		assert.match(text(b), /je Etappe überschreibbar/);
	});
});
