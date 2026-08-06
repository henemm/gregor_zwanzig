// ESM-Hook: stubbt SvelteKits virtuelles Modul `$app/environment` fuer
// Node-SSR-Tests (`svelte/server`). Noetig fuer jeden SSR-Test, dessen
// Komponentenbaum transitiv `$app/environment` importiert (z. B. ueber
// `mobile/Sheet.svelte`, `mobile/Drawer.svelte`) — `$app/*` ist ein
// SvelteKit-Build-Alias, existiert unter reinem Node nicht als Paket.
//
// Ergaenzt test-svelte-ssr-hooks.mjs additiv (eigene Datei, keine Aenderung
// an der bestehenden Hook-Kette) — per `register()` VOR den bestehenden
// Hooks im Testfile einzuhaengen.

export async function resolve(specifier, context, nextResolve) {
	if (specifier === '$app/environment') {
		return {
			url: 'data:text/javascript,export const browser=false;export const building=false;export const dev=true;export const version="test";',
			shortCircuit: true
		};
	}
	return nextResolve(specifier, context);
}
