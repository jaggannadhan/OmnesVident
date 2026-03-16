import { useRef, useMemo, useState, memo } from "react";
import { useFrame } from "@react-three/fiber";
import { AdditiveBlending } from "three";
import type { Mesh, MeshBasicMaterial } from "three";
import type { Vector3 } from "three";
import type { StoryOut } from "../../services/api";

/** Map category → hex colour per the A&D spec + extended palette */
export const CATEGORY_COLORS: Record<string, string> = {
  WORLD:         "#FF2E2E",
  POLITICS:      "#F59E0B",
  SCIENCE_TECH:  "#2E90FF",
  BUSINESS:      "#10B981",
  HEALTH:        "#34D399",
  ENTERTAINMENT: "#EC4899",
  SPORTS:        "#F97316",
};

interface MarkerProps {
  story: StoryOut;
  position: Vector3;
  isSelected: boolean;
  onClick: () => void;
  /** How many stories share this coordinate bucket (used for size + glow) */
  regionCount: number;
  /** When true, dims the marker — used by State Focus to fade out non-focus blips */
  dimmed?: boolean;
  /**
   * Three.js renderOrder — higher values draw on top.
   * Sub-national blips use 2; country-level blips use 1 so local markers
   * are never occluded by broad national placeholders at the same centroid.
   */
  renderOrder?: number;
}

export const Marker = memo(function Marker({
  story, position, isSelected, onClick, regionCount, dimmed = false, renderOrder = 1,
}: MarkerProps) {
  const pulseRef  = useRef<Mesh>(null);
  const matRef    = useRef<MeshBasicMaterial>(null);
  const [isHovered, setIsHovered] = useState(false);

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

  // Halo base opacity grows with density: busier regions glow brighter
  const haloBaseOpacity = Math.min(0.85, 0.4 + (regionCount - 1) * 0.08);

  useFrame(({ clock }) => {
    const t = clock.getElapsedTime() * 1.6 + phase;
    const pulse = (Math.sin(t) + 1) / 2; // 0 → 1

    if (pulseRef.current) {
      const hoverBoost = isHovered ? 1.3 : 1;
      const s = isSelected
        ? (1.4 + pulse * 1.6) * hoverBoost
        : (1 + pulse * 1.2) * hoverBoost;
      pulseRef.current.scale.setScalar(s);
    }
    if (matRef.current) {
      const baseOp = isSelected
        ? haloBaseOpacity * (1 - pulse * 0.4)
        : haloBaseOpacity * (1 - pulse * 0.5);
      matRef.current.opacity = baseOp * (dimmed ? 0.12 : 1);
    }
  });

  const alpha = dimmed ? 0.12 : 1;

  return (
    <group position={position} renderOrder={renderOrder}>

      {/* Large invisible hit sphere — generous click/hover target; disabled when dimmed */}
      {!dimmed && (
        <mesh
          onClick={(e) => { e.stopPropagation(); onClick(); }}
          onPointerEnter={(e) => { e.stopPropagation(); setIsHovered(true); }}
          onPointerLeave={(e) => { e.stopPropagation(); setIsHovered(false); }}
        >
          <sphereGeometry args={[0.12, 8, 8]} />
          <meshBasicMaterial transparent opacity={0} depthWrite={false} />
        </mesh>
      )}

      {/* Core dot — scales up on hover or selection; glows at density ≥ 5 */}
      <mesh>
        <sphereGeometry args={[
          isSelected ? baseRadius * 1.45
            : isHovered ? baseRadius * 1.8
            : baseRadius,
          8, 8
        ]} />
        <meshStandardMaterial
          color={color}
          emissive={color}
          emissiveIntensity={dimmed ? 0 : Math.min(2.5, Math.max(0, (regionCount - 1) * 0.5))}
          transparent={dimmed}
          opacity={alpha}
        />
      </mesh>

      {/* Pulsing halo — density-driven base opacity */}
      <mesh ref={pulseRef}>
        <sphereGeometry args={[haloRadius, 8, 8]} />
        <meshBasicMaterial
          ref={matRef}
          color={color}
          transparent
          opacity={haloBaseOpacity * alpha}
          blending={AdditiveBlending}
          depthWrite={false}
        />
      </mesh>

      {/* Selection ring — never shown on dimmed markers */}
      {isSelected && !dimmed && (
        <mesh>
          <torusGeometry args={[baseRadius * 2.6, 0.008, 6, 24]} />
          <meshBasicMaterial color={color} />
        </mesh>
      )}

    </group>
  );
});