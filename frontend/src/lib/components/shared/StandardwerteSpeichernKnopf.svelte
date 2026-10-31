<script lang="ts">
	// Issue #2521 S3 — „Mit Standardwerten speichern": EIN geteilter Knopf fuer
	// /trips/new und /compare/new (keine context-Verzweigung). Das Gate
	// (`canFinishMitStandardwerten`) berechnet der Editor und reicht es als
	// `enabled` herein; waehrend des Speicherns ist der Knopf gesperrt.
	// Spec: docs/specs/modules/onboarding_standardwerte_hilfe.md
	import { t } from '$lib/i18n';

	let {
		enabled,
		saving = false,
		onclick,
		testid
	}: {
		enabled: boolean;
		saving?: boolean;
		onclick: () => unknown;
		testid: string;
	} = $props();

	const aktiv = $derived(enabled && !saving);
</script>

<button
	type="button"
	data-testid={testid}
	disabled={!aktiv}
	{onclick}
	style="padding: 6px 12px; min-height: 36px; border-radius: var(--g-r-2); border: 1px solid var(--g-ink); background: var(--g-card); color: var(--g-ink); font-size: 13px; font-weight: 500; cursor: {aktiv ? 'pointer' : 'not-allowed'}; opacity: {aktiv ? 1 : 0.4};"
>{$t('standardwerte.knopf')}</button>
