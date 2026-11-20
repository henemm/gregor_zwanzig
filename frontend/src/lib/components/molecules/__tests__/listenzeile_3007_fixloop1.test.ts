// Fix-Loop 1 — Issue #3007 (Epic #2913), Adversary F001, F003, F004 (Mutationen M5, M8, M10, M14,
// M17, M18, M20). Spec: docs/specs/modules/feat_3007_etappen_orte_listen.md — AC-2, AC-11, AC-13.
//
// Gemessen wird dort, wo es WIRKT:
//   F001 (AC-11)  der ECHTE Reiter EditStagesPanelNew mit einer Fahrrad-Aktivität, serverseitig
//                 gerendert: die Gehzeit der Zeile folgt dem Tempo des Trips (deriveTempo, #3196),
//                 Soll unabhängig aus computeArrivalTimes.
//   F003 (AC-13)  (a) SSR des ECHTEN Reiters mit aufgeklappter Etappe 3 (Startwert per
//                 startzustandHook): nur Zeile 3 trägt aria-expanded="true", der Editor steht direkt
//                 unter Zeile 3 und zeigt die Daten der Etappe 3 (Name, Wegpunkte), nicht die der 1.
//                 (b) Verhalten der ECHTEN Instanz-Funktionen `zeileUmschalten`/`handleStageActivate`
//                 über den Prüfstand (kein DOM im Projekt): Klick öffnet genau diese Etappe und macht
//                 sie zur aktiven (der Editor rendert `activeStage`), erneuter Klick schließt, Wechsel
//                 im Band nimmt den offenen Editor mit, bei geschlossener Liste öffnet das Band nichts.
//   F004 (AC-2)   die ECHTE Tastatur-Funktion der Einstellungszeile und ihre Verdrahtung am
//                 Zeilen-Element: Enter und Leertaste lösen die Zeilenaktion aus; dieselben Tasten
//                 auf einem Kind-Element (z. B. Knopf „entfernen“ in der Zeile) tun es NICHT und
//                 verhindern dessen eigene Tastenwirkung nicht.
//
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types \
//     --experimental-test-module-mocks --test src/lib/components/molecules/__tests__/listenzeile_3007_fixloop1.test.ts

import { test, describe, afterEach } from 'node:test';
import assert from 'node:assert/strict';
import { register } from 'node:module';
import { readFileSync, readdirSync } from 'node:fs';
import { fileURLToPath, pathToFileURL } from 'node:url';
import path from 'node:path';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const FRONTEND = path.resolve(HERE, '../../../../..');
const KOMP = path.resolve(HERE, '../..');
const reg = (p: string) => register(pathToFileURL(p).href, pathToFileURL(FRONTEND + '/').href);
reg(path.join(FRONTEND, 'src/routes/account/__tests__/app-navigation-stub-hooks.mjs'));
reg(path.join(KOMP, 'shared/__tests__/svelteTsModulHook.mjs'));
reg(path.join(FRONTEND, 'test-svelte-ssr-hooks.mjs'));
reg(path.join(KOMP, 'organisms/__tests__/startzustandHook.mjs'));

const { render } = await import('svelte/server');
const { locale } = await import(pathToFileURL(path.join(FRONTEND, 'src/lib/i18n/index.ts')).href);
const { baum, alle, text: rohText } = await import('../../shared/hub-kopf/__tests__/htmlBaum.ts');
const { computeArrivalTimes, deriveTempo } = await import(pathToFileURL(path.join(FRONTEND, 'src/lib/utils/naismith.ts')).href);
const { umgebungFuer, werte, ohneTypen } = await import('../../shared/__tests__/svelteInstanzPruefstand.ts');
type Knoten = import('../../shared/hub-kopf/__tests__/htmlBaum.ts').Knoten;

afterEach(() => locale.set('de'));

const DE: Record<string, string> = {};
for (const f of readdirSync(path.join(FRONTEND, 'src/lib/i18n/messages/de')).filter((n) => n.endsWith('.json')))
	Object.assign(DE, JSON.parse(readFileSync(path.join(FRONTEND, 'src/lib/i18n/messages/de', f), 'utf8')));

