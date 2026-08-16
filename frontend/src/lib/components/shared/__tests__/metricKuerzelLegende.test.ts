// TDD RED — Issue #1888 (Etappe E6, Scheibe B): Legende fuer die SMS-Kuerzel im
// Reiter „Wetter-Metriken" — EIN geteilter Baustein fuer Trip UND Ortsvergleich.
//
// Spec: docs/specs/modules/fix_1888_e6b_kuerzel_legende.md
//   AC-1  jedes gerenderte Kuerzel steht mit nichtleerem Erklaertext in der Legende
//   AC-2  Trip: die sechs Temperatur-/Windchill-Groessen tragen ihr Registerlabel
//   AC-2a Vergleich: `D`/`TF` je ZWEI Zeilen (Auswertung unterscheidet), Kuerzel ohne +/-
//   AC-3  Quelle = Marken-Quelle, keine zweite Liste im Frontend
//   AC-4  fehlende Quelle -> keine Legende (fail-soft), Reiter bleibt bedienbar
//   AC-5  ein Snippet, an BEIDEN Reihenfolge-Bloecken gerendert
// AC-6/AC-7 (Lesbarkeit 320-899 px, Kontrast >= 4.5:1) gehoeren NICHT hierher:
// sie brauchen einen echten Browser gegen Staging (Praezedenzfall #1446).
//
// DREI SCHICHTEN, und alle drei sind noetig:
//   (A) DATEN — AC-1/AC-2/AC-2a sind Aussagen ueber MENGEN und TEXTE („kein
//       Kuerzel ohne Bedeutung", „`D` genau zweimal"). An einer .svelte-Datei
//       sind sie nicht messbar: WeatherMetricsTab holt seine Kataloge in
//       $effect/onMount, und SSR fuehrt beides nie aus — ein SSR-Test waere
//       strukturell immer gruen (#1717). Deshalb verlangen diese Tests eine
//       reine Ableitung `buildKuerzelLegende()` und fuettern sie mit dem
//       ECHTEN Backend-Katalog (`uv run python3`, Muster
//       corridor-editor/__tests__/compareMetricCatalogParity.test.ts).
//       Kein Mock, kein erfundenes Fixture, keine hartkodierte Erwartungsliste.
//   (B) STRUKTUR — dass die Legende im Reiter wirklich haengt, in BEIDEN
//       Kontexten, aus den Marken-Quellen gespeist und fail-soft geschuetzt,
//       wird am ECHTEN Svelte-5-AST geprueft (Muster officialAlertLegend.test.ts
//       und weather_metric_kuerzel_marken.test.ts).
//   (C) VERDRAHTUNG — Adversary F002: (A) und (B) zusammen bewachen die
//       Zusicherung nur dort, wo der Code STEHT, nicht dort, wo er WIRKT.
//       (A) ruft die Ableitung mit selbst sortierten Argumenten auf, (B)
//       prueft nur die ERREICHBARKEIT der Bezeichner. Vertauscht man an der
//       Aufrufstelle die Argumente, ist die Trip-Legende in Produktion leer —
//       und beide Schichten bleiben gruen. Deshalb liest (C) den Quelltext
//       der ECHTEN Aufrufstelle aus dem AST und fuehrt ihn gegen die echten
//       Kataloge aus: Argumentreihenfolge inbegriffen, nichts nachgebaut.
//
// VERTRAG der Ableitung (neu: weather-metrics-tab/kuerzelLegende.ts):
//   buildKuerzelLegende(gerenderteIds, kuerzelById, metricById)
//       -> { kuerzel, bedeutung }[]
//   * massgeblich ist `gerenderteIds` — die Groessen, die der Reihenfolge-
//     Block WIRKLICH zeigt (aktive Zeilen + Aus-Gruppe). Weder der volle
//     Backend-Katalog (Adversary F001: 29 Katalog- gegen 9 gerenderte
//     Groessen in einer frischen Tour) noch der rohe Kuerzel-Katalog
//     (Messung M1: `cape`/`CP` ist selectable=False und nie eine Marke).
//   * je (Groesse, Kuerzel) ein Eintrag; Groessen ohne Kuerzel oder ohne Label
//     entfallen.
//   * `bedeutung` = Label, im Vergleich um die Auswertung ergaenzt.
//   Alle drei Argumente liegen an beiden Aufrufstellen heute schon
//   nebeneinander (route: activeChannelSections + metricSymbols + metricById ·
//   vergleich: compareChannelSections + compareKuerzelById +
//   compareMetricById) — keine neue Ladelogik, kein neuer Endpunkt.
//
// Pfadregel #1409: alles relativ zu DIESER Datei aufloesen — nie ueber einen
// festen Hauptrepo-Pfad, sonst misst der Test aus dem Worktree die falsche Datei.
//
// Ausfuehren:
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types \
//     --test src/lib/components/shared/__tests__/metricKuerzelLegende.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { execFileSync } from 'node:child_process';
import { existsSync, readFileSync, readdirSync, statSync } from 'node:fs';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { parse } from 'svelte/compiler';
import { toCompareSelectionEntries } from '../weather-metrics-tab/compareMetricSelection.ts';

const HIER = dirname(fileURLToPath(import.meta.url));
const SHARED = join(HIER, '..');
const TAB = join(SHARED, 'WeatherMetricsTab.svelte');
const BAUTEIL = join(SHARED, 'weather-metrics-tab', 'kuerzelLegende.ts');
const BAUTEIL_SPEC = '../weather-metrics-tab/kuerzelLegende.ts';
// __tests__ -> shared -> components -> lib -> src -> frontend -> repo
const REPO = resolve(HIER, '..', '..', '..', '..', '..', '..');

/** Anker der Legende — auch der Messpunkt des spaeteren Browser-Nachweises
 *  (AC-6/AC-7). Ohne stabile Testid kann dort nichts gemessen werden. */
const LEGENDE_TESTID = 'metric-kuerzel-legend';

/** Die sechs Groessen aus AC-2. Ihre LABEL stehen bewusst NICHT hier — sie
 *  werden zur Laufzeit aus dem Register gelesen (s. `tripMetricById`). */
