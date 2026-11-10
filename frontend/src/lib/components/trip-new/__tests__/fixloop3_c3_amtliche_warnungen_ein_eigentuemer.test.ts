// Fix-Loop 3 Issue #2794 S3a Teil-PR 3, Befund C3: Trip anlegen — „Amtliche Warnungen" hatte
// zwei Eigentuemer. Jeder Stand-Bericht des Reiters Wetter ueberschrieb den Schalter im Schritt
// Zustellung (AlarmeTab); die Geste dort floss nicht in den Wetter-Zustand zurueck. Folge: der
// Schalter sprang nach einem Schrittwechsel zurueck, und der Startwert war „an" statt der
// Neuanlage-Vorgabe „aus" (#1258, api_contract `official_warnings`).
//
// Tech-Lead-Entscheid (fix-loop-3.md): die Neuanlage-Vorgabe `official_warnings.enabled=false`
// bleibt; die ODER-Lese-Regel (AC-20) betrifft bestehende Abos, nicht die Vorbelegung. EIN
// Eigentuemer je Wert (AC-38-Geist): der Alarm-Zustand des Editors. Beide Reiter lesen ihn und
// schreiben ihn nur per Geste; der POST traegt beide Warn-Felder mit demselben Wert (AC-20).
//
// Gemessen dort, wo es WIRKT: die ECHTEN Instanz-Skripte von TripNewEditor.svelte und
// WetterTab.svelte, verbunden wie im Markup (Muster f002_trip_anlegen_ampel_im_post.test.ts).
// Referenz-Repro im Browser: frontend/e2e/gewitter-absolutregel-gesperrt.spec.ts:162,175.
//
//   cd frontend && npm test -- src/lib/components/trip-new/__tests__/fixloop3_c3_amtliche_warnungen_ein_eigentuemer.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

import { umgebungFuer, findeKomponenten, ohneTypen, werte, type Knoten } from '../../shared/__tests__/svelteInstanzPruefstand.ts';
import { live } from '../../shared/wetter-tab/__tests__/wetterTabDaten.ts';
import * as Z from '../../shared/wetter-tab/wetterZustand.ts';
import * as L from '../tripNewLogic.ts';

const HIER = dirname(fileURLToPath(import.meta.url));
const EDITOR = join(HIER, '..', 'TripNewEditor.svelte');
const WETTER_TAB = join(HIER, '..', '..', 'shared', 'wetter-tab', 'WetterTab.svelte');

const LIVE_API = {
	get: async (pfad: string) => {
		const d = live();
		if (pfad === '/api/metrics') return d.metrics;
		if (pfad === '/api/templates') return d.templates;
		if (pfad === '/api/metric-presets') return [];
		throw new Error(`unerwartet: ${pfad}`);
	}
};

const deklaration = (ast: Knoten, name: string): Knoten | undefined =>
	(ast.instance.content.body as Knoten[])
		.filter((s) => s.type === 'VariableDeclaration')
		.flatMap((s) => s.declarations as Knoten[])
		.find((d) => d.id?.name === name);

async function editor() {
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
	const decl = deklaration(ast, 'wetterAnlegeTrip');
	const stub = deklaration(ast, 'stubTrip');
	assert.ok(decl && stub, 'Messaufbau: wetterAnlegeTrip/stubTrip fehlen im Editor');
	const neuAbleiten = () => {
		u.stubTrip = werte(ohneTypen(quelle, stub.init), u);
		return werte(ohneTypen(quelle, decl.init), u) as Z.AboSicht;
	};
	return { ast, quelle, u, gesendet, neuAbleiten };
}
type Ed = Awaited<ReturnType<typeof editor>>;

async function wetterTabMontieren(ed: Ed): Promise<Knoten> {
	const { u } = await umgebungFuer(WETTER_TAB, {
		context: 'route',
		trip: ed.neuAbleiten(),
		preset: undefined,
		createMode: true,
		saveController: undefined,
		enqueueHubWrite: undefined,
		onTripUpdate: undefined,
		onCompareUpdate: undefined,
		onAnlegeStand: (n: unknown) => ed.u.handleWetterAnlegeStand(n),
		api: LIVE_API
	});
	await u.laden();
	assert.equal(u.phase, 'bereit', 'Messaufbau: WetterTab hat nicht geladen');
	return u;
}

async function warnFelderImPost(ed: Ed): Promise<{ alerts: unknown; ow: unknown }> {
	ed.u.ready = true;
	const id = await ed.u.buildAndSave();
	assert.equal(id, 'neu-1', `buildAndSave scheiterte: ${ed.u.saveError}`);
	const p = ed.gesendet.at(-1)!.payload;
	return { alerts: p.official_alerts_enabled, ow: (p.official_warnings as Knoten | undefined)?.enabled };
}

/** Der Schalter im Schritt Zustellung zeigt `alarm.officialWarningsEnabled` (Wertprop des AlarmeTab). */
const schalterZustellung = (ed: Ed): boolean => ed.u.alarm.officialWarningsEnabled;

