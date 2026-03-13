import { useMemo } from "react";
import type { StoryOut } from "../../services/api";
import { regionToVector3 } from "./utils/geoUtils";
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
}

export function NewsBlips({ stories, selectedId, onSelectId }: NewsBlipsProps) {
  const regionCounts = useMemo(() => {
    const counts: Record<string, number> = {};
    for (const story of stories) {
      counts[story.region_code] = (counts[story.region_code] ?? 0) + 1;
    }
    return counts;
  }, [stories]);

  const storyPositions = useMemo(
    () =>
      stories.map((story) => ({
        story,
        position: regionToVector3(story.region_code, MARKER_RADIUS),
      })),
    [stories]
  );

  const selected = storyPositions.find((s) => s.story.dedup_group_id === selectedId);

  return (
    <>
      {storyPositions.map(({ story, position }) => (
        <Marker
          key={story.dedup_group_id}
          story={story}
          position={position}
          isSelected={story.dedup_group_id === selectedId}
          regionCount={regionCounts[story.region_code] ?? 1}
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