const SECHS = [
	'temperature_night', 'temperature_day_low', 'temperature_day_high',
	'wind_chill_night', 'wind_chill_day_low', 'wind_chill_day_high'
];

type Knoten = Record<string, any>;
type Eintrag = { kuerzel: string; bedeutung: string };
/** Rueckgabe der Ableitung: die Zeilen UND der laute Ausgang fuer Groessen,
 *  deren Bedeutung sich nicht aufloesen laesst (frueher ein stummes `continue`). */
type Legende = { eintraege: Eintrag[]; unaufloesbar: string[] };

// ═══════════════════════════════════════════════════════════════════════════
// (A) DATENSCHICHT — echte Backend-Kataloge, kein Fixture
// ═══════════════════════════════════════════════════════════════════════════

const PY = [
	'import sys, json',
	"sys.path.insert(0, 'src'); sys.path.insert(0, '.')",
	'from api.routers.config import get_sms_symbols, get_metrics',
	'from output.renderers.compare_metric_catalog import get_compare_metric_catalog',
	"print(json.dumps({'sms': get_sms_symbols(), 'metrics': get_metrics(),"
		+ " 'compare': get_compare_metric_catalog()}, ensure_ascii=False))"
].join('\n');

let katalogCache: Knoten | null = null;
/** Die drei Katalog-Antworten, die der Reiter im Betrieb wirklich laedt. */
function live(): Knoten {
	if (!katalogCache) {
		const stdout = execFileSync('uv', ['run', 'python3', '-c', PY], {
			cwd: REPO, encoding: 'utf-8', maxBuffer: 32 * 1024 * 1024
		});
		katalogCache = JSON.parse(stdout.trim());
	}
	return katalogCache!;
}

/** `metricSymbols` — WeatherMetricsTab.svelte:182-186. */
function tripKuerzelById(): Record<string, string[]> {
	return Object.fromEntries(
		(live().sms.metrics as Knoten[]).map((m) => [m.metric_id, m.sms_symbols])
	);
}

/** `metricById` — WeatherMetricsTab.svelte:331-335 (Kategorien flachgezogen). */
function tripMetricById(): Record<string, Knoten> {
	const map: Record<string, Knoten> = {};
	for (const ms of Object.values(live().metrics) as Knoten[][]) for (const m of ms) map[m.id] = m;
	return map;
}

/** `compareKuerzelById`/`compareMetricById` — WeatherMetricsTab.svelte:1082-1106,
 *  ueber die ECHTE Endpunkt-Abbildung `toCompareSelectionEntries()`. */
function vergleichPaar(): { kuerzelById: Record<string, string[]>; metricById: Record<string, Knoten> } {
	const kuerzelById: Record<string, string[]> = {};
	const metricById: Record<string, Knoten> = {};
	for (const e of toCompareSelectionEntries({ metrics: live().compare } as never)) {
		if (e.sms_code) kuerzelById[e.metric] = [e.sms_code];
		metricById[e.metric] = {
			id: e.metric, label: e.label, aggregation_label: e.aggregation_label,
			col_label: e.col_label, sms_code: e.sms_code
		};
	}
	return { kuerzelById, metricById };
}

/** Die im Reihenfolge-Block gerenderte Menge des TRIPS. Genommen wird die
 *  Anlege-Vorbelegung (`trip_default_enabled`) — das ist die Auswahl, die eine
 *  frische Tour wirklich zeigt, und sie ist eine echte Teilmenge des Katalogs
 *  (Adversary F001). Nichts hier ist getippt: die Ids kommen aus /api/metrics. */
function gerendertRoute(zusaetzlich: string[] = []): string[] {
	const metricById = tripMetricById();
	const standard = Object.keys(metricById).filter((id) => metricById[id].trip_default_enabled);
	return [...new Set([...standard, ...zusaetzlich])];
}

/** Die im Reihenfolge-Block gerenderte Menge des ORTSVERGLEICHS. Der
 *  Vergleich hat keine Standard-Vorbelegung im Katalog; genommen wird deshalb
 *  „alle Zeilen ausser einer" — die zurueckgehaltene Zeile ist die
 *  Positivkontrolle dafuer, dass Nichtgerendertes auch nicht erklaert wird.
 *  Zurueckgehalten wird eine Zeile mit EINDEUTIGEM Kuerzel (nicht `D`/`TF`),
 *  sonst bliebe ihr Zeichen ueber die Schwesterzeile ohnehin sichtbar. */
function gerendertVergleich(): string[] {
	const { kuerzelById } = vergleichPaar();
	const haeufigkeit = new Map<string, number>();
	for (const ks of Object.values(kuerzelById)) {
		for (const k of ks) haeufigkeit.set(k, (haeufigkeit.get(k) ?? 0) + 1);
	}
	const zurueck = Object.keys(kuerzelById).find(
		(id) => (kuerzelById[id] ?? []).every((k) => haeufigkeit.get(k) === 1)
	);
	assert.ok(zurueck, 'Keine Vergleichszeile mit eindeutigem Kuerzel gefunden.');
	return Object.keys(kuerzelById).filter((id) => id !== zurueck);
}

async function ableitung(): Promise<(
	ids: string[] | null | undefined,
	kuerzelById: Record<string, string[]> | null | undefined,
	metricById: Record<string, Knoten> | null | undefined
) => Legende> {
	assert.ok(
		existsSync(BAUTEIL),
		`RED: die Ableitung \`${BAUTEIL_SPEC}\` gibt es noch nicht. Die Legende ` +
			`braucht eine reine Funktion ` +
			`\`buildKuerzelLegende(gerenderteIds, kuerzelById, metricById)\`, sonst sind ` +
			`AC-1/AC-2/AC-2a (Mengen und Texte) im Kern nicht messbar — der Reiter laedt ` +
			`seine Kataloge in $effect/onMount, unter SSR bleiben sie leer.`
	);
	const mod: Knoten = await import(BAUTEIL_SPEC);
	assert.equal(
		typeof mod.buildKuerzelLegende, 'function',
		`${BAUTEIL_SPEC} exportiert kein \`buildKuerzelLegende\`.`
	);
	return mod.buildKuerzelLegende;
}

