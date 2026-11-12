// Fix-Loop 1 Issue #2794 S3a Teil-PR 3, Adversary-Findings F001 (HIGH) und F002 (Vergleichs-Teil):
//
// F001: Im Anlegen eines Orts-Briefings steht der WetterTab nur im Schritt Wetter und wird beim
// Wechsel in den Schritt Zustellung zerstoert. Beim Zurueckkehren liest er die Abo-Sicht
// `wetterAbo` des Editors neu — fehlte dort `display_config.ampel`, fiel er auf die
// Standardvorlage des Profils zurueck, und sein erster Stand-Bericht ueberschrieb die vom
// Nutzer gewaehlte Vorlage, Grenzen und Alarm-ab-Stufen still (POST mit Standard).
// F002: Die Ampel muss im Anlege-POST ankommen (`display_config.ampel`), inklusive der Ampel aus
// dem ersten Stand-Bericht des WetterTab (Anlegen ohne jede Aenderung).
//
// Gemessen dort, wo es WIRKT: die ECHTEN Instanz-Skripte von CompareNewEditor.svelte und
// WetterTab.svelte (svelteInstanzPruefstand.ts) werden verbunden wie im Markup
// (`preset={wetterAbo}`, `onAnlegeStand={handleWetterAnlegeStand}`). Ein Reiterwechsel ist das
// Zerstoeren und Neuaufbauen des WetterTab mit der dann aktuellen `wetterAbo`. Der POST wird
// am gesaeten `api.post` mitgeschnitten (Muster trip_new_alarme_verdrahtung.test.ts).
// Vorlagen/Katalog kommen live aus dem Python-Core (wetterTabDaten.ts), der Vergleichs-Katalog
// aus `output.renderers.compare_metric_catalog` (Quelle von GET /api/compare/metrics).
//
//   cd frontend && npm test -- src/lib/components/compare-new/__tests__/f001_f002_vergleich_anlegen_ampel.test.ts

import { test, describe, before, after } from 'node:test';
import assert from 'node:assert/strict';
import { execFileSync } from 'node:child_process';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

import { umgebungFuer, findeKomponenten, attributAusdruck, ohneTypen, werte, type Knoten } from '../../shared/__tests__/svelteInstanzPruefstand.ts';
import { live, REPO } from '../../shared/wetter-tab/__tests__/wetterTabDaten.ts';
import { toCompareSelectionEntries } from '../../shared/weather-metrics-tab/compareMetricSelection.ts';
import * as Z from '../../shared/wetter-tab/wetterZustand.ts';
import type { Ampel } from '../../../types.ts';

const HIER = dirname(fileURLToPath(import.meta.url));
const EDITOR = join(HIER, '..', 'CompareNewEditor.svelte');
const WETTER_TAB = join(HIER, '..', '..', 'organisms', 'wetter-tab', 'WetterTabInhalt.svelte');

const PY_KATALOG = [
	'import sys, json',
	"sys.path.insert(0, 'src'); sys.path.insert(0, '.')",
	'from output.renderers.compare_metric_catalog import get_compare_metric_catalog',
	"print(json.dumps({'metrics': get_compare_metric_catalog(lang='de')}, ensure_ascii=False))"
].join('\n');
const KATALOG_ANTWORT = JSON.parse(execFileSync('uv', ['run', 'python3', '-c', PY_KATALOG], { cwd: REPO, encoding: 'utf-8' }).trim());
const KATALOG = toCompareSelectionEntries(KATALOG_ANTWORT);

/** GET /api/compare/metrics fuer den Katalog-Lader des Editors (sonst kein Netz). */
let vorherFetch: typeof globalThis.fetch;
before(() => {
	vorherFetch = globalThis.fetch;
	(globalThis as { fetch: unknown }).fetch = async (input: unknown) => {
		const pfad = new URL(String(input), 'http://gz.invalid').pathname;
		if (pfad === '/api/compare/metrics') return new Response(JSON.stringify(KATALOG_ANTWORT), { status: 200, headers: { 'Content-Type': 'application/json' } });
		return new Response('{}', { status: 404 });
	};
});
after(() => {
	(globalThis as { fetch: unknown }).fetch = vorherFetch;
});

