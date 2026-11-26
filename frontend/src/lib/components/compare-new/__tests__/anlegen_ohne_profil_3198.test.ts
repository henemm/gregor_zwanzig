// TDD RED — Issue #3198 (S4b-3, Teil von #2796, Epic #2791): Orts-Vergleich anlegen ohne
// Aktivitaetsprofil-Kacheln; maßgeblich ist die Vorlage im Reiter Wetter (ADR-0108).
// Spec: docs/specs/modules/feat_3198_s4b3_compare_anlegen_ohne_profil.md (AC-1..AC-9)
//
// Gemessen dort, wo es WIRKT (kein Mock-Theater):
//   * die ECHTE Payload-Funktion `buildNewComparePresetPayload` und die ECHTE Feldsatz-Factory,
//   * das ECHTE Instanz-Skript von CompareNewEditor.svelte, verbunden mit dem ECHTEN WetterTab
//     (Muster f001_f002_vergleich_anlegen_ampel.test.ts); mitgeschnitten wird nur `api.post`,
//   * die ECHTE Server-Aufloesung `src/app/ampel.py::template_id_for` auf die gesendete Nutzlast,
//   * das ECHTE SSR-Rendern des Anlege-Editors (f10Pruefstand, Desktop + Mobil, DE + EN),
//   * die Kataloge DE/EN (Daten, nicht Quelltext).
//
// Vertrag (Tech-Lead-Entscheidung der Spec, Implementation Details 1-6):
//   * Neuanlage schickt konstant `profil: 'allgemein'`.
//   * Neuanlage schickt IMMER `display_config.ampel.template` = angezeigte Vorlage.
//   * Feldsatz-Feld `vorlageId` (Standard `STANDARD_VORLAGE` = 'allgemein') ist die Quelle
//     der angezeigten Vorlage; `feldsatzAusVorlage` (?from=<id>) belegt es aus der Quelle
//     (ampel.template → preset_name → profil → allgemein).
//
//   cd frontend && npm test -- src/lib/components/compare-new/__tests__/anlegen_ohne_profil_3198.test.ts

