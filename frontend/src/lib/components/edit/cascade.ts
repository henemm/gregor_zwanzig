// Issue #498 — Datums-Arithmetik für Etappen-Datum-Editor & Kaskaden-Logik.
//
// Pure helpers — keine DOM-Abhängigkeit, keine Mocks. Werden von
// EditStagesPanelNew.svelte verwendet, um:
//   1. Folge-Etappen bei Tourstart-Verschiebung um N Tage zu verschieben (addDays)
//   2. Den Tage-Delta zwischen altem und neuem Datum zu berechnen (computeCascadeDelta)
//
// ISO-Format: "YYYY-MM-DD" (lokales Datum, ohne Timezone-Shift).
// Verwendung von 'T00:00:00' beim Parsen vermeidet UTC-Tagesgrenzen-Bugs.

/**
 * Addiert delta Tage (kann negativ sein) zu einem ISO-Datum.
 * @example addDays('2026-01-31', 1) → '2026-02-01'
 */
export function addDays(iso: string, delta: number): string {
	const d = new Date(iso + 'T00:00:00');
	d.setDate(d.getDate() + delta);
	const y = d.getFullYear();
	const m = String(d.getMonth() + 1).padStart(2, '0');
	const day = String(d.getDate()).padStart(2, '0');
	return `${y}-${m}-${day}`;
}

/**
 * Berechnet die Anzahl Tage zwischen oldIso und newIso (newIso - oldIso).
 * Positiv = neues Datum liegt später, negativ = früher, 0 = unverändert.
 */
export function computeCascadeDelta(oldIso: string, newIso: string): number {
	const oldMs = new Date(oldIso + 'T00:00:00').getTime();
	const newMs = new Date(newIso + 'T00:00:00').getTime();
	return Math.round((newMs - oldMs) / 86_400_000);
}

/**
 * Bug #1393 — die Folge-Etappen werden LÜCKENLOS durchdatiert, nicht um
 * denselben Betrag verschoben. Legt der Nutzer eine Etappe auf den 26.7., wird
 * die nächste der 27.7., die übernächste der 28.7. — ungleiche Abstände der
 * Ausgangstour werden dabei bewusst eingeebnet (PO-Entscheidung).
 *
 * `followerIds` sind die Etappen HINTER der bearbeiteten, in Reihenfolge und
 * nur die MIT Datum: eine Etappe ohne Datum steht nicht in der Liste, bleibt
 * dadurch ohne Datum und verbraucht keinen Tag. Ein Pausentag hat ein Datum,
 * steht also drin und rückt mit — sonst verschöbe sich die Tour gegenüber der
 * Wirklichkeit.
 *
 * @example consecutiveDates('2026-07-26', ['b','c']) → { b: '2026-07-27', c: '2026-07-28' }
 */
export function consecutiveDates(anchorIso: string, followerIds: string[]): Record<string, string> {
	const out: Record<string, string> = {};
	followerIds.forEach((id, i) => {
		out[id] = addDays(anchorIso, i + 1);
	});
	return out;
}

/** ISO 'YYYY-MM-DD' → 'DD.MM.YYYY' für die Anzeige. Leer bleibt leer. */
export function formatDeDate(iso: string): string {
	const [y, m, d] = iso.split('-');
	return y && m && d ? `${d}.${m}.${y}` : '';
}
