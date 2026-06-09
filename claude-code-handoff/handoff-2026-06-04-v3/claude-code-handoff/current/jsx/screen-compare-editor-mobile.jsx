/* screen-compare-editor-mobile.jsx
 * ═══════════════════════════════════════════════════════════════════════
 *  Orts-Vergleich anlegen & bearbeiten — Mobile (375 px)
 *  Identisches Pattern wie ScreenTripNewV2Mobile.
 *  screen-compare-wizard-mobile war nie existiert — komplett neu.
 *
 *  Prefix: CEM_ — Babel-Scope-Disziplin (CLAUDE.md)
 *  Export:  window.ScreenCompareEditorMobile
 *
 *  mode="create"  →  Tabs sequenziell freigeschaltet + Fortschrittsbalken
 *  mode="edit"    →  alle Tabs frei, Speichern in TopAppBar
 * ═══════════════════════════════════════════════════════════════════════ */

const CEM_TABS = [
  { id: "vergleich",  label: "Vergleich",   lockHint: null },
  { id: "orte",       label: "Orte",         lockHint: "erst Vergleich benennen" },
  { id: "idealwerte", label: "Idealwerte",   lockHint: "erst mind. 2 Orte" },
  { id: "layout",     label: "Layout",       lockHint: "erst Idealwerte öffnen" },
  { id: "versand",    label: "Versand",      lockHint: "erst Layout öffnen" },
];

const CEM_CHANNELS = [
  { id: "email",    label: "Email",    maxCols: Infinity, hint: "alle Spalten + Detail" },
  { id: "telegram", label: "Telegram", maxCols: 8,        hint: "max 8 Spalten" },
  { id: "sms",      label: "SMS",      maxCols: 0,        hint: "flach · ≤ 140 Z." },
];

const CEM_IDEALS = {
  "wintersport": [
    { label: "Schneehöhe",      ideal: "≥ 80 cm",              pos: [0.55, 1.00], notes: "Mindestauflage", scale: ["0", "300+"] },
    { label: "Neuschnee 24 h",  ideal: "+ je mehr je besser",  pos: [0.30, 1.00], notes: "Pulver-Bonus",   scale: ["0", "40 cm"] },
    { label: "Wind (Mittel)",   ideal: "≤ 30 km/h",            pos: [0.00, 0.40], notes: "Lift ab 50",     scale: ["0", "Sturm"] },
    { label: "Temperatur gef.", ideal: "−8 bis +2 °C",         pos: [0.30, 0.65], notes: "pulvrig",        scale: ["−20°", "+15°"] },
    { label: "Niederschlag",    ideal: "Schnee ok · Regen aus", pos: [0.00, 0.25], notes: "Regen → Abbruch",scale: ["trocken", "Regen"] },
    { label: "Sichtweite",      ideal: "≥ 5 km",               pos: [0.50, 1.00], notes: "Nebel = Stopp",  scale: ["0", "klar"] },
  ],
  "alpine-touring": [
    { label: "Wind (Mittel)",   ideal: "≤ 30 km/h",  pos: [0.00, 0.40], notes: "Gratwege",    scale: ["0", "Sturm"] },
    { label: "Lawinenstufe",    ideal: "≤ Stufe 2",  pos: [0.00, 0.40], notes: "ab 3 Stopp",  scale: ["1", "5"] },
    { label: "Sichtweite",      ideal: "≥ 1 km",     pos: [0.20, 1.00], notes: "Spalten",     scale: ["Nebel", "klar"] },
    { label: "Sonnenstunden",   ideal: "≥ 3 h",      pos: [0.40, 1.00], notes: "Komfort",     scale: ["0 h", "8 h"] },
  ],
  "hiking": [
    { label: "Niederschlag",    ideal: "≤ 2 mm/h",   pos: [0.00, 0.25], notes: "trocken",     scale: ["trocken", "Regen"] },
    { label: "Wind (Mittel)",   ideal: "≤ 25 km/h",  pos: [0.00, 0.40], notes: "Grat",        scale: ["0", "Sturm"] },
    { label: "Gewitter",        ideal: "kein Risiko", pos: [0.00, 0.15], notes: "→ Abbruch",  scale: ["niedrig", "hoch"] },
    { label: "Temperatur",      ideal: "+8 bis +22 °C", pos: [0.40, 0.75], notes: "angenehm", scale: ["−5°", "+35°"] },
  ],
  "trail-running": [
    { label: "Temperatur",   ideal: "+8 bis +18 °C", pos: [0.40, 0.70], notes: "Wettkampf",  scale: ["0°", "+30°"] },
    { label: "UV-Index",     ideal: "≤ 6",           pos: [0.00, 0.55], notes: "Sonnenbrand", scale: ["0", "extrem"] },
    { label: "Niederschlag", ideal: "≤ 1 mm/h",      pos: [0.00, 0.20], notes: "trocken",    scale: ["trocken", "Regen"] },
  ],
  "wintersport-glacier": [
    { label: "Schneehöhe",      ideal: "≥ 150 cm",    pos: [0.65, 1.00], notes: "Gletscher",  scale: ["0", "400+"] },
    { label: "Wind (Mittel)",   ideal: "≤ 25 km/h",   pos: [0.00, 0.35], notes: "Höhenwind",  scale: ["0", "Sturm"] },
    { label: "Temperatur gef.", ideal: "−15 bis −2 °C", pos: [0.20, 0.55], notes: "kalt = stabil", scale: ["−30°", "+10°"] },
  ],
};