async function baue(
	ids: string[] | null | undefined,
	kuerzelById: Record<string, string[]> | null | undefined,
	metricById: Record<string, Knoten> | null | undefined
): Promise<Eintrag[]> {
	return (await ableitung())(ids, kuerzelById, metricById).eintraege;
}

/** Alle Quelldateien unterhalb frontend/src (ohne Tests) — fuer den
 *  Klassen-Waechter „keine Marke ohne Legende". */
function frontendQuellen(dir = join(REPO, 'frontend', 'src'), acc: string[] = []): string[] {
	for (const eintrag of readdirSync(dir)) {
		const voll = join(dir, eintrag);
		if (statSync(voll).isDirectory()) {
			if (eintrag === '__tests__' || eintrag === 'node_modules') continue;
			frontendQuellen(voll, acc);
		} else if (/\.(svelte|ts|js)$/.test(eintrag)) {
			acc.push(voll);
		}
	}
	return acc;
}

/** Probe-Zeilen fuer die Guard-Auswertung (F004): ECHTE Kuerzel und Labels aus
 *  dem Katalog, keine Platzhalter — sonst bestuende eine Bedingung, die am
 *  Inhalt haengt (`eintraege[0].kuerzel === 'X'`), jede Probe mit demselben
 *  Platzhalter. `variante` liefert zu derselben Anzahl andere Zeilen. */
function probeEintraege(anzahl: number, variante = 0): Eintrag[] {
	const kuerzelById = tripKuerzelById();
	const metricById = tripMetricById();
	const ids = Object.keys(metricById).filter((id) => (kuerzelById[id] ?? []).length > 0);
	const quelle = variante === 0 ? ids : [...ids].reverse();
	const zeilen: Eintrag[] = [];
	// Reicht der Katalog fuer die geforderte Anzahl nicht, wird er wiederholt —
	// die Bedingung soll an der ZAHL haengen, nicht an der Katalog-Groesse.
	for (let i = 0; i < anzahl; i++) {
		const id = quelle[i % quelle.length];
		zeilen.push({ kuerzel: kuerzelById[id][0], bedeutung: String(metricById[id].label) });
	}
	return zeilen;
}

/** Erwartete Zuordnung Kuerzel -> Bedeutung fuer eine gerenderte Menge,
 *  ausschliesslich aus den Katalogen berechnet (nicht aus dem Prueflingscode). */
function erwarteteZuordnung(
	ids: string[], kuerzelById: Record<string, string[]>, metricById: Record<string, Knoten>
): Map<string, Set<string>> {
	const erwartet = new Map<string, Set<string>>();
	for (const id of ids) {
		const label = String(metricById[id]?.label ?? '').trim();
		if (!label) continue;
		const auswertung = String(metricById[id]?.aggregation_label ?? '').trim();
		const bedeutung = auswertung ? `${label} (${auswertung})` : label;
		for (const k of kuerzelById[id] ?? []) {
			if (!erwartet.has(k)) erwartet.set(k, new Set());
			erwartet.get(k)!.add(bedeutung);
		}
	}
	return erwartet;
}

