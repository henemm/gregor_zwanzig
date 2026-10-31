// ESM-Hook (Issue #2648): `$app/navigation` fuer sprache_im_konto.test.ts, mit
// Zaehler fuer `invalidateAll` (globalThis.__gzInvalidateAllAufrufe). Das
// echte `invalidateAll` laedt im Browser die Layout-Daten neu; unter Node gibt
// es SvelteKits Laufzeit nicht. Der Zaehler belegt, DASS die Komponente das
// Neuladen anstoesst; was danach geladen wird, prueft der Test am echten
// Layout-Loader. Als letzter Hook registriert, ueberdeckt er nur dieses Modul.

const NAVIGATION = `
export async function invalidateAll() {
	globalThis.__gzInvalidateAllAufrufe = (globalThis.__gzInvalidateAllAufrufe ?? 0) + 1;
}
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

export async function resolve(specifier, context, nextResolve) {
	if (specifier === '$app/navigation') {
		return { url: 'data:text/javascript,' + encodeURIComponent(NAVIGATION), shortCircuit: true };
	}
	return nextResolve(specifier, context);
}