/** Lese-Client des WetterTab: echte Antworten von /api/metrics und /api/templates. */
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
		untrack: (fn: () => unknown) => fn(),
		stateOverride: undefined,
		vorlage: null,
		locations: [],
		alarmeCatalog: KATALOG, // Stand nach onMount (hydrateAlarmeTab)
		api: {
			post: async (url: string, payload: Knoten) => {
				gesendet.push({ url, payload });
				return { id: 'neu-1' };
			}
		}
	});
	assert.equal(typeof u.handleWetterAnlegeStand, 'function', 'Messaufbau: handleWetterAnlegeStand nicht herleitbar');
	assert.equal(typeof u.speichereNeuenVergleich, 'function', 'Messaufbau: speichereNeuenVergleich nicht herleitbar');
	assert.ok(u.wiz && typeof u.wiz === 'object', 'Messaufbau: wiz nicht herleitbar');
	// `wetterAbo` ist `$derived` — der Pruefstand wertet es einmal aus; ein Remount liest den
	// dann aktuellen Wert, darum hier der ECHTE Ausdruck aus dem Quelltext neu ausgewertet.
	const decl = (ast.instance.content.body as Knoten[])
		.filter((s) => s.type === 'VariableDeclaration')
		.flatMap((s) => s.declarations as Knoten[])
		.find((d) => d.id?.name === 'wetterAbo');
	assert.ok(decl, 'Messaufbau: wetterAbo fehlt im Editor');
	const wetterAbo = () => werte(ohneTypen(quelle, decl.init), u) as Z.AboSicht;
	let offen: Promise<void> = Promise.resolve();
	const stand = (n: unknown) => {
		offen = u.handleWetterAnlegeStand(n) as Promise<void>;
	};
	return { ast, quelle, u, gesendet, wetterAbo, stand, fertig: () => offen };
}

type Ed = Awaited<ReturnType<typeof editor>>;

/** WetterTab montieren (createMode) wie im Markup und den ersten Ladevorgang abwarten. */
async function wetterTabMontieren(ed: Ed): Promise<Knoten> {
	const { u } = await umgebungFuer(WETTER_TAB, {
		context: 'vergleich',
		preset: ed.wetterAbo(),
		trip: undefined,
		createMode: true,
		saveController: undefined,
		enqueueHubWrite: undefined,
		onTripUpdate: undefined,
		onCompareUpdate: undefined,
		onAnlegeStand: ed.stand,
		api: LIVE_API
	});
	assert.equal(typeof u.laden, 'function', 'Messaufbau: laden() des WetterTab nicht herleitbar');
	await u.laden();
	assert.equal(u.phase, 'bereit', 'Messaufbau: WetterTab hat nicht geladen');
	await ed.fertig();
	return u;
}

const ampelVon = (p: Knoten): Ampel | undefined => (p.display_config as Knoten | undefined)?.ampel;

