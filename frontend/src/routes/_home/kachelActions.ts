// Issue #2278 (AC-15) — Aktionsliste der Startseiten-Kachel: nur "Bearbeiten" (oeffnet den Hub).
// Bewusst NICHT aus der Listen-Tabelle: die Kachel behandelt nur `edit`, alles andere waere wirkungslos.
export function compareKachelActions(): Array<{ id: string; label: string }> {
	return [{ id: 'edit', label: 'Bearbeiten' }];
}
