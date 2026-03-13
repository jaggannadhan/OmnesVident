import { Suspense, useState, useCallback } from "react";
import { Canvas } from "@react-three/fiber";
import { OrbitControls, Stars } from "@react-three/drei";
import { Earth } from "./Earth";
import { GlobeGrid } from "./GlobeGrid";
import { ContinentLines } from "./ContinentLines";
import { NewsBlips } from "./NewsBlips";
import { useNews } from "../../hooks/useNews";
import { CATEGORY_COLORS } from "./Marker";
import { CATEGORY_META } from "../NewsCard";

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
// Legend overlay (pure DOM, outside Canvas)
// ---------------------------------------------------------------------------

function Legend() {
  const entries = Object.entries(CATEGORY_COLORS).filter(
    ([cat]) => cat !== "POLITICS" // deduplicate (shares colour with WORLD)
  );
  return (
    <div className="absolute bottom-3 left-3 flex flex-wrap gap-x-3 gap-y-1 pointer-events-none">
      {entries.map(([cat, color]) => (
        <div key={cat} className="flex items-center gap-1">
          <span
            className="inline-block w-2 h-2 rounded-full"
            style={{ background: color, boxShadow: `0 0 4px ${color}` }}
          />
          <span className="text-[9px] font-mono text-slate-500 uppercase tracking-wider">
            {CATEGORY_META[cat]?.label ?? cat}
          </span>
        </div>
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
}

export function GlobeScene({ region }: GlobeSceneProps) {
  const { data, isLoading } = useNews({ region, limit: 200 });
  const stories = data?.stories ?? [];

  // Pause auto-rotation while the cursor is over the globe
  const [cursorOver, setCursorOver] = useState(false);

  // Card state lifted here so the globe can freeze while a card is open
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const handleSelectId = useCallback((id: string | null) => setSelectedId(id), []);
  const cardOpen = selectedId !== null;

  return (
    <div
      className="relative w-full rounded-xl overflow-hidden border border-rim bg-base"
      style={{ height: "480px" }}
      onPointerEnter={() => setCursorOver(true)}
      onPointerLeave={() => setCursorOver(false)}
    >

      {/* Live blip count */}
      <div className="absolute top-3 left-3 z-10 flex items-center gap-2 pointer-events-none">
        <span className="text-[10px] font-mono text-slate-500">
          {isLoading ? "Loading…" : `${stories.length} blips active`}
        </span>
        {!isLoading && stories.length > 0 && (
          <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
        )}
      </div>

      {/* Interaction hint */}
      <div className="absolute top-3 right-3 z-10 pointer-events-none">
        <span className="text-[9px] font-mono text-slate-700">Drag · Scroll · Click marker</span>
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
            <ContinentLines />
            {stories.length > 0 && (
              <NewsBlips
                stories={stories}
                selectedId={selectedId}
                onSelectId={handleSelectId}
              />
            )}
          </Earth>
        </Suspense>
      </Canvas>

      <Legend />
    </div>
  );
}
