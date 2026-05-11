<script lang="ts">
	// ChannelToggle — generischer Toggle fuer einen Briefing-Kanal
	// (Epic #136 Sub-Spec #164 §4).
	//
	// Props:
	//   label    — sichtbarer Text neben der Checkbox
	//   checked  — aktueller Zustand der Checkbox
	//   onchange — (checked: boolean) => void  (Factory-Handler in Step4Briefings)
	//   disabled — optional, defaultet auf false; sperrt das Input und
	//              setzt Container-Style auf opacity-50/cursor-not-allowed
	//   hint     — optionaler Hilfetext (z.B. SMS: "demnaechst verfuegbar")
	//   testid   — data-testid fuer den Toggle-Container (Spec §9)
	//
	// Layout: flex items-center gap-3
	// Hint-TestID: `${testid}-hint` (nur gerendert, wenn `hint` gesetzt).

	interface Props {
		label: string;
		checked: boolean;
		onchange: (checked: boolean) => void;
		disabled?: boolean;
		hint?: string;
		testid: string;
	}

	let { label, checked, onchange, disabled = false, hint, testid }: Props = $props();

	function handleChange(e: Event): void {
		const target = e.target as HTMLInputElement;
		onchange(target.checked);
	}
</script>

<div
	data-testid={testid}
	class="flex flex-col gap-1 {disabled ? 'opacity-50 cursor-not-allowed' : ''}"
>
	<label
		class="flex items-center gap-3 text-sm {disabled
			? 'cursor-not-allowed'
			: 'cursor-pointer'}"
	>
		<input
			type="checkbox"
			{checked}
			{disabled}
			aria-disabled={disabled ? 'true' : undefined}
			onchange={handleChange}
			class="h-4 w-4"
		/>
		<span>{label}</span>
	</label>
	{#if hint}
		<span data-testid="{testid}-hint" class="text-xs text-[var(--g-ink-faint)] pl-7">
			{hint}
		</span>
	{/if}
</div>
