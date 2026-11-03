// Pruefstand-Helfer (KEINE Testdatei) — Issue #2727 (Epic #2345, DoD-1).
// Spec: docs/specs/modules/feat_2727_compare_wizardstate_abloesen.md
//
// Ersetzt den frueheren Helfer `neuerWiz()` aus infoboxSsr.ts: statt einer Instanz
// der geloeschten Zustandsklasse liefert er den Feldsatz der reinen Daten-Factory
// `compareFeldsatzStandard()` (compare/compareEditorSave.ts) — dieselben Startwerte,
// ein frisches Plain-Objekt, ohne `$state`.
//
// Bewusst Namensraum-Import statt `import { compareFeldsatzStandard }`: fehlt der
// Export (RED-Phase), wuerde ein benannter Import die GANZE Testdatei beim Laden
// abbrechen (null Tests gezaehlt, auch die Positivkontrollen). So scheitert nur der
// Test, der den Feldsatz wirklich braucht — mit der Meldung `VERTRAG FEHLT`.
//
// Pfadregel #1409: relativ zu DIESER Datei.

import * as speichern from '../../compare/compareEditorSave.ts';

export const VERTRAG_FEHLT_FELDSATZ =
	'VERTRAG FEHLT (#2727): compare/compareEditorSave.ts exportiert keine Funktion ' +
	'`compareFeldsatzStandard()` (reine Daten-Factory des Ortsvergleich-Feldsatzes).';

/** Die Factory selbst — wirft LAUT, wenn der Vertrag fehlt. */
export function feldsatzFabrik(): () => Record<string, any> {
	const fabrik = (speichern as Record<string, unknown>).compareFeldsatzStandard;
	if (typeof fabrik !== 'function') throw new Error(VERTRAG_FEHLT_FELDSATZ);
	return fabrik as () => Record<string, any>;
}

/** Frischer Standard-Feldsatz, optional mit ueberschriebenen Feldern. */
export function neuerFeldsatz(felder: Record<string, unknown> = {}): Record<string, any> {
	return { ...feldsatzFabrik()(), ...felder };
}