describe('AC-1: kein Kuerzel bleibt ohne Erklaertext', () => {
	test('Trip: die Legende deckt genau die Kuerzel der GERENDERTEN Groessen ab', async () => {
		const kuerzelById = tripKuerzelById();
		const metricById = tripMetricById();
		const gerendert = gerendertRoute();
		const erwartet = erwarteteZuordnung(gerendert, kuerzelById, metricById);

		// Positivkontrolle 1 (Adversary F001): die gerenderte Menge ist eine echte
		// TEILMENGE des Katalogs. Waeren beide gleich gross, koennte dieser Test
		// eine Legende aus dem vollen Katalog nicht mehr von der richtigen
		// unterscheiden.
		assert.ok(
			gerendert.length > 2 && gerendert.length < Object.keys(metricById).length,
			`Messgrundlage weg: ${gerendert.length} gerenderte von ` +
				`${Object.keys(metricById).length} Katalog-Groessen. Der Test braucht eine ` +
				`echte Teilmenge — Lage neu bewerten, nicht den Test anpassen.`
		);
		// Positivkontrolle 2 (Messung M1): der ROHE Kuerzel-Katalog fuehrt Kuerzel,
		// die keine gerenderte Groesse traegt — allen voran `CP` (`cape`,
		// selectable=False).
		const roh = new Set(Object.values(kuerzelById).flat());
		const nieGerendert = [...roh].filter((k) => !erwartet.has(k));
		assert.ok(
			nieGerendert.length > 0,
			`Messung M1 gilt nicht mehr: jedes Kuerzel des rohen Katalogs gehoert zu ` +
				`einer gerenderten Groesse. Dann kann dieser Test die naive Speisung aus ` +
				`\`smsSymbols.metrics\` nicht mehr von der richtigen unterscheiden.`
		);

		const eintraege = await baue(gerendert, kuerzelById, metricById);
		assert.deepEqual(
			[...new Set(eintraege.map((e) => e.kuerzel))].sort(),
			[...erwartet.keys()].sort(),
			`AC-1 FAIL: die Legende deckt nicht genau die Kuerzel der gerenderten ` +
				`Groessen ab. Zu viel heisst: sie erklaert Zeichen, die im ` +
				`Reihenfolge-Block gar nicht stehen (nicht gerendert waeren u.a. ` +
				`${nieGerendert.join(', ')}). Zu wenig heisst: eine Marke bleibt ` +
				`unaufloesbar.`
		);
		assert.deepEqual(
			eintraege.filter((e) => !e.bedeutung?.trim()), [],
			'AC-1 FAIL: Eintraege ohne Erklaertext — genau das entsteht, wenn die ' +
				'Legende ueber den rohen Kuerzel-Katalog statt ueber die gerenderten ' +
				'Groessen iteriert (Mutations-Gegenprobe 1 der Spec).'
		);
		for (const e of eintraege) {
			assert.ok(
				erwartet.get(e.kuerzel)?.has(e.bedeutung),
				`AC-1 FAIL: "${e.kuerzel}" wird als ${JSON.stringify(e.bedeutung)} erklaert, ` +
					`der Katalog kennt dafuer ${JSON.stringify([...(erwartet.get(e.kuerzel) ?? [])])}.`
			);
		}
	});

	test('Trip: eine NICHT gerenderte Groesse bekommt keinen Eintrag', async () => {
		const kuerzelById = tripKuerzelById();
		const metricById = tripMetricById();
		const gerendert = gerendertRoute();
		// Eine kuerzeltragende Groesse, die NICHT im Block steht, und deren Kuerzel
		// keine gerenderte Groesse mitfuehrt — echte Daten, nichts erfunden.
		const erwartet = erwarteteZuordnung(gerendert, kuerzelById, metricById);
		const draussen = Object.keys(metricById).find(
			(id) => !gerendert.includes(id) && (kuerzelById[id] ?? []).some((k) => !erwartet.has(k))
		);
		assert.ok(draussen, 'Keine nicht gerenderte Groesse mit eigenem Kuerzel gefunden.');
		const fremd = (kuerzelById[draussen!] ?? []).filter((k) => !erwartet.has(k));

		const eintraege = await baue(gerendert, kuerzelById, metricById);
		const treffer = eintraege.filter((e) => fremd.includes(e.kuerzel));
		assert.deepEqual(
			treffer, [],
			`AC-1 FAIL: die Legende erklaert ${JSON.stringify(fremd)} (Groesse ` +
				`"${draussen}"), obwohl diese Groesse im Reihenfolge-Block nicht steht. ` +
				`Genau so entsteht Rauschen: 20 von 29 Katalog-Groessen sind in einer ` +
				`frischen Tour nicht gewaehlt (Adversary F001).`
		);
	});

	test('Vergleich: jede gerenderte Zeile mit Kuerzel steht mit Bedeutung in der Legende', async () => {
		const { kuerzelById, metricById } = vergleichPaar();
		const gerendert = gerendertVergleich();
		const eintraege = await baue(gerendert, kuerzelById, metricById);
		const mitKuerzel = gerendert.filter((id) => (kuerzelById[id] ?? []).length > 0);
		assert.equal(
			eintraege.length, mitKuerzel.length,
			`AC-1 FAIL: ${mitKuerzel.length} gerenderte Vergleichszeilen tragen ein ` +
				`Kuerzel, die Legende zeigt ${eintraege.length} Eintraege.`
		);
		assert.deepEqual(
			eintraege.filter((e) => !e.kuerzel?.trim() || !e.bedeutung?.trim()), [],
			'AC-1 FAIL: leere Kuerzel oder leere Bedeutungen im Vergleich.'
		);
		// Die zurueckgehaltene Zeile darf nicht auftauchen.
		const zurueck = Object.keys(kuerzelById).find((id) => !gerendert.includes(id));
		const fremd = (kuerzelById[zurueck!] ?? []).filter(
			(k) => !gerendert.some((id) => (kuerzelById[id] ?? []).includes(k))
		);
		assert.deepEqual(
			eintraege.filter((e) => fremd.includes(e.kuerzel)), [],
			`AC-1 FAIL: die Legende erklaert ${JSON.stringify(fremd)} (Zeile ` +
				`"${zurueck}"), obwohl diese Zeile nicht gerendert wird.`
		);
	});
});

describe('AC-2: der Trip-Editor erklaert die sechs Temperatur-/Windchill-Groessen', () => {
	test('jedes der sechs Kuerzel traegt sein Registerlabel', async () => {
		const kuerzelById = tripKuerzelById();
		const metricById = tripMetricById();
		// Die sechs gehoeren nicht zur Anlege-Vorbelegung; die Zusicherung gilt
		// fuer den Nutzer, der sie waehlt — also stehen sie hier im Block.
		const eintraege = await baue(gerendertRoute(SECHS), kuerzelById, metricById);
		const nachKuerzel = new Map(eintraege.map((e) => [e.kuerzel, e.bedeutung]));
		for (const id of SECHS) {
			const kuerzel = kuerzelById[id] ?? [];
			assert.equal(
				kuerzel.length, 1,
				`Messung M3 gilt nicht mehr: ${id} traegt ${JSON.stringify(kuerzel)} statt ` +
					`genau einem Kuerzel — AC-2 neu fassen, nicht den Test.`
			);
			// Der erwartete Text kommt aus DERSELBEN Quelle, aus der ihn auch die
			// Komponente holt (/api/metrics -> label_de). Nichts hier ist getippt.
			const label = metricById[id]?.label;
			assert.ok(label, `Registerlabel fuer ${id} fehlt im Katalog — Scheibe A (#1887) pruefen.`);
			assert.equal(
				nachKuerzel.get(kuerzel[0]), label,
				`AC-2 FAIL: Kuerzel "${kuerzel[0]}" (${id}) wird in der Legende als ` +
					`${JSON.stringify(nachKuerzel.get(kuerzel[0]))} erklaert statt als ` +
					`${JSON.stringify(label)}. Ohne diese Zuordnung erkennt der Nutzer nicht, ` +
					`dass FK/FD/FN dieselben Groessen wie K/D/N in gefuehlter Form sind.`
			);
		}
	});
});