const entity = (s: string) => s.replace(/&amp;/g, '&').replace(/&nbsp;/g, ' ').replace(/&lt;/g, '<').replace(/&gt;/g, '>').replace(/&quot;/g, '"').replace(/&#39;/g, "'");
const text = (k: Knoten) => entity(rohText(k)).replace(/\s+/g, ' ').trim();
const mitTestid = (b: Knoten, id: string) => alle(b, (n) => n.attrs['data-testid'] === id);
const mitSlot = (b: Knoten, s: string) => alle(b, (n) => n.attrs['data-slot'] === s);
async function lade(file: string, start: [string, string][] = []): Promise<any> {
	const q = start.length ? `?start=${encodeURIComponent(JSON.stringify(start))}` : '';
	return (await import(pathToFileURL(file).href + q)).default;
}

const ESP = path.join(KOMP, 'edit', 'EditStagesPanelNew.svelte');
const EZ = path.join(KOMP, 'molecules', 'Einstellungszeile.svelte');
const wp = (id: string, name: string, lat: number, lon: number, elevation_m: number) => ({ id, name, lat, lon, elevation_m });
const ETAPPEN = [
	{ id: 's1', name: 'Tag 1', date: '2026-08-01', start_time: '08:00', waypoints: [wp('a', "Port d'Andratx", 39.54, 2.39, 10), wp('b', 'Sa Trapa', 39.58, 2.40, 380), wp('c', 'Estellencs', 39.65, 2.48, 150)] },
	{ id: 's2', name: 'Pausentag', date: '2026-08-02', waypoints: [] },
	{ id: 's3', name: 'Tag 3', date: '2026-08-03', start_time: '07:30', waypoints: [wp('d', 'Valldemossa', 39.71, 2.62, 420), wp('e', 'Deià', 39.75, 2.65, 150)] }
];

/** Gehzeit h:mm unabhängig: letzte minus erste Ankunft der vorhandenen Rechnung beim Tempo. */
function gehzeit(stage: any, tempo: any): string {
	const arr: string[] = computeArrivalTimes(stage, stage.start_time, tempo);
	const min = (s: string) => Number(s.slice(0, 2)) * 60 + Number(s.slice(3));
	let d = min(arr[arr.length - 1]) - min(arr[0]);
	if (d < 0) d += 24 * 60;
	return `${Math.floor(d / 60)}:${String(d % 60).padStart(2, '0')}`;
}
const gehzeitDE = (dauer: string) => DE['trip.hub.etappe_gehzeit'].replace(/\{\w+\}/, dauer);

// ═══ F001 (AC-11): Tempo der Aktivität im echten Reiter ═══════════════════════════════════
describe('#3007 F001: Gehzeit im Reiter folgt der Aktivität (AC-11)', () => {
	for (const aktivitaet of ['fahrrad_20', 'fahrrad_15'] as const) {
		test(`${aktivitaet}: Gehzeit der Zeile = Rechnung mit dem Tempo (Rad aus ${aktivitaet}, #3196), nicht Wandertempo`, async () => {
			const P = await lade(ESP);
			const b = baum(render(P, { props: { stages: ETAPPEN, tripId: 't1', listeZuerst: true, tempo: deriveTempo(aktivitaet) } }).body);
			const zeilen = mitTestid(b, 'etappen-liste-zeile');
			assert.equal(zeilen.length, ETAPPEN.length, 'Messaufbau: Zeilenzahl');
			for (const i of [0, 2]) {
				const tempo = deriveTempo(aktivitaet);
				const soll = gehzeit(ETAPPEN[i], tempo);
				const wandern = gehzeit(ETAPPEN[i], deriveTempo(undefined));
				assert.notEqual(soll, wandern, 'Messaufbau: Fahrrad- und Wandertempo ergeben dieselbe Gehzeit');
				assert.deepEqual(mitSlot(zeilen[i], 'listenzeile-meta').map(text), [gehzeitDE(soll)], `Etappe ${i + 1}: Gehzeit nicht mit Tempo ${tempo.grundtempo_kmh} km/h`);
			}
		});
	}
});

// ═══ F003 (AC-13) a: Markup mit aufgeklappter Etappe 3 ════════════════════════════════════
const OFFEN_S3: [string, string][] = [
	['let offeneEtappeId = $state<string | null>(null);', "let offeneEtappeId = $state<string | null>('s3');"],
	["stages.find((s) => !isPauseStage(s))?.id ?? stages[0]?.id ?? ''", "'s3'"]
];

describe('#3007 F003a: aufgeklappte Etappe im echten Reiter (AC-13, SSR)', () => {
	test('nur Zeile 3 aria-expanded="true", Editor direkt unter Zeile 3 mit den Daten der Etappe 3', async () => {
		const P = await lade(ESP, OFFEN_S3);
		const b = baum(render(P, { props: { stages: ETAPPEN, tripId: 't1', listeZuerst: true } }).body);
		const zeilen = mitTestid(b, 'etappen-liste-zeile');
		assert.equal(zeilen.length, 3, 'Messaufbau: Zeilenzahl');
		assert.deepEqual(zeilen.map((z) => z.attrs['aria-expanded']), ['false', 'false', 'true'], 'aria-expanded folgt nicht der offenen Etappe');
		const auf = mitTestid(b, 'etappen-aufklapp');
		assert.equal(auf.length, 1, `${auf.length} aufgeklappte Bereiche statt genau einem`);
		const geschwister = zeilen[2].eltern!.kinder;
		assert.equal(geschwister[geschwister.indexOf(zeilen[2]) + 1], auf[0], 'Editor steht nicht direkt unter Zeile 3');
		const editor = mitTestid(auf[0], 'etappen-reiterflaeche');
		assert.equal(editor.length, 1, 'eingebetteter Editor fehlt');
		const sidebar = mitTestid(editor[0], 'waypoint-sidebar');
		assert.equal(sidebar.length, 1, 'Wegpunkt-Liste fehlt im Editor');
		const st = text(sidebar[0]);
		assert.ok(st.includes('Valldemossa') && st.includes('Deià'), `Editor zeigt nicht die Wegpunkte der Etappe 3: „${st.slice(0, 200)}“`);
		assert.ok(!st.includes("Port d'Andratx") && !st.includes('Sa Trapa'), 'Editor zeigt Wegpunkte der Etappe 1');
		assert.ok(alle(editor[0], (n) => n.tag === 'p' && text(n) === 'Tag 3').length === 1, 'Editor-Titel ist nicht „Tag 3“');
	});
	test('Grundzustand: kein aufgeklappter Bereich', async () => {
		const P = await lade(ESP);
		const b = baum(render(P, { props: { stages: ETAPPEN, tripId: 't1', listeZuerst: true } }).body);
		assert.equal(mitTestid(b, 'etappen-aufklapp').length, 0);
		assert.ok(mitTestid(b, 'etappen-liste-zeile').every((z) => z.attrs['aria-expanded'] === 'false'));
	});
});

// ═══ F003 (AC-13) b: Verhalten der echten Instanz-Funktionen ══════════════════════════════
/** Instanz des Reiters über den Prüfstand; `neu()` wertet die echten $derived erneut aus. */
async function panelInstanz() {
	const { ast, quelle, u } = await umgebungFuer(ESP, { stages: structuredClone(ETAPPEN), tripId: 't1', listeZuerst: true });
	const deklaration = (name: string) => {
		for (const s of ast.instance.content.body)
			if (s.type === 'VariableDeclaration') for (const d of s.declarations) if (d.id?.type === 'Identifier' && d.id.name === name) return d;
		throw new Error(`Prüfstand: Deklaration ${name} fehlt`);
	};
	const neu = () => {
		for (const n of ['activeStage', 'offenId']) u[n] = werte(ohneTypen(quelle, deklaration(n).init), u);
	};
	for (const f of ['zeileUmschalten', 'handleStageActivate']) assert.equal(typeof u[f], 'function', `Prüfstand: ${f} nicht auswertbar`);
	neu();
	const klick = (id: string) => {
		u.zeileUmschalten(id);
		neu();
	};
	const band = (id: string) => {
		u.handleStageActivate(id);
		neu();
	};
	return { u, klick, band };
}

describe('#3007 F003b: Klick, erneuter Klick, Wechsel im Band (AC-13, Instanz-Funktionen)', () => {
	test('Grundzustand: nichts offen', async () => {
		const { u } = await panelInstanz();
		assert.equal(u.offenId, null);
	});
	test('Klick auf Zeile 3 öffnet genau Etappe 3 und macht sie zur Editor-Etappe', async () => {
		const { u, klick } = await panelInstanz();
		assert.equal(u.activeStageId, 's1', 'Messaufbau: Startetappe');
		klick('s3');
		assert.equal(u.offenId, 's3', 'offene Zeile ist nicht Etappe 3');
		assert.equal(u.activeStageId, 's3', 'Editor zeigt nicht Etappe 3');
		assert.equal(u.activeStage?.name, 'Tag 3', 'Editor-Etappe ist nicht Etappe 3');
	});
	test('erneuter Klick auf dieselbe Zeile schließt', async () => {
		const { u, klick } = await panelInstanz();
		klick('s3');
		klick('s3');
		assert.equal(u.offenId, null, 'erneuter Klick schließt nicht');
	});
	test('Klick auf andere Zeile wechselt (höchstens einer offen)', async () => {
		const { u, klick } = await panelInstanz();
		klick('s3');
		klick('s1');
		assert.equal(u.offenId, 's1');
		assert.equal(u.activeStageId, 's1');
	});
	test('Wechsel im Band bei offenem Editor nimmt den Editor mit', async () => {
		const { u, klick, band } = await panelInstanz();
		klick('s1');
		band('s3');
		assert.equal(u.offenId, 's3', 'Editor bleibt unter der alten Zeile');
		assert.equal(u.activeStageId, 's3');
	});
	test('Wechsel der aktiven Etappe bei geschlossener Liste öffnet nichts', async () => {
		const { u, band } = await panelInstanz();
		band('s3');
		assert.equal(u.offenId, null, 'Band öffnet bei geschlossener Liste einen Editor');
		assert.equal(u.activeStageId, 's3');
	});
});

// ═══ F004 (AC-2): Tastatur an der klickbaren Zeile, Kind-Elemente ausgenommen ══════════════
/** Zeilen-Element der Einstellungszeile im AST und der Ausdruck seines Attributs `name`. */
function zeilenAttribut(ast: any, quelle: string, name: string): string {
	let treffer: any = null;
	(function lauf(n: any): void {
		if (!n || typeof n !== 'object' || treffer) return;
		if (Array.isArray(n)) return n.forEach(lauf);
		if (n.type === 'RegularElement' && n.name === 'div' && n.attributes?.some((a: any) => a.name === 'data-slot' && a.value?.[0]?.data === 'einstellungszeile')) treffer = n;
		for (const k of Object.keys(n)) if (k !== 'parent' && k !== 'loc') lauf(n[k]);
	})(ast.fragment);
	assert.ok(treffer, 'Prüfstand: Zeilen-Element der Einstellungszeile nicht gefunden');
	const a = treffer.attributes.find((x: any) => x.name === name);
	assert.ok(a, `Zeilen-Element ohne Attribut ${name}`);
	return a.value === true ? name : a.value.type === 'ExpressionTag' ? quelle.slice(a.value.expression.start, a.value.expression.end) : name;
}

async function zeilenTastatur() {
	const aufrufe: number[] = [];
	const onclick = () => aufrufe.push(1);
	const { ast, quelle, u } = await umgebungFuer(EZ, { titel: 'Zeile', onclick });
	const handler = werte(zeilenAttribut(ast, quelle, 'onkeydown'), u) as (e: any) => void;
	assert.equal(typeof handler, 'function', 'klickbare Zeile ohne Tastatur-Handler');
	const zeile = { name: 'zeile' };
	const druecke = (key: string, target: object) => {
		let verhindert = false;
		handler({ key, target, currentTarget: zeile, preventDefault: () => (verhindert = true) });
		return verhindert;
	};
	return { aufrufe, druecke, zeile };
}

describe('#3007 F004: Tastatur der klickbaren Zeile (AC-2, Instanz-Funktion)', () => {
	test('Enter und Leertaste auf der Zeile lösen die Zeilenaktion aus (und verhindern das Scrollen)', async () => {
		const { aufrufe, druecke, zeile } = await zeilenTastatur();
		assert.equal(druecke('Enter', zeile), true, 'Enter: preventDefault fehlt');
		assert.equal(aufrufe.length, 1, 'Enter löst die Zeilenaktion nicht aus');
		assert.equal(druecke(' ', zeile), true, 'Leertaste: preventDefault fehlt');
		assert.equal(aufrufe.length, 2, 'Leertaste löst die Zeilenaktion nicht aus');
	});
	test('andere Tasten tun nichts', async () => {
		const { aufrufe, druecke, zeile } = await zeilenTastatur();
		for (const k of ['a', 'Tab', 'Escape', 'ArrowDown']) assert.equal(druecke(k, zeile), false, `${k}: preventDefault`);
		assert.equal(aufrufe.length, 0);
	});
	test('Enter/Leertaste auf einem Kind-Knopf in der Zeile lösen NICHT die Zeilenaktion aus', async () => {
		const { aufrufe, druecke } = await zeilenTastatur();
		const kindKnopf = { name: 'entfernen' };
		assert.equal(druecke('Enter', kindKnopf), false, 'Enter auf Kind-Knopf: Zeile verhindert dessen Tastenwirkung');
		assert.equal(druecke(' ', kindKnopf), false, 'Leertaste auf Kind-Knopf: Zeile verhindert dessen Tastenwirkung');
		assert.equal(aufrufe.length, 0, 'Taste auf Kind-Knopf löst die Zeilenaktion aus');
	});
	test('Klick-Verdrahtung: onclick des Zeilen-Elements ist die übergebene Aktion', async () => {
		const aufrufe: number[] = [];
		const onclick = () => aufrufe.push(1);
		const { ast, quelle, u } = await umgebungFuer(EZ, { titel: 'Zeile', onclick });
		assert.equal(werte(zeilenAttribut(ast, quelle, 'onclick'), u), onclick);
	});
	test('ohne onclick kein Tastatur-Handler (Einstellungszeile unverändert)', async () => {
		const { ast, quelle, u } = await umgebungFuer(EZ, { titel: 'Zeile', onclick: undefined });
		assert.equal(werte(zeilenAttribut(ast, quelle, 'onkeydown'), u), undefined);
	});
});
