<script lang="ts">
	// Issue #578 — CompareBriefingPreview-Molecule.
	// Kanonische Quelle: molecules.jsx::CompareBriefingPreview
	//
	// Delegiert je nach Kanal an die passende Vorschau-Komponente.

	import CompareChatBubble from './CompareChatBubble.svelte';
	import CompareSmsPreview from './CompareSmsPreview.svelte';
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
{:else if channel === 'telegram'}
	<CompareChatBubble class={className} {channel} profile={profile as any} data={data as any} {subscriptionName} />
{:else if channel === 'sms'}
	<CompareSmsPreview class={className} profile={profile as any} data={data as any} />
{:else}
	<ComparePreviewMissing class={className} />
{/if}
