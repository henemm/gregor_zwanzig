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
//   * Ein Wert gleich dem gespeicherten verwirft Offenes (`verwerfen`) — das deckt auch die
//     Rücknahme nach gescheitertem Speichern ab (bits-ui setzt den zurückgenommenen Wert). Eine
//     eigene Sperre beim fremden Wertwechsel war wirkungslos (Fix-Loop 2, Mutation) und entfiel.
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

	/**
	 * Feld verlassen (#2947). Berührt und unvollständig (Segment „––") ⇒ geleert: ein
	 * zurückgehaltener Zwischenwert (z. B. „01:00" nach der ersten Rücktaste aus 15:00) wird
	 * verworfen, nie gemeldet; mit `leerMelden` und gespeichertem Wert wird einmal '' gemeldet.
	 * Sonst wie `abschliessen()`. Rückgabe true = geleert verlassen.
	 */
	verlassen(o: { beruehrt: boolean; unvollstaendig: boolean; leerMelden: boolean; gespeichert: string }): boolean {
		if (o.beruehrt && o.unvollstaendig) {
			this.#offen = null;
			if (o.leerMelden && o.gespeichert !== '') this.#melde('');
			return true;
		}
		this.abschliessen();
		return false;
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
 * Zählt die im fokussierten Segment getippten Ziffern — über `keydown`, denselben Weg, über den
 * bits-ui die Ziffern selbst annimmt. Die Anzeige taugt dafür nicht (das Uhrzeitfeld zeigt „0"
 * schon gepolstert als „00"). Fokus auf ein Segment setzt dessen Zähler zurück: wer später in ein
 * fertiges Segment zurückkehrt und „1" tippt, hat ein angefangenes Segment, kein fertiges.
 */
export class TippZaehler {
	#anzahl = new WeakMap<Element, number>();
	/** Segment per Rücktaste angefasst und noch nicht wieder voll getippt. */
	#geloescht = new WeakSet<Element>();

	taste = (e: KeyboardEvent): void => {
		const seg = e.target as Element | null;
		const teil = zifferTeil(seg);
		if (!teil) return;
		if (/^\d$/.test(e.key)) {
			const n = (this.#anzahl.get(seg!) ?? 0) + 1;
			this.#anzahl.set(seg!, n);
			if (n >= bedarf(teil)) this.#geloescht.delete(seg!);
		} else if (e.key === 'Backspace' || e.key === 'Delete') {
			this.#anzahl.set(seg!, 0);
			this.#geloescht.add(seg!);
		}
	};

	fokus = (e: FocusEvent): void => {
		const seg = e.target as Element | null;
		if (!zifferTeil(seg)) return;
		this.#anzahl.set(seg!, 0);
		this.#geloescht.delete(seg!);
	};

	/** Ist das fokussierte Segment in `feld` angefangen (zu wenige Ziffern oder per Rücktaste gekürzt)? */
	unfertig(feld: HTMLElement | null): boolean {
		const aktiv = typeof document === 'undefined' ? null : document.activeElement;
		const teil = zifferTeil(aktiv);
		if (!(feld && aktiv && teil && feld.contains(aktiv))) return false;
		const n = this.#anzahl.get(aktiv) ?? 0;
		return this.#geloescht.has(aktiv) || (n > 0 && n < bedarf(teil));
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
