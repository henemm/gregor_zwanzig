// TDD RED — Issue #2727 (Epic #2345, DoD-1): compareWizardState ablösen.
// Spec: docs/specs/modules/feat_2727_compare_wizardstate_abloesen.md — AC-1, AC-2, AC-3, AC-4
//
// Wächter gegen die Rückkehr des geteilten Ortsvergleich-Zustandsmoduls — geprüft wird die ROLLE,
// nicht nur der Name (Vorbild compare_hub_bridge_restlos_entfernt.test.ts):
//   (a) AC-1: die Datei des Zustandsmoduls existiert nicht, und keine Datei unter frontend/src
//       (Produktivcode, Test, Hilfsmodul wie svelteTsModulHook.mjs) lädt sie — gezählt wird jede
//       Nennung des Dateistamms in einem String-Literal auf einer Code-Zeile (statischer/dynamischer
//       Import, `import type`, Pfadbau). Kommentar-Erwähnungen zählen NICHT (shared/-Produktivdateien
//       erwähnen den Namen in Kommentaren und bleiben laut AC-18 unberührt).
//   (b) AC-2: die Context-Schlüssel kommen unter frontend/src auf keiner Code-Zeile vor
//       (Kommentarzeilen `//`, `*`, `/*`, `<!--` ausgenommen).
//   (c) AC-3: unter compare/ und compare-new/ (ohne __tests__ und *.test.ts) exportiert keine
//       `.ts`/`.svelte.ts`-Datei eine Klasse oder Factory, die `$state` benutzt (Kommentare
//       entfernt) — auch nicht unter anderem Namen. Reine Daten-Factories ohne `$state` bleiben erlaubt.
//   (d) AC-4: unter compare/ und compare-new/ (ohne Tests) ruft keine `.svelte`/`.ts`-Datei
//       `setContext`/`getContext` auf (Kommentare ausgenommen).
//
// Alle Suchbegriffe sind aus ZWEI String-Teilen zusammengesetzt — sonst fände der Wächter sich
// selbst. Jede Wächterfunktion nimmt die Wurzel als Parameter: die Positivkontrollen laufen über
// DENSELBEN Codepfad in einem Temp-Verzeichnis (mkdtemp, danach aufgeräumt).
// grep-Exit 2 = Messfehler (kaputtes Muster/Pfad); Exit 1 = „kein Treffer" ist der GREEN-Fall.
//
// Warum heute rot: die Datei existiert, Hub/Anlege-Seite/Editor/Vorlage/Step2Orte und mehrere
// Tests laden sie, die Seite /compare/new setzt beide Context-Schlüssel, Step2Orte und
// CompareNewEditor rufen getContext auf. Die Positivkontrollen und Messaufbau-Checks sind heute grün.
//
// Pfadregel #1409: Wurzel relativ zu DIESER Datei.
//
// Ausführen (aus frontend/):
//   node --import ./test-lib-loader.mjs --experimental-strip-types --experimental-test-module-mocks \
//     --test src/lib/components/compare/__tests__/compare_wizard_state_entfernt.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { existsSync, mkdirSync, mkdtempSync, readFileSync, readdirSync, rmSync, statSync, writeFileSync } from 'node:fs';
import { spawnSync } from 'node:child_process';
import { tmpdir } from 'node:os';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

/** __tests__ -> compare -> components -> lib -> src */
const SRC = join(dirname(fileURLToPath(import.meta.url)), '..', '..', '..', '..');

const STAMM = 'compareWizard' + 'State.svelte'; // Dateistamm, groß-/kleinschreibungsgenau
const SCHLUESSEL = ['compare-wizard' + '-state', 'compare-wizard' + '-profile'];
const ROLLEN_ORDNER = ['compare', 'compare-new'];

interface Treffer {
	datei: string;
	nr: number;
	text: string;
}

// ── Messwerkzeuge (Wurzel als Parameter) ─────────────────────────────────────────

function istKommentarZeile(text: string): boolean {
	const t = text.trim();
	return t.startsWith('//') || t.startsWith('*') || t.startsWith('/*') || t.startsWith('<!--');
}

/** grep -rnF über eine Wurzel; Exit 2 wirft (Messfehler), Exit 1 = keine Zeile. */
function grepZeilen(wurzel: string, begriff: string): Treffer[] {
	const lauf = spawnSync(
		'grep',
		['-rnF', '--include=*.ts', '--include=*.svelte', '--include=*.mjs', '--include=*.js', '-e', begriff, '.'],
		{ cwd: wurzel, encoding: 'utf-8' }
	);
	if (lauf.status === 2 || lauf.error) {
		throw new Error(`Messfehler: grep ist gescheitert (Status ${lauf.status}): ${lauf.stderr ?? lauf.error}`);
	}
	return (lauf.stdout ?? '')
		.split('\n')
		.filter((z) => z.trim() !== '')
		.map((z) => {
			const m = /^\.\/(.*?):(\d+):(.*)$/.exec(z);
			if (!m) throw new Error(`Messfehler: unlesbare grep-Zeile: ${z}`);
			return { datei: m[1], nr: Number(m[2]), text: m[3] };
		});
}

