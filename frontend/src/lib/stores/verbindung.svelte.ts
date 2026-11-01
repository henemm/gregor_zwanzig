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

import { api } from '../api.ts';

/** Ereignisnamen, ueber die `$lib/api.ts` den Ausgang eines Abrufs meldet. */
export const ABRUF_GELUNGEN = 'gz-abruf-gelungen';
// Ereignisname = Protokoll, kein Nutzertext (Ratsche #2660: Marker i18n-log).
export const ABRUF_FEHLGESCHLAGEN = 'gz-abruf-fehlgeschlagen'; // i18n-log

// Issue #2361: Probe gegen die Sperr-Sackgasse. Das Zeitlimit in `api.ts` kann
// einen langsamen, aber erreichbaren Server als „offline" melden; entsperrt wird
// nur durch einen GELUNGENEN Abruf — den eine gesperrte Oberflaeche nicht mehr
// ausloest. Solange offline UND die Seite sichtbar ist, geht deshalb alle 15 s
// ein `GET /api/health` ueber `api.ts`; gelingt er, meldet `api.ts`
// `gz-abruf-gelungen` und der Store entsperrt sich. 15 s: zuegiges Entsperren
// nach Rueckkehr der Verbindung, im Funkloch vernachlaessigbare Last.
export const PROBE_INTERVALL_MS = 15_000;
let probeIntervallMs = PROBE_INTERVALL_MS;

/** Nur fuer Tests: verkuerzt das Probe-Intervall. */
export function setzeProbeIntervall(ms: number): void {
	probeIntervallMs = ms;
}

function seiteSichtbar(): boolean {
	return typeof document === 'undefined' || document.visibilityState === 'visible';
}

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

	/** Laufendes Probe-Intervall (#2361); hoechstens eines. */
	#probe: ReturnType<typeof setInterval> | null = null;

	/** Ein Probe-Abruf ist unterwegs — kein zweiter daneben. */
	#probeUnterwegs = false;

	/**
	 * Start/Stopp aus den Ereignis-Handlern, nicht aus einem `$effect`: ein Store
	 * ausserhalb einer Komponente hat keinen Effekt-Besitzer.
	 */
	#probeAbgleichen(): void {
		const noetig = this.offline && seiteSichtbar();
		if (noetig && this.#probe === null) {
			this.#probe = setInterval(() => this.#probeSenden(), probeIntervallMs);
		} else if (!noetig && this.#probe !== null) {
			clearInterval(this.#probe);
			this.#probe = null;
		}
	}

	#probeSenden(): void {
		if (this.#probeUnterwegs) return;
		this.#probeUnterwegs = true;
		// Den Ausgang meldet `api.ts` selbst (gelungen/fehlgeschlagen) —
		// hier wird nur der Fehler geschluckt.
		api
			.get('/api/health')
			.catch(() => {})
			.finally(() => {
				this.#probeUnterwegs = false;
			});
	}

	starte(): void {
		if (typeof window === 'undefined' || this.#gestartet) return;
		this.#gestartet = true;
		// Ausgangslage: `navigator.onLine === false` ist die Geraetemeldung
		// bereits vor dem ersten Ereignis.
		if (navigator.onLine === false) this.offline = true;
		window.addEventListener('offline', () => {
			this.offline = true;
			this.#probeAbgleichen();
		});
		window.addEventListener(ABRUF_FEHLGESCHLAGEN, () => {
			this.offline = true;
			this.#probeAbgleichen();
		});
		window.addEventListener(ABRUF_GELUNGEN, () => {
			this.offline = false;
			this.#probeAbgleichen();
		});
		if (typeof document !== 'undefined') {
			document.addEventListener('visibilitychange', () => this.#probeAbgleichen());
		}
		this.#probeAbgleichen();
	}
}

export const verbindung = new Verbindung();
