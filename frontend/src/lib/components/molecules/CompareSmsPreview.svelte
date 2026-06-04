<script lang="ts">
	// Issue #578 — CompareSmsPreview-Molecule.
	// Kanonische Quelle: molecules.jsx::CompareSmsPreview
	//
	// Token-Format ≤ 140 Zeichen. Warn-Farbe #f0a060 bei Überschreitung.

	const COMPARE_SMS_MAX = 140;

	interface Col {
		key: string;
		label?: string;
		primary?: boolean;
	}

	interface Row {
		id: string;
		rank: number;
		score: string | number;
		[key: string]: unknown;
	}

	interface Profile {
		cols: Col[];
	}

	interface Data {
		rows: Row[];
		locations: Record<string, { name: string }>;
	}

	interface Props {
		profile: Profile;
		data: Data;
		class?: string;
	}

	let { profile, data, class: className = '' }: Props = $props();

	const top = $derived(
		profile.cols.find((c) => c.primary && c.key !== 'score') ?? profile.cols[1]
	);

	const body = $derived(() => {
		const parts = data.rows.map((r) => {
			const loc = data.locations[r.id];
			const short = (loc?.name ?? String(r.id)).split(/[\s(]/)[0];
			const topVal = top ? String(r[top.key] ?? '—').replace(/\s/g, '') : '';
			return `${r.rank}.${short} ${r.score}${top ? `(${topVal})` : ''}`;
		});
		let b = `GZ Vergleich: ${parts.join('  ')}`;
		if (b.length > COMPARE_SMS_MAX) {
			b = b.slice(0, COMPARE_SMS_MAX - 1) + '…';
		}
		return b;
	});

	const over = $derived(body().length > COMPARE_SMS_MAX);
	const charCount = $derived(body().length);
</script>

<div
	class={className}
	style:background="#0b0b0d"
	style:border-radius="var(--g-r-3)"
	style:padding="16px 14px 18px"
>
	<div style:display="flex" style:align-items="center" style:justify-content="space-between" style:margin-bottom="12px">
		<span style:color="#fff" style:font-size="12.5px" style:font-weight="600">SMS · Gregor Zwanzig</span>
		<span style:font-family="var(--g-font-mono)" style:font-size="9.5px" style:color="rgba(255,255,255,0.45)" style:letter-spacing="0.06em" style:text-transform="uppercase">flach · ohne Spalten</span>
	</div>
	<div style:max-width="280px" style:background="#3a3a3c" style:border-radius="4px 16px 16px 16px" style:padding="11px 13px">
		<div style:font-family="var(--g-font-mono)" style:font-size="12px" style:color="#fff" style:line-height="1.5" style:word-break="break-word">{body()}</div>
	</div>
	<div style:font-family="var(--g-font-mono)" style:font-size="10px" style:color={over ? '#f0a060' : 'rgba(255,255,255,0.45)'} style:margin-top="8px">
		{charCount}/{COMPARE_SMS_MAX} Zeichen{over ? ' · gekürzt' : ''}
	</div>
</div>
