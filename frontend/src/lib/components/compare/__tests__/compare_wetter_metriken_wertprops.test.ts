// TDD RED — Issue #2276 Scheibe S6g (Epic #2345): der Wetter-Metriken-Reiter
// des Ortsvergleichs (`shared/WeatherMetricsTab.svelte`, `context="vergleich"`)
// arbeitet auf reinen WERTPROPS + Rueckrufen statt auf dem Wizard-
// Zustandsobjekt `wiz`. Das Buendel baut eine einzige Funktion
// `compare/wetterMetrikenPropsAus.ts`, die alle DREI Vergleichs-Mounts
// identisch einspeisen.
//
// Spec: docs/specs/modules/rework_2276_s6g_wetter_metriken_wertprops.md
//   AC-1  WeatherMetricsTab ist im Vergleichs-Zweig wertprop-rein (AST-Scan,
//         KEIN Text-Grep — die Datei traegt viele Kommentare mit „wiz", ein
//         Text-Grep bliebe nach korrektem GREEN rot)
//   AC-2  alle drei Vergleichs-Mounts streuen `{...wetterMetrikenPropsAus(x)}`
//         IM Markup-Ausdruck; das Buendel traegt alle 19 Namen
//   AC-3  Wirkort-Guard: der Selbst-Speicher-Effekt wirkt nur an Flaeche B (Hub)
//   AC-7  `weatherMetricsCompareSave.ts` ist `wiz`-frei (Datei-weiter Grep)
//   AC-9  gekoppelter Rueckruf `onVergleichsMetrikenChange(active, channelActive)`
//         — EIN Aufruf fuer die Abwahl mit Kanal-Durchschreibung
//
// WAS HIER GEMESSEN WIRD — und was nicht:
//   Die Kernsuite ist SSR-only (`node --test` + `svelte/server`, kein DOM).
//   `$effect` und Ereignisse laufen dort nie von selbst. Diese Datei wertet
//   deshalb die ECHTE Herleitung des Instanz-Skripts gegen gesaete Props aus
//   (`svelteInstanzPruefstand.ts`), FUEHRT den `$effect`-Rumpf, der
//   `vergleichSpeicherung` nennt, wirklich aus (`effekteVon()`) und loest die
//   Abwahl-Geste ueber den ECHTEN `onchange`-Ausdruck der Checkbox im Markup
//   aus. Der Wirkort „Browser" (Klick -> PUT -> Reload) bleibt bei
//   `compare-wetter-metriken-speichert-selbst.spec.ts` (AC-4 der Spec).
//
// 🔴 VAKUUM-FALLE, bewusst entschaerft: `wiz` wird EXPLIZIT als `undefined`
// gesaet (nicht weggelassen) — solange der Quelltext `wiz` noch referenziert,
// liefert das einen deterministischen, lesbaren roten Befund statt eines
// stillen ReferenceError, den `umgebungFuer()` beim Herleiten schluckt. Nach
// der Umstellung ist der Saat-Eintrag wirkungslos — genau das haelt AC-1 fest.
//
// 🔴 `wetterMetrikenPropsAus` wird NUR dynamisch importiert (`ladeBuendel()`):
// ein statischer Import eines (in RED) fehlenden Moduls liesse die ganze Datei
// mit EINEM Ladefehler scheitern, und AC-1/AC-3/AC-7/AC-9 verloren ihren
// eigenen Rot-Grund.
//
// Pfadregel #1409: alles relativ zu DIESER Datei aufgeloest.
//
// Ausfuehren:
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types \
//     --test src/lib/components/compare/__tests__/compare_wetter_metriken_wertprops.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { dirname, join, relative, resolve } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { parse } from 'svelte/compiler';
import {
	umgebungFuer,
	werte,
	effekteVon,
	findeKomponenten,
	attributAusdruck,
	attributNamen,
	type Knoten
} from '../../shared/__tests__/svelteInstanzPruefstand.ts';

const HIER = dirname(fileURLToPath(import.meta.url));
const COMPARE = join(HIER, '..');
const COMPONENTS = join(COMPARE, '..');
const SHARED = join(COMPONENTS, 'shared');
const TAB = join(SHARED, 'WeatherMetricsTab.svelte');
const SPEICHERWEG = join(SHARED, 'weather-metrics-tab', 'weatherMetricsCompareSave.ts');
const HUB = join(COMPARE, 'CompareTabs.svelte');
const ANLEGE = join(COMPONENTS, 'compare-new', 'CompareNewEditor.svelte');
const BUENDEL_MODUL = join(COMPARE, 'wetterMetrikenPropsAus.ts');
// __tests__ -> compare -> components -> lib -> src -> frontend
const FRONTEND = resolve(HIER, '..', '..', '..', '..', '..');

// ── Freigegebene Namen (Spec AC-1, Design-Entscheidung 1/3) ───────────────────

/** Die zehn Wertprops. */
const WERTPROPS = [
	'activeMetricKeys',
	'channelActiveMetricKeys',
	'officialAlertsEnabled',
	'dayWindowStartHour',
	'dayWindowEndHour',
	'hourlyMetricKeys',
	'hourlyEnabled',
	'outlookMetricKeys',
	'outlookMetricFormats',
	'outlookEnabled'
] as const;

