import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, act } from "@testing-library/react";
import { AuthGuard } from "@/components/layout/AuthGuard";

// ── Router mock (override setup.tsx to get a controllable replace fn) ──
const mockReplace = vi.fn();

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn(), replace: mockReplace, back: vi.fn() }),
  usePathname: () => "/bronze",
  useParams: () => ({}),
  redirect: vi.fn(),
}));

beforeEach(() => {
  localStorage.clear();
  mockReplace.mockClear();
});

describe("AuthGuard — renders null while checking", () => {
  it("renders nothing before the useEffect fires (initial state)", () => {
    // localStorage is empty so it will redirect, but before the effect
    // settles the component should render null.
    // We capture the container synchronously, before any async effects.
    const { container } = render(<AuthGuard><span>protected</span></AuthGuard>);
    // In happy-dom useEffect fires synchronously after render, so
    // the component is in the redirect branch and still shows nothing.
    expect(container.querySelector("span")).toBeNull();
  });
});

describe("AuthGuard — localStorage key present", () => {
  it("renders children when bp_api_key is set", async () => {
    localStorage.setItem("bp_api_key", "test-key");
    await act(async () => {
      render(<AuthGuard><span>protected content</span></AuthGuard>);
    });
    expect(screen.getByText("protected content")).toBeInTheDocument();
  });

  it("does not call router.replace when key is present", async () => {
    localStorage.setItem("bp_api_key", "test-key");
    await act(async () => {
      render(<AuthGuard><span>ok</span></AuthGuard>);
    });
    expect(mockReplace).not.toHaveBeenCalled();
  });
});

describe("AuthGuard — localStorage key absent", () => {
  it("redirects to /login?from=... when no key in localStorage", async () => {
    await act(async () => {
      render(<AuthGuard><span>secret</span></AuthGuard>);
    });
    expect(mockReplace).toHaveBeenCalledWith(
      expect.stringContaining("/login?from=")
    );
  });

  it("encodes the current pathname in the redirect URL", async () => {
    await act(async () => {
      render(<AuthGuard><span>secret</span></AuthGuard>);
    });
    // usePathname returns "/bronze" from our mock
    expect(mockReplace).toHaveBeenCalledWith(
      `/login?from=${encodeURIComponent("/bronze")}`
    );
  });

  it("does not render children when key is missing", async () => {
    await act(async () => {
      render(<AuthGuard><span>secret</span></AuthGuard>);
    });
    expect(screen.queryByText("secret")).not.toBeInTheDocument();
  });
});