/* ─── Lock / Done ─── */
function CEM_unlocked(name, pickedCount, idealsVis, layoutVis) {
  const s = new Set(["vergleich"]);
  if (name.trim()) s.add("orte");
  if (pickedCount >= 2) s.add("idealwerte");
  if (idealsVis) s.add("layout");
  if (layoutVis) s.add("versand");
  return s;
}

function CEM_doneSet(name, pickedCount, idealsVis, layoutVis, versandVis) {
  const s = new Set();
  if (name.trim()) s.add("vergleich");
  if (pickedCount >= 2) s.add("orte");
  if (idealsVis) s.add("idealwerte");
  if (layoutVis) s.add("layout");
  if (versandVis) s.add("versand");
  return s;
}

/* ─── Tab Bar (scrollbar horizontal) ─── */
function CEM_TabBar({ active, unlocked, onChange, isEdit, onLockedTap }) {
  return (
    <div style={{
      display: "flex", gap: 0, overflowX: "auto",
      borderBottom: "1px solid var(--g-rule-soft)",
      WebkitOverflowScrolling: "touch", scrollbarWidth: "none", flexShrink: 0,
    }}>
      {CEM_TABS.map(t => {
        const on   = t.id === active;
        const open = isEdit || unlocked.has(t.id);
        return (
          <button key={t.id}
            onClick={() => open ? onChange(t.id) : onLockedTap(t)}
            style={{
              display: "inline-flex", alignItems: "center", gap: 5,
              padding: "13px 13px", minHeight: 44, flexShrink: 0,
              background: "transparent", border: "none",
              cursor: open ? "pointer" : "default",
              fontSize: 14, fontWeight: on ? 600 : 500,
              color: on ? "var(--g-ink)" : open ? "var(--g-ink-3)" : "var(--g-ink-4)",
              borderBottom: on ? "2px solid var(--g-accent)" : "2px solid transparent",
              marginBottom: -1, whiteSpace: "nowrap", fontFamily: "var(--g-font-sans)",
              opacity: open ? 1 : 0.35,
            }}>
            {t.label}
            {!open && <span className="mono" style={{ fontSize: 10, opacity: 0.8 }}>⊘</span>}
          </button>
        );
      })}
    </div>
  );
}

/* ─── Fortschrittsbalken ─── */
function CEM_Progress({ done }) {
  const steps = ["vergleich", "orte", "idealwerte", "layout", "versand"];
  const n = steps.filter(s => done.has(s)).length;
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 8, padding: "8px 16px 0" }}>
      <div style={{ display: "flex", gap: 3, flex: 1 }}>
        {steps.map(s => (
          <div key={s} style={{
            flex: 1, height: 3, borderRadius: 2,
            background: done.has(s) ? "var(--g-accent)" : "var(--g-rule)",
            transition: "background 350ms",
          }}/>
        ))}
      </div>
      <span className="mono" style={{ fontSize: 10, color: "var(--g-ink-4)", flexShrink: 0 }}>{n}/5</span>
    </div>
  );
}

/* ─── Lock-Hint Toast ─── */
function CEM_LockHint({ msg }) {
  return (
    <div style={{
      position: "absolute", bottom: 72, left: 16, right: 16, zIndex: 50,
      background: "var(--g-ink)", color: "var(--g-paper)",
      borderRadius: "var(--g-r-3)", padding: "11px 16px",
      fontSize: 13, fontFamily: "var(--g-font-mono)",
      boxShadow: "0 4px 20px rgba(26,26,24,0.25)",
      display: "flex", alignItems: "center", gap: 10,
      pointerEvents: "none",
    }}>
      <span style={{ opacity: 0.6 }}>⊘</span>
      <span>{msg}</span>
    </div>
  );
}

