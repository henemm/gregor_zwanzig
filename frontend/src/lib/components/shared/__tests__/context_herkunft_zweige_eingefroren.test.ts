// Ratsche fuer Issue #2276 Scheibe S6a (Epic #2345) — AC-2 und AC-3.
// Spec: docs/specs/modules/rework_2276_s6a_totcode_und_ratsche.md
//
// ZWECK
// -----
// Friert die Zahl UND die Fundorte der `context ===`/`context !==`-
// Verzweigungen unter `frontend/src/lib/components/shared/` als benannte
// `Datei:Zeile`-Liste ein. Erst damit laesst sich in S6b–S6f nachweisen, dass
// eine HERKUNFT-Verzweigung wirklich ENTFERNT statt nur verschoben wurde —
// eine bloße Zahl wuerde ein Verschieben nicht von einem Entfernen
// unterscheiden.
//
// KEIN VERZEICHNIS-SCAN FUER DIE SOLL-SEITE. Die Soll-Liste unten ist
// eingefrorene Literal-Daten. Wuerde der Waechter seine Soll-Menge zur
// Laufzeit selbst aus dem Verzeichnis herleiten, waere er vakuum-gruen: ein
// versehentliches Leeren der Ist-Liste wuerde ihn nicht scheitern lassen
// (bekanntes Muster, Memory
// `ratsche_leeren_macht_den_abhaengigen_test_vakuum_gruen`). Gemessen wird
// deshalb Soll (Literal) gegen Ist (echter Zaehlbefehl) — in BEIDEN
// Richtungen.
//
// TDD RED (Stand `73f504c9`)
// -------------------------
// Beim Stand vor S6a liefert der Zaehlbefehl 69 Fundstellen. Die eingefrorene
// Soll-Liste hat 68 Eintraege: `WeatherMetricsTab.svelte:577` fehlt darin
// absichtlich, weil AC-1 dieser Scheibe genau diese TOTE Bedingung entfernt
// (`(context === 'vergleich' || context === 'route')` ist fuer beide Werte des
// Union-Typs wahr). Der Test ist deshalb VOR der Implementierung ROT mit
// „Ist-Eintrag zusaetzlich: WeatherMetricsTab.svelte:577" und wird GRUEN,
// sobald der Rueckbau erfolgt ist.
//
// 🔴 VERTRAG AN DIE IMPLEMENTIERUNG (S6a, /50): Die Kommentar-Bereinigung der
// sieben `buildHubPutPayload`-Nennungen ist eine ERSETZUNG AN ORT UND STELLE,
// NIEMALS ein Loeschen von Zeilen. Dasselbe gilt fuer den Kommentarblock
// oberhalb der toten Bedingung in `WeatherMetricsTab.svelte` und fuer die
// Ersetzung der toten Bedingung selbst (eine Zeile -> eine Zeile). Grund:
// unterhalb dieser Stellen liegen weitere eingefrorene Fundstellen
// (`WeatherMetricsTab.svelte:589/602/1273/1323`,
// `weather-metrics-tab/weatherMetricsCompareSave.ts:534`,
// `versandVergleichSpeicherung.ts:221`,
// `corridor-editor/wertebereicheVergleichSpeicherung.ts:200`), deren
// Zeilennummern sonst verrutschen. Wird dieser Waechter waehrend `/50` rot:
// die Zeilenzahl der bearbeiteten Datei wiederherstellen — NICHT die
// eingefrorene Liste nachziehen.
//
// Ausfuehrung:
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types --test \
//     src/lib/components/shared/__tests__/context_herkunft_zweige_eingefroren.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { execSync } from 'node:child_process';
import { existsSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

/** Wurzel der Messflaeche — relativ zur EIGENEN Testdatei aufgeloest, nie
 *  ueber einen festen Hauptrepo-Pfad (sonst falsches Gruen aus dem Worktree). */
const SHARED = join(dirname(fileURLToPath(import.meta.url)), '..');

/** Eingefrorener Zaehlbefehl aus der Spec, Abschnitt „Eingefrorener
 *  Zaehlbefehl" — wortgleich. Wird mit `SHARED` als cwd ausgefuehrt. */
const ZAEHLBEFEHL =
	`grep -rn 'context ===\\|context !==' . --include='*.svelte' --include='*.ts'` +
	` | grep -v __tests__ | grep -vE ':\\s*(\\*|//|/\\*)'`;

/**
 * Eingefrorene Soll-Liste (67 Fundstellen) — Zielzustand NACH dem
 * Totcode-Rueckbau von S6a UND dem Guard-Rueckbau von S6b. Entspricht dem
 * Anhang der S6a-Spec (69 Fundstellen, Stand `73f504c9`) MINUS
 * `WeatherMetricsTab.svelte:577` (tote Bedingung, entfaellt per S6a AC-1)
 * MINUS `WeatherMetricsTab.svelte:1273` (Redundanz, entfaellt per S6b AC-4/AC-5,
 * Spec `docs/specs/modules/rework_2276_s6b_wetter_metriken.md`). Die
 * Kategorien HERKUNFT/FACHLICH/DARSTELLUNG stehen im Spec-Anhang, nicht hier —
 * diese Ratsche misst Fundorte, nicht Absichten.
 *
 * TDD RED (S6b): solange `:1273` noch `context !== 'vergleich' || !wiz ||
 * !vergleichSpeicherung` lautet, meldet der Mengenvergleich
 * „zusaetzlich: WeatherMetricsTab.svelte:1273" — das ist der rote Ausgangs-
 * zustand dieser Scheibe. Gruen wird er mit der zeilentreuen Verkuerzung auf
 * `if (!vergleichSpeicherung) return;`.
 *
 * 🔴 ZEILENZAHL-VERTRAG an S6b /50: `WeatherMetricsTab.svelte:1323` steht
 * UNTERHALB des Instanz-Skripts (`</script>` bei 1282). Jede im Skript
 * HINZUGEFUEGTE Zeile — auch die zwei neuen Wertprop-Adapter — verschiebt
 * diesen eingefrorenen Eintrag. Wird der Waechter deshalb rot: die Zeilenzahl
 * der bearbeiteten Datei wiederherstellen (Ersetzung an Ort und Stelle,
 * vorhandenen Kommentarumfang mitnutzen) — NICHT die eingefrorene Liste
 * nachziehen. Genau EIN Eintrag (`:1273`) darf in dieser Scheibe fallen.
 */
const EINGEFROREN: readonly string[] = [
	'AlarmeTab.svelte:171',
	'AlarmeTab.svelte:174',
	'AlarmeTab.svelte:186',
	'AlarmeTab.svelte:199',
	'AlarmeTab.svelte:216',
	'AlarmeTab.svelte:221',
	'AlarmeTab.svelte:243',
	'AlarmeTab.svelte:253',
	'AlarmeTab.svelte:280',
	'AlarmeTab.svelte:285',
	'AlarmeTab.svelte:345',
	'AlarmeTab.svelte:367',
	'AlarmeTab.svelte:379',
	'AlarmeTab.svelte:424',
	'AlarmeTab.svelte:443',
	'AlarmeTab.svelte:459',
	'AlarmeTab.svelte:467',
	'AlarmeTab.svelte:482',
	'VersandTab.svelte:284',
	'VersandTab.svelte:294',
	'VersandTab.svelte:330',
	'versandVergleichSpeicherung.ts:221',
	'WeatherMetricsTab.svelte:545',
	'WeatherMetricsTab.svelte:560',
	'WeatherMetricsTab.svelte:589',
	'WeatherMetricsTab.svelte:602',
	'WeatherMetricsTab.svelte:1323',
	'versand-tab/vtBriefingChannelsText.ts:21',
	'versand-tab/vtBriefingChannelsText.ts:26',
	'corridor-editor/CorridorEditorMobile.svelte:70',
	'corridor-editor/CorridorEditorMobile.svelte:91',
	'corridor-editor/CorridorEditorMobile.svelte:96',
	'corridor-editor/CorridorEditorMobile.svelte:98',
	'corridor-editor/CorridorEditorMobile.svelte:126',
	'corridor-editor/CorridorEditorMobile.svelte:151',
	'corridor-editor/CorridorEditorMobile.svelte:207',
	'corridor-editor/CorridorEditorMobile.svelte:234',
	'corridor-editor/CorridorEditorMobile.svelte:297',
	'corridor-editor/CorridorEditorMobile.svelte:310',
	'corridor-editor/CorridorEditorMobile.svelte:313',
	'corridor-editor/CorridorEditorMobile.svelte:318',
	'corridor-editor/CorridorEditorMobile.svelte:330',
	'corridor-editor/CorridorEditorMobile.svelte:451',
	'corridor-editor/CorridorEditor.svelte:57',
	'corridor-editor/CorridorEditor.svelte:79',
	'corridor-editor/CorridorEditor.svelte:89',
	'corridor-editor/CorridorEditor.svelte:95',
	'corridor-editor/CorridorEditor.svelte:138',
	'corridor-editor/CorridorEditor.svelte:170',
	'corridor-editor/CorridorEditor.svelte:240',
	'corridor-editor/CorridorEditor.svelte:268',
	'corridor-editor/CorridorEditor.svelte:302',
	'corridor-editor/CorridorEditor.svelte:315',
	'corridor-editor/CorridorEditor.svelte:318',
	'corridor-editor/CorridorEditor.svelte:324',
	'corridor-editor/CorridorEditor.svelte:345',
	'corridor-editor/CorridorEditor.svelte:474',
	'corridor-editor/corridorEditorState.ts:297',
	'versand-tab/VTSchedulePlan.svelte:55',
	'versand-tab/VTSchedulePlan.svelte:83',
	'alarme-tab/alarmeTabSections.ts:27',
	'alarme-tab/alarmeTabSections.ts:38',
	'alarme-tab/alarmeTabSections.ts:42',
	'corridor-editor/wertebereicheVergleichSpeicherung.ts:200',
	'weather-metrics-tab/weatherMetricsTabSections.ts:72',
	'weather-metrics-tab/weatherMetricsTabSections.ts:73',
	'weather-metrics-tab/weatherMetricsCompareSave.ts:534',
];

/** Erwartete Laenge als zweite, unabhaengige Schranke gegen ein
 *  versehentliches Kuerzen des Literals oben. */
const EINGEFROREN_SOLL_ANZAHL = 67;

/** Reines Mengen-Delta in BEIDEN Richtungen. Bewusst als eigene Funktion, weil
 *  AC-3 verlangt, dass ein FEHLENDER Soll-Eintrag den Waechter genauso rot
 *  macht wie ein ZUSAETZLICHER Ist-Eintrag — eine Einbahn-Pruefung
 *  („jeder Ist-Eintrag steht im Soll") waere blind gegen das Leeren der
 *  Ist-Liste. */
export function vergleicheZweigListen(
	soll: readonly string[],
	ist: readonly string[]
): { fehlt: string[]; zusaetzlich: string[] } {
	const sollMenge = new Set(soll);
	const istMenge = new Set(ist);
	return {
		fehlt: soll.filter((e) => !istMenge.has(e)),
		zusaetzlich: ist.filter((e) => !sollMenge.has(e))
	};
}

/** Fuehrt den eingefrorenen Zaehlbefehl aus und normalisiert auf
 *  `Datei:Zeile`. Bricht ab, wenn eine Ausgabezeile nicht dem erwarteten
 *  `grep -rn`-Format entspricht (Format-Drift wuerde sonst als „alles fehlt"
 *  erscheinen). */
function messeIstListe(): string[] {
	let ausgabe = '';
	try {
		ausgabe = execSync(ZAEHLBEFEHL, {
			cwd: SHARED,
			encoding: 'utf-8',
			shell: '/bin/bash'
		});
	} catch (e) {
		// grep endet mit 1, wenn die Pipeline leer bleibt — dann bleibt `ausgabe`
		// leer und der Mengenvergleich unten schlaegt mit „alles fehlt" fehl.
		ausgabe = (e as { stdout?: string }).stdout ?? '';
	}
	return ausgabe
		.split('\n')
		.filter((z) => z.trim() !== '')
		.map((z) => {
			const m = /^\.\/(.+?):(\d+):/.exec(z);
			assert.ok(m, `Zeile passt nicht zum grep -rn-Format: ${JSON.stringify(z)}`);
			return `${m[1]}:${m[2]}`;
		});
}

describe('AC-2: eingefrorene HERKUNFT-Zweig-Liste deckt sich mit dem Ist-Stand', () => {
	test('Messflaeche ist ueberhaupt erreichbar (Schutz gegen falsches cwd)', () => {
		assert.ok(
			existsSync(join(SHARED, 'AlarmeTab.svelte')),
			`SHARED zeigt nicht auf frontend/src/lib/components/shared (aufgeloest: ${SHARED})`
		);
	});

	test('die eingefrorene Soll-Liste ist unversehrt (67 Eintraege, keine Duplikate)', () => {
		assert.strictEqual(
			EINGEFROREN.length,
			EINGEFROREN_SOLL_ANZAHL,
			'EINGEFROREN wurde gekuerzt oder erweitert, ohne EINGEFROREN_SOLL_ANZAHL nachzufuehren'
		);
		assert.strictEqual(
			new Set(EINGEFROREN).size,
			EINGEFROREN.length,
			'EINGEFROREN enthaelt Duplikate — der Mengenvergleich waere verfaelscht'
		);
	});

	test('Soll und Ist sind mengengleich — kein Eintrag fehlt, keiner kommt hinzu', () => {
		const ist = messeIstListe();
		const { fehlt, zusaetzlich } = vergleicheZweigListen(EINGEFROREN, ist);
		const alsListe = (e: string[]) => (e.length === 0 ? '—' : e.join(', '));
		assert.deepStrictEqual(
			{ fehlt, zusaetzlich },
			{ fehlt: [], zusaetzlich: [] },
			'HERKUNFT-Zweig-Ratsche verletzt.\n' +
				`  Soll (eingefroren): ${EINGEFROREN.length}\n` +
				`  Ist (Zaehlbefehl):  ${ist.length}\n` +
				`  Soll fehlt im Ist (Zeile verschoben oder entfernt): ${alsListe(fehlt)}\n` +
				`  Ist nicht im Soll (neue oder verschobene Verzweigung): ${alsListe(zusaetzlich)}\n` +
				'  Eine ENTFERNTE Verzweigung wird bewusst nachgetragen (Liste kuerzen);\n' +
				'  eine VERSCHOBENE Zeilennummer ist ein Befund, kein Nachtrag.'
		);
	});
});

describe('AC-3: Rueckdreh-Gegenprobe — ein fehlender Soll-Eintrag macht rot', () => {
	// Diese beiden Tests sind bereits in der RED-Phase gruen. Sie pruefen nicht
	// das Feature, sondern die Schutzwirkung der Ratsche selbst: dass der
	// Mengenvergleich BEIDE Richtungen meldet. Ohne sie koennte ein spaeterer
	// Umbau die `fehlt`-Richtung stillschweigend fallen lassen — und genau dann
	// wuerde ein Leeren der Ist-Liste unbemerkt durchgehen.
	// Der eigentliche AC-3-Nachweis ist der Mutations-Lauf im Adversary-Schritt:
	//   1. eine beliebige Zeile aus `EINGEFROREN` oben entfernen,
	//   2. NUR diese Datei laufen lassen,
	//   3. erwartet: genau dieser Waechter rot, kein anderer.

	test('ein aus dem Soll entfernter Eintrag erscheint als „zusaetzlich" im Ist', () => {
		const ist = [...EINGEFROREN];
		const sollGekuerzt = EINGEFROREN.slice(1);
		const { fehlt, zusaetzlich } = vergleicheZweigListen(sollGekuerzt, ist);
		assert.deepStrictEqual(fehlt, []);
		assert.deepStrictEqual(
			zusaetzlich,
			[EINGEFROREN[0]],
			'Das Entfernen einer Zeile aus der eingefrorenen Liste muss den Waechter rot machen'
		);
	});

	test('eine geleerte Ist-Liste meldet alle Soll-Eintraege als fehlend (kein Vakuum-Gruen)', () => {
		const { fehlt, zusaetzlich } = vergleicheZweigListen(EINGEFROREN, []);
		assert.strictEqual(fehlt.length, EINGEFROREN.length);
		assert.deepStrictEqual(zusaetzlich, []);
	});
});
