import { describe, it, expect, beforeEach } from "vitest";
import { render, screen, act } from "@testing-library/react";
import TestingLayout from "@/app/testing/layout";

// AuthGuard checks localStorage for bp_api_key; set it so children render.
beforeEach(() => {
  localStorage.setItem("bp_api_key", "test-key");
});

describe("TestingLayout", () => {
  it("renders its children", async () => {
    await act(async () => {
      render(<TestingLayout><p>test content</p></TestingLayout>);
    });
    expect(screen.getByText("test content")).toBeInTheDocument();
  });

  it("renders the Sidebar (aside landmark)", async () => {
    await act(async () => {
      render(<TestingLayout><p>child</p></TestingLayout>);
    });
    expect(document.querySelector("aside")).toBeInTheDocument();
  });

  it("renders the Header (sticky header element)", async () => {
    await act(async () => {
      render(<TestingLayout><p>child</p></TestingLayout>);
    });
    expect(document.querySelector("header")).toBeInTheDocument();
  });

  it("renders children inside a main element", async () => {
    await act(async () => {
      render(<TestingLayout><p>main content</p></TestingLayout>);
    });
    const main = document.querySelector("main");
    expect(main).toBeInTheDocument();
    expect(main!.textContent).toContain("main content");
  });

  it("wraps output in a full-height container (smoke test — no crash)", async () => {
    let container: HTMLElement;
    await act(async () => {
      ({ container } = render(<TestingLayout><span>ok</span></TestingLayout>));
    });
    expect(container!.firstChild).toBeInTheDocument();
  });
});
