<script lang="ts">
	// TelegramKurzstilToggle — Issue #1260 Scheibe S5: EINE geteilte Bedien-
	// komponente fuer den Opt-in „Telegram im SMS-Kurzstil". Wird in BEIDEN
	// Editor-Kontexten mit demselben Baustein + derselben Beschriftung verwendet
	// (Trip/Compare-Sharing-Invariante, CLAUDE.md — KEIN Compare-Nachbau):
	//   - Trip (context="route"): shared/versand-tab/VTBriefingChannels.svelte,
	//     unter der Telegram-Zeile, bindet an report_config.telegram_style.
	//   - Compare (context="vergleich"): shared/AlarmeTab.svelte, bei den
	//     amtlichen Compare-Warnungs-Kanaelen, bindet an
	//     display_config.telegram_style.
	//
	// Nur sinnvoll/aktiv, wenn Telegram als Kanal an ist (disabled → ausgegraut),
	// konsistent zum vorhandenen Kanal-Gating (VTBriefingChannels/ChannelToggle).
	//
	// Spec: docs/specs/modules/feat_1260_telegram_kurzstil.md (AC-11)

	import { Checkbox } from '$lib/components/ui/checkbox';

	interface Props {
		/** Kontext-Marker fuer die Sharing-Invariante (AC-11) — beide Kontexte
		 * rendern DIESE Komponente, nicht zwei Nachbauten. */
		context?: 'route' | 'vergleich';
		/** Aktueller Wert; 'kurzform' = Checkbox an, 'rich' (Default) = aus. */
		style: 'rich' | 'kurzform';
		onchange: (style: 'rich' | 'kurzform') => void;
		/** true = Telegram-Kanal nicht aktiv → Schalter ausgegraut/gesperrt. */
		disabled?: boolean;
		testid?: string;
	}
	let {
		context = 'route',
		style,
		onchange,
		disabled = false,
		testid = 'telegram-kurzstil-toggle'
	}: Props = $props();

	// Factory-Handler (Safari-Closure-Schutz, CLAUDE.md).
	function handleChange(e: Event): void {
		const checked = (e.target as HTMLInputElement).checked;
		onchange(checked ? 'kurzform' : 'rich');
	}
</script>

<div
	data-testid={testid}
	data-context={context}
	class="tks-wrap {disabled ? 'tks-disabled' : ''}"
>
	<span class="inline-flex items-center gap-2">
		<Checkbox
			checked={style === 'kurzform'}
			{disabled}
			aria-disabled={disabled ? 'true' : undefined}
			onchange={handleChange}
		>Telegram im SMS-Kurzstil</Checkbox>
	</span>
	<p class="tks-sub">
		{#if disabled}
			Erst aktiv, wenn Telegram als Kanal an ist.
		{:else}
			Telegram bekommt denselben kurzen Ein-Zeilen-Text wie SMS — ohne Knöpfe.
		{/if}
	</p>
</div>

<style>
	.tks-wrap {
		display: flex;
		flex-direction: column;
	}
	.tks-disabled {
		opacity: 0.5;
	}
	.tks-sub {
		font-size: 11px;
		color: var(--g-ink-3);
		margin: 2px 0 0;
		padding-left: 24px;
	}
</style>