/** Die neun Rueckrufe — `onVergleichsMetrikenChange` ist der gekoppelte. */
const RUECKRUFE = [
	'onVergleichsMetrikenChange',
	'onOfficialAlertsEnabledChange',
	'onDayWindowStartHourChange',
	'onDayWindowEndHourChange',
	'onHourlyMetricKeysChange',
	'onHourlyEnabledChange',
	'onOutlookMetricKeysChange',
	'onOutlookMetricFormatsChange',
	'onOutlookEnabledChange'
] as const;

/** Einfeld-Rueckruf -> sein Feld (alle ausser dem gekoppelten). */
const EINFELD_RUECKRUF: [string, string][] = [
	['onOfficialAlertsEnabledChange', 'officialAlertsEnabled'],
	['onDayWindowStartHourChange', 'dayWindowStartHour'],
	['onDayWindowEndHourChange', 'dayWindowEndHour'],
	['onHourlyMetricKeysChange', 'hourlyMetricKeys'],
	['onHourlyEnabledChange', 'hourlyEnabled'],
	['onOutlookMetricKeysChange', 'outlookMetricKeys'],
	['onOutlookMetricFormatsChange', 'outlookMetricFormats'],
	['onOutlookEnabledChange', 'outlookEnabled']
];

/** Unveraenderte Props — die Flaeche A (Tour) darf nichts verlieren (AC-6). */
const UNVERAENDERTE_PROPS = [
	'context',
	'trip',
	'createMode',
	'onChannelsChange',
	'onWeatherMetricsChange',
	'onDayWindowChange',
	'onTripUpdate',
	'saveController',
	'preset',
	'onCompareUpdate',
	'enqueueHubWrite'
] as const;

/** Die Metrik, die in AC-9 abgewaehlt wird, und eine, die bleibt. Beide
 *  stehen in `COMPARE_METRIC_KEYS` — damit ist die Vorbedingung „M ist
 *  angewaehlt" auch unter dem Alt-Code (`wiz` undefined -> Vorgabemenge)
 *  erfuellt, und das Rot kommt aus der Zusicherung, nicht aus dem Aufbau. */
const M = 'wind_max_kmh';
const ANDERE = 'temp_max_c';

// ── Hilfen ───────────────────────────────────────────────────────────────────

async function ladeBuendel(): Promise<(q: Knoten) => Knoten> {
	let mod: Knoten;
	try {
		mod = (await import(pathToFileURL(BUENDEL_MODUL).href)) as Knoten;
	} catch (e) {
		return assert.fail(
			`AC-2 FAIL: das Buendel-Modul ${relative(FRONTEND, BUENDEL_MODUL)} laesst sich nicht ` +
				`laden (${(e as Error).message.split('\n')[0]}). Ohne \`wetterMetrikenPropsAus\` ` +
				'haben die drei Vergleichs-Mounts keine gemeinsame Quelle fuer Werte und Rueckrufe.'
		);
	}
	assert.strictEqual(
		typeof mod.wetterMetrikenPropsAus,
		'function',
		'AC-2 FAIL: das Modul exportiert keine Funktion `wetterMetrikenPropsAus`.'
	);
	return mod.wetterMetrikenPropsAus as (q: Knoten) => Knoten;
}

function holeAusdruck(u: Knoten, ausdruck: string, warum: string): unknown {
	try {
		return werte(ausdruck, u);
	} catch (e) {
		return assert.fail(
			`${warum}\n  \`${ausdruck}\` liess sich nicht auswerten: ${(e as Error).message}\n` +
				`  Herleitbar waren: ${JSON.stringify(Object.keys(u).sort())}`
		);
	}
}

function tabAst(): { ast: Knoten; quelle: string } {
	const quelle = readFileSync(TAB, 'utf-8');
	return { ast: parse(quelle, { modern: true }) as Knoten, quelle };
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

function zeileVon(quelle: string, offset: number): number {
	return quelle.slice(0, offset).split('\n').length;
}

/** Alle Zeilen, an denen der Teilbaum den Bezeichner `name` nennt — AST,
 *  Kommentare zaehlen also NICHT (freistehend, `wiz!`, `wiz?.`, `p.wiz`,
 *  Objekt-Schluessel, Kurzform `{ wiz }`, TS-Prop-Signatur `wiz?:`). */
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
			treffer.push(`Zeile ${zeileVon(quelle, k.start)}`);
		}
		for (const key of Object.keys(k)) {
			if (key !== 'parent' && key !== 'loc') lauf(k[key]);
		}
	}
	lauf(knoten);
	return treffer;
}

/** Objekt-Schluessel `name` in Objekt-Literalen, die als ARGUMENT eines
 *  Funktionsaufrufs stehen — z. B. `erstelleWetterMetrikenVergleichSpeicherung(
 *  { wiz: bruecke, … })` statt `{ zustand: bruecke, … }`. */
