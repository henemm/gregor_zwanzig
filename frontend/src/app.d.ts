// See https://svelte.dev/docs/kit/types#app.d.ts
declare global {
	namespace App {
		// interface Error {}
		interface Locals {
			userId: string;
			/** Issue #2647 — Sprache dieser Anfrage (hooks.server.ts, Profil im Layout-Loader). */
			lang: 'de' | 'en';
		}
		interface PageData {
			lang: 'de' | 'en';
		}
		// interface PageState {}
		// interface Platform {}
	}
}

export {};
