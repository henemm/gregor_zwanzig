// Issue #2317 Baustein 3 — Anzeige nach dem Browser-Neuladen.
// Spec: docs/specs/modules/speicherung_beim_neuladen.md § Baustein 3, AC-8..AC-11
//
// Ging beim Entladen eine Speicherung per keepalive raus, kann die neu geladene
// Seite trotzdem noch den alten Stand zeigen: der Seitenaufbau-GET und der
// Speicher-PUT haben keine garantierte Reihenfolge. Die Detailseite startet
// deshalb beim Mount diesen Baustein: nur bei einem Merker fuer GENAU diese
// Kennung holt er bis zu 6-mal im Abstand von 500 ms den Server-Stand und
// uebernimmt eine abweichende Fassung — nie, wenn der Nutzer seit dem Laden
// selbst etwas geaendert hat.
//
// Ein Baustein fuer Trip UND Ortsvergleich (Code-Teilung); nur die Quelle
// unterscheidet sich (Trip: ETag, Ortsvergleich: Inhalts-Fingerabdruck).
// BEWUSST svelte-frei — unter node:test ladbar.

import type { SaveStatus } from './saveStatusStore.svelte.ts';
import { nimmSpeicherungBeimEntladen, type NachladeKennung } from '../pwa/geraetespeicher.ts';
import { api, getMitFassung } from '../api.ts';

export const NACHLADE_VERSUCHE = 6;
export const NACHLADE_ABSTAND_MS = 500;

export interface NachladeZeitgeber {
	setTimeout(fn: () => void, ms: number): unknown;
	clearTimeout(handle: unknown): void;
}

export interface NachladeAntwort<T> {
	stand: T;
	fassung: string;
}

export interface NachladeOptionen<T> {
	kennung: NachladeKennung;
	ctl: SaveStatus;
	/** Fassung, die der Seitenaufbau ausgeliefert hat. */
	ausgelieferteFassung: string | undefined;
	holen: () => Promise<NachladeAntwort<T>>;
	uebernehmen: (stand: T, fassung: string) => void;
	zeitgeber?: NachladeZeitgeber;
}

const echterZeitgeber: NachladeZeitgeber = {
	setTimeout: (fn, ms) => setTimeout(fn, ms),
	clearTimeout: (h) => clearTimeout(h as ReturnType<typeof setTimeout>)
};

/**
 * Hat der Nutzer seit dem Start etwas geaendert? Einmal ja, immer ja (AC-8 b:
 * auch eine inzwischen gespeicherte Eingabe zaehlt). Signale: eine ausstehende
 * Speicherung, ein neuer Gespeichert-Zeitstempel oder ein laufender/gescheiterter
 * Speichervorgang. `dirty` allein zaehlt bewusst NICHT — das setzen Reiter auch
 * ohne Speicherung (Gate „skip"), und es darf die Anzeige-Korrektur nicht still
 * abschalten.
 */
function aenderungsWaechter(ctl: SaveStatus): () => boolean {
	const savedAtStart = ctl.savedAt;
	let geaendert = false;
	return () => {
		if (
			ctl.hasPending ||
			ctl.savedAt !== savedAtStart ||
			ctl.state === 'saving' ||
			ctl.state === 'error' ||
			ctl.state === 'conflict'
		) {
			geaendert = true;
		}
		return geaendert;
	};
}

export function starteNachladenNachEntladen<T>(o: NachladeOptionen<T>): {
	stoppen(): void;
	fertig: Promise<void>;
} {
	let aufloesen!: () => void;
	const fertig = new Promise<void>((r) => {
		aufloesen = r;
	});
	if (!nimmSpeicherungBeimEntladen(o.kennung)) {
		aufloesen();
		return { stoppen() {}, fertig };
	}
	const zeit = o.zeitgeber ?? echterZeitgeber;
	const nutzerHatGeaendert = aenderungsWaechter(o.ctl);
	let beendet = false;
	let handle: unknown = null;
	let versuche = 0;

	function beenden(): void {
		if (beendet) return;
		beendet = true;
		if (handle !== null) zeit.clearTimeout(handle);
		handle = null;
		aufloesen();
	}

	async function versuch(): Promise<void> {
		handle = null;
		if (beendet) return;
		nutzerHatGeaendert();
		versuche++;
		try {
			const antwort = await o.holen();
			if (beendet) return;
			// Eine neue Eingabe (auch eine schon gespeicherte) wird nie ueberschrieben (AC-8).
			if (nutzerHatGeaendert()) return beenden();
			if (antwort.fassung && antwort.fassung !== o.ausgelieferteFassung) {
				o.uebernehmen(antwort.stand, antwort.fassung);
				return beenden();
			}
		} catch {
			if (beendet) return;
		}
		if (versuche >= NACHLADE_VERSUCHE) return beenden();
		handle = zeit.setTimeout(() => void versuch(), NACHLADE_ABSTAND_MS);
	}

	void versuch();
	return { stoppen: beenden, fertig };
}

/**
 * Trip-Quelle: GET ueber `api`, Fassung = ETag DIESER Antwort. `api.ts` legt ihn
 * selbst in die Registry (`setKnownEtagIfUnchanged`) — genau der Stempel, den
 * die naechste Speicherung als If-Match braucht (AC-11); ein zusaetzliches
 * Setzen bei der Uebernahme waere redundant. Hat die Registry ihn NICHT
 * uebernommen (ein anderer Vorgang hat den Eintrag waehrend des GET veraendert),
 * gilt der Versuch als gescheitert: sonst passte die angezeigte Fassung nicht zum
 * If-Match der naechsten Speicherung. Der naechste Versuch holt neu.
 */
export function tripNachladeQuelle<T = unknown>(tripId: string): () => Promise<NachladeAntwort<T>> {
	return async () => {
		const { daten, etag, inRegistry } = await getMitFassung<T>(`/api/trips/${encodeURIComponent(tripId)}`);
		if (!etag || !inRegistry) throw new Error('Nachladen: Fassung passt nicht zur Registry');
		return { stand: daten, fassung: etag };
	};
}

/** Inhalts-Fingerabdruck mit sortierten Schluesseln (Ortsvergleich hat keinen ETag im Seitenaufbau). */
export function inhaltsFassung(wert: unknown): string {
	return JSON.stringify(wert, (_k, v: unknown) =>
		v && typeof v === 'object' && !Array.isArray(v)
			? Object.fromEntries(Object.entries(v as Record<string, unknown>).sort(([a], [b]) => (a < b ? -1 : a > b ? 1 : 0)))
			: v
	);
}

/** Ortsvergleich-Quelle: GET des Presets, Fassung = Inhalts-Fingerabdruck. */
export function vergleichNachladeQuelle<T = unknown>(presetId: string): () => Promise<NachladeAntwort<T>> {
	return async () => {
		const stand = await api.get<T>(`/api/compare/presets/${encodeURIComponent(presetId)}`);
		return { stand, fassung: inhaltsFassung(stand) };
	};
}
