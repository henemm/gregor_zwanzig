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
// 🔴 STAND S6c (Issue #2276): der Zeilenzahl-Vertrag unten gilt fuer
// `AlarmeTab.svelte` in DIESER Scheibe NICHT — dort werden 14 Eintraege bewusst
// gestrichen und 4 auf neue Zeilennummern nachgefuehrt. Begruendung und genaue
// Auflage: Kommentar an `EINGEFROREN` weiter unten.
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
import { existsSync, readFileSync } from 'node:fs';
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
 * Eingefrorene Soll-Liste (53 Fundstellen) — Zielzustand NACH S6a (Totcode),
 * S6b (Guard-Rueckbau) UND S6c (Alarme-Flaeche auf Wertprops). Die Kategorien
 * HERKUNFT/FACHLICH/DARSTELLUNG stehen im Spec-Anhang, nicht hier — diese
 * Ratsche misst Fundorte, nicht Absichten.
 *
 * TDD RED (S6c): solange die 14 in der Schicksals-Tabelle als FAELLT markierten
 * AlarmeTab-Zweige im Quelltext stehen, meldet der Mengenvergleich sie als
 * „zusaetzlich" — das ist der rote Ausgangszustand dieser Scheibe. Gruen wird
 * er, wenn der Vergleichs-Zweig auf Wertprops steht und /50 die vier
 * verbliebenen Eintraege auf ihre NEUEN Zeilennummern nachgefuehrt hat.
 *
 * 🔴 VERTRAG AN S6c /50 — er ERSETZT den Zeilenzahl-Vertrag von S6a/S6b fuer
 * DIESE Scheibe (Spec `rework_2276_s6c_alarme.md`, Design-Entscheidung 1):
 * In `AlarmeTab.svelte` entstehen rund 24 neue Prop-Zeilen OBERHALB aller
 * eingefrorenen Eintraege. Zeilenzahl-Wiederherstellung waere hier Verrenkung,
 * nicht Sorgfalt — deshalb gilt ausnahmsweise:
 *   * die 14 FAELLT-Eintraege werden BEWUSST gestrichen (Begruendung je
 *     Eintrag in der Commit-Nachricht, im selben Commit wie der Rueckbau),
 *   * die 4 BLEIBT-Eintraege werden auf ihre neu gemessenen Zeilennummern
 *     nachgefuehrt — geprueft wird, dass der BEDINGUNGSTEXT derselbe ist
 *     (siehe Kommentar an der Liste), nicht die Position,
 *   * `alarme-tab/alarmeTabSections.ts:27/:38/:42` bleiben unberuehrt; ihre
 *     Zeilennummern duerfen sich NICHT verschieben.
 * Fuer alle Dateien AUSSERHALB von `AlarmeTab.svelte` gilt der alte Vertrag
 * unveraendert weiter: verschobene Zeilennummer = Befund, kein Nachtrag.
 */
