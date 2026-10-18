// Fix-Loop 4 — Issue #2278, F025/F026 (AC-1, AC-7, AC-12, AC-16): der ECHTE Pause-Weg des Compare-Hubs
// als Verhalten, ueber die ganze Kette:
//   Seite handleAction('pause'|'resume') -> togglePause -> compareDetailRef.toggleActiveFromParent
//   -> CompareDetail.toggleActiveFromParent -> tabs.toggleActiveFromParent (CompareTabs) -> handleToggleActive
//   -> PUT { schedule, previous_schedule } gegen einen Ersatz-Server (api.put, haelt Zustand).
// Alle drei Instanzen sind der ECHTE Instanz-Code (Pruefstand `umgebungFuer`); die zwei `bind:this`-Verdrahtungen
// (Seite -> CompareDetail, CompareDetail -> CompareTabs) setzt der Test von Hand und sichert sie unten per
// Bindungstest (BindDirective `this`) ab — ohne DOM ist das Mounten selbst nicht moeglich.
//
// Pfadregel #1409: relativ zu DIESER Datei.
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types \
//     --experimental-test-module-mocks --test src/lib/components/compare/__tests__/compare_hub_pausieren_kette.test.ts

import { test, describe, before } from 'node:test';
import assert from 'node:assert/strict';
import { register } from 'node:module';
import path from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { umgebungFuer, type Knoten } from '../../shared/__tests__/svelteInstanzPruefstand.ts';
import { ladeSvelte, komponenten, funktion, kurz, collect, bedingungen } from '../../shared/__tests__/aktionsmodellAst.ts';

const HIER = path.dirname(fileURLToPath(import.meta.url));
const FRONTEND = path.resolve(HIER, '../../../../..');
const TABS = path.join(HIER, '..', 'CompareTabs.svelte');
const DETAIL = path.join(HIER, '..', 'CompareDetail.svelte');
const SEITE = path.join(FRONTEND, 'src/routes/compare/[id]/+page.svelte');

register(
	pathToFileURL(path.join(FRONTEND, 'test-env-dynamic-private-stub-hooks.mjs')).href,
	pathToFileURL(FRONTEND + '/').href
);

interface Put {
	url: string;
	body: Record<string, unknown>;
}

/** Ersatz-Server: `put` fuehrt den Rumpf per Merge in den gespeicherten Stand ein (wie der Go-Store). */
function baue(start: Record<string, unknown>, ablauf: string[]) {
	const stand: Record<string, unknown> = { ...start };
	const puts: Put[] = [];
	const zustand = { scheitern: false };
	const api = {
		put: async (url: string, body: unknown) => {
			ablauf.push('put');
			puts.push({ url, body: body as Record<string, unknown> });
			if (zustand.scheitern) throw new Error('HTTP 500');
			Object.assign(stand, body);
			return { ...stand };
		},
		get: async () => ({ ...stand })
	};
	return { stand, puts, api, zustand };
}

