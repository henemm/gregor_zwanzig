import adapter from '@sveltejs/adapter-node';
import { createHash } from 'node:crypto';
import { readFileSync } from 'node:fs';

/**
 * Issue #2961 (FE6) — Hashes der Inline-Skripte aus `src/app.html`.
 *
 * SvelteKit versieht nur seine EIGENEN Inline-Skripte mit Nonce bzw. Hash.
 * Das Kopf-Skript in app.html (Dunkel-Modus vor dem ersten Paint, #2400)
 * braucht deshalb einen eigenen Eintrag in `script-src`. Er wird hier aus der
 * Datei selbst berechnet, damit eine Aenderung am Skript die Richtlinie nicht
 * still bricht.
 */
function appHtmlSkriptHashes() {
	const html = readFileSync(new URL('./src/app.html', import.meta.url), 'utf-8');
	return [...html.matchAll(/<script(?![^>]*\bsrc=)[^>]*>([\s\S]*?)<\/script>/gi)].map(
		(treffer) => `sha256-${createHash('sha256').update(treffer[1], 'utf8').digest('base64')}`
	);
}

/** @type {import('@sveltejs/kit').Config} */
const config = {
	compilerOptions: {
		// Force runes mode for the project, except for libraries. Can be removed in svelte 6.
		runes: ({ filename }) => (filename.split(/[/\\]/).includes('node_modules') ? undefined : true)
	},
	kit: {
		// adapter-auto only supports some environments, see https://svelte.dev/docs/kit/adapters for a list.
		// If your environment is not supported, or you settled on a specific environment, switch out the adapter.
		// See https://svelte.dev/docs/kit/adapters for more information about adapters.
		adapter: adapter({ out: 'build' }),
		// Issue #2961 (FE6): Content-Security-Policy fuer jede Seitenantwort.
		// `mode: 'auto'` = Nonce fuer dynamisch erzeugte, Hash fuer vorgerenderte
		// Seiten; SvelteKit ergaenzt seine eigenen Inline-Skripte selbst.
		// Bewusst ohne 'unsafe-eval' und ohne script-src 'unsafe-inline'.
		// style-src braucht 'unsafe-inline': Svelte (style:-Direktiven) und
		// Leaflet (Kartenkacheln, Marker) setzen Inline-Styles.
		// img-src: Kartenkacheln von OpenTopoMap (MapCanvas.svelte); data:/blob:
		// fuer eingebettete Bilder (Vite, Leaflet).
		// Die Alarm-Vorschau rendert die Mail per srcdoc-iframe; srcdoc-Dokumente
		// erben diese Richtlinie (Inline-Styles erlaubt, keine Skripte).
		csp: {
			mode: 'auto',
			directives: {
				'default-src': ['self'],
				'script-src': ['self', ...appHtmlSkriptHashes()],
				'style-src': ['self', 'unsafe-inline'],
				'img-src': ['self', 'data:', 'blob:', 'https://*.tile.opentopomap.org'],
				'connect-src': ['self'],
				'font-src': ['self', 'data:'],
				'worker-src': ['self'],
				'manifest-src': ['self'],
				'frame-src': ['self'],
				'frame-ancestors': ['none'],
				'base-uri': ['self'],
				'form-action': ['self'],
				'object-src': ['none']
			}
		}
	}
};

export default config;
