// TDD RED — Issue #2276 Scheibe S6d (Epic #2345): die Wertebereiche-Flaeche des
// Ortsvergleichs (`CorridorEditor.svelte` + `CorridorEditorMobile.svelte`,
// `context="vergleich"`) arbeitet auf reinen WERTPROPS + Rueckrufen statt auf
// dem Wizard-Zustandsobjekt `ws` (`getContext('compare-wizard-state')`). Das
// Buendel baut eine einzige Funktion `compare/corridorPropsAus.ts`, die alle
// Vergleichs-Mounts identisch einspeisen.
//
// Spec: docs/specs/modules/rework_2276_s6d_wertebereiche.md
//   AC-1  beide Corridor-Bausteine sind im Vergleichs-Zweig wertprop-rein
//   AC-2  Wirkort-Guard: der Selbst-Speicherweg wirkt NUR an Flaeche B (Hub)
//   AC-3  Flaeche C (/compare/new) behaelt ihre Bedienelemente an beiden Mounts,
//         und `corridorPropsAus(wiz)` steht IM Markup-Ausdruck (Form-Auflage A1)
//   AC-8  der Proxy-Adapter `corridorZustandsBruecke` erhaelt den Speicherweg
//
// WAS HIER GEMESSEN WIRD — und was nicht:
//   Die Kernsuite ist SSR-only (`node --test` + `svelte/server`, kein DOM).
//   `$effect` und Ereignisse laufen dort nie von selbst. Diese Datei wertet
//   deshalb die ECHTE Herleitung der Instanz-Skripte gegen gesaete Props aus
//   (`svelteInstanzPruefstand.ts`) und ruft den ECHTEN Handler `maybeSchedule()`
//   auf. Gemessen wird, was der Code mit den Props TUT — nicht, ob ein
//   Bezeichner im Quelltext steht.
//   Der Wirkort „Browser" (Klick -> PUT -> Neuladen) ist damit NICHT abgedeckt;
//   dafuer sind AC-4 bis AC-7 zustaendig
//   (`frontend/e2e/compare-wertebereiche-wertprops.spec.ts`).
//
// 🔴 ABWEICHUNG vom Wortlaut der Spec bei AC-2 — bewusst, mit Begruendung:
//   Die Spec nennt als Messweg `effekteVon()` (Muster S6c, AC-4 von
//   `compare_alarme_wertprops.test.ts`). In `AlarmeTab.svelte` entsteht der
//   Selbst-Speicherweg tatsaechlich IN einem `$effect`. In den beiden
//   Corridor-Bausteinen ist das NICHT so: `vergleichSpeicherung` entsteht in
//   einer `untrack(...)`-Deklaration (`CorridorEditor.svelte:62`), und
//   `aenderungMelden()` wird aus der Funktion `maybeSchedule()` gerufen
//   (`:239`). KEIN `$effect` nennt `vergleichSpeicherung`. `effekteVon(…,
//   'vergleichSpeicherung')` lieferte hier eine LEERE Liste — der Aufrufer
//   fuehrte nichts aus und jede Zusicherung darunter waere vakuum-gruen.
//   Gemessen wird deshalb am tatsaechlichen Wirkort: der echte Handler
//   `maybeSchedule()` wird gerufen. Die Zusicherung von AC-2 bleibt woertlich
//   dieselbe (schweigt an Flaeche A/C, wirkt an Flaeche B) — nur der Griff,
//   mit dem sie angefasst wird, ist der, den dieser Baustein wirklich hat.
//   Der Test unten haelt die Abwesenheit eines solchen `$effect` als eigene
//   Zusicherung fest: taucht spaeter doch einer auf, faellt diese Abweichung
//   auf, statt still zu veralten.
//
// 🔴 VAKUUM-FALLEN, die hier bewusst entschaerft sind:
//   (a) Keiner der vier neuen Prop-Namen (`corridors`, `idealRanges`,
//       `activeMetricKeys`, `metricAlertLevels`) existiert heute als lokale
//       Deklaration in den beiden Dateien (gemessen 2026-09-22) — die Saat
//       kann also keine echte Deklaration verdecken (`umgebungFuer()`
//       ueberspringt jede Deklaration, deren Name schon in der Saat steht).
//   (b) `vergleichSpeicherung` wird NIE gesaet — die Umgebung leitet sie aus
//       dem ECHTEN Produktivcode her (Fixture-Falle #2387).
//   (c) `ws: undefined` IST gesaet, solange der Quelltext den Namen noch
//       nennt. Sonst scheiterte die Deklarationskette mit ReferenceError und
//       `maybeSchedule()` stuerzte ab — der RED-Befund waere ein Absturz
//       statt der Zusicherung. Nach der Umstellung ist der Saat-Eintrag
//       wirkungslos, weil der Name nicht mehr vorkommt; genau das haelt AC-1
//       fest.

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { dirname, join, relative, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { parse } from 'svelte/compiler';
import {
	attributNamen,
	findeKomponenten,
	umgebungFuer,
	werte,
	type Knoten
} from '../../__tests__/svelteInstanzPruefstand.ts';

const HIER = dirname(fileURLToPath(import.meta.url));
const CORRIDOR = join(HIER, '..');
const COMPONENTS = resolve(HIER, '..', '..', '..');
const DESKTOP = join(CORRIDOR, 'CorridorEditor.svelte');
const MOBIL = join(CORRIDOR, 'CorridorEditorMobile.svelte');
const HUB = join(COMPONENTS, 'compare', 'CompareTabs.svelte');
const ANLEGE = join(COMPONENTS, 'compare-new', 'CompareNewEditor.svelte');
// __tests__ -> corridor-editor -> shared -> components -> lib -> src -> frontend
const FRONTEND = resolve(HIER, '..', '..', '..', '..', '..', '..');

/** Die in AC-1 woertlich freigegebenen Wertprops. */
const WERTPROPS = ['corridors', 'idealRanges', 'activeMetricKeys', 'metricAlertLevels'] as const;

/** Die in AC-1 woertlich freigegebenen Rueckrufe. */
const RUECKRUFE = [
	'onCorridorsChange',
	'onIdealRangesChange',
	'onActiveMetricKeysChange',
	'onMetricAlertLevelsChange'
] as const;

/** Welcher Rueckruf welches Wertprop fortschreibt — im Produkt haelt der
 *  Elternteil den Zustand, hier die Messumgebung. Ohne dieses Zurueckschreiben
 *  saehe die Bruecke beim Melden noch den ALTEN Stand und das Diff-Gate
 *  schwiege: der Test waere gruen, obwohl nichts gespeichert wuerde. */
const RUECKRUF_ZU_PROP: Record<string, string> = {
	onCorridorsChange: 'corridors',
	onIdealRangesChange: 'idealRanges',
	onActiveMetricKeysChange: 'activeMetricKeys',
	onMetricAlertLevelsChange: 'metricAlertLevels'
};

const DATEIEN: [string, string][] = [
	['CorridorEditor.svelte (Desktop)', DESKTOP],
	['CorridorEditorMobile.svelte (Mobil)', MOBIL]
];

/** Eine gueltige Editor-Zeile (mindestens eine Grenze gesetzt) — sonst liefert
 *  `saveGateDecision()` `'dirty'` und `maybeSchedule()` kehrt sofort zurueck. */
function zeile(zusatz: Knoten = {}): Knoten {
	return {
		metric: 'snow_depth_cm',
		label: 'Schneehoehe',
		unit: 'cm',
		scale: [0, 300],
		step: 1,
		min: 30,
		max: 200,
		notify: false,
		mark: true,
		kind: 'range',
		...zusatz
	};
}

/** Saat fuer den ORGANISMUS im Vergleichs-Zweig. `vergleichSpeicherung` fehlt
 *  bewusst (siehe Kopf, Vakuum-Falle b). */
function saatVergleich(zusatz: Knoten = {}): Knoten {
	return {
		context: 'vergleich',
		// Alt-Bezeichner, solange er im Quelltext steht (Kopf, Vakuum-Falle c).
		ws: undefined,
		untrack: (fn: () => unknown) => fn(),
		// gesaet, weil `$lib/api` unter node nicht aufloest — ohne diese Bindung
		// scheiterte die `vergleichSpeicherung`-Deklaration still.
		api: { put: async () => ({}) },
		// die vier Wertprops dieser Scheibe
		corridors: [],
		idealRanges: {},
		activeMetricKeys: [],
		metricAlertLevels: {},
		// die vier Rueckrufe — vom Aufrufer ueberschrieben
		onCorridorsChange: () => {},
		onIdealRangesChange: () => {},
		onActiveMetricKeysChange: () => {},
		onMetricAlertLevelsChange: () => {},
		// unveraenderte Props
		trip: undefined,
		onTripUpdate: undefined,
		preset: null,
		saveController: null,
		enqueueHubWrite: <T>(fn: () => Promise<T>) => fn(),
		onCompareUpdate: () => {},
		// der Bedien-Stand, auf dem `maybeSchedule()` arbeitet
		rows: [zeile()],
		...zusatz
	};
}

/** Die WIRKSAM gebundenen Prop-Namen: das Destrukturierungsmuster von
 *  `$props()`, nicht der Kommentar der TS-Schnittstelle darueber. */
function gebundeneProps(ast: Knoten, quelle: string): string[] {
	const muster = ((ast.instance?.content?.body as Knoten[]) ?? [])
		.filter((s) => s.type === 'VariableDeclaration')
		.flatMap((s) => (s.declarations as Knoten[]) ?? [])
		.find(
			(d) =>
				d.id?.type === 'ObjectPattern' &&
				d.init &&
				quelle.slice(d.init.start, d.init.end).includes('$props()')
		);
	assert.ok(muster, 'Kein `let { … } = $props()` im Instanz-Skript gefunden.');
	return ((muster!.id.properties as Knoten[]) ?? [])
		.map((p) => (p.key?.name ?? p.argument?.name) as string)
		.filter(Boolean);
}

/** Alle Zeilennummern, an denen der Teilbaum den Bezeichner `name` nennt. */
function nennungen(knoten: unknown, quelle: string, name: string): string[] {
	const treffer: string[] = [];
	function lauf(n: unknown): void {
		if (n === null || typeof n !== 'object') return;
		if (Array.isArray(n)) {
			n.forEach(lauf);
			return;
		}
		const k = n as Knoten;
		if (k.type === 'Identifier' && k.name === name && typeof k.start === 'number') {
			treffer.push(`Zeile ${quelle.slice(0, k.start).split('\n').length}`);
		}
		for (const key of Object.keys(k)) {
			if (key !== 'parent' && key !== 'loc') lauf(k[key]);
		}
	}
	lauf(knoten);
	return treffer;
}

// ── AC-1 ────────────────────────────────────────────────────────────────────

describe('AC-1: beide Corridor-Bausteine leiten den Vergleichs-Zweig aus Wertprops her', () => {
	for (const [was, datei] of DATEIEN) {
		test(`${was}: die Prop-Schnittstelle bindet alle acht freigegebenen Namen`, async () => {
			const { ast, quelle } = await umgebungFuer(datei, saatVergleich());
			const namen = gebundeneProps(ast, quelle);
			for (const pflicht of [...WERTPROPS, ...RUECKRUFE]) {
				assert.ok(
					namen.includes(pflicht),
					`AC-1 FAIL (${was}): die Komponente bindet kein \`${pflicht}\`. ` +
						`Gebunden: ${[...namen].sort().join(', ')}`
				);
			}
			for (const unveraendert of [
				'context',
				'trip',
				'onTripUpdate',
				'saveController',
				'preset',
				'enqueueHubWrite',
				'onCompareUpdate'
			]) {
				assert.ok(
					namen.includes(unveraendert),
					`AC-1 FAIL (${was}): die unveraenderte Prop \`${unveraendert}\` ist ` +
						'verschwunden — diese Scheibe tauscht nur die Wizard-Quelle aus, sie ' +
						'nimmt der Flaeche A nichts weg (AC-10).'
				);
			}
		});

		test(`${was}: nirgends im Instanz-Skript oder Markup steht noch eine \`ws\`-Referenz`, async () => {
			const { ast, quelle } = await umgebungFuer(datei, saatVergleich());
			const treffer = [
				...nennungen(ast.instance?.content, quelle, 'ws'),
				...nennungen(ast.fragment, quelle, 'ws')
			];
			assert.deepStrictEqual(
				treffer,
				[],
				`AC-1 FAIL (${was}): \`ws\` wird noch ${treffer.length}x referenziert ` +
					`(${treffer.join(', ')}). „Wertprop wenn da, sonst \`ws\`" ist genau das ` +
					'Anti-Muster, das S6 beseitigen soll (Spec § Known Limitations): die ' +
					'Umstellung ist an allen Vergleichs-Mounts vollstaendig oder sie unterbleibt.'
			);
		});

		test(`${was}: kein \`getContext\`-Aufruf mehr`, async () => {
			const { ast, quelle } = await umgebungFuer(datei, saatVergleich());
			const treffer = nennungen(ast.instance?.content, quelle, 'getContext');
			assert.deepStrictEqual(
				treffer,
				[],
				`AC-1 FAIL (${was}): \`getContext\` wird noch ${treffer.length}x genannt ` +
					`(${treffer.join(', ')}). Der geteilte Baustein darf sich seine Daten nicht ` +
					'selbst aus der Compare-Klebeschicht ziehen — das ist der Kern von #2276.'
			);
		});

		test(`${was}: der Typ-Import von \`CompareWizardState\` ist verschwunden`, async () => {
			const { ast, quelle } = await umgebungFuer(datei, saatVergleich());
			const importe = ((ast.instance?.content?.body as Knoten[]) ?? [])
				.filter((s) => s.type === 'ImportDeclaration')
				.map((s) => quelle.slice(s.start, s.end));
			assert.deepStrictEqual(
				importe.filter((q) => q.includes('CompareWizardState')),
				[],
				`AC-1 FAIL (${was}): der Baustein importiert weiterhin den Wizard-Typ aus ` +
					'compare/ — die Klebeschicht bliebe damit Teil der Schnittstelle des ' +
					'geteilten Organismus.'
			);
		});
	}
});

// ── AC-2 Wirkort-Guard ──────────────────────────────────────────────────────

describe('AC-2 Wirkort-Guard: der Selbst-Speicherweg wirkt nur an Flaeche B', () => {
	/** Baut die Umgebung, verdrahtet die vier Rueckrufe mit Zaehler UND
	 *  Rueckschreiben, und liefert den echten Handler `maybeSchedule`. */
	async function aufbau(datei: string, zusatz: Knoten) {
		const gemeldet: string[] = [];
		const geplant: unknown[] = [];
		const putAufrufe: { url: string; body: Knoten }[] = [];
		let u!: Knoten;
		const melder =
			(name: string) =>
			(...a: unknown[]) => {
				gemeldet.push(name);
				u[RUECKRUF_ZU_PROP[name]] = a[0];
			};
		const saat = saatVergleich({
			onCorridorsChange: melder('onCorridorsChange'),
			onIdealRangesChange: melder('onIdealRangesChange'),
			onActiveMetricKeysChange: melder('onActiveMetricKeysChange'),
			onMetricAlertLevelsChange: melder('onMetricAlertLevelsChange'),
			api: {
				put: async (url: string, body: Knoten) => {
					putAufrufe.push({ url, body });
					return { id: 'p1', name: 'x', location_ids: [], display_config: {} };
				}
			},
			...zusatz
		});
		const umgebung = await umgebungFuer(datei, saat);
		u = umgebung.u;
		assert.ok(
			'vergleichSpeicherung' in u,
			'Messaufbau kaputt: `vergleichSpeicherung` liess sich aus dem Produktivcode nicht ' +
				'herleiten (`umgebungFuer` schluckt Deklarations-Fehler still). Ohne diese ' +
				'Herleitung misst der Guard unten nichts.'
		);
		const maybeSchedule = u.maybeSchedule as (() => void) | undefined;
		assert.strictEqual(
			typeof maybeSchedule,
			'function',
			'Messaufbau kaputt: `maybeSchedule` liess sich nicht herleiten — der echte ' +
				'Wirkort dieser Zusicherung ist damit unerreichbar.'
		);
		return { u, maybeSchedule: maybeSchedule!, gemeldet, geplant, putAufrufe };
	}

	/** Ein Speicher-Controller, der nur mitschreibt. */
	function controller(geplant: unknown[]): Knoten {
		return {
			schedule: (fn: unknown) => geplant.push(fn),
			setDirty: () => {},
			cancel: () => {},
			markPristine: () => {}
		};
	}

	const hubZusatz = (geplant: unknown[]): Knoten => ({
		preset: { id: 'p1', name: 'x', location_ids: [], display_config: {} },
		saveController: controller(geplant)
	});

	for (const [was, datei] of DATEIEN) {
		test(`${was} — Flaeche B (Hub): die Geste meldet ueber alle vier Rueckrufe und plant EINEN Speichervorgang`, async () => {
			const geplant: unknown[] = [];
			const aufb = await aufbau(datei, hubZusatz(geplant));
			aufb.maybeSchedule();

			assert.deepStrictEqual(
				[...new Set(aufb.gemeldet)].sort(),
				[...RUECKRUFE].sort(),
				`AC-2 FAIL (${was}, Flaeche B): die Geste hat nicht ueber alle vier Rueckrufe ` +
					`gemeldet (gemeldet: ${aufb.gemeldet.join(', ') || '—'}). Schreibt der ` +
					'Baustein noch direkt auf `ws`, verpufft die Aenderung hier vollstaendig: ' +
					'der Elternteil erfaehrt nichts und speichert nichts.'
			);
			assert.strictEqual(
				geplant.length,
				1,
				`AC-2 FAIL (${was}, Flaeche B): am positiven Ort wurde ${geplant.length} ` +
					'Speichervorgang geplant statt genau einem. Ohne diese Richtung misst der ' +
					'Guard nur „der Speicherweg laeuft nie" — vakuum-gruen.'
			);
			assert.ok(
				aufb.u.vergleichSpeicherung,
				`AC-2 FAIL (${was}, Flaeche B): mit \`preset\` + \`saveController\` muss der ` +
					'Produktivcode eine Vergleichs-Speicherung erzeugen.'
			);
		});

		test(`${was} — Flaeche A (Tour, context="route"): kein Vergleichs-Rueckruf, aber der Tour-Speicherweg laeuft`, async () => {
			const geplant: unknown[] = [];
			const aufb = await aufbau(datei, {
				context: 'route',
				trip: { id: 't-1', corridors: [], display_config: {} },
				saveController: controller(geplant)
			});
			aufb.maybeSchedule();

			assert.deepStrictEqual(
				aufb.gemeldet,
				[],
				`AC-2 FAIL (${was}, Flaeche A): der Tour-Zweig ruft Vergleichs-Rueckrufe ` +
					`(${aufb.gemeldet.join(', ')}). Faellt der Guard \`if (context === ` +
					"'vergleich')\` weg, laeuft die Tour in den Vergleichs-Speicherweg."
			);
			assert.strictEqual(
				aufb.u.vergleichSpeicherung,
				null,
				`AC-2 FAIL (${was}, Flaeche A): an der Tour darf es keine Vergleichs-Speicherung ` +
					'geben.'
			);
			assert.strictEqual(
				geplant.length,
				1,
				`AC-2 FAIL (${was}, Flaeche A): der Tour-Zweig hat NICHTS geplant — dann misst ` +
					'die Abwesenheits-Zusicherung darueber nichts (der Rumpf lief gar nicht).'
			);
		});

		test(`${was} — Flaeche C (Anlegen, ohne preset/saveController): Rueckrufe ja, Speicherweg nein`, async () => {
			const aufb = await aufbau(datei, { preset: null, saveController: null });
			aufb.maybeSchedule();

			assert.strictEqual(
				aufb.u.vergleichSpeicherung,
				null,
				`AC-2 FAIL (${was}, Flaeche C): die Anlege-Seite hat keine Basis und keinen ` +
					'Speicher-Controller — es darf dort keinen eigenen Speicherweg geben (sonst ' +
					'PUT auf einen Vergleich, den es noch nicht gibt).'
			);
			assert.deepStrictEqual(
				[...new Set(aufb.gemeldet)].sort(),
				[...RUECKRUFE].sort(),
				`AC-2 FAIL (${was}, Flaeche C): die Anlege-Seite meldet ihre Aenderung nicht ` +
					`nach oben (gemeldet: ${aufb.gemeldet.join(', ') || '—'}) — dann geht die ` +
					'Auswahl beim Anlegen verloren.'
			);
		});

		test(`${was} — AC-8: die Bruecke reicht den FRISCHEN Stand an den PUT durch`, async () => {
			const geplant: unknown[] = [];
			const aufb = await aufbau(datei, hubZusatz(geplant));
			aufb.maybeSchedule();
			assert.strictEqual(
				geplant.length,
				1,
				`AC-8 FAIL (${was}): ohne geplanten Speichervorgang ist nichts zu pruefen — ` +
					'siehe Flaeche-B-Test oben.'
			);

			await (geplant[0] as (init?: unknown) => Promise<void>)();

			assert.strictEqual(
				aufb.putAufrufe.length,
				1,
				`AC-8 FAIL (${was}): der geplante Vorgang hat ${aufb.putAufrufe.length} PUTs ` +
					'ausgeloest statt genau einem.'
			);
			assert.deepStrictEqual(
				aufb.putAufrufe[0].body.corridors,
				aufb.u.corridors,
				`AC-8 FAIL (${was}): der PUT traegt NICHT den Stand, den die Rueckrufe ` +
					'gemeldet haben. Genau hier entstuende stiller Datenverlust: liest die ' +
					'Bruecke einen eingefrorenen Stand statt bei jedem Zugriff frisch aus den ' +
					'Wertprops, speichert der Hub die vorletzte Fassung.'
			);
		});
	}

	test('Abwesenheits-Zusicherung zur Messweg-Abweichung: kein `$effect` nennt `vergleichSpeicherung`', () => {
		for (const [was, datei] of DATEIEN) {
			const quelle = readFileSync(datei, 'utf-8');
			const ast: Knoten = parse(quelle, { modern: true });
			const effekte = ((ast.instance?.content?.body as Knoten[]) ?? []).filter((s) => {
				if (s.type !== 'ExpressionStatement') return false;
				const a = s.expression as Knoten | undefined;
				if (a?.type !== 'CallExpression') return false;
				const c = a.callee as Knoten;
				const istEffekt =
					(c?.type === 'Identifier' && c.name === '$effect') ||
					(c?.type === 'MemberExpression' &&
						(c.object as Knoten)?.type === 'Identifier' &&
						(c.object as Knoten).name === '$effect');
				return istEffekt && nennungen(a.arguments, quelle, 'vergleichSpeicherung').length > 0;
			});
			assert.strictEqual(
				effekte.length,
				0,
				`${was}: es gibt jetzt doch einen \`$effect\`, der \`vergleichSpeicherung\` ` +
					'nennt. Dann ist die im Kopf dieser Datei begruendete Abweichung vom ' +
					'Spec-Wortlaut („statt `effekteVon()` der echte Handler `maybeSchedule()`") ' +
					'ueberholt — der Guard gehoert auf `effekteVon()` umgestellt, sonst bleibt ' +
					'der neue Effekt-Rumpf unbewacht.'
			);
		}
	});
});

// ── AC-3 Mounts ─────────────────────────────────────────────────────────────

/** Die `{...corridorPropsAus(x)}`-Streuung einer Einbettung — als AST, nicht als
 *  Textmuster. Liefert den Quelltext des Aufrufs und den Namen des uebergebenen
 *  Zustands-Bezeichners. */
function streuung(
	einbettung: Knoten,
	quelle: string
): { ausdruck: string; zustand: string } | null {
	for (const a of (einbettung.attributes ?? []) as Knoten[]) {
		if (a.type !== 'SpreadAttribute') continue;
		const e = a.expression as Knoten;
		if (e?.type !== 'CallExpression') continue;
		const callee = e.callee as Knoten;
		if (callee?.type !== 'Identifier' || callee.name !== 'corridorPropsAus') continue;
		const arg = (e.arguments as Knoten[])?.[0];
		if (arg?.type !== 'Identifier') continue;
		return { ausdruck: quelle.slice(e.start, e.end), zustand: arg.name as string };
	}
	return null;
}

function einbettungen(datei: string, komponente: string): { quelle: string; treffer: Knoten[] } {
	const quelle = readFileSync(datei, 'utf-8');
	const ast: Knoten = parse(quelle, { modern: true });
	return { quelle, treffer: findeKomponenten(ast, komponente) };
}

/** Ein vollstaendig besetzter Wizard-Zustand fuer die vier Corridor-Felder. */
function wizStand(): Knoten {
	return {
		corridors: [{ metric: 'snow_depth_cm', range: [30, 200], notify: false, mark: true }],
		idealRanges: { snow_depth_cm: { min: 30, max: 200 } },
		activeMetricKeys: ['snow_depth_cm'],
		metricAlertLevels: { wind_max_kmh: 'hoch' },
		isEditMode: true,
		activityProfile: 'wandern'
	};
}

const MOUNTS: [string, string, string][] = [
	['Hub /compare/[id], Desktop (Mount B)', HUB, 'CorridorEditor'],
	['Hub /compare/[id], Mobil (Mount B)', HUB, 'CorridorEditorMobile'],
	['Anlege-Seite /compare/new, Desktop (Mount C)', ANLEGE, 'CorridorEditor'],
	['Anlege-Seite /compare/new, Mobil (Mount C)', ANLEGE, 'CorridorEditorMobile']
];

describe('AC-3: alle Vergleichs-Mounts speisen dasselbe Buendel ein', () => {
	for (const [was, datei, komponente] of MOUNTS) {
		test(`${was}: ruft \`corridorPropsAus(<zustand>)\` IM Markup-Ausdruck auf`, () => {
			const { quelle, treffer } = einbettungen(datei, komponente);
			assert.strictEqual(
				treffer.length,
				1,
				`AC-3 FAIL: ${treffer.length} \`${komponente}\`-Einbettungen in ` +
					`${relative(FRONTEND, datei)} statt genau einer.`
			);
			const s = streuung(treffer[0], quelle);
			assert.ok(
				s,
				`AC-3 FAIL (${was}): die Einbettung streut kein ` +
					'`{...corridorPropsAus(<zustand>)}`. 🔴 Form-Auflage A1 der Spec ' +
					'(Design-Entscheidung 1): der Aufruf steht IM Markup-Ausdruck, nicht in ' +
					'einer Skript-Variablen — ein einmal berechnetes, dort eingefrorenes Objekt ' +
					'bestuende SSR-Pruefstand und AST-Waechter anstandslos und fiele erst im ' +
					`Browser auf. Attribute heute: ${attributNamen(treffer[0]).join(', ') || '—'}.`
			);
		});

		test(`${was}: das gestreute Buendel traegt alle vier Werte und alle vier Rueckrufe`, async () => {
			const { quelle, treffer } = einbettungen(datei, komponente);
			const s = treffer.length === 1 ? streuung(treffer[0], quelle) : null;
			assert.ok(s, `AC-3 FAIL (${was}): keine Streuung — siehe vorigen Test.`);

			const wiz = wizStand();
			const { u } = await umgebungFuer(datei, {
				[s!.zustand]: wiz,
				untrack: (fn: () => unknown) => fn()
			});
			let buendel: Knoten;
			try {
				buendel = werte(s!.ausdruck, u) as Knoten;
			} catch (e) {
				return assert.fail(
					`AC-3 FAIL (${was}): \`${s!.ausdruck}\` liess sich nicht auswerten: ` +
						`${(e as Error).message}`
				);
			}

			for (const prop of WERTPROPS) {
				assert.deepStrictEqual(
					buendel[prop],
					wiz[prop],
					`AC-3 FAIL (${was}): das Buendel traegt \`${prop}\` nicht unveraendert aus ` +
						'dem Wizard-Zustand. Jedes Feld, das der Weg vom Zustand zum Baustein ' +
						'verliert, faellt beim naechsten Speichern aus der Nutzlast.'
				);
			}
			for (const rueckruf of RUECKRUFE) {
				assert.strictEqual(
					typeof buendel[rueckruf],
					'function',
					`AC-3 FAIL (${was}): das Buendel liefert keinen \`${rueckruf}\` — ohne ` +
						'Rueckruf verpufft die zugehoerige Geste an diesem Mount.'
				);
			}
		});

		test(`${was}: die Rueckrufe des Buendels schreiben in den Wizard-Zustand zurueck`, async () => {
			const { quelle, treffer } = einbettungen(datei, komponente);
			const s = treffer.length === 1 ? streuung(treffer[0], quelle) : null;
			assert.ok(s, `AC-3 FAIL (${was}): keine Streuung — siehe oben.`);

			const wiz = wizStand();
			const { u } = await umgebungFuer(datei, {
				[s!.zustand]: wiz,
				untrack: (fn: () => unknown) => fn()
			});
			const buendel = werte(s!.ausdruck, u) as Knoten;
			const neu = [{ metric: 'wind_gust', range: [null, 70], notify: false, mark: false }];
			(buendel.onCorridorsChange as (v: unknown) => void)(neu);

			assert.deepStrictEqual(
				wiz.corridors,
				neu,
				`AC-3 FAIL (${was}): \`onCorridorsChange\` erreicht den Wizard-Zustand nicht. ` +
					'Ein Buendel, dessen Rueckrufe ins Leere laufen, bestuende jeden reinen ' +
					'Werte-Vergleich — die Geste waere im Browser trotzdem wirkungslos.'
			);
		});
	}
});