describe('AC-2a: der Ortsvergleich entdoppelt nicht nach Kuerzel', () => {
	test('`D` und `TF` bekommen je zwei Zeilen, unterschieden durch die Auswertung', async () => {
		const { kuerzelById, metricById } = vergleichPaar();
		const gerendert = gerendertVergleich();
		const eintraege = await baue(gerendert, kuerzelById, metricById);
		for (const kuerzel of ['D', 'TF']) {
			const zeilen = gerendert.filter((k) => (kuerzelById[k] ?? []).includes(kuerzel));
			// Positivkontrolle zu Messung M2 — ohne Doppelbelegung prueft der Rest nichts.
			assert.equal(
				zeilen.length, 2,
				`Messung M2 gilt nicht mehr: "${kuerzel}" steht auf ${zeilen.length} ` +
					`Katalogzeilen (${zeilen.join(', ')}). AC-2a neu fassen, nicht den Test.`
			);
			const treffer = eintraege.filter((e) => e.kuerzel === kuerzel);
			assert.equal(
				treffer.length, 2,
				`AC-2a FAIL: "${kuerzel}" erscheint ${treffer.length}-mal statt zweimal. ` +
					`Eine Entdopplung nach Kuerzel bricht die Zusicherung „dieselbe Quelle wie ` +
					`die Marken" — die Marken zeigen das Kuerzel an BEIDEN Zeilen.`
			);
			for (const key of zeilen) {
				const auswertung = String(metricById[key].aggregation_label ?? '');
				assert.equal(
					treffer.filter((t) => t.bedeutung.includes(auswertung)).length, 1,
					`AC-2a FAIL: die Auswertung ${JSON.stringify(auswertung)} (${key}) ist in ` +
						`der Legende nicht genau einmal ablesbar. Ohne sie sind die beiden ` +
						`"${kuerzel}"-Zeilen nicht unterscheidbar: ` +
						`${JSON.stringify(treffer.map((t) => t.bedeutung))}`
				);
			}
		}
		// Der Editor zeigt das ROHE Kuerzel; erst die zugestellte SMS haengt das
		// Auswertungszeichen an (comparison.py:647-650, Messung M2b). Die Legende
		// bildet das Editor-Vokabular ab — `D`, nicht `D+`/`D-`.
		assert.deepEqual(
			eintraege.filter((e) => /[+-]/.test(e.kuerzel)), [],
			'AC-2a FAIL: Kuerzel mit Auswertungszeichen in der Vergleichs-Legende — ' +
				'die Marken im selben Editor zeigen das Zeichen nicht.'
		);
	});
});

describe('AC-4: fehlende Quelle erzeugt keine Leerzeilen', () => {
	test('leere oder halbe Datenlage liefert gar keine Eintraege', async () => {
		const gerendert = gerendertRoute();
		assert.deepEqual(await baue([], {}, {}), [], 'AC-4 FAIL: Eintraege ohne jede Quelle.');
		assert.deepEqual(
			await baue(gerendert, tripKuerzelById(), {}), [],
			'AC-4 FAIL: Kuerzel ohne Bedeutungs-Katalog erzeugen Eintraege — die Legende ' +
				'zeigte dann Kuerzel ohne Erklaerung (schlechter als keine Legende).'
		);
		assert.deepEqual(
			await baue(gerendert, {}, tripMetricById()), [],
			'AC-4 FAIL: Bedeutungen ohne Kuerzel-Katalog erzeugen Eintraege.'
		);
		assert.deepEqual(
			await baue([], tripKuerzelById(), tripMetricById()), [],
			'AC-4 FAIL: ohne gerenderte Groessen entstehen Eintraege — dann haengt die ' +
				'Menge doch am vollen Katalog statt am Reihenfolge-Block (Adversary F001).'
		);
		assert.deepEqual(
			await baue(null, null, null), [],
			'AC-4 FAIL: die Ableitung wirft oder liefert bei fehlenden Quellen nicht [].'
		);
	});
});

// ═══════════════════════════════════════════════════════════════════════════
// (A2) DER LAUTE AUSGANG — Staging-Befund, zweite Haelfte
//
// Frueher verschwand eine gerenderte Groesse ohne aufloesbare Bedeutung
// spurlos (`if (!label) continue`). Eine Luecke, die niemand sehen kann,
// faellt auch keinem Test auf. Sie verlaesst die Ableitung jetzt als eigenes
// Feld `unaufloesbar` — und dieser Test bewacht, dass sie es tut.
// ═══════════════════════════════════════════════════════════════════════════

describe('Kein stilles Verschwinden: unaufloesbare Groessen werden gemeldet', () => {
	test('Kuerzel ohne Bedeutung: kein Eintrag, aber ein Vermerk', async () => {
		const bauen = await ableitung();
		const kuerzelById = tripKuerzelById();
		const metricById = tripMetricById();
		const gerendert = gerendertRoute();
		// Eine Groesse, die WIRKLICH ein Kuerzel traegt — ohne Kuerzel gaebe es
		// auch keine Marke, und dann ist das Ueberspringen richtig und stumm.
		const ersteId = gerendert.find((id) => (kuerzelById[id] ?? []).length > 0);
		assert.ok(ersteId, 'Keine gerenderte Groesse mit Kuerzel gefunden.');

		const sauber = bauen(gerendert, kuerzelById, metricById);
		assert.deepEqual(
			sauber.unaufloesbar, [],
			`Mit echten Katalogen darf nichts unaufloesbar sein — gemeldet: ` +
				`${JSON.stringify(sauber.unaufloesbar)}.`
		);

		// Bedeutung entziehen, Kuerzel behalten: genau der Fall, den der Reiter
		// als Marke rendern wuerde („m" ist da, das Label leer).
		const ohneLabel = { ...metricById, [ersteId]: { ...metricById[ersteId], label: '' } };
		const kaputt = bauen(gerendert, kuerzelById, ohneLabel);
		assert.ok(
			kaputt.unaufloesbar.includes(ersteId),
			`FAIL: "${ersteId}" traegt ein Kuerzel, aber keine Bedeutung — und die ` +
				`Ableitung meldet das nicht (unaufloesbar=${JSON.stringify(kaputt.unaufloesbar)}). ` +
				`Genau dieses stille Ueberspringen hat den Staging-Befund verdeckt.`
		);
		assert.ok(
			!kaputt.eintraege.some((e) => (kuerzelById[ersteId] ?? []).includes(e.kuerzel)),
			`FAIL: die Ableitung erfindet fuer "${ersteId}" trotzdem einen Erklaertext. ` +
				`Ohne Bedeutung darf keine Zeile entstehen (AC-1) — der Fall gehoert ` +
				`gemeldet, nicht ausgefuellt.`
		);
	});
});

