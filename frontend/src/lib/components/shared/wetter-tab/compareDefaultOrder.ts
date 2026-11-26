// Issue #2989: Mail-Standardfolge der Vergleichs-Schluessel (`default_order` der
// Katalog-Antwort) — einzige Quelle fuer „nie eingestellt = alle Groessen". Modulweit,
// sprachunabhaengig; `null` bis eine Antwort da ist.
//
// Bewusst OHNE Importe: die reinen Ableitungen (compareMetricOrder.ts, ampelSchreiben.ts)
// lesen hier, ohne den Katalog-Lader samt API-Client (`$lib/api`, Seiteneffekt auf
// `window` beim Laden) in ihren Importgraphen zu ziehen. Befuellt wird der Speicher
// ausschliesslich vom Lader (compareMetricCatalogLoader.ts), der den Getter re-exportiert.

let defaultOrder: string[] | null = null;

/** Standardfolge aus der ersten verarbeiteten Katalog-Antwort (Kopie), sonst `null`. */
export function getCompareDefaultOrder(): string[] | null {
	return defaultOrder ? [...defaultOrder] : null;
}

/** Nur fuer den Katalog-Lader: uebernimmt `default_order` einer Katalog-Antwort. */
export function setCompareDefaultOrder(order: string[]): void {
	defaultOrder = [...order];
}
