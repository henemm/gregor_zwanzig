// Issue #3020 R1 (E137; Spec docs/specs/modules/rework_3020_altbausteine_entfernen.md, AC-6) — Fehler #3361:
// Anlegen, Karte „Was steht wo“ bedient (ein Haken, den 3-Tages-Ausblick fasst niemand an), danach in Zustellung
// nur das Morgen-Briefing: der Ausblick steht in keinem Briefing. Soll (#3155 AC-7, #3122 AC-9): wer den Ausblick nicht
// selbst gewählt hat, bekommt ihn in dem Briefing, das es gibt. #3361 behebt ihn.
//
// Kette ohne Nachbau, für zwei Nutzer mit je eigenem Bestand: echte Vorschau des Python-Kerns
// (build_placements_preview) -> ECHTES Instanz-Skript der Karte (Haken) -> echter Anlege-Rumpf (Trip und Orte) ->
// Ausblick, den der Python-Kern aus diesem Rumpf auflöst.
//
//   cd frontend && npm test -- src/lib/components/trip-new/__tests__/anlegen_ausblick_vorbelegung_folgt_zustellung.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { execFileSync } from 'node:child_process';

import * as T from '../tripNewLogic.ts';
import { baueVergleichAnlegeRumpf, compareFeldsatzStandard, mitZustellungVergleich } from '../../compare/compareEditorSave.ts';
import { standAusPreset, standAusTrip } from '../../shared/zustellung-tab/zustellungModell.ts';
import { REPO } from '../../shared/wetter-tab/__tests__/wetterTabDaten.ts';
import * as P from '../../trip-detail/__tests__/tripMehrreiterPruefstand.ts';

type J = any; // eslint-disable-line @typescript-eslint/no-explicit-any
type Kind = 'route' | 'vergleich';
const KINDS = ['route', 'vergleich'] as const;
const NUTZER = ['e137-a', 'e137-b'] as const;
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

/** Der eine Anlege-Rumpf wie im Editor: Reiter Zustellung auf „nur Morgen“ (`nurMorgen`), Karte `karte`. */
const RUMPF: Record<Kind, (nurMorgen: boolean, karte?: J) => J> = {
	route: (nurMorgen, karte) => {
		const stand = { ...standAusTrip({ id: '__new__', name: 'n', stages: [] } as J), ...(nurMorgen ? { abendAn: false } : {}) };
		const r = T.mitZustellung(undefined, T.initialCreateTripAlarmState(), stand);
		return T.buildCreateTripPayload({
			name: 'Neu-E137',
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
		const wiz: J = { ...compareFeldsatzStandard(), name: 'Neu-E137', pickedIds: ['loc-a', 'loc-b'] };
		mitZustellungVergleich(wiz, { ...standAusPreset({ id: '', name: 'n', location_ids: wiz.pickedIds } as J), morgenAn: true, abendAn: !nurMorgen });
		return baueVergleichAnlegeRumpf(wiz, { ampel: { template: 'allgemein' }, auswahl: METRIKEN.map((metric_id) => ({ metric_id, aggregation: 'max' })), karte });
	}
};

/** Die echte Karte im Anlegen: erste Vorschau geladen, ein Haken (Wind, Telegram) abgewählt; gemeldeter Stand. */
async function karteMitEinemHaken(kind: Kind, antwort: J): Promise<J> {
	const staende: J[] = [];
	const k = await P.bauen(P.DATEI.karte, {
		...P.LAUFZEIT,
		api: { ...P.LAUFZEIT.api, post: async () => antwort },
		context: kind,
		id: '',
		createMode: true,
		entwurf: () => ({}),
		onAnlegeStand: (s: J) => staende.push(JSON.parse(JSON.stringify(s)))
	});
	await k.u.laden();
	assert.equal(k.u.phase, 'bereit', 'Messaufbau: Karte nicht geladen');
	// `$derived aktFelder`: der Prüfstand wertet ihn nur einmal aus, vor dem Laden.
	k.u.aktFelder = k.u.felderAusAntwort(k.u.antwort);
	k.u.haken({ metrik: 'wind', stelle: 'telegram', an: false });
	assert.equal(staende.length, 1, 'Messaufbau: ein gemeldeter Stand');
	assert.equal(staende[0].placements.rows.find((r: J) => r.metric_id === 'wind').places.telegram, false);
	return staende[0];
}

describe('E137: Ausblick folgt im Anlegen der Zustellung', () => {
	for (const kind of KINDS) {
		// Ohne Bedienung der Karte gilt die Regel (E138 bis E140); sie belegt zugleich, dass die Kette messen kann.
		test(`Messaufbau E137: Karte nicht bedient, nur Morgen: Ausblick steht im Morgen-Briefing (${kind})`, () => {
			for (const r of vorschau(NUTZER.map((n) => [n, kind, RUMPF[kind](true)]))) assert.deepEqual(r.ausblick, ['morning']);
		});

		test(`Anlegen, Karte bedient ohne Ausblick-Wahl, danach nur Morgen: Ausblick steht im Morgen-Briefing (${kind})`, async () => {
			const erste = vorschau(NUTZER.map((n) => [n, kind, RUMPF[kind](false)]));
			const staende = await Promise.all(erste.map((v) => karteMitEinemHaken(kind, v.antwort)));
			const r = vorschau(NUTZER.map((n, i) => [n, kind, RUMPF[kind](true, staende[i])]));
			assert.deepEqual(r.map((x) => x.ausblick), [['morning'], ['morning']]);
		});
	}
});
