// ESM-Hooks für $lib/* → src/lib/* Auflösung
// Wird von test-lib-loader.mjs via register() geladen.

export async function resolve(specifier, context, nextResolve) {
	if (specifier.startsWith('$lib/')) {
		const rest = specifier.slice('$lib/'.length);
		if (context.parentURL) {
			const base = context.parentURL;
			const match = base.match(/^(file:\/\/\/.*?\/frontend)\//);
			if (match) {
				// .ts-Extension ergänzen wenn noch keine Extension vorhanden
				const withExt = rest.includes('.') ? rest : rest + '.ts';
				const libUrl = `${match[1]}/src/lib/${withExt}`;
				return { url: libUrl, shortCircuit: true };
			}
		}
	}
	try {
		return await nextResolve(specifier, context);
	} catch (err) {
		// Fallback: relative Imports ohne Extension (z.B. './compareEditorSave')
		// scheitern unter striktem Node-ESM. Erlaubt Direkt-Import von .svelte.ts-
		// State-Klassen fuer Prototype-Inspektion in Tests (kein Dateiinhalt-Grep).
		if (
			(err && err.code === 'ERR_MODULE_NOT_FOUND') &&
			(specifier.startsWith('./') || specifier.startsWith('../')) &&
			!/\.[a-zA-Z]+$/.test(specifier)
		) {
			return nextResolve(specifier + '.ts', context);
		}
		throw err;
	}
}
