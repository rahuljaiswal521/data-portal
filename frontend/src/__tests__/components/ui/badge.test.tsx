import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { Badge } from "@/components/ui/badge";

describe("Badge", () => {
  it("renders children text", () => {
    render(<Badge>Hello</Badge>);
    expect(screen.getByText("Hello")).toBeInTheDocument();
  });

  describe("variants", () => {
    it("default variant renders", () => {
      render(<Badge variant="default">Default</Badge>);
      const badge = screen.getByText("Default");
      expect(badge.className).toMatch(/bg-bg-secondary/);
    });

    it("accent variant renders", () => {
      render(<Badge variant="accent">Accent</Badge>);
      const badge = screen.getByText("Accent");
      expect(badge.className).toMatch(/bg-accent-light/);
    });

    it("success variant renders", () => {
      render(<Badge variant="success">Success</Badge>);
      const badge = screen.getByText("Success");
      expect(badge.className).toMatch(/text-success/);
    });

    it("warning variant renders", () => {
      render(<Badge variant="warning">Warning</Badge>);
      const badge = screen.getByText("Warning");
      expect(badge.className).toMatch(/text-warning/);
    });

    it("error variant renders", () => {
      render(<Badge variant="error">Error</Badge>);
      const badge = screen.getByText("Error");
      expect(badge.className).toMatch(/text-error/);
    });

    it("info variant renders", () => {
      render(<Badge variant="info">Info</Badge>);
      const badge = screen.getByText("Info");
      expect(badge.className).toMatch(/text-info/);
    });
  });

  it("uses default variant when no variant prop given", () => {
    render(<Badge>No variant</Badge>);
    const badge = screen.getByText("No variant");
    expect(badge.className).toMatch(/bg-bg-secondary/);
  });

  it("accepts extra className", () => {
    render(<Badge className="my-extra">Extra</Badge>);
    expect(screen.getByText("Extra").className).toMatch(/my-extra/);
  });

  it("renders as a span element", () => {
    render(<Badge>Span</Badge>);
    expect(screen.getByText("Span").tagName).toBe("SPAN");
  });
});
