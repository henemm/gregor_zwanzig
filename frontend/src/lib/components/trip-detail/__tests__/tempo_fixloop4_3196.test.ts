// Fix-Loop 4 — Issue #3196 (Workflow feat-3196-trip-tempo-etappen), Adversary F-A3-1/2/3/5.
// Spec: docs/specs/modules/feat_3196_trip_tempo_etappen.md — AC-4, AC-7, AC-6
//
// Gemessen dort, wo es WIRKT:
//   F-A3-1 (AC-4) Das ECHTE Instanz-Skript des Etappen-Panels (svelteInstanzPruefstand): der Klick
//                 auf Rad (tempoAendern) wirkt SOFORT, ohne neue Prop — die Karte zeigt Rad/20, die
//                 Gehzeit der Listenzeile und die Ankunftszeiten folgen DAV-Rad. Die `$derived`-
//                 Herleitungen werden nach dem Klick aus ihrem ECHTEN Quelltext neu ausgewertet
//                 (so wie Svelte sie neu ausfuehrt), die Listenzeile aus dem ECHTEN `{@const}`.
//   F-A3-2 (AC-7) Der ECHTE Anlege-Editor, serverseitig gerendert (Handy und Desktop): genau eine
//                 Tempo-Karte im Dokument, im richtigen Markup-Baum.
//   F-A3-3 (AC-7, Datenverlust-Schutz) Das ECHTE Effekt-Skript von WeatherMetricsTab mit der ECHTEN
//                 applyPreset: im Bearbeiten-Modus (Bestandstrip mit tempo Rad) und bei ungesichertem
//                 Stand ueberschreibt der Vorlagen-Effekt die Metrikwahl nicht und markiert nichts als
//                 Nutzer-Aenderung (userTouched ist das Gate des Autosave, weatherSaveGate).
//   F-A3-5 (AC-6) tempoVonTrip zeigt nie ein Tempo, mit dem die Rechner nicht rechnen.
//
//   cd frontend && npm test -- src/lib/components/trip-detail/__tests__/tempo_fixloop4_3196.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import path from 'node:path';

const T = await import('./f9Pruefstand.ts');
const P = await import('../../shared/__tests__/svelteInstanzPruefstand.ts');
const { umgebungFuer, effekteVon, findeKomponenten, attributAusdruck, werte, ohneTypen } = P;
const SSR = await import('../../trip-new/__tests__/tripNewSsr.ts');
const N = await import('../../../utils/naismith.ts');
type Knoten = Record<string, any>; // eslint-disable-line @typescript-eslint/no-explicit-any

const PANEL = path.join(T.KOMP, 'edit', 'EditStagesPanelNew.svelte');
const WMT = path.join(T.KOMP, 'shared', 'WeatherMetricsTab.svelte');

// Etappe wie tempo_panel_3196_fixloop3: A (0 km, 1000 m) → B (4 km, 1600 m) → C (8 km, 1000 m), 08:00.
//   zu Fuss 4: 10:30, 12:12, Gehzeit 4:12 — Rad 20: 09:06, 09:48, Gehzeit 1:48
const etappe = () => [{
	id: 's1', name: 'Tag 1', date: '2026-07-01', start_time: '08:00',
	waypoints: [
		{ id: 'A', name: 'Alm', lat: 47, lon: 11, elevation_m: 1000, distance_from_start_km: 0 },
		{ id: 'B', name: 'Gipfel', lat: 47, lon: 11, elevation_m: 1600, distance_from_start_km: 4 },
		{ id: 'C', name: 'Huette', lat: 47, lon: 11, elevation_m: 1000, distance_from_start_km: 8 }
	]
}];

/** Wertet die `$derived`-Deklarationen `namen` aus ihrem ECHTEN Quelltext neu aus (Quelltext-Reihenfolge). */
function neuHerleiten(ast: Knoten, quelle: string, u: Knoten, namen: string[]): void {
	for (const stmt of ast.instance.content.body as Knoten[]) {
		if (stmt.type !== 'VariableDeclaration') continue;
		for (const d of stmt.declarations as Knoten[]) {
			if (d.id?.type === 'Identifier' && namen.includes(d.id.name)) u[d.id.name] = werte(ohneTypen(quelle, d.init), u);
		}
	}
}