describe('F001/F002: Vergleich anlegen — die Ampel ueberlebt den Reiterwechsel und reist im POST', () => {
	test('Markup-Verdrahtung: jeder WetterTab im Editor bekommt preset={wetterAbo} und onAnlegeStand={handleWetterAnlegeStand}', async () => {
		const { ast, quelle } = await editor();
		const tabs = findeKomponenten(ast, 'WetterTab');
		assert.equal(tabs.length, 2, 'Messaufbau: Desktop + Mobil');
		for (const t of tabs) {
			assert.equal(attributAusdruck(t, quelle, 'preset'), 'wetterAbo');
			assert.equal(attributAusdruck(t, quelle, 'onAnlegeStand'), 'handleWetterAnlegeStand');
			assert.equal(attributAusdruck(t, quelle, 'createMode'), 'true');
		}
	});

	test('F002: Anlegen ohne Aenderung — der erste Stand-Bericht bringt die Vorlagen-Ampel in den POST', async () => {
		const ed = await editor();
		const wt = await wetterTabMontieren(ed);
		ed.u.wiz.name = 'Test';
		await ed.u.speichereNeuenVergleich();
		assert.equal(ed.gesendet.length, 1, `kein POST: ${JSON.stringify(ed.gesendet)}`);
		assert.equal(ed.gesendet[0].url, '/api/compare/presets');
		const a = ampelVon(ed.gesendet[0].payload);
		assert.ok(a, 'POST ohne display_config.ampel — das Abo faellt in Python auf das Profil zurueck');
		assert.equal(a!.template, wt.stand.vorlageId);
		// F-A1 (AC-20): der Reiter zeigt „an" (ODER-Regel) — der POST setzt BEIDE Felder gleich.
		assert.equal(wt.stand.warnungenAn, true, 'Messaufbau: Standard ist „an"');
		assert.equal(ed.gesendet[0].payload.official_alerts_enabled, true);
		assert.equal((ed.gesendet[0].payload.official_warnings as Knoten).enabled, true, 'AC-20: official_warnings.enabled weicht vom Schalter ab');
	});

	test('F001: Vorlage „Wassersport" + Boeen „Alarm ab Rot", Wechsel zu Zustellung und zurueck ⇒ Stand bleibt, POST traegt ihn', async () => {
		const ed = await editor();
		const wt1 = await wetterTabMontieren(ed);
		const v = wt1.daten.vorlagen;
		assert.notEqual(wt1.stand.vorlageId, 'wassersport', 'Messaufbau: Profil-Standard darf nicht schon Wassersport sein');
		wt1.vorlageSetzen(Z.mitVorlage(wt1.stand, 'wassersport', v));
		wt1.aendern(Z.mitAlarmAb(wt1.stand, 'gust', 'red'));
		await ed.fertig();
		const gemeldet = structuredClone(ed.u.wetterAmpel) as Ampel;
		assert.equal(gemeldet?.template, 'wassersport', 'Messaufbau: Stand-Bericht kam nicht beim Editor an');
		assert.equal(gemeldet.metrics?.gust?.alarm_ab, 'red', 'Messaufbau: Alarm ab kam nicht beim Editor an');

		// Reiterwechsel Wetter → Zustellung → Wetter: der WetterTab wird neu aufgebaut.
		const wt2 = await wetterTabMontieren(ed);
		assert.equal(wt2.stand.vorlageId, 'wassersport', 'Remount zeigt nicht mehr die gewaehlte Vorlage');
		assert.equal(wt2.stand.ampel.metrics?.gust?.alarm_ab, 'red', 'Remount zeigt „Alarm ab" nicht mehr');
		assert.deepEqual([...wt2.stand.auswahl].sort(), [...wt1.stand.auswahl].sort(), 'Remount verliert Metriken der Auswahl');
		assert.deepEqual(ed.u.wetterAmpel, gemeldet, 'der erste Stand-Bericht nach dem Remount hat die Ampel ueberschrieben');

		ed.u.wiz.name = 'Test';
		await ed.u.speichereNeuenVergleich();
		const p = ed.gesendet[0].payload;
		assert.deepEqual(ampelVon(p), gemeldet, 'POST traegt nicht die eingestellte Ampel');
		// AC-37: active_metrics im POST = Auswahl des Reiters, im Speicherformat {metric_id, aggregation}.
		const am = (p.display_config as Knoten).active_metrics as Knoten[];
		assert.ok(am.every((m) => typeof m === 'object' && typeof m.metric_id === 'string'), `active_metrics nicht im Speicherformat: ${JSON.stringify(am)}`);
		assert.deepEqual([...new Set(am.map((m) => m.metric_id))].sort(), [...wt1.stand.auswahl].sort(), 'POST-Auswahl weicht von der Ampel-Auswahl ab');
	});
});

