// Issue #2881 Lieferung B: Melde-Regel der Segment-Felder DatumFeld und UhrzeitFeld (bits-ui).
//
// bits-ui setzt den Wert schon bei jedem getippten Segment (z. B. Tag „2" ⇒ 02, Monat „0" ⇒
// Januar, Jahr „2" ⇒ 0002) — ein natives Feld meldet erst den fertigen Wert. Deshalb:
//   * Ist das gerade getippte Segment noch unfertig (weniger Ziffern als es braucht), bleibt der
//     Wert zurück — ohne Zeitgeber (Fix-Loop F-B1: ein Ruhe-Zeitgeber liess „02.08." als PUT
//     hinaus, wenn die nächste Ziffer später kam). Er geht erst hinaus, wenn das Segment fertig
//     ist (dann sofort) oder das Feld verlassen wird.
//   * Wahl ohne Tippen (Kalender, Programm) oder fertiges Segment: sofort melden — sonst wäre ein
//     gleich danach angetippter Knopf, der am Wert hängt („Etappen anlegen"), noch gesperrt.
//   * Ein FREMDER Wertwechsel (z. B. andere Etappe gewählt) verwirft Offenes (der Baustein ruft
//     `verwerfen`). Eine eigene Sperre gegen Rückschreiben von bits-ui ist entfallen (Fix-Loop
//     F-B3): mit dieser Regel schreibt bits-ui nach einem Wechsel nichts zurück — belegt durch
//     DS-2 Etappenwechsel, GG-3 und SC-4 ohne Sperre.
// Bewusst ohne TS-Parameter-Properties (Kernsuite strippt Typen).

export class SegmentFeldMeldung {
	#melde: (wert: string) => void;
	#offen: string | null = null;

	constructor(melde: (wert: string) => void) {
		this.#melde = melde;
	}

	/** Neuer Wert aus dem Feld; `unfertig` = das getippte Segment braucht noch Ziffern. */
	aendern(wert: string, unfertig: boolean): void {
		if (unfertig) {
			this.#offen = wert;
			return;
		}
		this.#offen = null;
		this.#melde(wert);
	}

	/** Gibt es einen zurückgehaltenen Wert? */
	get offen(): boolean {
		return this.#offen !== null;
	}

	/** Offenen Wert jetzt melden (Feld verlassen). */
	abschliessen(): void {
		if (this.#offen === null) return;
		const wert = this.#offen;
		this.#offen = null;
		this.#melde(wert);
	}

	verwerfen(): void {
		this.#offen = null;
	}
}

const bedarf = (teil: string) => (teil === 'year' ? 4 : 2);
// Nur echte Ziffern-Segmente (bits-ui markiert auch Literale, AM/PM und den Kalender-Knopf
// „trigger" mit data-segment).
const ZIFFERN_TEILE = new Set(['day', 'month', 'year', 'hour', 'minute', 'second']);
const zifferTeil = (el: Element | null): string | null => {
	const teil = el?.getAttribute?.('data-segment') ?? null;
	return teil && ZIFFERN_TEILE.has(teil) ? teil : null;
};

/**
 * Zählt die im fokussierten Segment getippten Ziffern (Tastatur, und per `beforeinput` auch
 * Bildschirmtastaturen ohne Tastencode). Die Anzeige allein reicht nicht: das Uhrzeitfeld zeigt
 * „0" schon gepolstert als „00".
 */
export class TippZaehler {
	#anzahl = new WeakMap<Element, number>();
	#perTaste = false;

	#plus(seg: Element): void {
		this.#anzahl.set(seg, (this.#anzahl.get(seg) ?? 0) + 1);
	}

	taste = (e: KeyboardEvent): void => {
		const seg = e.target as Element | null;
		if (!zifferTeil(seg)) return;
		if (/^\d$/.test(e.key)) {
			this.#perTaste = true;
			this.#plus(seg!);
		} else if (e.key === 'Backspace' || e.key === 'Delete') {
			this.#anzahl.set(seg!, 0);
		}
	};

	eingabe = (e: InputEvent): void => {
		const seg = e.target as Element | null;
		if (this.#perTaste || !zifferTeil(seg) || !e.data || !/^\d$/.test(e.data)) return;
		this.#plus(seg!);
	};

	loslassen = (): void => {
		this.#perTaste = false;
	};

	fokus = (e: FocusEvent): void => {
		const seg = e.target as Element | null;
		if (zifferTeil(seg)) this.#anzahl.set(seg!, 0);
	};

	/** Hat das fokussierte Segment in `feld` angefangene, aber noch nicht genug Ziffern? */
	unfertig(feld: HTMLElement | null): boolean {
		const aktiv = typeof document === 'undefined' ? null : document.activeElement;
		const teil = zifferTeil(aktiv);
		if (!(feld && aktiv && teil && feld.contains(aktiv))) return false;
		const n = this.#anzahl.get(aktiv) ?? 0;
		return n > 0 && n < bedarf(teil);
	}
}

/**
 * Ist in `feld` irgendein Ziffern-Segment leer oder angefangen (z. B. Stunde nach Rücktaste „––")?
 * bits-ui meldet das Leeren eines Uhrzeit-Segments nicht immer als leeren Wert — beim Verlassen
 * zählt deshalb, was im Feld steht.
 */
export function segmenteUnvollstaendig(feld: HTMLElement | null): boolean {
	if (!feld) return false;
	return Array.from(feld.querySelectorAll('[data-segment]')).some((el) => {
		const teil = zifferTeil(el);
		return !!teil && (el.textContent ?? '').replace(/\D/g, '').length < bedarf(teil);
	});
}

/**
 * Zeigt das fokussierte Segment in `feld` weniger Ziffern als es braucht (z. B. Tag „2",
 * Jahr „20")? Zusatzprüfung zum TippZaehler; bits-ui zeigt ein angefangenes Datumssegment
 * ungepolstert an.
 */
export function tipptIn(feld: HTMLElement | null): boolean {
	const aktiv = typeof document === 'undefined' ? null : document.activeElement;
	const teil = zifferTeil(aktiv);
	if (!(feld && aktiv && teil && feld.contains(aktiv))) return false;
	return (aktiv.textContent ?? '').replace(/\D/g, '').length < bedarf(teil);
}