/** Das ECHTE `{@const name = …}` im Markup, ausgewertet gegen `u` plus Snippet-Parameter. */
function constTag(ast: Knoten, quelle: string, u: Knoten, name: string, lokal: Knoten): unknown {
	let treffer: Knoten | null = null;
	(function lauf(n: unknown): void {
		if (treffer || n === null || typeof n !== 'object') return;
		if (Array.isArray(n)) return n.forEach(lauf);
		const k = n as Knoten;
		if (k.type === 'ConstTag' && k.declaration?.declarations?.[0]?.id?.name === name) {
			treffer = k.declaration.declarations[0];
			return;
		}
		for (const key of Object.keys(k)) if (key !== 'parent' && key !== 'loc') lauf(k[key]);
	})(ast.fragment);
	assert.ok(treffer, `Messaufbau: {@const ${name}} fehlt im Markup`);
	const umgebung = Object.assign(Object.create(u), lokal);
	return werte(ohneTypen(quelle, (treffer as Knoten).init), umgebung);
}

// ── F-A3-1 (AC-4): der Klick wirkt sofort, ohne neue Prop ────────────────────

describe('F-A3-1 (AC-4): Wahl im Panel wirkt sofort auf Karte, Gehzeit und Ankuenfte', () => {
	async function panel() {
		const gespeichert: number[] = [];
		const { ast, quelle, u } = await umgebungFuer(PANEL, {
			stages: etappe(),
			tripId: 't',
			showSave: false,
			tempo: { ...N.STANDARD_TEMPO },
			scheduleSave: () => gespeichert.push(1)
		});
		assert.equal(typeof u.tempoAendern, 'function', 'Messaufbau: tempoAendern nicht herleitbar');
		const karte = findeKomponenten(ast, 'TempoKarte');
		assert.equal(karte.length, 1, 'Messaufbau: genau eine TempoKarte im Panel erwartet');
		const karteTempo = () => werte(attributAusdruck(karte[0], quelle, 'tempo')!, u) as Knoten;
		const zeile = () => constTag(ast, quelle, u, 'zeile', { stage: u.stages[0], i: 0 }) as Knoten;
		return { ast, quelle, u, gespeichert, karteTempo, zeile };
	}

	test('Ausgangslage zu Fuss 4: Karte, Gehzeit 4:12, Ankuenfte 10:30/12:12', async () => {
		const p = await panel();
		assert.deepEqual(p.karteTempo(), { fortbewegung: 'fuss', grundtempo_kmh: 4 });
		assert.ok(String(p.zeile().meta).includes('4:12'), `Listenzeile: ${p.zeile().meta}`);
		assert.deepEqual(p.u.arrivals, ['08:00', '10:30', '12:12']);
	});

	test('tempoAendern(Rad 20) OHNE neue Prop ⇒ Karte Rad/20, Gehzeit 1:48, Ankuenfte 09:06/09:48', async () => {
		const p = await panel();
		p.u.tempoAendern({ fortbewegung: 'rad', grundtempo_kmh: 20 });
		assert.equal(p.gespeichert.length, 1, 'Wahl loest kein Speichern aus');
		// Prop bleibt zu Fuss 4 (Serverantwort steht noch aus).
		assert.deepEqual(p.u.tempo, { fortbewegung: 'fuss', grundtempo_kmh: 4 });
		neuHerleiten(p.ast, p.quelle, p.u, ['tempoAktiv', 'arrivals']);
		assert.deepEqual(p.karteTempo(), { fortbewegung: 'rad', grundtempo_kmh: 20 }, 'Karte zeigt nicht sofort Rad/20');
		const meta = String(p.zeile().meta);
		assert.ok(meta.includes('1:48') && !meta.includes('4:12'), `Listenzeile nicht sofort DAV-Rad: ${meta}`);
		assert.deepEqual(p.u.arrivals, ['08:00', '09:06', '09:48'], 'Ankuenfte nicht sofort DAV-Rad');
	});
});

// ── F-A3-2 (AC-7): genau eine Tempo-Karte beim Anlegen, Handy und Desktop ────

describe('F-A3-2 (AC-7): Anlege-Dialog zeigt genau eine Tempo-Karte', () => {
	for (const [name, mobil, baum] of [['Desktop', false, 'desktop'], ['Handy', true, 'mobil']] as const) {
		test(`${name}: genau eine Karte, im ${baum}-Baum`, () => {
			const html = SSR.renderTripNew({ activeTab: 'route', isMobileViewport: mobil });
			assert.equal(SSR.countTestid(html, 'tempo-karte'), 1, `${name}: ${SSR.countTestid(html, 'tempo-karte')} Tempo-Karten`);
			assert.equal(SSR.bereichVon(html, 'tempo-karte'), baum, `${name}: Karte im falschen Markup-Baum`);
		});
	}
});

