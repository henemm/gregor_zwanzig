// Fix-Loop 2, Issue #1433 — F101/F102/F103 fuer den Ortsvergleich (Paritaet AC-20):
// (1) Seitenverdrahtung von routes/compare/[id]/+page.svelte (Seitenaufbau, Callback),
// (2) Regel 1/2 am Hub: kein Neuaufbau ueber sichtbare Eingabe, neuere Eingabe gewinnt.
//
// Spec: docs/specs/bugfix/trip_mehrreiter_konfliktschutz.md — AC-19, AC-20.
// Der Hub (CompareTabs.svelte:717) hydriert reaktiv auf jede neue `preset`-Referenz;
// deshalb setzt die Seite `currentPreset` NICHT bei 'geholt', sondern erst nach vollem
// Erfolg ('wiederholt', frisch geholt).
//
// Ausfuehren:
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types \
//     --experimental-test-module-mocks --test \
//     src/lib/components/compare/__tests__/compare_retry_fehlerpfade_kein_verlust.test.ts

import { test, describe, beforeEach, afterEach } from 'node:test';
import assert from 'node:assert/strict';
import { register } from 'node:module';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

import { api } from '../../../api.ts';
import { clearEtagRegistry, discardEtag, getKnownEtag, istKonflikt, markiereKonflikt } from '../../../etagRegistry.ts';
import type { ComparePreset } from '../../../types.ts';
import { createPutQueue } from '../compareHubPersistenz.ts';
import { hydrateAlarmFieldsFromPreset } from '../compareHubHydration.ts';
import { erstelleAlarmeVergleichSpeicherung } from '../../shared/alarmeVergleichSpeicherung.ts';
import { createController } from '../../shared/__tests__/versandVergleichPruefstand.ts';
import { reiterAufbau } from '../../shared/__tests__/compareReiterAufbauPruefstand.ts';
import { umgebungFuer, type Knoten } from '../../shared/__tests__/svelteInstanzPruefstand.ts';
import {
	createGoMergeServer,
	vollerVergleich,
	type GoMergeServer
} from '../../shared/__tests__/goMergeServerPruefstand.ts';

const HIER = dirname(fileURLToPath(import.meta.url));
const FRONTEND = resolve(HIER, '../../../../..');
const SEITE = join(FRONTEND, 'src/routes/compare/[id]/+page.svelte');
register(
	pathToFileURL(join(FRONTEND, 'test-env-dynamic-private-stub-hooks.mjs')).href,
	pathToFileURL(FRONTEND + '/').href
);

const ID = 'cp-1433-fl2';
const PFAD = `/api/compare/presets/${ID}`;
let server: GoMergeServer;
let fehler: ((method: string) => boolean) | null = null;

beforeEach(async () => {
	clearEtagRegistry();
	fehler = null;
	server = createGoMergeServer({ [ID]: vollerVergleich(ID) });
	server.install();
	const fake = globalThis.fetch;
	(globalThis as { fetch: unknown }).fetch = async (input: unknown, init?: RequestInit) => {
		if (fehler?.((init?.method ?? 'GET').toUpperCase())) {
			return new Response(JSON.stringify({ error: 'boom', detail: 'Serverfehler' }), {
				status: 500,
				headers: { 'Content-Type': 'application/json' }
			});
		}
		return fake(input as never, init);
	};
	await api.get(PFAD);
});
afterEach(() => {
	server.restore();
	delete (globalThis as { window?: unknown }).window;
});

async function seite(opt: { etag?: string; browser?: boolean; ctl?: unknown } = {}): Promise<Knoten> {
	const { u } = await umgebungFuer(SEITE, {
		data: { preset: vollerVergleich(ID), etag: opt.etag },
		browser: opt.browser ?? true,
		hubSaveCtl: opt.ctl ?? createController(ID)
	});
	return u;
}

