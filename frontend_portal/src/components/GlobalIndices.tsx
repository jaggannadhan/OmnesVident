// Placeholder market indices. Real analytics will replace this later;
// the values here are stable mock data so the layout reads correctly
// without flickering.

const INDICES = [
  { name: "DOW JONES",   value: "38,124.0", delta: "+0.14%", up: true  },
  { name: "BRENT CRUDE", value: "$78.14",   delta: "-1.22%", up: false },
  { name: "XAU/USD",     value: "$2,342.1", delta: "+0.85%", up: true  },
  { name: "BTC/USD",     value: "$64,102",  delta: "+3.44%", up: true  },
];

export function GlobalIndices() {
  return (
    <section className="p-6 border-b border-rim">
      <h4 className="font-mono text-[10px] uppercase tracking-[0.3em] font-bold mb-5" style={{ color: "var(--color-text)", opacity: 0.6 }}>
        GLOBAL INDICES
      </h4>
      <div className="grid grid-cols-2 gap-3">
        {INDICES.map((idx) => (
          <div
            key={idx.name}
            className="p-3 border border-rim/70 bg-card/40"
          >
            <div className="font-mono text-[9px] uppercase mb-1" style={{ color: "var(--color-text)", opacity: 0.5 }}>
              {idx.name}
            </div>
            <div className="flex justify-between items-end">
              <span className="font-mono text-xs font-bold" style={{ color: "var(--color-text)" }}>
                {idx.value}
              </span>
              <span className={`font-mono text-[10px] ${idx.up ? "text-emerald-500" : "text-red-500"}`}>
                {idx.delta}
              </span>
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}
