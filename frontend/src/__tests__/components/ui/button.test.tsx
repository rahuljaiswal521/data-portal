import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Button } from "@/components/ui/button";

describe("Button", () => {
  it("renders its children", () => {
    render(<Button>Click me</Button>);
    expect(screen.getByRole("button", { name: "Click me" })).toBeInTheDocument();
  });

  describe("variants", () => {
    it("primary variant renders", () => {
      render(<Button variant="primary">Primary</Button>);
      const btn = screen.getByRole("button");
      expect(btn.className).toMatch(/bg-bg-dark/);
    });

    it("secondary variant renders", () => {
      render(<Button variant="secondary">Secondary</Button>);
      const btn = screen.getByRole("button");
      expect(btn.className).toMatch(/bg-bg-card/);
    });

    it("ghost variant renders", () => {
      render(<Button variant="ghost">Ghost</Button>);
      const btn = screen.getByRole("button");
      expect(btn.className).toMatch(/text-text-secondary/);
    });

    it("danger variant renders", () => {
      render(<Button variant="danger">Danger</Button>);
      const btn = screen.getByRole("button");
      expect(btn.className).toMatch(/bg-error/);
    });
  });

  describe("sizes", () => {
    it("sm size renders", () => {
      render(<Button size="sm">Small</Button>);
      const btn = screen.getByRole("button");
      expect(btn.className).toMatch(/px-3/);
    });

    it("md size renders (default)", () => {
      render(<Button size="md">Medium</Button>);
      const btn = screen.getByRole("button");
      expect(btn.className).toMatch(/px-4/);
    });

    it("lg size renders", () => {
      render(<Button size="lg">Large</Button>);
      const btn = screen.getByRole("button");
      expect(btn.className).toMatch(/px-6/);
    });
  });

  describe("disabled state", () => {
    it("is disabled when disabled prop is true", () => {
      render(<Button disabled>Disabled</Button>);
      expect(screen.getByRole("button")).toBeDisabled();
    });

    it("applies opacity class when disabled", () => {
      render(<Button disabled>Disabled</Button>);
      expect(screen.getByRole("button").className).toMatch(/disabled:opacity-50/);
    });
  });

  it("forwards onClick handler", async () => {
    const user = userEvent.setup();
    const onClick = vi.fn();
    render(<Button onClick={onClick}>Click</Button>);
    await user.click(screen.getByRole("button"));
    expect(onClick).toHaveBeenCalledTimes(1);
  });

  it("does not fire onClick when disabled", async () => {
    const user = userEvent.setup();
    const onClick = vi.fn();
    render(<Button disabled onClick={onClick}>Click</Button>);
    await user.click(screen.getByRole("button"));
    expect(onClick).not.toHaveBeenCalled();
  });

  it("accepts extra className", () => {
    render(<Button className="my-custom-class">Styled</Button>);
    expect(screen.getByRole("button").className).toMatch(/my-custom-class/);
  });

  it("has default variant primary when no variant given", () => {
    render(<Button>Default</Button>);
    const btn = screen.getByRole("button");
    expect(btn.className).toMatch(/bg-bg-dark/);
  });
});
