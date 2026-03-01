"""Tests for RAG chat, history, index rebuild, and index status endpoints."""

BASE = "/api/v1/rag"


class TestChat:
    def test_chat_basic(self, client, mock_rag):
        resp = client.post(f"{BASE}/chat", json={"question": "What is bronze framework?"})
        assert resp.status_code == 200
        data = resp.json()
        assert "answer" in data
        assert "query_type" in data
        assert "session_id" in data
        assert "sources_used" in data

    def test_chat_answer_from_mock(self, client, mock_rag):
        resp = client.post(f"{BASE}/chat", json={"question": "How does SCD2 work?"})
        assert resp.status_code == 200
        assert resp.json()["answer"] == "The framework uses Delta Lake for storage."

    def test_chat_generates_session_id(self, client):
        resp = client.post(f"{BASE}/chat", json={"question": "Tell me about pipelines"})
        assert resp.status_code == 200
        assert len(resp.json()["session_id"]) > 0

    def test_chat_with_session_id(self, client, mock_rag):
        resp = client.post(f"{BASE}/chat", json={
            "question": "What sources exist?",
            "session_id": "my-session-123",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["session_id"] == "my-session-123"

    def test_chat_empty_question_rejected(self, client):
        resp = client.post(f"{BASE}/chat", json={"question": ""})
        assert resp.status_code == 422

    def test_chat_single_char_question(self, client):
        resp = client.post(f"{BASE}/chat", json={"question": "?"})
        assert resp.status_code == 200

    def test_chat_exactly_2000_chars(self, client):
        question = "x" * 2000
        resp = client.post(f"{BASE}/chat", json={"question": question})
        assert resp.status_code == 200

    def test_chat_2001_chars_rejected(self, client):
        question = "x" * 2001
        resp = client.post(f"{BASE}/chat", json={"question": question})
        assert resp.status_code == 422

    def test_chat_special_chars(self, client):
        resp = client.post(f"{BASE}/chat", json={"question": "What's SELECT * FROM sources?"})
        assert resp.status_code == 200

    def test_chat_unicode_question(self, client):
        resp = client.post(f"{BASE}/chat", json={"question": "Comment créer une source?"})
        assert resp.status_code == 200

    def test_chat_missing_question_field(self, client):
        resp = client.post(f"{BASE}/chat", json={"session_id": "abc"})
        assert resp.status_code == 422

    def test_chat_rag_service_called(self, client, mock_rag):
        client.post(f"{BASE}/chat", json={"question": "Hello"})
        mock_rag.answer.assert_called_once()
        call_kwargs = mock_rag.answer.call_args
        assert call_kwargs.kwargs["question"] == "Hello"

    def test_chat_no_api_key_dev_mode(self, client):
        # rag_require_auth is False (set in isolate_settings), so no key needed
        resp = client.post(f"{BASE}/chat", json={"question": "hi"})
        assert resp.status_code == 200

    def test_chat_invalid_api_key_returns_401(self, client, monkeypatch):
        from app.config import settings
        monkeypatch.setattr(settings, "rag_require_auth", True)
        resp = client.post(
            f"{BASE}/chat",
            json={"question": "hi"},
            headers={"X-API-Key": "invalid-key-999"},
        )
        assert resp.status_code == 401

    def test_chat_missing_key_auth_required_returns_401(self, client, monkeypatch):
        from app.config import settings
        monkeypatch.setattr(settings, "rag_require_auth", True)
        resp = client.post(f"{BASE}/chat", json={"question": "hi"})
        assert resp.status_code == 401


class TestChatHistory:
    def test_history_empty_for_new_session(self, client):
        resp = client.get(f"{BASE}/chat/history?session_id=brand-new-session")
        assert resp.status_code == 200
        data = resp.json()
        assert data["session_id"] == "brand-new-session"
        assert data["messages"] == []

    def test_history_after_chat(self, client, mock_tenant):
        session_id = "test-session-abc"
        mock_tenant.save_chat_message(
            tenant_id="default",
            role="user",
            content="Hello",
            session_id=session_id,
        )
        mock_tenant.save_chat_message(
            tenant_id="default",
            role="assistant",
            content="Hello! How can I help?",
            session_id=session_id,
        )
        resp = client.get(f"{BASE}/chat/history?session_id={session_id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["session_id"] == session_id
        assert len(data["messages"]) == 2

    def test_history_missing_session_id(self, client):
        # session_id is required query param
        resp = client.get(f"{BASE}/chat/history")
        assert resp.status_code == 422

    def test_history_structure(self, client, mock_tenant):
        session_id = "struct-test"
        mock_tenant.save_chat_message("default", "user", "test q", session_id)
        resp = client.get(f"{BASE}/chat/history?session_id={session_id}")
        assert resp.status_code == 200
        messages = resp.json()["messages"]
        assert len(messages) == 1
        msg = messages[0]
        assert "role" in msg
        assert "content" in msg
        assert msg["role"] == "user"
        assert msg["content"] == "test q"


class TestIndexRebuild:
    def test_rebuild_index_success(self, client, mock_rag):
        resp = client.post(f"{BASE}/index/rebuild")
        assert resp.status_code == 200
        data = resp.json()
        assert data["shared_docs_indexed"] == 5
        assert data["source_configs_indexed"] == 2
        assert data["message"] == "Index rebuilt successfully"

    def test_rebuild_calls_build_index(self, client, mock_rag):
        client.post(f"{BASE}/index/rebuild")
        mock_rag.build_index.assert_called_once()

    def test_rebuild_no_auth_in_dev_mode(self, client):
        resp = client.post(f"{BASE}/index/rebuild")
        assert resp.status_code == 200


class TestIndexStatus:
    def test_index_status_success(self, client, mock_embedding):
        resp = client.get(f"{BASE}/index/status")
        assert resp.status_code == 200
        data = resp.json()
        assert data["shared_doc_chunks"] == 10
        assert data["tenant_source_chunks"] == 3

    def test_index_status_structure(self, client):
        resp = client.get(f"{BASE}/index/status")
        assert resp.status_code == 200
        data = resp.json()
        assert "shared_doc_chunks" in data
        assert "tenant_source_chunks" in data
