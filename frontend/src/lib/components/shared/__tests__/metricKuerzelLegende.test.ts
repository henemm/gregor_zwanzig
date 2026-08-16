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
import { existsSync, readFileSync } from 'node:fs';
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
) => Eintrag[]> {
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
	return (await ableitung())(ids, kuerzelById, metricById);
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
// (B) STRUKTURSCHICHT — echter Svelte-5-AST von WeatherMetricsTab.svelte
// ═══════════════════════════════════════════════════════════════════════════

const QUELLE = readFileSync(TAB, 'utf-8');
const AST: Knoten = parse(QUELLE, { modern: true });

interface Bedingung { quelle: string; test: Knoten; negiert: boolean }

/** Tiefensuche mit Elternkette UND den WIRKSAMEN {#if}-Bedingungen: im
 *  {:else}-Zweig gilt die Bedingung NEGIERT, nicht etwa gar nicht. Genau
 *  daran haengt die Kontext-Zuordnung — der Reiter ist ein einziges
 *  `{#if context === 'vergleich'} … {:else} … {/if}` (:1228/:1422/:1824). */
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

function legendenElemente(): { knoten: Knoten; eltern: Knoten[]; bed: Bedingung[] }[] {
	const treffer: { knoten: Knoten; eltern: Knoten[]; bed: Bedingung[] }[] = [];
	gehe(AST.fragment, (n, eltern, bed) => {
		if (n.type !== 'RegularElement' && n.type !== 'Component') return;
		if (attributWert(n, 'data-testid') === LEGENDE_TESTID) treffer.push({ knoten: n, eltern, bed });
	});
	return treffer;
}

/** Die eine Legende — mit sprechendem Fehlschlag statt Absturz, solange es sie nicht gibt. */
function dieLegende() {
	const treffer = legendenElemente();
	assert.equal(
		treffer.length, 1,
		`RED: es muss GENAU EIN Element mit data-testid="${LEGENDE_TESTID}" in ` +
			`WeatherMetricsTab.svelte geben (gefunden: ${treffer.length}). Null bedeutet ` +
			`keine Legende, mehr als eins bedeutet eine kontexteigene Kopie statt eines ` +
			`geteilten Bausteins (AC-5).`
	);
	return treffer[0];
}

const istVergleich = (bed: Bedingung[]) =>
	bed.some((b) => !b.negiert && /context\s*===\s*['"]vergleich['"]/.test(b.quelle));
const istRoute = (bed: Bedingung[]) =>
	bed.some((b) => b.negiert && /context\s*===\s*['"]vergleich['"]/.test(b.quelle));

/** Alle `{@render <name>(…)}`-Stellen samt wirksamen Bedingungen. */
function renderStellen(name: string): { knoten: Knoten; bed: Bedingung[] }[] {
	const stellen: { knoten: Knoten; bed: Bedingung[] }[] = [];
	gehe(AST.fragment, (n, _e, bed) => {
		if (n.type === 'RenderTag' && QUELLE.slice(n.start, n.end).includes(name + '('))
			stellen.push({ knoten: n, bed });
	});
	return stellen;
}

/** Namen, die eine Aufrufstelle erreicht: ihre Argumente plus — einen Schritt
 *  tief — die Herleitung der dort genannten Bezeichner (Muster
 *  weather_metric_kuerzel_marken.test.ts::kuerzelQuelle). */
function erreichteNamen(stelle: Knoten): Set<string> {
	const direkt = geleseneNamen(stelle);
	const alle = new Set(direkt);
	gehe(AST.instance?.content?.body, (n) => {
		if (n.type !== 'VariableDeclarator') return;
		const name = n.id?.type === 'Identifier' ? n.id.name : null;
		if (!name || !direkt.has(name)) return;
		for (const g of geleseneNamen(n.init)) alle.add(g);
	});
	return alle;
}

describe('AC-5: ein Snippet, an beiden Reihenfolge-Bloecken', () => {
	test('die Legende steht genau einmal, in einem Snippet', () => {
		const legende = dieLegende();
		const snippet = legende.eltern.filter((e) => e.type === 'SnippetBlock').pop();
		assert.ok(
			snippet,
			`AC-5 FAIL: das Legenden-Markup liegt in keinem {#snippet} — dann kann es ` +
				`nicht an zwei Stellen wiederverwendet werden, ohne kopiert zu werden ` +
				`(Vorbild: officialAlertsToggle, WeatherMetricsTab.svelte:1189-1226).`
		);
	});

	test('dasselbe Snippet wird in BEIDEN Kontexten gerendert', () => {
		const legende = dieLegende();
		const snippet = legende.eltern.filter((e) => e.type === 'SnippetBlock').pop();
		assert.ok(snippet, 'AC-5 FAIL: kein Snippet — s. Test darueber.');
		const name = String(snippet!.expression?.name ?? '');
		const stellen = renderStellen(name);
		assert.ok(
			stellen.some((s) => istVergleich(s.bed)),
			`AC-5 FAIL: \`${name}\` wird im Ortsvergleich-Zweig nicht gerendert. ` +
				`Gefundene Aufrufstellen: ${stellen.length}.`
		);
		assert.ok(
			stellen.some((s) => istRoute(s.bed)),
			`AC-5 FAIL: \`${name}\` wird im Trip-Zweig ({:else} von ` +
				`\`context === 'vergleich'\`) nicht gerendert. Aufrufstellen: ${stellen.length}.`
		);
	});

	test('beide Aufrufstellen haengen am Reihenfolge-Abschnitt', () => {
		const legende = dieLegende();
		const snippet = legende.eltern.filter((e) => e.type === 'SnippetBlock').pop();
		assert.ok(snippet, 'AC-5 FAIL: kein Snippet — s. Test darueber.');
		const name = String(snippet!.expression?.name ?? '');
		for (const [flaeche, waehle] of [['Ortsvergleich', istVergleich], ['Trip', istRoute]] as const) {
			const stelle = renderStellen(name).find((s) => waehle(s.bed));
			assert.ok(stelle, `AC-5 FAIL: keine Aufrufstelle im ${flaeche}-Zweig.`);
			assert.ok(
				stelle!.bed.some((b) => !b.negiert && /sections\.includes\(\s*'reihenfolge'\s*\)/.test(b.quelle)),
				`AC-5 FAIL: die ${flaeche}-Aufrufstelle haengt nicht am Reihenfolge-Abschnitt. ` +
					`Nur dieser Block zeigt ALLE Groessen inklusive der abgewaehlten und ist ` +
					`der einzige Ort, den beide Kontexte teilen. Bedingungen: ` +
					`${JSON.stringify(stelle!.bed.map((b) => (b.negiert ? '!' : '') + b.quelle))}`
			);
		}
	});
});

describe('AC-3: die Legende speist sich aus der Marken-Quelle, nicht aus einer zweiten Liste', () => {
	const TRIP_QUELLEN = ['metricSymbols', 'smsSymbols', 'sms_symbols'];
	const TRIP_BEDEUTUNG = ['metricById', 'catalog'];
	const VERGLEICH_QUELLEN = ['compareKuerzelById', 'compareCatalog'];
	const VERGLEICH_BEDEUTUNG = ['compareMetricById', 'compareCatalog'];

	test('Trip-Aufrufstelle: Kuerzel UND Bedeutung aus den Trip-Katalogen', () => {
		const legende = dieLegende();
		const snippet = legende.eltern.filter((e) => e.type === 'SnippetBlock').pop();
		assert.ok(snippet, 'AC-3 FAIL: kein Legenden-Snippet.');
		const stelle = renderStellen(String(snippet!.expression?.name ?? '')).find((s) => istRoute(s.bed));
		assert.ok(stelle, 'AC-3 FAIL: keine Trip-Aufrufstelle.');
		const erreicht = erreichteNamen(stelle!.knoten);
		assert.ok(
			TRIP_QUELLEN.some((q) => erreicht.has(q)),
			`AC-3 FAIL: die Trip-Legende erreicht keine der Kuerzel-Quellen ` +
				`${TRIP_QUELLEN.join('/')} — sie zeigte dann andere Kuerzel als die Marken ` +
				`daneben. Erreichbar: ${JSON.stringify([...erreicht].sort())}`
		);
		assert.ok(
			TRIP_BEDEUTUNG.some((q) => erreicht.has(q)),
			`AC-3 FAIL: die Trip-Legende erreicht weder \`metricById\` noch \`catalog\` — ` +
				`ohne die Menge der GERENDERTEN Groessen bleibt nur der rohe Kuerzel-Katalog ` +
				`als Quelle, und der bringt \`CP\` ohne Bedeutung mit (Messung M1). ` +
				`Erreichbar: ${JSON.stringify([...erreicht].sort())}`
		);
		const fremd = VERGLEICH_QUELLEN.filter((q) => erreicht.has(q));
		assert.deepEqual(fremd, [], `AC-3 FAIL: die Trip-Legende erreicht Vergleichs-Quellen (${fremd.join(', ')}).`);
	});

	test('Vergleichs-Aufrufstelle: Kuerzel UND Bedeutung aus den Compare-Katalogen', () => {
		const legende = dieLegende();
		const snippet = legende.eltern.filter((e) => e.type === 'SnippetBlock').pop();
		assert.ok(snippet, 'AC-3 FAIL: kein Legenden-Snippet.');
		const stelle = renderStellen(String(snippet!.expression?.name ?? '')).find((s) => istVergleich(s.bed));
		assert.ok(stelle, 'AC-3 FAIL: keine Vergleichs-Aufrufstelle.');
		const erreicht = erreichteNamen(stelle!.knoten);
		for (const gruppe of [VERGLEICH_QUELLEN, VERGLEICH_BEDEUTUNG]) {
			assert.ok(
				gruppe.some((q) => erreicht.has(q)),
				`AC-3 FAIL: die Vergleichs-Legende erreicht keine von ${gruppe.join('/')}. ` +
					`Erreichbar: ${JSON.stringify([...erreicht].sort())}`
			);
		}
		const fremd = ['metricSymbols', 'smsSymbols'].filter((q) => erreicht.has(q));
		assert.deepEqual(
			fremd, [],
			`AC-3 FAIL: die Vergleichs-Legende erreicht die TRIP-Quelle (${fremd.join(', ')}). ` +
				`Trip und Vergleich senden aus verschiedenen Tabellen — die Legende zeigte ` +
				`Kuerzel, die der Vergleich nie sendet.`
		);
	});

	test('im Legenden-Markup steht kein Kuerzel und kein Label als fester Text', () => {
		const legende = dieLegende();
		const snippet = legende.eltern.filter((e) => e.type === 'SnippetBlock').pop();
		assert.ok(snippet, 'AC-3 FAIL: kein Legenden-Snippet.');
		const verboten = new Set<string>([
			...Object.values(tripKuerzelById()).flat(),
			...Object.values(tripMetricById()).map((m) => String(m.label)),
			...SECHS
		]);
		const treffer = festeTexte(snippet).filter((t) => verboten.has(t));
		assert.deepEqual(
			treffer, [],
			`AC-3 FAIL: das Legenden-Snippet fuehrt feste Kuerzel/Labels ` +
				`(${treffer.join(', ')}) — das ist die zweite Liste im Frontend, die der ` +
				`Waechter officialAlertLegend.test.ts:395-415 fuer die Warnungs-Legende ` +
				`bereits verbietet. Kuerzel und Bedeutung muessen aus den Katalogen kommen.`
		);
	});
});

describe('AC-4: der Guard haengt an den Daten, nicht am Kontext', () => {
	test('die Legende steht unter einer Bedingung ueber ihrer eigenen Quelle', () => {
		const legende = dieLegende();
		const wirksam = legende.bed.filter((b) => !b.negiert);
		assert.ok(
			wirksam.length > 0,
			'AC-4 FAIL: das Legenden-Markup steht in keinem {#if}. Ohne Katalog erschiene ' +
				'eine leere Legende statt gar keiner (Vorbild: `{#if smsSymbols}`, :1210).'
		);
		const kontextGuard = legende.bed.find((b) => /\bcontext\b/.test(b.quelle));
		assert.equal(
			kontextGuard, undefined,
			`AC-4/AC-5 FAIL: die Legende haengt an einer Kontext-Bedingung ` +
				`(${kontextGuard?.quelle}) — sie muss in BEIDEN Flaechen erscheinen und nur ` +
				`an der geladenen Quelle haengen.`
		);
		const inhalt = geleseneNamen(legende.knoten);
		assert.ok(
			wirksam.some((b) => [...geleseneNamen(b.test)].some((name) => inhalt.has(name))),
			`AC-4 FAIL: die Bedingung prueft etwas anderes, als die Legende anzeigt ` +
				`(Bedingungen ${JSON.stringify(wirksam.map((b) => b.quelle))}, Legende liest ` +
				`${JSON.stringify([...inhalt])}). Dann kann trotz wahrer Bedingung eine leere ` +
				`Legende erscheinen.`
		);
	});

	// Adversary F003: der Test darueber prueft nur, ob die Bedingung denselben
	// NAMEN liest wie der Inhalt — nicht, ob sie auf Leere prueft. Eine
	// Tautologie wie `eintraege.length >= 0` liest denselben Namen, wird nie
	// falsch und rendert bei leerer Quelle ein leeres Geruest (Intro-Satz plus
	// leere Liste). Dieselbe Klasse wie F002: geprueft, wo der Code steht, nicht
	// wo er wirkt. Also wird die Bedingung hier AUSGEFUEHRT — mit demselben
	// Mechanismus wie Schicht C, gegen leere und nichtleere Daten.
	test('die Bedingung wertet bei leerer Legende WIRKLICH falsch aus', () => {
		const legende = dieLegende();
		const snippet = legende.eltern.filter((e) => e.type === 'SnippetBlock').pop();
		assert.ok(snippet, 'AC-4 FAIL: kein Legenden-Snippet.');
		const parameter = ((snippet!.parameters ?? []) as Knoten[])
			.map((p) => (p.type === 'Identifier' ? String(p.name) : null))
			.filter((n): n is string => Boolean(n));
		assert.ok(
			parameter.length > 0,
			'AC-4 FAIL: das Legenden-Snippet nimmt keinen benannten Parameter entgegen. ' +
				'Dann laesst sich seine Bedingung nicht gegen leere und nichtleere Daten ' +
				'ausfuehren — die Wirksamkeit des Guards bliebe ungeprueft, und genau das ' +
				'ist der Zustand, den dieser Test beendet (F003).'
		);
		assert.ok(
			legende.bed.length > 0,
			'AC-4 FAIL: ueber dem Legenden-Markup steht keine Bedingung. Bei leerer Quelle ' +
				'erschiene dann ein leeres Legenden-Geruest statt gar nichts.'
		);
		const ausdruck = legende.bed
			.map((b) => (b.negiert ? `!(${b.quelle})` : `(${b.quelle})`))
			.join(' && ');

		/** Wertet die ECHTE Bedingung aus, mit den Snippet-Parametern auf die
		 *  Probe-Daten gebunden. Ein Bezeichner, der nicht zum Legenden-Inhalt
		 *  gehoert, fliegt als ReferenceError auf statt still durchzulaufen. */
		function auswerten(eintraege: Eintrag[]): unknown {
			const umgebung = Object.fromEntries(parameter.map((name) => [name, eintraege]));
			try {
				return new Function('u', `with (u) { return ${ausdruck}; }`)(umgebung);
			} catch (e) {
				return assert.fail(
					`AC-4 FAIL: die Bedingung \`${ausdruck}\` laesst sich nicht gegen die Daten ` +
						`der Legende ausfuehren: ${(e as Error).message}. Sie haengt dann an ` +
						`etwas anderem als an dem Inhalt, den sie schuetzen soll.`
				);
			}
		}

		assert.ok(
			!auswerten([]),
			`AC-4 FAIL: die Bedingung \`${ausdruck}\` ist bei LEERER Legende WAHR. Der ` +
				`Reiter zeigte dann ohne Katalog ein leeres Geruest (Intro-Satz plus leere ` +
				`Liste) statt gar nichts. Eine namensgleiche, aber wirkungslose Bedingung ` +
				`(\`length >= 0\`) besteht die Namensprobe darueber und faellt nur hier auf.`
		);

		// F004: zwei Probepunkte (0 und 1) reichen nicht — `length === 1` traf
		// beide zufaellig und blieb ungefangen, obwohl die Legende damit im
		// Betrieb praktisch nie erschiene (eine frische Tour rendert 9 Groessen).
		// Geprueft wird deshalb eine REIHE von Groessen, ausdruecklich mit
		// * mehr als einer Zeile (faengt `=== 1`),
		// * der Zahl, die im Betrieb wirklich auftritt, und dem Doppelten davon
		//   (faengt jede obere Schranke wie `>= 1 && <= 2` oder `< 20`),
		// * einer Primzahl neben Vielfachen (faengt Rest-Bedingungen wie `% 3`).
		const echteAnzahl = gerendertRoute().reduce(
			(n, id) => n + (tripKuerzelById()[id] ?? []).length, 0
		);
		assert.ok(echteAnzahl > 2, `Messgrundlage weg: nur ${echteAnzahl} echte Legenden-Zeilen.`);
		for (const anzahl of [...new Set([1, 2, 3, 4, 6, echteAnzahl, echteAnzahl * 2])]) {
			assert.ok(
				auswerten(probeEintraege(anzahl)),
				`AC-4 FAIL: die Bedingung \`${ausdruck}\` ist bei ${anzahl} Zeilen FALSCH. ` +
					`Die Legende erschiene dann nicht, obwohl Zeilen vorliegen — eine ` +
					`Bedingung mit fester Zahl (\`=== 1\`) oder oberer Schranke faellt genau ` +
					`hier auf. Im Betrieb entstehen ${echteAnzahl} Zeilen.`
			);
		}
		// Und sie darf nicht am INHALT der Zeilen haengen, nur an ihrer Zahl:
		// eine Bedingung wie `eintraege[0].kuerzel === 'X'` bestuende sonst jede
		// Groessen-Probe, die zufaellig dieselben Daten benutzt.
		for (const anzahl of [1, echteAnzahl]) {
			assert.equal(
				Boolean(auswerten(probeEintraege(anzahl, 1))),
				Boolean(auswerten(probeEintraege(anzahl, 0))),
				`AC-4 FAIL: die Bedingung \`${ausdruck}\` haengt bei ${anzahl} Zeilen am ` +
					`INHALT der Zeilen, nicht an ihrer Zahl. Dann entscheidet ueber die ` +
					`Sichtbarkeit der Legende, WELCHE Groessen der Nutzer gewaehlt hat.`
			);
		}
	});

	// F005: die Ausfuehrungsprobe darueber ist eine STICHPROBE, und jede endliche
	// Stichprobe laesst sich umgehen — `eintraege.length && eintraege.length % 5
	// !== 0` besteht alle geprueften Groessen [0,1,2,3,4,6,9,18] und waere bei 5,
	// 10, 15 Zeilen trotzdem falsch. Ein Modulo-5-Punkt erzeugt eine
	// Modulo-7-Luecke: Wettruesten ohne Ende.
	//
	// Deshalb hier keine weitere Stichprobe, sondern eine FORM-Pruefung, die die
	// ganze Klasse schliesst. Verhalten und Form gemeinsam konvergieren: die
	// Ausfuehrungsprobe allein ist per Stichprobe umgehbar (F005), die Form
	// allein pruefte nur den Namen und nicht die Wirkung (F003).
	test('die Bedingung ist ein schlichter Leere-Test — bewusst, nicht zufaellig', () => {
		const legende = dieLegende();
		const snippet = legende.eltern.filter((e) => e.type === 'SnippetBlock').pop();
		assert.ok(snippet, 'AC-4 FAIL: kein Legenden-Snippet.');
		const parameter = ((snippet!.parameters ?? []) as Knoten[])
			.map((p) => (p.type === 'Identifier' ? String(p.name) : null))
			.filter((n): n is string => Boolean(n));
		assert.ok(parameter.length > 0, 'AC-4 FAIL: das Legenden-Snippet hat keinen benannten Parameter.');
		assert.equal(
			legende.bed.length, 1,
			`AC-4 FAIL: ueber dem Legenden-Markup stehen ${legende.bed.length} Bedingungen ` +
				`(${JSON.stringify(legende.bed.map((b) => (b.negiert ? '!' : '') + b.quelle))}). ` +
				`Erwartet ist genau eine: der Leere-Test auf die Legenden-Zeilen.`
		);
		assert.equal(legende.bed[0].negiert, false, 'AC-4 FAIL: die Legende haengt in einem {:else}-Zweig.');

		/** `<parameter>.length` — ohne Optional Chaining, ohne Index-Zugriff. */
		function istLaenge(n: Knoten | null | undefined): boolean {
			return !!n && n.type === 'MemberExpression' && !n.computed && !n.optional
				&& n.object?.type === 'Identifier' && parameter.includes(String(n.object.name))
				&& n.property?.type === 'Identifier' && n.property.name === 'length';
		}
		const istNull = (n: Knoten | null | undefined) => !!n && n.type === 'Literal' && n.value === 0;

		const test = legende.bed[0].test as Knoten;
		const schlicht =
			istLaenge(test) ||
			(test?.type === 'BinaryExpression' && (
				(['>', '!==', '!='].includes(test.operator) && istLaenge(test.left) && istNull(test.right)) ||
				(['<', '!==', '!='].includes(test.operator) && istNull(test.left) && istLaenge(test.right))
			));

		assert.ok(
			schlicht,
			`AC-4 FAIL: die Bedingung \`${legende.bed[0].quelle}\` ist kein schlichter ` +
				`Leere-Test auf ${parameter.join('/')}. Erlaubt sind genau ` +
				`\`${parameter[0]}.length\` und der Vergleich gegen 0 (\`> 0\`, \`!== 0\`) — ` +
				`nichts sonst: keine weiteren Operanden, keine andere Konstante, kein Modulo, ` +
				`kein Optional Chaining, kein zweiter Bezeichner.\n` +
				`WARUM SO STRENG: die Ausfuehrungsprobe darueber ist eine Stichprobe ueber ` +
				`einzelne Zeilenzahlen, und jede endliche Stichprobe hat Luecken — ` +
				`\`length && length % 5 !== 0\` besteht sie und waere bei 5, 10, 15 Zeilen ` +
				`trotzdem falsch (Adversary F005). Erst Form UND Verhalten zusammen schliessen ` +
				`die Klasse. Die Schlichtheit ist damit eine bewusste Invariante, kein Zufall.\n` +
				`WENN DU SIE AENDERN WILLST: nicht diesen Test aufweichen, sondern hier ` +
				`bewusst die neue Schreibweise aufnehmen und begruenden, warum sie ` +
				`ausschliesslich an der Leere haengt.`
		);
	});
});

// ═══════════════════════════════════════════════════════════════════════════
// (C) VERDRAHTUNGSSCHICHT — die ECHTE Aufrufstelle, gegen echte Kataloge
//
// Adversary F002: Schicht (A) ruft die Ableitung mit selbst sortierten
// Argumenten auf, Schicht (B) prueft nur, welche Bezeichner eine Aufrufstelle
// ERREICHT — nicht, an welcher Stelle sie stehen. Vertauscht man an der
// route-Aufrufstelle die Argumente, ist die Trip-Legende in Produktion leer,
// und beide Schichten bleiben gruen. Die Zusicherung war dort geprueft, wo der
// Code steht, nicht dort, wo er wirkt.
//
// Hier wird deshalb der Quelltext des `buildKuerzelLegende(...)`-Aufrufs aus
// dem AST gelesen und AUSGEFUEHRT — mit der echten Funktion und den echten
// Katalogen unter ihren echten Namen. Nichts daran ist nachgebaut: dreht
// jemand die Argumente, aendert sich das Ergebnis dieses Aufrufs.
// ═══════════════════════════════════════════════════════════════════════════

/** Quelltext des `buildKuerzelLegende(...)`-Aufrufs, der die Legende an DIESER
 *  Aufrufstelle speist: Renderstelle -> uebergebener Bezeichner -> dessen
 *  Deklaration -> der Aufruf darin. */
function aufrufQuelltext(waehle: (bed: Bedingung[]) => boolean, flaeche: string): string {
	const legende = dieLegende();
	const snippet = legende.eltern.filter((e) => e.type === 'SnippetBlock').pop();
	assert.ok(snippet, 'kein Legenden-Snippet.');
	const stelle = renderStellen(String(snippet!.expression?.name ?? '')).find((s) => waehle(s.bed));
	assert.ok(stelle, `keine ${flaeche}-Aufrufstelle der Legende.`);
	const uebergeben = geleseneNamen(stelle!.knoten);
	let quelltext: string | null = null;
	gehe(AST.instance?.content?.body, (n) => {
		if (n.type !== 'VariableDeclarator' || quelltext) return;
		if (n.id?.type !== 'Identifier' || !uebergeben.has(n.id.name)) return;
		gehe(n.init, (k) => {
			if (quelltext) return;
			if (k.type === 'CallExpression' && k.callee?.name === 'buildKuerzelLegende') {
				quelltext = QUELLE.slice(k.start, k.end);
			}
		});
	});
	assert.ok(
		quelltext,
		`F002 FAIL: an der ${flaeche}-Aufrufstelle laesst sich kein ` +
			`\`buildKuerzelLegende(...)\`-Aufruf finden (uebergeben: ` +
			`${JSON.stringify([...uebergeben].sort())}). Ohne ihn kann dieser Test die ` +
			`Argumentreihenfolge der echten Verdrahtung nicht pruefen.`
	);
	return quelltext!;
}

/** Fuehrt den Aufruf-Quelltext gegen echte Kataloge aus. Unbekannte Namen
 *  fliegen als ReferenceError auf — eine Legende darf sich nur aus den
 *  Quellen speisen, die auch die Marken speisen (AC-3). */
async function fuehreAufrufAus(quelltext: string, umgebung: Knoten): Promise<Eintrag[]> {
	const alle = { ...umgebung, buildKuerzelLegende: await ableitung() };
	try {
		return new Function('u', `with (u) { return ${quelltext}; }`)(alle) as Eintrag[];
	} catch (e) {
		assert.fail(
			`F002 FAIL: der echte Aufruf \`${quelltext}\` laeuft nicht gegen die ` +
				`Katalog-Quellen der Marken: ${(e as Error).message}. Bekannt sind hier ` +
				`${JSON.stringify(Object.keys(alle).sort())}.`
		);
	}
}

describe('F002: die ECHTE Aufrufstelle liefert eine richtige Legende', () => {
	test('Trip: der Aufruf aus der Komponente erklaert die gerenderten Kuerzel', async () => {
		const kuerzelById = tripKuerzelById();
		const metricById = tripMetricById();
		const aktiv = gerendertRoute(SECHS);
		const abgewaehlt = Object.keys(metricById).filter((id) => !aktiv.includes(id)).slice(0, 2);
		const erwartet = erwarteteZuordnung([...aktiv, ...abgewaehlt], kuerzelById, metricById);

		const eintraege = await fuehreAufrufAus(aufrufQuelltext(istRoute, 'Trip'), {
			// Die Namen sind die der Komponente; die Werte sind echt. `active` und
			// `off` sind beide gerendert (Aus-Gruppe, WeatherV2Reihenfolge:174-178).
			activeChannelSections: { active: aktiv, off: abgewaehlt },
			metricSymbols: kuerzelById,
			metricById,
			catalog: live().metrics,
			smsSymbols: live().sms
		});

		assert.ok(
			eintraege.length > 0,
			`F002 FAIL: die Trip-Legende ist bei voll geladenen Katalogen LEER. Genau das ` +
				`passiert, wenn an der Aufrufstelle die Argumente vertauscht sind — dem ` +
				`Nutzer fehlt dann die ganze Legende, ohne dass irgendetwas rot wird. ` +
				`Aufruf: ${aufrufQuelltext(istRoute, 'Trip')}`
		);
		assert.deepEqual(
			[...new Set(eintraege.map((e) => e.kuerzel))].sort(),
			[...erwartet.keys()].sort(),
			`F002/F001 FAIL: die echte Verdrahtung liefert nicht die Kuerzel der ` +
				`gerenderten Groessen. Zu viel heisst: die Menge haengt am vollen Katalog ` +
				`(${Object.keys(metricById).length} Groessen) statt am Reihenfolge-Block ` +
				`(${aktiv.length + abgewaehlt.length}).`
		);
		for (const e of eintraege) {
			assert.ok(
				erwartet.get(e.kuerzel)?.has(e.bedeutung),
				`F002 FAIL: "${e.kuerzel}" wird als ${JSON.stringify(e.bedeutung)} erklaert, ` +
					`der Katalog kennt ${JSON.stringify([...(erwartet.get(e.kuerzel) ?? [])])}.`
			);
		}
	});

	test('Vergleich: der Aufruf aus der Komponente erklaert die gerenderten Kuerzel', async () => {
		const { kuerzelById, metricById } = vergleichPaar();
		const aktiv = gerendertVergleich();
		const erwartet = erwarteteZuordnung(aktiv, kuerzelById, metricById);

		const eintraege = await fuehreAufrufAus(aufrufQuelltext(istVergleich, 'Vergleich'), {
			compareChannelSections: { active: aktiv, off: [] },
			compareKuerzelById: kuerzelById,
			compareMetricById: metricById,
			compareCatalog: toCompareSelectionEntries({ metrics: live().compare } as never)
		});

		assert.ok(
			eintraege.length > 0,
			'F002 FAIL: die Vergleichs-Legende ist bei geladenem Katalog LEER.'
		);
		assert.deepEqual(
			[...new Set(eintraege.map((e) => e.kuerzel))].sort(),
			[...erwartet.keys()].sort(),
			'F002/F001 FAIL: die echte Verdrahtung liefert nicht die Kuerzel der ' +
				'gerenderten Vergleichszeilen.'
		);
		// AC-2a an der echten Verdrahtung: `D` bleibt zweimal stehen.
		assert.equal(
			eintraege.filter((e) => e.kuerzel === 'D').length, 2,
			'F002/AC-2a FAIL: die echte Verdrahtung entdoppelt `D` — die Marken zeigen ' +
				'das Kuerzel an beiden Zeilen.'
		);
	});
});