import { test, describe, before, after } from 'node:test';
import assert from 'node:assert/strict';
import { execFileSync } from 'node:child_process';
import { readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

import { umgebungFuer, ohneTypen, werte, type Knoten } from '../../shared/__tests__/svelteInstanzPruefstand.ts';
import { aufgeloestVon, aufloesungPost, live, REPO } from '../../shared/wetter-tab/__tests__/wetterTabDaten.ts';
import { toCompareSelectionEntries } from '../../shared/weather-metrics-tab/compareMetricSelection.ts';
import * as Z from '../../shared/wetter-tab/wetterZustand.ts';
import { STANDARD_VORLAGE } from '../../shared/wetter-tab/ampelModell.ts';
import { vergleichVorbelegung } from '../../shared/wetter-tab/anlegeVorbelegung.ts';
import { buildCompareMetricDefs } from '../../shared/wetter-tab/compareMetricCatalogLoader.ts';
import {
	buildNewComparePresetPayload,
	buildComparePresetSavePayload,
	compareFeldsatzStandard
} from '../../compare/compareEditorSave.ts';
import { feldsatzAusVorlage } from '../compareNewVorlage.ts';
import type { ComparePreset, Location } from '../../../types.ts';

const HIER = dirname(fileURLToPath(import.meta.url));
const EDITOR = join(HIER, '..', 'CompareNewEditor.svelte');
const WETTER_TAB = join(HIER, '..', '..', 'organisms', 'wetter-tab', 'WetterTabInhalt.svelte');
const MESSAGES = join(HIER, '..', '..', '..', 'i18n', 'messages');

const PY_KATALOG = [
	'import sys, json',
	"sys.path.insert(0, 'src'); sys.path.insert(0, '.')",
	'from output.renderers.compare_metric_catalog import get_compare_metric_catalog',
	"print(json.dumps({'metrics': get_compare_metric_catalog(lang='de')}, ensure_ascii=False))"
].join('\n');
const KATALOG_ANTWORT = JSON.parse(execFileSync('uv', ['run', 'python3', '-c', PY_KATALOG], { cwd: REPO, encoding: 'utf-8' }).trim());
const KATALOG = toCompareSelectionEntries(KATALOG_ANTWORT);

/** Server-Aufloesung der Vorlage (Python `template_id_for`) auf eine gesendete Nutzlast. */
function serverVorlage(payload: Knoten): string {
	const py = [
		'import sys, json',
		"sys.path.insert(0, 'src'); sys.path.insert(0, '.')",
		'from app.ampel import template_id_for',
		'print(template_id_for(json.loads(sys.stdin.read())))'
	].join('\n');
	return execFileSync('uv', ['run', 'python3', '-c', py], { cwd: REPO, encoding: 'utf-8', input: JSON.stringify(payload) }).trim();
}

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

const LIVE_API = {
	get: async (pfad: string) => {
		const d = live();
		if (pfad === '/api/metrics') return d.metrics;
		if (pfad === '/api/templates') return d.templates;
		if (pfad === '/api/metric-presets') return [];
		throw new Error(`unerwartet: ${pfad}`);
	},
	post: aufloesungPost()
};

const ORTE = ['loc-a', 'loc-b', 'loc-c'].map((id) => ({ id, name: id, lat: 0, lon: 0 }));

// #3399 S2: die Seite loest die Quelle serverseitig auf und reicht `vorlageId` durch. Ohne
// ausdrueckliche Angabe nimmt der Pruefstand das ECHTE resolve_entwurf der Quelle (wie die Seite).
async function editor(opts: { stateOverride?: Knoten; vorlage?: Knoten | null; vorlageId?: string | null } = {}) {
	const vorlageId = opts.vorlageId !== undefined ? opts.vorlageId : opts.vorlage ? aufgeloestVon(opts.vorlage).vorlage_id : null;
	const gesendet: Array<{ url: string; payload: Knoten }> = [];
	const { ast, quelle, u } = await umgebungFuer(EDITOR, {
		untrack: (fn: () => unknown) => fn(),
		stateOverride: opts.stateOverride,
		vorlage: opts.vorlage ?? null,
		vorlageId,
		locations: ORTE,
		alarmeCatalog: KATALOG,
		api: {
			post: async (url: string, payload: Knoten) => {
				gesendet.push({ url, payload });
				return { id: 'neu-3198' };
			}
		}
	});
	assert.equal(typeof u.speichereNeuenVergleich, 'function', 'Messaufbau: speichereNeuenVergleich nicht herleitbar');
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
	return { u, gesendet, wetterAbo, stand, fertig: () => offen };
}
type Ed = Awaited<ReturnType<typeof editor>>;

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
	await u.laden();
	assert.equal(u.phase, 'bereit', 'Messaufbau: WetterTab hat nicht geladen');
	await ed.fertig();
	return u;
}

async function speichern(ed: Ed): Promise<Knoten> {
	ed.u.wiz.name = ed.u.wiz.name || 'Test 3198';
	ed.u.wiz.pickedIds = ed.u.wiz.pickedIds?.length ? ed.u.wiz.pickedIds : ['loc-a', 'loc-b'];
	await ed.u.speichereNeuenVergleich();
	assert.equal(ed.gesendet.length, 1, `erwartet genau EIN Speichern, gesehen ${ed.gesendet.length}`);
	return ed.gesendet[0].payload;
}
const vorlageImPost = (p: Knoten): unknown => ((p.display_config as Knoten | undefined)?.ampel as Knoten | undefined)?.template;

