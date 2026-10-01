// ESM-Resolver-Hook fuer node --test: macht `+page.server.ts` ausserhalb von Vite
// importierbar, damit `load()` ECHT aufgerufen werden kann.
//
// Kopie von frontend/src/routes/compare/__tests__/server-load-resolve.hooks.mjs
// (Issue #2154 Scheibe B) — generischer Hook, keine Compare-spezifische Logik,
// je Routen-Testordner dupliziert nach bestehender Konvention (dort gibt es
// bislang nur die eine Kopie).
//
// Zwei Luecken werden geschlossen, mehr nicht:
//   1. `$env/dynamic/private|public` — virtuelle SvelteKit-Module, die es unter
//      node gar nicht gibt. Stub liefert eine LEERE Umgebung; `apiBase()` faellt
//      damit auf seinen eigenen Default zurueck.
//   2. `…/foo.js`, wo im Baum `…/foo.ts` liegt (SvelteKit-Import-Konvention).
//      Der vorhandene test-lib-hooks.mjs ergaenzt nur eine FEHLENDE Extension.
//
// Am Prueflig selbst wird nichts ersetzt — nur die Modul-Aufloesung.

import { existsSync } from 'node:fs';
import { fileURLToPath } from 'node:url';

const LEERE_ENV = 'data:text/javascript,export const env = {};';

export async function resolve(specifier, context, nextResolve) {
	if (specifier === '$env/dynamic/private' || specifier === '$env/dynamic/public') {
		return { url: LEERE_ENV, shortCircuit: true };
	}

	const ergebnis = await nextResolve(specifier, context);
	if (ergebnis?.url?.startsWith('file://') && ergebnis.url.endsWith('.js')) {
		const alsTs = ergebnis.url.slice(0, -3) + '.ts';
		if (!existsSync(fileURLToPath(ergebnis.url)) && existsSync(fileURLToPath(alsTs))) {
			return { url: alsTs, shortCircuit: true };
		}
	}
	return ergebnis;
}
