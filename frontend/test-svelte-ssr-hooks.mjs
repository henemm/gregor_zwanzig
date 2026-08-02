// ESM-Hooks: Svelte-Komponenten fuer node:test serverseitig lauffaehig machen.
//
// Ergaenzt test-lib-hooks.mjs um zwei Dinge, die fuer ECHTE Component-Tests
// noetig sind (statt Datei-Inhalt-Greps, CLAUDE.md "Test-Politik"):
//   1. `.svelte`-Dateien werden mit svelte/compiler nach SSR-JS uebersetzt,
//      so dass `render()` aus `svelte/server` sie ausgeben kann.
//   2. `$lib/x.js`-Importe (SvelteKit-Konvention) zeigen auf `src/lib/x.ts`.
//
// Registrierung erfolgt IM TESTFILE via node:module `register()` — der
// Basis-Pfad wird dort relativ zur Testdatei aufgeloest (Pfadregel #1409),
// damit im Worktree auch die Worktree-Kopie geprueft wird.

import { readFileSync, existsSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { compile } from 'svelte/compiler';

/** Erste existierende Variante eines Modul-URLs (.ts/.svelte/index.ts). */
function firstExisting(baseUrl) {
	const candidates = baseUrl.endsWith('.js')
		? [baseUrl.slice(0, -3) + '.ts', baseUrl.slice(0, -3) + '.svelte', baseUrl]
		: /\.[a-zA-Z]+$/.test(baseUrl)
			? [baseUrl]
			: [baseUrl + '.ts', baseUrl + '.svelte', baseUrl + '/index.ts', baseUrl + '.js'];
	return candidates.find((c) => existsSync(fileURLToPath(c))) ?? null;
}

export async function resolve(specifier, context, nextResolve) {
	const parent = context.parentURL ?? '';
	if (specifier.startsWith('$lib/')) {
		const root = parent.match(/^(file:\/\/\/.*?\/frontend)\//);
		if (root) {
			const hit = firstExisting(`${root[1]}/src/lib/${specifier.slice(5)}`);
			if (hit) return { url: hit, shortCircuit: true };
		}
	}
	if ((specifier.startsWith('./') || specifier.startsWith('../')) && parent) {
		const hit = firstExisting(new URL(specifier, parent).href);
		if (hit) return { url: hit, shortCircuit: true };
	}
	return nextResolve(specifier, context);
}

export async function load(url, context, nextLoad) {
	if (url.endsWith('.svelte')) {
		const file = fileURLToPath(url);
		const { js } = compile(readFileSync(file, 'utf-8'), {
			generate: 'server',
			filename: file
		});
		return { format: 'module', shortCircuit: true, source: js.code };
	}
	return nextLoad(url, context);
}
