// Fix-Loop 1 — Issue #3197 (Workflow feat-3197-tempo-je-etappe), Adversary F002/F003/F004.
// Spec: docs/specs/modules/feat_3197_tempo_je_etappe.md — AC-4, AC-6
//
// Gemessen dort, wo es WIRKT (ECHTES Instanz-Skript und ECHTES Markup, kein Mock):
//   F002 (AC-4) „Trip-Tempo verwenden": der Rückruf, den das Panel an die Karte gibt (Desktop:
//               TempoKarteInhalt im Panel; mobil: StageCardM → TempoKarteInhalt), wird aus seinem
//               echten Quelltext ausgelöst ⇒ grundtempo_kmh der Etappe ist entfernt, die Gehzeit der
//               echten Listenzeile ({@const zeile}) entspricht wieder dem Trip-Tempo.
//   F003 (AC-6) Hinweis im DOM: Fortbewegungswechsel ohne überschriebene Etappe ⇒ kein Hinweis; mit zwei
//               ⇒ Hinweis „2 Etappen". Zahl aus dem echten tempoAendern, DOM aus dem echten Render.
//   F004        zurueckgesetztAnzahl wird bei der nächsten Tempo-Aktion (Trip-Grundtempo ohne Wechsel,
//               Etappen-Tempo setzen, Etappen-Tempo zurücknehmen) wieder 0.
//
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types \
//     --experimental-test-module-mocks --test src/lib/components/trip-detail/__tests__/tempo_je_etappe_3197_fixloop1.test.ts

import { test, describe, afterEach } from 'node:test';
import assert from 'node:assert/strict';
import path from 'node:path';
import { readFileSync } from 'node:fs';
import { pathToFileURL } from 'node:url';

const T = await import('./f9Pruefstand.ts');
const P = await import('../../shared/__tests__/svelteInstanzPruefstand.ts');
const { umgebungFuer, findeKomponenten, attributAusdruck, werte, ohneTypen } = P;
const { render } = await import('svelte/server');
const { createRawSnippet } = await import('svelte');
const { baum, alle, text: rohText } = await import('../../shared/hub-kopf/__tests__/htmlBaum.ts');
type Knoten = Record<string, any>; // eslint-disable-line @typescript-eslint/no-explicit-any

const PANEL = path.join(T.KOMP, 'edit', 'EditStagesPanelNew.svelte');
const KARTE_M = path.join(T.KOMP, 'mobile', 'StageCardM.svelte');
const { locale } = T;
afterEach(() => locale.set('de'));

const TABELLE = JSON.parse(readFileSync(path.resolve(T.FRONTEND, '..', 'tests', 'fixtures', 'naismith_dav_paritaet.json'), 'utf-8'));
const UE = TABELLE.etappen_ueberschreibung;
const TRIP_TEMPO = UE.tempo;
const PAUSE = { id: 'S3', name: 'Ruhetag', date: '2026-07-03', waypoints: [] };
const etappen = () => [...structuredClone(UE.stages), structuredClone(PAUSE)];
/** S1 und S2 überschrieben (S1 5 km/h, S2 3 km/h aus der Falltabelle). */
const zwei = () => {
	const s = etappen();
	s[0] = { ...s[0], grundtempo_kmh: 5 };
	return s;
};
const ohne = () => etappen().map(({ grundtempo_kmh: _x, ...s }: Knoten) => s);

async function panel(stages: unknown[]) {
	const gespeichert: number[] = [];
	const r = await umgebungFuer(PANEL, { stages, tripId: 't', showSave: false, tempo: { ...TRIP_TEMPO }, scheduleSave: () => gespeichert.push(1) });
	assert.equal(typeof r.u.tempoAendern, 'function', 'Messaufbau: tempoAendern nicht herleitbar');
	return { ...r, gespeichert };
}

/** `$derived`-Deklarationen aus ihrem ECHTEN Quelltext neu auswerten (wie Svelte nach einer Änderung). */
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
	return werte(ohneTypen(quelle, (treffer as Knoten).init), Object.assign(Object.create(u), lokal));
}

/** Rückruf-Attribut `attr` einer Einbettung `komp`, ausgewertet mit den Snippet-Parametern `lokal`. */
function rueckruf(ast: Knoten, quelle: string, u: Knoten, komp: string, attr: string, lokal: Knoten): () => void {
	const treffer = findeKomponenten(ast, komp);
	assert.equal(treffer.length, 1, `Messaufbau: genau eine ${komp}-Einbettung erwartet (${treffer.length})`);
	const ausdruck = attributAusdruck(treffer[0], quelle, attr);
	assert.ok(ausdruck, `${komp}: Attribut ${attr} fehlt`);
	const f = werte(ausdruck!, Object.assign(Object.create(u), lokal));
	assert.equal(typeof f, 'function', `${komp}.${attr} ist keine Funktion`);
	return f as () => void;
}

const gehzeit = (p: Knoten, i: number) => String((constTag(p.ast, p.quelle, p.u, 'zeile', { stage: p.u.stages[i], i }) as Knoten).meta);

