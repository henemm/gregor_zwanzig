// Issue #2961 (FE1) — Inhalt der Wegpunkt-Sprechblase auf der Karte.
//
// Leaflet setzt einen als Zeichenkette uebergebenen Popup-Inhalt als HTML ein.
// Wegpunktnamen stammen aber aus Nutzereingaben und importierten GPX-Dateien,
// sind also beliebiger Text. Darum bekommt Leaflet hier einen fertigen
// DOM-Knoten, dessen Text ausschliesslich ueber `textContent` gesetzt wird:
// der Name erscheint immer woertlich, nie als Auszeichnung.

/** Das Einzige, was der Baustein vom Dokument braucht. */
export type KnotenFabrik = Pick<Document, 'createElement'>;

/** Sichtbarer Text der Sprechblase: laufende Nummer und Name. */
export function popupText(nummer: number, name: string | null | undefined): string {
	return `${nummer}. ${name ?? ''}`;
}

/** DOM-Knoten fuer `bindPopup` — Text, nie HTML. */
export function popupKnoten(
	dokument: KnotenFabrik,
	nummer: number,
	name: string | null | undefined
): HTMLElement {
	const knoten = dokument.createElement('span');
	knoten.textContent = popupText(nummer, name);
	return knoten;
}
