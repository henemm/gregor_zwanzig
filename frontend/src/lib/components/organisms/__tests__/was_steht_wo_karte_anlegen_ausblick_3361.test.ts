// TDD RED — Issue #3361 (Spec docs/specs/modules/fix_3361_ausblick_anlegen.md, AC-2 bis AC-5; AC-1 ist E137 in
// trip-new/__tests__/anlegen_ausblick_vorbelegung_folgt_zustellung.test.ts).
// Anlegen mit der Karte „Was steht wo“: der Anlege-Stand trägt den 3-Tages-Ausblick (`outlook_reports`) nur, wenn
// der Nutzer ihn selbst gewählt hat; ohne Wahl löst der Python-Kern die Vorbelegung beim Lesen nach der dann
// gültigen Zustellung auf. Bearbeiten im Hub (`createMode=false`) bleibt unverändert.
//
// Kette ohne Nachbau, je für zwei Nutzer mit eigenem Bestand und für Trip ('route') und Orte ('vergleich'):
// echte Vorschau des Python-Kerns (build_placements_preview) -> ECHTES Instanz-Skript der Karte
// (`tripMehrreiterPruefstand`) -> echter Anlege-Rumpf (T.buildCreateTripPayload bzw. baueVergleichAnlegeRumpf) ->
// Ausblick, den der Python-Kern aus diesem Rumpf auflöst.
// Hinweis Prüfstand: `$derived` wird nur einmal beim Aufbau ausgewertet (vor dem Laden). Nach dem Laden werden die
// Ableitungen deshalb aus dem Quelltext der Karte neu ausgewertet (`nachrechnen`), keine Nachbildung.
//
//   cd frontend && npm test -- src/lib/components/organisms/__tests__/was_steht_wo_karte_anlegen_ausblick_3361.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { execFileSync } from 'node:child_process';

import * as T from '../../trip-new/tripNewLogic.ts';
import { baueVergleichAnlegeRumpf, compareFeldsatzStandard, mitZustellungVergleich } from '../../compare/compareEditorSave.ts';
import { standAusPreset, standAusTrip } from '../../shared/zustellung-tab/zustellungModell.ts';
import { REPO } from '../../shared/wetter-tab/__tests__/wetterTabDaten.ts';
import { werte, ohneTypen, type Knoten } from '../../shared/__tests__/svelteInstanzPruefstand.ts';
import * as P from '../../trip-detail/__tests__/tripMehrreiterPruefstand.ts';

type J = any; // eslint-disable-line @typescript-eslint/no-explicit-any
type Kind = 'route' | 'vergleich';
const KINDS = ['route', 'vergleich'] as const;
const NUTZER = ['n3361-a', 'n3361-b'] as const;
const METRIKEN = ['temperature', 'wind', 'gust'];

const PY = `
import sys, json, os, tempfile
from pathlib import Path
sys.path.insert(0, 'src'); sys.path.insert(0, '.')
from services.placements_view_service import build_placements_preview
faelle = json.loads(sys.stdin.read())
aus = []
with tempfile.TemporaryDirectory() as wurzel:
    os.environ["GZ_DATA_DIR"] = wurzel
    for nutzer, kind, entwurf in faelle:
        Path(wurzel, "users", nutzer).mkdir(parents=True, exist_ok=True)
        a = build_placements_preview(kind, entwurf, nutzer)
        aus.append({"antwort": a, "ausblick": a["outlook_reports"]})
print(json.dumps(aus))
`;
/** Vorschau des Python-Kerns je [Nutzer, Art, Anlege-Rumpf]. */
function vorschau(faelle: [string, Kind, J][]): { antwort: J; ausblick: string[] }[] {
	const stdout = execFileSync('uv', ['run', 'python3', '-c', PY], {
		cwd: REPO,
		input: JSON.stringify(faelle),
		encoding: 'utf-8',
		maxBuffer: 8 * 1024 * 1024,
		stdio: ['pipe', 'pipe', 'ignore']
	});
	return JSON.parse(stdout.trim().split('\n').pop()!);
}

