// Fix-Loop 1 Issue #2794 S3a Teil-PR 3, Adversary-Finding F002 (Trip-Teil), dazu der
// F001-Fall des Trips (Adversary: Neuaufbau des WetterTab beim Wechsel Desktop ↔ Mobil):
//
// Die Ampel des Reiters Wetter muss im Anlege-POST /api/trips ankommen
// (`display_config.ampel`) — auch ohne jede Aenderung (erster Stand-Bericht des WetterTab im
// Anlegen) — und ein neu aufgebauter WetterTab darf den gemeldeten Stand nicht mit dem
// Profil-Standard ueberschreiben.
//
// Gemessen dort, wo es WIRKT: die ECHTEN Instanz-Skripte von TripNewEditor.svelte und
// WetterTab.svelte (svelteInstanzPruefstand.ts), verbunden wie im Markup
// (`trip={wetterAnlegeTrip}`, `onAnlegeStand={handleWetterAnlegeStand}`); der POST wird am
// gesaeten `api.post` mitgeschnitten und durchlaeuft den echten `buildCreateTripPayload`
// (Muster trip_new_alarme_verdrahtung.test.ts). Vorlagen/Katalog live aus dem Python-Core.
//
//   cd frontend && npm test -- src/lib/components/trip-new/__tests__/f002_trip_anlegen_ampel_im_post.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

