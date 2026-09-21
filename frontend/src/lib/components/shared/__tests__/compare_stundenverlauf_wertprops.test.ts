// TDD RED — Issue #2276 Scheibe S6b (Epic #2345): die Stundenverlauf-Bedienflaeche
// des Ortsvergleichs (`CompareHourlyLayoutControls.svelte`) arbeitet auf reinen
// WERTPROPS + Rueckrufen statt auf dem Zustandsobjekt `wiz`.
//
// Spec: docs/specs/modules/rework_2276_s6b_wetter_metriken.md
//   AC-1  Kind ist wertprop-rein (`metricKeys`/`enabled` + `onMetricKeys`/
//         `onEnabledChange`; kein `wiz`, kein totes `onHourlyCommit`; der
//         Ein/Aus-Schalter erscheint nur mit `onEnabledChange`)
//   AC-3  der Mount-Block in WeatherMetricsTab bleibt waechterkonform
//         (genau EINE Einbettung, `catalog` bleibt erhalten)
//
// WAS HIER GEMESSEN WIRD — und was nicht:
//   Die Kernsuite ist SSR-only (`node --test` + `svelte/server`, kein DOM).
//   `$effect` und Ereignisse laufen dort nie. Diese Datei misst deshalb die
//   ECHTE Herleitung der Instanz-Skripte gegen gesaete Props
//   (`svelteInstanzPruefstand.ts`): sie ruft die echten Handler der Komponente
//   auf und sieht nach, WAS sie tun — nicht, ob ein Bezeichner im Quelltext
//   steht.
//   Der Wirkort „Browser" (Klick -> Speicherung -> Reload) ist damit NICHT
//   abgedeckt; dafuer ist AC-2 zustaendig
//   (`frontend/e2e/compare-stundenverlauf-wertprops.spec.ts`). Memory-Lehre
//   `bausteintest_beweist_die_verdrahtung_nicht`.
//
// FIXTURE-FALLE (Memory #2387): die Saat unten setzt die neuen Props — das
// allein beweist nichts ueber den MOUNT. Deshalb liest der letzte Block die
// Attribut-Ausdruecke der ECHTEN Einbettung aus `WeatherMetricsTab.svelte`
// und ruft die dort uebergebenen Rueckrufe auf. Schreibt ein Adapter das
// falsche `wiz`-Feld oder fehlt ein Rueckruf, wird genau das rot.
//
// Pfadregel #1409: alles relativ zu DIESER Datei aufgeloest.
//
// Ausfuehren:
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types \
//     --test src/lib/components/shared/__tests__/compare_stundenverlauf_wertprops.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { execFileSync } from 'node:child_process';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { toCompareSelectionEntries } from '../weather-metrics-tab/compareMetricSelection.ts';
import {
	umgebungFuer,
	werte,
	findeKomponenten,
	attributAusdruck,
	attributNamen,
	type Knoten
} from './svelteInstanzPruefstand.ts';

const HIER = dirname(fileURLToPath(import.meta.url));
const SHARED = join(HIER, '..');
const KIND = join(SHARED, 'CompareHourlyLayoutControls.svelte');
const TAB = join(SHARED, 'WeatherMetricsTab.svelte');
// __tests__ -> shared -> components -> lib -> src -> frontend -> repo
const REPO = resolve(HIER, '..', '..', '..', '..', '..', '..');

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

/** Saat fuer das KIND — ausschliesslich die neuen Wertprops. Kein `wiz`:
 *  bleibt im Instanz-Skript eine `wiz`-Referenz stehen, scheitert die
 *  Auswertung LAUT (ReferenceError), statt still durchzulaufen. */
