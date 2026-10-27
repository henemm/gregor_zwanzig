// Mobile-Shell S2 — Initialen für den Konto-Kreis (User-Badge neben der
// Tabbar). Anzeigename hat Vorrang (#642), sonst die Login-Kennung.
//   "Henning Emmrich" -> "HE" · "Henning" -> "HE" · "hem" -> "HE" · "" -> "?"
export function initialen(displayName: string | null | undefined, userId?: string | null): string {
	const quelle = (displayName ?? '').trim() || (userId ?? '').trim();
	if (!quelle) return '?';
	const woerter = quelle.split(/[\s._-]+/).filter(Boolean);
	const roh = woerter.length >= 2 ? woerter[0][0] + woerter[1][0] : quelle.slice(0, 2);
	return roh.toUpperCase();
}
