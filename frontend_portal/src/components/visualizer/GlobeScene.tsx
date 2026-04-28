import { Suspense, useState, useCallback, useEffect, useRef } from "react";
import { Canvas } from "@react-three/fiber";
import { OrbitControls, Stars } from "@react-three/drei";
import { Earth } from "./Earth";
import { GlobeGrid } from "./GlobeGrid";
import { ContinentLines } from "./ContinentLines";
import { StateBorders } from "./StateBorders";
import { NewsBlips } from "./NewsBlips";
import { useNews } from "../../hooks/useNews";
import { CATEGORY_COLORS } from "./Marker";
import { CATEGORY_META } from "../NewsCard";

// ---------------------------------------------------------------------------
// State Focus — subdivisions available per high-res country
// ---------------------------------------------------------------------------

const FOCUS_STATES: Record<string, Array<{ code: string; name: string }>> = {
  US: [
    { code: "US-CA", name: "CA" }, { code: "US-TX", name: "TX" },
    { code: "US-NY", name: "NY" }, { code: "US-FL", name: "FL" },
    { code: "US-WA", name: "WA" }, { code: "US-IL", name: "IL" },
    { code: "US-GA", name: "GA" }, { code: "US-OH", name: "OH" },
    { code: "US-NC", name: "NC" }, { code: "US-PA", name: "PA" },
  ],
  IN: [
    { code: "IN-MH", name: "MH" }, { code: "IN-DL", name: "DL" },
    { code: "IN-KA", name: "KA" }, { code: "IN-TN", name: "TN" },
    { code: "IN-WB", name: "WB" }, { code: "IN-GJ", name: "GJ" },
    { code: "IN-RJ", name: "RJ" }, { code: "IN-UP", name: "UP" },
  ],
  CN: [
    { code: "CN-BJ", name: "BJ" }, { code: "CN-SH", name: "SH" },
    { code: "CN-GD", name: "GD" }, { code: "CN-SC", name: "SC" },
    { code: "CN-HB", name: "HB" }, { code: "CN-ZJ", name: "ZJ" },
    { code: "CN-JS", name: "JS" },
  ],
  BR: [
    { code: "BR-SP", name: "SP" }, { code: "BR-RJ", name: "RJ" },
    { code: "BR-MG", name: "MG" }, { code: "BR-CE", name: "CE" },
    { code: "BR-BA", name: "BA" }, { code: "BR-RS", name: "RS" },
  ],
  CA: [
    { code: "CA-ON", name: "ON" }, { code: "CA-BC", name: "BC" },
    { code: "CA-QC", name: "QC" }, { code: "CA-AB", name: "AB" },
  ],
  AU: [
    { code: "AU-NSW", name: "NSW" }, { code: "AU-VIC", name: "VIC" },
    { code: "AU-QLD", name: "QLD" }, { code: "AU-WA",  name: "WA"  },
  ],
  ZA: [
    { code: "ZA-GT", name: "GT" }, { code: "ZA-WC", name: "WC" },
    { code: "ZA-KZN", name: "KZN" },
  ],
};

// ---------------------------------------------------------------------------
// Loading fallback rendered inside the Canvas
// ---------------------------------------------------------------------------

function GlobeLoader() {
  return (
    <mesh>
      <sphereGeometry args={[2, 16, 16]} />
      <meshBasicMaterial color="#0a1628" wireframe />
    </mesh>
  );
}

// ---------------------------------------------------------------------------
// Legend overlay — collapsible
// ---------------------------------------------------------------------------

const LEGEND_PREVIEW_COLORS = ["#f87171", "#22d3ee", "#34d399", "#a78bfa", "#fb923c"];