describe('F102: Seitenverdrahtung /compare/[id]', () => {
	test('N15/N16: der Seitenaufbau beendet einen offenen Konflikt und uebernimmt den Stempel (im Skript-Kopf)', async () => {
		markiereKonflikt(ID);
		await seite({ etag: server.etagOf(ID) });
		assert.equal(istKonflikt(ID), false);
		assert.equal(getKnownEtag(ID), server.etagOf(ID));
	});

	test('F105: im SSR-Prozess (browser=false) bleibt die Registry unberuehrt', async () => {
		clearEtagRegistry();
		await seite({ etag: server.etagOf(ID), browser: false });
		assert.equal(getKnownEtag(ID), undefined);
	});

	test('N17: die Seite registriert ihren Uebernahme-Callback am Controller', async () => {
		const ctl = createController(ID);
		await seite({ ctl });
		assert.equal(typeof ctl.onAdopt, 'function');
	});

	test("N18/F202: bei 'geholt' bleibt `currentPreset` unveraendert und der Hub wird nicht neu aufgebaut (Seite, mit window und abweichendem Serverstand)", async () => {
		// Mit gesetztem `window` MUSS ein faelschlich reagierender Callback sichtbar werden:
		// ohne `window` wirft er im try an `window.location` und der catch verschluckt es
		// (Mutation G15 war vakuum-gruen, Adversary-Runde 3).
		(globalThis as { window?: unknown }).window = {
			location: { href: `http://x/compare/${ID}?tab=alarme` },
			dispatchEvent: () => true,
			addEventListener: () => {}
		};
		const ctl = createController(ID);
		const u = await seite({ ctl });
		const name = (u.currentPreset as ComparePreset).name;
		server.fremdSchreiben(ID, { name: 'Server-Stand' });
		ctl.onAdopt!({ ...(vollerVergleich(ID) as object), name: 'GET-Stand' }, 'geholt');
		await new Promise((r) => setTimeout(r, 80));
		assert.equal((u.currentPreset as ComparePreset).name, name, 'CompareTabs:717 wuerde den offenen Reiter sonst neu hydrieren');
		assert.equal(u.uebernommeneFassung, 0);
	});

	test("N19/F103: bei 'wiederholt' wird frisch geholt, uebernommen und der Hub (mit offenem Reiter) neu aufgebaut", async () => {
		(globalThis as { window?: unknown }).window = {
			location: { href: `http://x/compare/${ID}?tab=alarme` },
			dispatchEvent: () => true,
			addEventListener: () => {}
		};
		const ctl = createController(ID);
		const u = await seite({ ctl });
		server.fremdSchreiben(ID, { name: 'Server-Stand' });
		ctl.onAdopt!({}, 'wiederholt');
		await new Promise((r) => setTimeout(r, 50));
		assert.equal((u.currentPreset as ComparePreset).name, 'Server-Stand');
		assert.equal(u.uebernommeneFassung, 1);
		assert.equal(u.tabNachUebernahme, 'alarme');
	});
});

/** Alarme-Reiter des Hubs mit echtem Controller, Queue, Hydration. */
function alarmeReiter() {
	let basis = vollerVergleich(ID) as unknown as ComparePreset;
	const ctl = createController(ID);
	const queue = createPutQueue();
	const zustand: Record<string, unknown> = {};
	hydrateAlarmFieldsFromPreset(zustand, basis, []);
	const speicherung = erstelleAlarmeVergleichSpeicherung({
		client: api,
		preset: () => basis,
		enqueueHubWrite: <T>(fn: () => Promise<T>) => queue.enqueue(fn),
		onCompareUpdate: (p: ComparePreset) => {
			basis = p;
		},
		saveController: ctl,
		zustand
	});
	return {
		ctl,
		zustand,
		aendern(feld: string, wert: unknown) {
			zustand[feld] = wert;
			speicherung.aenderungMelden();
		}
	};
}
const fertig = async (ctl: ReturnType<typeof createController>) => {
	await ctl.flush();
	const l = ctl.laufendeSpeicherung;
	if (l) await l;
};
const puts = () => server.mitschnitt.filter((e) => e.method === 'PUT');

