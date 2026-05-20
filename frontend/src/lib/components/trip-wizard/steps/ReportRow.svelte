<script lang="ts">
	import { Checkbox } from '$lib/components/ui/checkbox';

	// ReportRow — Toggle + Zeit-Input fuer einen Report-Typ (Morgen/Abend).
	// Epic #136 Sub-Spec #164 §5.
	//
	// Props:
	//   label           — sichtbarer Text neben der Checkbox (z.B. "Morgen-Briefing")
	//   enabled         — Toggle-Zustand
	//   time            — 'HH:MM'-String
	//   onEnabledChange — (enabled: boolean) => void  (Factory-Handler in Step4Briefings)
	//   onTimeChange    — (time: string) => void      (Factory-Handler in Step4Briefings)
	//   testidToggle    — data-testid fuer die Checkbox
	//   testidTime      — data-testid fuer den Zeit-Input
	//
	// Layout: flex items-center gap-4
	// Zeit-Input ist disabled wenn `enabled === false` (Spec §5 / AC#11).

	interface Props {
		label: string;
		enabled: boolean;
		time: string;
		onEnabledChange: (enabled: boolean) => void;
		onTimeChange: (time: string) => void;
		testidToggle: string;
		testidTime: string;
	}

	let {
		label,
		enabled,
		time,
		onEnabledChange,
		onTimeChange,
		testidToggle,
		testidTime
	}: Props = $props();

	function handleToggle(e: Event): void {
		const target = e.target as HTMLInputElement;
		onEnabledChange(target.checked);
	}

	function handleTime(e: Event): void {
		const target = e.target as HTMLInputElement;
		onTimeChange(target.value);
	}
</script>

<div class="flex items-center gap-4 text-sm">
	<Checkbox
		data-testid={testidToggle}
		checked={enabled}
		onchange={handleToggle}
	/>
	<span class="flex-1">{label}</span>
	<input
		type="time"
		data-testid={testidTime}
		value={time}
		disabled={!enabled}
		oninput={handleTime}
		class="h-9 rounded-lg border border-[var(--g-ink-faint)]/40 bg-transparent px-2.5 text-sm outline-none focus-visible:ring-2 focus-visible:ring-[var(--g-accent)] disabled:opacity-50"
	/>
</div>
