/**
 * Inline-relationship config for entity edit pages.
 *
 * For each top-level entity (actor, faction, location_, object_, history,
 * world_data) we describe which junction tables to render as sections under
 * its edit form. The component reads these to render a list of linked rows
 * with add/remove + a couple of inline-editable extra columns.
 *
 * Anything in this map is hidden from the Lorekeeper sidebar submenu — the
 * point of inline relationships is to *replace* the standalone junction
 * pages.
 */

export interface RelationshipExtra {
  column: string;
  label: string;
  inputType: "text" | "number";
}

export interface InlineRelationship {
  /** Display name for the section header */
  title: string;
  /** Junction table on the server, e.g. "actor_to_skills" */
  junctionTable: string;
  /** FK column on the junction that points at the parent (e.g. "actor_id") */
  parentFk: string;
  /** Target entity table (e.g. "skills") */
  targetTable: string;
  /** FK column on the junction that points at the target (e.g. "skill_id") */
  targetFk: string;
  /** Optional inline-editable columns shown next to each row */
  extras?: RelationshipExtra[];
}

export const ENTITY_RELATIONSHIPS: Record<string, InlineRelationship[]> = {
  actor: [
    {
      title: "Heritage",
      junctionTable: "actor_to_race",
      parentFk: "actor_id",
      targetTable: "race",
      targetFk: "race_id",
    },
    {
      title: "Classes & Professions",
      junctionTable: "actor_to_class",
      parentFk: "actor_id",
      targetTable: "class",
      targetFk: "class_id",
      extras: [{ column: "current_level", label: "Level", inputType: "number" }],
    },
    {
      title: "Statistics",
      junctionTable: "actor_to_stat",
      parentFk: "actor_id",
      targetTable: "stat",
      targetFk: "stat_id",
      extras: [{ column: "base_value", label: "Score", inputType: "number" }],
    },
    {
      title: "Skills & Abilities",
      junctionTable: "actor_to_skills",
      parentFk: "actor_id",
      targetTable: "skills",
      targetFk: "skill_id",
      extras: [
        { column: "proficiency_level", label: "Prof.", inputType: "number" },
      ],
    },
    {
      title: "Organization Memberships",
      junctionTable: "faction_members",
      parentFk: "actor_id",
      targetTable: "faction",
      targetFk: "faction_id",
      extras: [{ column: "role", label: "Role", inputType: "text" }],
    },
    {
      title: "Places They Live",
      junctionTable: "residents",
      parentFk: "actor_id",
      targetTable: "location_",
      targetFk: "location_id",
      extras: [
        { column: "residency_type", label: "Type", inputType: "text" },
      ],
    },
    {
      title: "Possessions",
      junctionTable: "object_to_owner",
      parentFk: "actor_id",
      targetTable: "object_",
      targetFk: "object_id",
    },
    {
      title: "Historical Events",
      junctionTable: "history_actor",
      parentFk: "actor_id",
      targetTable: "history",
      targetFk: "history_id",
      extras: [
        { column: "role_in_event", label: "Role", inputType: "text" },
      ],
    },
  ],
  faction: [
    {
      title: "Members",
      junctionTable: "faction_members",
      parentFk: "faction_id",
      targetTable: "actor",
      targetFk: "actor_id",
      extras: [{ column: "role", label: "Role", inputType: "text" }],
    },
    {
      title: "Territories & Influence",
      junctionTable: "location_to_faction",
      parentFk: "faction_id",
      targetTable: "location_",
      targetFk: "location_id",
    },
    {
      title: "Historical Events",
      junctionTable: "history_faction",
      parentFk: "faction_id",
      targetTable: "history",
      targetFk: "history_id",
    },
  ],
  location_: [
    {
      title: "Residents",
      junctionTable: "residents",
      parentFk: "location_id",
      targetTable: "actor",
      targetFk: "actor_id",
    },
    {
      title: "Controlling Organizations",
      junctionTable: "location_to_faction",
      parentFk: "location_id",
      targetTable: "faction",
      targetFk: "faction_id",
    },
    {
      title: "Geographic Connections",
      junctionTable: "location_geographic_relations",
      parentFk: "location_a_id",
      targetTable: "location_",
      targetFk: "location_b_id",
      extras: [
        { column: "geographic_type", label: "Type", inputType: "text" },
        { column: "distance", label: "Distance", inputType: "text" },
      ],
    },
    {
      title: "Political Relations",
      junctionTable: "location_political_relations",
      parentFk: "location_a_id",
      targetTable: "location_",
      targetFk: "location_b_id",
      extras: [
        { column: "political_type", label: "Type", inputType: "text" },
      ],
    },
    {
      title: "Economic Relations",
      junctionTable: "location_economic_relations",
      parentFk: "location_a_id",
      targetTable: "location_",
      targetFk: "location_b_id",
      extras: [
        { column: "economic_type", label: "Type", inputType: "text" },
      ],
    },
    {
      title: "General Relations",
      junctionTable: "location_a_on_b_relations",
      parentFk: "location_a_id",
      targetTable: "location_",
      targetFk: "location_b_id",
    },
    {
      title: "Hierarchy (Child Locations)",
      junctionTable: "location_hierarchy",
      parentFk: "parent_location_id",
      targetTable: "location_",
      targetFk: "child_location_id",
    },
    {
      title: "Historical Events",
      junctionTable: "history_location",
      parentFk: "location_id",
      targetTable: "history",
      targetFk: "history_id",
    },
  ],
  object_: [
    {
      title: "Owners",
      junctionTable: "object_to_owner",
      parentFk: "object_id",
      targetTable: "actor",
      targetFk: "actor_id",
    },
    {
      title: "Historical Events",
      junctionTable: "history_object",
      parentFk: "object_id",
      targetTable: "history",
      targetFk: "history_id",
    },
  ],
  history: [
    {
      title: "Characters Involved",
      junctionTable: "history_actor",
      parentFk: "history_id",
      targetTable: "actor",
      targetFk: "actor_id",
      extras: [{ column: "role_in_event", label: "Role", inputType: "text" }],
    },
    {
      title: "Places Involved",
      junctionTable: "history_location",
      parentFk: "history_id",
      targetTable: "location_",
      targetFk: "location_id",
    },
    {
      title: "Organizations Involved",
      junctionTable: "history_faction",
      parentFk: "history_id",
      targetTable: "faction",
      targetFk: "faction_id",
    },
    {
      title: "Items Involved",
      junctionTable: "history_object",
      parentFk: "history_id",
      targetTable: "object_",
      targetFk: "object_id",
    },
    {
      title: "Lore Elements",
      junctionTable: "history_world_data",
      parentFk: "history_id",
      targetTable: "world_data",
      targetFk: "world_data_id",
    },
  ],
  world_data: [
    {
      title: "Related Events",
      junctionTable: "history_world_data",
      parentFk: "world_data_id",
      targetTable: "history",
      targetFk: "history_id",
    },
  ],
};

/**
 * Every junction table referenced by ENTITY_RELATIONSHIPS — used to hide them
 * from the sidebar so they aren't reachable twice.
 */
export const INLINE_JUNCTION_TABLES: ReadonlySet<string> = new Set(
  Object.values(ENTITY_RELATIONSHIPS).flatMap((rels) =>
    rels.map((r) => r.junctionTable),
  ),
);

export function relationshipsFor(table: string): InlineRelationship[] {
  return ENTITY_RELATIONSHIPS[table] ?? [];
}