/* ─── Tab 1: Vergleich ─── */
function CEM_VergleichTab({ name, onName, region, onRegion, profileId, onProfile, isEdit, onContinue }) {
  const can = name.trim().length > 0;
  const profiles = window.LOCATION_ACTIVITY_PROFILES || [];

  return (
    <ScreenScroll padding={16} style={{ paddingBottom: 88 }}>
      <MField label="Name des Vergleichs" sub="Erscheint im Mail-Betreff">
        <MInput value={name} onChange={e => onName(e.target.value)}
          placeholder="z.B. Skitouren Hochkönig"/>
      </MField>

      <MField label="Region" sub="optional · max 60 Zeichen">
        <MInput value={region} onChange={e => onRegion(e.target.value.slice(0, 60))}
          placeholder="z.B. Hochkönig · Salzburger Land"/>
      </MField>

      <div style={{ marginBottom: 8 }}>
        <div className="mono" style={{ fontSize: 10, color: "var(--g-ink-4)", letterSpacing: "0.10em", textTransform: "uppercase", marginBottom: 10 }}>
          Aktivitätsprofil
        </div>
        <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
          {profiles.map(p => (
            <button key={p.id} onClick={() => onProfile(p.id)} style={{
              display: "flex", alignItems: "center", gap: 12, minHeight: 52,
              padding: "12px 14px",
              background: profileId === p.id ? "var(--g-accent-tint)" : "var(--g-card)",
              border: profileId === p.id ? "1.5px solid var(--g-accent)" : "1px solid var(--g-rule)",
              borderRadius: "var(--g-r-3)", cursor: "pointer", textAlign: "left",
              fontFamily: "var(--g-font-sans)",
            }}>
              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{ fontSize: 14.5, fontWeight: 600, color: profileId === p.id ? "var(--g-accent-deep)" : "var(--g-ink)" }}>{p.label}</div>
                <div className="mono" style={{ fontSize: 10, color: "var(--g-ink-3)", marginTop: 2, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                  {p.metrics.slice(0, 4).join(" · ")}{p.metrics.length > 4 ? " …" : ""}
                </div>
              </div>
              {profileId === p.id && (
                <span style={{ width: 20, height: 20, borderRadius: "50%", background: "var(--g-accent)", display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0 }}>
                  <svg width={11} height={11} viewBox="0 0 12 12" fill="none" stroke="#fff" strokeWidth="2.5"><path d="M2 6l3 3 5-6"/></svg>
                </span>
              )}
            </button>
          ))}
        </div>
      </div>

      {!isEdit && (
        <div style={{ position: "absolute", bottom: 16, left: 16, right: 16, zIndex: 10 }}>
          <MBtn block variant={can ? "primary" : "quiet"} size="xl"
            onClick={can ? onContinue : undefined}
            style={!can ? { opacity: 0.4 } : {}}>
            {can ? "Orte hinzufügen →" : "Name eingeben"}
          </MBtn>
        </div>
      )}
    </ScreenScroll>
  );
}

/* ─── Tab 2: Orte ─── */
function CEM_OrteTab({ pickedIds, setPickedIds, isEdit, onContinue }) {
  const locations = window.MOCK_LOCATIONS || [];
  const picked    = pickedIds.map(id => locations.find(l => l.id === id)).filter(Boolean);
  const canAdv    = pickedIds.length >= 2;
  const [libOpen, setLibOpen] = React.useState(false);

  const groups = locations.filter(l => l.group !== "Test").reduce((acc, l) => {
    (acc[l.group] = acc[l.group] || []).push(l); return acc;
  }, {});

  return (
    <React.Fragment>
      <ScreenScroll padding={14} style={{ paddingBottom: 88 }}>

        {/* Picked list */}
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 10 }}>
          <div className="mono" style={{ fontSize: 10, color: "var(--g-ink-4)", letterSpacing: "0.10em", textTransform: "uppercase", fontWeight: 600 }}>
            Im Vergleich · {picked.length}
          </div>
          <span className="mono" style={{ fontSize: 10.5, color: picked.length < 2 ? "var(--g-warn)" : "var(--g-ink-4)" }}>
            {picked.length < 2 ? "min. 2" : picked.length > 5 ? "viel — Empf. 3–5" : "passt"}
          </span>
        </div>

        {picked.length === 0 ? (
          <div style={{ padding: "24px 16px", border: "1px dashed var(--g-rule)", borderRadius: "var(--g-r-3)", textAlign: "center", color: "var(--g-ink-3)", fontSize: 13, marginBottom: 12 }}>
            Noch keine Orte gewählt.
          </div>
        ) : (
          <div style={{ display: "flex", flexDirection: "column", gap: 8, marginBottom: 12 }}>
            {picked.map((l, i) => (
              <div key={l.id} style={{ display: "flex", alignItems: "center", gap: 10, padding: "11px 14px", background: "var(--g-card)", border: "1px solid var(--g-rule)", borderRadius: "var(--g-r-3)", minHeight: 52 }}>
                <span className="mono" style={{ width: 24, height: 24, borderRadius: 4, background: "var(--g-ink)", color: "#fff", display: "inline-flex", alignItems: "center", justifyContent: "center", fontSize: 10, fontWeight: 700, flexShrink: 0 }}>{i + 1}</span>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ fontSize: 14, fontWeight: 600, color: "var(--g-ink)", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>{l.name}</div>
                  <div className="mono" style={{ fontSize: 10.5, color: "var(--g-ink-4)", marginTop: 1 }}>{l.group} · {l.elev} m</div>
                </div>
                <button onClick={() => setPickedIds(pickedIds.filter(x => x !== l.id))} style={{ background: "transparent", border: "none", padding: 8, color: "var(--g-ink-4)", cursor: "pointer", fontSize: 16, minHeight: 44, flexShrink: 0 }}>✕</button>
              </div>
            ))}
          </div>
        )}

        <button onClick={() => setLibOpen(true)} style={{
          display: "flex", alignItems: "center", justifyContent: "center", gap: 8,
          width: "100%", padding: "14px", minHeight: 52,
          background: "var(--g-card)", border: "1px dashed var(--g-rule)",
          borderRadius: "var(--g-r-3)", cursor: "pointer",
          fontSize: 14, color: "var(--g-ink-3)", fontFamily: "var(--g-font-sans)",
        }}>
          <svg width={16} height={16} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round"><path d="M12 5v14M5 12h14"/></svg>
          Ort aus Bibliothek wählen
        </button>
      </ScreenScroll>

      {/* Floating CTA */}
      {!isEdit && (
        <div style={{ position: "absolute", bottom: 16, left: 16, right: 16, zIndex: 10 }}>
          <MBtn block variant={canAdv ? "primary" : "quiet"} size="xl"
            onClick={canAdv ? onContinue : undefined}
            style={!canAdv ? { opacity: 0.4 } : {}}>
            {canAdv ? "Idealwerte festlegen →" : `noch ${2 - pickedIds.length} Ort${2 - pickedIds.length !== 1 ? "e" : ""} nötig`}
          </MBtn>
        </div>
      )}

      {/* Bibliotheks-Sheet */}
      <Sheet open={libOpen} onClose={() => setLibOpen(false)} title="Ort wählen" snap="full">
        <ScreenScroll padding={0} style={{ paddingBottom: 20 }}>
          {Object.entries(groups).map(([group, items]) => (
            <div key={group} style={{ marginBottom: 8 }}>
              <div className="mono" style={{ fontSize: 10, color: "var(--g-ink-4)", letterSpacing: "0.10em", textTransform: "uppercase", padding: "8px 16px 4px", fontWeight: 600 }}>{group}</div>
              {items.map((l, i) => {
                const on = pickedIds.includes(l.id);
                return (
                  <button key={l.id} onClick={() => {
                    setPickedIds(on ? pickedIds.filter(x => x !== l.id) : [...pickedIds, l.id]);
                  }} style={{
                    display: "flex", alignItems: "center", gap: 14, width: "100%",
                    padding: "12px 16px", minHeight: 52, background: on ? "var(--g-accent-tint)" : "transparent",
                    border: "none", borderTop: i === 0 ? "1px solid var(--g-rule-soft)" : "none",
                    borderBottom: "1px solid var(--g-rule-soft)", cursor: "pointer", textAlign: "left",
                    fontFamily: "var(--g-font-sans)",
                  }}>
                    <span style={{ width: 22, height: 22, borderRadius: 4, border: `1.5px solid ${on ? "var(--g-accent)" : "var(--g-rule)"}`, background: on ? "var(--g-accent)" : "transparent", display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0 }}>
                      {on && <svg width="11" height="11" viewBox="0 0 12 12" fill="none" stroke="#fff" strokeWidth="2.5"><path d="M2 6l3 3 5-6"/></svg>}
                    </span>
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <div style={{ fontSize: 14, fontWeight: on ? 600 : 500, color: on ? "var(--g-accent-deep)" : "var(--g-ink)" }}>{l.name}</div>
                      <div className="mono" style={{ fontSize: 10.5, color: "var(--g-ink-3)", marginTop: 1 }}>{l.elev} m</div>
                    </div>
                  </button>
                );
              })}
            </div>
          ))}
        </ScreenScroll>
      </Sheet>
    </React.Fragment>
  );
}

