// ESM-Hooks für $lib/* → src/lib/* Auflösung
// Wird von test-lib-loader.mjs via register() geladen.

export function resolve(specifier, context, nextResolve) {
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
	return nextResolve(specifier, context);
}
