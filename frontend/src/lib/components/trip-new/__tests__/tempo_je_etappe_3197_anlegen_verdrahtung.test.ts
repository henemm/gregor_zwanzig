// Fix-Loop 3 — Issue #3197 (Workflow feat-3197-tempo-je-etappe), Adversary F001/F002/F003.
// Spec: docs/specs/modules/feat_3197_tempo_je_etappe.md — AC-2, AC-4, AC-5, AC-6 im ANLEGEN.
//
// Die reinen Brückenfunktionen (tripNewLogic.ts) sind in tempo_je_etappe_3197_anlegen.test.ts
// bewacht. Hier wird die VERDRAHTUNG in TripNewEditor.svelte gemessen, dort, wo der Nutzer sie
// erreicht (Muster f002_trip_anlegen_ampel_im_post.test.ts / trip_new_alarme_verdrahtung.test.ts):
//   - ECHTES Instanz-Skript (svelteInstanzPruefstand.ts), Rückrufe aus den ECHTEN Attribut-
//     Ausdrücken der Einbettungen (TempoKarte.onchange, EditStagesPanelNew.tempo),
//   - der POST wird am gesäten `api.post` mitgeschnitten (durchläuft den echten
//     buildCreateTripPayload, F001: einziger Pfad für den Etappen-Rumpf),
//   - der Hinweis zu zurückgesetzten Etappen aus dem ECHTEN SSR-Render (f8variante setzt nur den
//     Startwert `etappenZurueckgesetzt`, der Wert kommt aus dem echten Handler).
//
//   cd frontend && npm test -- src/lib/components/trip-new/__tests__/tempo_je_etappe_3197_anlegen_verdrahtung.test.ts

import { test, describe, afterEach } from 'node:test';
import assert from 'node:assert/strict';
import path from 'node:path';
import { pathToFileURL } from 'node:url';

// Registriert die SSR-Hooks (Runen, $app, .svelte-Compiler, f8variante).
const T = await import('../../trip-detail/__tests__/f9Pruefstand.ts');
const { umgebungFuer, findeKomponenten, attributAusdruck, werte } = await import('../../shared/__tests__/svelteInstanzPruefstand.ts');
const { render } = await import('svelte/server');
const { baum, alle, text: rohText } = await import('../../shared/hub-kopf/__tests__/htmlBaum.ts');
type Knoten = Record<string, any>; // eslint-disable-line @typescript-eslint/no-explicit-any

const EDITOR = path.join(T.KOMP, 'trip-new', 'TripNewEditor.svelte');
const { locale } = T;
afterEach(() => locale.set('de'));

const FUSS = { fortbewegung: 'fuss', grundtempo_kmh: 4 };
const RAD = { fortbewegung: 'rad', grundtempo_kmh: 20 };

const wps = (p: string) => [
	{ id: `${p}a`, name: 'A', lat: 47, lon: 11, elevation_m: 1000 },
	{ id: `${p}b`, name: 'B', lat: 47.02, lon: 11.02, elevation_m: 1600 }
];
/** Anlege-Zustand mit drei Etappen; `tempi[i]` = Etappen-Tempo (undefined = folgt dem Trip). */
const anlage = (tempi: (number | undefined)[]) =>
	tempi.map((kmh, i) => ({
		id: i + 1,
		name: `Tag ${i + 1}`,
		gpx: null,
		waypoints: wps(`s${i + 1}`),
		...(kmh !== undefined ? { grundtempo_kmh: kmh } : {})
	}));