// ═══════════════════════════════════════════════════════════════════════════
// (B) STRUKTURSCHICHT — echter Svelte-5-AST der MARKEN-Komponente
//
// Seit dem Staging-Befund steht die Legende in `WeatherV2Reihenfolge.svelte` —
// derselben Komponente, die die Marken rendert, gespeist aus denselben Props.
// Vorher hing sie einmalig im Reiter am Reihenfolge-Block, waehrend die Seite
// mehrere Marken-Bloecke traegt (Trip: Reihenfolge + Ausblick; Vergleich:
// zusaetzlich Stundenverlauf) — deren Marken blieben unerklaert. Die Barriere
// gehoert an den Gefahrenpunkt, nicht acht Bloecke weiter oben.
// ═══════════════════════════════════════════════════════════════════════════

const MARKEN_DATEI = join(SHARED, 'weather-metrics-tab', 'WeatherV2Reihenfolge.svelte');
const QUELLE = readFileSync(MARKEN_DATEI, 'utf-8');
const AST: Knoten = parse(QUELLE, { modern: true });

/** Testid der Kurzform-Marke — der Anker, an dem die Legende haengen muss. */
const MARKE_TESTID = 'wm2-kurzform-badge';

interface Bedingung { quelle: string; test: Knoten; negiert: boolean }

/** Tiefensuche mit Elternkette UND den WIRKSAMEN {#if}-Bedingungen: im
 *  {:else}-Zweig gilt die Bedingung NEGIERT, nicht etwa gar nicht. */
function gehe(
	node: unknown,
	besuch: (n: Knoten, eltern: Knoten[], bed: Bedingung[]) => void,
	eltern: Knoten[] = [], bed: Bedingung[] = []
): void {
	if (node === null || typeof node !== 'object') return;
	if (Array.isArray(node)) { node.forEach((n) => gehe(n, besuch, eltern, bed)); return; }
	const n = node as Knoten;
	if (n.type) besuch(n, eltern, bed);
	const kette = n.type ? [...eltern, n] : eltern;
	const test = n.type === 'IfBlock' && n.test ? QUELLE.slice(n.test.start, n.test.end) : null;
	for (const key of Object.keys(n)) {
		if (key === 'parent' || key === 'loc') continue;
		const naechste = test === null || (key !== 'consequent' && key !== 'alternate')
			? bed
			: [...bed, { quelle: test, test: n.test, negiert: key === 'alternate' }];
		gehe(n[key], besuch, kette, naechste);
	}
}

/** Bezeichner UND Objekt-Eigenschaften eines Teilbaums (`m.sms_code` -> beide). */
function geleseneNamen(subtree: unknown): Set<string> {
	const namen = new Set<string>();
	gehe(subtree, (n) => {
		if (n.type === 'Identifier' && typeof n.name === 'string') namen.add(n.name);
		if (n.type === 'MemberExpression' && !n.computed && n.property?.type === 'Identifier')
			namen.add(n.property.name);
	});
	return namen;
}

/** Alle festen Texte eines Teilbaums: Zeichenketten-Literale und Markup-Text. */
function festeTexte(subtree: unknown): string[] {
	const out: string[] = [];
	gehe(subtree, (n) => {
		if (n.type === 'Literal' && typeof n.value === 'string') out.push(n.value.trim());
		if (n.type === 'Text' && typeof n.data === 'string') out.push(n.data.trim());
	});
	return out.filter(Boolean);
}

function attributWert(n: Knoten, name: string): string | null {
	for (const a of n.attributes ?? []) {
		if (a.type !== 'Attribute' || a.name !== name) continue;
		const v = Array.isArray(a.value) ? a.value : [a.value];
		const literal = v.find((x: Knoten) => x?.type === 'Text');
		return literal ? String(literal.data) : '';
	}
	return null;
}

function elementeMitTestid(testid: string): { knoten: Knoten; eltern: Knoten[]; bed: Bedingung[] }[] {
	const treffer: { knoten: Knoten; eltern: Knoten[]; bed: Bedingung[] }[] = [];
	gehe(AST.fragment, (n, eltern, bed) => {
		if (n.type !== 'RegularElement' && n.type !== 'Component') return;
		if (attributWert(n, 'data-testid') === testid) treffer.push({ knoten: n, eltern, bed });
	});
	return treffer;
}

/** Die eine Legende — mit sprechendem Fehlschlag statt Absturz. */
function dieLegende() {
	const treffer = elementeMitTestid(LEGENDE_TESTID);
	assert.equal(
		treffer.length, 1,
		`FAIL: es muss GENAU EIN Element mit data-testid="${LEGENDE_TESTID}" in ` +
			`WeatherV2Reihenfolge.svelte geben (gefunden: ${treffer.length}). Null heisst: ` +
			`ein Marken-Block ohne Legende — genau der Staging-Befund. Mehr als eins heisst: ` +
			`eine Kopie statt des geteilten Bausteins.`
	);
	return treffer[0];
}

