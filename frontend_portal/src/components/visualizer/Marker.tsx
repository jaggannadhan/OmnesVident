import { useRef, useMemo, memo } from "react";
import { useFrame } from "@react-three/fiber";
import type { Mesh, MeshBasicMaterial } from "three";
import type { Vector3 } from "three";
import type { StoryOut } from "../../services/api";

/** Map category → hex colour per the A&D spec + extended palette */
export const CATEGORY_COLORS: Record<string, string> = {
  WORLD:         "#FF2E2E",
  POLITICS:      "#FF2E2E",
  TECHNOLOGY:    "#2E90FF",
  BUSINESS:      "#10B981",
  SCIENCE:       "#A855F7",
  HEALTH:        "#34D399",
  ENTERTAINMENT: "#EC4899",
  SPORTS:        "#F97316",
};

interface MarkerProps {
  story: StoryOut;
  position: Vector3;
  isSelected: boolean;
  onClick: () => void;
  /** How many stories share this region (used to scale blip size down) */
  regionCount: number;
}

export const Marker = memo(function Marker({ story, position, isSelected, onClick, regionCount }: MarkerProps) {
  const pulseRef  = useRef<Mesh>(null);
  const matRef    = useRef<MeshBasicMaterial>(null);

  // Each marker gets a deterministic phase offset so they don't all pulse in sync
  const phase = useMemo(
    () => story.dedup_group_id.split("").reduce((a, c) => a + c.charCodeAt(0), 0) % 628 / 100,
    [story.dedup_group_id]
  );

  const color = CATEGORY_COLORS[story.category] ?? "#ffffff";

  // Scale dot size down as more stories share the same region; min 0.012
  const baseRadius = useMemo(
    () => Math.max(0.012, 0.038 / Math.sqrt(regionCount)),
    [regionCount]
  );
  const haloRadius = baseRadius * 1.7;

  useFrame(({ clock }) => {
    const t = clock.getElapsedTime() * 1.6 + phase;
    const pulse = (Math.sin(t) + 1) / 2; // 0 → 1

    if (pulseRef.current) {
      const s = isSelected ? 1.4 + pulse * 1.6 : 1 + pulse * 1.2;
      pulseRef.current.scale.setScalar(s);
    }
    if (matRef.current) {
      matRef.current.opacity = isSelected ? 0.8 - pulse * 0.5 : 0.5 - pulse * 0.35;
    }
  });

  return (
    <group position={position}>

      {/* Large invisible hit sphere — makes the marker easy to click without
          zooming in. Radius 0.12 gives a generous target regardless of how
          many stories share the region (baseRadius can be as small as 0.012). */}
      <mesh onClick={(e) => { e.stopPropagation(); onClick(); }}>
        <sphereGeometry args={[0.12, 8, 8]} />
        <meshBasicMaterial transparent opacity={0} depthWrite={false} />
      </mesh>

      {/* Core dot (visual only — click handled by hit sphere above) */}
      <mesh>
        <sphereGeometry args={[isSelected ? baseRadius * 1.45 : baseRadius, 8, 8]} />
        <meshBasicMaterial color={color} />
      </mesh>

      {/* Pulsing halo */}
      <mesh ref={pulseRef}>
        <sphereGeometry args={[haloRadius, 8, 8]} />
        <meshBasicMaterial
          ref={matRef}
          color={color}
          transparent
          opacity={0.4}
        />
      </mesh>

      {/* Selection ring */}
      {isSelected && (
        <mesh>
          <torusGeometry args={[baseRadius * 2.6, 0.008, 6, 24]} />
          <meshBasicMaterial color={color} />
        </mesh>
      )}

    </group>
  );
});