function aufrufSchluessel(knoten: unknown, quelle: string, name: string): string[] {
	const treffer: string[] = [];
	function lauf(n: unknown): void {
		if (n === null || typeof n !== 'object') return;
		if (Array.isArray(n)) {
			n.forEach(lauf);
			return;
		}
		const k = n as Knoten;
		if (k.type === 'CallExpression') {
			const callee = k.callee as Knoten;
			const wer =
				callee?.type === 'Identifier'
					? callee.name
					: callee?.type === 'MemberExpression'
						? quelle.slice(callee.start, callee.end)
						: '?';
			for (const arg of (k.arguments as Knoten[]) ?? []) {
				if (arg?.type !== 'ObjectExpression') continue;
				for (const p of (arg.properties as Knoten[]) ?? []) {
					if (p.type === 'Property' && p.key?.type === 'Identifier' && p.key.name === name) {
						treffer.push(`${wer}(… ${name}: …) Zeile ${zeileVon(quelle, p.start)}`);
					}
				}
			}
		}
		for (const key of Object.keys(k)) {
			if (key !== 'parent' && key !== 'loc') lauf(k[key]);
		}
	}
	lauf(knoten);
	return treffer;
}

/** Wertprops fuer den Vergleichs-Zweig — ALLE zehn nicht-`undefined`, damit
 *  GREEN in der Wahl seines Praesenz-Guards frei bleibt (Spec DE-7). */
function wertpropsStand(): Knoten {
	return {
		activeMetricKeys: [M, ANDERE],
		channelActiveMetricKeys: { email: null, telegram: null, sms: null },
		officialAlertsEnabled: true,
		dayWindowStartHour: 5,
		dayWindowEndHour: 18,
		hourlyMetricKeys: [ANDERE],
		hourlyEnabled: true,
		outlookMetricKeys: [ANDERE],
		outlookMetricFormats: {},
		outlookEnabled: true
	};
}

function stilleRueckrufe(): Knoten {
	return Object.fromEntries(RUECKRUFE.map((r) => [r, () => {}]));
}

/** Saat fuer den ORGANISMUS im Vergleichs-Zweig — Wertprops + Rueckrufe.
 *  `wiz` explizit `undefined` (siehe Kopfkommentar). */
function saatVergleich(zusatz: Knoten = {}): Knoten {
	return {
		context: 'vergleich',
		wiz: undefined,
		untrack: (fn: () => unknown) => fn(),
		api: { put: async () => ({}) },
		...wertpropsStand(),
		...stilleRueckrufe(),
		trip: undefined,
		createMode: false,
		onChannelsChange: undefined,
		onWeatherMetricsChange: undefined,
		onDayWindowChange: undefined,
		onTripUpdate: undefined,
		saveController: null,
		preset: null,
		onCompareUpdate: () => {},
		enqueueHubWrite: <T>(fn: () => Promise<T>) => fn(),
		...zusatz
	};
}

function controller(): Knoten {
	return { schedule: () => {}, setDirty: () => {}, cancel: () => {}, markPristine: () => {} };
}

const PRESET = { id: 'p-2276-s6g', name: 'x', location_ids: [], display_config: {} };

// ── AC-1 ─────────────────────────────────────────────────────────────────────

describe('AC-1: WeatherMetricsTab leitet den Vergleichs-Zweig aus Wertprops her', () => {
	test('die Prop-Schnittstelle bindet alle zehn Wertprops, alle neun Rueckrufe und die unveraenderten Props — kein `wiz`', () => {
		const { ast, quelle } = tabAst();
		const namen = gebundeneProps(ast, quelle);
		for (const pflicht of [...WERTPROPS, ...RUECKRUFE]) {
			assert.ok(
				namen.includes(pflicht),
				`AC-1 FAIL: die Komponente bindet kein \`${pflicht}\`. Gebunden: ${[...namen].sort().join(', ')}`
			);
		}
		for (const unveraendert of UNVERAENDERTE_PROPS) {
			assert.ok(
				namen.includes(unveraendert),
				`AC-1 FAIL: die unveraenderte Prop \`${unveraendert}\` ist verschwunden — diese Scheibe ` +
					'tauscht nur die Wizard-Quelle aus, sie nimmt der Flaeche A (Tour) nichts weg (AC-6).'
			);
		}
		assert.ok(
			!namen.includes('wiz'),
			'AC-1 FAIL: `wiz` wird weiterhin als Prop gebunden. Die Umstellung ist an allen drei ' +
				'Vergleichs-Mounts vollstaendig oder sie unterbleibt (Spec § Known Limitations).'
		);
	});

	test('nirgends im Instanz-Skript oder Markup steht noch ein Bezeichner `wiz` (AST, Kommentare zaehlen nicht)', () => {
		const { ast, quelle } = tabAst();
		const treffer = [
			...nennungen(ast.module?.content, quelle, 'wiz'),
			...nennungen(ast.instance?.content, quelle, 'wiz'),
			...nennungen(ast.fragment, quelle, 'wiz')
		];
		assert.deepStrictEqual(
			treffer,
			[],
			`AC-1 FAIL: \`wiz\` wird noch ${treffer.length}x referenziert (${treffer.join(', ')}). ` +
				'„Wertprop wenn da, sonst `wiz`" ist genau das Anti-Muster, das S6 beseitigen soll.'
		);
	});

	test('kein Funktionsaufruf uebergibt ein Objekt mit dem Schluessel `wiz` (Fabrik/Praedikat heissen `zustand`)', () => {
		const { ast, quelle } = tabAst();
		const treffer = [
			...aufrufSchluessel(ast.instance?.content, quelle, 'wiz'),
			...aufrufSchluessel(ast.fragment, quelle, 'wiz')
		];
		assert.deepStrictEqual(
			treffer,
			[],
			`AC-1 FAIL: ${treffer.join('; ')}. \`--experimental-strip-types\` type-checkt nicht und ` +
				'`WetterMetrikenZustand` ist lose typisiert — ein falscher Schluessel `wiz:` statt ' +
				'`zustand:` liesse das Praedikat still auf `false` fallen (Speicherweg tot).'
		);
	});

	test('der Typ `CompareWizardState` ist verschwunden (Import und jede Nennung)', () => {
		const { ast, quelle } = tabAst();
		const treffer = [
			...nennungen(ast.module?.content, quelle, 'CompareWizardState'),
			...nennungen(ast.instance?.content, quelle, 'CompareWizardState')
		];
		assert.deepStrictEqual(
			treffer,
			[],
			`AC-1 FAIL: \`CompareWizardState\` wird noch genannt (${treffer.join(', ')}) — die ` +
				'Compare-Klebeschicht bliebe Teil der Schnittstelle des geteilten Organismus.'
		);
	});
});

