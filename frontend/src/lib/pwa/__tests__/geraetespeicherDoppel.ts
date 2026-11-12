// Issue #2961 — In-Memory-Gerätespeicher (CacheStorage/Cache) fuer Node-Tests.
//
// Node kennt keine Cache-Storage-API. Dieses Doppel bildet die Teilmenge nach,
// die der Inhaltsspeicher des Service Workers benutzt (keys/open/delete/has,
// match/put/delete/keys), mit derselben Semantik: Schluessel werden wie im
// Browser gegen den Ursprung aufgeloest, jede Antwort wird bei `match` als
// frische Kopie geliefert (der Koerper ist mehrfach lesbar). Es spiegelt keine
// Erwartung zurueck, sondern speichert und liefert tatsaechlich.

const URSPRUNG = 'http://localhost/';

function schluesselVon(eingabe: RequestInfo | URL): string {
	if (eingabe instanceof Request) return eingabe.url;
	return new URL(String(eingabe), URSPRUNG).href;
}

export class CacheDoppel {
	private eintraege = new Map<string, Response>();

	async match(eingabe: RequestInfo | URL): Promise<Response | undefined> {
		return this.eintraege.get(schluesselVon(eingabe))?.clone();
	}

	async put(eingabe: RequestInfo | URL, antwort: Response): Promise<void> {
		this.eintraege.set(schluesselVon(eingabe), antwort.clone());
	}

	async delete(eingabe: RequestInfo | URL): Promise<boolean> {
		return this.eintraege.delete(schluesselVon(eingabe));
	}

	async keys(): Promise<Request[]> {
		return [...this.eintraege.keys()].map((url) => new Request(url));
	}

	/** Testhilfe: Pfade aller Eintraege. */
	pfade(): string[] {
		return [...this.eintraege.keys()].map((url) => new URL(url).pathname).sort();
	}
}

export class GeraetespeicherDoppel {
	private speicher = new Map<string, CacheDoppel>();

	async keys(): Promise<string[]> {
		return [...this.speicher.keys()];
	}

	async has(name: string): Promise<boolean> {
		return this.speicher.has(name);
	}

	async open(name: string): Promise<Cache> {
		let cache = this.speicher.get(name);
		if (!cache) {
			cache = new CacheDoppel();
			this.speicher.set(name, cache);
		}
		return cache as unknown as Cache;
	}

	async delete(name: string): Promise<boolean> {
		return this.speicher.delete(name);
	}

	async match(eingabe: RequestInfo | URL): Promise<Response | undefined> {
		for (const cache of this.speicher.values()) {
			const treffer = await cache.match(eingabe);
			if (treffer) return treffer;
		}
		return undefined;
	}

	/** Testhilfe: direkter Zugriff auf einen Speicher. */
	cache(name: string): CacheDoppel | undefined {
		return this.speicher.get(name);
	}
}
