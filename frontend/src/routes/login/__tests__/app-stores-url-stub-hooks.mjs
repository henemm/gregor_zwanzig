// ESM-Hook: stubbt SvelteKits virtuelles Modul `$app/stores` wie
// app-stores-stub-hooks.mjs — mit EINEM Unterschied: die URL von `$page` ist je
// Test einstellbar (`globalThis.__gzLoginTestUrl`), damit `/login?error=<code>`
// serverseitig gerendert werden kann (Issue #2147 Scheibe C, AC-18).
//
// Der Wert wird bei JEDEM subscribe frisch gelesen, nicht beim Modul-Laden —
// sonst saehen alle Renderings desselben Testlaufs die erste URL.
//
// Eigene Datei statt Aenderung am bestehenden Stub: login_erstes_bild.test.ts
// und login_email_unbestaetigt_verzweigung.test.ts bleiben unberuehrt.

const STUB_SOURCE = `
function aktuelleSeite() {
	const href = globalThis.__gzLoginTestUrl ?? 'http://localhost/login';
	return {
		url: new URL(href),
		params: {},
		route: { id: '/login' },
		status: 200,
		error: null,
		data: {},
		form: null
	};
}

export const page = {
	subscribe(run) {
		run(aktuelleSeite());
		return () => {};
	}
};

function readableStore(value) {
	return {
		subscribe(run) {
			run(value);
			return () => {};
		}
	};
}

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