function CollapsibleLegend() {
  const [open, setOpen] = useState(false);
  const entries = Object.entries(CATEGORY_COLORS);

  return (
    <div className="absolute bottom-3 left-3 z-10">
      {/* Toggle button — always visible */}
      <button
        onClick={() => setOpen((p) => !p)}
        className="flex items-center gap-1.5 px-2 py-1 rounded-md border border-rim bg-base/80 backdrop-blur-sm text-slate-400 hover:text-slate-200 hover:border-rim-bright transition-colors"
      >
        {/* Mini colour dots */}
        <span className="flex gap-0.5">
          {LEGEND_PREVIEW_COLORS.map((c) => (
            <span
              key={c}
              className="inline-block w-1.5 h-1.5 rounded-full"
              style={{ background: c, boxShadow: `0 0 3px ${c}` }}
            />
          ))}
        </span>
        <span className="text-[9px] font-mono uppercase tracking-widest">Legend</span>
        <span className="text-[8px] text-slate-600">{open ? "▲" : "▼"}</span>
      </button>

      {/* Expanded panel */}
      {open && (
        <div className="mt-1 p-2 rounded-md border border-rim bg-base/90 backdrop-blur-sm flex flex-wrap gap-x-3 gap-y-1.5 max-w-[260px]">
          {entries.map(([cat, color]) => (
            <div key={cat} className="flex items-center gap-1">
              <span
                className="inline-block w-2 h-2 rounded-full shrink-0"
                style={{ background: color, boxShadow: `0 0 4px ${color}` }}
              />
              <span className="text-[9px] font-mono text-slate-400 uppercase tracking-wider">
                {CATEGORY_META[cat]?.label ?? cat}
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Sync countdown — counts to the next 15-minute scheduler boundary
// ---------------------------------------------------------------------------

function SyncCountdown() {
  const [secsLeft, setSecsLeft] = useState(() => {
    const ms = 15 * 60 * 1000;
    return Math.ceil((ms - (Date.now() % ms)) / 1000);
  });
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    intervalRef.current = setInterval(() => {
      setSecsLeft(() => {
        const ms = 15 * 60 * 1000;
        return Math.ceil((ms - (Date.now() % ms)) / 1000);
      });
    }, 1000);
    return () => { if (intervalRef.current) clearInterval(intervalRef.current); };
  }, []);

  const m = String(Math.floor(secsLeft / 60)).padStart(2, "0");
  const s = String(secsLeft % 60).padStart(2, "0");

  return (
    <div className="flex items-center gap-2 px-2.5 py-1 rounded-md border border-cyan-500/20 bg-cyan-400/5 backdrop-blur-sm pointer-events-none">
      <span className="w-1.5 h-1.5 rounded-full bg-cyan-400 animate-pulse shrink-0" />
      <span className="text-[9px] font-mono text-cyan-500/80 uppercase tracking-widest">
        News in{" "}
        <span className="text-cyan-300 font-semibold tabular-nums">{m}:{s}</span>
      </span>
    </div>
  );
}

// ---------------------------------------------------------------------------
// State Focus selector bar (shown only for the 7 high-res countries)
// ---------------------------------------------------------------------------

interface StateFocusBarProps {
  country: string;
  focusState: string | null;
  onFocusState: (code: string | null) => void;
}

function StateFocusBar({ country, focusState, onFocusState }: StateFocusBarProps) {
  const states = FOCUS_STATES[country];
  if (!states) return null;

  return (
    <div className="absolute bottom-9 left-3 right-3 flex flex-wrap items-center gap-1 z-10 pointer-events-auto">
      <span className="text-[8px] font-mono text-slate-700 mr-1 uppercase tracking-widest">
        State Focus:
      </span>

      {/* "All" clears the focus filter */}
      <button
        onClick={() => onFocusState(null)}
        className={`text-[8px] font-mono px-1.5 py-0.5 rounded border transition-colors ${
          focusState === null
            ? "border-cyan-400/60 text-cyan-400 bg-cyan-400/10"
            : "border-rim text-slate-600 hover:text-slate-400"
        }`}
      >
        All
      </button>

      {states.map(({ code, name }) => (
        <button
          key={code}
          onClick={() => onFocusState(focusState === code ? null : code)}
          className={`text-[8px] font-mono px-1.5 py-0.5 rounded border transition-colors ${
            focusState === code
              ? "border-cyan-400/60 text-cyan-400 bg-cyan-400/10"
              : "border-rim text-slate-600 hover:text-slate-400"
          }`}
        >
          {name}
        </button>
      ))}
    </div>
  );
}

// ---------------------------------------------------------------------------
// GlobeScene
// ---------------------------------------------------------------------------

interface GlobeSceneProps {
  /** Optional: restrict blips to a region; undefined = global */
  region?: string;
  /** Optional: restrict blips to a category; undefined = all */
  category?: string;
  /** ISO-8601 — show stories on or after this timestamp */
  startDate?: string;
  /** ISO-8601 — show stories on or before this timestamp */
  endDate?: string;
}

export function GlobeScene({ region, category, startDate, endDate }: GlobeSceneProps) {
  const { data } = useNews({ region, category, limit: 1000, start_date: startDate, end_date: endDate });
  const stories = data?.stories ?? [];

  // Pause auto-rotation while the cursor is over the globe
  const [cursorOver, setCursorOver] = useState(false);

  // Card state lifted here so the globe can freeze while a card is open
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const handleSelectId = useCallback((id: string | null) => setSelectedId(id), []);
  const cardOpen = selectedId !== null;

  // State Focus — reset whenever the active country changes
  const [focusState, setFocusState] = useState<string | null>(null);
  useEffect(() => { setFocusState(null); }, [region]);

  const hasStateFocus = region !== undefined && FOCUS_STATES[region] !== undefined;

  return (
    <div
      className="relative w-full rounded-xl overflow-hidden border border-rim bg-base"
      style={{ height: "480px" }}
      onPointerEnter={() => setCursorOver(true)}
      onPointerLeave={() => setCursorOver(false)}
    >

      {/* Sync countdown — top-right */}
      <div className="absolute top-3 right-3 z-10">
        <SyncCountdown />
      </div>

      <Canvas
        camera={{ position: [0, 0, 5.5], fov: 45, near: 0.1, far: 100 }}
        gl={{ antialias: true, alpha: false }}
        style={{ background: "#02030a" }}
      >
        {/* Lighting — brighter to make the globe clearly visible */}
        <ambientLight intensity={0.45} />
        <pointLight position={[8, 5, 6]} intensity={3.5} color="#6699ff" />
        <pointLight position={[-6, -3, -4]} intensity={0.8} color="#2255cc" />
        <pointLight position={[0, 6, 0]} intensity={1.2} color="#88bbff" />

        {/* Background stars */}
        <Stars radius={80} depth={50} count={4000} factor={3} saturation={0} fade speed={0.4} />

        {/* Controls — autoRotate paused when cursor is over the canvas */}
        <OrbitControls
          enableZoom
          enablePan={false}
          minDistance={3}
          maxDistance={9}
          dampingFactor={0.08}
          enableDamping
          autoRotate={!cursorOver && !cardOpen}
          autoRotateSpeed={0.4}
        />

        <Suspense fallback={<GlobeLoader />}>
          <Earth paused={cursorOver || cardOpen}>
            <GlobeGrid />
            <StateBorders />
            <ContinentLines />
            {stories.length > 0 && (
              <NewsBlips
                stories={stories}
                selectedId={selectedId}
                onSelectId={handleSelectId}
                focusState={focusState}
              />
            )}
          </Earth>
        </Suspense>
      </Canvas>

      {/* State Focus bar — 7 high-res countries only */}
      {hasStateFocus && (
        <StateFocusBar
          country={region!}
          focusState={focusState}
          onFocusState={setFocusState}
        />
      )}

      <CollapsibleLegend />
    </div>
  );
}
