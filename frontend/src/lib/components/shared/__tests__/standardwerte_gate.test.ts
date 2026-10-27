// TDD RED — Onboarding S3 (Issue #2521): Gate von „Mit Standardwerten speichern".
// Spec: docs/specs/modules/onboarding_standardwerte_hilfe.md — AC-1, AC-2, AC-3,
// AC-4, AC-5, AC-10.
//
// Zwei Messebenen, weil die Mutationen der Spec an ZWEI Orten wirken:
//   (1) die kind-neutrale Gate-Funktion `canFinishMitStandardwerten(
//       {pflichtErfuellt, defaultsBereit, bestandFrei})` in anlegeLockEngine.ts
//       — Wahrheitstabelle (AC-5-Mutation „bestandFrei ignoriert", AC-3/AC-4
//       „defaultsBereit ignoriert" auf Kern-Ebene);
//   (2) die WIRKSTELLE in den Editoren: welche Werte reicht der Editor an den
//       Knopf? `etDone`, Name, Startdatum, `catalogLoaded` (Trip) bzw. Name und
//       `>= 2` Orte, Vergleichs-Katalog (Compare) werden im Editor berechnet —
//       eine Wahrheitstabelle auf den Kern faengt deren Mutation nie. Gemessen
//       wird das Attribut `enabled` der ECHTEN `<StandardwerteSpeichernKnopf>`-
//       Einbettungen, ausgewertet gegen das ECHTE Instanz-Skript
//       (standardwerteEditorPruefstand.ts / svelteInstanzPruefstand.ts).
//
// Vertraege, die dieser Test festlegt (Spec nennt sie, oder sie folgen daraus):
//   - Export `canFinishMitStandardwerten` in shared/anlegeLockEngine.ts
//   - Trip-Editor fuehrt den Katalog-Zustand unter dem Spec-Namen `catalogLoaded`
//   - Compare-Editor laedt den Vergleichs-Katalog ueber GET /api/compare/metrics;
//     ein Fehlschlag laesst den Knopf gesperrt (Netzgrenze `fetch` ersetzt)
//   - beide Editoren betten `StandardwerteSpeichernKnopf` mit Prop `enabled` ein
//
// AC-10 (Autosave) ist BEWUSST GRUEN: es sichert Bestandsverhalten
// (`beforeNavigate` bleibt an `ready`), damit die Mutation „Autosave an das neue
// Gate gebunden" rot wird.
//
// Kein statischer Import neuer Exporte (sonst bricht die ganze Datei beim Laden).
//
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types \
//     --test src/lib/components/shared/__tests__/standardwerte_gate.test.ts

import { test, describe, before, after } from 'node:test';
import assert from 'node:assert/strict';
import { execFileSync } from 'node:child_process';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import * as engine from '../anlegeLockEngine.ts';
import { neuerWiz } from './infoboxSsr.ts';
import {
	TRIP_EDITOR,
	COMPARE_EDITOR,
	editorUmgebung,
	mountenUndWarten,
	derivedNeu,
	knopfEinbettungen,
	knopfAttribut,
	type EditorUmgebung
} from './standardwerteEditorPruefstand.ts';

type Gate = (p: { pflichtErfuellt: boolean; defaultsBereit: boolean; bestandFrei: boolean }) => boolean;
const gate = (engine as Record<string, unknown>).canFinishMitStandardwerten as Gate | undefined;

function gateDa(): Gate {
	assert.equal(
		typeof gate,
		'function',
		'anlegeLockEngine.ts exportiert keine Funktion `canFinishMitStandardwerten` (Spec: Gate)'
	);
	return gate!;
}

