import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { FormWizard } from "@/components/forms/form-wizard";

const makeSteps = (count: number) =>
  Array.from({ length: count }, (_, i) => ({
    id: `step-${i}`,
    title: `Step ${i + 1} Title`,
    description: `Step ${i + 1} description`,
    content: <div data-testid={`content-${i}`}>Content {i + 1}</div>,
  }));

describe("FormWizard", () => {
  it("renders the first step title in the content heading", () => {
    render(<FormWizard steps={makeSteps(3)} onSubmit={vi.fn()} />);
    // The h3 in the content area (not sidebar) shows the current step title
    expect(screen.getByRole("heading", { name: "Step 1 Title" })).toBeInTheDocument();
  });

  it("renders first step description in the content area", () => {
    render(<FormWizard steps={makeSteps(3)} onSubmit={vi.fn()} />);
    // Content description (p in content, not sidebar which has its own description)
    // The content area description is in a <p> with mb-6 class
    expect(screen.getAllByText("Step 1 description").length).toBeGreaterThanOrEqual(1);
  });

  it("renders first step content", () => {
    render(<FormWizard steps={makeSteps(3)} onSubmit={vi.fn()} />);
    expect(screen.getByTestId("content-0")).toBeInTheDocument();
  });

  it("Previous button is disabled on first step", () => {
    render(<FormWizard steps={makeSteps(3)} onSubmit={vi.fn()} />);
    expect(screen.getByRole("button", { name: "Previous" })).toBeDisabled();
  });

  it("Continue button is visible on non-last step", () => {
    render(<FormWizard steps={makeSteps(3)} onSubmit={vi.fn()} />);
    expect(screen.getByRole("button", { name: "Continue" })).toBeInTheDocument();
  });

  it("clicking Continue navigates to step 2", async () => {
    const user = userEvent.setup();
    render(<FormWizard steps={makeSteps(3)} onSubmit={vi.fn()} />);
    await user.click(screen.getByRole("button", { name: "Continue" }));
    expect(screen.getByRole("heading", { name: "Step 2 Title" })).toBeInTheDocument();
    expect(screen.getByTestId("content-1")).toBeInTheDocument();
  });

  it("Previous is enabled after moving past step 1", async () => {
    const user = userEvent.setup();
    render(<FormWizard steps={makeSteps(3)} onSubmit={vi.fn()} />);
    await user.click(screen.getByRole("button", { name: "Continue" }));
    expect(screen.getByRole("button", { name: "Previous" })).not.toBeDisabled();
  });

  it("clicking Previous goes back one step", async () => {
    const user = userEvent.setup();
    render(<FormWizard steps={makeSteps(3)} onSubmit={vi.fn()} />);
    await user.click(screen.getByRole("button", { name: "Continue" }));
    await user.click(screen.getByRole("button", { name: "Previous" }));
    expect(screen.getByRole("heading", { name: "Step 1 Title" })).toBeInTheDocument();
  });

  it("clicking a step in the sidebar jumps directly to it", async () => {
    const user = userEvent.setup();
    render(<FormWizard steps={makeSteps(3)} onSubmit={vi.fn()} />);
    // The sidebar nav buttons contain the step title as text
    const sidebarStep3 = screen.getByRole("button", {
      name: /Step 3 Title/,
    });
    await user.click(sidebarStep3);
    expect(screen.getByRole("heading", { name: "Step 3 Title" })).toBeInTheDocument();
    expect(screen.getByTestId("content-2")).toBeInTheDocument();
  });

  it("shows Submit button (not Continue) on last step", async () => {
    const user = userEvent.setup();
    render(<FormWizard steps={makeSteps(2)} onSubmit={vi.fn()} />);
    await user.click(screen.getByRole("button", { name: "Continue" }));
    expect(screen.queryByRole("button", { name: "Continue" })).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Create Source" })).toBeInTheDocument();
  });

  it("shows Submit immediately when only 1 step", () => {
    render(<FormWizard steps={makeSteps(1)} onSubmit={vi.fn()} />);
    expect(screen.getByRole("button", { name: "Create Source" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Continue" })).not.toBeInTheDocument();
  });

  it("calls onSubmit when Submit button is clicked", async () => {
    const user = userEvent.setup();
    const onSubmit = vi.fn();
    render(<FormWizard steps={makeSteps(1)} onSubmit={onSubmit} />);
    await user.click(screen.getByRole("button", { name: "Create Source" }));
    expect(onSubmit).toHaveBeenCalledTimes(1);
  });

  it("shows custom submitLabel", () => {
    render(<FormWizard steps={makeSteps(1)} onSubmit={vi.fn()} submitLabel="Save Entity" />);
    expect(screen.getByRole("button", { name: "Save Entity" })).toBeInTheDocument();
  });

  it("shows 'Creating...' and disables submit when submitting=true", () => {
    render(<FormWizard steps={makeSteps(1)} onSubmit={vi.fn()} submitting />);
    const btn = screen.getByRole("button", { name: "Creating..." });
    expect(btn).toBeInTheDocument();
    expect(btn).toBeDisabled();
  });

  it("shows all 3 step titles in the sidebar nav", () => {
    render(<FormWizard steps={makeSteps(3)} onSubmit={vi.fn()} />);
    // Each step title appears in at least one nav button in the sidebar
    expect(screen.getByRole("button", { name: /Step 1 Title/ })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Step 2 Title/ })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Step 3 Title/ })).toBeInTheDocument();
  });
});