function escapeRe(s: string): string {
	return s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

/** (a) Code-Zeilen, die den Dateistamm in einem String-Literal nennen. */
export function stammLadestellen(wurzel: string): Treffer[] {
	const imString = new RegExp(`['"\`][^'"\`]*${escapeRe(STAMM)}`);
	return grepZeilen(wurzel, STAMM).filter((t) => !istKommentarZeile(t.text) && imString.test(t.text));
}

/** (a) Existiert die Moduldatei unter `<src>/lib/components/compare/`? */
export function moduldateiExistiert(wurzel: string): boolean {
	return existsSync(join(wurzel, 'lib', 'components', 'compare', STAMM + '.ts'));
}

/** (b) Code-Zeilen mit einem der Context-Schlüssel. */
export function schluesselStellen(wurzel: string): Treffer[] {
	return SCHLUESSEL.flatMap((s) => grepZeilen(wurzel, s)).filter((t) => !istKommentarZeile(t.text));
}

/** Kommentare durch Leerzeichen ersetzen (Zeilenumbrüche bleiben ⇒ Zeilennummern stimmen). */
function ohneKommentare(quelle: string): string {
	const leer = (m: string) => m.replace(/[^\n]/g, ' ');
	return quelle
		.replace(/<!--[\s\S]*?-->/g, leer)
		.replace(/\/\*[\s\S]*?\*\//g, leer)
		.replace(/(^|[ \t])\/\/[^\n]*/gm, (m, vor: string) => vor + leer(m.slice(vor.length)));
}

/** Alle Nicht-Test-Dateien unter `<components>/compare|compare-new` mit passender Endung. */
function rollenDateien(components: string, endungen: string[]): string[] {
	const ergebnis: string[] = [];
	function lauf(ordner: string): void {
		if (!existsSync(ordner)) return;
		for (const name of readdirSync(ordner)) {
			const pfad = join(ordner, name);
			if (statSync(pfad).isDirectory()) {
				if (name !== '__tests__' && name !== 'node_modules') lauf(pfad);
				continue;
			}
			if (/\.test\.(ts|js)$/.test(name)) continue;
			if (endungen.some((e) => name.endsWith(e))) ergebnis.push(pfad);
		}
	}
	for (const o of ROLLEN_ORDNER) lauf(join(components, o));
	return ergebnis.sort();
}

const EXPORT_ROLLE = /^\s*export\s+(default\b|(abstract\s+)?class\b|(async\s+)?function\b|const\b|let\b|var\b)/m;

/** (c) Dateien, die `$state` benutzen UND eine Klasse/Factory exportieren. */
export function zustandsModule(components: string): string[] {
	return rollenDateien(components, ['.ts'])
		.filter((d) => {
			const code = ohneKommentare(readFileSync(d, 'utf-8'));
			return /\$state\b/.test(code) && EXPORT_ROLLE.test(code);
		})
		.map((d) => d.slice(components.length + 1));
}

/** (d) setContext/getContext-Aufrufe (Kommentare ausgenommen). */
export function contextStellen(components: string): Treffer[] {
	const treffer: Treffer[] = [];
	for (const d of rollenDateien(components, ['.svelte', '.ts'])) {
		ohneKommentare(readFileSync(d, 'utf-8'))
			.split('\n')
			.forEach((zeile, i) => {
				if (/\b(set|get)Context\b/.test(zeile)) treffer.push({ datei: d.slice(components.length + 1), nr: i + 1, text: zeile.trim() });
			});
	}
	return treffer;
}

const liste = (t: Treffer[]) => t.map((x) => `  ${x.datei}:${x.nr}: ${x.text.trim()}`).join('\n');

// ── Positivkontrollen im Temp-Verzeichnis (derselbe Codepfad) ─────────────────────

function mitTempBaum(dateien: Record<string, string>, fn: (wurzel: string) => void): void {
	const wurzel = mkdtempSync(join(tmpdir(), 'gz2727-'));
	try {
		for (const [rel, inhalt] of Object.entries(dateien)) {
			mkdirSync(dirname(join(wurzel, rel)), { recursive: true });
			writeFileSync(join(wurzel, rel), inhalt);
		}
		fn(wurzel);
	} finally {
		rmSync(wurzel, { recursive: true, force: true });
	}
}

describe('Messaufbau und Positivkontrollen (heute grün)', () => {
	test('Messfläche erreichbar: SRC zeigt auf frontend/src, Rollen-Ordner haben Dateien', () => {
		assert.ok(existsSync(join(SRC, 'lib', 'components', 'compare', 'compareEditorSave.ts')), `SRC falsch: ${SRC}`);
		assert.ok(rollenDateien(join(SRC, 'lib', 'components'), ['.ts', '.svelte']).length > 10, 'Rollen-Ordner leer?');
	});

	test('(a) findet Import, Typ-Import und Pfadbau des Dateistamms — nicht die Kommentar-Erwähnung', () => {
		mitTempBaum(
			{
				['lib/components/compare/' + STAMM + '.ts']: 'export const x = 1;\n',
				'lib/a.svelte': `<script lang="ts">\n\timport type { X } from '../compare/${STAMM}';\n</script>\n`,
				'lib/b.ts': `const m = await import(path.join(C, 'compare/${STAMM}.ts'));\n`,
				'lib/c.mjs': `// Beispiel: \`./${STAMM}\` zeigt in Vite auf .svelte.ts\n * siehe '${STAMM}'\n`
			},
			(w) => {
				assert.equal(moduldateiExistiert(w), true);
				assert.deepEqual(stammLadestellen(w).map((t) => t.datei).sort(), ['lib/a.svelte', 'lib/b.ts']);
			}
		);
	});

	test('(b) findet einen Schlüssel im Code, nicht in Kommentarzeilen', () => {
		mitTempBaum(
			{
				'x.svelte': `<script>\n\tsetContext('${SCHLUESSEL[0]}', s);\n</script>\n<!-- ${SCHLUESSEL[1]} -->\n`,
				'y.ts': `const m = new Map([['${SCHLUESSEL[1]}', 1]]);\n// getContext('${SCHLUESSEL[0]}')\n\t *  statt aus getContext('${SCHLUESSEL[0]}')\n`
			},
			(w) => {
				assert.deepEqual(schluesselStellen(w).map((t) => `${t.datei}:${t.nr}`).sort(), ['x.svelte:2', 'y.ts:1']);
			}
		);
	});

	test('(c) findet eine UMBENANNTE Klasse und eine Pfeil-Factory mit $state — nicht die reine Daten-Factory', () => {
		mitTempBaum(
			{
				'compare/feldHalter.svelte.ts': "export class FeldHalter {\n\tname = $state('');\n}\n",
				'compare-new/fabrik.svelte.ts': 'export const fabrik = () => ({ n: $state(0) });\n',
				'compare/daten.ts':
					'/** Der Hub macht daraus `$state(compareFeldsatzStandard())`. */\n' +
					"export function compareFeldsatzStandard() {\n\treturn { name: '' }; // nie $state hier\n}\n",
				'compare/nurKommentar.ts':
					'// Kein $state-Feld mehr\nexport function versandPropsAus(w) { return w; }\n' +
					'// auf — die `$state`-Lesezugriffe würden dann außerhalb des Renderns registriert\n',
				'compare/__tests__/hilfe.svelte.ts': "export class Testhilfe { a = $state(1); }\n"
			},
			(w) => {
				assert.deepEqual(zustandsModule(w), ['compare-new/fabrik.svelte.ts', 'compare/feldHalter.svelte.ts']);
			}
		);
	});

	test('(d) findet getContext im Skript, nicht im Kommentar und nicht in __tests__', () => {
		mitTempBaum(
			{
				'compare/steps/X.svelte': "<script lang=\"ts\">\n\timport { getContext } from 'svelte';\n\tconst w = getContext('k');\n</script>\n",
				'compare/y.ts': '/**\n * ruft setContext(...) auf\n */\nexport const y = 1;\n',
				'compare-new/__tests__/z.ts': "setContext('k', 1);\n"
			},
			(w) => {
				assert.deepEqual(contextStellen(w).map((t) => `${t.datei}:${t.nr}`), ['compare/steps/X.svelte:2', 'compare/steps/X.svelte:3']);
			}
		);
	});
});

// ── Wächter gegen den echten Quellbaum (heute rot) ───────────────────────────────

describe('AC-1..AC-4: das geteilte Ortsvergleich-Zustandsmodul ist restlos abgelöst', () => {
	test('AC-1 (a): die Moduldatei existiert nicht mehr', () => {
		assert.equal(moduldateiExistiert(SRC), false, `Datei existiert noch: compare/${STAMM}.ts`);
	});

	test('AC-1 (a): keine Datei unter frontend/src lädt das Modul (Import, Typ-Import, Pfadbau)', () => {
		const t = stammLadestellen(SRC);
		assert.equal(t.length, 0, `${t.length} Ladestelle(n) des Moduls:\n${liste(t)}`);
	});

	test('AC-2 (b): die Context-Schlüssel kommen auf keiner Code-Zeile unter frontend/src vor', () => {
		const t = schluesselStellen(SRC);
		assert.equal(t.length, 0, `${t.length} Code-Zeile(n) mit Context-Schlüssel:\n${liste(t)}`);
	});

	test('AC-3 (c): unter compare/ und compare-new/ exportiert keine Datei eine Klasse/Factory mit $state', () => {
		const t = zustandsModule(join(SRC, 'lib', 'components'));
		assert.equal(t.length, 0, `Zustandsmodul(e) mit gleicher Rolle: ${t.join(', ')}`);
	});

	test('AC-4 (d): unter compare/ und compare-new/ kein setContext/getContext', () => {
		const t = contextStellen(join(SRC, 'lib', 'components'));
		assert.equal(t.length, 0, `${t.length} Context-Aufruf(e):\n${liste(t)}`);
	});
});
