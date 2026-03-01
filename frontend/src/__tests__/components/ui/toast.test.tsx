import { describe, it, expect, vi, afterEach } from "vitest";
import { render, screen, fireEvent, act } from "@testing-library/react";
import { ToastProvider, useToast } from "@/components/ui/toast";

// Helper component that exposes the toast function via a button
function ToastTrigger({
  message,
  type,
}: {
  message: string;
  type?: "success" | "error" | "info";
}) {
  const { toast } = useToast();
  return <button onClick={() => toast(message, type)}>Trigger</button>;
}

function renderWithProvider(
  message = "Hello toast",
  type?: "success" | "error" | "info"
) {
  return render(
    <ToastProvider>
      <ToastTrigger message={message} type={type} />
    </ToastProvider>
  );
}

afterEach(() => {
  vi.useRealTimers();
});

describe("ToastProvider / useToast", () => {
  it("shows toast message after calling toast()", () => {
    renderWithProvider("My message");
    fireEvent.click(screen.getByRole("button", { name: "Trigger" }));
    expect(screen.getByText("My message")).toBeInTheDocument();
  });

  it("auto-dismisses after 4000ms", async () => {
    vi.useFakeTimers();
    renderWithProvider("Auto dismiss");
    fireEvent.click(screen.getByRole("button", { name: "Trigger" }));
    expect(screen.getByText("Auto dismiss")).toBeInTheDocument();

    await act(async () => {
      vi.advanceTimersByTime(4001);
    });

    expect(screen.queryByText("Auto dismiss")).not.toBeInTheDocument();
  });

  it("does NOT dismiss before 4000ms", async () => {
    vi.useFakeTimers();
    renderWithProvider("Still here");
    fireEvent.click(screen.getByRole("button", { name: "Trigger" }));

    await act(async () => {
      vi.advanceTimersByTime(3999);
    });

    expect(screen.getByText("Still here")).toBeInTheDocument();
  });

  it("removes toast when dismiss X button clicked", () => {
    renderWithProvider("Dismiss me");
    fireEvent.click(screen.getByRole("button", { name: "Trigger" }));
    expect(screen.getByText("Dismiss me")).toBeInTheDocument();

    // The X dismiss button has no text — get all buttons and click the non-Trigger one
    const allButtons = screen.getAllByRole("button");
    const dismissBtn = allButtons.find((b) => b.textContent !== "Trigger");
    expect(dismissBtn).toBeDefined();
    fireEvent.click(dismissBtn!);
    expect(screen.queryByText("Dismiss me")).not.toBeInTheDocument();
  });

  it("can show a second toast while first is visible", () => {
    renderWithProvider("First");
    fireEvent.click(screen.getByRole("button", { name: "Trigger" }));
    fireEvent.click(screen.getByRole("button", { name: "Trigger" }));
    expect(screen.getAllByText("First")).toHaveLength(2);
  });

  it("applies success styling to the toast container", () => {
    renderWithProvider("Success!", "success");
    fireEvent.click(screen.getByRole("button", { name: "Trigger" }));
    const msg = screen.getByText("Success!");
    expect(msg.closest("div")?.className).toMatch(/border-success/);
  });

  it("applies error styling to the toast container", () => {
    renderWithProvider("Failed!", "error");
    fireEvent.click(screen.getByRole("button", { name: "Trigger" }));
    const msg = screen.getByText("Failed!");
    expect(msg.closest("div")?.className).toMatch(/border-error/);
  });
});
