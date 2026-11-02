// Issue #1721 (Epic #2259), Fix-Loop 1 (Adversary F002/F003): Verdrahtung des
// Schalters "Nacht-Stundentabelle in der Mail zeigen" im ECHTEN Reiter
// `WeatherMetricsTab.svelte`.
//
// Spec: docs/specs/modules/fix_1721_nachtausgabe.md — AC-1, AC-2, AC-3.
//
// WARUM SO: die Kernsuite hat kein DOM, und unter `svelte/server` rendert der
// Trip-Zweig nur die Lade-Huelle (catalogLoaded wird erst nach dem Fetch wahr).
// Gemessen wird deshalb am ECHTEN Quelltext mit dem ECHTEN Svelte-Compiler:
//   - unter WELCHEN Bedingungen die Checkbox (data-testid wm-night-block-toggle)
//     steht — die Bedingungskette wird gegen gesaete Zustaende AUSGEWERTET
//     (route/vergleich/createMode), nicht als Text verglichen;
//   - ihr `onchange`-/`checked`-Ausdruck aus dem Markup wird in der echten
//     Instanz-Umgebung ausgewertet und aufgerufen (= der Klick), gemessen am
//     Anfrage-Rumpf gegen den Ersatz-Server (Go-Merge-Semantik);
//   - initFromTrip(), handleDiscard() und der isDirty-Ausdruck laufen echt.
//
// Ausfuehren:
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types \
//     --experimental-test-module-mocks --test \
//     src/lib/components/trip-detail/__tests__/trip_night_block_schalter_verdrahtung.test.ts

import { test, describe, afterEach } from 'node:test';
import assert from 'node:assert/strict';

import { api } from '../../../api.ts';
import { clearEtagRegistry } from '../../../etagRegistry.ts';
import { createFakeTripServer, type FakeTripServer } from '../../../__tests__/fakeTripServer.ts';
import * as P from './tripMehrreiterPruefstand.ts';
import {
	umgebungFuer,
	werte,
	ohneTypen,
	type Knoten
} from '../../shared/__tests__/svelteInstanzPruefstand.ts';
import { bedingungen, mitAttribut, attrAusdruck } from '../../shared/__tests__/aktionsmodellAst.ts';

const SCHALTER = 'wm-night-block-toggle';

function tripMitNachtBlock(wert: boolean | undefined): Record<string, unknown> {
	const t = P.vollerTrip();
	const dc = { ...(t.display_config as Record<string, unknown>) };
	if (wert === undefined) delete dc.show_night_block;
	else dc.show_night_block = wert;
	return { ...t, display_config: dc };
}

/** Echte Instanz-Umgebung des Reiters (ohne Speicher-Controller). */
async function reiter(saat: Knoten): Promise<{ u: Knoten; ast: Knoten; quelle: string }> {
	P.registriereHooks();
	return umgebungFuer(P.DATEI.wetterMetriken, {
		context: 'route',
		createMode: false,
		saveController: undefined,
		onTripUpdate: undefined,
		untrack: (fn: () => unknown) => fn(),
		...saat
	});
}

function schalterKnoten(ast: Knoten): Knoten {
	const treffer = mitAttribut(ast, 'data-testid', SCHALTER);
	assert.equal(treffer.length, 1, `genau eine Checkbox mit data-testid="${SCHALTER}" erwartet`);
	return treffer[0];
}

/** Attribut-Ausdruck aus dem Markup, in der Instanz-Umgebung ausgewertet. */
function attributWert(inst: { u: Knoten; ast: Knoten; quelle: string }, name: string): unknown {
	const ausdruck = attrAusdruck(schalterKnoten(inst.ast), name);
	assert.ok(ausdruck, `Checkbox hat kein Attribut ${name}`);
	return werte(ohneTypen(inst.quelle, ausdruck), inst.u);
}

/** Wird die Checkbox bei diesem Zustand gerendert? Alle Bedingungen der Kette auswerten. */
function gerendert(inst: { u: Knoten; ast: Knoten }): boolean {
	const kette = bedingungen(inst.ast.fragment, schalterKnoten(inst.ast));
	assert.ok(kette, 'Checkbox liegt nicht erreichbar im Markup');
	return kette.every((b) => Boolean(werte(b, inst.u)));
}

/** Der `$derived`-Ausdruck von isDirty, frisch gegen den aktuellen Zustand ausgewertet. */
function isDirty(inst: { u: Knoten; ast: Knoten; quelle: string }): boolean {
	for (const stmt of (inst.ast.instance?.content?.body as Knoten[]) ?? []) {
		if (stmt.type !== 'VariableDeclaration') continue;
		for (const d of stmt.declarations as Knoten[]) {
			if (d.id?.name !== 'isDirty') continue;
			return Boolean(werte(ohneTypen(inst.quelle, d.init.arguments[0]), inst.u));
		}
	}
	throw new Error('isDirty nicht im Instanz-Skript gefunden');
}

