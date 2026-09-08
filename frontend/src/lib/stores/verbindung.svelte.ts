// Verbindungszustand (Issue #2131, Spec Abschnitt H, Stufe 2).
//
// ASYMMETRISCH und in beide Richtungen fail-closed:
//
//   * SPERREN meldet das `offline`-Ereignis des Geraets. Als NEGATIVES Signal
//     ist es verlaesslich — sagt das Geraet, es habe keine Verbindung, hat es
//     keine. Auf den ersten fehlgeschlagenen Abruf zu warten waere falsch:
//     dieser Abruf waere der Schreibversuch, der nach AC-10 gerade nicht ins
//     Leere laufen darf.
//   * SPERREN tut ebenso jeder tatsaechlich fehlgeschlagene Abruf (api.ts).
//     Das faengt die Lage ab, in der das Geraet eine Verbindung meldet, aber
//     niemand antwortet (Funkloch mit eingebuchtem Netz, Anmeldeportal im WLAN).
//   * ENTSPERREN tut das `online`-Ereignis ausdruecklich NICHT. Als positives
//     Signal ist es untauglich: `navigator.onLine` meldet nur eine vorhandene
//     Netzwerkschnittstelle, nicht einen erreichbaren Server. Entsperrt wird
//     erst, wenn ein Abruf nachweislich GELUNGEN ist.

/** Ereignisnamen, ueber die `$lib/api.ts` den Ausgang eines Abrufs meldet. */
export const ABRUF_GELUNGEN = 'gz-abruf-gelungen';
export const ABRUF_FEHLGESCHLAGEN = 'gz-abruf-fehlgeschlagen';

class Verbindung {
	/** Das Netz ist nachweislich weg (Geraetemeldung oder gescheiterter Abruf). */
	offline = $state(false);

	/** Die gezeigte Ansicht stammt aus dem Gerätespeicher (Stufe 1, statisch). */
	ausSpeicher = $state(false);

	/** Sperrgrund vorhanden? Eine der beiden Stufen genuegt. */
	get gesperrt(): boolean {
		return this.offline || this.ausSpeicher;
	}

	/** Lauschen ist einmalig — ein Wiedereinhaengen doppelte nur die Zuhoerer. */
	#gestartet = false;

	starte(): void {
		if (typeof window === 'undefined' || this.#gestartet) return;
		this.#gestartet = true;
		// Ausgangslage: `navigator.onLine === false` ist die Geraetemeldung
		// bereits vor dem ersten Ereignis.
		if (navigator.onLine === false) this.offline = true;
		window.addEventListener('offline', () => {
			this.offline = true;
		});
		window.addEventListener(ABRUF_FEHLGESCHLAGEN, () => {
			this.offline = true;
		});
		window.addEventListener(ABRUF_GELUNGEN, () => {
			this.offline = false;
		});
	}
}

export const verbindung = new Verbindung();
