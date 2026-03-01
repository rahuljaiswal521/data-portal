import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { SourceTable } from "@/components/sources/source-table";
import type { SourceSummary } from "@/types";

const makeSrc = (overrides: Partial<SourceSummary> = {}): SourceSummary => ({
  name: "test_source",
  source_type: "jdbc",
  description: "A test source",
  enabled: true,
  tags: {},
  target_table: "dev.bronze.test",
  cdc_mode: "append",
  load_type: "full",
  schedule: null,
  ...overrides,
});

const src1 = makeSrc({ name: "alpha_source", source_type: "jdbc" });
const src2 = makeSrc({ name: "beta_source", source_type: "file" });

describe("SourceTable - loading state", () => {
  it("renders 5 skeleton rows when loading=true", () => {
    const { container } = render(<SourceTable sources={[]} loading={true} />);
    const skeletons = container.querySelectorAll(".animate-pulse");
    expect(skeletons).toHaveLength(5);
  });

  it("does not render a table element when loading", () => {
    const { container } = render(<SourceTable sources={[]} loading={true} />);
    expect(container.querySelector("table")).not.toBeInTheDocument();
  });
});

describe("SourceTable - empty state", () => {
  it("shows empty state text when sources is empty", () => {
    render(<SourceTable sources={[]} loading={false} />);
    expect(screen.getByText("No sources configured")).toBeInTheDocument();
  });

  it("shows Add First Source CTA in empty state", () => {
    render(<SourceTable sources={[]} loading={false} />);
    expect(screen.getByText("Add First Source")).toBeInTheDocument();
  });

  it("does not render table when sources is empty", () => {
    const { container } = render(<SourceTable sources={[]} loading={false} />);
    expect(container.querySelector("table")).not.toBeInTheDocument();
  });
});

describe("SourceTable - with data", () => {
  it("renders source names as links", () => {
    render(<SourceTable sources={[src1, src2]} loading={false} />);
    expect(screen.getByText("alpha_source")).toBeInTheDocument();
    expect(screen.getByText("beta_source")).toBeInTheDocument();
  });

  it("renders a table element with data", () => {
    const { container } = render(<SourceTable sources={[src1, src2]} loading={false} />);
    expect(container.querySelector("table")).toBeInTheDocument();
  });

  it("renders target table in monospace", () => {
    render(<SourceTable sources={[src1]} loading={false} />);
    expect(screen.getByText("dev.bronze.test")).toBeInTheDocument();
  });

  it("renders type badge for each source", () => {
    render(<SourceTable sources={[src1, src2]} loading={false} />);
    expect(screen.getByText("JDBC")).toBeInTheDocument();
    expect(screen.getByText("FILE")).toBeInTheDocument();
  });

  it("shows search input", () => {
    render(<SourceTable sources={[src1, src2]} loading={false} />);
    expect(screen.getByPlaceholderText("Search sources...")).toBeInTheDocument();
  });
});

describe("SourceTable - search filter", () => {
  it("filters rows by name when searching", async () => {
    const user = userEvent.setup();
    render(<SourceTable sources={[src1, src2]} loading={false} />);
    const searchInput = screen.getByPlaceholderText("Search sources...");
    await user.type(searchInput, "alpha");
    expect(screen.getByText("alpha_source")).toBeInTheDocument();
    expect(screen.queryByText("beta_source")).not.toBeInTheDocument();
  });

  it("shows all rows when search is cleared", async () => {
    const user = userEvent.setup();
    render(<SourceTable sources={[src1, src2]} loading={false} />);
    const searchInput = screen.getByPlaceholderText("Search sources...");
    await user.type(searchInput, "alpha");
    await user.clear(searchInput);
    expect(screen.getByText("alpha_source")).toBeInTheDocument();
    expect(screen.getByText("beta_source")).toBeInTheDocument();
  });
});