// ── AC-3: Neuanlage ohne Besuch des Reiters Wetter speichert die angezeigte Vorlage ──────
describe('AC-3: ohne Wetter-Besuch gilt die angezeigte Vorlage „Allgemein“ (nicht „Wandern“)', () => {
	test('Feldsatz-Standard traegt die Vorlage der Neuanlage: vorlageId = STANDARD_VORLAGE („allgemein“)', () => {
		assert.equal(STANDARD_VORLAGE, 'allgemein', 'Messaufbau');
		assert.equal(
			(compareFeldsatzStandard() as unknown as Knoten).vorlageId,
			'allgemein',
			'VERTRAG FEHLT (#3198): compareFeldsatzStandard() hat kein Feld `vorlageId` mit Standard „allgemein“'
		);
	});

	test('reine Nutzlast: profil ist konstant „allgemein“ — auch ohne und mit Rest-activityProfile', () => {
		const basis = { ...compareFeldsatzStandard(), name: 'X', pickedIds: ['a', 'b'] } as never;
		assert.equal(buildNewComparePresetPayload(basis).profil, 'allgemein', 'Rueckfall „wandern“ beim Anlegen (Widerspruch zur angezeigten Vorlage)');
		const mitRest = { ...compareFeldsatzStandard(), name: 'X', pickedIds: ['a', 'b'], activityProfile: 'wintersport' } as never;
		assert.equal(buildNewComparePresetPayload(mitRest).profil, 'allgemein', 'profil wird beim Anlegen noch aus einer Nutzerwahl abgeleitet');
	});

	test('Editor ohne Wetter-Besuch: POST traegt display_config.ampel.template = „allgemein“ und profil = „allgemein“', async () => {
		const ed = await editor();
		const p = await speichern(ed);
		assert.equal(p.profil, 'allgemein', `profil im POST: ${JSON.stringify(p.profil)}`);
		assert.equal(vorlageImPost(p), 'allgemein', `POST ohne ampel.template — der Server faellt auf das Profil zurueck: ${JSON.stringify((p.display_config as Knoten)?.ampel)}`);
	});

	test('Server-Aufloesung (Python template_id_for) der gesendeten Nutzlast ergibt „allgemein“', async () => {
		const ed = await editor();
		const p = await speichern(ed);
		assert.equal(serverVorlage(p), 'allgemein', 'Versand/Bewertung nutzen eine andere Vorlage als angezeigt');
	});

	test('Gegenprobe Rest-Saat: ein activityProfile im stateOverride beeinflusst die Neuanlage nicht mehr', async () => {
		const ed = await editor({ stateOverride: { activityProfile: 'wintersport' } });
		const p = await speichern(ed);
		assert.equal(p.profil, 'allgemein');
		assert.equal(vorlageImPost(p), 'allgemein');
	});
});

// ── AC-4: Vorlage im Reiter Wetter waehlen ⇒ genau diese wird gespeichert ─────────────────
describe('AC-4: im Reiter Wetter „Wintersport“ gewaehlt ⇒ POST traegt „wintersport“', () => {
	test('Vorlage Wintersport waehlen, speichern ⇒ ampel.template wintersport, profil allgemein, Server loest wintersport auf', async () => {
		const ed = await editor();
		const wt = await wetterTabMontieren(ed);
		assert.equal(wt.stand.vorlageId, 'allgemein', 'Messaufbau: der Reiter zeigt ohne Wahl „Allgemein“');
		wt.vorlageSetzen(Z.mitVorlage(wt.stand, 'wintersport', wt.daten.vorlagen, 'vergleich', wt.altSchluessel));
		await ed.fertig();
		const p = await speichern(ed);
		assert.equal(vorlageImPost(p), 'wintersport');
		assert.equal(p.profil, 'allgemein', 'profil folgt nicht mehr der Nutzerwahl');
		assert.equal(serverVorlage(p), 'wintersport');
	});
});

// ── AC-5: /compare/new?from=<id> übernimmt die Vorlage der Quelle ──────────────────────────
function quelle(over: Partial<ComparePreset> = {}): ComparePreset {
	return {
		id: 'cmp-quelle',
		name: 'Skitouren Tirol',
		location_ids: ['loc-a', 'loc-b'],
		schedule: 'daily',
		profil: 'wintersport',
		empfaenger: [],
		display_config: { region: 'Tirol' },
		...over
	} as unknown as ComparePreset;
}

