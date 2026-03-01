import { describe, it, expect } from "vitest";
import {
  SOURCE_TYPES,
  CDC_MODES,
  LOAD_TYPES,
  FILE_FORMATS,
  SCHEMA_EVOLUTION_MODES,
  AUTH_TYPES,
  PAGINATION_TYPES,
  METADATA_EXPRESSIONS,
  API_BASE_URL,
} from "@/lib/constants";

describe("SOURCE_TYPES", () => {
  it("has 4 entries", () => {
    expect(SOURCE_TYPES).toHaveLength(4);
  });

  it("includes jdbc, file, api, stream values", () => {
    const values = SOURCE_TYPES.map((t) => t.value);
    expect(values).toContain("jdbc");
    expect(values).toContain("file");
    expect(values).toContain("api");
    expect(values).toContain("stream");
  });

  it("every entry has value, label, description", () => {
    for (const t of SOURCE_TYPES) {
      expect(t).toHaveProperty("value");
      expect(t).toHaveProperty("label");
      expect(t).toHaveProperty("description");
    }
  });
});

describe("CDC_MODES", () => {
  it("has 3 entries", () => {
    expect(CDC_MODES).toHaveLength(3);
  });

  it("includes append, upsert, scd2", () => {
    const values = CDC_MODES.map((m) => m.value);
    expect(values).toContain("append");
    expect(values).toContain("upsert");
    expect(values).toContain("scd2");
  });
});

describe("LOAD_TYPES", () => {
  it("has 2 entries", () => {
    expect(LOAD_TYPES).toHaveLength(2);
  });

  it("includes full and incremental", () => {
    const values = LOAD_TYPES.map((l) => l.value);
    expect(values).toContain("full");
    expect(values).toContain("incremental");
  });
});

describe("FILE_FORMATS", () => {
  it("has 6 formats", () => {
    expect(FILE_FORMATS).toHaveLength(6);
  });

  it("includes parquet, json, csv", () => {
    expect(FILE_FORMATS).toContain("parquet");
    expect(FILE_FORMATS).toContain("json");
    expect(FILE_FORMATS).toContain("csv");
  });
});

describe("SCHEMA_EVOLUTION_MODES", () => {
  it("has merge, strict, rescue", () => {
    const values = SCHEMA_EVOLUTION_MODES.map((m) => m.value);
    expect(values).toContain("merge");
    expect(values).toContain("strict");
    expect(values).toContain("rescue");
  });
});

describe("AUTH_TYPES", () => {
  it("includes none and oauth2", () => {
    const values = AUTH_TYPES.map((a) => a.value);
    expect(values).toContain("none");
    expect(values).toContain("oauth2");
  });
});

describe("PAGINATION_TYPES", () => {
  it("has offset, cursor, link_header", () => {
    const values = PAGINATION_TYPES.map((p) => p.value);
    expect(values).toContain("offset");
    expect(values).toContain("cursor");
    expect(values).toContain("link_header");
  });
});

describe("METADATA_EXPRESSIONS", () => {
  it("includes current_timestamp() expression", () => {
    const values = METADATA_EXPRESSIONS.map((e) => e.value);
    expect(values).toContain("current_timestamp()");
  });
});

describe("API_BASE_URL", () => {
  it("has a fallback default", () => {
    expect(typeof API_BASE_URL).toBe("string");
    expect(API_BASE_URL.length).toBeGreaterThan(0);
  });
});