async function kette(opts: { schedule?: string; previous?: string; currentId?: string } = {}) {
	const start = {
		id: 'c1',
		name: 'Vergleich',
		location_ids: ['a', 'b'],
		schedule: opts.schedule ?? 'daily',
		previous_schedule: opts.previous ?? opts.schedule ?? 'daily',
		unbekanntes_feld: 'server'
	};
	const ablauf: string[] = [];
	const server = baue(start, ablauf);
	const meldungen: string[] = [];
	const fehler: string[] = [];
	const ctl: Knoten = {
		setSaving: () => {},
		setSaved: () => meldungen.push('saved'),
		setError: (m: string) => fehler.push(m),
		flush: async () => void ablauf.push('flush'),
		imWiederholen: false
	};
	const zeitplaene: string[] = [];
	// Der Prop `preset` ist veraltet (anderer Fremdfeld-Wert) — currentPreset ist der gepflegte Stand.
	const stale = { ...start, unbekanntes_feld: 'VERALTET' };
	const { u: tabs } = await umgebungFuer(TABS, { preset: stale, locations: [], saveController: ctl, api: server.api, extractMessage: (e: any) => String(e?.message ?? e), onScheduleChange: (s: string) => zeitplaene.push(s) });
	tabs.currentPreset = { ...start, id: opts.currentId ?? 'c1' };
	const { u: detail } = await umgebungFuer(DETAIL, { preset: stale, locations: [], saveController: ctl });
	detail.tabs = tabs; // bind:this={tabs}
	const { u: seite } = await umgebungFuer(SEITE, { data: { preset: { ...start }, locations: [], profile: {} } }, { jsAlsTs: true });
	seite.compareDetailRef = detail; // bind:this={compareDetailRef}
	const aktion = async (id: string) => {
		const vorher = server.puts.length;
		seite.handleAction(id);
		const ende = Date.now() + 5000;
		while ((server.puts.length === vorher || seite.isPausing !== false) && Date.now() < ende) {
			await new Promise((r) => setTimeout(r, 5));
		}
		if (server.puts.length === vorher && !server.zustand.scheitern) assert.fail(`„${id}" hat keinen PUT ausgeloest`);
		if (seite.isPausing !== false) assert.fail('Pausieren ist nicht zur Ruhe gekommen');
	};
	return { server, tabs, detail, seite, aktion, meldungen, fehler, zeitplaene, ablauf };
}

describe('F025: der Pause-Weg schreibt wirklich (Seite -> CompareDetail -> CompareTabs -> PUT)', () => {
	test('„pause" -> ein PUT { schedule:"manual", previous_schedule:<gemerkt> } auf den Vergleich; Anzeige folgt', async () => {
		const k = await kette({ schedule: 'weekly' });
		await k.aktion('pause');
		assert.deepEqual(k.server.puts.map((p) => [p.url, p.body]), [
			['/api/compare/presets/c1', { schedule: 'manual', previous_schedule: 'weekly' }]
		]);
		assert.equal(k.tabs.localSchedule, 'manual');
		assert.deepEqual(k.zeitplaene, ['manual']);
		assert.equal(k.seite.pauseError, null);
		assert.deepEqual(k.meldungen, ['saved']);
	});

	test('Rundreise Pausieren -> Fortsetzen stellt den Zeitplan wieder her (previous_schedule wird gemerkt)', async () => {
		const k = await kette({ schedule: 'weekly' });
		await k.aktion('pause');
		await k.aktion('resume');
		assert.equal(k.server.stand.schedule, 'weekly');
		assert.equal(k.tabs.localSchedule, 'weekly');
		assert.deepEqual(k.server.puts[1].body, { schedule: 'weekly', previous_schedule: 'weekly' });
	});

	test('F026: ausstehende Speicherungen der Reiter werden VOR dem Status-PUT abgeschlossen (flush, dann put)', async () => {
		const k = await kette();
		await k.aktion('pause');
		assert.deepEqual(k.ablauf, ['flush', 'put']);
	});

	test('F026: pausiert wird der LAUFENDE Zeitplan gemerkt, nicht der veraltete previous_schedule des Props', async () => {
		// Server: laeuft "weekly", gemerkt (veraltet) "daily" — Pausieren muss "weekly" als previous_schedule schreiben.
		const k = await kette({ schedule: 'weekly', previous: 'daily' });
		await k.aktion('pause');
		assert.deepEqual(k.server.puts[0].body, { schedule: 'manual', previous_schedule: 'weekly' });
		await k.aktion('resume');
		assert.equal(k.server.stand.schedule, 'weekly', 'Fortsetzen stellt den vor dem Pausieren laufenden Zeitplan wieder her');
	});

	test('zweimal hin und zurueck (jeweils nach der Antwort): manual, weekly, manual, weekly — Anzeige und Server stimmen', async () => {
		const k = await kette({ schedule: 'weekly' });
		const server: string[] = [];
		const lokal: string[] = [];
		for (const id of ['pause', 'resume', 'pause', 'resume']) {
			await k.aktion(id);
			server.push(String(k.server.stand.schedule));
			lokal.push(String(k.tabs.localSchedule));
		}
		assert.deepEqual(server, ['manual', 'weekly', 'manual', 'weekly']);
		assert.deepEqual(lokal, server);
		assert.deepEqual(k.zeitplaene, server, 'die Header-Pille (onScheduleChange) folgt jedem Wechsel');
	});

	test('der Rumpf traegt nur { schedule, previous_schedule } — kein Fremdfeld, URL aus dem gepflegten currentPreset', async () => {
		const k = await kette({ schedule: 'daily', currentId: 'c-aktuell' });
		await k.aktion('pause');
		assert.deepEqual(Object.keys(k.server.puts[0].body).sort(), ['previous_schedule', 'schedule']);
		assert.equal(k.server.puts[0].url, '/api/compare/presets/c-aktuell', 'URL kommt aus currentPreset, nicht aus dem veralteten Prop');
		assert.equal(k.server.stand.unbekanntes_feld, 'server', 'Fremdfelder des Servers bleiben unangetastet');
	});
});