describe('AC-5: Anlegen aus Vorlage (?from=<id>)', () => {
	test('reine Funktion: Quelle profil=wintersport ohne ampel.template ⇒ vorlageId „wintersport“', () => {
		const f = feldsatzAusVorlage(quelle(), ORTE as unknown as Location[], aufgeloestVon(quelle() as never).vorlage_id) as Knoten;
		assert.equal(f.vorlageId, 'wintersport', `VERTRAG FEHLT (#3198): feldsatzAusVorlage leitet die Vorlage nicht ab (vorlageId=${JSON.stringify(f.vorlageId)})`);
	});

	test('reine Funktion: Quelle mit ampel.template „wassersport“ (profil wandern) ⇒ vorlageId „wassersport“', () => {
		const q = quelle({ profil: 'wandern', display_config: { region: 'Tirol', ampel: { template: 'wassersport' } } } as never);
		const f = feldsatzAusVorlage(q, ORTE as unknown as Location[], aufgeloestVon(q as never).vorlage_id) as Knoten;
		assert.equal(f.vorlageId, 'wassersport', 'ampel.template der Quelle wird nicht uebernommen');
	});

	test('Editor mit Quelle profil=wintersport, ohne Wetter-Besuch gespeichert ⇒ POST ampel.template wintersport, profil allgemein', async () => {
		const ed = await editor({ vorlage: quelle() as unknown as Knoten });
		const p = await speichern(ed);
		assert.equal(vorlageImPost(p), 'wintersport', `Vorlage der Quelle geht verloren: ${JSON.stringify((p.display_config as Knoten)?.ampel)}`);
		assert.equal(p.profil, 'allgemein');
	});

	test('Editor mit Quelle profil=wintersport: der Reiter Wetter zeigt „Wintersport“ vorausgewaehlt', async () => {
		const ed = await editor({ vorlage: quelle() as unknown as Knoten });
		const wt = await wetterTabMontieren(ed);
		assert.equal(wt.stand.vorlageId, 'wintersport');
	});

	// #3399 S2 (AC-5): die Vorlage kommt aus der Server-Aufloesung der Seite, nicht aus der Rangfolge.
	test('#3399 S2: Server-ID „wassersport“ bei Quelle profil=wintersport ⇒ Reiter und POST „wassersport“', async () => {
		const ed = await editor({ vorlage: quelle() as unknown as Knoten, vorlageId: 'wassersport' });
		const wt = await wetterTabMontieren(ed);
		assert.equal(wt.stand.vorlageId, 'wassersport', 'Editor rechnet die Vorlage selbst statt der Server-ID');
		assert.equal(vorlageImPost(await speichern(ed)), 'wassersport');
	});

	test('#3399 S2: Aufloesung gescheitert (vorlageId null) ⇒ POST „allgemein“, Name und Orte der Quelle bleiben', async () => {
		const ed = await editor({ vorlage: quelle() as unknown as Knoten, vorlageId: null });
		const p = await speichern(ed);
		assert.equal(vorlageImPost(p), 'allgemein', 'bei Fehler geratene Vorlage aus der Rangfolge');
		assert.match(String(p.name), /Skitouren Tirol/);
		assert.deepEqual(p.location_ids, ['loc-a', 'loc-b']);
	});

	test('Editor mit Quelle ampel.template „wassersport“: Reiter zeigt und POST traegt „wassersport“', async () => {
		const ed = await editor({ vorlage: quelle({ profil: 'wandern', display_config: { region: 'Tirol', ampel: { template: 'wassersport' } } } as never) as unknown as Knoten });
		const wt = await wetterTabMontieren(ed);
		assert.equal(wt.stand.vorlageId, 'wassersport');
		const p = await speichern(ed);
		assert.equal(vorlageImPost(p), 'wassersport');
		assert.equal(p.profil, 'allgemein');
	});
});