// Fix-Loop 2, F-A1 (AC-20/AC-21/AC-37/AC-38): die uebrigen Felder des Rueckkanals am POST bzw.
// dort, wo sie wirken. `wiz.activeMetricKeys` speist die Wertebereiche-Vorbelegung und damit
// `corridors` im POST; die Vorbelegung selbst rechnet shared/wetter-tab/anlegeVorbelegung.ts
// (eigene Tests, anlege_vorbelegung.test.ts), sie ist hier nicht ausgewertet.
describe('F-A1 (Vergleich): Warnungen, Radar, Tagesfenster und Auswahl aus dem Reiter Wetter', () => {
	test('Warnungen aus, Radar an, Tagesfenster 6–21, eine Metrik entfernt ⇒ POST und Wertebereiche-Auswahl folgen; Remount behaelt alles', async () => {
		const ed = await editor();
		const wt1 = await wetterTabMontieren(ed);
		const weg = wt1.stand.auswahl.find((id: string) => KATALOG.some((e) => e.metric_id === id));
		assert.ok(weg, 'Messaufbau: keine Metrik der Auswahl im Vergleichs-Katalog');
		const wegSchluessel = KATALOG.filter((e) => e.metric_id === weg).map((e) => e.metric);
		assert.equal(wt1.stand.warnungenAn, true, 'Messaufbau: Standard ist „an"');
		assert.equal(wt1.stand.radarAn, false, 'Messaufbau: Standard ist „aus"');
		wt1.aendern({ ...Z.ohneMetrik(wt1.stand, weg), warnungenAn: false, radarAn: true, tagesfenster: { start: 6, end: 21 } });
		await ed.fertig();

		// Wertebereiche-Vorbelegung bekommt die neue Auswahl: sie liest `wiz.activeMetricKeys`
		// (seit #2794 Teil-PR 4a direkt im Effekt des Editors, vorher ueber die Einbettung
		// `{...corridorPropsAus(wiz)}` eines versteckten CorridorEditors).
		const keys = ed.u.wiz.activeMetricKeys as string[];
		assert.ok(Array.isArray(keys) && keys.length > 0, `Wertebereiche bekommen keine Auswahl: ${JSON.stringify(keys)}`);
		for (const k of wegSchluessel) assert.ok(!keys.includes(k), `entfernte Metrik ${k} steht noch in der Wertebereiche-Auswahl`);

		const wt2 = await wetterTabMontieren(ed); // Reiterwechsel
		assert.equal(wt2.stand.warnungenAn, false, 'Remount zeigt die Warnungen wieder an');
		assert.equal(wt2.stand.radarAn, true, 'Remount zeigt Radar wieder aus');
		assert.deepEqual(wt2.stand.tagesfenster, { start: 6, end: 21 }, 'Remount verliert das Tagesfenster');
		assert.ok(!wt2.stand.auswahl.includes(weg), 'Remount bringt die entfernte Metrik zurueck');

		ed.u.wiz.name = 'Test';
		await ed.u.speichereNeuenVergleich();
		const p = ed.gesendet[0].payload;
		assert.equal(p.official_alerts_enabled, false, 'AC-20: official_alerts_enabled im POST');
		assert.equal((p.official_warnings as Knoten).enabled, false, 'AC-20: official_warnings.enabled im POST');
		assert.equal(p.radar_alert_enabled, true, 'AC-21: radar_alert_enabled im POST');
		assert.equal(p.day_window_start_hour, 6, 'AC-21: Tagesfenster-Anfang im POST');
		assert.equal(p.day_window_end_hour, 21, 'AC-21: Tagesfenster-Ende im POST');
		const am = (p.display_config as Knoten).active_metrics as Knoten[];
		assert.ok(!am.some((m) => m.metric_id === weg), 'entfernte Metrik steht im POST');
	});
});
