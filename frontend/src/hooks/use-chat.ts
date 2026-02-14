"use client";

import { useCallback, useRef, useState } from "react";
import { api } from "@/lib/api";
import type { ChatMessage, ChatResponse } from "@/types";

export function useChat() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const sessionIdRef = useRef<string | null>(null);

  const sendMessage = useCallback(async (question: string) => {
    setError(null);
    setIsLoading(true);

    // Add user message immediately (optimistic)
    const userMessage: ChatMessage = { role: "user", content: question };
    setMessages((prev) => [...prev, userMessage]);

    try {
      const response: ChatResponse = await api.chat({
        question,
        session_id: sessionIdRef.current || undefined,
      });

      sessionIdRef.current = response.session_id;

      const assistantMessage: ChatMessage = {
        role: "assistant",
        content: response.answer,
        query_type: response.query_type,
        sources_used: response.sources_used,
      };
      setMessages((prev) => [...prev, assistantMessage]);
    } catch (err: any) {
      setError(err.message || "Failed to get response");
      // Remove the optimistic user message on error
      setMessages((prev) => prev.slice(0, -1));
    } finally {
      setIsLoading(false);
    }
  }, []);

  const clearChat = useCallback(() => {
    setMessages([]);
    sessionIdRef.current = null;
    setError(null);
  }, []);

  return {
    messages,
    isLoading,
    error,
    sendMessage,
    clearChat,
    sessionId: sessionIdRef.current,
  };
}