describe('AC-1: Schalter nur im Trip, nicht im Ortsvergleich, nicht beim Anlegen', () => {
	async function mitZustand(saat: Knoten) {
		const inst = await reiter({ trip: tripMitNachtBlock(undefined), ...saat });
		// Geladener Reiter: sonst steht der Trip-Zweig hinter der Lade-Huelle.
		inst.u.catalogLoaded = true;
		inst.u.loadError = null;
		return inst;
	}

	test('route + bestehender Trip: Checkbox wird gerendert', async () => {
		assert.equal(gerendert(await mitZustand({ context: 'route', createMode: false })), true);
	});

	test('Ortsvergleich (context="vergleich"): Checkbox wird NICHT gerendert', async () => {
		assert.equal(gerendert(await mitZustand({ context: 'vergleich', createMode: false })), false);
	});

	test('Anlegen (createMode): Checkbox wird NICHT gerendert', async () => {
		assert.equal(gerendert(await mitZustand({ context: 'route', createMode: true })), false);
	});
});

describe('AC-2: Anfangszustand nach initFromTrip()', () => {
	test('Alt-Trip ohne Feld: Checkbox checked (Standard an), Wert wird nicht gesendet', async () => {
		const inst = await reiter({ trip: tripMitNachtBlock(undefined) });
		inst.u.showNightBlock = false; // initFromTrip() muss den Stand selbst herstellen
		inst.u.nightBlockSend = true;
		(inst.u.initFromTrip as () => void)();
		assert.equal(attributWert(inst, 'checked'), true);
		assert.equal(inst.u.nightBlockSend, false);
	});

	test('Trip mit show_night_block=false: Checkbox nicht checked, Wert wird gesendet', async () => {
		const inst = await reiter({ trip: tripMitNachtBlock(false) });
		inst.u.showNightBlock = true;
		inst.u.nightBlockSend = false;
		(inst.u.initFromTrip as () => void)();
		assert.equal(attributWert(inst, 'checked'), false);
		assert.equal(inst.u.nightBlockSend, true);
	});
});

describe('AC-3: Verwerfen und Ungespeichert-Zustand', () => {
	test('Schalter umlegen macht den Reiter dirty; Verwerfen stellt Schalter und Sende-Merker zurueck', async () => {
		const inst = await reiter({ trip: tripMitNachtBlock(undefined) });
		(inst.u.initFromTrip as () => void)();
		assert.equal(isDirty(inst), false, 'Vorbedingung: frisch geladen ist der Reiter sauber');

		const onchange = attributWert(inst, 'onchange') as (e: unknown) => void;
		onchange({ target: { checked: false } });
		assert.equal(inst.u.showNightBlock, false);
		assert.equal(isDirty(inst), true, 'Umlegen muss den Reiter als ungespeichert markieren');

		(inst.u.handleDiscard as () => void)();
		assert.equal(inst.u.showNightBlock, true, 'Verwerfen muss den Schalter zuruecksetzen');
		assert.equal(inst.u.nightBlockSend, false, 'Verwerfen muss den Sende-Merker zuruecksetzen');
		assert.equal(isDirty(inst), false, 'nach dem Verwerfen ist der Reiter wieder sauber');
	});
});

describe('AC-3: gespeicherter Wert false ist nach dem Laden sauber', () => {
	test('Trip mit show_night_block=false: nach initFromTrip() ist der Reiter nicht dirty', async () => {
		const inst = await reiter({ trip: tripMitNachtBlock(false) });
		(inst.u.initFromTrip as () => void)();
		assert.equal(inst.u.showNightBlock, false, 'Vorbedingung: gespeichertes false geladen');
		assert.equal(
			isDirty(inst),
			false,
			'der Snapshot muss den geladenen Schalterstand fuehren, sonst gilt der Reiter ohne Geste als geaendert'
		);
	});
});

describe('AC-3: Klick auf die gerenderte Checkbox speichert show_night_block=false', () => {
	let server: FakeTripServer;
	afterEach(() => server.restore());

	test('Alt-Trip ohne Feld: onchange aus dem Markup sendet false an /weather-config', async () => {
		clearEtagRegistry();
		server = createFakeTripServer({ merge: true });
		server.install();
		server.seed(P.TRIP_ID, tripMitNachtBlock(undefined));
		await api.get(P.TRIP_PFAD);
		const a = P.neuerAufbau(tripMitNachtBlock(undefined));
		const wm = await P.wetterMetrikenReiter(a);
		wm.inst.u.userTouched = false; // die Geste selbst muss das Speicher-Gate oeffnen

		const onchange = attributWert(wm.inst, 'onchange') as (e: unknown) => void;
		onchange({ target: { checked: false } });
		await P.fertig(a.ctl);

		const put = server.calls.find((c) => c.method === 'PUT' && /\/weather-config$/.test(c.path));
		assert.ok(put, 'Klick auf die Checkbox muss /weather-config speichern');
		assert.equal((put.anfrage as Record<string, unknown>).show_night_block, false);
	});
});