describe('F026: Fehler werden gemeldet, nicht als Erfolg verbucht', () => {
	test('PUT-Fehler: toggleActiveFromParent liefert false, Fehleranzeige des Controllers und pauseError der Seite gesetzt', async () => {
		const k = await kette();
		k.server.zustand.scheitern = true;
		assert.equal(await k.detail.toggleActiveFromParent(), false);
		assert.equal(k.fehler.length, 1);
		assert.match(k.fehler[0], /500/);
		assert.equal(k.tabs.localSchedule, 'daily', 'lokaler Zeitplan bleibt beim alten Stand');
		k.seite.handleAction('pause');
		const ende = Date.now() + 5000;
		while (typeof k.seite.pauseError !== 'string' && Date.now() < ende) await new Promise((r) => setTimeout(r, 5));
		assert.match(k.seite.pauseError, /Status-Änderung fehlgeschlagen/);
	});

	test('Erfolg liefert true (und meldet keinen Fehler)', async () => {
		const k = await kette();
		assert.equal(await k.detail.toggleActiveFromParent(), true);
		assert.deepEqual(k.fehler, []);
	});

	test('CompareDetail ohne verbundenes CompareTabs liefert false (kein stilles true)', async () => {
		const k = await kette();
		k.detail.tabs = undefined;
		assert.equal(await k.detail.toggleActiveFromParent(), false);
	});
});

describe('Bindungen, die das Mounten sonst herstellt (bind:this)', () => {
	const bindThis = (ast: Knoten, komponente: string) =>
		komponenten(ast, komponente).map((c) =>
			(c.attributes ?? []).filter((a: Knoten) => a.type === 'BindDirective' && a.name === 'this').map((a: Knoten) => kurz(a.expression))
		);

	test('CompareDetail bindet CompareTabs an `tabs`, die Seite bindet CompareDetail an `compareDetailRef` — unbedingt', () => {
		const detail = ladeSvelte(DETAIL);
		const seite = ladeSvelte(SEITE);
		assert.deepEqual(bindThis(detail, 'CompareTabs'), [['tabs']]);
		assert.deepEqual(bindThis(seite, 'CompareDetail'), [['compareDetailRef']]);
		assert.deepEqual(bedingungen(detail.fragment, komponenten(detail, 'CompareTabs')[0]), []);
	});

	test('CompareDetail leitet an tabs.toggleActiveFromParent() weiter, CompareTabs an handleToggleActive()', () => {
		const detail = ladeSvelte(DETAIL);
		const tabs = ladeSvelte(TABS);
		assert.equal(kurz(funktion(detail, 'toggleActiveFromParent').body), '{ return tabs?.toggleActiveFromParent() ?? Promise.resolve(false) }');
		assert.equal(kurz(funktion(tabs, 'toggleActiveFromParent').body), '{ return handleToggleActive() }');
		assert.equal(collect(tabs.instance, (n) => n.type === 'FunctionDeclaration' && n.id?.name === 'toggleActiveFromParent').length, 1);
	});
});
