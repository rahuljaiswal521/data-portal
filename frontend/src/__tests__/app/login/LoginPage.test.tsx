import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, fireEvent, waitFor, act } from "@testing-library/react";
import LoginPage from "@/app/login/page";

// ── Router / searchParams mock ──────────────────────────────────────────
const mockReplace = vi.fn();
const mockSearchParamsGet = vi.fn<(key: string) => string | null>(() => null);

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn(), replace: mockReplace, back: vi.fn() }),
  usePathname: () => "/login",
  useParams: () => ({}),
  useSearchParams: () => ({ get: mockSearchParamsGet }),
  redirect: vi.fn(),
}));

// ── api.login mock ──────────────────────────────────────────────────────
const mockLogin = vi.fn();
vi.mock("@/lib/api", () => ({
  api: {
    login: (body: { username: string; password: string }) => mockLogin(body),
  },
}));

class MockApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
    this.name = "ApiError";
  }
}

beforeEach(() => {
  localStorage.clear();
  mockReplace.mockClear();
  mockLogin.mockReset();
  mockSearchParamsGet.mockReset();
  mockSearchParamsGet.mockReturnValue(null);
});

afterEach(() => {
  vi.restoreAllMocks();
});

async function fillAndSubmit(username: string, password: string) {
  const userInput = screen.getByPlaceholderText(/admin/i);
  const pwInput = screen.getByPlaceholderText(/enter password/i);
  fireEvent.change(userInput, { target: { value: username } });
  fireEvent.change(pwInput, { target: { value: password } });
  await act(async () => {
    fireEvent.click(screen.getByRole("button", { name: /sign in/i }));
  });
}

// ── Rendering ────────────────────────────────────────────────────────────

describe("LoginPage — rendering", () => {
  it("renders username and password inputs", () => {
    render(<LoginPage />);
    expect(screen.getByPlaceholderText(/admin/i)).toBeInTheDocument();
    expect(screen.getByPlaceholderText(/enter password/i)).toBeInTheDocument();
  });

  it("renders a Sign in button", () => {
    render(<LoginPage />);
    expect(screen.getByRole("button", { name: /sign in/i })).toBeInTheDocument();
  });

  it("renders the page heading 'Data Portal'", () => {
    render(<LoginPage />);
    expect(screen.getByText("Data Portal")).toBeInTheDocument();
  });
});

// ── Button disabled state ─────────────────────────────────────────────────

describe("LoginPage — Sign in button disabled state", () => {
  it("Sign in button is disabled when fields are empty", () => {
    render(<LoginPage />);
    expect(screen.getByRole("button", { name: /sign in/i })).toBeDisabled();
  });

  it("Sign in button is enabled only when both fields are filled", async () => {
    render(<LoginPage />);
    const userInput = screen.getByPlaceholderText(/admin/i);
    const pwInput = screen.getByPlaceholderText(/enter password/i);
    await act(async () => {
      fireEvent.change(userInput, { target: { value: "admin" } });
    });
    expect(screen.getByRole("button", { name: /sign in/i })).toBeDisabled();
    await act(async () => {
      fireEvent.change(pwInput, { target: { value: "pw" } });
    });
    expect(screen.getByRole("button", { name: /sign in/i })).not.toBeDisabled();
  });
});

// ── Successful login ──────────────────────────────────────────────────────

describe("LoginPage — successful login", () => {
  it("stores api_key + profile in localStorage on success", async () => {
    mockLogin.mockResolvedValue({
      api_key: "bp_issued_key",
      tenant_id: "default",
      username: "admin",
      display_name: "Administrator",
      role: "admin",
    });
    render(<LoginPage />);
    await fillAndSubmit("admin", "hunter2");
    await waitFor(() => {
      expect(localStorage.getItem("bp_api_key")).toBe("bp_issued_key");
    });
    expect(localStorage.getItem("bp_username")).toBe("admin");
    expect(localStorage.getItem("bp_display_name")).toBe("Administrator");
    expect(localStorage.getItem("bp_role")).toBe("admin");
  });

  it("redirects to /bronze by default after successful login", async () => {
    mockLogin.mockResolvedValue({
      api_key: "k",
      tenant_id: "default",
      username: "admin",
      display_name: null,
      role: "user",
    });
    render(<LoginPage />);
    await fillAndSubmit("admin", "pw");
    await waitFor(() => {
      expect(mockReplace).toHaveBeenCalledWith("/bronze");
    });
  });

  it("redirects to 'from' param path after successful login", async () => {
    mockSearchParamsGet.mockReturnValue("/bronze/my-source");
    mockLogin.mockResolvedValue({
      api_key: "k",
      tenant_id: "default",
      username: "admin",
      display_name: null,
      role: "user",
    });
    render(<LoginPage />);
    await fillAndSubmit("admin", "pw");
    await waitFor(() => {
      expect(mockReplace).toHaveBeenCalledWith("/bronze/my-source");
    });
  });

  it("calls api.login with username and password", async () => {
    mockLogin.mockResolvedValue({
      api_key: "k",
      tenant_id: "default",
      username: "admin",
      display_name: null,
      role: "user",
    });
    render(<LoginPage />);
    await fillAndSubmit("admin", "my-secret");
    await waitFor(() => {
      expect(mockLogin).toHaveBeenCalledWith({
        username: "admin",
        password: "my-secret",
      });
    });
  });
});

// ── Failed login ──────────────────────────────────────────────────────────

describe("LoginPage — failed login (401)", () => {
  it("shows invalid-credentials error on 401 response", async () => {
    mockLogin.mockRejectedValue(new MockApiError(401, "Invalid username or password"));
    render(<LoginPage />);
    await fillAndSubmit("admin", "wrong");
    await waitFor(() => {
      expect(screen.getByText(/invalid username or password/i)).toBeInTheDocument();
    });
  });

  it("does not store key in localStorage on 401", async () => {
    mockLogin.mockRejectedValue(new MockApiError(401, "Invalid username or password"));
    render(<LoginPage />);
    await fillAndSubmit("admin", "wrong");
    await waitFor(() => {
      expect(screen.getByText(/invalid username or password/i)).toBeInTheDocument();
    });
    expect(localStorage.getItem("bp_api_key")).toBeNull();
  });

  it("does not redirect on 401", async () => {
    mockLogin.mockRejectedValue(new MockApiError(401, "Invalid username or password"));
    render(<LoginPage />);
    await fillAndSubmit("admin", "wrong");
    await waitFor(() => {
      expect(screen.getByText(/invalid username or password/i)).toBeInTheDocument();
    });
    expect(mockReplace).not.toHaveBeenCalled();
  });
});

// ── Network error ─────────────────────────────────────────────────────────

describe("LoginPage — network error", () => {
  it("shows server unreachable error on non-401 failure", async () => {
    mockLogin.mockRejectedValue(new Error("Network error"));
    render(<LoginPage />);
    await fillAndSubmit("admin", "any");
    await waitFor(() => {
      expect(screen.getByText(/could not reach the server/i)).toBeInTheDocument();
    });
  });

  it("does not redirect on network error", async () => {
    mockLogin.mockRejectedValue(new Error("Network error"));
    render(<LoginPage />);
    await fillAndSubmit("admin", "any");
    await waitFor(() => {
      expect(screen.getByText(/could not reach the server/i)).toBeInTheDocument();
    });
    expect(mockReplace).not.toHaveBeenCalled();
  });
});
