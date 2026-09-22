// ESM-Hook fuer den SSR-Rendertest von `+layout.svelte` (Issue #2268).
//
// Das Layout liest `page` aus `$app/state` (Runen-Variante von SvelteKit) — in
// keinem bestehenden Stub vorhanden — und importiert `../app.css`. Ausserhalb
// von Vite existiert beides nicht.
//
// Der Pfad ist je Test einstellbar (`globalThis.__gzLayoutTestPath`) und wird
// bei JEDEM Zugriff auf `page.url` frisch gelesen, nicht beim Modul-Laden —
// sonst saehen alle Renderings desselben Testlaufs den ersten Pfad.

import { existsSync, readFileSync } from 'node:fs';
import { stripTypeScriptTypes } from 'node:module';
import { compileModule } from 'svelte/compiler';
import { fileURLToPath } from 'node:url';

const STATE_STUB = `
export const page = {
	get url() {
		return new URL(globalThis.__gzLayoutTestPath ?? '/trips', 'http://localhost');
	},
	params: {},
	route: { id: null },
	status: 200,
	error: null,
	data: {},
	form: null
};
export const navigating = { from: null, to: null, type: null };
export const updated = { current: false, check: async () => false };
`;

// `$lib/x.svelte` bzw. `./x.svelte` meint hier eine Runen-Moduldatei
// `x.svelte.ts` (z. B. stores/verbindung.svelte.ts); der gemeinsame Resolver
// wuerde sie als Komponenten-Datei `x.svelte` suchen und nicht finden.
function runenModul(specifier, parent) {
	if (!specifier.endsWith('.svelte')) return null;
	let basis;
	if (specifier.startsWith('$lib/')) {
		const root = parent.match(/^(file:\/\/\/.*?\/frontend)\//);
		if (!root) return null;
		basis = `${root[1]}/src/lib/${specifier.slice(5)}`;
	} else if (specifier.startsWith('./') || specifier.startsWith('../')) {
		basis = new URL(specifier, parent).href;
	} else {
		return null;
	}
	const kandidat = basis + '.ts';
	return existsSync(fileURLToPath(kandidat)) && !existsSync(fileURLToPath(basis)) ? kandidat : null;
}

export async function resolve(specifier, context, nextResolve) {
	const runen = runenModul(specifier, context.parentURL ?? '');
	if (runen) return { url: runen, shortCircuit: true };
	if (specifier === '$app/state') {
		return {
			url: 'data:text/javascript,' + encodeURIComponent(STATE_STUB),
			shortCircuit: true
		};
	}
	return nextResolve(specifier, context);
}

// Runen-Module in TypeScript: erst Typen strippen (compileModule versteht nur
// JS), dann mit dem echten Svelte-Compiler uebersetzen.
export async function load(url, context, nextLoad) {
	if (/\.svelte\.ts$/.test(url) && url.startsWith('file:')) {
		const file = fileURLToPath(url);
		const js = stripTypeScriptTypes(readFileSync(file, 'utf-8'));
		const { js: out } = compileModule(js, { generate: 'server', filename: file });
		return { format: 'module', shortCircuit: true, source: out.code };
	}
	if (url.endsWith('.css')) {
		return { format: 'module', shortCircuit: true, source: 'export default "";' };
	}
	return nextLoad(url, context);
}