/** Der eine Anlege-Rumpf wie im Editor: Zustellung „nur Morgen“ (`nurMorgen`) oder beide Briefings, Karte `karte`. */
const RUMPF: Record<Kind, (nurMorgen: boolean, karte?: J) => J> = {
	route: (nurMorgen, karte) => {
		const stand = { ...standAusTrip({ id: '__new__', name: 'n', stages: [] } as J), ...(nurMorgen ? { abendAn: false } : {}) };
		const r = T.mitZustellung(undefined, T.initialCreateTripAlarmState(), stand);
		return T.buildCreateTripPayload({
			name: 'Neu-3361',
			startDate: '2027-07-01',
			stages: [{ id: 1, name: 'A', waypoints: [] }],
			weatherMetrics: METRIKEN.map((metric_id) => ({ metric_id, enabled: true })),
			channels: { email: true, telegram: false, sms: false },
			alarm: r.alarm,
			reportConfig: T.ergaenzeStandardwerteReportConfig(r.reportConfig),
			karte
		} as J);
	},
	vergleich: (nurMorgen, karte) => {
		const wiz: J = { ...compareFeldsatzStandard(), name: 'Neu-3361', pickedIds: ['loc-a', 'loc-b'] };
		mitZustellungVergleich(wiz, { ...standAusPreset({ id: '', name: 'n', location_ids: wiz.pickedIds } as J), morgenAn: true, abendAn: !nurMorgen });
		return baueVergleichAnlegeRumpf(wiz, { ampel: { template: 'allgemein' }, auswahl: METRIKEN.map((metric_id) => ({ metric_id, aggregation: 'max' })), karte });
	}
};

/** `$derived`-Ableitung `name` der Karte aus ihrem Quelltext neu auswerten (der Prüfstand tut es nur beim Aufbau). */
function nachrechnen(k: P.Instanz, name: string): unknown {
	for (const stmt of (k.ast.instance?.content?.body as Knoten[]) ?? []) {
		if (stmt.type !== 'VariableDeclaration') continue;
		for (const d of stmt.declarations as Knoten[]) {
			if (d.id?.name !== name || d.init?.type !== 'CallExpression' || d.init.callee?.name !== '$derived') continue;
			const w = werte(ohneTypen(k.quelle, d.init.arguments[0]), k.u);
			k.u[name] = w;
			return w;
		}
	}
	throw new Error(`Messaufbau: keine Ableitung ${name} in der Karte`);
}
/** Alle Ableitungen, die die Ausblick-Schalter und ihre Geste lesen, im Stand nach dem Laden bzw. der letzten Geste. */
function ableitungen(k: P.Instanz): void {
	nachrechnen(k, 'aktFelder');
	nachrechnen(k, 'ausblickBerichte');
	nachrechnen(k, 'lage');
}

/** Die echte Karte im Anlegen, erste Vorschau-Antwort geladen. */
async function anlegeKarte(kind: Kind, antwort: J): Promise<{ k: P.Instanz; staende: J[] }> {
	const staende: J[] = [];
	const k = await P.bauen(P.DATEI.karte, {
		...P.LAUFZEIT,
		api: { ...P.LAUFZEIT.api, post: async () => JSON.parse(JSON.stringify(antwort)) },
		context: kind,
		id: '',
		createMode: true,
		entwurf: () => ({}),
		onAnlegeStand: (s: J) => staende.push(JSON.parse(JSON.stringify(s)))
	});
	await k.u.laden();
	assert.equal(k.u.phase, 'bereit', 'Messaufbau: Karte nicht geladen');
	ableitungen(k);
	return { k, staende };
}

/** Anlegen, ein Haken (Wind, Telegram) abgewählt, Ausblick nicht angefasst: gemeldeter Stand. */
async function nurHaken(kind: Kind, antwort: J): Promise<J> {
	const { k, staende } = await anlegeKarte(kind, antwort);
	k.u.haken({ metrik: 'wind', stelle: 'telegram', an: false });
	assert.equal(staende.length, 1, 'Messaufbau: ein gemeldeter Stand');
	assert.equal(staende[0].placements.rows.find((r: J) => r.metric_id === 'wind').places.telegram, false);
	return staende[0];
}

