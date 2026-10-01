// ESM-Hook fuer den SSR-Test der isAdmin-Durchreichung +layout.svelte -> KontoSheet
// (Issue #2155 S4, Adversary-Finding F002).
//
// Problem: das Layout haelt `kontoOpen` als eigenen Zustand (Start `false`); im
// SSR-Render ist das Konto-Sheet daher immer zu, und `mobile/Sheet.svelte` gibt
// seinen Inhalt nicht aus. Ob das Layout `isAdmin` korrekt an KontoSheet
// weitergibt, waere so unbeobachtbar.
//
// Loesung: NUR die Sichtbarkeits-Bedingung des generischen Bottom-Sheets wird
// auf "offen" gestellt. Layout und KontoSheet bleiben unveraendert und echt —
// geprueft wird der gerenderte Sheet-Inhalt, also die Stelle, an der die
// Weitergabe wirkt. Findet der Hook das Muster nicht mehr, bricht er ab, statt
// den Test still vakuum-gruen werden zu lassen.

import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { compile } from 'svelte/compiler';

const MUSTER = "{#if open || variant === 'embedded'}";

export async function load(url, context, nextLoad) {
	if (url.startsWith('file:') && url.endsWith('/lib/components/mobile/Sheet.svelte')) {
		const file = fileURLToPath(url);
		const quelle = readFileSync(file, 'utf-8');
		if (quelle.split(MUSTER).length !== 2) {
			throw new Error(`konto-sheet-offen.hooks: Muster "${MUSTER}" nicht genau einmal in ${file}`);
		}
		const { js } = compile(quelle.replace(MUSTER, '{#if true}'), {
			generate: 'server',
			filename: file
		});
		return { format: 'module', shortCircuit: true, source: js.code };
	}
	return nextLoad(url, context);
}
