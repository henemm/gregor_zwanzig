// Issue #2216 — Aufbereitung der 409-Antwort `location_in_use` beim Ort-Loeschen.
// Reine Logik, per `node --test` pruefbar. Spec: fix_2216_ort_loeschen_sperre.md (AC-4).

export type OrtInUseHinweis = {
	text: string;
	links: { href: string; name: string }[];
};

/** Deutet den von `api.del` geworfenen Fehlerkoerper; null = anderer Fehler. */
export function ortInUseHinweis(fehler: unknown): OrtInUseHinweis | null {
	const f = fehler as { error?: unknown; compare_presets?: unknown } | null | undefined;
	if (!f || f.error !== 'location_in_use' || !Array.isArray(f.compare_presets)) return null;
	const presets = (f.compare_presets as { id?: unknown; name?: unknown }[]).filter(
		(p) => typeof p?.id === 'string' && typeof p?.name === 'string'
	) as { id: string; name: string }[];
	if (presets.length === 0) return null;
	const namen = presets.map((p) => p.name).join(', ');
	return {
		text: `Dieser Ort wird noch in diesen Ortsvergleichen verwendet: ${namen}. Entferne ihn dort zuerst.`,
		links: presets.map((p) => ({ href: `/compare/${encodeURIComponent(p.id)}`, name: p.name })),
	};
}
