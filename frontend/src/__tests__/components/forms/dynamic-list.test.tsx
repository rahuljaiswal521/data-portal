import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { DynamicList } from "@/components/forms/dynamic-list";

// Stateful wrapper so we can observe the full interaction cycle
function Wrapper({ initial = [] }: { initial?: string[] }) {
  const [value, setValue] = useState<string[]>(initial);
  return <DynamicList label="Tags" value={value} onChange={setValue} placeholder="Enter tag" />;
}

describe("DynamicList", () => {
  it("renders the label", () => {
    render(<Wrapper />);
    expect(screen.getByText("Tags")).toBeInTheDocument();
  });

  it("renders no inputs initially when value is empty", () => {
    render(<Wrapper />);
    expect(screen.queryAllByRole("textbox")).toHaveLength(0);
  });

  it("renders existing items as inputs", () => {
    render(<Wrapper initial={["alpha", "beta"]} />);
    expect(screen.getAllByRole("textbox")).toHaveLength(2);
    expect(screen.getByDisplayValue("alpha")).toBeInTheDocument();
    expect(screen.getByDisplayValue("beta")).toBeInTheDocument();
  });

  it("adds an empty item when Add button clicked", async () => {
    const user = userEvent.setup();
    render(<Wrapper />);
    await user.click(screen.getByRole("button", { name: /add/i }));
    expect(screen.getAllByRole("textbox")).toHaveLength(1);
  });

  it("updates item value when user types", async () => {
    const user = userEvent.setup();
    render(<Wrapper initial={[""]} />);
    const input = screen.getByRole("textbox");
    await user.type(input, "newvalue");
    expect(screen.getByDisplayValue("newvalue")).toBeInTheDocument();
  });

  it("removes an item when trash button is clicked", async () => {
    const user = userEvent.setup();
    render(<Wrapper initial={["remove-me", "keep-me"]} />);
    expect(screen.getAllByRole("textbox")).toHaveLength(2);
    // Click the first trash button
    const trashButtons = screen.getAllByRole("button").filter((b) => !b.textContent?.includes("Add"));
    await user.click(trashButtons[0]);
    expect(screen.getAllByRole("textbox")).toHaveLength(1);
    expect(screen.queryByDisplayValue("remove-me")).not.toBeInTheDocument();
    expect(screen.getByDisplayValue("keep-me")).toBeInTheDocument();
  });

  it("can add multiple items", async () => {
    const user = userEvent.setup();
    render(<Wrapper />);
    const addBtn = screen.getByRole("button", { name: /add/i });
    await user.click(addBtn);
    await user.click(addBtn);
    await user.click(addBtn);
    expect(screen.getAllByRole("textbox")).toHaveLength(3);
  });

  it("shows placeholder in inputs", async () => {
    const user = userEvent.setup();
    render(<Wrapper />);
    await user.click(screen.getByRole("button", { name: /add/i }));
    expect(screen.getByPlaceholderText("Enter tag")).toBeInTheDocument();
  });
});
