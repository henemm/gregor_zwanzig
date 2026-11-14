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
/**
 * #2999 F005: Endet ein Strom ungültig, darf kein Zwischenstand dieses Stroms gespeichert bleiben
 * (AC-5). Ein stimmiger Zwischenstand (z. B. 31.05. nach „31" bei Basis 15.05.) geht nach DS-2
 * hinaus; weicht der Modellwert jetzt vom Wert zu Strombeginn ab, wird dieser zurückgemeldet.
 * Rückgabe: der zurückzumeldende Wert oder null (nichts ging hinaus, Strombeginn unbekannt).
 */
export function ruecknahmeNachUngueltig(wertVorStrom: string | null, aktuellerWert: string): string | null {
	if (wertVorStrom === null || wertVorStrom === aktuellerWert) return null;
	return wertVorStrom;
}

export class DatumTipp {
	#ziffern = '';
	#reihenfolge: Segment[] = STANDARD;
	#wertVorStrom: string | null = null;

	/**
	 * null solange unvollständig; mit der 8. Ziffer das Ergebnis (danach beginnt der Strom neu).
	 * `modellwert`: der Wert des Felds (`YYYY-MM-DD` oder ''); die Ziffer, die einen Strom beginnt,
	 * merkt ihn als `wertVorStrom` (#2999 F005).
	 */
	taste(key: string, reihenfolge: Segment[] = STANDARD, modellwert?: string): TippErgebnis | null {
		if (!/^\d$/.test(key)) {
			this.#ziffern = '';
			return null;
		}
		if (this.#ziffern === '') this.#wertVorStrom = modellwert ?? null;
		this.#reihenfolge = reihenfolge;
		this.#ziffern += key;
		if (this.#ziffern.length < ZIFFERN) return null;
		const ergebnis = pruefeTipp(this.#ziffern, reihenfolge);
		this.#ziffern = '';
		return ergebnis;
	}

	get laeuft(): boolean {
		return this.#ziffern.length > 0;
	}

	/** Modellwert zu Beginn des laufenden bzw. zuletzt beendeten Stroms (null: nicht übergeben). */
	get wertVorStrom(): string | null {
		return this.#wertVorStrom;
	}

	/**
	 * Weicht ein gemeldeter Wert (`YYYY-MM-DD`) von den bisher getippten Ziffern des Stroms ab
	 * (bits-ui hat geklemmt oder ist verrutscht, z. B. Tag 31 → 30, oder „3" im Februar sofort
	 * als Tag 03 abgeschlossen)? Ein angefangenes Segment muss mit seinen Ziffern beginnen.
	 * Nur dann ist er ein verfälschter Zwischenstand; stimmt er, gilt die bisherige Regel (DS-2).
	 */
	widerspricht(iso: string): boolean {
		const [jahr, monat, tag] = iso.split('-');
		const gemeldet: Record<Segment, string> = { day: tag ?? '', month: monat ?? '', year: jahr ?? '' };
		let pos = 0;
		for (const seg of this.#reihenfolge) {
			const getippt = this.#ziffern.slice(pos, pos + LAENGE[seg]);
			if (!getippt) return false;
			if (!gemeldet[seg].startsWith(getippt)) return true;
			pos += LAENGE[seg];
		}
		return false;
	}

	zuruecksetzen(): void {
		this.#ziffern = '';
	}
}
