import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import BronzeTestingPage from "@/app/testing/bronze/page";

// Return an empty, fully-loaded state so the page renders real content
// (no skeleton placeholders) and shows the empty state.
vi.mock("swr", () => ({
  default: vi.fn(() => ({ data: { suites: [] }, isLoading: false, error: null })),
}));

describe("BronzeTestingPage — header row", () => {
  it("renders the page heading 'Test Suite'", () => {
    render(<BronzeTestingPage />);
    expect(screen.getByRole("heading", { name: /test suite/i, level: 1 })).toBeInTheDocument();
  });

  it("renders a 'Run All' button", () => {
    render(<BronzeTestingPage />);
    expect(screen.getByRole("button", { name: /run all/i })).toBeInTheDocument();
  });

  it("'Run All' button is disabled when no suites exist", () => {
    render(<BronzeTestingPage />);
    expect(screen.getByRole("button", { name: /run all/i })).toBeDisabled();
  });
});

describe("BronzeTestingPage — layer tab strip", () => {
  it("renders Bronze tab", () => {
    render(<BronzeTestingPage />);
    expect(screen.getByText("Bronze")).toBeInTheDocument();
  });

  it("Bronze tab is rendered as a link (active, navigable)", () => {
    render(<BronzeTestingPage />);
    // The active tab is a Link, which the mock renders as <a>
    const bronzeEl = screen.getByText("Bronze");
    expect(bronzeEl.tagName).toBe("A");
  });

  it("Bronze tab link points to /testing/bronze", () => {
    render(<BronzeTestingPage />);
    const bronzeLink = screen.getByText("Bronze").closest("a");
    expect(bronzeLink).not.toBeNull();
    expect(bronzeLink!.getAttribute("href")).toBe("/testing/bronze");
  });

  it("Bronze tab has active (accent border) styling", () => {
    render(<BronzeTestingPage />);
    const bronzeLink = screen.getByText("Bronze").closest("a");
    expect(bronzeLink).not.toBeNull();
    expect(bronzeLink!.className).toMatch(/border-accent/);
  });

  it("renders Silver tab", () => {
    render(<BronzeTestingPage />);
    expect(screen.getByText("Silver")).toBeInTheDocument();
  });

  it("Silver tab is not a link (disabled)", () => {
    render(<BronzeTestingPage />);
    // disabled tab renders as <span>, not <a>
    const silverEl = screen.getByText("Silver");
    expect(silverEl.tagName).toBe("SPAN");
  });

  it("Silver tab has cursor-not-allowed styling", () => {
    render(<BronzeTestingPage />);
    const silverEl = screen.getByText("Silver");
    expect(silverEl.className).toMatch(/cursor-not-allowed/);
  });

  it("Silver tab shows 'coming soon' label", () => {
    render(<BronzeTestingPage />);
    const silverEl = screen.getByText("Silver").closest("span");
    expect(silverEl).not.toBeNull();
    expect(silverEl!.textContent).toMatch(/coming soon/i);
  });
});

describe("BronzeTestingPage — stats cards", () => {
  it("renders 'Total Suites' label", () => {
    render(<BronzeTestingPage />);
    expect(screen.getByText("Total Suites")).toBeInTheDocument();
  });

  it("renders 'Passing' label", () => {
    render(<BronzeTestingPage />);
    expect(screen.getByText("Passing")).toBeInTheDocument();
  });

  it("renders 'Failing' label", () => {
    render(<BronzeTestingPage />);
    expect(screen.getByText("Failing")).toBeInTheDocument();
  });

  it("renders 'Not Run' label", () => {
    render(<BronzeTestingPage />);
    expect(screen.getByText("Not Run")).toBeInTheDocument();
  });

  it("all four stat values show 0", () => {
    render(<BronzeTestingPage />);
    const zeros = screen.getAllByText("0");
    expect(zeros).toHaveLength(4);
  });
});

describe("BronzeTestingPage — empty state", () => {
  it("renders empty state heading", () => {
    render(<BronzeTestingPage />);
    expect(screen.getByText("No test suites configured yet")).toBeInTheDocument();
  });

  it("renders helper description text", () => {
    render(<BronzeTestingPage />);
    expect(
      screen.getByText(/test suites are auto-generated/i)
    ).toBeInTheDocument();
  });

  it("renders an SVG icon inside the empty state icon wrapper", () => {
    const { container } = render(<BronzeTestingPage />);
    // The icon wrapper has rounded-full class — find it and confirm an SVG is inside
    const iconWrapper = container.querySelector(".rounded-full");
    expect(iconWrapper).not.toBeNull();
    const svg = iconWrapper!.querySelector("svg");
    expect(svg).not.toBeNull();
  });

  it("renders the subtitle about validation and data quality", () => {
    render(<BronzeTestingPage />);
    expect(
      screen.getByText(/row counts|schema checks|data quality/i)
    ).toBeInTheDocument();
  });
});
