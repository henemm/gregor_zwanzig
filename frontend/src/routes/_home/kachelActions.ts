// Issue #2278 (AC-15) — Aktionsliste der Startseiten-Kachel: nur "Bearbeiten" (oeffnet den Hub).
// Bewusst NICHT aus der Listen-Tabelle: die Kachel behandelt nur `edit`, alles andere waere wirkungslos.
// Issue #2346 S2: kind-neutral (Trip und Ortsvergleich teilen die Kachel).
// #2652 (i18n F3): Label beim Aufruf aus dem Katalog (aktuelle locale).
import { tr } from '../../lib/i18n/index.ts';

export function kachelActions(): Array<{ id: string; label: string }> {
	return [{ id: 'edit', label: tr('home.kachel.bearbeiten') }];
}
