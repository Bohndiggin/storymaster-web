/**
 * Lorekeeper categories — the top-level navigation buckets.
 *
 * Mirrors the desktop's `MAIN_CATEGORIES` from
 * `storymaster.model.lorekeeper.entity_mappings.MAIN_CATEGORIES`, with each
 * category's submenu filtered to tables exposed under
 * `/api/v1/settings/{id}/entities/{table}` (i.e. tables in
 * `LOREKEEPER_TABLES` on the backend). Tables that exist in the schema but
 * aren't broadly user-facing (alignment, stat, sub_race) only show up as
 * submenu items, not top-level categories.
 *
 * `litography_notes` is intentionally omitted: it lives on a different router
 * and is storyline-scoped, not setting-scoped, so it doesn't fit this nav.
 */

export interface LorekeeperSubmenuItem {
  table: string;
  label: string;
}

export interface LorekeeperCategory {
  table: string;
  label: string; // plural form used as the nav label
  icon: string;
  submenu?: LorekeeperSubmenuItem[];
}

export const LOREKEEPER_CATEGORIES: LorekeeperCategory[] = [
  {
    table: "actor",
    label: "Characters",
    icon: "👤",
    submenu: [
      { table: "actor_a_on_b_relations", label: "Relationships" },
      { table: "actor_to_skills", label: "Skills & Abilities" },
      { table: "actor_to_race", label: "Heritage" },
      { table: "actor_to_class", label: "Classes & Professions" },
      { table: "actor_to_stat", label: "Statistics" },
      { table: "alignment", label: "Alignments" },
      { table: "object_to_owner", label: "Possessions" },
    ],
  },
  {
    table: "faction",
    label: "Organizations",
    icon: "🏛️",
    submenu: [
      { table: "faction_members", label: "Members" },
      { table: "faction_a_on_b_relations", label: "Relations" },
      { table: "location_to_faction", label: "Territories" },
    ],
  },
  {
    table: "location_",
    label: "Places",
    icon: "🗺️",
    submenu: [
      { table: "residents", label: "Residents" },
      { table: "location_a_on_b_relations", label: "Relations" },
      { table: "location_geographic_relations", label: "Geographic" },
      { table: "location_political_relations", label: "Political" },
      { table: "location_economic_relations", label: "Economic" },
      { table: "location_hierarchy", label: "Hierarchy" },
      { table: "location_dungeon", label: "Dungeons" },
      { table: "location_city", label: "Cities" },
      { table: "location_city_districts", label: "Districts" },
      { table: "location_flora_fauna", label: "Flora & Fauna" },
    ],
  },
  {
    table: "object_",
    label: "Items",
    icon: "⚔️",
    submenu: [{ table: "object_to_owner", label: "Owners" }],
  },
  {
    table: "history",
    label: "Events",
    icon: "📜",
    submenu: [
      { table: "history_actor", label: "Characters Involved" },
      { table: "history_location", label: "Places Involved" },
      { table: "history_faction", label: "Organizations Involved" },
      { table: "history_object", label: "Items Involved" },
      { table: "history_world_data", label: "Lore Elements" },
    ],
  },
  {
    table: "world_data",
    label: "Lore",
    icon: "📚",
    submenu: [{ table: "history_world_data", label: "Related Events" }],
  },
  { table: "background", label: "Backgrounds", icon: "🎭" },
  {
    table: "race",
    label: "Heritage Types",
    icon: "🧬",
    submenu: [{ table: "sub_race", label: "Sub-types" }],
  },
  { table: "class", label: "Professions", icon: "⚔️" },
  { table: "skills", label: "Skills", icon: "🎯" },
];

/**
 * Reverse lookup: given any table name (top-level or submenu), find which
 * category it belongs to. Used to keep the right submenu expanded when the
 * user navigates straight to a sub-table by URL.
 */
export function findCategoryForTable(
  table: string,
): { category: LorekeeperCategory; isSubmenu: boolean } | null {
  for (const category of LOREKEEPER_CATEGORIES) {
    if (category.table === table) return { category, isSubmenu: false };
    if (category.submenu?.some((s) => s.table === table)) {
      return { category, isSubmenu: true };
    }
  }
  return null;
}