// ── AC-2 ─────────────────────────────────────────────────────────────────────

/** Die `{...wetterMetrikenPropsAus(x)}`-Streuung einer Einbettung — als AST. */
function streuung(einbettung: Knoten, quelle: string): { ausdruck: string; zustand: string } | null {
	for (const a of (einbettung.attributes ?? []) as Knoten[]) {
		if (a.type !== 'SpreadAttribute') continue;
		const e = a.expression as Knoten;
		if (e?.type !== 'CallExpression') continue;
		const callee = e.callee as Knoten;
		if (callee?.type !== 'Identifier' || callee.name !== 'wetterMetrikenPropsAus') continue;
		const arg = (e.arguments as Knoten[])?.[0];
		if (arg?.type !== 'Identifier') continue;
		return { ausdruck: quelle.slice(e.start, e.end), zustand: arg.name as string };
	}
	return null;
}

function einbettungen(datei: string): { quelle: string; treffer: Knoten[] } {
	const quelle = readFileSync(datei, 'utf-8');
	const ast: Knoten = parse(quelle, { modern: true });
	return { quelle, treffer: findeKomponenten(ast, 'WeatherMetricsTab') };
}

/** Eine vollstaendig besetzte, unterscheidbare Quelle (alle zehn Felder). */
function quellStand(): Knoten {
	return {
		activeMetricKeys: [M, ANDERE],
		channelActiveMetricKeys: { email: [M], telegram: null, sms: [ANDERE] },
		officialAlertsEnabled: false,
		dayWindowStartHour: 6,
		dayWindowEndHour: 20,
		hourlyMetricKeys: ['temperature'],
		hourlyEnabled: false,
		outlookMetricKeys: [ANDERE],
		outlookMetricFormats: { [ANDERE]: true },
		outlookEnabled: false
	};
}

const MOUNTS: [string, string, number][] = [
	['Hub /compare/[id] (Mount B)', HUB, 1],
	['Anlege-Seite /compare/new, Desktop + Mobil (Mounts C und D)', ANLEGE, 2]
];

describe('AC-2: alle drei Vergleichs-Mounts speisen dasselbe Buendel ein', () => {
	for (const [was, datei, anzahl] of MOUNTS) {
		test(`${was}: ruft \`wetterMetrikenPropsAus(<zustand>)\` IM Markup-Ausdruck auf und reicht kein \`wiz\` mehr durch`, () => {
			const { quelle, treffer } = einbettungen(datei);
			assert.strictEqual(
				treffer.length,
				anzahl,
				`AC-2 FAIL: ${treffer.length} WeatherMetricsTab-Einbettungen in ` +
					`${relative(FRONTEND, datei)} statt ${anzahl}.`
			);
			for (const [i, einbettung] of treffer.entries()) {
				const s = streuung(einbettung, quelle);
				assert.ok(
					s,
					`AC-2 FAIL: Einbettung ${i + 1} in ${relative(FRONTEND, datei)} streut kein ` +
						'`{...wetterMetrikenPropsAus(<zustand>)}`. 🔴 Form-Auflage der Spec (Design-' +
						'Entscheidung 1): der Aufruf steht IM Markup-Ausdruck, nicht in einer ' +
						'Skript-Variablen — ein einmal berechnetes, eingefrorenes Objekt bestuende ' +
						'SSR-Pruefstand und AST-Waechter und fiele erst im Browser auf. Attribute heute: ' +
						`${attributNamen(einbettung).join(', ') || '—'}.`
				);
				assert.ok(
					!attributNamen(einbettung).includes('wiz'),
					`AC-2 FAIL: Einbettung ${i + 1} in ${relative(FRONTEND, datei)} reicht weiterhin ` +
						'`wiz` durch.'
				);
			}
		});

		test(`${was}: das gestreute Buendel traegt alle zehn Werte und alle neun Rueckrufe aus dem Zustand`, async () => {
			const { quelle: q0, treffer } = einbettungen(datei);
			const gestreut = treffer.map((e) => streuung(e, q0));
			assert.ok(
				gestreut.length > 0 && gestreut.every((s) => s !== null),
				`AC-2 FAIL: nicht jede WeatherMetricsTab-Einbettung in ${relative(FRONTEND, datei)} ` +
					'streut `wetterMetrikenPropsAus(...)` — siehe vorigen Test.'
			);
			for (const [i, s] of gestreut.entries()) {
				const zustand = quellStand();
				const { u } = await umgebungFuer(datei, {
					[s!.zustand]: zustand,
					untrack: (fn: () => unknown) => fn()
				});
				const buendel = holeAusdruck(
					u,
					s!.ausdruck,
					`AC-2 FAIL: \`${s!.ausdruck}\` (Einbettung ${i + 1}) laesst sich nicht auswerten.`
				) as Knoten;
				for (const feld of WERTPROPS) {
					assert.deepStrictEqual(
						buendel[feld],
						zustand[feld],
						`AC-2 FAIL: das Buendel traegt \`${feld}\` nicht unveraendert aus dem Zustand ` +
							`(Einbettung ${i + 1}, ${relative(FRONTEND, datei)}).`
					);
				}
				for (const r of RUECKRUFE) {
					assert.strictEqual(
						typeof buendel[r],
						'function',
						`AC-2 FAIL: dem Buendel fehlt der Rueckruf \`${r}\` (Einbettung ${i + 1}, ` +
							`${relative(FRONTEND, datei)}). Mounts C/D sind in der CI-Ampel fuer diesen ` +
							'Reiter strukturell unbewacht — die Geste verpuffte dort unbemerkt.'
					);
				}
			}
		});
	}
});

