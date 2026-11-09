// Issue #2881 Lieferung B: Melde-Regel der Segment-Felder DatumFeld und UhrzeitFeld (bits-ui).
//
// bits-ui setzt den Wert schon bei jedem getippten Segment (z. B. Monat „0" ⇒ Januar, Jahr „2" ⇒
// 0002) — ein natives Feld meldet erst den fertigen Wert. Deshalb:
//   * Tippen im Feld (Fokus auf einem Segment): Wert erst nach kurzer Ruhe melden, beim Verlassen
//     des Felds sofort; Zwischenstände gehen nie nach außen.
//   * Wahl ohne Tippen (Kalender, Programm): sofort melden.
//   * Ein FREMDER Wertwechsel (z. B. andere Etappe gewählt) verwirft Offenes und sperrt bis zum
//     nächsten Takt — bits-ui schreibt sonst die zuletzt getippten Segmente in den neuen Wert zurück.
// Bewusst ohne TS-Parameter-Properties (Kernsuite strippt Typen).

export class SegmentFeldMeldung {
	#melde: (wert: string) => void;
	#ruheMs: number;
	#timer: ReturnType<typeof setTimeout> | null = null;
	#offen: string | null = null;
	#gesperrt = false;

	constructor(melde: (wert: string) => void, ruheMs = 300) {
		this.#melde = melde;
		this.#ruheMs = ruheMs;
	}

	/** Neuer Wert aus dem Feld; `tippt` = Fokus liegt auf einem Segment. */
	aendern(wert: string, tippt: boolean): void {
		if (this.#gesperrt) return;
		if (!tippt) {
			this.verwerfen();
			this.#melde(wert);
			return;
		}
		this.#offen = wert;
		if (this.#timer) clearTimeout(this.#timer);
		this.#timer = setTimeout(() => this.abschliessen(), this.#ruheMs);
	}

	/** Offenen Wert sofort melden (Feld verlassen, Ruhezeit um). */
	abschliessen(): void {
		if (this.#timer) clearTimeout(this.#timer);
		this.#timer = null;
		if (this.#offen === null) return;
		const wert = this.#offen;
		this.#offen = null;
		this.#melde(wert);
	}

	verwerfen(): void {
		if (this.#timer) clearTimeout(this.#timer);
		this.#timer = null;
		this.#offen = null;
	}

	/** Fremder Wertwechsel: Offenes verwerfen, bis `freigeben()` nichts annehmen. */
	sperren(): void {
		this.verwerfen();
		this.#gesperrt = true;
	}

	freigeben(): void {
		this.#gesperrt = false;
	}
}

/** Liegt der Fokus auf einem Segment innerhalb von `feld`? */
export function tipptIn(feld: HTMLElement | null): boolean {
	const aktiv = typeof document === 'undefined' ? null : document.activeElement;
	return !!(feld && aktiv && feld.contains(aktiv) && aktiv.hasAttribute('data-segment'));
}
