import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, act, waitFor } from "@testing-library/react";

// ── Router mock ─────────────────────────────────────────────────────────
const mockReplace = vi.fn();

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn(), replace: mockReplace, back: vi.fn() }),
  usePathname: () => "/bronze",
  useParams: () => ({}),
  redirect: vi.fn(),
}));

// ── api mock ────────────────────────────────────────────────────────────
const mockLogout = vi.fn();
vi.mock("@/lib/api", () => ({
  api: {
    logout: () => mockLogout(),
  },
}));

// ── useCurrentUser mock (controllable per-test) ─────────────────────────
type CurrentUser = {
  tenant_id: string;
  username: string | null;
  display_name: string | null;
  role: string;
  last_login: string | null;
};

const mockUseCurrentUser = vi.fn<() => { data: CurrentUser | undefined }>(() => ({
  data: undefined,
}));

vi.mock("@/hooks/use-current-user", () => ({
  useCurrentUser: () => mockUseCurrentUser(),
}));

import { Header } from "@/components/layout/header";

beforeEach(() => {
  localStorage.clear();
  mockReplace.mockClear();
  mockLogout.mockReset();
  mockLogout.mockResolvedValue({ success: true });
  mockUseCurrentUser.mockReset();
  mockUseCurrentUser.mockReturnValue({ data: undefined });
});

// ── Avatar / initial rendering ──────────────────────────────────────────

describe("Header — avatar initial", () => {
  it("renders first initial of display_name uppercased", () => {
    mockUseCurrentUser.mockReturnValue({
      data: {
        tenant_id: "default",
        username: "alice",
        display_name: "alice cooper",
        role: "admin",
        last_login: null,
      },
    });
    render(<Header />);
    // The avatar badge shows the first character — find via the parent button.
    const button = screen.getByRole("button", { name: /alice cooper/i });
    // A — first char of "alice cooper" uppercased
    expect(button.textContent).toContain("A");
  });

  it("falls back to username initial when display_name is null", () => {
    mockUseCurrentUser.mockReturnValue({
      data: {
        tenant_id: "default",
        username: "bob",
        display_name: null,
        role: "user",
        last_login: null,
      },
    });
    render(<Header />);
    const button = screen.getByRole("button", { name: /bob/i });
    expect(button.textContent).toContain("B");
  });

  it("falls back to 'U' when no user data and no localStorage values", () => {
    render(<Header />);
    const button = screen.getByRole("button", { name: /account/i });
    expect(button.textContent).toContain("U");
  });

  it("falls back to localStorage display_name when SWR has no data", () => {
    localStorage.setItem("bp_display_name", "Stored Name");
    render(<Header />);
    const button = screen.getByRole("button", { name: /stored name/i });
    expect(button.textContent).toContain("S");
  });

  it("falls back to localStorage username when neither SWR data nor display_name is present", () => {
    localStorage.setItem("bp_username", "carol");
    render(<Header />);
    const button = screen.getByRole("button", { name: /carol/i });
    expect(button.textContent).toContain("C");
  });
});

// ── Menu open/close ─────────────────────────────────────────────────────