describe('AC-2: `wetterMetrikenPropsAus` selbst (Fake-Quelle)', () => {
	test('liefert alle 19 Schluessel — genau die zehn Werte der Quelle und neun Funktionen', async () => {
		const wetterMetrikenPropsAus = await ladeBuendel();
		const quelle = quellStand();
		const buendel = wetterMetrikenPropsAus(quelle);
		for (const feld of WERTPROPS) {
			assert.ok(feld in buendel, `AC-2 FAIL: dem Buendel fehlt der Wert \`${feld}\`.`);
			assert.deepStrictEqual(
				buendel[feld],
				quelle[feld],
				`AC-2 FAIL: \`${feld}\` kommt nicht unveraendert aus der Quelle.`
			);
		}
		for (const r of RUECKRUFE) {
			assert.strictEqual(typeof buendel[r], 'function', `AC-2 FAIL: \`${r}\` fehlt oder ist keine Funktion.`);
		}
		assert.ok(!('wiz' in buendel), 'AC-2 FAIL: das Buendel reicht ein `wiz` durch.');
	});

	test('leere Quelle: die Vorgaben sind dieselben wie in `wetterMetrikenSnapshotAus` (Spec DE-1)', async () => {
		const wetterMetrikenPropsAus = await ladeBuendel();
		const buendel = wetterMetrikenPropsAus({});
		const erwartet: Knoten = {
			activeMetricKeys: null,
			channelActiveMetricKeys: { email: null, telegram: null, sms: null },
			officialAlertsEnabled: true,
			dayWindowStartHour: 4,
			dayWindowEndHour: 19,
			hourlyMetricKeys: null,
			hourlyEnabled: true,
			outlookMetricKeys: null,
			outlookMetricFormats: null,
			outlookEnabled: true
		};
		for (const feld of WERTPROPS) {
			assert.deepStrictEqual(
				buendel[feld],
				erwartet[feld],
				`AC-2 FAIL: Vorgabe fuer \`${feld}\` weicht ab (gesehen ${JSON.stringify(buendel[feld])}).`
			);
		}
	});

	for (const [rueckruf, feld] of EINFELD_RUECKRUF) {
		test(`\`${rueckruf}\` schreibt GENAU \`${feld}\` in die Quelle zurueck`, async () => {
			const wetterMetrikenPropsAus = await ladeBuendel();
			const quelle = quellStand();
			const vorher = quellStand();
			const neu = `neu-${feld}`;
			(wetterMetrikenPropsAus(quelle)[rueckruf] as (v: unknown) => void)(neu);
			assert.strictEqual(quelle[feld], neu, `AC-2 FAIL: \`${rueckruf}\` schreibt nicht nach \`${feld}\`.`);
			for (const anderes of WERTPROPS) {
				if (anderes === feld) continue;
				assert.deepStrictEqual(
					quelle[anderes],
					vorher[anderes],
					`AC-2 FAIL: \`${rueckruf}\` hat das fremde Feld \`${anderes}\` mitbeschrieben.`
				);
			}
		});
	}
});

// ── AC-3 Wirkort-Guard ───────────────────────────────────────────────────────
// Der eine `$effect`, der `vergleichSpeicherung` nennt, wird ueber
// `effekteVon()` registriert und wirklich ausgefuehrt. Die Fabrik
// `erstelleWetterMetrikenVergleichSpeicherung` ist ein Spion (gesaete Namen
// verdraengen den echten Import) — das PRAEDIKAT bleibt der echte Produktivcode.
// `vergleichSpeicherung` wird BEWUSST NICHT gesaet (Fixture-Falle #2387).