const beideBriefings = (kind: Kind) => vorschau(NUTZER.map((n) => [n, kind, RUMPF[kind](false)]));

for (const kind of KINDS) {
	describe(`#3361 Karte im Anlegen: Ausblick nur bei eigener Wahl (${kind})`, () => {
		test(`AC-2: Haken bedient, Ausblick nicht angefasst, beide Briefings: Stand ohne outlook_reports, Ausblick abends (${kind})`, async () => {
			const erste = beideBriefings(kind);
			for (const v of erste) assert.deepEqual(v.ausblick, ['evening'], 'Messaufbau: Vorbelegung bei beiden Briefings ist abends');
			const staende = await Promise.all(erste.map((v) => nurHaken(kind, v.antwort)));
			for (const s of staende) {
				assert.equal(
					'outlook_reports' in s.placements,
					false,
					`gemeldeter Stand trägt den nie gewählten Ausblick fest: ${JSON.stringify(s.placements.outlook_reports)}`
				);
			}
			const r = vorschau(NUTZER.map((n, i) => [n, kind, RUMPF[kind](false, staende[i])]));
			assert.deepEqual(r.map((x) => x.ausblick), [['evening'], ['evening']], 'bisherige Vorbelegung bei beiden Briefings');
		});

		test(`AC-3: Ausblick selbst gewählt, danach nur Morgen: genau die Wahl je Nutzer bleibt (${kind})`, async () => {
			const erste = beideBriefings(kind);
			const staende: J[] = [];
			// Nutzer A: Morgen dazu (Vorbelegung abends) -> morning+evening; Nutzer B: Abend ausdrücklich bestätigt -> evening.
			const gesten: [('morning' | 'evening'), boolean][] = [['morning', true], ['evening', true]];
			for (const [i, v] of erste.entries()) {
				const { k, staende: s } = await anlegeKarte(kind, v.antwort);
				k.u.ausblick(gesten[i][0], gesten[i][1]);
				assert.equal(s.length, 1, 'Messaufbau: Ausblick-Geste meldet einen Stand');
				staende.push(s[0]);
			}
			assert.deepEqual(staende.map((s) => s.placements.outlook_reports), [['morning', 'evening'], ['evening']], 'gemeldeter Stand trägt die Wahl');
			const r = vorschau(NUTZER.map((n, i) => [n, kind, RUMPF[kind](true, staende[i])]));
			assert.deepEqual(r.map((x) => x.ausblick), [['morning', 'evening'], ['evening']], 'Wahl gilt unabhängig von der Zustellung');
		});

		test(`AC-5: Anlegen ohne Ausblick-Wahl: Schalter zeigen die Vorbelegung der Vorschau, Stand ohne outlook_reports (${kind})`, async () => {
			for (const v of beideBriefings(kind)) {
				const { k, staende } = await anlegeKarte(kind, v.antwort);
				k.u.haken({ metrik: 'wind', stelle: 'telegram', an: false });
				ableitungen(k);
				assert.deepEqual(k.u.ausblickBerichte, ['evening'], 'Ausblick-Schalter: Abend an, Morgen aus');
				assert.equal((k.u.lage as J).ausblickAn, true);
				assert.equal('outlook_reports' in staende[0].placements, false, 'nichts davon im gemeldeten Stand');
			}
		});

		test(`AC-2/AC-5: Neuaufbau über start (Reiterwechsel), weiterer Haken: Stand weiter ohne outlook_reports, nur Morgen -> morning (${kind})`, async () => {
			const erste = beideBriefings(kind);
			const staende: J[] = [];
			for (const v of erste) {
				const s1 = await nurHaken(kind, v.antwort);
				assert.equal('outlook_reports' in s1.placements, false, 'Messaufbau: S1 ohne Ausblick');
				const gemeldet: J[] = [];
				const k2 = await P.bauen(P.DATEI.karte, {
					...P.LAUFZEIT,
					api: { ...P.LAUFZEIT.api, post: async () => JSON.parse(JSON.stringify(v.antwort)) },
					context: kind,
					id: '',
					createMode: true,
					entwurf: () => ({}),
					start: JSON.parse(JSON.stringify(s1)),
					onAnlegeStand: (s: J) => gemeldet.push(JSON.parse(JSON.stringify(s)))
				});
				await k2.u.laden();
				assert.equal(k2.u.phase, 'bereit', 'Messaufbau: Karte 2 nicht geladen');
				ableitungen(k2);
				k2.u.haken({ metrik: 'gust', stelle: 'telegram', an: false });
				ableitungen(k2);
				assert.equal(gemeldet.length, 1, 'Messaufbau: ein gemeldeter Stand nach Neuaufbau');
				const s2 = gemeldet[0];
				assert.equal(s2.placements.rows.find((r: J) => r.metric_id === 'wind').places.telegram, false, 'Messaufbau: S1-Haken bleibt');
				assert.equal(
					'outlook_reports' in s2.placements,
					false,
					`Stand nach Neuaufbau trägt den nie gewählten Ausblick fest: ${JSON.stringify(s2.placements.outlook_reports)}`
				);
				assert.deepEqual(k2.u.ausblickBerichte, ['evening'], 'Ausblick-Schalter nach Neuaufbau: Vorbelegung der Vorschau');
				staende.push(s2);
			}
			const r = vorschau(NUTZER.map((n, i) => [n, kind, RUMPF[kind](true, staende[i])]));
			assert.deepEqual(r.map((x) => x.ausblick), [['morning'], ['morning']], 'nur Morgen nach Neuaufbau: Ausblick morgens');
		});

		test(`AC-4: Hub (createMode=false): Karte schreibt die Tabelle samt Ausblick der Antwort unverändert (${kind})`, async () => {
			for (const [i, v] of beideBriefings(kind).entries()) {
				const id = `abo-3361-${i}`;
				const lesen: string[] = [];
				const schreiben: { pfad: string; rumpf: J }[] = [];
				const anlegeStaende: J[] = [];
				const antwort = { ...v.antwort, stored: true };
				assert.deepEqual(antwort.placements.outlook_reports, ['evening'], 'Messaufbau: Antwort trägt den Ausblick');
				const k = await P.bauen(P.DATEI.karte, {
					...P.LAUFZEIT,
					api: {
						...P.LAUFZEIT.api,
						get: async (pfad: string) => (lesen.push(pfad), JSON.parse(JSON.stringify(antwort))),
						put: async (pfad: string, rumpf: J) => (schreiben.push({ pfad, rumpf: JSON.parse(JSON.stringify(rumpf)) }), {}),
						post: async () => assert.fail('Hub lädt nie über die Vorschau')
					},
					context: kind,
					id,
					createMode: false,
					onAnlegeStand: (s: J) => anlegeStaende.push(s)
				});
				await k.u.laden();
				assert.equal(k.u.phase, 'bereit', 'Messaufbau: Karte nicht geladen');
				assert.deepEqual(lesen, [`/api/briefings/${id}/placements?kind=${kind}`]);
				assert.deepEqual(k.u.lokal, antwort.placements, 'Hub: lokaler Stand = Antwort, Ausblick inklusive');
				ableitungen(k);
				k.u.haken({ metrik: 'wind', stelle: 'telegram', an: false });
				await new Promise((r) => setImmediate(r));
				assert.equal(schreiben.length, 1, 'Hub: ein Tabellen-PUT');
				assert.equal(schreiben[0].pfad, `/api/briefings/${id}/placements?kind=${kind}`);
				assert.deepEqual(schreiben[0].rumpf.outlook_reports, ['evening'], 'Hub-PUT trägt den Ausblick wie bisher');
				assert.deepEqual(anlegeStaende, [], 'Hub meldet keinen Anlege-Stand');
			}
		});
	});
}