// ── F-A3-3 (AC-7, Datenverlust-Schutz): Vorlage nur beim Anlegen ─────────────

describe('F-A3-3: der Vorlagen-Effekt ueberschreibt keine Bestandswahl', () => {
	const EIGENE = { primary: ['temp', 'wind'], secondary: [], off: [] };
	async function wetterReiter(saat: Knoten) {
		const { ast, quelle, u } = await umgebungFuer(WMT, {
			trip: { id: 't1', tempo: { fortbewegung: 'rad', grundtempo_kmh: 20 } },
			templates: [
				{ id: 'alpen-trekking', metrics: ['temp', 'rain'] },
				{ id: 'radtour', metrics: ['wind_gust', 'rain', 'temp'] },
				{ id: 'skitouren', metrics: ['snow'] }
			],
			catalog: {},
			userPresets: [],
			buckets: structuredClone(EIGENE),
			...saat
		});
		assert.equal(typeof u.applyPreset, 'function', 'Messaufbau: applyPreset nicht herleitbar (muss die ECHTE sein)');
		const effekte = effekteVon(ast, quelle, u, 'FORTBEWEGUNG_TO_TEMPLATE');
		assert.equal(effekte.length, 1, 'Messaufbau: Vorlagen-Effekt nicht gefunden');
		effekte[0]();
		return u;
	}

	test('Positivkontrolle Anlegen (createMode, sauber): Vorlage radtour wird angewendet', async () => {
		const u = await wetterReiter({ createMode: true, isDirty: false });
		assert.equal(u.selectedTemplate, 'radtour');
		assert.deepEqual(u.buckets.primary, ['wind_gust', 'rain', 'temp']);
	});

	test('Bearbeiten (createMode false), Trip mit tempo Rad: Metrikwahl bleibt, kein Speicher-Anstoss', async () => {
		const u = await wetterReiter({ createMode: false, isDirty: false });
		assert.deepEqual(u.buckets, EIGENE, 'Bestandswahl durch die Vorlage ersetzt');
		assert.notEqual(u.selectedTemplate, 'radtour');
		assert.equal(u.userTouched, false, 'userTouched gesetzt — der Autosave wuerde die Vorlage speichern');
	});

	test('Anlegen mit ungesichertem Stand (isDirty): Metrikwahl bleibt', async () => {
		const u = await wetterReiter({ createMode: true, isDirty: true });
		assert.deepEqual(u.buckets, EIGENE, 'ungesicherte Wahl durch die Vorlage ersetzt');
		assert.equal(u.userTouched, false);
	});
});

// ── F-A3-5 (AC-6): Anzeige = Rechnung ────────────────────────────────────────

describe('F-A3-5: tempoVonTrip zeigt nur, womit gerechnet wird', () => {
	for (const [name, tempo] of [
		['Grundtempo 0', { fortbewegung: 'rad', grundtempo_kmh: 0 }],
		['Grundtempo 99', { fortbewegung: 'fuss', grundtempo_kmh: 99 }],
		['unbekannte Fortbewegung', { fortbewegung: 'boot', grundtempo_kmh: 5 }]
	] as const) {
		test(`ungueltiges gespeichertes Tempo (${name}) ⇒ zu Fuss 4, wie die Rechner`, () => {
			const trip = { tempo: tempo as unknown as Knoten, activity: 'fahrrad_20' };
			const angezeigt = N.tempoVonTrip(trip as never);
			assert.deepEqual(angezeigt, N.STANDARD_TEMPO);
			const gerechnet = N.tripTempo(trip as never);
			assert.equal(angezeigt.fortbewegung, gerechnet.fortbewegung);
			assert.equal(angezeigt.grundtempo_kmh, gerechnet.grundtempo_kmh);
		});
	}

	test('gueltiges gespeichertes Tempo bleibt, fehlendes wird aus activity abgeleitet', () => {
		assert.deepEqual(N.tempoVonTrip({ tempo: { fortbewegung: 'ski', grundtempo_kmh: 2.5 } }), { fortbewegung: 'ski', grundtempo_kmh: 2.5 });
		assert.deepEqual(N.tempoVonTrip({ activity: 'fahrrad_20' }), { fortbewegung: 'rad', grundtempo_kmh: 20 });
	});
});
