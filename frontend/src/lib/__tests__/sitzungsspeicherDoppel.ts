// Issue #2317 — Sitzungsspeicher-Doppel fuer node:test.
//
// Node 22 kennt kein `sessionStorage`. Dieses Doppel bildet das echte
// Storage-Verhalten (Web Storage, HTML-Standard) nach: Schluessel und Werte
// werden zu Zeichenketten, `getItem` liefert fuer Unbekanntes `null`,
// `key(i)`/`length` erlauben das vollstaendige Durchsuchen aller Eintraege.
// KEIN Mock im verbotenen Sinn: es spiegelt keine Annahme zurueck, sondern ist
// ein echter Speicher, in den der Pruefling schreibt und aus dem der Test liest.

export class SitzungsspeicherDoppel {
	private readonly eintraege = new Map<string, string>();

	get length(): number {
		return this.eintraege.size;
	}

	key(index: number): string | null {
		return [...this.eintraege.keys()][index] ?? null;
	}

	getItem(schluessel: string): string | null {
		const wert = this.eintraege.get(String(schluessel));
		return wert === undefined ? null : wert;
	}

	setItem(schluessel: string, wert: string): void {
		this.eintraege.set(String(schluessel), String(wert));
	}

	removeItem(schluessel: string): void {
		this.eintraege.delete(String(schluessel));
	}

	clear(): void {
		this.eintraege.clear();
	}

	/** Alle Eintraege als [Schluessel, Wert] — ueber die oeffentliche Storage-Schnittstelle gelesen. */
	alleEintraege(): Array<[string, string]> {
		const out: Array<[string, string]> = [];
		for (let i = 0; i < this.length; i++) {
			const k = this.key(i) as string;
			out.push([k, this.getItem(k) as string]);
		}
		return out;
	}
}

/** Legt ein frisches Doppel auf `globalThis.sessionStorage` und liefert es zurueck. */
export function installiereSitzungsspeicher(): SitzungsspeicherDoppel {
	const speicher = new SitzungsspeicherDoppel();
	(globalThis as { sessionStorage?: unknown }).sessionStorage = speicher;
	return speicher;
}

/** Entfernt das Doppel wieder (afterEach). */
export function entferneSitzungsspeicher(): void {
	delete (globalThis as { sessionStorage?: unknown }).sessionStorage;
}
