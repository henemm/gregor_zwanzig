// ESM-Hook: stubbt SvelteKits virtuelles Modul `$env/dynamic/private` fuer
// Node-Tests, die ein Server-Modul (z. B. `src/hooks.server.ts`) per echtem
// `import()` laden. `$env/*` ist ein SvelteKit-Build-Alias und existiert unter
// reinem Node nicht als Paket; der Stub reicht `process.env` durch, sodass ein
// Test die Umgebung vor dem Import setzen kann.
//
// Loest zusaetzlich `$lib/x.js` auf `src/lib/x.ts` auf — Server-Module folgen
// der SvelteKit-Konvention, TS-Dateien mit `.js`-Endung zu importieren.
//
// Ergaenzt test-lib-hooks.mjs additiv (eigene Datei, keine Aenderung an der
// bestehenden Hook-Kette) — per `register()` im Testfile einzuhaengen.

export async function resolve(specifier, context, nextResolve) {
	if (specifier === '$env/dynamic/private') {
		return {
			url: 'data:text/javascript,export const env = process.env;',
			shortCircuit: true
		};
	}
	if (specifier.startsWith('$lib/') && specifier.endsWith('.js') && context.parentURL) {
		const match = context.parentURL.match(/^(file:\/\/\/.*?\/frontend)\//);
		if (match) {
			const rest = specifier.slice('$lib/'.length, -'.js'.length);
			return { url: `${match[1]}/src/lib/${rest}.ts`, shortCircuit: true };
		}
	}
	return nextResolve(specifier, context);
}
