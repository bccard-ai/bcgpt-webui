import uuid

from bcgpt.test.util.abstract_integration_test import AbstractPostgresTest
from bcgpt.test.util.mock_user import mock_app_user


class TestFilesAccessControl(AbstractPostgresTest):
    """Regression tests for P0-1: cross-user file IDOR.

    ``has_access_to_file()`` is an ``async def`` but was invoked WITHOUT
    ``await`` inside the access-control ``if (... or ...)`` expressions in
    routers/files.py. An un-awaited coroutine object is always truthy, so the
    ``or`` short-circuited to True and EVERY authenticated user could read /
    delete ANY file by id. These tests pin the fixed behaviour: a non-owner,
    non-admin user with no knowledge-base access must be denied (404).
    """

    BASE_PATH = "/api/v1/files"

    OWNER_ID = "2"
    ATTACKER_ID = "99"

    def setup_method(self):
        super().setup_method()
        from bcgpt.models.files import FileForm, Files

        self.files = Files
        # The integration harness truncates a fixed table list that does NOT
        # include "file", so use a fresh id per test to avoid PK collisions.
        self.FILE_ID = f"idor-{uuid.uuid4().hex}"
        self.files.insert_new_file(
            self.OWNER_ID,
            FileForm(
                id=self.FILE_ID,
                filename="secret.txt",
                path=f"/data/uploads/{self.FILE_ID}.txt",
                data={"content": "TOP SECRET — owner only"},
                meta={"name": "secret.txt"},
            ),
        )

    # --- positive control: the owner keeps access ---------------------------

    def test_owner_can_read_own_file_metadata(self):
        with mock_app_user(id=self.OWNER_ID, role="user"):
            response = self.fast_api_client.get(self.create_url(f"/{self.FILE_ID}"))
        assert response.status_code == 200
        assert response.json()["id"] == self.FILE_ID

    # --- regression: a different user must NOT reach another user's file ----

    def test_non_owner_cannot_read_file_metadata(self):
        with mock_app_user(id=self.ATTACKER_ID, role="user"):
            response = self.fast_api_client.get(self.create_url(f"/{self.FILE_ID}"))
        assert response.status_code == 404

    def test_non_owner_cannot_read_file_data_content(self):
        with mock_app_user(id=self.ATTACKER_ID, role="user"):
            response = self.fast_api_client.get(
                self.create_url(f"/{self.FILE_ID}/data/content")
            )
        assert response.status_code == 404

    def test_non_owner_cannot_delete_file(self):
        with mock_app_user(id=self.ATTACKER_ID, role="user"):
            response = self.fast_api_client.delete(self.create_url(f"/{self.FILE_ID}"))
        assert response.status_code == 404
        # the file must still exist — denial must not have side effects
        assert self.files.get_file_by_id(self.FILE_ID) is not None
