import { describe, expect, it } from "vitest";

import { de } from "../src/i18n/de";
import { en } from "../src/i18n/en";

type Json = Record<string, unknown>;

/** Recursively collect dotted leaf key paths from a catalog object. */
function leafKeys(obj: Json, prefix = ""): string[] {
  const keys: string[] = [];
  for (const [key, value] of Object.entries(obj)) {
    const path = prefix ? `${prefix}.${key}` : key;
    if (value !== null && typeof value === "object") {
      keys.push(...leafKeys(value as Json, path));
    } else {
      keys.push(path);
    }
  }
  return keys.sort();
}

function leafValues(obj: Json): string[] {
  const values: string[] = [];
  for (const value of Object.values(obj)) {
    if (value !== null && typeof value === "object") {
      values.push(...leafValues(value as Json));
    } else {
      values.push(value as string);
    }
  }
  return values;
}

describe("catalogs", () => {
  it("define identical key sets", () => {
    expect(leafKeys(de as Json)).toEqual(leafKeys(en as Json));
  });

  it("have only non-empty string leaves", () => {
    for (const value of [...leafValues(en as Json), ...leafValues(de as Json)]) {
      expect(typeof value).toBe("string");
      expect(value.trim().length).toBeGreaterThan(0);
    }
  });

  it("keep the exact prescribed English attribution sentence in both languages", () => {
    const sentence = "This product uses the TMDB API but is not endorsed or certified by TMDB.";
    expect(en.footer.notice).toBe(sentence);
    expect(de.footer.notice).toContain(sentence);
  });
});
