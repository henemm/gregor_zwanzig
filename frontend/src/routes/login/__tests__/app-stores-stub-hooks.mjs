// ESM-Hook: stubbt SvelteKits virtuelles Modul `$app/stores` fuer den
// SSR-Test dieser Route (login_erstes_bild.test.ts).
//
// `frontend/src/routes/login/+page.svelte` liest `$page.url.searchParams`
// (die Merkmale `registered`/`expired`) und uebergibt `$page.url` an
// `abmeldungLiegtVor()`. `$page` ist ein STORE, kein einfaches Objekt --
// Svelte kompiliert `$page.x` zu einem `subscribe`-Aufruf (Store-Vertrag:
// `subscribe(run)` ruft `run(wert)` sofort synchron auf und liefert eine
// Unsubscribe-Funktion). Ein Plain Object waere KEIN gueltiger Store und
// wuerde beim Kompilat mit einem Laufzeitfehler scheitern.
//
// Bewusst LOKAL neben dem Test, nicht in die geteilte Hook-Kette
// (test-svelte-ssr-hooks.mjs) eingetragen -- eine Aenderung dort wuerde
// jeden anderen SSR-Test mit betreffen, der $app/stores nicht braucht.
// Vorbild fuer das Muster "eigener $app/*-Stub per data:-URL":
// test-app-environment-stub-hooks.mjs.

const STUB_SOURCE = `
const PAGE_VALUE = {
	url: new URL('http://localhost/login'),
	params: {},
	route: { id: '/login' },
	status: 200,
	error: null,
	data: {},
	form: null
};

function readableStore(value) {
	return {
		subscribe(run) {
			run(value);
			return () => {};
		}
	};
}

export const page = readableStore(PAGE_VALUE);
export const navigating = readableStore(null);
export const updated = {
	subscribe: readableStore(false).subscribe,
	check: async () => false
};
`;

export async function resolve(specifier, context, nextResolve) {
	if (specifier === '$app/stores') {
		return {
			url: 'data:text/javascript,' + encodeURIComponent(STUB_SOURCE),
			shortCircuit: true
		};
	}
	return nextResolve(specifier, context);
}
