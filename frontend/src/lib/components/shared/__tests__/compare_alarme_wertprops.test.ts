// TDD RED — Issue #2276 Scheibe S6c (Epic #2345): die Alarme-Flaeche des
// Ortsvergleichs (`AlarmeTab.svelte`, `context="vergleich"`) arbeitet auf reinen
// WERTPROPS + Rueckrufen statt auf dem Zustandsobjekt `wiz`. Das Buendel baut
// eine einzige Funktion `compare/alarmePropsAus.ts`, die alle DREI
// Vergleichs-Mounts identisch einspeisen.
//
// Spec: docs/specs/modules/rework_2276_s6c_alarme.md
//   AC-1  AlarmeTab ist im Vergleichs-Zweig wertprop-rein (kein `wiz`)
//   AC-3  `/compare/new` behaelt seine Bedienelemente an beiden Mounts
//   AC-4  Wirkort-Guard: der Selbst-Speicher-Effekt schweigt an negativen Orten
//   AC-6  Aequivalenz-Beweis `context !== 'route'` <=> `!trip` (Entscheidung
//         zu `AlarmeTab.svelte:345`, Implementation Details Punkt 3)
//
// WAS HIER GEMESSEN WIRD — und was nicht:
//   Die Kernsuite ist SSR-only (`node --test` + `svelte/server`, kein DOM).
//   `$effect` und Ereignisse laufen dort nie von selbst. Diese Datei wertet
//   deshalb die ECHTE Herleitung der Instanz-Skripte gegen gesaete Props aus
//   (`svelteInstanzPruefstand.ts`), ruft die echten Handler auf und FUEHRT die
//   Effekt-Ruempfe wirklich aus (`effekteVon()`). Gemessen wird, was der Code
//   mit den Props TUT — nicht, ob ein Bezeichner im Quelltext steht.
//   Der Wirkort „Browser" (Klick -> PUT -> Reload) ist damit NICHT abgedeckt;
//   dafuer ist AC-2 zustaendig (`frontend/e2e/compare-alarme-wertprops.spec.ts`).
//
// 🔴 VAKUUM-FALLE (Memory `fixture_legt_das_feld_selbst_...`, #2387): vier der
// neuen Prop-Namen (`officialWarningsEnabled`, `cooldownMinutes`, `quietFrom`,
// `quietTo`) heissen heute schon so — als LOKALE route-Zustaende in
// AlarmeTab.svelte. `umgebungFuer()` ueberspringt jede Deklaration, deren Name
// bereits in der Saat steht (`if (d.id.name in u) continue`). Eine Saat allein
// bewiese also nichts: sie gewaenne auch dann, wenn die Komponente die Prop
// gar nicht bindet. Deshalb ist der erste Test unten (Prop-Schnittstelle aus
// dem `$props()`-Destrukturierungsmuster) die Anti-Vakuum-Vorbedingung fuer
// alle uebrigen Bloecke — er misst die WIRKSAME Bindung.
//
// 🔴 VERTRAG AN /50: die vier gleichnamigen route-Zustaende muessen umbenannt
// werden (z. B. `routeOfficialWarningsEnabled`), sonst verdeckt der lokale
// `$state` die gleichnamige Prop. Das verschiebt Zeilen auch im Trip-Zweig —
// ausdruecklich zulaessig: Design-Entscheidung 1 der Spec nimmt die
// Zeilenverschiebung in dieser Scheibe in Kauf (die Ratsche wird bewusst
// gepflegt, NICHT durch Zeilenzahl-Wiederherstellung gerettet).
//
// Pfadregel #1409: alles relativ zu DIESER Datei aufgeloest.
//
// Ausfuehren:
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types \
//     --test src/lib/components/shared/__tests__/compare_alarme_wertprops.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { execFileSync, execSync } from 'node:child_process';
import { readFileSync } from 'node:fs';
import { dirname, join, relative, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { parse } from 'svelte/compiler';
import { toCompareSelectionEntries } from '../weather-metrics-tab/compareMetricSelection.ts';
import { deriveActiveAlertMetricsFromCatalog } from '../alarme-tab/activeAlertMetricsFromCatalog.ts';
import { materializeActiveMetricKeys } from '../weather-metrics-tab/compareMetricOrder.ts';
import { alarmSnapshotAus } from '../alarmeVergleichSpeicherung.ts';
import {
	umgebungFuer,
	werte,
	effekteVon,
	findeKomponenten,
	attributAusdruck,
	attributNamen,
	type Knoten
} from './svelteInstanzPruefstand.ts';

const HIER = dirname(fileURLToPath(import.meta.url));
const SHARED = join(HIER, '..');
const COMPONENTS = join(SHARED, '..');
const TAB = join(SHARED, 'AlarmeTab.svelte');
const HUB = join(COMPONENTS, 'compare', 'CompareTabs.svelte');
const ANLEGE = join(COMPONENTS, 'compare-new', 'CompareNewEditor.svelte');
const TRIP = join(COMPONENTS, 'trip-detail', 'AlarmeScheduleTab.svelte');
// __tests__ -> shared -> components -> lib -> src -> frontend -> repo
const REPO = resolve(HIER, '..', '..', '..', '..', '..', '..');
const FRONTEND = join(REPO, 'frontend');

const PY = [
	'import sys, json',
	"sys.path.insert(0, 'src'); sys.path.insert(0, '.')",
	'from output.renderers.compare_metric_catalog import get_compare_metric_catalog',
	'print(json.dumps(get_compare_metric_catalog(), ensure_ascii=False))'
].join('\n');

let katalogCache: Knoten[] | null = null;
/** Die ECHTE Katalogantwort von GET /api/compare/metrics — kein Fixture. */
function katalog(): Knoten[] {
	if (!katalogCache) {
		const stdout = execFileSync('uv', ['run', 'python3', '-c', PY], {
			cwd: REPO,
			encoding: 'utf-8',
			maxBuffer: 32 * 1024 * 1024
		});
		katalogCache = toCompareSelectionEntries({
			metrics: JSON.parse(stdout.trim())
		} as never) as unknown as Knoten[];
	}
	return katalogCache!;
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

/** Die in AC-1 woertlich freigegebenen Wertprops. */
const WERTPROPS = [
	'officialWarningsEnabled',
	'metricAlertLevels',
	'sendTelegram',
	'sendSms',
	'sendPremiumSms',
	'channelThresholds',
	'telegramStyle',
	'cooldownMinutes',
	'quietFrom',
	'quietTo',
	'radarAlertEnabled'
] as const;

/** Die in AC-1 woertlich freigegebenen Rueckrufe. */
const RUECKRUFE = [
	'onOfficialWarningsChange',
	'onMetricLevelChange',
	'onChannelToggle',
	'onThresholdChange',
	'onTelegramStyleChange',
	'onCooldownChange',
	'onQuietHoursChange',
	'onRadarAlertChange'
] as const;

/** Saat fuer den ORGANISMUS im Vergleichs-Zweig — ausschliesslich Wertprops.
 *  Kein `wiz`: bleibt im Instanz-Skript eine `wiz`-Referenz stehen, liefert sie
 *  `undefined` — die Zusicherungen unten werden dann rot, statt still
 *  durchzulaufen. */
function saatVergleich(zusatz: Knoten = {}): Knoten {
	return {
		context: 'vergleich',
		catalog: katalog(),
		untrack: (fn: () => unknown) => fn(),
		officialWarningsEnabled: true,
		metricAlertLevels: { wind_max_kmh: 'hoch' },
		sendTelegram: true,
		sendSms: false,
		sendPremiumSms: false,
		channelThresholds: { telegram: 'mittel' },
		telegramStyle: 'kurzform',
		cooldownMinutes: 30,
		quietFrom: '22:00',
		quietTo: '07:00',
		radarAlertEnabled: false,
		zonenBezug: 'des ersten Orts',
		profileOverride: { premium_sms_allowed: false },
		// route-Props, die der Organismus auch im Vergleichs-Zweig deklariert —
		// ohne sie scheitern seine route-Herleitungen still (ReferenceError).
		existingChannels: null,
		existingChannelThresholds: null,
		...zusatz
	};
}

describe('AC-1: AlarmeTab leitet den Vergleichs-Zweig aus Wertprops her', () => {
	test('die Prop-Schnittstelle bindet alle freigegebenen Wertprops und Rueckrufe — und nicht mehr `wiz`', async () => {
		const { ast, quelle } = await umgebungFuer(TAB, saatVergleich());
		const namen = gebundeneProps(ast, quelle);

		for (const pflicht of [...WERTPROPS, ...RUECKRUFE, 'zonenBezug']) {
			assert.ok(
				namen.includes(pflicht),
				`AC-1 FAIL: die Komponente bindet kein \`${pflicht}\`. Gebunden: ${[...namen].sort().join(', ')}`
			);
		}
		assert.ok(
			!namen.includes('wiz'),
			'AC-1 FAIL: `wiz` wird weiterhin als Prop gebunden. Die Umstellung ist an ' +
				'allen drei Vergleichs-Mounts vollstaendig oder sie unterbleibt — „Wertprop ' +
				'wenn da, sonst wiz" ist genau das Anti-Muster, das S6 beseitigen soll ' +
				'(Spec § Known Limitations).'
		);
	});

	test('nirgends im Instanz-Skript oder Markup steht noch eine `wiz`-Referenz', async () => {
		const { ast, quelle } = await umgebungFuer(TAB, saatVergleich());
		const treffer: string[] = [];
		function lauf(n: unknown): void {
			if (n === null || typeof n !== 'object') return;
			if (Array.isArray(n)) {
				n.forEach(lauf);
				return;
			}
			const k = n as Knoten;
			if (k.type === 'Identifier' && k.name === 'wiz' && typeof k.start === 'number') {
				treffer.push(`Zeile ${quelle.slice(0, k.start).split('\n').length}`);
			}
			for (const key of Object.keys(k)) {
				if (key !== 'parent' && key !== 'loc') lauf(k[key]);
			}
		}
		lauf(ast.instance?.content);
		lauf(ast.fragment);
		assert.deepStrictEqual(
			treffer,
			[],
			`AC-1 FAIL: \`wiz\` wird noch ${treffer.length}x referenziert (${treffer.join(', ')}).`
		);
	});

	test('der Typ-Import von `CompareWizardState` ist verschwunden', async () => {
		const { ast, quelle } = await umgebungFuer(TAB, saatVergleich());
		const importe = ((ast.instance?.content?.body as Knoten[]) ?? [])
			.filter((s) => s.type === 'ImportDeclaration')
			.map((s) => quelle.slice(s.start, s.end));
		assert.deepStrictEqual(
			importe.filter((q) => q.includes('CompareWizardState')),
			[],
			'AC-1 FAIL: AlarmeTab importiert weiterhin den Wizard-Typ aus compare/ — die ' +
				'Klebeschicht bliebe damit Teil der Schnittstelle des geteilten Organismus.'
		);
	});

	test('die Anzeige zeigt die Wertprops, nicht `wiz`', async () => {
		const { ast, quelle, u } = await umgebungFuer(TAB, saatVergleich());
		// Anti-Vakuum-Vorbedingung: die Saat wirkt nur ueber echte Props.
		const namen = gebundeneProps(ast, quelle);
		for (const p of ['officialWarningsEnabled', 'metricAlertLevels', 'channelThresholds']) {
			assert.ok(namen.includes(p), `Messaufbau: \`${p}\` ist keine gebundene Prop.`);
		}

		assert.strictEqual(
			holeAusdruck(u, 'displayOfficialWarningsEnabled', 'AC-1 FAIL: Anzeige nicht herleitbar.'),
			true,
			'AC-1 FAIL: der Schalter „Amtliche Warnungen" zeigt nicht den Wert der Prop ' +
				'`officialWarningsEnabled` (steht die Herleitung noch auf ' +
				'`wiz?.officialWarningsEnabled`, ist sie hier `false`).'
		);
		assert.deepStrictEqual(
			holeAusdruck(u, 'effectiveMetricLevels', 'AC-1 FAIL: Metrik-Stufen nicht herleitbar.'),
			{ wind_max_kmh: 'hoch' },
			'AC-1 FAIL: die Empfindlichkeits-Tabelle liest nicht die Prop `metricAlertLevels`.'
		);
		const kanaele = holeAusdruck(
			u,
			'displayChannelState',
			'AC-1 FAIL: Kanal-Zustand nicht herleitbar.'
		) as Record<string, boolean>;
		assert.deepStrictEqual(
			{ telegram: kanaele.telegram, sms: kanaele.sms, premium_sms: kanaele.premium_sms },
			{ telegram: true, sms: false, premium_sms: false },
			'AC-1 FAIL: die Kanal-Schalter lesen nicht die Props ' +
				'`sendTelegram`/`sendSms`/`sendPremiumSms`.'
		);
		const schwellen = holeAusdruck(
			u,
			'displayChannelThresholds',
			'AC-1 FAIL: Kanal-Schwellen nicht herleitbar.'
		) as Record<string, string>;
		assert.strictEqual(
			schwellen.telegram,
			'mittel',
			'AC-1 FAIL: die Kanal-Schwellen lesen nicht die Prop `channelThresholds`.'
		);
	});

	const gesten: [string, string, unknown[], string, unknown[]][] = [
		[
			'Amtliche Warnungen umschalten',
			'handleOfficialWarningsToggle',
			[false],
			'onOfficialWarningsChange',
			[false]
		],
		[
			'Empfindlichkeit einer Metrik aendern',
			'handleMetricLevelChange',
			['wind_max_kmh', 'gering'],
			'onMetricLevelChange',
			['wind_max_kmh', 'gering']
		],
		['Kanal umschalten', 'handleChannelToggle', ['telegram'], 'onChannelToggle', ['telegram']],
		[
			'Kanal-Schwelle aendern',
			'handleThresholdChange',
			['sms', 'hoch'],
			'onThresholdChange',
			['sms', 'hoch']
		]
	];

	for (const [was, handler, argumente, rueckruf, erwartet] of gesten) {
		test(`${was} meldet ueber \`${rueckruf}\` — statt \`wiz\` zu schreiben`, async () => {
			const gemeldet: unknown[][] = [];
			const { u } = await umgebungFuer(
				TAB,
				saatVergleich({ [rueckruf]: (...a: unknown[]) => gemeldet.push(a) })
			);
			const fn = holeAusdruck(
				u,
				handler,
				`AC-1 FAIL: \`${handler}\` laesst sich nicht herleiten.`
			) as (...a: unknown[]) => void;
			try {
				fn(...argumente);
			} catch (e) {
				assert.fail(
					`AC-1 FAIL: \`${handler}\` scheitert beim Aufruf: ${(e as Error).message}. ` +
						'Schreibt er noch `wiz.*`, gibt es dieses Objekt im Organismus nicht mehr.'
				);
			}
			assert.strictEqual(
				gemeldet.length,
				1,
				`AC-1 FAIL: \`${rueckruf}\` wurde nicht genau einmal gerufen (${gemeldet.length}x). ` +
					'Ohne Rueckruf verpufft die Geste — der Wert wird nirgends gehalten und nie ' +
					'gespeichert.'
			);
			assert.deepStrictEqual(
				gemeldet[0],
				erwartet,
				`AC-1 FAIL: \`${rueckruf}\` meldet die falschen Werte.`
			);
		});
	}
});

/** Die `{...alarmePropsAus(x)}`-Streuung einer Einbettung — als AST, nicht als
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
		if (callee?.type !== 'Identifier' || callee.name !== 'alarmePropsAus') continue;
		const arg = (e.arguments as Knoten[])?.[0];
		if (arg?.type !== 'Identifier') continue;
		return { ausdruck: quelle.slice(e.start, e.end), zustand: arg.name as string };
	}
	return null;
}

/** Der Wert eines fest geschriebenen Text-Attributs (`context="vergleich"`) —
 *  `attributAusdruck()` aus dem Pruefstand liest nur Ausdruecke und faellt bei
 *  Text-Attributen auf den Attributnamen zurueck. */
function textAttribut(einbettung: Knoten, name: string): string | null {
	for (const a of (einbettung.attributes ?? []) as Knoten[]) {
		if (a.type !== 'Attribute' || a.name !== name) continue;
		const v = a.value;
		if (Array.isArray(v) && v.length === 1 && v[0]?.type === 'Text') return String(v[0].data);
		return null;
	}
	return null;
}

/** Alle AlarmeTab-Einbettungen einer Datei samt Quelltext. */
function einbettungen(datei: string): { quelle: string; treffer: Knoten[] } {
	const quelle = readFileSync(datei, 'utf-8');
	const ast: Knoten = parse(quelle, { modern: true });
	return { quelle, treffer: findeKomponenten(ast, 'AlarmeTab') };
}

describe('AC-3: alle drei Vergleichs-Mounts speisen dasselbe Buendel ein', () => {
	/** Ein vollstaendig besetzter Wizard-Zustand (alle 13 Alarm-Felder). */
	function wizStand(): Knoten {
		return {
			officialAlertsEnabled: true,
			officialWarningsEnabled: true,
			radarAlertEnabled: true,
			metricAlertLevels: { wind_max_kmh: 'hoch' },
			alertCooldownMinutes: 30,
			alertQuietFrom: '22:00',
			alertQuietTo: '07:00',
			telegramStyle: 'kurzform',
			sendTelegram: true,
			sendSms: false,
			sendPremiumSms: false,
			channelThresholds: { telegram: 'mittel', sms: 'gering' },
			activeMetricKeys: ['wind_max_kmh']
		};
	}

	const mounts: [string, string, number][] = [
		['Hub /compare/[id] (Mount B)', HUB, 1],
		['Anlege-Seite /compare/new, Desktop + Mobil (Mounts C und D)', ANLEGE, 2]
	];

	for (const [was, datei, anzahl] of mounts) {
		test(`${was}: ruft \`alarmePropsAus(wiz)\` IM Markup-Ausdruck auf und reicht kein \`wiz\` mehr durch`, () => {
			const { quelle, treffer } = einbettungen(datei);
			assert.strictEqual(
				treffer.length,
				anzahl,
				`AC-3 FAIL: ${treffer.length} AlarmeTab-Einbettungen in ${relative(FRONTEND, datei)} ` +
					`statt ${anzahl}.`
			);
			for (const [i, einbettung] of treffer.entries()) {
				const s = streuung(einbettung, quelle);
				assert.ok(
					s,
					`AC-3 FAIL: Einbettung ${i + 1} in ${relative(FRONTEND, datei)} streut kein ` +
						'`{...alarmePropsAus(<zustand>)}`. 🔴 Form-Auflage der Spec (Implementation ' +
						'Details Punkt 4): der Aufruf steht IM Markup-Ausdruck, nicht in einer ' +
						'Skript-Variablen — ein einmal berechnetes, eingefrorenes Objekt bestuende ' +
						'SSR-Pruefstand und AST-Waechter anstandslos und fiele erst im Browser auf. ' +
						`Attribute heute: ${attributNamen(einbettung).join(', ') || '—'}.`
				);
				assert.ok(
					!attributNamen(einbettung).includes('wiz'),
					`AC-3 FAIL: Einbettung ${i + 1} in ${relative(FRONTEND, datei)} reicht weiterhin ` +
						'`wiz` durch.'
				);
				assert.ok(
					attributAusdruck(einbettung, quelle, 'catalog'),
					`AC-3 FAIL: Einbettung ${i + 1} in ${relative(FRONTEND, datei)} reicht kein ` +
						'`catalog` mehr durch — ohne Katalog zeigt die Empfindlichkeits-Tabelle ' +
						'„keine Metriken".'
				);
			}
		});

		test(`${was}: das gestreute Buendel traegt alle Werte und alle Rueckrufe`, async () => {
			const { quelle: q0, treffer } = einbettungen(datei);
			const gestreut = treffer.map((e) => streuung(e, q0));
			assert.ok(
				gestreut.length > 0 && gestreut.every((s) => s !== null),
				`AC-3 FAIL: nicht jede AlarmeTab-Einbettung in ${relative(FRONTEND, datei)} streut ` +
					'`alarmePropsAus(...)` — siehe vorigen Test.'
			);

			for (const [i, s] of gestreut.entries()) {
				const wiz = wizStand();
				const { u } = await umgebungFuer(datei, {
					[s!.zustand]: wiz,
					untrack: (fn: () => unknown) => fn(),
					catalog: katalog(),
					alarmeCatalog: katalog()
				});
				const buendel = holeAusdruck(
					u,
					s!.ausdruck,
					`AC-3 FAIL: \`${s!.ausdruck}\` (Einbettung ${i + 1}) laesst sich nicht auswerten.`
				) as Knoten;
				assert.ok(
					buendel && typeof buendel === 'object',
					`AC-3 FAIL: \`${s!.ausdruck}\` liefert kein Objekt.`
				);

				for (const feld of WERTPROPS) {
					assert.ok(
						feld in buendel,
						`AC-3 FAIL: dem Buendel fehlt der Wert \`${feld}\` (Einbettung ${i + 1}, ` +
							`${relative(FRONTEND, datei)}). Fehlt ein Wert, zeigt die Flaeche dort ` +
							'stumm den Vorgabewert statt des gespeicherten Standes.'
					);
				}
				for (const r of RUECKRUFE) {
					assert.strictEqual(
						typeof buendel[r],
						'function',
						`AC-3 FAIL: dem Buendel fehlt der Rueckruf \`${r}\` (Einbettung ${i + 1}, ` +
							`${relative(FRONTEND, datei)}). Regel „Prop da -> Bedienelement da": ohne ` +
							'Rueckruf verschwindet das Bedienelement oder die Geste verpufft — und ' +
							'KEINE gelistete E2E-Spec beruehrt /compare/new im Alarme-Reiter.'
					);
				}
				assert.strictEqual(
					buendel.zonenBezug,
					'des ersten Orts',
					`AC-3 FAIL: Vergleichs-Mount ${i + 1} liefert nicht den Bezug „des ersten Orts" ` +
						'fuer die Stillen Stunden (#1378 AC-4) — der Vorgabewert „der Tour" gilt nur ' +
						'fuer die Tour.'
				);

				// Rueckschreiben: jeder Rueckruf trifft GENAU sein Feld im Zustand.
				(buendel.onOfficialWarningsChange as (v: boolean) => void)(false);
				assert.strictEqual(
					wiz.officialWarningsEnabled,
					false,
					'AC-3 FAIL: `onOfficialWarningsChange` schreibt nicht nach `officialWarningsEnabled`.'
				);
				(buendel.onMetricLevelChange as (m: string, l: string) => void)('wind_max_kmh', 'gering');
				assert.deepStrictEqual(
					wiz.metricAlertLevels,
					{ wind_max_kmh: 'gering' },
					'AC-3 FAIL: `onMetricLevelChange` schreibt nicht nach `metricAlertLevels`.'
				);
				(buendel.onChannelToggle as (k: string) => void)('telegram');
				assert.strictEqual(
					wiz.sendTelegram,
					false,
					'AC-3 FAIL: `onChannelToggle("telegram")` schaltet `sendTelegram` nicht um.'
				);
				(buendel.onThresholdChange as (k: string, s: string) => void)('sms', 'hoch');
				assert.strictEqual(
					(wiz.channelThresholds as Record<string, string>).sms,
					'hoch',
					'AC-3 FAIL: `onThresholdChange` schreibt nicht nach `channelThresholds`.'
				);
				assert.strictEqual(
					(wiz.channelThresholds as Record<string, string>).telegram,
					'mittel',
					'AC-3 FAIL: `onThresholdChange` hat eine fremde Kanal-Schwelle mitbeschrieben.'
				);
				(buendel.onTelegramStyleChange as (s: string) => void)('rich');
				assert.strictEqual(
					wiz.telegramStyle,
					'rich',
					'AC-3 FAIL: `onTelegramStyleChange` schreibt nicht nach `telegramStyle`.'
				);
				(buendel.onCooldownChange as (m: number | undefined) => void)(45);
				assert.strictEqual(
					wiz.alertCooldownMinutes,
					45,
					'AC-3 FAIL: `onCooldownChange` schreibt nicht nach `alertCooldownMinutes`.'
				);
				(buendel.onQuietHoursChange as (v: string | undefined, b: string | undefined) => void)(
					'23:00',
					'06:00'
				);
				assert.deepStrictEqual(
					{ von: wiz.alertQuietFrom, bis: wiz.alertQuietTo },
					{ von: '23:00', bis: '06:00' },
					'AC-3 FAIL: `onQuietHoursChange(von, bis)` schreibt nicht nach ' +
						'`alertQuietFrom`/`alertQuietTo`.'
				);
				(buendel.onRadarAlertChange as (v: boolean) => void)(false);
				assert.strictEqual(
					wiz.radarAlertEnabled,
					false,
					'AC-3 FAIL: `onRadarAlertChange` schreibt nicht nach `radarAlertEnabled`.'
				);
			}
		});
	}

	test('die gewaehlten Metriken erreichen die Empfindlichkeits-Tabelle ueber das Buendel', async () => {
		// Name-agnostisch: WELCHES Feld das Buendel fuer die gewaehlten Metriken
		// fuehrt, entscheidet /50 — gemessen wird die WIRKUNG am Organismus.
		const { quelle: q0, treffer } = einbettungen(HUB);
		const s = streuung(treffer[0], q0);
		assert.ok(s, 'AC-3 FAIL: der Hub-Mount streut kein `alarmePropsAus(...)` — siehe oben.');

		const wiz = wizStand();
		const { u } = await umgebungFuer(HUB, {
			[s!.zustand]: wiz,
			untrack: (fn: () => unknown) => fn(),
			alarmeCatalog: katalog()
		});
		const buendel = holeAusdruck(u, s!.ausdruck, 'AC-3 FAIL: Buendel nicht auswertbar.') as Knoten;

		const { u: uTab } = await umgebungFuer(TAB, saatVergleich({ ...buendel, catalog: katalog() }));
		const erwartet = deriveActiveAlertMetricsFromCatalog(
			materializeActiveMetricKeys(wiz.activeMetricKeys as string[]),
			katalog() as never
		);
		assert.ok(
			erwartet.length > 0,
			'Messgrundlage weg: der echte Katalog liefert fuer `wind_max_kmh` keine Alarm-Metrik.'
		);
		assert.deepStrictEqual(
			holeAusdruck(uTab, 'effectiveActiveMetrics', 'AC-3 FAIL: Alarm-Metriken nicht herleitbar.'),
			erwartet,
			'AC-3 FAIL: die Empfindlichkeits-Tabelle zeigt nicht die im Vergleich GEWAEHLTEN ' +
				'Groessen. Faellt die Auswahl aus dem Buendel, zeigt der Alarme-Reiter die ' +
				'Vorgabemenge statt der Auswahl des Nutzers.'
		);
	});
});

// ── AC-4: Wirkort-Guard (Lehre aus S6b-Adversary-Finding F001) ───────────────
// Der Selbst-Speicher-Effekt traegt seine Zusicherung im GUARD: er darf nur
// dort arbeiten, wo es eine Vergleichs-Speicherung gibt. Die Mutation
// `if (!vergleichSpeicherung) return;` -> `if (false) return;` ist im Browser
// UNBEOBACHTBAR, weil die E2E-Spec nur im Hub laeuft, wo der Wert ohnehin
// gesetzt ist. Die Zusicherung WIRKT aber genau dort, wo er null ist: im Trip
// (`context === 'route'`) und auf `/compare/new` (ohne preset/saveController).
describe('AC-4 Wirkort-Guard: der Selbst-Speicher-Effekt schweigt ohne Vergleichs-Speicherung', () => {
	/** `vergleichSpeicherung` wird BEWUSST NICHT gesaet — die Umgebung leitet
	 *  sie aus dem ECHTEN Produktivcode her (Fixture-Falle #2387: eine gesaete
	 *  Null liesse genau die Bedingungskette aus, die den Wert erst null macht). */
	async function effektAufbauen(zusatz: Knoten) {
		const gesehen: unknown[] = [];
		const spion = (ziel: unknown) => {
			gesehen.push(ziel);
			return {};
		};
		const { ast, quelle, u } = await umgebungFuer(
			TAB,
			saatVergleich({ alarmSnapshotAus: spion, preset: null, saveController: null, ...zusatz })
		);
		assert.strictEqual(
			u.alarmSnapshotAus,
			spion,
			'Messaufbau kaputt: `alarmSnapshotAus` ist nicht der Spion — dann stuende dort die ' +
				'echte Funktion, der Zaehler bliebe immer 0 und der Test waere vakuum-gruen.'
		);
		const rueckrufe = effekteVon(ast, quelle, u, 'vergleichSpeicherung');
		assert.strictEqual(
			rueckrufe.length,
			1,
			`Messaufbau kaputt: ${rueckrufe.length} $effect-Ruempfe nennen \`vergleichSpeicherung\` ` +
				'(erwartet: genau einer). Eine leere Liste hiesse „nichts ausgefuehrt" — jede ' +
				'Abwesenheits-Zusicherung darunter waere dann wertlos.'
		);
		gesehen.length = 0;
		return { u, rueckruf: rueckrufe[0], gesehen };
	}

	const negativeOrte: [string, Knoten][] = [
		['Trip-Reiter (context === "route")', { context: 'route', trip: { id: 't-1' } }],
		['Anlege-Seite /compare/new (vergleich, ohne preset/saveController)', {}]
	];

	for (const [was, zusatz] of negativeOrte) {
		test(`${was}: der Effekt-Rumpf ruehrt den Speicherweg NICHT an`, async () => {
			const { u, rueckruf, gesehen } = await effektAufbauen(zusatz);
			assert.ok(
				'vergleichSpeicherung' in u,
				'AC-4 FAIL: `vergleichSpeicherung` liess sich aus dem Produktivcode nicht ' +
					'herleiten (umgebungFuer schluckt Deklarations-Fehler still). Solange die ' +
					'Zeile noch `wiz` nennt, scheitert sie hier mit ReferenceError — nach der ' +
					'Umstellung auf das Faehigkeits-Gate (`preset && saveController`) muss sie ' +
					'gelingen, sonst misst der Guard-Test nichts.'
			);
			assert.strictEqual(
				u.vergleichSpeicherung,
				null,
				`Messaufbau kaputt: hier darf es keine Vergleichs-Speicherung geben (${was}).`
			);

			let fehler: unknown = null;
			try {
				rueckruf();
			} catch (e) {
				fehler = e;
			}
			// ZUERST die Zusicherung — unter der Mutation `if (false) return;` laeuft
			// der Snapshot VOR dem TypeError aus `null.aenderungMelden()`. Nur diese
			// Reihenfolge meldet den echten Befund statt eines Folgefehlers.
			assert.strictEqual(
				gesehen.length,
				0,
				'AC-4 FAIL: der Selbst-Speicher-Effekt arbeitet, obwohl es keine ' +
					`Vergleichs-Speicherung gibt (${was}). Faellt der Guard ` +
					'`if (!vergleichSpeicherung) return;` weg, laeuft der Trip-/Anlege-Zweig in ' +
					'den Vergleichs-Speicherweg.'
			);
			assert.strictEqual(
				fehler,
				null,
				`AC-4 FAIL: der Effekt-Rumpf ist gescheitert (${was}): ${(fehler as Error)?.message}`
			);
		});
	}

	test('Gegenprobe: MIT Vergleichs-Speicherung laeuft derselbe Rumpf — und sieht ALLE Alarmfelder', async () => {
		// Ohne diese Richtung misst der Block oben nur „der Effekt laeuft nie".
		// Zusaetzlich faengt sie stillen Datenverlust: der Speicherweg liest 13
		// Felder. Verliert der Weg von `wiz` ueber das Buendel zum Speicherweg
		// eines davon, faellt es beim naechsten Alarm-PUT aus der Nutzlast.
		const { quelle: q0, treffer } = einbettungen(HUB);
		const s = streuung(treffer[0], q0);
		assert.ok(s, 'AC-4 FAIL: der Hub-Mount streut kein Prop-Buendel (siehe AC-3).');

		const wiz: Knoten = {
			officialAlertsEnabled: true,
			officialWarningsEnabled: true,
			radarAlertEnabled: true,
			metricAlertLevels: { wind_max_kmh: 'hoch' },
			alertCooldownMinutes: 30,
			alertQuietFrom: '22:00',
			alertQuietTo: '07:00',
			telegramStyle: 'kurzform',
			sendTelegram: true,
			sendSms: false,
			sendPremiumSms: true,
			channelThresholds: { telegram: 'mittel' },
			activeMetricKeys: ['wind_max_kmh']
		};
		const { u: uHub } = await umgebungFuer(HUB, {
			[s!.zustand]: wiz,
			untrack: (fn: () => unknown) => fn(),
			alarmeCatalog: katalog()
		});
		const buendel = holeAusdruck(
			uHub,
			s!.ausdruck,
			'AC-4 FAIL: Buendel nicht auswertbar.'
		) as Knoten;

		const geplant: unknown[] = [];
		const { u, rueckruf, gesehen } = await effektAufbauen({
			...buendel,
			preset: { id: 'p1', name: 'x', location_ids: [], display_config: {} },
			api: { put: async () => ({}) },
			enqueueHubWrite: <T>(fn: () => Promise<T>) => fn(),
			saveController: {
				schedule: (fn: unknown) => geplant.push(fn),
				cancel: () => {},
				markPristine: () => {}
			}
		});
		assert.ok(
			u.vergleichSpeicherung,
			'Messaufbau kaputt: mit `preset` + `saveController` muss der Produktivcode eine ' +
				'Vergleichs-Speicherung erzeugen.'
		);

		rueckruf();

		assert.strictEqual(
			gesehen.length,
			1,
			'AC-4 FAIL: der Effekt-Rumpf liest den Alarmstand nicht mehr — ein Test, der nur ' +
				'„der Effekt laeuft nie" misst, waere vakuum-gruen.'
		);
		assert.deepStrictEqual(
			alarmSnapshotAus(gesehen[0] as never),
			alarmSnapshotAus(wiz as never),
			'AC-4 FAIL: der Stand, den der Speicherweg sieht, deckt sich NICHT mit dem ' +
				'gehaltenen Alarmstand. Genau hier entstuende stiller Datenverlust: jedes Feld, ' +
				'das der Weg von den Props zum Speicherweg verliert, faellt beim naechsten ' +
				'Alarm-PUT aus der Nutzlast — z. B. `officialAlertsEnabled`, das gar kein ' +
				'Bedienelement hat und deshalb leicht vergessen wird.'
		);
	});
});

// ── AC-6 / Implementation Details Punkt 3: Aequivalenz `context !== 'route'`
//    <=> `!trip` (Schicksal von `AlarmeTab.svelte:345`) ───────────────────────
// Die Spec laesst beide Ausgaenge zu: gelingt der Beweis, faellt `:345`
// zeilentreu zu `if (!trip) return;` und die Ratsche endet bei 53; gelingt er
// nicht, bleibt `:345` stehen und sie endet bei 54. Der Beweis besteht aus zwei
// Teilen — der Praemisse an den ECHTEN Mounts und dem Wirkort-Test des Effekts.
describe('AC-6: `context !== "route"` und `!trip` sind an den echten Mounts gleichbedeutend', () => {
	test('Praemisse: nur der Trip-Mount uebergibt `trip` — und es gibt keinen vierten Ort', () => {
		const ausgabe = execSync("grep -rl '<AlarmeTab' src --include='*.svelte'", {
			cwd: FRONTEND,
			encoding: 'utf-8'
		});
		const dateien = ausgabe
			.split('\n')
			.map((z) => z.trim())
			.filter((z) => z !== '')
			.sort();
		assert.deepStrictEqual(
			dateien,
			[
				'src/lib/components/compare-new/CompareNewEditor.svelte',
				'src/lib/components/compare/CompareTabs.svelte',
				'src/lib/components/trip-detail/AlarmeScheduleTab.svelte'
			].sort(),
			'AC-6 FAIL: die Menge der AlarmeTab-Einbettungen hat sich geaendert. Der ' +
				'Aequivalenz-Beweis `context !== "route"` <=> `!trip` gilt nur fuer die hier ' +
				'gezaehlten Mounts — ein neuer Mount kann ihn brechen.'
		);

		for (const [datei, mitTrip] of [
			[HUB, false],
			[ANLEGE, false],
			[TRIP, true]
		] as [string, boolean][]) {
			const { treffer } = einbettungen(datei);
			assert.ok(treffer.length > 0, `Messgrundlage weg: keine Einbettung in ${datei}.`);
			for (const [i, e] of treffer.entries()) {
				assert.strictEqual(
					attributNamen(e).includes('trip'),
					mitTrip,
					`AC-6 FAIL: Einbettung ${i + 1} in ${relative(FRONTEND, datei)} uebergibt \`trip\` ` +
						'anders als erwartet. Damit faellt die Praemisse des Aequivalenz-Beweises: ' +
						'`:345` darf dann NICHT auf `if (!trip) return;` verkuerzt werden (die ' +
						'Ratsche endete bei 54 statt 53).'
				);
				assert.strictEqual(
					textAttribut(e, 'context'),
					mitTrip ? 'route' : 'vergleich',
					`AC-6 FAIL: Einbettung ${i + 1} in ${relative(FRONTEND, datei)} faehrt einen ` +
						'anderen Kontext — die Zuordnung Kontext <-> `trip` stimmt nicht mehr.'
				);
			}
		}
	});

	test('Wirkort: ohne `trip` ruehrt der Trip-Speicherweg nichts an', async () => {
		const gebaut: unknown[] = [];
		const geplant: unknown[] = [];
		const spion = (...a: unknown[]) => {
			gebaut.push(a);
			return async () => {};
		};
		const { ast, quelle, u } = await umgebungFuer(
			TAB,
			saatVergleich({
				baueTripSpeicherung: spion,
				saveController: { schedule: (fn: unknown) => geplant.push(fn) }
			})
		);
		assert.strictEqual(
			u.baueTripSpeicherung,
			spion,
			'Messaufbau kaputt: `baueTripSpeicherung` ist nicht der Spion — der Zaehler bliebe ' +
				'immer 0 und der Test waere vakuum-gruen.'
		);
		assert.strictEqual(u.trip, undefined, 'Messaufbau kaputt: hier darf es keine Tour geben.');

		const rueckrufe = effekteVon(ast, quelle, u, '_prevAlarmeJson');
		assert.strictEqual(
			rueckrufe.length,
			1,
			`Messaufbau kaputt: ${rueckrufe.length} $effect-Ruempfe nennen \`_prevAlarmeJson\` ` +
				'(erwartet: genau einer — der Trip-Speicher-Effekt).'
		);
		// Ein echter Unterschied zum Ausgangs-Snapshot, damit der Diff-Guard nicht
		// schon vorher abbricht: ohne ihn waere „nichts passiert" nichtssagend.
		u.routeMetricLevels = { wind_max_kmh: 'hoch' };
		gebaut.length = 0;
		geplant.length = 0;

		let fehler: unknown = null;
		try {
			rueckrufe[0]();
		} catch (e) {
			fehler = e;
		}
		assert.deepStrictEqual(
			{ gebaut: gebaut.length, geplant: geplant.length },
			{ gebaut: 0, geplant: 0 },
			'AC-6 FAIL: der Trip-Speicherweg arbeitet, obwohl keine Tour uebergeben wurde. ' +
				'Genau das waere die Folge, wenn der Guard (`AlarmeTab.svelte:345`) ersatzlos ' +
				'entfiele — der Vergleichs-Mount liefe in `buildAlarmeSaveFn()`, das `trip!.id` liest.'
		);
		assert.strictEqual(
			fehler,
			null,
			`AC-6 FAIL: der Trip-Speicher-Effekt ist ohne Tour gescheitert: ${(fehler as Error)?.message}`
		);
	});

	test('Gegenprobe: MIT `trip` plant derselbe Rumpf einen Speichervorgang ein', async () => {
		const gebaut: unknown[] = [];
		const geplant: unknown[] = [];
		const { ast, quelle, u } = await umgebungFuer(TAB, {
			context: 'route',
			trip: { id: 't-1', display_config: {} },
			untrack: (fn: () => unknown) => fn(),
			profileOverride: { premium_sms_allowed: false },
			activeMetrics: [],
			metricLevels: {},
			existingChannels: null,
			existingChannelThresholds: null,
			baueTripSpeicherung: (...a: unknown[]) => {
				gebaut.push(a);
				return async () => {};
			},
			saveController: { schedule: (fn: unknown) => geplant.push(fn) }
		});
		const rueckrufe = effekteVon(ast, quelle, u, '_prevAlarmeJson');
		assert.strictEqual(rueckrufe.length, 1, 'Messaufbau kaputt: Trip-Effekt nicht registriert.');
		u.routeMetricLevels = { wind_max_kmh: 'hoch' };
		gebaut.length = 0;
		geplant.length = 0;

		rueckrufe[0]();

		assert.strictEqual(
			geplant.length,
			1,
			'AC-6 FAIL: mit Tour und geaendertem Stand muss der Trip-Speicherweg genau einen ' +
				'Vorgang einplanen — sonst misst der Test darueber nur „der Effekt laeuft nie".'
		);
		assert.strictEqual(
			gebaut.length,
			1,
			'AC-6 FAIL: die Speicherfunktion wurde nicht aus dem Trip-Stand gebaut.'
		);
	});
});