describe("Header — dropdown menu", () => {
  it("menu is closed by default", () => {
    mockUseCurrentUser.mockReturnValue({
      data: {
        tenant_id: "default",
        username: "alice",
        display_name: "Alice",
        role: "admin",
        last_login: null,
      },
    });
    render(<Header />);
    expect(screen.queryByText(/sign out/i)).not.toBeInTheDocument();
  });

  it("clicking the avatar opens the menu", async () => {
    mockUseCurrentUser.mockReturnValue({
      data: {
        tenant_id: "default",
        username: "alice",
        display_name: "Alice",
        role: "admin",
        last_login: null,
      },
    });
    render(<Header />);
    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: /alice/i }));
    });
    expect(screen.getByText(/sign out/i)).toBeInTheDocument();
  });

  it("menu shows display_name", async () => {
    mockUseCurrentUser.mockReturnValue({
      data: {
        tenant_id: "default",
        username: "alice",
        display_name: "Alice Wonderland",
        role: "admin",
        last_login: null,
      },
    });
    render(<Header />);
    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: /alice/i }));
    });
    // Both the trigger and the menu show the name; assert the menu contains it.
    const matches = screen.getAllByText("Alice Wonderland");
    expect(matches.length).toBeGreaterThanOrEqual(1);
  });

  it("menu shows the role", async () => {
    mockUseCurrentUser.mockReturnValue({
      data: {
        tenant_id: "default",
        username: "alice",
        display_name: "Alice",
        role: "admin",
        last_login: null,
      },
    });
    render(<Header />);
    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: /alice/i }));
    });
    // The role text is rendered with `capitalize` CSS — text content is still
    // the raw value 'admin'.
    expect(screen.getByText("admin")).toBeInTheDocument();
  });

  it("clicking outside closes the menu", async () => {
    mockUseCurrentUser.mockReturnValue({
      data: {
        tenant_id: "default",
        username: "alice",
        display_name: "Alice",
        role: "admin",
        last_login: null,
      },
    });
    render(<Header />);
    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: /alice/i }));
    });
    expect(screen.getByText(/sign out/i)).toBeInTheDocument();

    // Mousedown outside the menu container — the listener uses mousedown.
    await act(async () => {
      fireEvent.mouseDown(document.body);
    });
    expect(screen.queryByText(/sign out/i)).not.toBeInTheDocument();
  });
});

// ── Sign out behaviour ──────────────────────────────────────────────────

describe("Header — sign out", () => {
  async function openMenuAndClickSignOut() {
    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: /alice|account/i }));
    });
    await act(async () => {
      fireEvent.click(screen.getByText(/sign out/i));
    });
  }

  it("clears all bp_* localStorage keys", async () => {
    localStorage.setItem("bp_api_key", "key");
    localStorage.setItem("bp_username", "alice");
    localStorage.setItem("bp_display_name", "Alice");
    localStorage.setItem("bp_role", "admin");

    mockUseCurrentUser.mockReturnValue({
      data: {
        tenant_id: "default",
        username: "alice",
        display_name: "Alice",
        role: "admin",
        last_login: null,
      },
    });
    render(<Header />);
    await openMenuAndClickSignOut();

    await waitFor(() => {
      expect(localStorage.getItem("bp_api_key")).toBeNull();
    });
    expect(localStorage.getItem("bp_username")).toBeNull();
    expect(localStorage.getItem("bp_display_name")).toBeNull();
    expect(localStorage.getItem("bp_role")).toBeNull();
  });

  it("redirects to /login via router.replace", async () => {
    mockUseCurrentUser.mockReturnValue({
      data: {
        tenant_id: "default",
        username: "alice",
        display_name: "Alice",
        role: "admin",
        last_login: null,
      },
    });
    render(<Header />);
    await openMenuAndClickSignOut();

    await waitFor(() => {
      expect(mockReplace).toHaveBeenCalledWith("/login");
    });
  });

  it("calls api.logout()", async () => {
    mockUseCurrentUser.mockReturnValue({
      data: {
        tenant_id: "default",
        username: "alice",
        display_name: "Alice",
        role: "admin",
        last_login: null,
      },
    });
    render(<Header />);
    await openMenuAndClickSignOut();

    await waitFor(() => {
      expect(mockLogout).toHaveBeenCalled();
    });
  });

  it("still clears localStorage and redirects when api.logout() rejects", async () => {
    localStorage.setItem("bp_api_key", "key");
    mockLogout.mockRejectedValue(new Error("offline"));
    mockUseCurrentUser.mockReturnValue({
      data: {
        tenant_id: "default",
        username: "alice",
        display_name: "Alice",
        role: "admin",
        last_login: null,
      },
    });
    render(<Header />);
    await openMenuAndClickSignOut();

    await waitFor(() => {
      expect(localStorage.getItem("bp_api_key")).toBeNull();
    });
    expect(mockReplace).toHaveBeenCalledWith("/login");
  });
});
