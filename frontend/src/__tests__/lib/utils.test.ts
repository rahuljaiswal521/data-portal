import { describe, it, expect } from "vitest";
import { cn } from "@/lib/utils";

describe("cn()", () => {
  it("returns empty string when no args", () => {
    expect(cn()).toBe("");
  });

  it("merges multiple class strings", () => {
    expect(cn("foo", "bar")).toBe("foo bar");
  });

  it("ignores falsy values", () => {
    expect(cn("foo", false, undefined, null, "bar")).toBe("foo bar");
  });

  it("resolves Tailwind conflicts (last wins)", () => {
    // tailwind-merge resolves padding conflicts
    const result = cn("px-2", "px-4");
    expect(result).toBe("px-4");
  });

  it("resolves mixed Tailwind conflicts", () => {
    const result = cn("text-red-500", "text-blue-500");
    expect(result).toBe("text-blue-500");
  });

  it("accepts arrays", () => {
    expect(cn(["foo", "bar"])).toBe("foo bar");
  });

  it("accepts conditional objects", () => {
    expect(cn({ foo: true, bar: false, baz: true })).toBe("foo baz");
  });

  it("does not duplicate classes that do not conflict", () => {
    const result = cn("flex items-center", "gap-2");
    expect(result).toBe("flex items-center gap-2");
  });
});