// ── AC-7: Bearbeiten-Pfad laesst das gespeicherte profil unberuehrt (ADR-0101) ─────────────
describe('AC-7: Bearbeiten behaelt das gespeicherte profil', () => {
	test('buildComparePresetSavePayload reicht original.profil durch (kein Ueberschreiben mit „allgemein“)', () => {
		const original = quelle({ profil: 'sommer_trekking' } as never);
		const edits = { ...compareFeldsatzStandard(), name: 'X', pickedIds: ['loc-a', 'loc-b'], activityProfile: null, activeMetricKeys: [] };
		const { body } = buildComparePresetSavePayload(original, edits as never);
		assert.equal((body as unknown as Knoten).profil, 'sommer_trekking');
		assert.deepEqual((body as unknown as Knoten).id, original.id, 'Identitaet des Bestands');
	});
});

// ── AC-8: Wertebereiche-Vorbelegung bleibt „Allgemein“, unabhaengig von der Vorlage ───────
describe('AC-8: Vorbelegung der Wertebereiche folgt der Vorlage nicht', () => {
	test('vergleichVorbelegung mit vorlageId „wintersport“ == Vorbelegung des Standard-Feldsatzes (Allgemein)', () => {
		const defs = buildCompareMetricDefs(KATALOG_ANTWORT);
		const std = vergleichVorbelegung(compareFeldsatzStandard() as never, defs);
		assert.ok(std && std.corridors.length > 0, 'Messaufbau: Allgemein belegt nichts vor');
		const winter = vergleichVorbelegung({ ...compareFeldsatzStandard(), vorlageId: 'wintersport' } as never, defs);
		assert.deepEqual(winter, std);
	});
});

// ── AC-1/AC-2: keine Profil-Kacheln, kein Profil-Knopf (Desktop + Mobil, DE + EN) ─────────
describe('AC-1/AC-2: gerenderter Anlege-Editor ohne Profil-Auswahl', async () => {
	const P = await import('../../compare/__tests__/f10Pruefstand.ts');
	const faelle = [
		{ tab: 'vergleich', mobil: false },
		{ tab: 'vergleich', mobil: false, name: 'Skitouren Tirol' },
		{ tab: 'vergleich', mobil: true },
		{ tab: 'vergleich', mobil: true, name: 'Skitouren Tirol' }
	];
	for (const lang of ['de', 'en'] as const) {
		test(`${lang}: weder Profil-Kacheln (Desktop) noch Profil-Knopf (Mobil) noch Hinweistext`, () => {
			P.locale.set(lang);
			for (const f of faelle) {
				const html = P.anlegenRendern(f);
				assert.ok(html.includes('compare-editor'), 'Messaufbau: Editor nicht gerendert');
				assert.ok(!/compare-editor-profile/.test(html), `${lang} ${f.mobil ? 'mobil' : 'desktop'}: Profil-Auswahl noch im Editor`);
				for (const text of ['Aktivitätsprofil', 'Activity profile', 'Bestimmt, welche Wetter-Metriken', 'Determines which weather metrics', 'Sommer-Trekking', 'Summer trekking']) {
					assert.ok(!html.includes(text), `${lang} ${f.mobil ? 'mobil' : 'desktop'}: „${text}“ steht noch im Anlege-Editor`);
				}
			}
		});
	}
});

// ── AC-9: verwaister Katalogtext entfernt, Orts-Profil-Text bleibt (LocationForm, AC-6) ──
describe('AC-9: Kataloge DE/EN', () => {
	for (const lang of ['de', 'en']) {
		test(`${lang}: vergleich.neu.profil_hinweis entfernt; vergleich.neu.aktivitaetsprofil bleibt (Ort bearbeiten nutzt ihn)`, () => {
			const k = JSON.parse(readFileSync(join(MESSAGES, lang, 'vergleich.json'), 'utf-8')) as Record<string, string>;
			assert.ok(!('vergleich.neu.profil_hinweis' in k), `${lang}: vergleich.neu.profil_hinweis ist verwaist und muss weg`);
			assert.ok('vergleich.neu.aktivitaetsprofil' in k, `${lang}: Ort-bearbeiten-Beschriftung darf nicht entfernt werden (AC-6)`);
		});
	}
});
