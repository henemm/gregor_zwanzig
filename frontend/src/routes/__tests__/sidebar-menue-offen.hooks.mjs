// ESM-Hook fuer den F4-Sprachtest (Issue #2653): das Benutzer-Menue der Sidebar
// (Konto, System-Status, Hell/Dunkel, Abmelden) ist im SSR-Render immer zu
// (`userMenuOpen` startet mit `false`), seine Texte waeren unbeobachtbar.
// NUR der Startwert wird schaltbar: `globalThis.__gzSidebarMenueOffen === true`
// oeffnet das Menue fuer die naechste Instanz; ohne Schalter bleibt alles wie
// im Original (Golden unveraendert). Sidebar laeuft sonst echt. Findet der Hook
// das Muster nicht genau einmal, bricht er ab, statt still vakuum-gruen zu werden.

import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { compile } from 'svelte/compiler';

const MUSTER = 'let userMenuOpen = $state(false);';
const ERSATZ = 'let userMenuOpen = $state(globalThis.__gzSidebarMenueOffen === true);';

export async function load(url, context, nextLoad) {
	if (url.startsWith('file:') && url.endsWith('/lib/components/ui/sidebar/Sidebar.svelte')) {
		const file = fileURLToPath(url);
		const quelle = readFileSync(file, 'utf-8');
		if (quelle.split(MUSTER).length !== 2) {
			throw new Error(`sidebar-menue-offen.hooks: Muster "${MUSTER}" nicht genau einmal in ${file}`);
		}
		const { js } = compile(quelle.replace(MUSTER, ERSATZ), { generate: 'server', filename: file });
		return { format: 'module', shortCircuit: true, source: js.code };
	}
	return nextLoad(url, context);
}
