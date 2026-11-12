// Fix-Loop 1 — Issue #2794 S3a Teil-PR 4b, Adversary F001 (AC-32 U4):
// die VERDRAHTUNG der Alarm-Zeile in trip-detail/HubOverview.svelte als Verhalten.
// Spec: docs/specs/modules/feat_2794_s3a_teil4_entfernen.md („Präzisierungen": U4)
//
// Gemessen wird am Wirkort, nicht im Modell:
//   (a) nach onMount (Vorlagen geladen) zeigt die Alarm-Zeile den „Alarm ab"-Zähler des
//       Reiters Wetter („x von y Metriken lösen einen Alarm aus …"), nicht „—";
//   (b) ein Trip, der NUR über die Ampel alarmiert (alert_on_changes aus, keine Regeln,
//       kein Preset), gilt als aktiv — die Erwartung kommt aus der echten Python-Regel
//       `ampel_alarmquelle_aktiv`, nicht aus einer Frontend-Kopie;
//   (c) scheitert der Abruf /api/templates, steht „—" und die Zeile ist nicht aktiv.
//
// Messaufbau (wie hub_uebersicht_verdrahtung_laufzeit.test.ts): kein DOM im Projekt, der
// SSR-Render führt kein onMount aus. Deshalb läuft das ECHTE Instanz-Skript über den
// Prüfstand (`umgebungFuer`); der onMount-Rückruf aus dem Quelltext wird registriert und
// ausgeführt. Das Netz ist ein Fetch-Ersatz am Ausgang (`$lib/api.js` ist das echte Modul),
// beantwortet mit den ECHTEN Antworten von /api/templates und /api/metrics (Python-Core,
// `live()`). Die Props der Alarm-Zeile (`time`, `active`) werden über die ECHTEN
// Attribut-Ausdrücke der Einbettung <ReportLine kind="alert" …> ausgewertet.
//
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types \
//     --experimental-test-module-mocks --test \
//     src/lib/components/trip-detail/__tests__/hub_overview_alarm_ab_verdrahtung.test.ts

import { test, describe, afterEach } from 'node:test';
import assert from 'node:assert/strict';
import { register } from 'node:module';
import { execFileSync } from 'node:child_process';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';
import {
	umgebungFuer,
	findeKomponenten,
	attributAusdruck,
	werte,
	ohneTypen,
	type Knoten
} from '../../shared/__tests__/svelteInstanzPruefstand.ts';
import { live } from '../../shared/wetter-tab/__tests__/wetterTabDaten.ts';

const HIER = dirname(fileURLToPath(import.meta.url));
// __tests__ -> trip-detail -> components -> lib -> src -> frontend
const FRONTEND = resolve(HIER, '..', '..', '..', '..', '..');
const REPO = resolve(FRONTEND, '..');
const COMPONENTS = resolve(HIER, '..', '..');
const HUB_OVERVIEW = join(HIER, '..', 'HubOverview.svelte');
const basis = pathToFileURL(FRONTEND + '/').href;
register(pathToFileURL(join(FRONTEND, 'test-env-dynamic-private-stub-hooks.mjs')).href, basis);
register(pathToFileURL(join(FRONTEND, 'test-app-environment-stub-hooks.mjs')).href, basis);
register(pathToFileURL(join(FRONTEND, 'test-svelte-ssr-hooks.mjs')).href, basis);

const { tr, locale } = await import(pathToFileURL(join(FRONTEND, 'src', 'lib', 'i18n', 'index.ts')).href);
const am = await import(pathToFileURL(join(COMPONENTS, 'shared', 'wetter-tab', 'ampelModell.ts')).href);
const wz = await import(pathToFileURL(join(COMPONENTS, 'shared', 'wetter-tab', 'wetterZustand.ts')).href);

type Json = any; // eslint-disable-line @typescript-eslint/no-explicit-any

/** Trip ohne jede bisherige Alarmquelle — einzige mögliche Quelle ist die Ampel (Vorlage „allgemein"). */
const TRIP: Json = {
	id: 't-2794-4b-verdrahtung',
	name: 'Ampel-Übersicht',
	stages: [{ id: 'T1', name: 'Tag 1', date: '2099-07-01', waypoints: [{ id: 'G1', name: 'Start', lat: 47.0, lon: 11.0, elevation_m: 1000 }] }],
	report_config: { enabled: true, alert_on_changes: false },
	alert_rules: [],
	display_config: { trip_id: 't-2794-4b-verdrahtung', metrics: [{ metric_id: 'gust', enabled: true }], ampel: { template: 'allgemein' } }
};

/** Erwartung „aktiv" aus der echten Server-Regel (Python). */
function serverAktiv(trip: Json): boolean {
	const PY = [
		'import sys, json',
		"sys.path.insert(0, 'src'); sys.path.insert(0, '.')",
		'from app.loader import load_trip_from_dict',
		'from services.trip_alert import ampel_alarmquelle_aktiv',
		'print(json.dumps(bool(ampel_alarmquelle_aktiv(load_trip_from_dict(json.loads(sys.stdin.read()))))))'
	].join('\n');
	const out = execFileSync('uv', ['run', 'python3', '-c', PY], { cwd: REPO, encoding: 'utf-8', input: JSON.stringify(trip) });
	return JSON.parse(out.trim().split('\n').pop()!);
}

// ── Netz: Fetch-Ersatz am Ausgang ────────────────────────────────────────────

const echtesFetch = globalThis.fetch;
afterEach(() => {
	globalThis.fetch = echtesFetch;
	locale.set('de');
});

