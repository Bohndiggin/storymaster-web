import type { EntityRow } from "@/api/types";

/** Display name for an actor row, mirroring `BaseModel._actor_full_name`. */
export function actorDisplayName(actor: EntityRow): string {
  const get = (k: string) =>
    typeof actor[k] === "string" ? (actor[k] as string).trim() : "";
  const composed = [get("first_name"), get("middle_name"), get("last_name")]
    .filter(Boolean)
    .join(" ");
  if (composed) return composed;
  const title = get("title");
  if (title) return title;
  return `Actor #${actor.id}`;
}
