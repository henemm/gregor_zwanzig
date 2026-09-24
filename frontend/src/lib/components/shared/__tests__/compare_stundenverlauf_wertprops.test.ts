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
import { fileURLToPath, pathToFileURL } from 'node:url';
import { toCompareSelectionEntries } from '../weather-metrics-tab/compareMetricSelection.ts';
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
const KIND = join(SHARED, 'CompareHourlyLayoutControls.svelte');
const TAB = join(SHARED, 'WeatherMetricsTab.svelte');
// Issue #2276 S6g: WeatherMetricsTab bekommt im Vergleich Wertprops aus dem
// Buendel `compare/wetterMetrikenPropsAus.ts` statt `wiz`. Dynamisch geladen,
// damit ein fehlendes Modul nur die Mount-Tests trifft, nicht die ganze Datei.
const BUENDEL_MODUL = join(SHARED, '..', 'compare', 'wetterMetrikenPropsAus.ts');
async function wetterMetrikenPropsAus(zustand: Knoten): Promise<Knoten> {
	const mod = (await import(pathToFileURL(BUENDEL_MODUL).href)) as Knoten;
	return mod.wetterMetrikenPropsAus(zustand) as Knoten;
}
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
	/** Saat fuer das ELTERNTEIL — der Zustand, den der Ortsvergleich wirklich haelt,
	 *  #2276 S6g: als Wertprop-Buendel `wetterMetrikenPropsAus(wiz)` wie an den
	 *  echten Vergleichs-Mounts (Rueckrufe schreiben in `wiz` zurueck). */
	async function saatTab(wiz: Knoten): Promise<Knoten> {
		return {
			context: 'vergleich',
			...(await wetterMetrikenPropsAus(wiz)),
			compareCatalog: katalog(),
			metricSymbols: {}
		};
	}

	async function mount(wiz: Knoten) {
		const { ast, quelle, u } = await umgebungFuer(TAB, await saatTab(wiz));
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

// ── Fix-Loop S6b, Adversary-Finding F001 (HIGH) ──────────────────────────────
// Die Verkuerzung des Selbst-Speicher-Effekts in `WeatherMetricsTab.svelte`
// (Z. 1272 ff.) traegt ihre Zusicherung im GUARD: der Effekt darf nur dort
// arbeiten, wo es eine Vergleichs-Speicherung gibt. Die Mutation
// `if (!vergleichSpeicherung) return;` -> `if (false) return;` hat KEINEN Test
// rot gemacht — der Pruefstand verwarf `$effect`-Rueckrufe (`u.$effect = () => {}`),
// und die E2E-Spec laeuft ausschliesslich im Ortsvergleich-Hub, wo
// `vergleichSpeicherung` ohnehin gesetzt ist. Die Zusicherung WIRKT aber genau
// dort, wo sie null ist: im Trip (`context === 'route'`) und auf der Anlege-
// Seite `/compare/new` (ohne `preset`/`saveController`).
//
// Deshalb fuehrt der Block unten den Effekt-Rumpf WIRKLICH aus
// (`effekteVon()`), mit `wetterMetrikenSnapshotAus` als Spion. Kein
// Dateiinhalt-Check: gemessen wird, ob der Rumpf laeuft, nicht ob eine Zeile
// im Quelltext steht.
describe('AC-4 Wirkort-Guard: der Selbst-Speicher-Effekt schweigt ohne Vergleichs-Speicherung', () => {
	/** Saat fuer den Effekt. `vergleichSpeicherung` wird BEWUSST NICHT gesaet —
	 *  die Umgebung leitet sie aus dem ECHTEN Produktivcode her
	 *  (`wetterMetrikenVergleichSpeicherungAktiv`, Fixture-Falle #2387: eine
	 *  gesaete Null wuerde genau die Bedingungskette ueberspringen, die den
	 *  Wert ueberhaupt erst null macht).
	 *  `untrack` ist gesaet, weil der Pruefstand `svelte`-Importe nicht bindet;
	 *  ausserhalb einer Reaktion ist `untrack(fn)` exakt `fn()`. */
	function saatEffekt(zusatz: Knoten, spion: (...a: unknown[]) => void): Knoten {
		return {
			context: 'route',
			// #2276 S6g: Wertprops statt `wiz` (alle zehn + neun Rueckrufe gesetzt,
			// damit die Wahl des Praesenz-Guards die Messung nicht beeinflusst).
			...wertpropsVergleich(),
			preset: null,
			saveController: null,
			untrack: (fn: () => unknown) => fn(),
			wetterMetrikenSnapshotAus: spion,
			...zusatz
		};
	}

	function wertpropsVergleich(): Knoten {
		return {
			activeMetricKeys: null,
			channelActiveMetricKeys: { email: null, telegram: null, sms: null },
			officialAlertsEnabled: true,
			dayWindowStartHour: 4,
			dayWindowEndHour: 19,
			hourlyMetricKeys: null,
			hourlyEnabled: true,
			outlookMetricKeys: null,
			outlookMetricFormats: null,
			outlookEnabled: true,
			onVergleichsMetrikenChange: () => {},
			onOfficialAlertsEnabledChange: () => {},
			onDayWindowStartHourChange: () => {},
			onDayWindowEndHourChange: () => {},
			onHourlyMetricKeysChange: () => {},
			onHourlyEnabledChange: () => {},
			onOutlookMetricKeysChange: () => {},
			onOutlookMetricFormatsChange: () => {},
			onOutlookEnabledChange: () => {}
		};
	}

	async function effektAufbauen(zusatz: Knoten) {
		const aufrufe: unknown[] = [];
		const spion = (...a: unknown[]) => {
			aufrufe.push(a);
		};
		const { ast, quelle, u } = await umgebungFuer(TAB, saatEffekt(zusatz, spion));
		// Vorbedingung 1: der Spion haengt wirklich in der Umgebung. Trifft die
		// Saat den Namen nicht, stuende dort die ECHTE Funktion — der Zaehler
		// bliebe immer 0 und der Test waere vakuum-gruen.
		assert.strictEqual(
			u.wetterMetrikenSnapshotAus,
			spion,
			'Messaufbau kaputt: `wetterMetrikenSnapshotAus` ist nicht der Spion.'
		);
		// Vorbedingung 2: der Effekt existiert und liess sich registrieren.
		// Eine leere Liste hiesse „nichts ausgefuehrt" — jede Abwesenheits-
		// Zusicherung darunter waere dann wertlos.
		const rueckrufe = effekteVon(ast, quelle, u, 'vergleichSpeicherung');
		assert.strictEqual(
			rueckrufe.length,
			1,
			'Messaufbau kaputt: ' +
				rueckrufe.length +
				' $effect-Rueckrufe nennen `vergleichSpeicherung` (erwartet: genau einer).'
		);
		aufrufe.length = 0;
		return { u, rueckruf: rueckrufe[0], aufrufe };
	}

	const wirkorte: [string, Knoten][] = [
		['Trip-Kontext (context === "route")', {}],
		[
			'Anlege-Seite /compare/new (vergleich, aber ohne preset/saveController)',
			{ context: 'vergleich', preset: null, saveController: null }
		]
	];

	for (const [was, zusatz] of wirkorte) {
		test(`${was}: der Effekt-Rumpf ruehrt den Speicherweg NICHT an`, async () => {
			const { u, rueckruf, aufrufe } = await effektAufbauen(zusatz);
			// Vorbedingung 3: die Praemisse stammt aus dem Produktivcode.
			assert.ok(
				'vergleichSpeicherung' in u,
				'Messaufbau kaputt: `vergleichSpeicherung` liess sich nicht herleiten ' +
					'(umgebungFuer schluckt Deklarations-Fehler still).'
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
			// ZUERST die Zusicherung — unter der Mutation `if (false) return;`
			// laeuft `wetterMetrikenSnapshotAus(wiz!)` VOR dem TypeError aus
			// `null.aenderungMelden()`. Nur diese Reihenfolge meldet den echten
			// Befund statt eines Folgefehlers.
			assert.strictEqual(
				aufrufe.length,
				0,
				`AC-4 FAIL: der Selbst-Speicher-Effekt arbeitet, obwohl es keine ` +
					`Vergleichs-Speicherung gibt (${was}). Faellt der Guard ` +
					'`if (!vergleichSpeicherung) return;` weg, laeuft der Trip-/Anlege-Zweig ' +
					'in den Vergleichs-Speicherweg.'
			);
			assert.strictEqual(
				fehler,
				null,
				`AC-4 FAIL: der Effekt-Rumpf ist gescheitert (${was}): ${(fehler as Error)?.message}`
			);
		});
	}

	test('Gegenprobe: MIT Vergleichs-Speicherung laeuft derselbe Rumpf und meldet die Aenderung', async () => {
		// Ohne diese Richtung misst der Block oben nur „der Effekt laeuft nie".
		const geplant: unknown[] = [];
		const { u, rueckruf, aufrufe } = await effektAufbauen({
			context: 'vergleich',
			hourlyMetricKeys: null,
			hourlyEnabled: true,
			preset: { id: 'p1' },
			api: { put: async () => ({}) },
			saveController: {
				schedule: (fn: unknown) => geplant.push(fn),
				cancel: () => {},
				markPristine: () => {}
			}
		});
		assert.ok(
			u.vergleichSpeicherung,
			'Messaufbau kaputt: mit vergleich + wiz + preset + saveController muss der ' +
				'Produktivcode eine Vergleichs-Speicherung erzeugen.'
		);
		// Der Stand weicht jetzt von der beim Erzeugen genommenen Baseline ab —
		// `aenderungMelden()` muss deshalb einen Speichervorgang einplanen.
		// #2276 S6g: die Wertprop aendert sich (so, wie der Eltern-Zustand sie
		// nach dem Rueckruf neu einspeist) — die Bruecke liest sie frisch.
		u.hourlyEnabled = false;

		rueckruf();

		assert.strictEqual(
			aufrufe.length,
			1,
			'AC-4 FAIL: der Effekt-Rumpf liest den Stand nicht mehr — ein Test, der nur ' +
				'„der Effekt laeuft nie" misst, waere vakuum-gruen.'
		);
		assert.strictEqual(
			geplant.length,
			1,
			'AC-4 FAIL: die gemeldete Aenderung erreicht den Speicher-Controller nicht ' +
				'(`aenderungMelden()` wurde nicht gerufen oder verpufft).'
		);
	});
});
