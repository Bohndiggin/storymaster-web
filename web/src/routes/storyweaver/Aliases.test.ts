/// <reference types="vitest/globals" />
import { describe, expect, it } from "vitest";

import {
  expandEntitiesWithAliases,
  parseEntityMap,
  serializeEntityMap,
} from "./Aliases";

describe("entity_map_json (de)serialization", () => {
  it("round-trips a populated map", () => {
    const raw = '{"actor_42":["Strider","Ranger"],"location_7":["The Inn"]}';
    const parsed = parseEntityMap(raw);
    expect(parsed).toEqual({
      actor_42: ["Strider", "Ranger"],
      location_7: ["The Inn"],
    });
    // Stable key ordering — locations come before actors alphabetically.
    expect(serializeEntityMap(parsed)).toBe(
      '{"actor_42":["Strider","Ranger"],"location_7":["The Inn"]}',
    );
  });

  it("returns {} for empty / malformed input", () => {
    expect(parseEntityMap(null)).toEqual({});
    expect(parseEntityMap("")).toEqual({});
    expect(parseEntityMap("not json")).toEqual({});
    expect(parseEntityMap("[1,2]")).toEqual({});
    expect(parseEntityMap('{"actor_1": "not-a-list"}')).toEqual({});
  });

  it("filters non-string alias entries", () => {
    expect(parseEntityMap('{"a_1":["ok",123,null,"also"]}')).toEqual({
      a_1: ["ok", "also"],
    });
  });

  it("drops empty alias arrays on serialize", () => {
    expect(serializeEntityMap({ actor_1: [], location_2: ["X"] })).toBe(
      '{"location_2":["X"]}',
    );
  });
});

describe("expandEntitiesWithAliases", () => {
  const aragorn = { id: "actor_42", name: "Aragorn", type: "actor" };
  const inn = { id: "location_7", name: "Prancing Pony", type: "location" };

  it("appends one virtual entity per alias, copying type/id", () => {
    const out = expandEntitiesWithAliases(
      [aragorn, inn],
      { actor_42: ["Strider", "Ranger"] },
    );
    expect(out).toHaveLength(4);
    const aliases = out.filter((e) => e.id === "actor_42" && e.name !== "Aragorn");
    expect(aliases.map((a) => a.name).sort()).toEqual(["Ranger", "Strider"]);
    // All variants point at the same target id/type.
    expect(aliases.every((a) => a.type === "actor" && a.id === "actor_42")).toBe(true);
  });

  it("returns the input unchanged when no aliases", () => {
    expect(expandEntitiesWithAliases([aragorn], {})).toEqual([aragorn]);
  });

  it("ignores aliases that point at a deleted entity", () => {
    // entity_1000 doesn't exist in the canonical list; alias should drop.
    const out = expandEntitiesWithAliases(
      [aragorn],
      { entity_1000: ["ghost"] },
    );
    expect(out).toEqual([aragorn]);
  });
});