/* ─── Tab 3: Idealwerte ─── */
function CEM_IdealwerteTab({ profileId, isEdit, onContinue }) {
  const profiles = window.LOCATION_ACTIVITY_PROFILES || [];
  const profile  = profiles.find(p => p.id === profileId) || { label: profileId };
  const ideals   = CEM_IDEALS[profileId] || CEM_IDEALS["wintersport"];

  return (
    <ScreenScroll padding={14} style={{ paddingBottom: 88 }}>
      <div className="mono" style={{ fontSize: 10, color: "var(--g-ink-4)", letterSpacing: "0.08em", textTransform: "uppercase", marginBottom: 12 }}>
        {profile.label} · {ideals.length} Metriken
      </div>
      <div style={{ background: "var(--g-card)", border: "1px solid var(--g-rule)", borderRadius: "var(--g-r-3)", overflow: "hidden" }}>
        {ideals.map((it, i) => {
          const [start, end] = it.pos;
          return (
            <div key={i} style={{ padding: "14px 14px", borderBottom: i < ideals.length - 1 ? "1px solid var(--g-rule-soft)" : "none" }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", marginBottom: 8 }}>
                <div style={{ fontSize: 14, fontWeight: 600, color: "var(--g-ink)" }}>{it.label}</div>
                <span className="mono" style={{ fontSize: 11, fontWeight: 600, color: "var(--g-accent-deep)" }}>{it.ideal}</span>
              </div>
              <div style={{ position: "relative", height: 8, background: "var(--g-rule-soft)", borderRadius: 4, marginBottom: 5 }}>
                <div style={{ position: "absolute", top: 0, bottom: 0, left: `${start * 100}%`, width: `${(end - start) * 100}%`, background: "var(--g-accent)", opacity: 0.85 }}/>
                <div style={{ position: "absolute", top: -3, left: `${start * 100}%`, width: 14, height: 14, marginLeft: -7, background: "#fff", border: "2px solid var(--g-accent)", borderRadius: "50%" }}/>
                <div style={{ position: "absolute", top: -3, left: `${end * 100}%`, width: 14, height: 14, marginLeft: -7, background: "#fff", border: "2px solid var(--g-accent)", borderRadius: "50%" }}/>
              </div>
              <div style={{ display: "flex", justifyContent: "space-between" }}>
                <span className="mono" style={{ fontSize: 9.5, color: "var(--g-ink-4)" }}>{it.scale[0]}</span>
                <span className="mono" style={{ fontSize: 9.5, color: "var(--g-ink-4)", fontStyle: "italic" }}>{it.notes}</span>
                <span className="mono" style={{ fontSize: 9.5, color: "var(--g-ink-4)" }}>{it.scale[1]}</span>
              </div>
            </div>
          );
        })}
      </div>
      <button style={{ display: "flex", alignItems: "center", justifyContent: "center", gap: 8, width: "100%", marginTop: 10, padding: "13px", border: "1px dashed var(--g-rule)", borderRadius: "var(--g-r-3)", background: "transparent", color: "var(--g-ink-3)", fontSize: 14, cursor: "pointer", fontFamily: "var(--g-font-sans)" }}>
        + Metrik hinzufügen
      </button>

      {!isEdit && (
        <div style={{ position: "absolute", bottom: 16, left: 16, right: 16, zIndex: 10 }}>
          <MBtn block variant="primary" size="xl" onClick={onContinue}>Layout einrichten →</MBtn>
        </div>
      )}
    </ScreenScroll>
  );
}

/* ─── Tab 4: Layout ─── */
function CEM_LayoutTab({ isEdit, onContinue }) {
  const [channel, setChannel] = React.useState("email");
  const chDef = CEM_CHANNELS.find(c => c.id === channel);

  const colDefs = [
    { label: "Score (Gesamt)",   on: true,  pinned: true },
    { label: "Schneehöhe",       on: true  },
    { label: "Neuschnee 24 h",   on: true  },
    { label: "Wind / Böen",      on: true  },
    { label: "Temperatur gef.",  on: true  },
    { label: "Sonnenstunden",    on: channel === "email" },
    { label: "Bewölkung",        on: false },
  ];

  return (
    <ScreenScroll padding={14} style={{ paddingBottom: 88 }}>
      {/* Kanal-Segmented */}
      <div className="mono" style={{ fontSize: 10, color: "var(--g-ink-4)", letterSpacing: "0.10em", textTransform: "uppercase", marginBottom: 10 }}>
        Kanal wählen
      </div>
      <div style={{ display: "flex", gap: 6, marginBottom: 20 }}>
        {CEM_CHANNELS.map(c => (
          <button key={c.id} onClick={() => setChannel(c.id)} style={{
            flex: 1, padding: "10px 8px", background: channel === c.id ? "var(--g-accent-tint)" : "var(--g-card)",
            border: channel === c.id ? "1.5px solid var(--g-accent)" : "1px solid var(--g-rule)",
            borderRadius: "var(--g-r-2)", cursor: "pointer", textAlign: "center", fontFamily: "var(--g-font-sans)",
          }}>
            <div style={{ fontSize: 13, fontWeight: 600, color: channel === c.id ? "var(--g-accent-deep)" : "var(--g-ink)" }}>{c.label}</div>
            <div className="mono" style={{ fontSize: 9.5, color: "var(--g-ink-3)", marginTop: 2 }}>
              {c.maxCols === Infinity ? "∞" : c.maxCols === 0 ? "—" : `max ${c.maxCols}`}
            </div>
          </button>
        ))}
      </div>

      {/* Spalten */}
      <div className="mono" style={{ fontSize: 10, color: "var(--g-ink-4)", letterSpacing: "0.10em", textTransform: "uppercase", marginBottom: 10 }}>
        Spalten
      </div>
      <div style={{ background: "var(--g-card)", border: "1px solid var(--g-rule)", borderRadius: "var(--g-r-3)", overflow: "hidden" }}>
        {colDefs.map((col, i) => {
          const overLimit = chDef.maxCols !== Infinity && chDef.maxCols !== 0 && i >= chDef.maxCols + 1;
          const dimmed = overLimit && col.on;
          return (
            <div key={i} style={{ display: "flex", alignItems: "center", gap: 10, padding: "12px 14px", minHeight: 48, borderBottom: i < colDefs.length - 1 ? "1px solid var(--g-rule-soft)" : "none", opacity: dimmed ? 0.5 : 1, background: dimmed ? "rgba(192,138,26,0.05)" : "transparent" }}>
              <span style={{ flex: 1, fontSize: 14, color: "var(--g-ink-2)" }}>{col.label}</span>
              {col.pinned && <span className="mono" style={{ fontSize: 9, color: "var(--g-ink-4)", textTransform: "uppercase" }}>fix</span>}
              {dimmed && <span className="mono" style={{ fontSize: 9.5, color: "var(--g-warn)", fontWeight: 600 }}>↳ Detail</span>}
              <Switch checked={col.on} tone="good"/>
            </div>
          );
        })}
      </div>
      <div className="mono" style={{ marginTop: 8, fontSize: 10.5, color: "var(--g-ink-4)" }}>
        {chDef.maxCols === Infinity ? "Email zeigt alles" : chDef.maxCols === 0 ? "SMS: kein Tabellen-Layout — Fließtext" : `Max ${chDef.maxCols} Spalten in Telegram`}
      </div>

      {!isEdit && (
        <div style={{ position: "absolute", bottom: 16, left: 16, right: 16, zIndex: 10 }}>
          <MBtn block variant="primary" size="xl" onClick={onContinue}>Versand einrichten →</MBtn>
        </div>
      )}
    </ScreenScroll>
  );
}

/* ─── Tab 5: Versand ─── */
function CEM_VersandTab({ name, pickedIds, isEdit, isReady }) {
  return (
    <ScreenScroll padding={14} style={{ paddingBottom: 20 }}>
      <div className="mono" style={{ fontSize: 10, color: "var(--g-ink-4)", letterSpacing: "0.10em", textTransform: "uppercase", marginBottom: 10 }}>
        Versandzeit
      </div>
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 8, marginBottom: 20 }}>
        {[
          { label: "Versand",     value: "06:30", sub: "täglich" },
          { label: "Fenster",     value: "09–16", sub: "bewertet" },
          { label: "Horizont",    value: "+48 h", sub: "morgen + ü." },
        ].map(item => (
          <button key={item.label} style={{ padding: "11px 10px", background: "var(--g-card)", border: "1px solid var(--g-rule)", borderRadius: "var(--g-r-2)", textAlign: "left", cursor: "pointer", fontFamily: "var(--g-font-sans)", display: "flex", flexDirection: "column", gap: 3 }}>
            <span className="mono" style={{ fontSize: 9, color: "var(--g-ink-4)", letterSpacing: "0.10em", textTransform: "uppercase" }}>{item.label}</span>
            <span style={{ fontSize: 15, fontWeight: 600, color: "var(--g-ink)", fontVariantNumeric: "tabular-nums" }}>{item.value}</span>
            <span style={{ fontSize: 10, color: "var(--g-ink-3)" }}>{item.sub}</span>
          </button>
        ))}
      </div>

      <div className="mono" style={{ fontSize: 10, color: "var(--g-ink-4)", letterSpacing: "0.10em", textTransform: "uppercase", marginBottom: 10 }}>
        Versand-Kanäle
      </div>
      <div style={{ background: "var(--g-card)", border: "1px solid var(--g-rule)", borderRadius: "var(--g-r-3)", overflow: "hidden", marginBottom: 20 }}>
        {[
          { label: "Email",    target: "gregor_zwanzig@henemm.com", on: true },
          { label: "Telegram", target: "@henemm",                    on: false },
          { label: "SMS",      target: "+49 151 12345 678",          on: false },
        ].map((ch, i) => (
          <div key={ch.label} style={{ display: "flex", alignItems: "center", gap: 12, padding: "13px 14px", minHeight: 52, borderTop: i === 0 ? "none" : "1px solid var(--g-rule-soft)" }}>
            <div style={{ flex: 1, minWidth: 0 }}>
              <div style={{ fontSize: 14.5, fontWeight: 600 }}>{ch.label}</div>
              <div className="mono" style={{ fontSize: 10.5, color: "var(--g-ink-3)", marginTop: 1, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{ch.target}</div>
            </div>
            <Switch checked={ch.on} tone="good"/>
          </div>
        ))}
      </div>

      {!isEdit && isReady && (
        <div style={{ padding: "16px", background: "var(--g-good)", borderRadius: "var(--g-r-3)", color: "#fff" }}>
          <div className="mono" style={{ fontSize: 10, letterSpacing: "0.12em", textTransform: "uppercase", color: "rgba(255,255,255,0.7)", marginBottom: 6 }}>Bereit zum Aktivieren</div>
          <div style={{ fontSize: 15, fontWeight: 600 }}>„{name}" · {pickedIds.length} Orte</div>
          <div style={{ fontSize: 12.5, color: "rgba(255,255,255,0.85)", marginTop: 4, lineHeight: 1.5 }}>
            Die Webseite musst du im Urlaub nicht öffnen — alles kommt automatisch in dein Postfach.
          </div>
        </div>
      )}
    </ScreenScroll>
  );
}

/* ════════════════════════════════════════════════════════════════════
 *  Main: ScreenCompareEditorMobile
 * ════════════════════════════════════════════════════════════════════ */
function ScreenCompareEditorMobile({ mode = "create", preset = "empty", initialTab, editingName, activated = false } = {}) {
  const isEdit = mode === "edit";

  const CEM_PRESETS = {
    empty:           { name: "", region: "", profileId: "wintersport", pickedIds: [], idealsVis: false, layoutVis: false, versandVis: false, tab: "vergleich" },
    name_done:       { name: "Skitouren Hochkönig", region: "Hochkönig · Salzburger Land", profileId: "wintersport", pickedIds: [], idealsVis: false, layoutVis: false, versandVis: false, tab: "orte" },
    orte_done:       { name: "Skitouren Hochkönig", region: "Hochkönig · Salzburger Land", profileId: "wintersport", pickedIds: ["loc-01", "loc-07", "loc-08", "loc-09"], idealsVis: false, layoutVis: false, versandVis: false, tab: "idealwerte" },
    idealwerte_done: { name: "Skitouren Hochkönig", region: "Hochkönig · Salzburger Land", profileId: "wintersport", pickedIds: ["loc-01", "loc-07", "loc-08", "loc-09"], idealsVis: true,  layoutVis: false, versandVis: false, tab: "layout" },
    all_done:        { name: "Skitouren Hochkönig", region: "Hochkönig · Salzburger Land", profileId: "wintersport", pickedIds: ["loc-01", "loc-07", "loc-08", "loc-09"], idealsVis: true,  layoutVis: true,  versandVis: true,  tab: "versand" },
  };

  const p = isEdit ? {
    name: editingName || "Skitouren Hochkönig", region: "Hochkönig · Salzburger Land", profileId: "wintersport",
    pickedIds: ["loc-01", "loc-07", "loc-08", "loc-09"], idealsVis: true, layoutVis: true, versandVis: true,
    tab: initialTab || "vergleich",
  } : (CEM_PRESETS[preset] || CEM_PRESETS.empty);

  const [name,       setName]       = React.useState(p.name);
  const [region,     setRegion]     = React.useState(p.region);
  const [profileId,  setProfileId]  = React.useState(p.profileId);
  const [pickedIds,  setPickedIds]  = React.useState(p.pickedIds);
  const [idealsVis,  setIdealsVis]  = React.useState(p.idealsVis);
  const [layoutVis,  setLayoutVis]  = React.useState(p.layoutVis);
  const [versandVis, setVersandVis] = React.useState(p.versandVis);
  const [tab,        setTab]        = React.useState(p.tab);
  const [dirty,      setDirty]      = React.useState(false);
  const [lockHint,   setLockHint]   = React.useState(null);

  const ul   = CEM_unlocked(name, pickedIds.length, idealsVis, layoutVis);
  const done = CEM_doneSet(name, pickedIds.length, idealsVis, layoutVis, versandVis);
  const isReady = done.has("versand");

  const switchTab = (id) => {
    setTab(id);
    if (id === "idealwerte") setIdealsVis(true);
    if (id === "layout")     setLayoutVis(true);
    if (id === "versand")    setVersandVis(true);
    if (isEdit)              setDirty(true);
  };

  const handleLockedTap = (t) => {
    setLockHint(t.lockHint || "Schritt noch gesperrt");
    setTimeout(() => setLockHint(null), 2000);
  };

  const markDirty = (fn) => (...args) => { fn(...args); if (isEdit) setDirty(true); };

  const tabTitle = {
    vergleich:  "Vergleich",
    orte:       "Orte",
    idealwerte: "Idealwerte",
    layout:     "Layout",
    versand:    "Versand",
  }[tab] || "Vergleich";

  return (
    <PhoneFrame height={780} time="09:41">
      <div style={{ position: "absolute", inset: 0, display: "flex", flexDirection: "column", background: "var(--g-paper)" }}>

        {/* TopAppBar */}
        <TopAppBar
          title={tabTitle}
          eyebrow={name.trim() || (isEdit ? "Bearbeiten" : "Neuer Vergleich")}
          leftIcon="back"
          right={
            isEdit ? (
              <button style={{
                height: 44, padding: "0 14px", border: "none", background: "transparent",
                color: dirty ? "var(--g-accent)" : "var(--g-ink-4)",
                fontWeight: 600, fontSize: 14, cursor: dirty ? "pointer" : "default",
                fontFamily: "var(--g-font-sans)",
              }} onClick={() => setDirty(false)}>
                {dirty ? "Speichern" : "Gespeichert"}
              </button>
            ) : (
              <button style={{
                height: 44, padding: "0 14px", border: "none", background: "transparent",
                color: isReady ? "var(--g-accent)" : "var(--g-ink-4)",
                fontWeight: 600, fontSize: 14, cursor: isReady ? "pointer" : "default",
                fontFamily: "var(--g-font-sans)",
              }}>
                {isReady ? "Aktivieren" : "…"}
              </button>
            )
          }
        />

        {/* Fortschritt (create only) */}
        {!isEdit && <CEM_Progress done={done}/>}

        {/* Tab-Bar */}
        <CEM_TabBar active={tab} unlocked={ul} onChange={switchTab} isEdit={isEdit} onLockedTap={handleLockedTap}/>

        {/* Tab-Inhalt */}
        <div style={{ flex: 1, position: "relative", overflow: "hidden" }}>
          {tab === "vergleich"  && <CEM_VergleichTab  name={name} onName={markDirty(setName)} region={region} onRegion={markDirty(setRegion)} profileId={profileId} onProfile={markDirty(setProfileId)} isEdit={isEdit} onContinue={() => switchTab("orte")}/>}
          {tab === "orte"       && <CEM_OrteTab       pickedIds={pickedIds} setPickedIds={markDirty(setPickedIds)} isEdit={isEdit} onContinue={() => switchTab("idealwerte")}/>}
          {tab === "idealwerte" && <CEM_IdealwerteTab profileId={profileId} isEdit={isEdit} onContinue={() => switchTab("layout")}/>}
          {tab === "layout"     && <CEM_LayoutTab     isEdit={isEdit} onContinue={() => switchTab("versand")}/>}
          {tab === "versand"    && <CEM_VersandTab    name={name} pickedIds={pickedIds} isEdit={isEdit} isReady={isReady}/>}
        </div>

        {/* Lock-Hint Toast */}
        {lockHint && <CEM_LockHint msg={lockHint}/>}
      </div>
    </PhoneFrame>
  );
}

window.ScreenCompareEditorMobile = ScreenCompareEditorMobile;
