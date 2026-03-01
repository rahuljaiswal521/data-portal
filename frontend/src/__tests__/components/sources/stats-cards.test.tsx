import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { StatsCards } from "@/components/sources/stats-cards";
import type { DashboardStats } from "@/types";

const mockStats: DashboardStats = {
  total_sources: 5,
  enabled_sources: 3,
  disabled_sources: 2,
  recent_failures: 1,
  sources_by_type: {},
  recent_runs: 4,
};

describe("StatsCards", () => {
  it("shows 4 skeleton elements when loading", () => {
    const { container } = render(<StatsCards loading={true} />);
    // Each card renders a Skeleton div when loading
    // Skeletons have animate-pulse class
    const skeletons = container.querySelectorAll(".animate-pulse");
    expect(skeletons.length).toBeGreaterThanOrEqual(4);
  });

  it("shows stat values when stats provided and not loading", () => {
    render(<StatsCards stats={mockStats} loading={false} />);
    expect(screen.getByText("5")).toBeInTheDocument();
    expect(screen.getByText("3")).toBeInTheDocument();
    expect(screen.getByText("2")).toBeInTheDocument();
    expect(screen.getByText("1")).toBeInTheDocument();
  });

  it("shows 0 for each card when stats is undefined", () => {
    render(<StatsCards stats={undefined} loading={false} />);
    const zeros = screen.getAllByText("0");
    expect(zeros).toHaveLength(4);
  });

  it("renders card labels", () => {
    render(<StatsCards stats={mockStats} loading={false} />);
    expect(screen.getByText("Total Sources")).toBeInTheDocument();
    expect(screen.getByText("Enabled")).toBeInTheDocument();
    expect(screen.getByText("Disabled")).toBeInTheDocument();
    expect(screen.getByText("Failures (24h)")).toBeInTheDocument();
  });

  it("does not show skeleton when not loading", () => {
    const { container } = render(<StatsCards stats={mockStats} loading={false} />);
    const skeletons = container.querySelectorAll(".animate-pulse");
    expect(skeletons).toHaveLength(0);
  });
});
