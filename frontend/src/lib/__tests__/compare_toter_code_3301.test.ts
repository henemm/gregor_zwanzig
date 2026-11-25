// # doc-compliance-test
// Lösch- und Sperrnachweis — Issue #3301 (Epic #3122).
// Spec: docs/specs/fast/fix-3301-compare-toter-code.md (AC-1, AC-2)
//
// Ausdrücklich ein Dateiinhalt-/Dateisystem-Nachweis (Ausnahme `# doc-compliance-test` der Test-Politik):
// AC-1: compareHourlyMetricDefs.ts ist gelöscht, keine Produktionsdatei importiert es.
// AC-2: die Anlegeseite des Ortsvergleichs (routes/compare/new/+page.svelte) samt aller transitiv
//       eingebundenen lokalen .svelte/.ts-Module nennt weder `WeatherMetricsTab` noch `layout_kanal`.
// AC-3 (Speichern erhält hourly_metrics) belegt compareEditorHourlyMetrics.test.ts.
//
// RED vor #3301: compareHourlyMetricDefs.ts existierte noch.
//
// Ausführen (aus frontend/):
//   npm test -- src/lib/__tests__/compare_toter_code_3301.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { existsSync, readdirSync, readFileSync, statSync } from 'node:fs';
import { dirname, join, relative, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const SRC = fileURLToPath(new URL('../../', import.meta.url)); // frontend/src/
const LIB = join(SRC, 'lib');
const pfad = (rel: string) => join(SRC, rel);

const TOT = 'lib/components/compare/compareHourlyMetricDefs.ts';
const ANLEGESEITE = 'routes/compare/new/+page.svelte';

const istTest = (rel: string) => /(^|\/)__tests__\//.test(rel) || /\.(test|spec)\.[tj]s$/.test(rel);

function produktionsdateien(): string[] {
	const aus: string[] = [];
	const lauf = (dir: string) => {
		for (const name of readdirSync(dir)) {
			const voll = join(dir, name);
			if (statSync(voll).isDirectory()) {
				if (name !== 'node_modules') lauf(voll);
				continue;
			}
			const rel = relative(SRC, voll).split('\\').join('/');
			if (/\.(ts|js|svelte)$/.test(name) && !istTest(rel)) aus.push(rel);
		}
	};
	lauf(SRC);
	return aus;
}

/** Löst einen Import-Spezifizierer (relativ oder $lib) auf eine existierende Datei auf, sonst null. */
function aufloesen(von: string, spez: string): string | null {
	let basis: string;
	if (spez.startsWith('$lib/') || spez === '$lib') basis = join(LIB, spez.slice(4));
	else if (spez.startsWith('./') || spez.startsWith('../')) basis = resolve(dirname(von), spez);
	else return null;
	const kandidaten = [
		basis,
		`${basis}.ts`,
		`${basis}.js`,
		`${basis}.svelte`,
		basis.replace(/\.js$/, '.ts'),
		join(basis, 'index.ts'),
		join(basis, 'index.js')
	];
	for (const k of kandidaten) {
		if (existsSync(k) && statSync(k).isFile() && /\.(ts|js|svelte)$/.test(k)) return k;
	}
	return null;
}

/** Entfernt Block-, HTML- und Zeilenkommentare; Zeilenzahl bleibt erhalten (Zeilenumbrüche bleiben). */
function ohneKommentare(text: string): string {
	const leeren = (s: string) => s.replace(/[^\n]/g, ' ');
	return text
		.replace(/\/\*[\s\S]*?\*\//g, leeren)
		.replace(/<!--[\s\S]*?-->/g, leeren)
		.replace(/(^|[^:'"`])\/\/[^\n]*/g, (_m, vor: string) => vor);
}

const IMPORT_MUSTER = /(?:from|import\s*\(|import)\s*['"]([^'"]+)['"]/g;

/** Transitive Hülle der lokalen Importe ab einer Startdatei. */
function importHuelle(start: string): string[] {
	const gesehen = new Set<string>();
	const stapel = [start];
	while (stapel.length) {
		const datei = stapel.pop()!;
		if (gesehen.has(datei)) continue;
		gesehen.add(datei);
		const text = readFileSync(datei, 'utf8');
		for (const m of text.matchAll(IMPORT_MUSTER)) {
			const ziel = aufloesen(datei, m[1]);
			if (ziel && !gesehen.has(ziel)) stapel.push(ziel);
		}
	}
	return [...gesehen];
}

describe('#3301 AC-1: compareHourlyMetricDefs.ts gelöscht, kein Produktionsimport', () => {
	test(`gelöscht: ${TOT}`, () => {
		assert.equal(existsSync(pfad(TOT)), false, `${TOT} existiert noch`);
	});

	test('keine Produktionsdatei importiert compareHourlyMetricDefs (statisch, Barrel-Export, dynamisch)', () => {
		const muster = /(?:from|import\s*\()\s*['"][^'"]*\/compareHourlyMetricDefs(?:\.ts|\.js)?['"]/g;
		const funde: string[] = [];
		for (const rel of produktionsdateien()) {
			if (muster.test(readFileSync(pfad(rel), 'utf8'))) funde.push(rel);
			muster.lastIndex = 0;
		}
		assert.deepEqual(funde, [], 'Produktions-Importe von compareHourlyMetricDefs');
	});
});

describe('#3301 AC-2: Anlegeseite Ortsvergleich ohne Kanal-Layout-Karte', () => {
	test('Importkette ist auflösbar und nicht trivial', () => {
		const huelle = importHuelle(pfad(ANLEGESEITE));
		assert.ok(
			huelle.some((d) => d.endsWith('CompareNewEditor.svelte')),
			'Importkette löst CompareNewEditor.svelte nicht auf — Nachweis wäre leer'
		);
	});

	// Geprüft wird eingebundener Code (Importe, Markup, Schlüssel), nicht Kommentare: Verweise in
	// Kommentaren auf den gelöschten Alt-Editor binden nichts ein.
	test('keine Datei der Importkette bindet WeatherMetricsTab oder layout_kanal ein (ohne Kommentare)', () => {
		const funde: string[] = [];
		for (const datei of importHuelle(pfad(ANLEGESEITE))) {
			ohneKommentare(readFileSync(datei, 'utf8'))
				.split('\n')
				.forEach((zeile, i) => {
					if (/WeatherMetricsTab|layout_kanal/.test(zeile)) {
						funde.push(`${relative(SRC, datei)}:${i + 1}`);
					}
				});
		}
		assert.deepEqual(funde, [], 'Treffer auf WeatherMetricsTab/layout_kanal in der Anlegeseite');
	});
});
