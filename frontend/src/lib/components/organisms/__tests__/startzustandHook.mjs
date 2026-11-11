// ESM-Hook nur für Tests (#2913 Teil 2, Fix-Loop 1): eine Svelte-Komponente mit anderem
// STARTWERT eines `$state` serverseitig rendern, ohne den Produktivcode zu ändern.
//
// Der Server-Render führt kein onMount aus; Zweige, die erst nach einem Laden oder einem
// Klick erscheinen (z. B. die Fehler-Phase von WetterTabInhalt, das offene Vorlage-Menü),
// wären sonst im SSR unerreichbar. Der Test importiert die Komponente mit der Abfrage
// `?start=<encodeURIComponent(JSON [[alt, neu], …])>`; dieser Hook liest die ECHTE Datei,
// ersetzt jede Zeichenkette `alt` (muss genau einmal vorkommen, sonst Fehler) durch `neu` und
// übersetzt das Ergebnis wie test-svelte-ssr-hooks.mjs. Das gerenderte Markup ist damit das
// der Produktivdatei — jede Verfälschung dort (Testid, Größe) bleibt sichtbar.
//
// Relative Importe der Komponente lösen gegen die URL ohne Abfrage auf und laufen weiter über
// den regulären SSR-Hook.

import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { compile } from 'svelte/compiler';

export async function load(url, context, nextLoad) {
	const i = url.indexOf('?start=');
	if (!url.startsWith('file:') || i < 0 || !url.slice(0, i).endsWith('.svelte')) return nextLoad(url, context);
	const file = fileURLToPath(url.slice(0, i));
	const paare = JSON.parse(decodeURIComponent(url.slice(i + '?start='.length)));
	let quelle = readFileSync(file, 'utf-8');
	for (const [alt, neu] of paare) {
		const n = quelle.split(alt).length - 1;
		if (n !== 1) throw new Error(`startzustandHook: „${alt}“ kommt in ${file} ${n}-mal vor (erwartet genau einmal)`);
		quelle = quelle.replace(alt, () => neu);
	}
	const { js } = compile(quelle, { generate: 'server', filename: file });
	return { format: 'module', shortCircuit: true, source: js.code };
}