describe('F101 (Regel 1/2) am Hub: die zuletzt gesehene und gespeicherte Eingabe gewinnt', () => {
	test('(a) Retry scheitert 500, derselbe Reiter speichert mit 412 ⇒ Konflikt bleibt, Nochmal speichern schreibt BEIDE Eingaben', async () => {
		server.fremdSchreiben(ID, { name: 'Fremder 1' });
		const h = alarmeReiter();
		h.aendern('alertCooldownMinutes', 77);
		await fertig(h.ctl);
		assert.equal(h.ctl.state, 'conflict');

		fehler = (m) => m === 'PUT';
		await h.ctl.retryConflict();
		fehler = null;
		assert.equal(h.ctl.state, 'conflict', 'gescheiterte Wiederholung: der Knopf bleibt');
		assert.equal(h.zustand.alertCooldownMinutes, 77, 'der offene Reiter behaelt seine sichtbare Eingabe (kein Rollback beim Wiederholen)');

		server.fremdSchreiben(ID, { name: 'Fremder 2' });
		h.aendern('alertQuietFrom', '21:00');
		await fertig(h.ctl);
		assert.equal(h.ctl.state, 'conflict', 'nie „Gespeichert" ohne Server-Stand');

		await h.ctl.retryConflict();
		const s = server.stand(ID);
		assert.equal(s.alert_cooldown_minutes, 77, 'die erste Eingabe ging nicht verloren');
		assert.equal(s.alert_quiet_from, '21:00');
		assert.equal(s.name, 'Fremder 2');
		assert.equal(h.ctl.state, 'idle');
	});

	// Fix-Loop 4 (F301a) AENDERT diese Zusicherung bewusst: nach gescheitertem Retry traegt die
	// Registry wieder den Stempel von VOR dem GET — der Save des (veralteten) Hub-Reiters
	// bekommt 412 statt 200 (sonst ueberschriebe er die Fremdaenderung, PX2). Der neuere Rumpf
	// ersetzt den alten Eintrag, „Nochmal speichern" schreibt ihn, danach nichts mehr.
	test('(b) Retry scheitert 500, derselbe Reiter speichert danach ⇒ 412 (Konflikt bleibt), Nochmal speichern schreibt die neuere Eingabe, kein Altstand darueber', async () => {
		server.fremdSchreiben(ID, { name: 'Fremder 1' });
		const h = alarmeReiter();
		h.aendern('alertCooldownMinutes', 77);
		await fertig(h.ctl);
		fehler = (m) => m === 'PUT';
		await h.ctl.retryConflict();
		fehler = null;

		h.aendern('alertCooldownMinutes', 99);
		await fertig(h.ctl);
		assert.equal(puts().at(-1)!.status, 412);
		assert.notEqual(server.stand(ID).alert_cooldown_minutes, 99, 'Server unveraendert');
		assert.equal(h.ctl.state, 'conflict');

		await h.ctl.retryConflict();
		assert.equal(puts().at(-1)!.status, 200);
		assert.equal(server.stand(ID).alert_cooldown_minutes, 99);
		assert.equal(h.ctl.state, 'idle');

		const vorher = puts().length;
		await h.ctl.retryConflict();
		assert.equal(puts().length, vorher);
		assert.equal(server.stand(ID).alert_cooldown_minutes, 99, 'kein Altstand (77) ueber der neueren Eingabe');
	});
});

describe('F101 (imWiederholen): scheitert der Retry mit 500, behaelt JEDER Compare-Reiter seine Eingabe und sendet sie erneut', () => {
	const faelle = [
		['versand', 'Versand'],
		['wertebereiche', 'Wertebereiche'],
		['wetterMetriken', 'Wetter-Metriken']
	] as const;
	for (const [reiter, titel] of faelle) {
		test(`${titel}: 500 beim Retry setzt die Anzeige nicht zurueck; der naechste Versuch schreibt die Eingabe auf den Server`, async () => {
			server.fremdSchreiben(ID, { name: 'Fremder 1' });
			const stand0 = JSON.stringify(server.stand(ID));
			const h = reiterAufbau(reiter, vollerVergleich(ID) as unknown as ComparePreset);
			h.aendern();
			h.speicherung.aenderungMelden();
			await fertig(h.ctl);
			assert.equal(h.ctl.state, 'conflict', 'Vorbedingung: 412');
			const anzeige = JSON.stringify(h.zustand);

			fehler = (m) => m === 'PUT';
			await h.ctl.retryConflict();
			fehler = null;
			assert.equal(h.ctl.state, 'conflict');
			assert.equal(JSON.stringify(h.zustand), anzeige, 'kein Rollback der sichtbaren Eingabe beim Wiederholen');
			assert.equal(JSON.stringify(server.stand(ID)), stand0, 'Vorbedingung: nichts geschrieben');

			await h.ctl.retryConflict();
			assert.equal(h.ctl.state, 'idle');
			assert.equal(puts().at(-1)!.status, 200);
			assert.notEqual(JSON.stringify(server.stand(ID)), stand0, 'die Eingabe steht jetzt auf dem Server');
			assert.equal(server.stand(ID).name, 'Fremder 1');
		});
	}
});

