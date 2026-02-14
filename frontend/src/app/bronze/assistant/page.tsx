"use client";

import { ChatContainer } from "@/components/assistant/chat-container";

export default function AssistantPage() {
  return (
    <div className="max-w-4xl mx-auto">
      <div className="mb-6">
        <h1 className="text-2xl font-semibold text-text-primary">
          Data Platform Assistant
        </h1>
        <p className="text-sm text-text-secondary mt-1">
          Ask questions about your Bronze, Silver, and Gold layer pipelines
        </p>
      </div>
      <ChatContainer />
    </div>
  );
}