async function editor(tempi: (number | undefined)[] = [undefined, undefined, undefined]) {
	const gesendet: Array<{ url: string; payload: Knoten }> = [];
	const { ast, quelle, u } = await umgebungFuer(EDITOR, {
		stateOverride: undefined,
		untrack: (fn: () => unknown) => fn(),
		api: {
			post: async (url: string, payload: Knoten) => {
				gesendet.push({ url, payload });
				return { id: 'neu-1' };
			}
		}
	});
	for (const f of ['handleTempoChange', 'switchTab', 'buildAndSave', 'syncEditorBack', 'buildEditorStages'])
		assert.equal(typeof u[f], 'function', `Messaufbau: ${f} nicht herleitbar`);
	u.name = 'GR20';
	u.startDate = '2026-07-01';
	u.stages = anlage(tempi);
	u.selectedTempo = { ...FUSS };
	return { ast, quelle, u, gesendet };
}
type Ed = Awaited<ReturnType<typeof editor>>;

/** Die `onchange`-Rückrufe ALLER TempoKarte-Einbettungen (Desktop + mobil), aus ihrem Quelltext. */
function tempoKartenRueckrufe(ed: Ed): Array<(t: Knoten) => void> {
	const karten = findeKomponenten(ed.ast, 'TempoKarte');
	assert.equal(karten.length, 2, 'Messaufbau: TempoKarte Desktop + mobil erwartet');
	return karten.map((k, i) => {
		const ausdruck = attributAusdruck(k, ed.quelle, 'onchange');
		assert.ok(ausdruck, `TempoKarte ${i + 1}: onchange fehlt`);
		const f = werte(ausdruck!, ed.u);
		assert.equal(typeof f, 'function', `TempoKarte ${i + 1}: onchange ist keine Funktion`);
		return f as (t: Knoten) => void;
	});
}

async function speichern(ed: Ed): Promise<Knoten> {
	ed.u.ready = true; // `ready` hängt am GPX-Upload — für den Speicherweg ohne Belang
	const id = await ed.u.buildAndSave();
	assert.equal(id, 'neu-1', `buildAndSave scheiterte: ${ed.u.saveError}`);
	assert.equal(ed.gesendet.length, 1);
	assert.equal(ed.gesendet[0].url, '/api/trips');
	return ed.gesendet[0].payload;
}

const tempoIm = (stages: Knoten[]) => stages.map((s) => s.grundtempo_kmh);

// ═══ F002 (AC-6): Tempo-Karte im Anlegen ═════════════════════════════════════════════════
describe('F002 (AC-6): Fortbewegungswechsel an der echten Tempo-Karte des Anlege-Editors', () => {
	for (const [i, wo] of ['Desktop', 'mobil'].entries()) {
		test(`${wo}: Wechsel zu Fuß → Rad verwirft beide Etappen-Tempi, Anzahl 2, Tempo übernommen`, async () => {
			const ed = await editor([5, undefined, 3]);
			tempoKartenRueckrufe(ed)[i]({ ...RAD });
			assert.deepEqual(tempoIm(ed.u.stages), [undefined, undefined, undefined], 'Etappen-Überschreibungen nicht verworfen');
			for (const s of ed.u.stages) assert.ok(!('grundtempo_kmh' in s), 'Feld grundtempo_kmh bleibt stehen');
			assert.equal(ed.u.etappenZurueckgesetzt, 2, 'Anzahl zurückgesetzter Etappen nicht gesetzt');
			assert.deepEqual(ed.u.selectedTempo, RAD, 'Trip-Tempo nicht übernommen');
			// Wirkung am POST: kein Etappen-Tempo mehr, Trip fährt Rad.
			const p = await speichern(ed);
			for (const s of p.stages as Knoten[]) assert.ok(!('grundtempo_kmh' in s), 'POST trägt verworfenes Etappen-Tempo');
			assert.deepEqual(p.tempo, RAD);
		});

		test(`${wo}: nur Tempo-Wert ändern (Fortbewegung bleibt) verwirft nichts, Anzahl 0`, async () => {
			const ed = await editor([5, undefined, 3]);
			tempoKartenRueckrufe(ed)[i]({ fortbewegung: 'fuss', grundtempo_kmh: 3.5 });
			assert.deepEqual(tempoIm(ed.u.stages), [5, undefined, 3], 'Etappen-Tempo ohne Fortbewegungswechsel verworfen');
			assert.equal(ed.u.etappenZurueckgesetzt, 0);
			assert.equal(ed.u.selectedTempo.grundtempo_kmh, 3.5, 'Trip-Tempo nicht übernommen');
		});
	}

	test('Wechsel ohne überschriebene Etappe ⇒ Anzahl 0; nächster Wert-Wechsel nach Hinweis ⇒ wieder 0', async () => {
		const ohne = await editor();
		tempoKartenRueckrufe(ohne)[0]({ ...RAD });
		assert.equal(ohne.u.etappenZurueckgesetzt, 0);

		const ed = await editor([5, 4.5, undefined]);
		const [desktop] = tempoKartenRueckrufe(ed);
		desktop({ ...RAD });
		assert.equal(ed.u.etappenZurueckgesetzt, 2, 'Messaufbau');
		desktop({ fortbewegung: 'rad', grundtempo_kmh: 18 });
		assert.equal(ed.u.etappenZurueckgesetzt, 0, 'Hinweis bleibt nach der nächsten Tempo-Aktion stehen');
	});
});

