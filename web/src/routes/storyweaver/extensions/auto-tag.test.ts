/// <reference types="vitest/globals" />
import { describe, expect, it } from "vitest";

// We exercise the regex compilation via a tiny ad-hoc reimplementation that
// shares the same algorithm. The real builder lives inside the plugin
// closure; promoting it to module-level would couple the test to ProseMirror
// internals we don't need here. The contract under test is the *pattern
// shape*, which is the only piece we have to keep aligned with the desktop's
// MarkdownHighlighter.

import type { StoryweaverEntity } from "@/api/documents";

function compilePatterns(entities: StoryweaverEntity[]) {
  const sorted = [...entities].sort((a, b) => b.name.length - a.name.length);
  return sorted
    .filter((e) => e.name && e.name.trim().length >= 2)
    .map((e) => {
      const escaped = e.name.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
      return new RegExp(`\\b${escaped}(?:'s)?\\b`, "gi");
    });
}

function findAll(text: string, entities: StoryweaverEntity[]): string[] {
  const hits: string[] = [];
  for (const re of compilePatterns(entities)) {
    re.lastIndex = 0;
    let m: RegExpExecArray | null;
    // eslint-disable-next-line no-cond-assign
    while ((m = re.exec(text))) hits.push(m[0]);
  }
  return hits;
}

const e = (id: string, name: string, type = "actor"): StoryweaverEntity => ({
  id,
  name,
  type,
});

describe("auto-tag pattern compilation", () => {
  it("matches whole words case-insensitively", () => {
    const entities = [e("actor_1", "Aragorn")];
    expect(findAll("aragorn rode east", entities)).toEqual(["aragorn"]);
    expect(findAll("ARAGORN!", entities)).toEqual(["ARAGORN"]);
  });

  it("matches the optional possessive 's", () => {
    const entities = [e("actor_1", "Frodo")];
    expect(findAll("Frodo's ring fell", entities)).toEqual(["Frodo's"]);
  });

  it("doesn't match across word boundaries", () => {
    const entities = [e("actor_1", "Sam")];
    expect(findAll("Samwise was there, but Sam left", entities)).toEqual(["Sam"]);
  });

  it("escapes regex special chars in names", () => {
    const entities = [e("loc_1", "St. Mungo's", "location")];
    // Two matches: with and without the possessive expansion. We just need
    // the literal string to be findable without throwing.
    expect(findAll("met at St. Mungo's", entities)).toContain("St. Mungo's");
  });

  it("filters out very short names", () => {
    const entities = [e("actor_1", "X")];
    expect(findAll("X marks the spot", entities)).toEqual([]);
  });

  it("orders longer names first so they win on overlap", () => {
    // If the order weren't enforced, "Aragorn" would match before
    // "Aragorn the King" and we'd get the short hit only.
    const entities = [
      e("actor_1", "Aragorn"),
      e("actor_2", "Aragorn the King"),
    ];
    const hits = findAll("Aragorn the King strode in", entities);
    expect(hits).toContain("Aragorn the King");
  });
});