describe('F501 / F502 (Fix-Loop 5): gescheiterter Retry laesst keinen Save mit veraltetem Reiterstand durch', () => {
	test('Teil-Erfolg: Alarme ok, Wertebereiche scheitert ⇒ ein NIE gespeicherter, veralteter Versand-Reiter bekommt 412; Fremdwert bleibt, Eingabe nicht still geschrieben', async () => {
		server.fremdSchreiben(ID, { name: 'Fremder 1', morning_time: '06:30' });
		const geteilt = { ctl: createController(ID), queue: createPutQueue() };
		const start = vollerVergleich(ID) as unknown as ComparePreset;
		const al = reiterAufbau('alarme', start, api, geteilt);
		const we = reiterAufbau('wertebereiche', start, api, geteilt);
		const ve = reiterAufbau('versand', start, api, geteilt); // veraltet, nie gespeichert
		const ctl = geteilt.ctl;
		al.aendern();
		al.speicherung.aenderungMelden();
		await fertig(ctl);
		assert.equal(ctl.state, 'conflict', 'Vorbedingung: Konflikt');
		we.aendern();
		we.speicherung.aenderungMelden();
		await fertig(ctl);

		let n = 0;
		fehler = (m) => m === 'PUT' && ++n === 2; // erster Wiederholungs-PUT ok, zweiter 500
		await ctl.retryConflict();
		fehler = null;
		assert.equal(ctl.state, 'conflict');
		assert.equal(istKonflikt(ID), true);

		const vorher = puts().length;
		ve.aendern(); // morningTime = 07:15
		ve.speicherung.aenderungMelden();
		await fertig(ctl);
		const neue = puts().slice(vorher);
		assert.ok(neue.length > 0, 'Messaufbau: der Save wurde gesendet');
		assert.ok(neue.every((e) => e.status === 412), 'der Save des veralteten Reiters wird abgelehnt');
		assert.equal(server.stand(ID).morning_time, '06:30', 'Fremdwert bleibt, Eingabe nicht still geschrieben');
		assert.equal(ctl.state, 'conflict');
	});

	test('F502 Konflikt OHNE Stempel, Retry scheitert ⇒ Folge-Save traegt If-Match und bekommt 412, Server unveraendert', async () => {
		server.fremdSchreiben(ID, { name: 'Fremder 1' });
		const h = alarmeReiter();
		h.aendern('alertCooldownMinutes', 77);
		await fertig(h.ctl);
		assert.equal(h.ctl.state, 'conflict');
		discardEtag(ID); // synthetisch: kein Stempel vor dem GET

		fehler = (m) => m === 'PUT';
		await h.ctl.retryConflict();
		fehler = null;
		assert.equal(h.ctl.state, 'conflict');

		const vorher = puts().length;
		const standVorher = JSON.stringify(server.stand(ID));
		h.aendern('alertCooldownMinutes', 99);
		await fertig(h.ctl);
		const neue = puts().slice(vorher);
		assert.ok(neue.length > 0, 'Messaufbau: der Folge-Save wurde gesendet');
		assert.ok(neue.every((e) => !!e.ifMatch && e.status === 412), 'If-Match gesetzt und abgelehnt');
		assert.equal(JSON.stringify(server.stand(ID)), standVorher, 'Server unveraendert');
		assert.equal(h.ctl.state, 'conflict');
	});
});
