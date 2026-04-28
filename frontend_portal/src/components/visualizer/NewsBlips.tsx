import { useMemo } from "react";
import { Html } from "@react-three/drei";
import type { Vector3 } from "three";
import type { StoryOut } from "../../services/api";
import { latLngToVector3, regionToVector3 } from "./utils/geoUtils";
import { Marker, CATEGORY_COLORS } from "./Marker";
import { HudOverlay } from "./HudOverlay";
import { GLOBE_RADIUS } from "./Earth";

/** Place markers just above the globe surface */
const MARKER_RADIUS = GLOBE_RADIUS + 0.04;

/** Show the +N count badge once a cluster has at least this many stories */
const BADGE_THRESHOLD = 3;

interface NewsBlipsProps {
  stories: StoryOut[];
  /** Lifted to GlobeScene so the globe can freeze while a card is open */
  selectedId: string | null;
  onSelectId: (id: string | null) => void;
  /** ISO 3166-2 code to spotlight; blips outside it are dimmed */
  focusState?: string | null;
}

interface Cluster {
  representative:   StoryOut;     // story rendered + opened on click
  ids:              string[];     // every story id in this bucket
  count:            number;
  dominantCategory: string;
  color:            string;       // dominant-category colour, or red if any breaking
  hasBreaking:      boolean;
  position:         Vector3;
}

/** Build a coordinate-bucket key (~1km granularity at 2 dp). */
function bucketKey(pos: Vector3): string {
  return `${pos.x.toFixed(2)},${pos.y.toFixed(2)},${pos.z.toFixed(2)}`;
}

/**
 * Pick the representative story for a cluster:
 *   1. prefer breaking news (highest heat_score)
 *   2. otherwise highest heat_score
 *   3. tie-break on most recent timestamp
 */
function pickRepresentative(group: StoryOut[]): StoryOut {
  const breaking = group.filter((s) => s.is_breaking);
  const pool = breaking.length > 0 ? breaking : group;
  return [...pool].sort((a, b) => {
    if (b.heat_score !== a.heat_score) return b.heat_score - a.heat_score;
    return new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime();
  })[0];
}

/** Most-frequent category in a group; ties resolved by alphabetical order. */
function dominantCategory(group: StoryOut[]): string {
  const counts: Record<string, number> = {};
  for (const s of group) counts[s.category] = (counts[s.category] ?? 0) + 1;
  return Object.entries(counts)
    .sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]))[0][0];
}

export function NewsBlips({ stories, selectedId, onSelectId, focusState }: NewsBlipsProps) {
  const clusters = useMemo<Cluster[]>(() => {
    // Resolve each story to a position on the globe
    const placed = stories.map((story) => ({
      story,
      pos:
        story.latitude != null && story.longitude != null
          ? latLngToVector3(story.latitude, story.longitude, MARKER_RADIUS)
          : regionToVector3(story.region_code, MARKER_RADIUS),
    }));

    // Group by coordinate bucket
    const groups = new Map<string, { pos: Vector3; items: StoryOut[] }>();
    for (const { story, pos } of placed) {
      const k = bucketKey(pos);
      const existing = groups.get(k);
      if (existing) existing.items.push(story);
      else groups.set(k, { pos, items: [story] });
    }

    // Build a Cluster per bucket
    return Array.from(groups.values()).map(({ pos, items }) => {
      const rep         = pickRepresentative(items);
      const cat         = dominantCategory(items);
      const hasBreaking = items.some((s) => s.is_breaking);
      const color       = hasBreaking
        ? "#FF2020"
        : (CATEGORY_COLORS[cat] ?? "#A78BFA");
      return {
        representative:   rep,
        ids:              items.map((s) => s.dedup_group_id),
        count:            items.length,
        dominantCategory: cat,
        color,
        hasBreaking,
        position:         pos,
      };
    });
  }, [stories]);

  // Find the cluster whose representative is currently selected
  const selectedCluster = clusters.find(
    (c) => c.representative.dedup_group_id === selectedId
  );

  return (
    <>
      {clusters.map((c) => {
        const id = c.representative.dedup_group_id;
        const dimmed = focusState != null && c.representative.region_code !== focusState;
        return (
          <Marker
            key={id}
            story={c.representative}
            position={c.position}
            isSelected={id === selectedId}
            regionCount={c.count}
            clusterColor={c.color}
            dimmed={dimmed}
            renderOrder={c.representative.region_code.includes("-") ? 2 : 1}
            onClick={() => onSelectId(selectedId === id ? null : id)}
          />
        );
      })}

      {/* Count badges — only on multi-story clusters that aren't dimmed away */}
      {clusters
        .filter(
          (c) =>
            c.count >= BADGE_THRESHOLD &&
            !(focusState != null && c.representative.region_code !== focusState)
        )
        .map((c) => (
          <Html
            key={`badge-${c.representative.dedup_group_id}`}
            position={c.position}
            center
            distanceFactor={1.4}
            style={{ pointerEvents: "none" }}
            zIndexRange={[10, 0]}
          >
            <div
              style={{
                transform: "translate(14px, -14px)",
                padding: "1px 5px",
                fontFamily: "JetBrains Mono, Menlo, monospace",
                fontSize: "9px",
                fontWeight: 700,
                color: c.color,
                background: "rgba(8,10,24,0.85)",
                border: `1px solid ${c.color}55`,
                borderRadius: "8px",
                whiteSpace: "nowrap",
                boxShadow: `0 0 6px ${c.color}55`,
                userSelect: "none",
              }}
            >
              +{c.count}
            </div>
          </Html>
        ))}

      {selectedCluster && (
        <HudOverlay
          story={selectedCluster.representative}
          position={selectedCluster.position}
          onClose={() => onSelectId(null)}
        />
      )}
    </>
  );
}
