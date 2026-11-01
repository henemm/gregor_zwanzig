<script lang="ts">
	// Issue #2346 S2 — EINE Startseiten-Kachel fuer Trip und Ortsvergleich (ersetzt TripKachel/CompareKachel).
	// Thin-Wrapper auf SubscriptionCard (compact). Klick und "Bearbeiten" oeffnen den Hub, der Name ist
	// ein echter Link. Trip-Kanaele aus den report_config-Flags (nie aus empfaenger, #1452/AC-9).
	// nextSend/lastSent kommen fertig vom Aufrufer (kachelVersand, GET /api/next-briefings).

	import { goto } from '$app/navigation';
	import SubscriptionCard from '$lib/components/organisms/SubscriptionCard.svelte';
	import { presetChannels } from '$lib/components/compare/subscriptionHelpers.js';
	import type { SubscriptionKind } from '$lib/components/shared/subscriptionTabs.js';
	import type { ComparePreset, Trip } from '$lib/types.js';
	import { kachelActions } from './kachelActions.js';
	import { reportChannels } from './cockpitHelpers.js';
	import { locale } from '$lib/i18n/index.js';

	interface Props {
		kind: SubscriptionKind;
		sub: Trip | ComparePreset;
		nextSend?: string | null;
		lastSent?: string | null;
	}

	let { kind, sub, nextSend = null, lastSent = null }: Props = $props();

	// Anzeigenamen wie presetChannels (Vergleich), damit beide kinds gleich aussehen.
	const KANAL_NAME: Record<string, string> = {
		email: 'Email',
		telegram: 'Telegram',
		sms: 'SMS',
		'premium-sms': 'Premium-SMS'
	};
	const channels = $derived(
		kind === 'trip'
			? reportChannels((sub as Trip).report_config).map((k) => KANAL_NAME[k] ?? k)
			: presetChannels(sub as ComparePreset)
	);
	const hub = $derived((kind === 'trip' ? '/trips/' : '/compare/') + sub.id);
	// #2652 (i18n F3): Aktions-Label folgt der Sprache ohne Neuladen.
	const actions = $derived.by(() => {
		void $locale;
		return kachelActions();
	});
</script>

<SubscriptionCard
	{kind}
	{sub}
	compact
	href={hub}
	{channels}
	{nextSend}
	{lastSent}
	{actions}
	onclick={() => goto(hub)}
	onAction={(id) => {
		if (id === 'edit') goto(hub);
	}}
/>
