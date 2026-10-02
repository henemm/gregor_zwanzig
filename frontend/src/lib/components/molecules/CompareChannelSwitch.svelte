<script lang="ts">
	// Issue #578 — CompareChannelSwitch-Molecule.
	// Kanonische Quelle: molecules.jsx::CompareChannelSwitch
	//
	// Segmentierter Umschalter Email · Signal · Telegram · SMS.
	// Nur konfigurierte Kanäle sind aktiv; der Rest bleibt sichtbar (grau).

	interface Props {
		value: string;
		onChange?: (ch: string) => void;
		channels?: string[];
		dense?: boolean;
		class?: string;
		/** Issue #2229 (AC-3): Hinweis neben den Reitern, z. B. bei Premium-SMS. Leer ⇒ nicht gerendert. */
		note?: string;
	}

	let { value, onChange, channels = [], dense = false, class: className = '', note = '' }: Props = $props();

	// #610: signal entfernt — 3 Kanäle
	// ADR-0049: kein vierter Reiter für Premium-SMS — sie hat keinen eigenen Inhalt, sie sendet den SMS-Text (Hinweis über `note`, #2229)
	const all = ['email', 'telegram', 'sms'];
	const LABELS: Record<string, string> = {
		email: 'Email',
		telegram: 'Telegram',
		sms: 'SMS',
	};
</script>

<div
	class={className}
	style:display="inline-flex"
	style:background="var(--g-paper-deep)"
	style:border="1px solid var(--g-rule)"
	style:border-radius="var(--g-r-2)"
	style:padding="3px"
	style:gap="2px"
	style:flex-wrap="wrap"
>
	{#each all as ch (ch)}
		{@const on = value === ch}
		{@const has = channels.includes(ch)}
		<button
			onclick={() => onChange && onChange(ch)}
			style:padding={dense ? '6px 10px' : '7px 13px'}
			style:border="none"
			style:cursor="pointer"
			style:border-radius="var(--g-r-1, 4px)"
			style:font-size="12.5px"
			style:font-weight={on ? '600' : '500'}
			style:font-family="var(--g-font-sans)"
			style:background={on ? 'var(--g-card)' : 'transparent'}
			style:box-shadow={on ? 'var(--g-shadow-1)' : 'none'}
			style:color={on ? 'var(--g-ink)' : has ? 'var(--g-ink-3)' : 'var(--g-ink-4)' /* audit:exempt: inactive/disabled channel */}
			style:display="inline-flex"
			style:align-items="center"
			style:gap="6px"
		>
			{LABELS[ch]}
			{#if !has}
				<span style:width="5px" style:height="5px" style:border-radius="50%" style:background="var(--g-rule)"></span>
			{/if}
		</button>
	{/each}
	{#if note}
		<span
			data-testid="compare-preview-premium-sms-note"
			style:align-self="center"
			style:padding="0 8px"
			style:font-size="12px"
			style:font-family="var(--g-font-sans)"
			style:color="var(--g-ink-3)"
		>{note}</span>
	{/if}
</div>
