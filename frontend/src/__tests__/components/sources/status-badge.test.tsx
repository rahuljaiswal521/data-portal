import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import {
  TypeBadge,
  StatusBadge,
  CdcBadge,
  EnabledDot,
} from "@/components/sources/status-badge";

describe("TypeBadge", () => {
  it("renders JDBC in uppercase", () => {
    render(<TypeBadge type="jdbc" />);
    expect(screen.getByText("JDBC")).toBeInTheDocument();
  });

  it("renders FILE in uppercase", () => {
    render(<TypeBadge type="file" />);
    expect(screen.getByText("FILE")).toBeInTheDocument();
  });

  it("renders API in uppercase", () => {
    render(<TypeBadge type="api" />);
    expect(screen.getByText("API")).toBeInTheDocument();
  });

  it("renders STREAM in uppercase", () => {
    render(<TypeBadge type="stream" />);
    expect(screen.getByText("STREAM")).toBeInTheDocument();
  });

  it("jdbc uses info variant", () => {
    render(<TypeBadge type="jdbc" />);
    expect(screen.getByText("JDBC").className).toMatch(/text-info/);
  });

  it("api uses accent variant", () => {
    render(<TypeBadge type="api" />);
    expect(screen.getByText("API").className).toMatch(/text-accent/);
  });

  it("stream uses warning variant", () => {
    render(<TypeBadge type="stream" />);
    expect(screen.getByText("STREAM").className).toMatch(/text-warning/);
  });

  it("unknown type falls back to default variant", () => {
    render(<TypeBadge type="unknown" />);
    expect(screen.getByText("UNKNOWN")).toBeInTheDocument();
  });
});

describe("StatusBadge", () => {
  it("renders SUCCESS", () => {
    render(<StatusBadge status="SUCCESS" />);
    const badge = screen.getByText("SUCCESS");
    expect(badge).toBeInTheDocument();
    expect(badge.className).toMatch(/text-success/);
  });

  it("renders FAILURE with error variant", () => {
    render(<StatusBadge status="FAILURE" />);
    const badge = screen.getByText("FAILURE");
    expect(badge.className).toMatch(/text-error/);
  });

  it("renders RUNNING with info variant", () => {
    render(<StatusBadge status="RUNNING" />);
    const badge = screen.getByText("RUNNING");
    expect(badge.className).toMatch(/text-info/);
  });

  it("renders unknown status with default variant", () => {
    render(<StatusBadge status="PENDING" />);
    const badge = screen.getByText("PENDING");
    expect(badge.className).toMatch(/bg-bg-secondary/);
  });
});

describe("CdcBadge", () => {
  it("renders SCD2 for scd2 mode", () => {
    render(<CdcBadge mode="scd2" />);
    expect(screen.getByText("SCD2")).toBeInTheDocument();
  });

  it("scd2 uses accent variant", () => {
    render(<CdcBadge mode="scd2" />);
    expect(screen.getByText("SCD2").className).toMatch(/text-accent/);
  });

  it("renders Upsert (capitalized) for upsert mode", () => {
    render(<CdcBadge mode="upsert" />);
    expect(screen.getByText("Upsert")).toBeInTheDocument();
  });

  it("upsert uses info variant", () => {
    render(<CdcBadge mode="upsert" />);
    expect(screen.getByText("Upsert").className).toMatch(/text-info/);
  });

  it("renders Append (capitalized) for append mode", () => {
    render(<CdcBadge mode="append" />);
    expect(screen.getByText("Append")).toBeInTheDocument();
  });

  it("append uses default variant", () => {
    render(<CdcBadge mode="append" />);
    expect(screen.getByText("Append").className).toMatch(/bg-bg-secondary/);
  });
});

describe("EnabledDot", () => {
  it("has Enabled title when enabled=true", () => {
    render(<EnabledDot enabled={true} />);
    expect(screen.getByTitle("Enabled")).toBeInTheDocument();
  });

  it("has Disabled title when enabled=false", () => {
    render(<EnabledDot enabled={false} />);
    expect(screen.getByTitle("Disabled")).toBeInTheDocument();
  });

  it("applies bg-success class when enabled", () => {
    render(<EnabledDot enabled={true} />);
    expect(screen.getByTitle("Enabled").className).toMatch(/bg-success/);
  });

  it("applies bg-text-tertiary class when disabled", () => {
    render(<EnabledDot enabled={false} />);
    expect(screen.getByTitle("Disabled").className).toMatch(/bg-text-tertiary/);
  });
});
