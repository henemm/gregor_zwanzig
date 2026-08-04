// ESM-Resolver-Hook fuer node --test: macht `+page.server.ts` ausserhalb von Vite
// importierbar, damit `load()` ECHT aufgerufen werden kann.
//
// Zwei Luecken werden geschlossen, mehr nicht:
//   1. `$env/dynamic/private|public` — virtuelle SvelteKit-Module, die es unter
//      node gar nicht gibt. Stub liefert eine LEERE Umgebung; `apiBase()` faellt
//      damit auf seinen eigenen Default zurueck.
//   2. `…/foo.js`, wo im Baum `…/foo.ts` liegt (SvelteKit-Import-Konvention).
//      Der vorhandene test-lib-hooks.mjs ergaenzt nur eine FEHLENDE Extension.
//
// Am Prueflig selbst wird nichts ersetzt — nur die Modul-Aufloesung.
// Ohne diesen Hook muesste der Test auf einen verbotenen Dateiinhalt-Grep
// ausweichen (vgl. pageServerMetricsCatalogFailSoft.test.ts, ausdruecklich KEIN
// Vorbild).

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
			// Kein `format` setzen — Node leitet aus `.ts` selbst
			// `module-typescript` ab und entfernt die Typ-Annotationen.
			return { url: alsTs, shortCircuit: true };
		}
	}
	return ergebnis;
}