// ═══ F002 (AC-4): „Trip-Tempo verwenden" am echten Panel ═══════════════════════════════════
describe('F002 (AC-4): „Trip-Tempo verwenden" entfernt das Etappen-Tempo', () => {
	test('Desktop: Rückruf der Etappen-Karte im Panel ⇒ Feld weg, Gehzeit wie Trip (5:36 → 4:12)', async () => {
		const p = await panel(etappen());
		assert.ok(gehzeit(p, 1).includes('5:36'), `Messaufbau S2: ${gehzeit(p, 1)}`);
		rueckruf(p.ast, p.quelle, p.u, 'TempoKarteInhalt', 'ontriptempo', { stage: p.u.stages[1] })();
		assert.ok(!('grundtempo_kmh' in p.u.stages[1]), 'S2: grundtempo_kmh nicht entfernt');
		assert.ok(gehzeit(p, 1).includes('4:12'), `S2 rechnet nicht wieder mit dem Trip-Tempo: ${gehzeit(p, 1)}`);
		assert.equal(p.u.stages[0].id, 'S1');
		assert.ok(p.gespeichert.length >= 1, 'Zurücknehmen löst kein Speichern aus');
	});

	test('Mobil: Panel-Rückruf an StageCardM ⇒ Feld weg, Gehzeit wie Trip', async () => {
		const p = await panel(etappen());
		rueckruf(p.ast, p.quelle, p.u, 'StageCardM', 'ontriptempo', { stage: p.u.stages[1], i: 1 })();
		assert.ok(!('grundtempo_kmh' in p.u.stages[1]), 'S2: grundtempo_kmh nicht entfernt (mobil)');
		assert.ok(gehzeit(p, 1).includes('4:12'), `S2 mobil: ${gehzeit(p, 1)}`);
	});

	test('Mobil: StageCardM reicht ontriptempo an ihre TempoKarteInhalt durch', async () => {
		const aufrufe: number[] = [];
		const { ast, quelle, u } = await umgebungFuer(KARTE_M, {
			stage: structuredClone(UE.stages[1]), index: 1, tempo: TRIP_TEMPO, tempoOffen: true,
			ontriptempo: () => aufrufe.push(1), onetappentempo: () => {}, ontempoaendern: () => {}
		});
		rueckruf(ast, quelle, u, 'TempoKarteInhalt', 'ontriptempo', {})();
		assert.equal(aufrufe.length, 1, 'StageCardM: „Trip-Tempo verwenden" erreicht das Panel nicht');
	});
});

// ═══ F003 (AC-6): Hinweis im DOM ═════════════════════════════════════════════════════════
describe('F003 (AC-6): Hinweis zu zurückgesetzten Etappen im DOM', () => {
	const kopf = () => createRawSnippet(() => ({ render: () => '<div data-testid="probe-kopf">Etappen</div>' }));
	async function dom(anzahl: number): Promise<{ hinweise: Knoten[]; text: string }> {
		const ers: [string, string][] = [['let zurueckgesetztAnzahl = $state(0);', `let zurueckgesetztAnzahl = $state(${anzahl});`]];
		const K = (await import(`${pathToFileURL(PANEL).href}?f8variante=${Buffer.from(JSON.stringify(ers)).toString('base64url')}`)).default;
		const b = baum(render(K, { props: { stages: etappen(), tripId: 't', showSave: false, tempo: TRIP_TEMPO, kopf: kopf(), listeZuerst: true } }).body);
		const hinweise = alle(b as never, (n: Knoten) => n.attrs['data-testid'] === 'etappen-tempo-zurueckgesetzt');
		return { hinweise, text: hinweise.map((h) => rohText(h as never)).join(' ').replace(/\s+/g, ' ') };
	}

	test('Wechsel ohne überschriebene Etappe ⇒ kein Hinweis', async () => {
		const p = await panel(ohne());
		p.u.tempoAendern({ fortbewegung: 'rad', grundtempo_kmh: 20 });
		assert.equal(p.u.zurueckgesetztAnzahl, 0);
		assert.equal((await dom(p.u.zurueckgesetztAnzahl)).hinweise.length, 0, 'Hinweis ohne betroffene Etappe');
	});

	test('Wechsel mit zwei überschriebenen Etappen ⇒ Hinweis „2 Etappen"', async () => {
		const p = await panel(zwei());
		p.u.tempoAendern({ fortbewegung: 'rad', grundtempo_kmh: 20 });
		assert.equal(p.u.zurueckgesetztAnzahl, 2);
		const d = await dom(p.u.zurueckgesetztAnzahl);
		assert.equal(d.hinweise.length, 1, 'Hinweis fehlt');
		assert.match(d.text, /2 Etappen/);
	});
});

// ═══ F004: Hinweis verschwindet bei der nächsten Tempo-Aktion ══════════════════════════════
describe('F004: zurueckgesetztAnzahl wird bei der nächsten Tempo-Aktion 0', () => {
	async function nachWechsel() {
		const p = await panel(zwei());
		p.u.tempoAendern({ fortbewegung: 'rad', grundtempo_kmh: 20 });
		assert.equal(p.u.zurueckgesetztAnzahl, 2, 'Messaufbau');
		neuHerleiten(p.ast, p.quelle, p.u, ['tempoAktiv']);
		assert.equal(p.u.tempoAktiv.fortbewegung, 'rad', 'Messaufbau: tempoAktiv nicht Rad');
		return p;
	}

	test('Trip-Grundtempo ändern ohne Fortbewegungswechsel ⇒ 0', async () => {
		const p = await nachWechsel();
		p.u.tempoAendern({ fortbewegung: 'rad', grundtempo_kmh: 15 });
		assert.equal(p.u.zurueckgesetztAnzahl, 0);
	});

	test('Etappen-Tempo setzen ⇒ 0', async () => {
		const p = await nachWechsel();
		p.u.etappenTempoSetzen('S2', { fortbewegung: 'rad', grundtempo_kmh: 10 });
		assert.equal(p.u.zurueckgesetztAnzahl, 0);
	});

	test('Etappen-Tempo zurücknehmen ⇒ 0', async () => {
		const p = await nachWechsel();
		p.u.etappenTempoZuruecknehmen('S2');
		assert.equal(p.u.zurueckgesetztAnzahl, 0);
	});
});
