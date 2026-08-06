// Issue #923 Adversary Finding F002: Fetch/Catch-Logik der SMS-Fidelity-
// Server-Vorschau, extrahiert aus ChannelFidelitySMS.svelte /
// ChannelPreviewCard.svelte — rein/DOM-frei testbar ohne $effect/mount()
// (svelte/server's render() führt beides nicht aus, der reale Fetch/Catch-
// Pfad war dadurch von keinem Test erreichbar).
//
// Bei Fehler (Netzwerkausfall, Reject) liefert diese Funktion IMMER
// `preview: null` — nie eine lokal nachgerechnete Kopie. Beide Komponenten
// rufen ausschließlich diese Funktion auf; keine eigene Kürzungs- oder
// Fallback-Logik im catch-Zweig.
//
// gz-eigenstaendig: Kein Compare-Pendant vorhanden — die SMS-Fidelity-Vorschau
// existiert bislang nur im Trip-Editor (#923), Compare ist ausdrücklich
// out of scope (siehe docs/specs/modules/fix_923_sms_fidelity_backend.md).

export interface SmsFidelityPreview {
	line: string;
	char_count: number;
	max_length: number;
	carried_ids: string[];
}

export interface SmsFidelityPreviewResult {
	preview: SmsFidelityPreview | null;
	error: string | null;
}

export async function loadSmsFidelityPreview(
	metricIds: string[],
	post: (path: string, body: unknown) => Promise<SmsFidelityPreview>
): Promise<SmsFidelityPreviewResult> {
	try {
		const preview = await post('/api/_validator/sms-fidelity-preview', { metric_ids: metricIds });
		return { preview, error: null };
	} catch (e: unknown) {
		const error =
			e && typeof e === 'object' && 'error' in e
				? String((e as { error: unknown }).error)
				: e instanceof Error
					? e.message
					: 'Vorschau konnte nicht geladen werden';
		return { preview: null, error };
	}
}