async function effektAufbauen(zusatz: Knoten) {
	const gemeldet: number[] = [];
	const optionen: Knoten[] = [];
	const fabrik = (opt: Knoten) => {
		optionen.push(opt);
		return { aenderungMelden: () => gemeldet.push(1) };
	};
	const { ast, quelle, u } = await umgebungFuer(
		TAB,
		saatVergleich({ erstelleWetterMetrikenVergleichSpeicherung: fabrik, ...zusatz })
	);
	assert.strictEqual(
		u.erstelleWetterMetrikenVergleichSpeicherung,
		fabrik,
		'Messaufbau kaputt: die Fabrik ist nicht der Spion — der Mitschnitt bliebe leer, vakuum-gruen.'
	);
	assert.ok(
		'vergleichSpeicherung' in u,
		'Messaufbau kaputt: `vergleichSpeicherung` liess sich aus dem Produktivcode nicht herleiten ' +
			'(`umgebungFuer` schluckt Deklarations-Fehler still) — dann misst dieser Block nichts.'
	);
	const rueckrufe = effekteVon(ast, quelle, u, 'vergleichSpeicherung');
	assert.strictEqual(
		rueckrufe.length,
		1,
		`Messaufbau kaputt: ${rueckrufe.length} $effect-Ruempfe nennen \`vergleichSpeicherung\` ` +
			'(erwartet: genau einer).'
	);
	return { u, rueckruf: rueckrufe[0], gemeldet, optionen };
}

describe('AC-3 Wirkort-Guard: der Selbst-Speicher-Effekt wirkt nur an Flaeche B (Hub)', () => {
	test('Flaeche B (Hub: vergleich + preset + saveController + Wertprops): der Effekt meldet die Aenderung', async () => {
		const { u, rueckruf, gemeldet, optionen } = await effektAufbauen({
			preset: PRESET,
			saveController: controller()
		});
		assert.strictEqual(
			optionen.length,
			1,
			'AC-3 FAIL: an Flaeche B entsteht keine Vergleichs-Speicherung (Fabrik nicht gerufen). ' +
				'Der Praesenz-Guard muss aus den WERTPROPS ableiten, dass der Vergleichs-Zweig ' +
				'Zustand hat — nicht mehr aus `!!wiz`.'
		);
		assert.ok(u.vergleichSpeicherung, 'AC-3 FAIL: `vergleichSpeicherung` ist an Flaeche B leer.');
		rueckruf();
		assert.strictEqual(
			gemeldet.length,
			1,
			'AC-3 FAIL: der Effekt-Rumpf meldet an Flaeche B keine Aenderung (`aenderungMelden()` ' +
				'nicht gerufen). Ohne diese Richtung misst der Guard nur „der Effekt laeuft nie".'
		);
	});

	test('Flaeche B: die Fabrik bekommt `zustand` (kein `wiz`) — eine LEBENDE Bruecke auf die Wertprops', async () => {
		const gesetzt: unknown[][] = [];
		const { u, optionen } = await effektAufbauen({
			preset: PRESET,
			saveController: controller(),
			onHourlyEnabledChange: (v: unknown) => gesetzt.push(['onHourlyEnabledChange', v])
		});
		assert.strictEqual(optionen.length, 1, 'AC-3 FAIL: siehe Positivfall — keine Fabrik-Optionen.');
		const opt = optionen[0];
		assert.ok(!('wiz' in opt), 'AC-3/AC-7 FAIL: die Fabrik bekommt noch einen Schluessel `wiz`.');
		assert.ok(opt.zustand, 'AC-3/AC-7 FAIL: die Fabrik bekommt keinen `zustand`.');
		assert.deepStrictEqual(
			opt.zustand.activeMetricKeys,
			[M, ANDERE],
			'AC-3 FAIL: die Bruecke liest `activeMetricKeys` nicht aus der Wertprop.'
		);
		// Lebendig, nicht eingefroren (Spec DE-5: `werte()` liest bei JEDEM Zugriff frisch).
		u.hourlyEnabled = false;
		assert.strictEqual(
			opt.zustand.hourlyEnabled,
			false,
			'AC-3 FAIL: die Bruecke ist eine eingefrorene Kopie — nach einer Prop-Aenderung liest ' +
				'der Speicherweg den alten Wert (Snapshot/Diff sehen die Geste nie).'
		);
		// Rueckschreiben (Rollback) laeuft ueber den Rueckruf des Feldes.
		opt.zustand.hourlyEnabled = true;
		assert.deepStrictEqual(
			gesetzt,
			[['onHourlyEnabledChange', true]],
			'AC-3 FAIL: ein Schreiben auf die Bruecke (Rollback) erreicht `onHourlyEnabledChange` nicht.'
		);
	});

	const negativ: [string, Knoten][] = [
		['Flaeche C/D (Anlegen: vergleich + Wertprops, OHNE preset/saveController)', {}],
		[
			'Flaeche A (Tour: context="route", sonst VOLLSTAENDIG — die Kontext-Barriere allein entscheidet)',
			{ context: 'route', trip: { id: 't-1' }, preset: PRESET, saveController: controller() }
		],
		[
			'Flaeche A (Tour wie echt gemountet: context="route", keine Wertprops/Rueckrufe)',
			{
				context: 'route',
				trip: { id: 't-1' },
				preset: undefined,
				saveController: controller(),
				...Object.fromEntries([...WERTPROPS, ...RUECKRUFE].map((n) => [n, undefined]))
			}
		]
	];

	for (const [was, zusatz] of negativ) {
		test(`${was}: keine Vergleichs-Speicherung, der Effekt-Rumpf bleibt wirkungslos`, async () => {
			const { u, rueckruf, gemeldet, optionen } = await effektAufbauen(zusatz);
			assert.strictEqual(
				optionen.length,
				0,
				`AC-3 FAIL: ${was}: die Vergleichs-Speicherung wird erzeugt — PUT auf einen Vergleich, ` +
					'den es (noch) nicht gibt, bzw. die Tour laeuft in den Vergleichs-Speicherweg.'
			);
			assert.strictEqual(u.vergleichSpeicherung, null, `AC-3 FAIL: ${was}: \`vergleichSpeicherung\` ist gesetzt.`);
			let fehler: unknown = null;
			try {
				rueckruf();
			} catch (e) {
				fehler = e;
			}
			assert.strictEqual(gemeldet.length, 0, `AC-3 FAIL: ${was}: der Effekt meldet eine Aenderung.`);
			assert.strictEqual(
				fehler,
				null,
				`AC-3 FAIL: ${was}: der Effekt-Rumpf ist gescheitert: ${(fehler as Error)?.message}`
			);
		});
	}
});

