import { useMemo } from "react";
import type { StoryOut } from "../../services/api";
import { latLngToVector3, regionToVector3, applyJitter } from "./utils/geoUtils";
import { Marker } from "./Marker";
import { HudOverlay } from "./HudOverlay";
import { GLOBE_RADIUS } from "./Earth";

/** Place markers just above the globe surface */
const MARKER_RADIUS = GLOBE_RADIUS + 0.04;

interface NewsBlipsProps {
  stories: StoryOut[];
  /** Lifted to GlobeScene so the globe can freeze while a card is open */
  selectedId: string | null;
  onSelectId: (id: string | null) => void;
  /** ISO 3166-2 code to spotlight; blips outside it are dimmed */
  focusState?: string | null;
}

/** Stable integer seed from a story's dedup_group_id */
function idSeed(id: string): number {
  return id.split("").reduce((acc, c) => acc + c.charCodeAt(0), 0);
}

export function NewsBlips({ stories, selectedId, onSelectId, focusState }: NewsBlipsProps) {
  // Count how many stories share the same resolved coordinate key so
  // jitter magnitude and glow can scale accordingly.
  const storyPositions = useMemo(() => {
    // First pass: resolve base positions without jitter
    const base = stories.map((story) => ({
      story,
      basePos:
        story.latitude != null && story.longitude != null
          ? latLngToVector3(story.latitude, story.longitude, MARKER_RADIUS)
          : regionToVector3(story.region_code, MARKER_RADIUS),
    }));

    // Count stories per coordinate bucket (rounded to 2 dp) for density
    const bucketCounts: Record<string, number> = {};
    for (const { basePos } of base) {
      const key = `${basePos.x.toFixed(2)},${basePos.y.toFixed(2)},${basePos.z.toFixed(2)}`;
      bucketCounts[key] = (bucketCounts[key] ?? 0) + 1;
    }

    // Second pass: apply jitter and attach density count
    return base.map(({ story, basePos }) => {
      const key = `${basePos.x.toFixed(2)},${basePos.y.toFixed(2)},${basePos.z.toFixed(2)}`;
      const density = bucketCounts[key] ?? 1;
      const seed    = idSeed(story.dedup_group_id);

      // Scale jitter with density so crowded regions spread further;
      // single stories stay essentially in place (magnitude ≈ 0).
      // Cap at 0.026 world-units (≈ 170 km on Earth) so dense clusters
      // in geographically tight regions (e.g. IN-TN next to Sri Lanka)
      // don't bleed across international borders.
      const magnitude = density > 1 ? 0.010 + Math.min(density - 1, 8) * 0.002 : 0;
      const position  = magnitude > 0 ? applyJitter(basePos, seed, magnitude) : basePos;

      return { story, position, density };
    });
  }, [stories]);

  const selected = storyPositions.find((s) => s.story.dedup_group_id === selectedId);

  return (
    <>
      {storyPositions.map(({ story, position, density }) => (
        <Marker
          key={story.dedup_group_id}
          story={story}
          position={position}
          isSelected={story.dedup_group_id === selectedId}
          regionCount={density}
          dimmed={focusState != null && story.region_code !== focusState}
          renderOrder={story.region_code.includes("-") ? 2 : 1}
          onClick={() =>
            onSelectId(selectedId === story.dedup_group_id ? null : story.dedup_group_id)
          }
        />
      ))}

      {selected && (
        <HudOverlay
          story={selected.story}
          position={selected.position}
          onClose={() => onSelectId(null)}
        />
      )}
    </>
  );
}