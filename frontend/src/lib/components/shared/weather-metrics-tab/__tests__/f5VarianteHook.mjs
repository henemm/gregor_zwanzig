// Issue #2654 (i18n F5, Epic #2644) — ESM-Hook des Pruefstands (nicht ausgeliefert).
// Bauart wie F8 (#2657, layout-tab/__tests__/f8VarianteHook.mjs): der Wertebereiche-
// Reiter setzt Katalog, Lade- und Fehlerzustand erst in `$effect`-Bloecken, die beim
// SSR-Render nie laufen. Damit der ECHTE Markup-Quelltext trotzdem in diesen
// Zustaenden gerendert werden kann, laedt dieser Hook eine Komponente mit der
// Abfrage `?f5variante=<base64url-JSON>`: genau benannte `$state`-Startwerte werden
// per exakter String-Ersetzung auf einen Wert aus `globalThis` umgelenkt (jede
// Ersetzung muss GENAU EINMAL passen, sonst Abbruch). Alles andere — Markup,
// Kataloge, Helfer, Imports — bleibt der unveraenderte Quelltext.
// Spec: docs/specs/modules/i18n_f5_wertebereiche_tab_2654.md

import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { compile } from 'svelte/compiler';

const MARKE = '?f5variante=';

export async function load(url, context, nextLoad) {
	const i = url.indexOf(MARKE);
	if (i < 0) return nextLoad(url, context);
	const datei = fileURLToPath(url.slice(0, i));
	const ersetzungen = JSON.parse(Buffer.from(url.slice(i + MARKE.length), 'base64url').toString('utf8'));
	let quelle = readFileSync(datei, 'utf-8');
	for (const [alt, neu] of ersetzungen) {
		const n = quelle.split(alt).length - 1;
		if (n !== 1) throw new Error(`f5variante: „${alt}" steht ${n}x in ${datei} (erwartet genau 1)`);
		quelle = quelle.replace(alt, () => neu);
	}
	const { js } = compile(quelle, { generate: 'server', filename: datei });
	return { format: 'module', shortCircuit: true, source: js.code };
}
