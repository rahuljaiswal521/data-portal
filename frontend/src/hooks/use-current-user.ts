import useSWR from "swr";
import { api } from "@/lib/api";
import type { CurrentUser } from "@/types";

export function useCurrentUser() {
  return useSWR<CurrentUser>("/auth/me", api.getCurrentUser, {
    revalidateOnFocus: false,
    shouldRetryOnError: false,
  });
}
