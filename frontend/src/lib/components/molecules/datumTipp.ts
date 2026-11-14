// Issue #2999: Tipp-Protokoll des Bausteins DatumFeld.
//
// bits-ui 2.17.3 begrenzt den Tag beim Tippen auf den Bezugsmonat (heute bzw. Monat des
// gespeicherten Werts) und klemmt den Tag auf die Monatslänge im Jahr des Platzhalters
// (31.03. wird 01.03., 31.04. wird 30.04., 29.02.2028 wird 28.02.). Deshalb führt der Baustein
// einen eigenen, segmentübergreifenden Ziffernstrom: erst die 8. Ziffer legt die Absicht fest,
// `pruefeTipp` prüft sie gegen die echte Monatslänge (inkl. Schaltjahr) und klemmt nie.
// Spec: docs/specs/modules/fix_2999_datumfeld_tag_31.md
// Bewusst ohne TS-Parameter-Properties (Kernsuite strippt Typen).

export type Segment = 'day' | 'month' | 'year';

export type TippErgebnis = { ok: true; iso: string } | { ok: false };

const STANDARD: Segment[] = ['day', 'month', 'year'];
const LAENGE: Record<Segment, number> = { day: 2, month: 2, year: 4 };
const ZIFFERN = 8;

const schaltjahr = (j: number): boolean => (j % 4 === 0 && j % 100 !== 0) || j % 400 === 0;

function tageImMonat(monat: number, jahr: number): number {
	if (monat === 2) return schaltjahr(jahr) ? 29 : 28;
	return [4, 6, 9, 11].includes(monat) ? 30 : 31;
}

/** Acht Ziffern in der Segment-Reihenfolge des Felds → ISO-Datum oder ungültig (nie geklemmt). */
export function pruefeTipp(ziffern: string, reihenfolge: Segment[] = STANDARD): TippErgebnis {
	if (!/^\d{8}$/.test(ziffern)) return { ok: false };
	const teile: Partial<Record<Segment, string>> = {};
	let pos = 0;
	for (const seg of reihenfolge) {
		teile[seg] = ziffern.slice(pos, pos + LAENGE[seg]);
		pos += LAENGE[seg];
	}
	if (pos !== ZIFFERN || !teile.day || !teile.month || !teile.year) return { ok: false };
	const tag = Number(teile.day);
	const monat = Number(teile.month);
	const jahr = Number(teile.year);
	if (jahr < 1000 || monat < 1 || monat > 12 || tag < 1 || tag > tageImMonat(monat, jahr)) return { ok: false };
	return { ok: true, iso: `${teile.year}-${teile.month}-${teile.day}` };
}

/**
 * Segmentübergreifender Ziffernstrom je Fokus. Jede Nicht-Ziffer (Rücktaste, Pfeil, Tab,
 * Trennzeichen) setzt ihn zurück, ebenso `zuruecksetzen()` (Fokuswechsel, Klick).
 */
export class DatumTipp {
	#ziffern = '';

	/** null solange unvollständig; mit der 8. Ziffer das Ergebnis (danach beginnt der Strom neu). */
	taste(key: string, reihenfolge: Segment[] = STANDARD): TippErgebnis | null {
		if (!/^\d$/.test(key)) {
			this.#ziffern = '';
			return null;
		}
		this.#ziffern += key;
		if (this.#ziffern.length < ZIFFERN) return null;
		const ergebnis = pruefeTipp(this.#ziffern, reihenfolge);
		this.#ziffern = '';
		return ergebnis;
	}

	get laeuft(): boolean {
		return this.#ziffern.length > 0;
	}

	zuruecksetzen(): void {
		this.#ziffern = '';
	}
}