function netz(templatesOk: boolean) {
	const urls: string[] = [];
	const antwort = (status: number, body: unknown) =>
		new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } });
	globalThis.fetch = (async (eingabe: unknown) => {
		const url = String(eingabe);
		urls.push(url);
		if (url === '/api/templates') return templatesOk ? antwort(200, live().templates) : antwort(503, { detail: 'kaputt' });
		return antwort(404, { error: 'not found' });
	}) as typeof fetch;
	return urls;
}

async function setzen() {
	for (let i = 0; i < 20; i++) await new Promise((r) => setTimeout(r, 0));
}

/** Die ECHTE Herleitung `name` aus dem Quelltext erneut gegen `u` auswerten. */
function neuAuswerten(ast: Knoten, quelle: string, u: Knoten, name: string): unknown {
	for (const stmt of (ast.instance?.content?.body as Knoten[]) ?? []) {
		if (stmt.type !== 'VariableDeclaration') continue;
		for (const d of stmt.declarations as Knoten[]) {
			if (d.id?.type === 'Identifier' && d.id.name === name && d.init) {
				u[name] = werte(ohneTypen(quelle, d.init), u);
				return u[name];
			}
		}
	}
	throw new Error(`Deklaration „${name}" nicht gefunden`);
}

/** HubOverview mit echtem Instanz-Skript; onMount-Rückrufe werden gesammelt und ausgeführt. */
async function hubOverview() {
	const beimMount: Array<() => unknown> = [];
	const ho = await umgebungFuer(
		HUB_OVERVIEW,
		{
			trip: TRIP,
			onJump: undefined,
			metricsCatalog: live().metrics,
			nextBriefing: null,
			// Der Lader des nächsten Briefings ist hier nicht Gegenstand der Messung.
			erstelleNaechstesBriefingLader: () => ({ wert: null }),
			onMount: (fn: () => unknown) => {
				beimMount.push(fn);
			}
		},
		{ jsAlsTs: true }
	);
	// Der Prüfstand wertet nur Deklarationen aus — onMount(...) ist eine Anweisung: registrieren.
	let gefunden = 0;
	for (const stmt of (ho.ast.instance?.content?.body as Knoten[]) ?? []) {
		const c = stmt.type === 'ExpressionStatement' ? stmt.expression : null;
		if (c?.type === 'CallExpression' && c.callee?.type === 'Identifier' && c.callee.name === 'onMount') {
			werte(ohneTypen(ho.quelle, c), ho.u);
			gefunden++;
		}
	}
	assert.ok(gefunden > 0, 'Messaufbau: HubOverview hat keinen onMount-Aufruf');
	for (const n of ['api', 'eig', 'wetterAlarmAktiv', 'alarmAbText']) {
		assert.ok(n in ho.u, `Messaufbau: „${n}" fehlt in der HubOverview-Umgebung`);
	}
	const [alarmZeile] = findeKomponenten(ho.ast, 'ReportLine').filter((e) =>
		((e.attributes ?? []) as Knoten[]).some((a) => a.name === 'kind' && a.value?.[0]?.data === 'alert')
	);
	assert.ok(alarmZeile, 'Messaufbau: <ReportLine kind="alert"> fehlt');
	/** Die Props der Alarm-Zeile, wie die Einbettung sie nach erneuter Herleitung reicht. */
	const zeile = () => {
		for (const n of ['eig', 'wetterAlarmAktiv', 'alarmAbText']) neuAuswerten(ho.ast, ho.quelle, ho.u, n);
		const p = (name: string) => {
			const a = attributAusdruck(alarmZeile, ho.quelle, name);
			assert.ok(a, `Messaufbau: Attribut ${name} fehlt an der Alarm-Zeile`);
			return werte(a!, ho.u);
		};
		return { time: p('time') as string, active: p('active') as boolean };
	};
	const mounten = async () => {
		for (const fn of beimMount) fn();
		await setzen();
	};
	return { zeile, mounten };
}

describe('F001 / AC-32 U4: Alarm-Zeile der Trip-Übersicht am Wirkort', () => {
	test('(a)+(b) nach onMount: Zähler des Reiters Wetter und „aktiv" wie der Server', async () => {
		const urls = netz(true);
		const ho = await hubOverview();
		const vorher = ho.zeile();
		assert.equal(vorher.time, '—', 'vor dem Laden der Vorlagen keine geratene Zahl');

		await ho.mounten();
		assert.deepEqual(urls, ['/api/templates'], `Abrufe: ${JSON.stringify(urls)}`);
		const nachher = ho.zeile();

		const d = live();
		const vorlagen = am.vorlagenAusTemplates(d.templates);
		const stand = wz.standAusAbo('route', TRIP, vorlagen);
		const z = am.alarmZaehler(stand.ampel, stand.auswahl, am.eigenschaftenAusKatalog(d.metrics));
		assert.equal(z.art, 'zaehler', 'Fixtur-Schutz: Böen ist alarmfähig');
		assert.equal(nachher.time, tr(z.schluessel, z.werte), `Alarm-Zeile zeigt nicht den Zähler: „${nachher.time}"`);
		assert.match(nachher.time, /^\d+ von \d+ Metriken lösen einen Alarm aus/);

		const soll = serverAktiv(TRIP);
		assert.equal(soll, true, 'Fixtur-Schutz: der Server alarmiert über die Ampel');
		assert.equal(nachher.active, soll, 'Übersicht zeigt „aus", obwohl der Server über die Ampel alarmiert');
	});

	test('(c) Ladefehler /api/templates ⇒ „—", Zeile nicht aktiv', async () => {
		const urls = netz(false);
		const ho = await hubOverview();
		await ho.mounten();
		assert.deepEqual(urls, ['/api/templates']);
		const z = ho.zeile();
		assert.equal(z.time, '—', `bei Ladefehler steht eine Zahl: „${z.time}"`);
		assert.equal(z.active, false);
	});
});