// ═══ F002 (AC-6): Hinweis im echten Render ══════════════════════════════════════════════
describe('F002 (AC-6): Hinweis zu zurückgesetzten Etappen im Anlege-Editor (DOM)', () => {
	async function hinweise(anzahl: number, mobil: boolean): Promise<{ n: number; text: string }> {
		const ers: [string, string][] = [['let etappenZurueckgesetzt = $state(0);', `let etappenZurueckgesetzt = $state(${anzahl});`]];
		const K = (await import(`${pathToFileURL(EDITOR).href}?f8variante=${Buffer.from(JSON.stringify(ers)).toString('base64url')}`)).default;
		const html = render(K, { props: { stateOverride: { activeTab: 'route', isMobileViewport: mobil, name: 'GR20', startDate: '2026-07-01' } } }).body;
		const h = alle(baum(html) as never, (n: Knoten) => n.attrs['data-testid'] === 'etappen-tempo-zurueckgesetzt');
		return { n: h.length, text: h.map((x) => rohText(x as never)).join(' ').replace(/\s+/g, ' ') };
	}

	for (const mobil of [false, true]) {
		const wo = mobil ? 'mobil' : 'Desktop';
		test(`${wo}: Wechsel mit zwei überschriebenen Etappen ⇒ genau ein Hinweis „2 Etappen"`, async () => {
			const ed = await editor([5, undefined, 3]);
			tempoKartenRueckrufe(ed)[mobil ? 1 : 0]({ ...RAD });
			const d = await hinweise(ed.u.etappenZurueckgesetzt, mobil);
			assert.equal(d.n, 1, 'Hinweis fehlt');
			assert.match(d.text, /2 Etappen/);
		});

		test(`${wo}: Wechsel ohne überschriebene Etappe ⇒ kein Hinweis`, async () => {
			const ed = await editor();
			tempoKartenRueckrufe(ed)[mobil ? 1 : 0]({ ...RAD });
			assert.equal((await hinweise(ed.u.etappenZurueckgesetzt, mobil)).n, 0, 'Hinweis ohne betroffene Etappe');
		});
	}
});