// ── (1) Kern: Wahrheitstabelle ───────────────────────────────────────────────
describe('Kern: canFinishMitStandardwerten — Wahrheitstabelle (AC-1..AC-5)', () => {
	test('alle 8 Kombinationen: wahr GENAU bei Pflicht erfuellt, Standardwerte bereit, Bestandsknopf gesperrt', () => {
		const g = gateDa();
		for (let m = 0; m < 8; m++) {
			const p = { pflichtErfuellt: !!(m & 1), defaultsBereit: !!(m & 2), bestandFrei: !!(m & 4) };
			assert.equal(g(p), p.pflichtErfuellt && p.defaultsBereit && !p.bestandFrei, JSON.stringify(p));
		}
	});
	test('AC-3/AC-4: Standardwerte nicht bereit => gesperrt, auch bei erfuellten Pflichtangaben', () => {
		assert.equal(gateDa()({ pflichtErfuellt: true, defaultsBereit: false, bestandFrei: false }), false);
	});
	test('AC-5: Bestandsknopf frei => Standardwerte-Knopf nicht aktiv (nie beide gleichzeitig)', () => {
		assert.equal(gateDa()({ pflichtErfuellt: true, defaultsBereit: true, bestandFrei: true }), false);
	});
	// #1743 AC-19: der Schritt „Versand" entfaellt — Fertig/Anlegen wird mit dem Besuch von
	// „Alarme" (letzter Schritt) frei, nicht frueher.
	test('Bestandsgate canFinish: nur der Alarme-Besuch zaehlt (#1743, vormals Versand)', () => {
		assert.equal(engine.canFinish(new Set(['wetter-metriken', 'wertebereiche'])), false);
		assert.equal(engine.canFinish(new Set(['alarme'])), true);
	});
});

// ── (2a) Wirkstelle Trip ─────────────────────────────────────────────────────
const GPX = { file: 'a.gpx', km: 10, asc: 500 };
const etappen = (mitGpx: boolean[]) =>
	mitGpx.map((g, i) => ({ id: i + 1, name: `E${i + 1}`, gpx: g ? GPX : null, waypoints: [] }));

interface TripSaat {
	name?: string;
	startDate?: string;
	gpx?: boolean[];
	catalogLoaded?: boolean;
	alleBesucht?: boolean;
}

async function tripUmgebung(s: TripSaat): Promise<EditorUmgebung> {
	const besucht = !!s.alleBesucht;
	return editorUmgebung(TRIP_EDITOR, {
		stateOverride: {},
		name: s.name ?? 'Trip X',
		startDate: s.startDate ?? '2026-07-01',
		stages: etappen(s.gpx ?? [true, true]),
		catalogLoaded: s.catalogLoaded ?? true,
		wtVisited: besucht,
		wbVisited: besucht,
		alVisited: besucht,
		vsVisited: besucht,
		api: { post: async () => ({ id: 'neu-1' }), get: async () => ({}) }
	});
}

function tripKnopfAktiv(e: EditorUmgebung): boolean[] {
	const knoepfe = knopfEinbettungen(e.ast);
	assert.ok(
		knoepfe.length >= 2,
		`TripNewEditor bettet <StandardwerteSpeichernKnopf> nicht Desktop UND mobil ein (gefunden: ${knoepfe.length})`
	);
	return knoepfe.map((k) => Boolean(knopfAttribut(k, e, 'enabled')));
}

