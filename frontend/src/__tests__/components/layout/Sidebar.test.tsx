import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { Sidebar } from "@/components/layout/sidebar";

// Override the next/navigation mock for this file so we can control
// usePathname per-test via mockReturnValue.
const mockUsePathname = vi.fn(() => "/bronze");

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn(), replace: vi.fn(), back: vi.fn() }),
  usePathname: () => mockUsePathname(),
  useParams: () => ({}),
  redirect: vi.fn(),
}));

describe("Sidebar — Testing section", () => {
  it("renders the Testing section heading", () => {
    render(<Sidebar />);
    expect(screen.getByText("Testing")).toBeInTheDocument();
  });

  it("renders a Bronze Tests link", () => {
    render(<Sidebar />);
    expect(screen.getByText("Bronze Tests")).toBeInTheDocument();
  });

  it("Bronze Tests link points to /testing/bronze", () => {
    render(<Sidebar />);
    const link = screen.getByText("Bronze Tests").closest("a");
    expect(link).not.toBeNull();
    expect(link!.getAttribute("href")).toBe("/testing/bronze");
  });

  it("renders Silver Tests label", () => {
    render(<Sidebar />);
    expect(screen.getByText("Silver Tests")).toBeInTheDocument();
  });

  it("Silver Tests has cursor-not-allowed styling (disabled)", () => {
    render(<Sidebar />);
    const el = screen.getByText("Silver Tests").closest("div");
    expect(el).not.toBeNull();
    expect(el!.className).toMatch(/cursor-not-allowed/);
  });

  it("Silver Tests is not a navigable link", () => {
    render(<Sidebar />);
    const el = screen.getByText("Silver Tests").closest("a");
    expect(el).toBeNull();
  });

  it("renders a 'soon' badge next to Silver Tests", () => {
    render(<Sidebar />);
    const silverItem = screen.getByText("Silver Tests").closest("div");
    expect(silverItem).not.toBeNull();
    expect(silverItem!.textContent).toMatch(/soon/i);
  });

  it("Bronze Tests link is active when pathname is /testing/bronze", () => {
    mockUsePathname.mockReturnValue("/testing/bronze");
    render(<Sidebar />);
    const link = screen.getByText("Bronze Tests").closest("a");
    expect(link).not.toBeNull();
    expect(link!.className).toMatch(/bg-accent-light/);
  });

  it("Bronze Tests link is inactive when pathname is /bronze", () => {
    // default mock returns "/bronze"
    mockUsePathname.mockReturnValue("/bronze");
    render(<Sidebar />);
    const link = screen.getByText("Bronze Tests").closest("a");
    expect(link).not.toBeNull();
    expect(link!.className).not.toMatch(/bg-accent-light/);
  });

  it("Bronze Tests link is active when pathname is a sub-path of /testing/bronze", () => {
    mockUsePathname.mockReturnValue("/testing/bronze/some-suite");
    render(<Sidebar />);
    const link = screen.getByText("Bronze Tests").closest("a");
    expect(link).not.toBeNull();
    expect(link!.className).toMatch(/bg-accent-light/);
  });
});

describe("Sidebar — logo", () => {
  it("renders the Ecran logo image", () => {
    render(<Sidebar />);
    const img = screen.getByAltText("Ecran");
    expect(img).toBeInTheDocument();
  });

  it("Ecran logo src points to /ecran-logo.png", () => {
    render(<Sidebar />);
    const img = screen.getByAltText("Ecran");
    expect(img.getAttribute("src")).toMatch(/ecran-logo\.png/);
  });

  it("does not render 'Data Portal' text (logo carries branding)", () => {
    render(<Sidebar />);
    expect(screen.queryByText("Data Portal")).toBeNull();
  });

  it("does not render 'Lakehouse Platform' text (logo carries branding)", () => {
    render(<Sidebar />);
    expect(screen.queryByText("Lakehouse Platform")).toBeNull();
  });
});

describe("Sidebar — existing sections still render", () => {
  it("renders Bronze Layer section heading", () => {
    render(<Sidebar />);
    expect(screen.getByText("Bronze Layer")).toBeInTheDocument();
  });

  it("renders Silver Layer section heading", () => {
    render(<Sidebar />);
    expect(screen.getByText("Silver Layer")).toBeInTheDocument();
  });

  it("renders Coming Soon section with Gold Layer", () => {
    render(<Sidebar />);
    expect(screen.getByText("Coming Soon")).toBeInTheDocument();
    expect(screen.getByText("Gold Layer")).toBeInTheDocument();
  });

  it("renders Platform section with AI Assistant", () => {
    render(<Sidebar />);
    expect(screen.getByText("AI Assistant")).toBeInTheDocument();
  });
});
