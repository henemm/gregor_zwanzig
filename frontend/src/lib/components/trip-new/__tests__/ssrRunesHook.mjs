// ESM-Hook-Ergaenzung fuer das SSR-Rendern GANZER Editor-Komponenten.
//
// `test-svelte-ssr-hooks.mjs` uebersetzt `.svelte`-Dateien. Fuer einen
// Vollrender von `TripNewEditor.svelte` reicht das nicht: die Komponente zieht
// ueber `$lib/components/ui/dialog` die Bibliothek `bits-ui` herein, und deren
// ausgelieferte `*.svelte.js`-Module enthalten unkompilierte Runes
// (`$state`, `$derived.by`). Node laedt sie sonst als reines JS und bricht mit
// `ReferenceError: $state is not defined` ab.
//
// Dieser Hook uebersetzt genau solche Runen-Module mit `compileModule` des
// echten Svelte-Compilers — kein Rune-Attrappen-Shim, der `$derived.by` eifrig
// statt faul auswerten wuerde und die Bibliothek dadurch anders laufen liesse
// als in der Anwendung.
//
// Zusaetzlich werden die SvelteKit-Laufzeit-Module `$app/*` aufloesbar gemacht;
// ausserhalb von Vite existieren sie nicht. Navigation ist im Render nicht
// beteiligt (`goto`/`beforeNavigate` werden nur in Event-Handlern aufgerufen).

import { readFileSync, existsSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { compileModule } from 'svelte/compiler';

const APP_STUBS = {
	'$app/navigation':
		'export function goto(){};export function beforeNavigate(){};' +
		'export function afterNavigate(){};export function invalidateAll(){};' +
		'export function pushState(){};export function replaceState(){}',
	'$app/environment': 'export const browser=false;export const dev=false;export const building=false;',
	'$app/stores':
		'export const page={subscribe(run){run({url:new URL("http://localhost/trips/new"),params:{}});return()=>{}}};' +
		'export const navigating={subscribe(run){run(null);return()=>{}}};'
};

export async function resolve(specifier, context, nextResolve) {
	const stub = APP_STUBS[specifier];
	if (stub) {
		return { url: `data:text/javascript,${encodeURIComponent(stub)}`, shortCircuit: true };
	}
	return nextResolve(specifier, context);
}

export async function load(url, context, nextLoad) {
	if (/\.svelte\.(js|ts)$/.test(url) && url.startsWith('file:')) {
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