describe('Wirkstelle Trip (/trips/new): enabled des Standardwerte-Knopfs', () => {
	test('AC-1: Name + Startdatum + alle Etappen mit GPX + Katalog geladen, Versand nie besucht => aktiv', async () => {
		const e = await tripUmgebung({});
		assert.equal(e.u.ready, false, 'Messaufbau: Bestandsknopf muss gesperrt sein (Versand nie besucht)');
		assert.deepEqual(tripKnopfAktiv(e), tripKnopfAktiv(e).map(() => true));
	});
	test('AC-1: ohne Name => deaktiviert', async () => {
		assert.ok(tripKnopfAktiv(await tripUmgebung({ name: '' })).every((a) => a === false));
	});
	test('AC-1: ohne Startdatum => deaktiviert', async () => {
		assert.ok(tripKnopfAktiv(await tripUmgebung({ startDate: '' })).every((a) => a === false));
	});
	test('AC-1: eine Etappe ohne GPX => deaktiviert (etDone ist Pflicht)', async () => {
		assert.ok(tripKnopfAktiv(await tripUmgebung({ gpx: [true, false] })).every((a) => a === false));
	});
	test('AC-3: Metrik-Katalog nicht geladen => deaktiviert, obwohl alle Pflichtangaben erfuellt', async () => {
		assert.ok(tripKnopfAktiv(await tripUmgebung({ catalogLoaded: false })).every((a) => a === false));
	});
	test('AC-3: ein Klick vor dem Katalog speichert nichts', async () => {
		const posts: string[] = [];
		const e = await editorUmgebung(TRIP_EDITOR, {
			stateOverride: {},
			name: 'Trip X',
			startDate: '2026-07-01',
			stages: etappen([true, true]),
			catalogLoaded: false,
			api: { post: async (url: string) => (posts.push(url), { id: 'neu-1' }), get: async () => ({}) }
		});
		const knoepfe = knopfEinbettungen(e.ast);
		assert.ok(knoepfe.length >= 1, 'TripNewEditor bettet <StandardwerteSpeichernKnopf> nicht ein');
		const klick = knopfAttribut(knoepfe[0], e, 'onclick') as () => unknown;
		await klick();
		assert.deepEqual(posts, [], 'Klick vor geladenem Katalog hat gespeichert');
	});
	test('AC-5: alle Reiter besucht (Bestandsknopf frei) => Standardwerte-Knopf nicht aktiv', async () => {
		const e = await tripUmgebung({ alleBesucht: true });
		assert.equal(e.u.ready, true, 'Messaufbau: Bestandsknopf muss frei sein');
		assert.ok(tripKnopfAktiv(e).every((a) => a === false));
	});
});

// ── (2b) Wirkstelle Ortsvergleich ────────────────────────────────────────────
// Netzgrenze: `globalThis.fetch`. GET /api/compare/metrics liefert den LIVE-
// Katalog aus dem Python-Kern (Muster compareMetricCatalogParity.test.ts) bzw.
// im Fehlerfall HTTP 500. Alles andere antwortet leer.
const REPO_ROOT = resolve(dirname(fileURLToPath(import.meta.url)), ...Array(6).fill('..'));
const PY =
	'import sys, json\n' +
	"sys.path.insert(0, 'src')\n" +
	'from output.renderers.compare_metric_catalog import get_compare_metric_catalog\n' +
	"print(json.dumps({'metrics': get_compare_metric_catalog()}))\n";
const KATALOG = JSON.parse(
	execFileSync('uv', ['run', 'python3', '-c', PY], { cwd: REPO_ROOT, encoding: 'utf-8' }).trim()
);

let katalogFehler = false;
let originalFetch: typeof globalThis.fetch;
before(() => {
	originalFetch = globalThis.fetch;
	globalThis.fetch = (async (input: unknown) => {
		const url = String(input);
		if (url.includes('/api/compare/metrics')) {
			return katalogFehler
				? new Response(JSON.stringify({ error: 'kaputt' }), { status: 500 })
				: new Response(JSON.stringify(KATALOG), { status: 200, headers: { 'content-type': 'application/json' } });
		}
		return new Response('[]', { status: 200, headers: { 'content-type': 'application/json' } });
	}) as typeof globalThis.fetch;
});
after(() => {
	globalThis.fetch = originalFetch;
});

async function compareUmgebung(s: { name?: string; orte?: number; versand?: boolean }): Promise<EditorUmgebung> {
	const wiz = neuerWiz({
		name: s.name ?? 'Vergleich X',
		pickedIds: Array.from({ length: s.orte ?? 2 }, (_, i) => `loc${i}`)
	});
	const alle = !!s.versand;
	const e = await editorUmgebung(COMPARE_EDITOR, {
		getContext: () => wiz,
		stateOverride: {
			activeTab: 'vergleich',
			isMobileViewport: false,
			metrikenVisited: alle,
			idealsVisited: alle,
			alarmeVisited: alle,
			versandVisited: alle
		},
		window: { matchMedia: () => ({ matches: false, addEventListener() {}, removeEventListener() {} }) }
	});
	await mountenUndWarten(e);
	derivedNeu(e);
	return e;
}