// ── AC-7 ─────────────────────────────────────────────────────────────────────

describe('AC-7: `weatherMetricsCompareSave.ts` ist `wiz`-frei', () => {
	test('kein Wort `wiz` in der ganzen Datei (Code UND Kommentare; „Wizard" trifft `\\b` nicht)', () => {
		const text = readFileSync(SPEICHERWEG, 'utf-8'); // doc-compliance-test
		const treffer = text
			.split('\n')
			.map((z, i) => [i + 1, z] as const)
			.filter(([, z]) => /\bwiz\b/.test(z))
			.map(([n, z]) => `:${n} ${z.trim()}`);
		assert.deepStrictEqual(
			treffer,
			[],
			`AC-7 FAIL: ${treffer.length} Zeile(n) nennen noch \`wiz\`:\n  ${treffer.join('\n  ')}\n` +
				'Die Fabrik UND das Praedikat heissen `zustand` (Spec DE-4) — ein stehengelassener ' +
				'`wiz`-Schluessel faellt unter `--experimental-strip-types` sonst nirgends auf.'
		);
	});
});

// ── AC-9 ─────────────────────────────────────────────────────────────────────

/** Das `<input>` der Einzel-Auswertungs-Zeile, dessen `onchange` die
 *  Grundauswahl umschaltet — die ECHTE Bedien-Geste. */
function abwahlCheckbox(ast: Knoten, quelle: string): string {
	const treffer: string[] = [];
	function lauf(n: unknown): void {
		if (n === null || typeof n !== 'object') return;
		if (Array.isArray(n)) {
			n.forEach(lauf);
			return;
		}
		const k = n as Knoten;
		if (k.type === 'RegularElement' && k.name === 'input') {
			const a = attributAusdruck(k, quelle, 'onchange');
			if (a && a.includes('toggleCompareMetric')) treffer.push(a);
		}
		for (const key of Object.keys(k)) {
			if (key !== 'parent' && key !== 'loc') lauf(k[key]);
		}
	}
	lauf(ast.fragment);
	assert.strictEqual(
		treffer.length,
		1,
		`Messaufbau kaputt: ${treffer.length} Checkboxen mit \`onchange\` -> toggleCompareMetric ` +
			'(erwartet: genau eine — die Einzel-Auswertungs-Zeile der Grundauswahl).'
	);
	return treffer[0];
}

