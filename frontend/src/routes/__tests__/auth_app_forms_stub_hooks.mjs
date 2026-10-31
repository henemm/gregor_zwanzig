// ESM-Hook: stubbt SvelteKits virtuelles Modul `$app/forms` fuer den SSR-Test
// der Auth-Routen (Issue #2650). `use:enhance` wirkt nur im Browser; serverseitig
// genuegt ein Export, der nichts tut. Vorbild: login/__tests__/app-stores-url-stub-hooks.mjs.

const STUB_SOURCE = `
export function enhance() {
	return { destroy() {} };
}
export function applyAction() {}
export async function deserialize(text) {
	return JSON.parse(text);
}
`;

export async function resolve(specifier, context, nextResolve) {
	if (specifier === '$app/forms') {
		return {
			url: 'data:text/javascript,' + encodeURIComponent(STUB_SOURCE),
			shortCircuit: true
		};
	}
	return nextResolve(specifier, context);
}
