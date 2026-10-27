// ESM-Hook (Issue #1969 Fix-Loop 1): eigene Runen-Module `*.svelte.ts` fuer die
// echte Svelte-CLIENT-Laufzeit uebersetzen (generate: 'client').
//
// Warum: die Kernsuite rendert serverseitig — dort laeuft kein `$effect`. Reine
// Runen-Module (ohne Markup) brauchen aber kein DOM: mit `effect_root` + `flush`
// aus `svelte/internal/client` laufen ihre Effekte samt echter Abhaengigkeits-
// Verfolgung unter Node. So wird gemessen, WANN der Lader neu abruft — nicht,
// ob ein Bezeichner im Quelltext steht.
//
// Nur im Testprozess registriert, der das Modul in Client-Form braucht
// (node --test startet je Datei einen eigenen Prozess).

import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { stripTypeScriptTypes } from 'node:module';
import { compileModule } from 'svelte/compiler';

export async function load(url, context, nextLoad) {
	if (url.startsWith('file:') && !url.includes('/node_modules/') && url.endsWith('.svelte.ts')) {
		const file = fileURLToPath(url);
		const js = stripTypeScriptTypes(readFileSync(file, 'utf-8'), { mode: 'strip' });
		const out = compileModule(js, { generate: 'client', filename: file.replace(/\.ts$/, '.js') });
		return { format: 'module', shortCircuit: true, source: out.js.code };
	}
	return nextLoad(url, context);
}
