import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { KeyValueField } from "@/components/forms/key-value-field";

function Wrapper({ initial = {} }: { initial?: Record<string, string> }) {
  const [value, setValue] = useState<Record<string, string>>(initial);
  return <KeyValueField label="Properties" value={value} onChange={setValue} />;
}

describe("KeyValueField", () => {
  it("renders the label", () => {
    render(<Wrapper />);
    expect(screen.getByText("Properties")).toBeInTheDocument();
  });

  it("renders no inputs initially when value is empty", () => {
    render(<Wrapper />);
    // Only the Add Entry button, no key/value inputs
    expect(screen.queryAllByPlaceholderText("Key")).toHaveLength(0);
  });

  it("renders existing key-value pairs", () => {
    render(<Wrapper initial={{ host: "localhost", port: "5432" }} />);
    expect(screen.getByDisplayValue("host")).toBeInTheDocument();
    expect(screen.getByDisplayValue("localhost")).toBeInTheDocument();
    expect(screen.getByDisplayValue("port")).toBeInTheDocument();
    expect(screen.getByDisplayValue("5432")).toBeInTheDocument();
  });

  it("adds a new empty pair when Add Entry clicked", async () => {
    const user = userEvent.setup();
    render(<Wrapper />);
    await user.click(screen.getByRole("button", { name: /add entry/i }));
    expect(screen.getByPlaceholderText("Key")).toBeInTheDocument();
    expect(screen.getByPlaceholderText("Value")).toBeInTheDocument();
  });

  it("updates value field when user types in value input", async () => {
    const user = userEvent.setup();
    render(<Wrapper initial={{ host: "" }} />);
    const valueInput = screen.getByPlaceholderText("Value");
    await user.type(valueInput, "localhost");
    expect(screen.getByDisplayValue("localhost")).toBeInTheDocument();
  });

  it("removes entry when trash button clicked", async () => {
    const user = userEvent.setup();
    render(<Wrapper initial={{ key1: "val1", key2: "val2" }} />);
    expect(screen.getAllByPlaceholderText("Key")).toHaveLength(2);

    const trashButtons = screen.getAllByRole("button").filter((b) => !b.textContent?.includes("Add"));
    await user.click(trashButtons[0]);

    expect(screen.getAllByPlaceholderText("Key")).toHaveLength(1);
  });

  it("can add a second entry after filling in the first key", async () => {
    const user = userEvent.setup();
    render(<Wrapper />);
    const addBtn = screen.getByRole("button", { name: /add entry/i });

    // Add first entry
    await user.click(addBtn);
    // Fill in the key so it's not an empty string (avoids object key collision)
    const keyInput = screen.getByPlaceholderText("Key");
    await user.type(keyInput, "host");

    // Now add second entry — key "" doesn't collide with "host"
    await user.click(addBtn);
    expect(screen.getAllByPlaceholderText("Key")).toHaveLength(2);
  });
});
