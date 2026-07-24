from bcgpt.test.util.abstract_integration_test import AbstractPostgresTest
from bcgpt.test.util.mock_user import mock_app_user


class TestToolsCodeAuthoring(AbstractPostgresTest):
    """Regression for P0-5: tool code is exec()'d WITHOUT sandboxing
    (utils/plugin.py), so authoring it is RCE-equivalent. A non-admin must NOT
    be able to author tool code by default — even when granted the
    'workspace.tools' permission — unless TOOLS_ALLOW_NON_ADMIN_CODE is set.
    """

    BASE_PATH = "/api/v1/tools"

    def test_non_admin_with_permission_cannot_author_code_by_default(self, monkeypatch):
        import bcgpt.routers.tools as tools_router
        from bcgpt.models.tools import Tools

        # Pass the workspace.tools permission gate so we actually reach the
        # code-authoring guard, with the opt-in flag OFF (its default).
        monkeypatch.setattr(tools_router, "has_permission", lambda *a, **k: True)
        monkeypatch.setattr(tools_router, "TOOLS_ALLOW_NON_ADMIN_CODE", False)

        with mock_app_user(id="2", role="user"):
            response = self.fast_api_client.post(
                self.create_url("/create"),
                json={
                    "id": "evil_tool",
                    "name": "evil",
                    "content": "import os  # would run unsandboxed with process privileges",
                    "meta": {"description": "x"},
                },
            )

        assert response.status_code == 403
        # The tool must never have been created (guard runs before exec/insert).
        assert Tools.get_tool_by_id("evil_tool") is None
