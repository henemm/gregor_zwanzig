// Issue #2881 Lieferung B: Melde-Regel der Segment-Felder DatumFeld und UhrzeitFeld (bits-ui).
//
// bits-ui setzt den Wert schon bei jedem getippten Segment (z. B. Monat „0" ⇒ Januar, Jahr „2" ⇒
// 0002) — ein natives Feld meldet erst den fertigen Wert. Deshalb:
//   * Tippen in einem noch unfertigen Segment (Monat „0", Jahr „20"): Wert erst nach kurzer Ruhe
//     melden, beim Verlassen des Felds sofort; ist das Segment fertig, sofort melden.
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

/**
 * Wird in `feld` gerade ein Segment getippt, das noch nicht fertig ist (z. B. Monat „0", Jahr „20")?
 * Nur dann wird die Meldung zurückgehalten; ein fertiges Segment meldet sofort — sonst wäre ein
 * gleich danach angetippter Knopf, der am Wert hängt („Etappen anlegen"), noch gesperrt.
 */
export function tipptIn(feld: HTMLElement | null): boolean {
	const aktiv = typeof document === 'undefined' ? null : document.activeElement;
	if (!(feld && aktiv && feld.contains(aktiv))) return false;
	const teil = aktiv.getAttribute('data-segment');
	if (!teil || teil === 'literal' || teil === 'dayPeriod') return false;
	const ziffern = (aktiv.textContent ?? '').replace(/\D/g, '').length;
	return ziffern < (teil === 'year' ? 4 : 2);
}