import { umgebungFuer, findeKomponenten, attributAusdruck, ohneTypen, werte, type Knoten } from '../../shared/__tests__/svelteInstanzPruefstand.ts';
import { live } from '../../shared/wetter-tab/__tests__/wetterTabDaten.ts';
import * as Z from '../../shared/wetter-tab/wetterZustand.ts';
import type { Ampel } from '../../../types.ts';

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
	assert.equal(typeof u.handleWetterAnlegeStand, 'function', 'Messaufbau: handleWetterAnlegeStand nicht herleitbar');
	assert.equal(typeof u.buildAndSave, 'function', 'Messaufbau: buildAndSave nicht herleitbar');
	// `wetterAnlegeTrip` ist `$derived` — beim Neuaufbau gilt der dann aktuelle Wert.
	const decl = (ast.instance.content.body as Knoten[])
		.filter((s) => s.type === 'VariableDeclaration')
		.flatMap((s) => s.declarations as Knoten[])
		.find((d) => d.id?.name === 'wetterAnlegeTrip');
	assert.ok(decl, 'Messaufbau: wetterAnlegeTrip fehlt im Editor');
	const neuAbleiten = () => {
		// stubTrip haengt an weatherMetrics/reportConfig — ebenfalls neu auswerten.
		const stub = (ast.instance.content.body as Knoten[])
			.filter((s) => s.type === 'VariableDeclaration')
			.flatMap((s) => s.declarations as Knoten[])
			.find((d) => d.id?.name === 'stubTrip');
		assert.ok(stub, 'Messaufbau: stubTrip fehlt im Editor');
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

async function speichern(ed: Ed): Promise<Knoten> {
	ed.u.ready = true; // `ready` haengt am GPX-Upload — fuer den Speicherweg ohne Belang
	const id = await ed.u.buildAndSave();
	assert.equal(id, 'neu-1', `buildAndSave scheiterte: ${ed.u.saveError}`);
	assert.equal(ed.gesendet.length, 1);
	assert.equal(ed.gesendet[0].url, '/api/trips');
	return ed.gesendet[0].payload;
}

describe('F002 (Trip): die Ampel des Reiters Wetter reist im POST /api/trips', () => {
	test('Markup-Verdrahtung: jeder WetterTab bekommt trip={wetterAnlegeTrip} und onAnlegeStand={handleWetterAnlegeStand}', async () => {
		const { ast, quelle } = await editor();
		const tabs = findeKomponenten(ast, 'WetterTab');
		assert.equal(tabs.length, 2, 'Messaufbau: Desktop + Mobil');
		for (const t of tabs) {
			assert.equal(attributAusdruck(t, quelle, 'trip'), 'wetterAnlegeTrip');
			assert.equal(attributAusdruck(t, quelle, 'onAnlegeStand'), 'handleWetterAnlegeStand');
			assert.equal(attributAusdruck(t, quelle, 'createMode'), 'true');
		}
	});

	test('ohne Aenderung: der erste Stand-Bericht bringt Vorlagen-Ampel und Auswahl in den POST', async () => {
		const ed = await editor();
		const wt = await wetterTabMontieren(ed);
		const p = await speichern(ed);
		const a = (p.display_config as Knoten).ampel as Ampel | undefined;
		assert.ok(a, 'POST ohne display_config.ampel — das Abo faellt in Python auf das Profil zurueck');
		assert.equal(a!.template, wt.stand.vorlageId);
		const aktiv = ((p.display_config as Knoten).metrics as Knoten[]).filter((m) => m.enabled).map((m) => m.metric_id);
		assert.deepEqual([...aktiv].sort(), [...wt.stand.auswahl].sort(), 'AC-37: metrics[] und Ampel-Auswahl laufen auseinander');
	});

	test('Vorlage „Wassersport" + Boeen „Alarm ab Rot": POST traegt sie; ein Neuaufbau des WetterTab ueberschreibt sie nicht', async () => {
		const ed = await editor();
		const wt1 = await wetterTabMontieren(ed);
		assert.notEqual(wt1.stand.vorlageId, 'wassersport', 'Messaufbau: Profil-Standard darf nicht schon Wassersport sein');
		wt1.vorlageSetzen(Z.mitVorlage(wt1.stand, 'wassersport', wt1.daten.vorlagen));
		wt1.aendern(Z.mitAlarmAb(wt1.stand, 'gust', 'red'));
		const gemeldet = structuredClone(ed.u.wetterAmpel) as Ampel;
		assert.equal(gemeldet?.template, 'wassersport', 'Messaufbau: Stand-Bericht kam nicht beim Editor an');
		assert.equal(gemeldet.metrics?.gust?.alarm_ab, 'red');

		// Wechsel Desktop ↔ Mobil: der WetterTab wird neu aufgebaut.
		const wt2 = await wetterTabMontieren(ed);
		assert.equal(wt2.stand.vorlageId, 'wassersport', 'Neuaufbau zeigt nicht mehr die gewaehlte Vorlage');
		assert.equal(wt2.stand.ampel.metrics?.gust?.alarm_ab, 'red', 'Neuaufbau zeigt „Alarm ab" nicht mehr');
		assert.deepEqual(ed.u.wetterAmpel, gemeldet, 'der erste Stand-Bericht nach dem Neuaufbau hat die Ampel ueberschrieben');

		const p = await speichern(ed);
		assert.deepEqual((p.display_config as Knoten).ampel, gemeldet, 'POST traegt nicht die eingestellte Ampel');
	});
});

// Fix-Loop 2, F-A1 (AC-20/AC-21/AC-38): die uebrigen Felder des Rueckkanals — amtliche Warnungen
// (BEIDE Felder, AC-20) und Tagesfenster (Trip: report_config) — am POST, nicht am Baustein.
describe('F-A1 (Trip): Warnungen und Tagesfenster aus dem Reiter Wetter reisen im POST', () => {
	const warnung = (p: Knoten) => ({
		alerts: p.official_alerts_enabled,
		ow: (p.official_warnings as Knoten | undefined)?.enabled
	});

	test('ohne Aenderung: Warnungen an ⇒ official_alerts_enabled UND official_warnings.enabled true', async () => {
		const ed = await editor();
		const wt = await wetterTabMontieren(ed);
		assert.equal(wt.stand.warnungenAn, true, 'Messaufbau: Standard ist „an"');
		assert.deepEqual(warnung(await speichern(ed)), { alerts: true, ow: true });
	});

	test('Warnungen aus, Tagesfenster 6–21 ⇒ beide Warn-Felder false, report_config 6/21; ein Neuaufbau behaelt beides', async () => {
		const ed = await editor();
		const wt1 = await wetterTabMontieren(ed);
		wt1.aendern({ ...wt1.stand, warnungenAn: false, tagesfenster: { start: 6, end: 21 } });

		const wt2 = await wetterTabMontieren(ed); // Wechsel Desktop ↔ Mobil
		assert.equal(wt2.stand.warnungenAn, false, 'Neuaufbau zeigt die Warnungen wieder an');
		assert.deepEqual(wt2.stand.tagesfenster, { start: 6, end: 21 }, 'Neuaufbau verliert das Tagesfenster');

		const p = await speichern(ed);
		assert.deepEqual(warnung(p), { alerts: false, ow: false }, 'AC-20: beide Felder muessen im POST aus sein');
		const rc = p.report_config as Knoten;
		assert.equal(rc.day_window_start_hour, 6);
		assert.equal(rc.day_window_end_hour, 21);
	});
});