const EINGEFROREN: readonly string[] = [
	// S6c: von 18 AlarmeTab-Eintraegen bleiben genau diese VIER (Schicksals-
	// Tabelle der Spec). Ihre Zeilennummern verschieben sich durch den Umbau —
	// /50 misst die neuen und traegt sie HIER ein (Bedingungstext woertlich
	// daneben, damit am Inhalt geprueft werden kann, nicht an der Position):
	//   :256  `context === 'vergleich'` — Ableitung `unalertableSelectedMetricNames`
	//         (FACHLICH: route liefert strukturell immer `[]`, #1435 AC-7)
	//   :514  `{#if context === 'vergleich' && unalertableSelectedMetricNames.length > 0}`
	//         (Anzeige-Zwilling der fachlichen Zusicherung aus :256)
	//   :533  `{#if context === 'vergleich'}` — Kurzstil-Schalter
	//         (DARSTELLUNG: im Trip steht derselbe Schalter im Versand-Reiter, #1260 S5)
	//   :566  `{#if context === 'vergleich'}` — Beispielwarnung
	//         (FACHLICH: Ort- statt Etappen-Subjekt, zwei verschiedene Komponenten)
	'AlarmeTab.svelte:256',
	'AlarmeTab.svelte:514',
	'AlarmeTab.svelte:533',
	'AlarmeTab.svelte:566',
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
const EINGEFROREN_SOLL_ANZAHL = 53;

/**
 * S6c: die vier ueberlebenden AlarmeTab-Eintraege, GEGEN IHREN INHALT gefesselt.
 *
 * Warum das noetig ist: in S6c verschieben sich ihre Zeilennummern zwangslaeufig
 * (Design-Entscheidung 1 der Spec), die Liste oben wird also nachgefuehrt. Ohne
 * diese Fesselung waere der billigste Weg zu Gruen, einfach die vier Nummern
 * einzutragen, die der Zaehlbefehl gerade ausgibt — dann bewachte die Ratsche
 * nur noch sich selbst. Geprueft wird deshalb: an der eingetragenen Zeile steht
 * WOERTLICH diese Bedingung, und im Fenster darunter steht der Baustein, zu dem
 * sie gehoert. Ein auf eine fremde Verzweigung gesetzter Eintrag faellt damit
 * auf, auch wenn die Mengen stimmen.
 */
const BLEIBT_MIT_INHALT: readonly { eintrag: string; zeile: string; folgt: string }[] = [
	{
		eintrag: 'AlarmeTab.svelte:256',
		zeile: "context === 'vergleich'",
		folgt: 'deriveUnalertableSelectedMetricNames('
	},
	{
		eintrag: 'AlarmeTab.svelte:514',
		zeile: "{#if context === 'vergleich' && unalertableSelectedMetricNames.length > 0}",
		folgt: 'alarme-unalertable-metrics-hint'
	},
	{
		eintrag: 'AlarmeTab.svelte:533',
		zeile: "{#if context === 'vergleich'}",
		folgt: 'TelegramKurzstilToggle'
	},
	{
		eintrag: 'AlarmeTab.svelte:566',
		zeile: "{#if context === 'vergleich'}",
		folgt: 'VTAlertSample'
	}
];

/** Wie viele Zeilen unter dem Zweig nach dem zugehoerigen Baustein gesucht wird. */
const FENSTER = 8;

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

	test('die eingefrorene Soll-Liste ist unversehrt (53 Eintraege, keine Duplikate)', () => {
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

describe('S6c: die vier ueberlebenden AlarmeTab-Eintraege zeigen auf ihre eigene Bedingung', () => {
	for (const { eintrag, zeile, folgt } of BLEIBT_MIT_INHALT) {
		test(`${eintrag} traegt weiterhin \`${zeile}\``, () => {
			assert.ok(
				EINGEFROREN.includes(eintrag),
				`Messaufbau kaputt: \`${eintrag}\` steht nicht mehr in EINGEFROREN. Diese vier ` +
					'Eintraege BLEIBEN in S6c — wer einen davon streicht, entfernt eine fachliche ' +
					'oder darstellerische Verzweigung, keine HERKUNFT-Weiche.'
			);
			const [datei, nr] = eintrag.split(':');
			const zeilen = readFileSync(join(SHARED, datei), 'utf-8').split('\n');
			const index = Number(nr) - 1;
			assert.ok(
				index >= 0 && index < zeilen.length,
				`Ratsche verletzt: ${eintrag} zeigt hinter das Dateiende (${zeilen.length} Zeilen).`
			);
			assert.strictEqual(
				zeilen[index].trim(),
				zeile,
				`Ratsche verletzt: an ${eintrag} steht eine ANDERE Bedingung als die eingefrorene. ` +
					'Wurde die Liste nach einer Zeilenverschiebung nur „nachgezogen", zeigt der ' +
					'Eintrag jetzt auf eine fremde Verzweigung — die Mengen stimmen dann, die ' +
					'Aussage nicht mehr. Nachfuehren heisst: die Zeile suchen, die DIESE Bedingung ' +
					'traegt.'
			);
			const fenster = zeilen.slice(index + 1, index + 1 + FENSTER).join('\n');
			assert.ok(
				fenster.includes(folgt),
				`Ratsche verletzt: unter ${eintrag} steht kein \`${folgt}\` mehr. Der Eintrag ` +
					'gehoert damit nicht mehr zu dem Baustein, fuer den er eingefroren wurde.'
			);
		});
	}
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