// ═══ F003: Brücke Etappen-Editor ⇄ Anlege-Zustand am Wirkort ═════════════════════════════
describe('F003 (AC-2/AC-4/AC-5): Etappen-Tempo aus dem eingebetteten Etappen-Editor', () => {
	test('Verlassen des Reiters Wegpunkte schreibt gesetztes UND zurückgenommenes Etappen-Tempo zurück, POST trägt es', async () => {
		const ed = await editor([5, undefined, undefined]);
		ed.u.activeTab = 'etappen';
		ed.u.switchTab('wegpunkte');
		assert.equal(ed.u.editorStages.length, 3, 'Messaufbau: Editor-Etappen nicht aufgebaut');
		assert.equal(ed.u.editorStages[0].grundtempo_kmh, 5, 'Editor bekommt das Etappen-Tempo nicht');
		// Was der Etappen-Editor über bind:stages zurückgibt: Etappe 2 auf 3 km/h,
		// Etappe 1 „Trip-Tempo verwenden" (Feld entfernt).
		const { grundtempo_kmh: _x, ...e1 } = ed.u.editorStages[0];
		ed.u.editorStages = [e1, { ...ed.u.editorStages[1], grundtempo_kmh: 3 }, ed.u.editorStages[2]];

		ed.u.switchTab('wetter');
		assert.deepEqual(tempoIm(ed.u.stages), [undefined, 3, undefined], 'Tabwechsel verliert das Etappen-Tempo');
		assert.ok(!('grundtempo_kmh' in ed.u.stages[0]), 'AC-4: zurückgenommenes Tempo bleibt im Anlege-Zustand');

		const p = await speichern(ed);
		const st = p.stages as Knoten[];
		assert.equal(st[1].grundtempo_kmh, 3, 'POST ohne Etappen-Tempo');
		assert.ok(!('grundtempo_kmh' in st[0]), 'AC-4: POST trägt zurückgenommenes Tempo');
		assert.ok(!('grundtempo_kmh' in st[2]));
		assert.equal((st[1].waypoints as Knoten[]).length, 2, 'Wegpunkte gehen im POST verloren');
	});

	test('Speichern direkt aus dem Reiter Wegpunkte (ohne Tabwechsel): Etappen-Tempo landet im POST', async () => {
		const ed = await editor();
		ed.u.activeTab = 'etappen';
		ed.u.switchTab('wegpunkte');
		ed.u.editorStages = ed.u.editorStages.map((s: Knoten, i: number) => (i === 2 ? { ...s, grundtempo_kmh: 2.5 } : s));
		assert.equal(ed.u.activeTab, 'wegpunkte', 'Messaufbau');
		const st = (await speichern(ed)).stages as Knoten[];
		assert.deepEqual(tempoIm(st), [undefined, undefined, 2.5], 'Sync vor dem POST fehlt');
	});

	test('F001: Etappen-Tempo im Anlege-Zustand reist unverändert im POST (ein Pfad über buildCreateTripPayload)', async () => {
		const ed = await editor([undefined, 6, undefined]);
		ed.u.activeTab = 'wetter';
		const st = (await speichern(ed)).stages as Knoten[];
		assert.deepEqual(tempoIm(st), [undefined, 6, undefined]);
		assert.deepEqual(st.map((s) => s.name), ['Tag 1', 'Tag 2', 'Tag 3']);
		assert.deepEqual(st.map((s) => s.date), ['2026-07-01', '2026-07-02', '2026-07-03']);
		for (const s of st) assert.ok(!('gpx' in s), 'interner Upload-Zustand gpx im POST');
	});

	test('jede EditStagesPanelNew-Einbettung (Desktop + mobil) bekommt das aktuelle Trip-Tempo', async () => {
		const ed = await editor();
		const panels = findeKomponenten(ed.ast, 'EditStagesPanelNew');
		assert.equal(panels.length, 2, 'Messaufbau: Desktop + mobil');
		tempoKartenRueckrufe(ed)[0]({ ...RAD });
		for (const [i, p] of panels.entries()) {
			const a = attributAusdruck(p, ed.quelle, 'tempo');
			assert.ok(a, `EditStagesPanelNew ${i + 1}: tempo-Prop fehlt — Gehzeit rechnet mit Standard statt Trip-Tempo`);
			assert.deepEqual(werte(a!, ed.u), RAD, `EditStagesPanelNew ${i + 1}: nicht das aktuelle Trip-Tempo`);
		}
	});
});
