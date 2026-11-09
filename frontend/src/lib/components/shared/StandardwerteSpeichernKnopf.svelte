<script lang="ts">
	// Issue #2521 S3 — „Mit Standardwerten speichern": EIN geteilter Knopf fuer
	// /trips/new und /compare/new (keine context-Verzweigung). Das Gate
	// (`canFinishMitStandardwerten`) berechnet der Editor und reicht es als
	// `enabled` herein; waehrend des Speicherns ist der Knopf gesperrt.
	// #2371 (AC-3): gesperrt ohne Opacity — Text --g-ink-3 (>= 4,5:1), Rahmen
	// --g-rule, aria-disabled="true"; natives disabled bleibt (kein Klick).
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
	class="standardwerte-knopf"
	data-testid={testid}
	disabled={!aktiv}
	aria-disabled={aktiv ? undefined : 'true'}
	{onclick}
	style="padding: 6px 12px; border-radius: var(--g-r-2); border: 1px solid {aktiv ? 'var(--g-ink)' : 'var(--g-rule)'}; background: {aktiv ? 'var(--g-card)' : 'transparent'}; color: {aktiv ? 'var(--g-ink)' : 'var(--g-ink-3)'}; font-size: 13px; font-weight: 500; cursor: {aktiv ? 'pointer' : 'not-allowed'};"
>{$t('standardwerte.knopf')}</button>

<style>
	.standardwerte-knopf {
		min-height: 36px;
	}
	/* #2881 R5: am Handy mindestens 44 px hoch (Tippfläche). */
	@media (max-width: 899px) {
		.standardwerte-knopf {
			min-height: 44px;
		}
	}
</style>
