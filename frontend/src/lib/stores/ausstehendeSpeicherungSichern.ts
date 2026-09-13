// Issue #2316 Scheibe A — gemeinsamer Speicher-Wächter für die Detailseiten
// `/trips/[id]` und `/compare/[id]`. Ersetzt 1:1 die bisher nur in
// `trips/[id]/+page.svelte` lebende `beforeNavigate`-Logik (Issue #758/#1376),
// jetzt EINMAL geschrieben und von beiden Seiten aufgerufen (Trip/Vergleich-
// Code-Teilung, siehe CLAUDE.md).
//
// Spec: docs/specs/modules/pwa_update_erkennung.md
//   § Implementation Details „compare/[id]/+page.svelte + trips/[id]/+page.svelte (Scheibe A)"
//   § Acceptance Criteria AC-9, AC-10
//
// BEWUSST kein Import aus `$app/*` und keine Runen — sonst ist das Modul unter
// node:test nicht ladbar. Die Svelte-Verdrahtung (`beforeNavigate` aus
// `$app/navigation`, `goto`) bleibt eine dünne Hülle in den aufrufenden Seiten.

import type { SaveStatus } from './saveStatusStore.svelte.ts';

/** Entspricht dem Argument, das SvelteKits `beforeNavigate` an seinen Callback reicht. */
export interface NavigationLike {
	willUnload: boolean;
	to: { url: URL } | null;
	cancel(): void;
}

/**
 * Sichert eine ausstehende Speicherung vor dem Verlassen/Neuladen der Seite.
 *
 * - Entladen (`willUnload`) + ausstehend: SOFORT mit `keepalive:true` flushen,
 *   OHNE die Navigation abzubrechen (PO-Entscheidung 2026-07-25: still
 *   speichern statt Verlassen-Rückfrage zu zeigen — Issue #1376/#2316 AC-9).
 * - Seitenwechsel innerhalb der App + ausstehend: Navigation anhalten,
 *   flushen, danach zum ursprünglichen Ziel weiternavigieren.
 * - Nichts ausstehend: unverändert durchlaufen lassen (kein Anhalten, kein
 *   eigener Speichervorgang, keine Umleitung).
 */
export function sichereAusstehendeSpeicherung(
	navigation: NavigationLike,
	ctl: SaveStatus,
	goto: (href: string) => unknown
): void {
	if (navigation.willUnload) {
		if (ctl.hasPending) void ctl.flush({ keepalive: true });
		return;
	}
	if (ctl.hasPending) {
		navigation.cancel();
		const targetUrl = navigation.to?.url?.href ?? null;
		void ctl.flush().then(() => {
			if (targetUrl) void goto(targetUrl);
		});
	}
}
