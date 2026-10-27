// ESM-Hook-Ergaenzung (Issue #2283): SvelteKit-Importe der Form
// `./compareWizardState.svelte` bzw. `$lib/stores/saveStatusStore.svelte`
// zeigen in Vite auf `<name>.svelte.ts`. Ausserhalb von Vite findet Node die
// Datei nicht (`test-svelte-ssr-hooks.mjs` prueft nur die Variante ohne
// Zusatzendung). Dieser Hook ergaenzt genau diese eine Aufloesung; die
// Uebersetzung der Runen erledigt `trip-new/__tests__/ssrRunesHook.mjs`.
//
// Gebraucht, um ganze Hub-Organismen (`CompareTabs.svelte`) serverseitig zu
// rendern — keine Attrappe, nur Pfadaufloesung.

import { existsSync, readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { stripTypeScriptTypes } from 'node:module';
import { compileModule } from 'svelte/compiler';

export async function resolve(specifier, context, nextResolve) {
	const parent = context.parentURL ?? '';
	if (specifier.endsWith('.svelte') && parent.startsWith('file:')) {
		let base = null;
		if (specifier.startsWith('./') || specifier.startsWith('../')) {
			base = new URL(specifier, parent).href;
		} else if (specifier.startsWith('$lib/')) {
			const root = parent.match(/^(file:\/\/\/.*?\/frontend)\//);
			if (root) base = `${root[1]}/src/lib/${specifier.slice(5)}`;
		}
		if (base && !existsSync(fileURLToPath(base)) && existsSync(fileURLToPath(base + '.ts'))) {
			return { url: base + '.ts', shortCircuit: true };
		}
	}
	return nextResolve(specifier, context);
}

// Eigene `*.svelte.ts`-Runenmodule mit TypeScript-Syntax: erst die Typen
// entfernen (Node-eigenes `stripTypeScriptTypes`, wie `--experimental-strip-types`),
// dann mit dem echten Svelte-Compiler serverseitig uebersetzen.
export async function load(url, context, nextLoad) {
	if (url.startsWith('file:') && url.endsWith('.svelte.ts') && !url.includes('/node_modules/')) {
		const file = fileURLToPath(url);
		const js = stripTypeScriptTypes(readFileSync(file, 'utf-8'), { mode: 'strip' });
		const out = compileModule(js, { generate: 'server', filename: file.replace(/\.ts$/, '.js') });
		return { format: 'module', shortCircuit: true, source: out.js.code };
	}
	return nextLoad(url, context);
}
