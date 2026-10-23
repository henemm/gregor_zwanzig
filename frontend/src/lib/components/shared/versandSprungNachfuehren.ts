// Issue #1743 F002: Der Sprung zum Versand-Abschnitt (`#versand`) darf nicht einmalig
// bleiben — der Wetter-Metriken-Inhalt OBERHALB laedt danach nach (Kataloge) und
// schob den Abschnitt aus dem Blick. Darum wird die Lage je Bild verglichen
// (getBoundingClientRect().top) und bei Verschiebung neu ausgerichtet. Ein
// ResizeObserver taugt hier nicht: die Section waechst nicht (sie wandert nur), und
// der Baustein hat keinen eigenen Behaelter mit Box.
// Schluss bei erster Nutzer-Absicht (Capture auf document; bewusst NICHT `scroll`,
// das loest das eigene scrollIntoView selbst aus), bei der Obergrenze oder beim
// Aufraeumen (Rueckgabewert, im `$effect`-Return des Panels).
import { tick } from 'svelte';

export const NUTZER_ABSICHT =['wheel', 'touchstart', 'keydown', 'pointerdown'] as const;
export const NACHFUEHR_OBERGRENZE_MS = 8_000;

export interface NachfuehrZiel {
	getBoundingClientRect(): { top: number };
	scrollIntoView?(opts?: ScrollIntoViewOptions): void;
}

export interface NachfuehrUmgebung {
	frame: (cb: () => void) => number;
	frameAbbrechen: (id: number) => void;
	dokument: Pick<Document, 'addEventListener' | 'removeEventListener'>;
	timer: (cb: () => void, ms: number) => unknown;
	timerAbbrechen: (id: unknown) => void;
}

function browserUmgebung(): NachfuehrUmgebung {
	return {
		frame: (cb) => requestAnimationFrame(cb),
		frameAbbrechen: (id) => cancelAnimationFrame(id),
		dokument: document,
		timer: (cb, ms) => setTimeout(cb, ms),
		timerAbbrechen: (id) => clearTimeout(id as ReturnType<typeof setTimeout>)
	};
}

export function versandSprungNachfuehren(
	ziel: NachfuehrZiel,
	umgebung: NachfuehrUmgebung = browserUmgebung(),
	obergrenzeMs = NACHFUEHR_OBERGRENZE_MS
): () => void {
	const ausrichten = () => {
		ziel.scrollIntoView?.({ block: 'start' });
		return ziel.getBoundingClientRect().top;
	};
	let aktiv = true;
	let frameId: number | null = null;
	let timerId: unknown = null;

	const beenden = () => {
		if (!aktiv) return;
		aktiv = false;
		if (frameId !== null) umgebung.frameAbbrechen(frameId);
		umgebung.timerAbbrechen(timerId);
		for (const typ of NUTZER_ABSICHT) umgebung.dokument.removeEventListener(typ, beenden, true);
	};

	// Soll-Lage = tatsaechlich erreichte Lage (am Seitenende kann `start` nicht ganz
	// oben landen); nur eine Abweichung davon loest die Neuausrichtung aus.
	let soll = ausrichten();
	const pruefen = () => {
		if (!aktiv) return;
		if (Math.abs(ziel.getBoundingClientRect().top - soll) > 1) soll = ausrichten();
		frameId = umgebung.frame(pruefen);
	};

	for (const typ of NUTZER_ABSICHT) {
		umgebung.dokument.addEventListener(typ, beenden, { capture: true, passive: true });
	}
	timerId = umgebung.timer(beenden, obergrenzeMs);
	frameId = umgebung.frame(pruefen);
	return beenden;
}

/** Einstieg des Panels: erst nach `tick()` starten (Baustein frisch gemountet);
 *  wird vorher aufgeraeumt, startet das Nachfuehren gar nicht. */
export function versandSprungNachTick(
	ziel: NachfuehrZiel,
	warten: () => Promise<unknown> = tick,
	umgebung?: NachfuehrUmgebung
): () => void {
	let beendet = false;
	let aufraeumen = () => {};
	void warten().then(() => {
		if (!beendet) aufraeumen = versandSprungNachfuehren(ziel, umgebung);
	});
	return () => {
		beendet = true;
		aufraeumen();
	};
}
