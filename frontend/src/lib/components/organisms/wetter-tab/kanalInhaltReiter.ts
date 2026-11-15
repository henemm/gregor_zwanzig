// #3031 Fix-Loop 1 (F002/F003): Reiter-Logik der Karte „Inhalt je Kanal und Fläche" als reine
// Funktionen, damit die Verdrahtung Karte → Signatur → Speicherer ohne onMount pruefbar ist
// (organisms/__tests__/kanal_inhalt_3031_reiter.test.ts). WetterTabInhalt.svelte nutzt genau diese.

import type { VorlagenAmpeln } from '../../shared/wetter-tab/ampelModell.ts';
import { mengeVon, type AboSicht, type WetterStand } from '../../shared/wetter-tab/wetterZustand.ts';
import { LISTEN_KANAELE, formatAusKatalog, hatGespeicherteListen, listenAusAbo, normalisiereZeilen, type Format, type KanalListen, type KatalogEintrag, type Kontext } from './kanalInhalt.ts';

type FormatFuer = (id: string) => Format;

/** Was gespeichert wird — inkl. der Kanallisten, sonst waere jede Karten-Aenderung ein stilles No-Op. */
export function signaturVon(s: WetterStand, vorlagen: VorlagenAmpeln): string {
	return JSON.stringify([mengeVon(s, vorlagen), s.auswahl, s.warnungenAn, s.radarAn, s.tagesfenster, s.kanaele ?? null]);
}

/** Neue Signatur, wenn sich Gespeichertes geaendert hat (dann melden), sonst null. */
export function zuMelden(gemeldet: string, neu: WetterStand, vorlagen: VorlagenAmpeln): string | null {
	const sig = signaturVon(neu, vorlagen);
	return sig === gemeldet ? null : sig;
}

/** Hydration: eigene Kanallisten des Abos in den Stand (sonst erst bei Bedienung der Karte). */
export function standMitKanaelen(kontext: Kontext, s: WetterStand, abo: AboSicht, formatFuer: FormatFuer): WetterStand {
	return hatGespeicherteListen(kontext, abo) ? { ...s, kanaele: listenAusAbo(kontext, abo, s.auswahl, formatFuer) } : s;
}

/** Was die Karte zeigt: Stand der Karte (bzw. Abo) gegen die aktuelle Wetter-Auswahl normalisiert. */
export function kanalListenFuerAnzeige(kontext: Kontext, s: WetterStand, abo: AboSicht, formatFuer: FormatFuer): KanalListen {
	const basis = s.kanaele ?? listenAusAbo(kontext, abo, s.auswahl, formatFuer);
	const aus = {} as KanalListen;
	for (const k of LISTEN_KANAELE) aus[k] = normalisiereZeilen(basis[k], s.auswahl, formatFuer);
	return aus;
}

/** Beim Anlegen keine Karte: die Anlege-Seiten uebernehmen keine Kanallisten. */
export function karteSichtbar(createMode: boolean, listen: KanalListen | null): boolean {
	return !!listen && !createMode;
}

/** Format einer neu aufgenommenen Zeile = Katalog-Default der Metrik. */
export function kanalFormatAusKatalog(katalog: Record<string, unknown> | null | undefined): FormatFuer {
	return (id) => formatAusKatalog(katalog?.[id] as KatalogEintrag | undefined);
}