function compareKnopfAktiv(e: EditorUmgebung): boolean[] {
	const knoepfe = knopfEinbettungen(e.ast);
	assert.ok(
		knoepfe.length >= 2,
		`CompareNewEditor bettet <StandardwerteSpeichernKnopf> nicht Kopfzeile UND mobil ein (gefunden: ${knoepfe.length})`
	);
	return knoepfe.map((k) => Boolean(knopfAttribut(k, e, 'enabled')));
}

// Reihenfolge ist Absicht: der Katalog-Lader cacht eine ERFOLGREICHE Antwort
// modulweit; ein Fehler invalidiert den Cache. Deshalb zuerst der Fehlerfall.
describe('Wirkstelle Ortsvergleich (/compare/new): Katalog-Fehler (AC-4)', () => {
	test('AC-4: Abruf des Vergleichs-Katalogs scheitert, Name + 2 Orte => Knopf gesperrt', async () => {
		katalogFehler = true;
		try {
			const e = await compareUmgebung({});
			assert.ok(compareKnopfAktiv(e).every((a) => a === false), 'Katalog-Fehler zaehlt als bereit');
		} finally {
			katalogFehler = false;
		}
	});
	test('AC-4: Bestandsweg bleibt nutzbar — nach Besuch aller Reiter ist „Aktivieren" trotz Katalog-Fehler frei', async () => {
		katalogFehler = true;
		try {
			const e = await compareUmgebung({ versand: true });
			assert.equal(e.u.canActivateNow, true);
		} finally {
			katalogFehler = false;
		}
	});
});

describe('Wirkstelle Ortsvergleich (/compare/new): Pflichtangaben (AC-2, AC-5)', () => {
	test('AC-2: Name + 2 Orte + Katalog geladen => aktiv', async () => {
		const e = await compareUmgebung({});
		assert.equal(e.u.canActivateNow, false, 'Messaufbau: Bestandsknopf muss gesperrt sein');
		assert.ok(compareKnopfAktiv(e).every((a) => a === true));
	});
	test('AC-2: nur 1 Ort => deaktiviert', async () => {
		assert.ok(compareKnopfAktiv(await compareUmgebung({ orte: 1 })).every((a) => a === false));
	});
	test('AC-2: ohne Namen => deaktiviert', async () => {
		assert.ok(compareKnopfAktiv(await compareUmgebung({ name: '' })).every((a) => a === false));
	});
	test('AC-5: alle Reiter besucht (Aktivieren frei) => Standardwerte-Knopf nicht aktiv', async () => {
		const e = await compareUmgebung({ versand: true });
		assert.equal(e.u.canActivateNow, true, 'Messaufbau: Bestandsknopf muss frei sein');
		assert.ok(compareKnopfAktiv(e).every((a) => a === false));
	});
});

// ── AC-10: Autosave bleibt an `ready` (Bestandsverhalten, bewusst gruen) ──────
async function navigiereWeg(s: TripSaat): Promise<{ cancelled: number; saves: number }> {
	const e = await tripUmgebung(s);
	assert.equal(e.navigationsWaechter.length, 1, 'Messaufbau: genau ein beforeNavigate im Trip-Editor erwartet');
	let saves = 0;
	e.u.buildAndSave = async () => {
		saves++;
		return null;
	};
	let cancelled = 0;
	e.navigationsWaechter[0]({ cancel: () => cancelled++, to: { url: { href: '/trips' } } });
	await new Promise((r) => setTimeout(r, 0));
	return { cancelled, saves };
}

describe('AC-10: beforeNavigate-Autosave haengt an ready, nicht am Standardwerte-Gate', () => {
	test('Pflicht erfuellt + Katalog geladen, aber Versand nie besucht: Wegnavigieren loest KEIN Speichern aus', async () => {
		const r = await navigiereWeg({});
		assert.equal(r.cancelled, 0, 'Navigation wurde fuer einen Autosave angehalten');
		assert.equal(r.saves, 0, 'Autosave ausgeloest, obwohl der Bestandsknopf gesperrt ist');
	});
	test('alle Reiter besucht (ready): Wegnavigieren speichert wie bisher automatisch', async () => {
		const r = await navigiereWeg({ alleBesucht: true });
		assert.equal(r.cancelled, 1);
		assert.equal(r.saves, 1);
	});
});
