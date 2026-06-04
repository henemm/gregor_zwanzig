<script lang="ts">
	// Issue #578 — ComparePreviewMissing-Molecule.
	// Kanonische Quelle: molecules.jsx::ComparePreviewMissing

	interface Props {
		note?: string;
		class?: string;
	}

	let { note, class: className = '' }: Props = $props();
</script>

<div
	class={className}
	style:border="1px dashed var(--g-rule)"
	style:border-radius="var(--g-r-3)"
	style:background="var(--g-card)"
	style:padding="20px"
	style:font-size="13px"
	style:color="var(--g-ink-3)"
>
	{note ?? 'Vorschau-Daten nicht verfügbar.'}
</div>