describe('AC-5: die Legende sitzt in der Komponente, die die Marken rendert', () => {
	test('Marken und Legende stehen in DERSELBEN Komponente', () => {
		const marken = elementeMitTestid(MARKE_TESTID);
		assert.ok(
			marken.length > 0,
			`FAIL: WeatherV2Reihenfolge rendert keine Kurzform-Marke (${MARKE_TESTID}) mehr — ` +
				`dann bewacht dieser Test nichts. Wanderten die Marken in eine andere ` +
				`Komponente, muss die Legende mitwandern.`
		);
		dieLegende();
	});

	test('KEINE Datei rendert Marken ohne Legende', () => {
		// Der Klassen-Waechter zum Staging-Befund: dort lagen Marken (in
		// WeatherV2Reihenfolge) und Legende (in WeatherMetricsTab) in
		// VERSCHIEDENEN Dateien, und drei Einbindungen der Marken-Komponente
		// hatten deshalb keine Legende. Wer kuenftig irgendwo eine Kurzform-Marke
		// rendert, muss sie an derselben Stelle auch erklaeren.
		// Auf das VOLLE Attribut geprueft, nicht auf die blosse Zeichenkette:
		// `data-testid="metric-kuerzel-legend-ZZ"` enthaelt den Anker als
		// Teilzeichenkette und haette eine Teilprüfung getäuscht (gemessen).
		const markeAttr = `data-testid="${MARKE_TESTID}"`;
		const legendeAttr = `data-testid="${LEGENDE_TESTID}"`;
		const ohneLegende: string[] = [];
		for (const datei of frontendQuellen()) {
			const src = readFileSync(datei, 'utf-8');
			if (!src.includes(markeAttr)) continue;
			if (!src.includes(legendeAttr)) ohneLegende.push(datei.slice(datei.indexOf('/src/') + 1));
		}
		assert.deepEqual(
			ohneLegende, [],
			`FAIL: diese Dateien rendern Kurzform-Marken, erklaeren sie aber nicht:\n  ` +
				`${ohneLegende.join('\n  ')}\n` +
				`Genau so entstand der Staging-Befund: die Seite traegt mehrere ` +
				`Marken-Bloecke (Trip: Reihenfolge + Ausblick; Vergleich: zusaetzlich ` +
				`Stundenverlauf), die Legende hing nur an einem. Sechs Marken blieben ` +
				`im Ortsvergleich unerklaert.`
		);
	});

	test('Der Reiter fuehrt keine zweite, eigene Legende mehr', () => {
		const reiter = readFileSync(join(SHARED, 'WeatherMetricsTab.svelte'), 'utf-8');
		assert.ok(
			!reiter.includes(LEGENDE_TESTID),
			'FAIL: WeatherMetricsTab.svelte rendert weiterhin eine eigene Legende. Zwei ' +
				'Legenden je Block koennen auseinanderlaufen — die Erklaerung gehoert an ' +
				'die Marke, und zwar genau einmal.'
		);
	});
});

describe('AC-3: die Legende speist sich aus den Props der Marken', () => {
	test('die Ableitung erreicht genau die Quellen, aus denen auch die Marken kommen', () => {
		const aufruf = aufrufKnoten();
		const erreicht = geleseneNamen(aufruf);
		for (const quelle of ['primaryColumns', 'offColumns', 'kuerzelById', 'metricById']) {
			assert.ok(
				erreicht.has(quelle),
				`AC-3 FAIL: die Legende erreicht \`${quelle}\` nicht. Sie muss aus DENSELBEN ` +
					`Props kommen wie die Marken — sonst kann sie von ihnen abweichen, und ` +
					`genau das ist auf Staging passiert. Erreichbar: ` +
					`${JSON.stringify([...erreicht].sort())}`
			);
		}
	});

	test('die Aus-Gruppe ist mitgedeckt', () => {
		const quelltext = QUELLE.slice(aufrufKnoten().start, aufrufKnoten().end);
		assert.ok(
			/offColumns/.test(quelltext),
			`AC-1 FAIL: die Legende deckt \`offColumns\` nicht ab. Die Aus-Gruppe wird ` +
				`gerendert und traegt Marken — ohne sie blieben deren Kuerzel unerklaert. ` +
				`Aufruf: ${quelltext}`
		);
	});

	test('im Legenden-Markup steht kein Kuerzel und kein Label als fester Text', () => {
		const legende = dieLegende();
		const verboten = new Set<string>([
			...Object.values(tripKuerzelById()).flat(),
			...Object.values(tripMetricById()).map((m) => String(m.label)),
			...SECHS
		]);
		const treffer = festeTexte(legende.knoten).filter((t) => verboten.has(t));
		assert.deepEqual(
			treffer, [],
			`AC-3 FAIL: das Legenden-Markup fuehrt feste Kuerzel/Labels (${treffer.join(', ')}) ` +
				`— das ist die zweite Liste im Frontend, die der Waechter ` +
				`officialAlertLegend.test.ts:395-415 fuer die Warnungs-Legende bereits verbietet.`
		);
	});
});

describe('AC-4: der Guard haengt an den Daten, nicht am Kontext', () => {
	test('die Legende steht unter einer Bedingung ueber ihrer eigenen Quelle', () => {
		const legende = dieLegende();
		const wirksam = legende.bed.filter((b) => !b.negiert);
		assert.ok(
			wirksam.length > 0,
			'AC-4 FAIL: das Legenden-Markup steht in keinem {#if}. Ohne Zeilen erschiene ' +
				'ein leeres Geruest statt gar nichts.'
		);
		const kontextGuard = legende.bed.find((b) => /\bcontext\b/.test(b.quelle));
		assert.equal(
			kontextGuard, undefined,
			`AC-4 FAIL: die Legende haengt an einer Kontext-Bedingung (${kontextGuard?.quelle}).`
		);
		const inhalt = geleseneNamen(legende.knoten);
		assert.ok(
			wirksam.some((b) => [...geleseneNamen(b.test)].some((name) => inhalt.has(name))),
			`AC-4 FAIL: die Bedingung prueft etwas anderes, als die Legende anzeigt ` +
				`(Bedingungen ${JSON.stringify(wirksam.map((b) => b.quelle))}).`
		);
	});

	test('die Bedingung wertet bei leerer Legende WIRKLICH falsch aus', () => {
		const legende = dieLegende();
		assert.ok(legende.bed.length > 0, 'AC-4 FAIL: keine Bedingung ueber der Legende.');
		const ausdruck = legende.bed
			.map((b) => (b.negiert ? `!(${b.quelle})` : `(${b.quelle})`))
			.join(' && ');
		const gebunden = [...geleseneNamen(legende.bed[0].test)];

		/** Wertet die ECHTE Bedingung aus. Der Name, unter dem die Zeilen reisen,
		 *  wird aus der Bedingung selbst gelesen — nicht hier festgelegt. */
		function auswerten(eintraege: Eintrag[]): unknown {
			const umgebung: Knoten = {};
			for (const name of gebunden) umgebung[name] = { eintraege, unaufloesbar: [] };
			// Die Bedingung darf sowohl `legende.eintraege.length` als auch einen
			// direkt uebergebenen Zeilen-Namen pruefen — beide Formen werden bedient.
			for (const name of gebunden) if (/eintraege|zeilen|rows/i.test(name)) umgebung[name] = eintraege;
			try {
				return new Function('u', `with (u) { return ${ausdruck}; }`)(umgebung);
			} catch (e) {
				return assert.fail(
					`AC-4 FAIL: die Bedingung \`${ausdruck}\` laesst sich nicht gegen die Zeilen ` +
						`der Legende ausfuehren: ${(e as Error).message}.`
				);
			}
		}

		assert.ok(
			!auswerten([]),
			`AC-4 FAIL: die Bedingung \`${ausdruck}\` ist bei LEERER Legende WAHR — der Block ` +
				`zeigte dann ein leeres Geruest statt gar nichts.`
		);
		// F004: eine Reihe von Groessen, nicht zwei Punkte — `=== 1` und obere
		// Schranken bestehen sonst zufaellig.
		const echteAnzahl = gerendertRoute().reduce(
			(n, id) => n + (tripKuerzelById()[id] ?? []).length, 0
		);
		for (const anzahl of [...new Set([1, 2, 3, 4, 6, echteAnzahl, echteAnzahl * 2])]) {
			assert.ok(
				auswerten(probeEintraege(anzahl)),
				`AC-4 FAIL: die Bedingung \`${ausdruck}\` ist bei ${anzahl} Zeilen FALSCH.`
			);
		}
		for (const anzahl of [1, echteAnzahl]) {
			assert.equal(
				Boolean(auswerten(probeEintraege(anzahl, 1))),
				Boolean(auswerten(probeEintraege(anzahl, 0))),
				`AC-4 FAIL: die Bedingung haengt bei ${anzahl} Zeilen am INHALT der Zeilen.`
			);
		}
	});
});

