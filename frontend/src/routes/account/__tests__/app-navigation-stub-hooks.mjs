// ESM-Hook: stubbt SvelteKits virtuelle Module `$app/navigation`,
// `$app/environment` und `$app/stores` fuer den SSR-Test der Kontoseite
// (pending_address_notice.test.ts).
//
// `frontend/src/routes/account/+page.svelte` importiert `invalidateAll` aus
// `$app/navigation`. `$app/*` ist ein SvelteKit-Build-Alias und existiert unter
// reinem Node nicht als Paket. Im SSR-Render wird keine dieser Funktionen
// aufgerufen (nur Event-Handler/onMount) — die Stubs muessen nur importierbar
// sein.
//
// Bewusst LOKAL neben dem Test, nicht in die geteilte Hook-Kette
// (test-svelte-ssr-hooks.mjs) eingetragen. Vorbild:
// src/routes/login/__tests__/app-stores-stub-hooks.mjs.

import { readFileSync, existsSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { compileModule } from 'svelte/compiler';

const NAVIGATION_STUB = `
export async function invalidateAll() {}
export async function invalidate() {}
export async function goto() {}
export function beforeNavigate() {}
export function afterNavigate() {}
export function onNavigate() {}
export async function preloadData() {}
export async function preloadCode() {}
export function pushState() {}
export function replaceState() {}
export function disableScrollHandling() {}
`;

const STORES_STUB = `
function readableStore(value) {
	return { subscribe(run) { run(value); return () => {}; } };
}
export const page = readableStore({
	url: new URL('http://localhost/account'), params: {}, route: { id: '/account' },
	status: 200, error: null, data: {}, form: null
});
export const navigating = readableStore(null);
export const updated = { subscribe: readableStore(false).subscribe, check: async () => false };
`;

function dataUrl(source) {
	return 'data:text/javascript,' + encodeURIComponent(source);
}

export async function resolve(specifier, context, nextResolve) {
	if (specifier === '$app/navigation') {
		return { url: dataUrl(NAVIGATION_STUB), shortCircuit: true };
	}
	if (specifier === '$app/stores') {
		return { url: dataUrl(STORES_STUB), shortCircuit: true };
	}
	if (specifier === '$app/environment') {
		return {
			url: dataUrl('export const browser=false;export const building=false;export const dev=true;export const version="test";'),
			shortCircuit: true
		};
	}
	return nextResolve(specifier, context);
}

// Die Kontoseite zieht ueber `$lib/components/ui/dialog` die Bibliothek
// `bits-ui` herein, deren ausgelieferte `*.svelte.js`-Module unkompilierte
// Runes (`$state`) enthalten. Ohne Uebersetzung bricht Node mit
// `ReferenceError: $state is not defined` ab. Uebersetzt wird mit dem echten
// Svelte-Compiler — Vorbild: src/lib/components/trip-new/__tests__/ssrRunesHook.mjs.
export async function load(url, context, nextLoad) {
	if (/\.svelte\.js$/.test(url) && url.startsWith('file:')) {
		const file = fileURLToPath(url);
		if (existsSync(file)) {
			const { js } = compileModule(readFileSync(file, 'utf-8'), {
				generate: 'server',
				filename: file
			});
			return { format: 'module', shortCircuit: true, source: js.code };
		}
	}
	return nextLoad(url, context);
}