describe('C3 Kern: ein Bericht des Reiters Wetter uebernimmt den Warn-Schalter nur bei einer Geste dort', () => {
	test('warnungenNachWetterBericht: erster Bericht, Echo und Geste', () => {
		assert.equal(typeof L.warnungenNachWetterBericht, 'function', 'tripNewLogic.warnungenNachWetterBericht fehlt');
		// erster Bericht eines Reiters: Lesart, keine Geste — der Editor-Wert bleibt
		assert.equal(L.warnungenNachWetterBericht(false, undefined, true), false);
		// Echo eines veralteten Werts nach einer Geste im Schritt Zustellung — bleibt
		assert.equal(L.warnungenNachWetterBericht(true, false, false), true);
		// Geste im Reiter Wetter (Wert aendert sich gegenueber seinem letzten Bericht)
		assert.equal(L.warnungenNachWetterBericht(false, false, true), true);
		assert.equal(L.warnungenNachWetterBericht(true, true, false), false);
	});
});

describe('C3: Trip anlegen — „Amtliche Warnungen" mit einem Eigentuemer', () => {
	test('ohne Geste: Neuanlage-Vorgabe „aus" in beiden Reitern und im POST (beide Felder false)', async () => {
		const ed = await editor();
		const wt = await wetterTabMontieren(ed);
		assert.equal(wt.stand.warnungenAn, false, 'Reiter Wetter startet nicht mit der Neuanlage-Vorgabe „aus"');
		assert.equal(schalterZustellung(ed), false, 'Schalter in der Zustellung springt durch den Wetter-Bericht auf „an"');
		assert.deepEqual(await warnFelderImPost(ed), { alerts: false, ow: false });
	});

	test('Geste in der Zustellung ueberlebt einen spaeteren Bericht des Reiters Wetter und reist im POST', async () => {
		const ed = await editor();
		const wt = await wetterTabMontieren(ed);
		// Gegenteil dessen, was der Reiter Wetter gerade zeigt — sonst ist die Geste unbeobachtbar.
		const ziel = !wt.stand.warnungenAn;
		ed.u.handleAlarmOfficialWarningsChange(ziel);
		assert.equal(schalterZustellung(ed), ziel);
		wt.aendern(Z.mitAlarmAb(wt.stand, 'gust', 'red')); // irgendeine Aenderung im Reiter Wetter
		assert.equal(schalterZustellung(ed), ziel, 'der Bericht des Reiters Wetter hat die Geste der Zustellung ueberschrieben');
		const wt2 = await wetterTabMontieren(ed); // Neuaufbau (Schrittwechsel, Desktop ↔ Mobil)
		assert.equal(wt2.stand.warnungenAn, ziel, 'die Geste der Zustellung fliesst nicht in den Reiter Wetter');
		assert.equal(schalterZustellung(ed), ziel);
		assert.deepEqual(await warnFelderImPost(ed), { alerts: ziel, ow: ziel });
	});

	test('Geste im Reiter Wetter erreicht die Zustellung und den POST', async () => {
		const ed = await editor();
		const wt = await wetterTabMontieren(ed);
		const ziel = !wt.stand.warnungenAn;
		wt.aendern({ ...wt.stand, warnungenAn: ziel });
		assert.equal(schalterZustellung(ed), ziel, 'Geste im Reiter Wetter kommt in der Zustellung nicht an');
		assert.deepEqual(await warnFelderImPost(ed), { alerts: ziel, ow: ziel });
	});

	test('Geste in der Zustellung baut den (verborgen gemounteten) Reiter Wetter neu auf', async () => {
		const ed = await editor();
		const tabs = findeKomponenten(ed.ast, 'WetterTab');
		assert.equal(tabs.length, 2, 'Messaufbau: Desktop + Mobil');
		// jeder WetterTab steht in einem {#key …}-Block, dessen Schluessel die Geste aendert
		const schluessel: string[] = [];
		(function lauf(n: unknown, key: string | null): void {
			if (n === null || typeof n !== 'object') return;
			if (Array.isArray(n)) return n.forEach((x) => lauf(x, key));
			const k = n as Knoten;
			const neu = k.type === 'KeyBlock' ? ed.quelle.slice(k.expression.start, k.expression.end) : key;
			if (k.type === 'Component' && k.name === 'WetterTab') schluessel.push(neu ?? '');
			for (const f of Object.keys(k)) if (f !== 'parent' && f !== 'loc') lauf(k[f], neu);
		})(ed.ast.fragment, null);
		assert.equal(schluessel.length, 2);
		for (const s of schluessel) assert.ok(s, 'WetterTab steht in keinem {#key}-Block — er zeigt nach der Geste den alten Wert');
		const vorher = schluessel.map((s) => JSON.stringify(werte(s, ed.u)));
		ed.u.handleAlarmOfficialWarningsChange(true);
		const nachher = schluessel.map((s) => JSON.stringify(werte(s, ed.u)));
		for (let i = 0; i < schluessel.length; i++) assert.notEqual(nachher[i], vorher[i], `Schluessel ${schluessel[i]} aendert sich bei der Geste nicht`);
	});
});
