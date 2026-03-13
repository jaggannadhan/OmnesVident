import type { ReactNode } from "react";
import { useRef } from "react";
import { useFrame } from "@react-three/fiber";
import type { Group } from "three";

const GLOBE_RADIUS = 2;

interface EarthProps {
  paused?: boolean;
  /** Grid lines and continent overlays rendered inside the rotating group */
  children?: ReactNode;
}

export function Earth({ paused = false, children }: EarthProps) {
  const groupRef = useRef<Group>(null);

  useFrame((_, delta) => {
    if (!paused && groupRef.current) {
      groupRef.current.rotation.y += delta * 0.03;
    }
  });

  return (
    <group ref={groupRef}>

      {/* Core globe — vivid deep ocean blue */}
      <mesh>
        <sphereGeometry args={[GLOBE_RADIUS, 64, 64]} />
        <meshStandardMaterial
          color="#0f3570"
          roughness={0.6}
          metalness={0.3}
          emissive="#1a5ccc"
          emissiveIntensity={0.35}
        />
      </mesh>

      {/* Grid lines + continent overlays (injected by GlobeScene) */}
      {children}

      {/* Outer atmosphere — bright halo.
          depthWrite={false} so this decorative shell never overwrites the depth
          buffer and occludes continent lines / grid that sit inside it. */}
      <mesh>
        <sphereGeometry args={[GLOBE_RADIUS + 0.09, 32, 32]} />
        <meshBasicMaterial color="#60a5fa" transparent opacity={0.1} depthWrite={false} />
      </mesh>

      {/* Inner rim glow — same reasoning: must not write depth. */}
      <mesh>
        <sphereGeometry args={[GLOBE_RADIUS + 0.025, 32, 32]} />
        <meshBasicMaterial color="#93c5fd" transparent opacity={0.14} depthWrite={false} />
      </mesh>

    </group>
  );
}

export { GLOBE_RADIUS };