function saatKind(zusatz: Knoten = {}): Knoten {
	return { metricKeys: null, enabled: true, catalog: katalog(), smsSymbols: {}, ...zusatz };
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

describe('AC-1: CompareHourlyLayoutControls leitet alles aus Wertprops her', () => {
	test('die Prop-Schnittstelle nennt die vier Wertprops — und weder `wiz` noch `onHourlyCommit`', async () => {
		const { ast, quelle } = await umgebungFuer(KIND, saatKind());
		// Gemessen wird die WIRKSAME Bindung: das Destrukturierungsmuster von
		// `$props()`, nicht der Kommentar der TS-Schnittstelle darueber.
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
		const namen = ((muster!.id.properties as Knoten[]) ?? [])
			.map((p) => (p.key?.name ?? p.argument?.name) as string)
			.filter(Boolean)
			.sort();

		for (const pflicht of ['metricKeys', 'enabled', 'onMetricKeys', 'onEnabledChange']) {
			assert.ok(
				namen.includes(pflicht),
				`AC-1 FAIL: die Komponente bindet kein \`${pflicht}\`. Gebunden: ${namen.join(', ')}`
			);
		}
		for (const verboten of ['wiz', 'onHourlyCommit']) {
			assert.ok(
				!namen.includes(verboten),
				`AC-1 FAIL: \`${verboten}\` wird weiterhin gebunden. Die Umstellung ist ` +
					`vollstaendig oder sie unterbleibt — „Wertprop wenn da, sonst wiz" ist ` +
					`genau das Anti-Muster, das S6 beseitigen soll (Spec § Known Limitations).`
			);
		}
	});

	test('nirgends im Instanz-Skript steht noch eine `wiz`-Referenz', async () => {
		const { ast, quelle } = await umgebungFuer(KIND, saatKind());
		const treffer: string[] = [];
		function lauf(n: unknown): void {
			if (n === null || typeof n !== 'object') return;
			if (Array.isArray(n)) {
				n.forEach(lauf);
				return;
			}
			const k = n as Knoten;
			if (k.type === 'Identifier' && k.name === 'wiz' && typeof k.start === 'number') {
				const zeile = quelle.slice(0, k.start).split('\n').length;
				treffer.push(`Zeile ${zeile}`);
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

	test('die Auswahl entsteht aus `metricKeys` — `null` liefert die Katalog-Vorgabe', async () => {
		const { u } = await umgebungFuer(KIND, saatKind({ metricKeys: null }));
		const vorgabe = holeAusdruck(
			u,
			'defaultHourlyKeys',
			'AC-1 FAIL: die Katalog-Vorgabe laesst sich nicht herleiten.'
		) as string[];
		const materialisiert = holeAusdruck(
			u,
			'materializedHourlyKeys',
			'AC-1 FAIL: die Auswahl wird nicht aus dem Wertprop `metricKeys` materialisiert ' +
				'(steht die Herleitung noch auf `wiz.hourlyMetricKeys`, scheitert genau das hier).'
		) as string[];
		assert.ok(vorgabe.length > 0, 'Messgrundlage weg: der Katalog nennt keine Vorgabe-Groesse.');
		assert.deepStrictEqual(
			[...materialisiert].sort(),
			[...vorgabe].sort(),
			'AC-1 FAIL: `metricKeys: null` („nie eingestellt") muss die Katalog-Vorgabe ergeben.'
		);
	});

	test('eine bewusst geleerte Auswahl (`[]`) bleibt leer', async () => {
		const { u } = await umgebungFuer(KIND, saatKind({ metricKeys: [] }));
		const materialisiert = holeAusdruck(
			u,
			'materializedHourlyKeys',
			'AC-1 FAIL: die Auswahl wird nicht aus dem Wertprop `metricKeys` materialisiert.'
		) as string[];
		assert.deepStrictEqual(
			materialisiert,
			[],
			'AC-1 FAIL: `[]` ist eine bewusst geleerte Auswahl, nicht „nie eingestellt".'
		);
	});

	test('Abwaehlen meldet die neue Liste ueber `onMetricKeys` — statt `wiz` zu schreiben', async () => {
		const gemeldet: string[][] = [];
		const { u } = await umgebungFuer(
			KIND,
			saatKind({ metricKeys: null, onMetricKeys: (k: string[]) => gemeldet.push(k) })
		);
		const gruppen = holeAusdruck(u, 'hourlyGroups', 'AC-1 FAIL: keine Gruppen.') as Knoten[];
		const aktiv = holeAusdruck(
			u,
			'materializedHourlyKeys',
			'AC-1 FAIL: keine materialisierte Auswahl.'
		) as string[];
		const gruppe = gruppen.find((g) => g.hourly_selectable && aktiv.includes(g.metric_id));
		assert.ok(gruppe, 'Messgrundlage weg: keine anwaehlbare, aktive Gruppe im Katalog.');

		const handler = holeAusdruck(
			u,
			`makeHourlyMetricHandler(hourlyGroups.find((g) => g.metric_id === ${JSON.stringify(gruppe!.metric_id)}))`,
			'AC-1 FAIL: der Umschalt-Handler laesst sich nicht herleiten.'
		) as () => void;
		try {
			handler();
		} catch (e) {
			assert.fail(
				`AC-1 FAIL: der Umschalt-Handler scheitert beim Aufruf: ${(e as Error).message}. ` +
					`Schreibt er noch \`wiz.hourlyMetricKeys\`, gibt es dieses Objekt nicht mehr.`
			);
		}
		assert.strictEqual(
			gemeldet.length,
			1,
			'AC-1 FAIL: das Abwaehlen hat `onMetricKeys` nicht genau einmal gerufen.'
		);
		assert.ok(
			!gemeldet[0].includes(gruppe!.metric_id),
			`AC-1 FAIL: „${gruppe!.metric_id}" war aktiv und muss nach dem Umschalten aus der ` +
				`gemeldeten Liste verschwunden sein. Gemeldet: ${JSON.stringify(gemeldet[0])}`
		);
	});

	test('der Ein/Aus-Schalter meldet ueber `onEnabledChange`', async () => {
		const gemeldet: boolean[] = [];
		const { u } = await umgebungFuer(
			KIND,
			saatKind({ enabled: true, onEnabledChange: (c: boolean) => gemeldet.push(c) })
		);
		const handler = holeAusdruck(
			u,
			'handleEnabledToggle',
			'AC-1 FAIL: der Schalter-Handler laesst sich nicht herleiten.'
		) as (c: boolean) => void;
		try {
			handler(false);
		} catch (e) {
			assert.fail(
				`AC-1 FAIL: der Schalter-Handler scheitert beim Aufruf: ${(e as Error).message}. ` +
					`Schreibt er noch \`wiz.hourlyEnabled\`, gibt es dieses Objekt nicht mehr.`
			);
		}
		assert.deepStrictEqual(
			gemeldet,
			[false],
			'AC-1 FAIL: `onEnabledChange` muss den neuen Zustand genau einmal melden.'
		);
	});

	test('der Schalter wird nur gerendert, wenn `onEnabledChange` uebergeben wird', async () => {
		// Strukturelle Zusicherung (Kunstgriff „Prop da -> Bedienelement da",
		// Vorbild CompareOutlookLayoutControls.svelte:211-227). Der SSR-Harness
		// kennt kein DOM; der sichtbare Beleg ist AC-2 im Browser.
		const { ast, quelle } = await umgebungFuer(KIND, saatKind());
		let gefunden: string | null = null;
		function lauf(n: unknown, bedingungen: string[]): void {
			if (n === null || typeof n !== 'object') return;
			if (Array.isArray(n)) {
				n.forEach((x) => lauf(x, bedingungen));
				return;
			}
			const k = n as Knoten;
			if (k.type === 'Component' && k.name === 'ChannelToggle') {
				gefunden = bedingungen.join(' && ');
				return;
			}
			const tiefer =
				k.type === 'IfBlock' && k.test
					? [...bedingungen, quelle.slice(k.test.start, k.test.end)]
					: bedingungen;
			for (const key of Object.keys(k)) {
				if (key !== 'parent' && key !== 'loc') lauf(k[key], tiefer);
			}
		}
		lauf(ast.fragment, []);
		assert.ok(gefunden !== null, 'AC-1 FAIL: keine `ChannelToggle`-Einbettung gefunden.');
		assert.ok(
			String(gefunden).includes('onEnabledChange'),
			`AC-1 FAIL: der Schalter haengt an der Bedingung „${gefunden}" statt an ` +
				`\`onEnabledChange\`. Eine Flaeche, die den Zustand nicht melden kann, darf ` +
				`ihn auch nicht anbieten.`
		);
	});
});

describe('AC-1/AC-3 Wirkort: der Mount-Block in WeatherMetricsTab reicht die Wertprops durch', () => {
	/** Saat fuer das ELTERNTEIL — der Zustand, den der Ortsvergleich wirklich haelt. */
	function saatTab(wiz: Knoten): Knoten {
		return {
			context: 'vergleich',
			wiz,
			compareCatalog: katalog(),
			metricSymbols: {}
		};
	}

	async function mount(wiz: Knoten) {
		const { ast, quelle, u } = await umgebungFuer(TAB, saatTab(wiz));
		const treffer = findeKomponenten(ast, 'CompareHourlyLayoutControls');
		assert.strictEqual(
			treffer.length,
			1,
			`AC-3 FAIL: ${treffer.length} Einbettungen von CompareHourlyLayoutControls statt genau einer.`
		);
		return { einbettung: treffer[0], quelle, u };
	}

	test('`catalog` bleibt am Mount erhalten (harte Randbedingung der Bestands-Waechter)', async () => {
		const { einbettung, quelle, u } = await mount({ hourlyMetricKeys: null, hourlyEnabled: true });
		const ausdruck = attributAusdruck(einbettung, quelle, 'catalog');
		assert.ok(ausdruck, 'AC-3 FAIL: der Mount reicht kein `catalog` mehr durch.');
		const wert = holeAusdruck(u, ausdruck!, 'AC-3 FAIL: `catalog` laesst sich nicht aufloesen.');
		assert.ok(
			Array.isArray(wert) && wert.length > 0,
			'AC-3 FAIL: `catalog` kommt leer am Kind an — der Auswahl-Block zeigte keine Zeile.'
		);
	});

	test('`wiz` wird nicht mehr durchgereicht', async () => {
		const { einbettung } = await mount({ hourlyMetricKeys: null, hourlyEnabled: true });
		const namen = attributNamen(einbettung);
		assert.ok(
			!namen.includes('wiz'),
			`AC-1 FAIL: der Mount reicht weiterhin \`wiz\` durch (Attribute: ${namen.join(', ')}).`
		);
	});

	test('`metricKeys` und `enabled` kommen aus dem gehaltenen Zustand', async () => {
		const wiz = { hourlyMetricKeys: ['temperature'], hourlyEnabled: false };
		const { einbettung, quelle, u } = await mount(wiz);
		const keysA = attributAusdruck(einbettung, quelle, 'metricKeys');
		const enabledA = attributAusdruck(einbettung, quelle, 'enabled');
		assert.ok(keysA, 'AC-1 FAIL: der Mount reicht kein `metricKeys` durch.');
		assert.ok(enabledA, 'AC-1 FAIL: der Mount reicht kein `enabled` durch.');
		assert.deepStrictEqual(
			holeAusdruck(u, keysA!, 'AC-1 FAIL: `metricKeys` laesst sich nicht aufloesen.'),
			['temperature'],
			'AC-1 FAIL: `metricKeys` zeigt nicht auf die gehaltene Stundenverlauf-Auswahl.'
		);
		assert.strictEqual(
			holeAusdruck(u, enabledA!, 'AC-1 FAIL: `enabled` laesst sich nicht aufloesen.'),
			false,
			'AC-1 FAIL: `enabled` zeigt nicht auf den gehaltenen Ein/Aus-Zustand.'
		);
	});

	test('`onMetricKeys` schreibt die gemeldete Auswahl zurueck in den gehaltenen Zustand', async () => {
		const wiz: Knoten = { hourlyMetricKeys: null, hourlyEnabled: true, outlookMetricKeys: null };
		const { einbettung, quelle, u } = await mount(wiz);
		const ausdruck = attributAusdruck(einbettung, quelle, 'onMetricKeys');
		assert.ok(ausdruck, 'AC-1 FAIL: der Mount reicht keinen `onMetricKeys`-Rueckruf durch.');
		const rueckruf = holeAusdruck(
			u,
			ausdruck!,
			'AC-1 FAIL: `onMetricKeys` laesst sich nicht aufloesen.'
		) as (k: string[]) => void;
		assert.strictEqual(typeof rueckruf, 'function', 'AC-1 FAIL: `onMetricKeys` ist keine Funktion.');
		rueckruf(['wind_speed']);
		assert.deepStrictEqual(
			wiz.hourlyMetricKeys,
			['wind_speed'],
			'AC-1 FAIL: der Adapter schreibt die gemeldete Auswahl nicht nach ' +
				'`hourlyMetricKeys`. Schreibt er ein anderes Feld (z. B. `outlookMetricKeys`), ' +
				'verliert der Stundenverlauf jede Aenderung — und das Feld daneben bekaeme sie.'
		);
		assert.deepStrictEqual(
			wiz.outlookMetricKeys,
			null,
			'AC-1 FAIL: der Adapter hat ein fremdes Feld mitbeschrieben.'
		);
	});

	test('`onEnabledChange` schreibt den gemeldeten Schalterzustand zurueck', async () => {
		const wiz: Knoten = { hourlyMetricKeys: null, hourlyEnabled: true, outlookEnabled: true };
		const { einbettung, quelle, u } = await mount(wiz);
		const ausdruck = attributAusdruck(einbettung, quelle, 'onEnabledChange');
		assert.ok(ausdruck, 'AC-1 FAIL: der Mount reicht keinen `onEnabledChange`-Rueckruf durch.');
		const rueckruf = holeAusdruck(
			u,
			ausdruck!,
			'AC-1 FAIL: `onEnabledChange` laesst sich nicht aufloesen.'
		) as (c: boolean) => void;
		rueckruf(false);
		assert.strictEqual(
			wiz.hourlyEnabled,
			false,
			'AC-1 FAIL: der Adapter schreibt den Schalterzustand nicht nach `hourlyEnabled`.'
		);
		assert.strictEqual(
			wiz.outlookEnabled,
			true,
			'AC-1 FAIL: der Adapter hat den Ausblick-Schalter mitbeschrieben.'
		);
	});
});
