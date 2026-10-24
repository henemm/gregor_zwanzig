// Issue #2278 (AC-15) — Aktionsliste der Startseiten-Kachel: nur "Bearbeiten" (oeffnet den Hub).
// Bewusst NICHT aus der Listen-Tabelle: die Kachel behandelt nur `edit`, alles andere waere wirkungslos.
// Issue #2346 S2: kind-neutral (Trip und Ortsvergleich teilen die Kachel).
export function kachelActions(): Array<{ id: string; label: string }> {
	return [{ id: 'edit', label: 'Bearbeiten' }];
}