describe('AC-9: gekoppelter Rueckruf `onVergleichsMetrikenChange` — EIN Aufruf fuer beide Felder', () => {
	test('Abwahl einer Metrik MIT Kanal-Override ueber die echte Checkbox-Geste: genau EIN Aufruf mit (active, channelActive)', async () => {
		const aufrufe: unknown[][] = [];
		const { ast, quelle, u } = await umgebungFuer(
			TAB,
			saatVergleich({
				activeMetricKeys: [M, ANDERE],
				channelActiveMetricKeys: { email: [M, ANDERE], telegram: [ANDERE], sms: null },
				onVergleichsMetrikenChange: (...a: unknown[]) => aufrufe.push(a)
			})
		);
		const vorher = u.materializedActiveMetricKeys as string[] | undefined;
		assert.ok(
			Array.isArray(vorher) && vorher.includes(M),
			`Messaufbau kaputt: \`${M}\` ist vor der Geste nicht angewaehlt ` +
				`(materializedActiveMetricKeys = ${JSON.stringify(vorher)}) — dann waere es eine Einwahl.`
		);
		const onchange = abwahlCheckbox(ast, quelle);
		u.group = { metric_id: M, options: [{ key: M }] };
		const geste = holeAusdruck(u, onchange, 'Messaufbau kaputt: die Checkbox-Geste ist nicht auswertbar.');
		assert.strictEqual(typeof geste, 'function', 'Messaufbau kaputt: `onchange` ist keine Funktion.');
		(geste as () => void)();

		assert.strictEqual(
			aufrufe.length,
			1,
			`AC-9 FAIL: \`onVergleichsMetrikenChange\` wurde ${aufrufe.length}x gerufen (erwartet: genau ` +
				'einmal). Zwei getrennte Schreibungen liessen den Selbst-Speicher-Effekt einen ' +
				'inkonsistenten Zwischenstand sehen; keine Schreibung hiesse, die Abwahl verpufft.'
		);
		assert.deepStrictEqual(
			aufrufe[0],
			[[ANDERE], { email: [ANDERE], telegram: [ANDERE], sms: null }],
			'AC-9 FAIL: der eine Aufruf traegt nicht BEIDE Felder — erwartet die neue Grundauswahl ' +
				'UND die durchgeschriebenen Kanal-Overrides (ADR-0050 Regel 3: eine globale Abwahl ' +
				'wirkt sofort in allen vorhandenen Overrides).'
		);
	});

	test('kanal-lokales Entfernen (`onCompareRemove`) nutzt DENSELBEN Rueckruf, Grundauswahl unveraendert (Spec DE-3)', async () => {
		const aufrufe: unknown[][] = [];
		const { u } = await umgebungFuer(
			TAB,
			saatVergleich({
				activeMetricKeys: [M, ANDERE],
				channelActiveMetricKeys: { email: null, telegram: null, sms: null },
				onVergleichsMetrikenChange: (...a: unknown[]) => aufrufe.push(a)
			})
		);
		const fn = holeAusdruck(u, 'onCompareRemove', 'Messaufbau kaputt: `onCompareRemove` fehlt.');
		(fn as (m: string) => void)(M);
		assert.strictEqual(
			aufrufe.length,
			1,
			`AC-9 FAIL: kanal-lokales Entfernen ruft \`onVergleichsMetrikenChange\` ${aufrufe.length}x.`
		);
		assert.deepStrictEqual(
			aufrufe[0],
			[[M, ANDERE], { email: [ANDERE], telegram: null, sms: null }],
			'AC-9 FAIL: kanal-lokales Entfernen muss die Grundauswahl unveraendert mitgeben und nur ' +
				'den Override des aktiven Kanals (email) anlegen.'
		);
	});

	test('der Rueckruf aus `wetterMetrikenPropsAus(quelle)` setzt BEIDE Felder der Quelle in einem Aufruf', async () => {
		const wetterMetrikenPropsAus = await ladeBuendel();
		const quelle = quellStand();
		const vorher = quellStand();
		const aktiv = [ANDERE];
		const kanal = { email: [ANDERE], telegram: null, sms: null };
		(wetterMetrikenPropsAus(quelle).onVergleichsMetrikenChange as (a: unknown, c: unknown) => void)(
			aktiv,
			kanal
		);
		assert.deepStrictEqual(quelle.activeMetricKeys, aktiv, 'AC-9 FAIL: `activeMetricKeys` nicht gesetzt.');
		assert.deepStrictEqual(
			quelle.channelActiveMetricKeys,
			kanal,
			'AC-9 FAIL: `channelActiveMetricKeys` nicht im selben Aufruf gesetzt.'
		);
		for (const feld of WERTPROPS) {
			if (feld === 'activeMetricKeys' || feld === 'channelActiveMetricKeys') continue;
			assert.deepStrictEqual(quelle[feld], vorher[feld], `AC-9 FAIL: fremdes Feld \`${feld}\` mitbeschrieben.`);
		}
	});

	test('Rollback ueber die Bruecke: Schreiben von `activeMetricKeys` meldet ueber den gekoppelten Rueckruf mit dem AKTUELLEN Kanal-Stand', async () => {
		const aufrufe: unknown[][] = [];
		const optionen: Knoten[] = [];
		const kanal = { email: [ANDERE], telegram: null, sms: null };
		await umgebungFuer(
			TAB,
			saatVergleich({
				preset: PRESET,
				saveController: controller(),
				channelActiveMetricKeys: kanal,
				onVergleichsMetrikenChange: (...a: unknown[]) => aufrufe.push(a),
				erstelleWetterMetrikenVergleichSpeicherung: (opt: Knoten) => {
					optionen.push(opt);
					return { aenderungMelden: () => {} };
				}
			})
		);
		assert.strictEqual(
			optionen.length,
			1,
			'AC-9 FAIL: an Flaeche B entsteht keine Vergleichs-Speicherung — die Bruecke ist nicht messbar ' +
				'(siehe AC-3 Positivfall).'
		);
		const zustand = optionen[0].zustand as Knoten;
		assert.ok(zustand, 'AC-9 FAIL: die Fabrik bekommt keinen `zustand`.');
		zustand.activeMetricKeys = [M, ANDERE];
		assert.deepStrictEqual(
			aufrufe,
			[[[M, ANDERE], kanal]],
			'AC-9 FAIL: ein Rollback-Schreiben von `activeMetricKeys` auf die Bruecke muss GENAU EINEN ' +
				'`onVergleichsMetrikenChange`-Aufruf ausloesen, dessen zweites Argument der frisch ' +
				'gelesene Kanal-Stand ist (Spec DE-5).'
		);
	});
});
