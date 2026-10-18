// Regressionstest #2278 (Befund aus /60-validate): `vite build` brach mit
// PARSE_ERROR ab, weil der Svelte-Compiler bei `function f(x?: T)` die
// Typannotation entfernt, das `?` aber stehen laesst — ungueltiges JS.
// svelte-check und die SSR-Kernsuite blieben gruen: svelte-check prueft TS,
// nicht das erzeugte JS, und der Pruefstand `svelteInstanzPruefstand.ts`
// blendet TS selbst per AST aus (inkl. des `?`) statt den Compiler zu fragen.
//
// Dieser Test geht DENSELBEN Weg wie der Build: Preprocess aus svelte.config.js
// (falls gesetzt) + `svelte/compiler` compile mit den Compiler-Optionen der
// Config, fuer client UND server — und parst das Ergebnis als ES-Modul.
//
// Pfadregel #1409: Dateien relativ zu DIESER Testdatei aufgeloesen.

import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync, readdirSync } from 'node:fs';
import { dirname, resolve, sep } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { compile, preprocess } from 'svelte/compiler';
import { parse as parseJs } from 'acorn';

const hier = dirname(fileURLToPath(import.meta.url));
const frontend = resolve(hier, '../../..');

// Adversary F003 (#2278): KEINE feste Liste — jede .svelte-Datei unter src/ wird geprueft,
// sonst bleibt eine neue/vergessene Datei mit demselben Fehler unbewacht. Es gibt KEINE
// Ausnahmen: auch die internen Seiten src/routes/_design*/ baut `vite build` mit.
const DATEIEN = (readdirSync(resolve(frontend, 'src'), { recursive: true }) as string[])
	.filter((p) => p.endsWith('.svelte'))
	.map((p) => 'src/' + p.split(sep).join('/'))
	.sort();

test('die Dateiliste ist nicht leer (Glob greift)', () => {
	assert.ok(DATEIEN.length > 100, `nur ${DATEIEN.length} .svelte-Dateien gefunden — Glob kaputt?`);
	assert.ok(DATEIEN.includes('src/lib/components/molecules/SendConfirmDialog.svelte'));
});

const config = (await import(pathToFileURL(resolve(frontend, 'svelte.config.js')).href)).default;

function runesFuer(filename: string): boolean | undefined {
	const r = config.compilerOptions?.runes;
	return typeof r === 'function' ? r({ filename }) : r;
}

for (const rel of DATEIEN) {
	for (const generate of ['client', 'server'] as const) {
		test(`${rel} (${generate}) kompiliert zu parsebarem JS`, async () => {
			const filename = resolve(frontend, rel);
			let code = readFileSync(filename, 'utf-8');
			if (config.preprocess) {
				code = (await preprocess(code, config.preprocess, { filename })).code;
			}
			const { runes: _r, ...rest } = config.compilerOptions ?? {};
			const out = compile(code, { ...rest, filename, generate, runes: runesFuer(filename) });
			assert.doesNotThrow(
				() => parseJs(out.js.code, { ecmaVersion: 'latest', sourceType: 'module' }),
				`${rel} (${generate}): erzeugtes JS ist nicht parsebar`
			);
		});
	}
}