// ═══════════════════════════════════════════════════════════════════════════
// (C) VERDRAHTUNGSSCHICHT — der ECHTE Aufruf, gegen die Regel der Marken
//
// Die Erwartung kommt hier NICHT mehr aus den Katalogen (das war der Fehler,
// den der externe Validator aufgedeckt hat: Test und Pruefling teilten die
// Quelle). Sie kommt aus der ANZEIGE-REGEL der Marken-Komponente: eine Marke
// erscheint genau dann, wenn die Zeile eine Bedeutung hat UND ein Kuerzel
// (`{#if m}` … `{#if kurzform && kurzform.length}`, WeatherV2Reihenfolge).
// Gegen genau diese Regel wird der echte Aufruf gemessen.
// ═══════════════════════════════════════════════════════════════════════════

/** Der `buildKuerzelLegende(...)`-Aufruf der Komponente, aus dem AST. */
function aufrufKnoten(): Knoten {
	let treffer: Knoten | null = null;
	gehe(AST.instance?.content?.body, (n) => {
		if (treffer) return;
		if (n.type === 'CallExpression' && n.callee?.name === 'buildKuerzelLegende') treffer = n;
	});
	assert.ok(
		treffer,
		'FAIL: in WeatherV2Reihenfolge.svelte gibt es keinen `buildKuerzelLegende(...)`-Aufruf. ' +
			'Ohne ihn kann dieser Test die echte Verdrahtung nicht pruefen.'
	);
	return treffer!;
}

/** Marken, die die Komponente nach ihrer eigenen Regel rendern wuerde. */
function markenNachAnzeigeRegel(
	ids: string[], kuerzelById: Record<string, string[]>, metricById: Record<string, Knoten>
): string[] {
	const marken: string[] = [];
	for (const id of [...new Set(ids)]) {
		if (!metricById[id]) continue;                 // `{#if m}` — sonst nur die rohe Id
		for (const k of kuerzelById[id] ?? []) marken.push(k); // `{#if kurzform && kurzform.length}`
	}
	return marken.sort();
}

describe('AC-1: der echte Aufruf erklaert GENAU die Marken seines Blocks', () => {
	for (const [flaeche, daten] of [
		['Trip', () => {
			const kuerzelById = tripKuerzelById();
			const metricById = tripMetricById();
			const primary = gerendertRoute(SECHS);
			const off = Object.keys(metricById).filter((id) => !primary.includes(id)).slice(0, 3);
			return { kuerzelById, metricById, primary, off };
		}],
		['Vergleich', () => {
			const { kuerzelById, metricById } = vergleichPaar();
			const alle = gerendertVergleich();
			return { kuerzelById, metricById, primary: alle.slice(0, -2), off: alle.slice(-2) };
		}]
	] as const) {
		test(`${flaeche}: Marken-Menge == Legenden-Menge`, async () => {
			const { kuerzelById, metricById, primary, off } = daten();
			const quelltext = QUELLE.slice(aufrufKnoten().start, aufrufKnoten().end);
			const bauen = await ableitung();
			const umgebung = {
				primaryColumns: primary, offColumns: off, kuerzelById, metricById,
				buildKuerzelLegende: bauen
			};
			let ergebnis: Knoten;
			try {
				ergebnis = new Function('u', `with (u) { return ${quelltext}; }`)(umgebung);
			} catch (e) {
				return assert.fail(
					`FAIL: der echte Aufruf \`${quelltext}\` laeuft nicht gegen die Props der ` +
						`Marken-Komponente: ${(e as Error).message}.`
				);
			}

			const erwartet = markenNachAnzeigeRegel([...primary, ...off], kuerzelById, metricById);
			assert.ok(erwartet.length > 2, `Messgrundlage weg: nur ${erwartet.length} Marken.`);
			assert.deepEqual(
				ergebnis.eintraege.map((e: Eintrag) => e.kuerzel).sort(), erwartet,
				`AC-1 FAIL (${flaeche}): die Legende erklaert nicht genau die Marken dieses ` +
					`Blocks. Fehlende Eintraege heissen: der Nutzer sieht ein Zeichen, das ` +
					`nirgends erklaert wird — genau der Staging-Befund (Trip: R/PR/G aus dem ` +
					`Ausblick-Block; Vergleich: PR/TF/TH/VS/W/WD aus Stundenverlauf und Ausblick).`
			);
			assert.deepEqual(
				ergebnis.unaufloesbar, [],
				`AC-1 FAIL (${flaeche}): unaufloesbare Groessen: ` +
					`${JSON.stringify(ergebnis.unaufloesbar)}.`
			);
		});
	}
});

