// reportSlotAktiv — Issue #2422 S3 (Verdikt N2, AC-23/AC-24).
//
// EINE Regel, ob ein Briefing-Slot (Morgen/Abend) eines Trips aktiv ist —
// dieselbe wie Python `slot_aktiv` (src/app/models.py) und Go
// `deriveFlatFields` (internal/store/trip.go). Alle drei Fassungen werden von
// derselben Fallzeilen-Tabelle `tests/fixtures/report_config_slot_faelle.json`
// getrieben, damit sie nicht unbemerkt auseinanderlaufen.
//
// Aufrufer: die Leser der Trip-Uebersicht (rightColumn, cockpitHelpers568,
// _home/cockpitHelpers, TripKachel, Startseite) und der Editor-Startzustand
// (reportConfigPayload.ts -> VersandTab).
//
// Pure Funktion, kein Netz-/DOM-Zugriff — node:testbar.

export type ReportSlot = 'morning' | 'evening';

/**
 * - kein `report_config` ⇒ aktiv (Bestandsverhalten: der Trip bekommt sein Briefing)
 * - `enabled === false` ⇒ aus (Gesamtschalter ist Master, schaltet BEIDE Slots ab)
 * - Per-Slot-Schluessel ist ein echtes `boolean` ⇒ dieser Wert
 * - sonst (fehlt, `null`, kein bool) ⇒ aktiv (Rueckfall auf den Gesamtschalter)
 */
export function reportSlotAktiv(rc: unknown, slot: ReportSlot): boolean {
	if (rc == null || typeof rc !== 'object') return true;
	const c = rc as Record<string, unknown>;
	if (c.enabled === false) return false;
	const perSlot = c[`${slot}_enabled`];
	return typeof perSlot === 'boolean' ? perSlot : true;
}
