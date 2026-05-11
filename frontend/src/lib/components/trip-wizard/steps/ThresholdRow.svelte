<script lang="ts">
	// ThresholdRow — Label + Number-Input ODER Select fuer einen Alert-Schwellwert.
	// Epic #136 Sub-Spec #164 §6.
	//
	// Props:
	//   label    — sichtbarer Text (z.B. "Boeen")
	//   type     — 'number'  -> <input type="number">
	//              'thunder' -> <select> mit Optionen NONE/MED/HIGH + leer
	//   value    — number | 'NONE' | 'MED' | 'HIGH' | null  (null = ungesetzt)
	//   unit     — optional, nur bei type='number' (z.B. 'km/h', 'mm', 'm')
	//   onchange — (v: number | ThunderLevel | null) => void  (Factory-Handler)
	//   testid   — data-testid fuer das Input/Select-Element

	type ThunderLevel = 'NONE' | 'MED' | 'HIGH';

	interface Props {
		label: string;
		type: 'number' | 'thunder';
		value: number | ThunderLevel | null;
		unit?: string;
		onchange: (v: number | ThunderLevel | null) => void;
		testid: string;
	}

	let { label, type, value, unit, onchange, testid }: Props = $props();

	function handleNumber(e: Event): void {
		const raw = (e.target as HTMLInputElement).value;
		onchange(raw === '' ? null : Number(raw));
	}

	function handleSelect(e: Event): void {
		const raw = (e.target as HTMLSelectElement).value;
		onchange(raw === '' ? null : (raw as ThunderLevel));
	}
</script>

<label class="flex items-center gap-3 text-sm">
	<span class="w-40 flex-shrink-0">{label}</span>
	{#if type === 'number'}
		<input
			type="number"
			min="0"
			step="1"
			data-testid={testid}
			value={value ?? ''}
			oninput={handleNumber}
			class="h-9 w-24 rounded-lg border border-[var(--g-ink-faint)]/40 bg-transparent px-2.5 outline-none focus-visible:ring-2 focus-visible:ring-[var(--g-accent)]"
		/>
		{#if unit}
			<span class="text-sm text-[var(--g-ink-faint)]">{unit}</span>
		{/if}
	{:else}
		<select
			data-testid={testid}
			value={value ?? ''}
			onchange={handleSelect}
			class="h-9 rounded-lg border border-[var(--g-ink-faint)]/40 bg-transparent px-2.5 text-sm outline-none focus-visible:ring-2 focus-visible:ring-[var(--g-accent)]"
		>
			<option value="">—</option>
			<option value="NONE">Kein</option>
			<option value="MED">Mittel</option>
			<option value="HIGH">Hoch</option>
		</select>
	{/if}
</label>
