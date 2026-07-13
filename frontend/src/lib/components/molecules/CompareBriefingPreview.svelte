<script lang="ts">
	// Issue #578 — CompareBriefingPreview-Molecule.
	// Kanonische Quelle: molecules.jsx::CompareBriefingPreview
	//
	// Delegiert je nach Kanal an die passende Vorschau-Komponente.
	// Hinweis (#1229 S2): telegram/sms sind im Hub nie mit profile/data
	// gemountet und routen daher (wie email) auf ComparePreviewMissing.
	// CompareChatBubble/CompareSmsPreview bleiben als Dateien bestehen (KL-3).

	import ComparePreviewMissing from './ComparePreviewMissing.svelte';

	interface Props {
		profileId?: string;
		channel?: string;
		subscriptionName?: string;
		profile?: object;
		data?: object;
		class?: string;
	}

	let { profileId, channel = 'email', subscriptionName, profile, data, class: className = '' }: Props = $props();
</script>

{#if !profile || !data}
	<ComparePreviewMissing class={className} />
{:else if channel === 'email'}
	<ComparePreviewMissing class={className} note="E-Mail-Vorschau wird separat gerendert." />
{:else}
	<ComparePreviewMissing class={className} />
{/if}
