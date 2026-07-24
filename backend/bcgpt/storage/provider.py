"""Storage provider abstraction for BCGPT WebUI.

Implements a pluggable file storage backend supporting local filesystem,
AWS S3, Google Cloud Storage, and Azure Blob Storage.  Each provider
conforms to the :class:`StorageProvider` ABC so they can be used
interchangeably via :func:`get_storage_provider`.
"""

import json
import logging
import os
import shutil
from abc import ABC, abstractmethod
from typing import BinaryIO, Tuple

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError

from google.cloud import storage
from google.cloud.exceptions import GoogleCloudError, NotFound

from azure.identity import DefaultAzureCredential
from azure.storage.blob import BlobServiceClient
from azure.core.exceptions import ResourceNotFoundError

from bcgpt.config import (
    AZURE_STORAGE_CONTAINER_NAME,
    AZURE_STORAGE_ENDPOINT,
    AZURE_STORAGE_KEY,
    GCS_BUCKET_NAME,
    GOOGLE_APPLICATION_CREDENTIALS_JSON,
    S3_ACCESS_KEY_ID,
    S3_ADDRESSING_STYLE,
    S3_BUCKET_NAME,
    S3_ENDPOINT_URL,
    S3_KEY_PREFIX,
    S3_REGION_NAME,
    S3_SECRET_ACCESS_KEY,
    S3_USE_ACCELERATE_ENDPOINT,
    STORAGE_PROVIDER,
    UPLOAD_DIR,
)
from bcgpt.constants import ERROR_MESSAGES
from bcgpt.env import SRC_LOG_LEVELS

log = logging.getLogger(__name__)
log.setLevel(SRC_LOG_LEVELS["MAIN"])


class StorageProvider(ABC):
    """Abstract base class defining the storage provider interface.

    All concrete storage backends must implement these four methods.
    """

    @abstractmethod
    def get_file(self, file_path: str) -> str:
        """Retrieve a file and return its local filesystem path."""
        ...

    @abstractmethod
    def upload_file(self, file: BinaryIO, filename: str) -> Tuple[bytes, str]:
        """Upload a file-like object.

        Returns:
            A tuple of ``(file_contents_bytes, storage_path)``.
        """
        ...

    @abstractmethod
    def delete_all_files(self) -> None:
        """Delete all stored files."""
        ...

    @abstractmethod
    def delete_file(self, file_path: str) -> None:
        """Delete a single file by its storage path."""
        ...


class LocalStorageProvider(StorageProvider):
    """Storage backend that writes files to the local ``UPLOAD_DIR``."""

    @staticmethod
    def upload_file(file: BinaryIO, filename: str) -> Tuple[bytes, str]:
        """Write *file* to ``UPLOAD_DIR/<filename>`` and return its contents."""
        contents = file.read()
        if not contents:
            raise ValueError(ERROR_MESSAGES.EMPTY_CONTENT)
        file_path = f"{UPLOAD_DIR}/{filename}"
        with open(file_path, "wb") as f:
            f.write(contents)
        return contents, file_path

    @staticmethod
    def get_file(file_path: str) -> str:
        """Return the local file path unchanged."""
        return file_path

    @staticmethod
    def delete_file(file_path: str) -> None:
        """Delete a single file from local storage."""
        filename = file_path.split("/")[-1]
        full_path = f"{UPLOAD_DIR}/{filename}"
        if os.path.isfile(full_path):
            os.remove(full_path)
        else:
            log.warning(f"File {full_path} not found in local storage.")

    @staticmethod
    def delete_all_files() -> None:
        """Delete every file and subdirectory inside ``UPLOAD_DIR``."""
        if os.path.exists(UPLOAD_DIR):
            for filename in os.listdir(UPLOAD_DIR):
                file_path = os.path.join(UPLOAD_DIR, filename)
                try:
                    if os.path.isfile(file_path) or os.path.islink(file_path):
                        os.unlink(file_path)
                    elif os.path.isdir(file_path):
                        shutil.rmtree(file_path)
                except Exception as e:
                    log.exception(f"Failed to delete {file_path}. Reason: {e}")
        else:
            log.warning(f"Directory {UPLOAD_DIR} not found in local storage.")


class S3StorageProvider(StorageProvider):
    """Storage backend backed by an S3-compatible object store.

    Files are first written to local storage, then uploaded to S3.
    Downloaded files are pulled from S3 into the local ``UPLOAD_DIR``.
    """

    def __init__(self) -> None:
        config = Config(
            s3={
                "use_accelerate_endpoint": S3_USE_ACCELERATE_ENDPOINT,
                "addressing_style": S3_ADDRESSING_STYLE,
            },
        )

        # Prefer explicit credentials when available; otherwise fall back to
        # the default AWS credential chain (IAM roles, instance profiles, etc.)
        if S3_ACCESS_KEY_ID and S3_SECRET_ACCESS_KEY:
            self.s3_client = boto3.client(
                "s3",
                region_name=S3_REGION_NAME,
                endpoint_url=S3_ENDPOINT_URL,
                aws_access_key_id=S3_ACCESS_KEY_ID,
                aws_secret_access_key=S3_SECRET_ACCESS_KEY,
                config=config,
            )
        else:
            self.s3_client = boto3.client(
                "s3",
                region_name=S3_REGION_NAME,
                endpoint_url=S3_ENDPOINT_URL,
                config=config,
            )

        self.bucket_name: str = S3_BUCKET_NAME
        self.key_prefix: str = S3_KEY_PREFIX if S3_KEY_PREFIX else ""

    def upload_file(self, file: BinaryIO, filename: str) -> Tuple[bytes, str]:
        """Upload *file* to S3 via the local staging directory."""
        _, file_path = LocalStorageProvider.upload_file(file, filename)
        try:
            s3_key = os.path.join(self.key_prefix, filename)
            self.s3_client.upload_file(file_path, self.bucket_name, s3_key)
            return (
                open(file_path, "rb").read(),
                "s3://" + self.bucket_name + "/" + s3_key,
            )
        except ClientError as e:
            raise RuntimeError(f"Error uploading file to S3: {e}")

    def get_file(self, file_path: str) -> str:
        """Download a file from S3 to the local staging directory."""
        try:
            s3_key = self._extract_s3_key(file_path)
            local_file_path = self._get_local_file_path(s3_key)
            self.s3_client.download_file(self.bucket_name, s3_key, local_file_path)
            return local_file_path
        except ClientError as e:
            raise RuntimeError(f"Error downloading file from S3: {e}")

    def delete_file(self, file_path: str) -> None:
        """Delete a file from both S3 and local storage."""
        try:
            s3_key = self._extract_s3_key(file_path)
            self.s3_client.delete_object(Bucket=self.bucket_name, Key=s3_key)
        except ClientError as e:
            raise RuntimeError(f"Error deleting file from S3: {e}")

        LocalStorageProvider.delete_file(file_path)

    def delete_all_files(self) -> None:
        """Delete all objects under *key_prefix* from S3, then clear local."""
        try:
            response = self.s3_client.list_objects_v2(Bucket=self.bucket_name)
            if "Contents" in response:
                for content in response["Contents"]:
                    if not content["Key"].startswith(self.key_prefix):
                        continue
                    self.s3_client.delete_object(
                        Bucket=self.bucket_name, Key=content["Key"]
                    )
        except ClientError as e:
            raise RuntimeError(f"Error deleting all files from S3: {e}")

        LocalStorageProvider.delete_all_files()

    def _extract_s3_key(self, full_file_path: str) -> str:
        """Parse the S3 object key from a full ``s3://`` URI."""
        return "/".join(full_file_path.split("//")[1].split("/")[1:])

    def _get_local_file_path(self, s3_key: str) -> str:
        """Derive the local staging path from an S3 key."""
        return f"{UPLOAD_DIR}/{s3_key.split('/')[-1]}"


class GCSStorageProvider(StorageProvider):
    """Storage backend backed by Google Cloud Storage."""

    def __init__(self) -> None:
        self.bucket_name: str = GCS_BUCKET_NAME

        if GOOGLE_APPLICATION_CREDENTIALS_JSON:
            self.gcs_client = storage.Client.from_service_account_info(
                info=json.loads(GOOGLE_APPLICATION_CREDENTIALS_JSON)
            )
        else:
            # Fall back to Application Default Credentials (metadata server,
            # user credentials, etc.)
            self.gcs_client = storage.Client()
        self.bucket = self.gcs_client.bucket(GCS_BUCKET_NAME)

    def upload_file(self, file: BinaryIO, filename: str) -> Tuple[bytes, str]:
        """Upload *file* to GCS via the local staging directory."""
        contents, file_path = LocalStorageProvider.upload_file(file, filename)
        try:
            blob = self.bucket.blob(filename)
            blob.upload_from_filename(file_path)
            return contents, "gs://" + self.bucket_name + "/" + filename
        except GoogleCloudError as e:
            raise RuntimeError(f"Error uploading file to GCS: {e}")

    def get_file(self, file_path: str) -> str:
        """Download a file from GCS to the local staging directory."""
        try:
            filename = file_path.removeprefix("gs://").split("/")[1]
            local_file_path = f"{UPLOAD_DIR}/{filename}"
            blob = self.bucket.get_blob(filename)
            blob.download_to_filename(local_file_path)
            return local_file_path
        except NotFound as e:
            raise RuntimeError(f"Error downloading file from GCS: {e}")

    def delete_file(self, file_path: str) -> None:
        """Delete a file from both GCS and local storage."""
        try:
            filename = file_path.removeprefix("gs://").split("/")[1]
            blob = self.bucket.get_blob(filename)
            blob.delete()
        except NotFound as e:
            raise RuntimeError(f"Error deleting file from GCS: {e}")

        LocalStorageProvider.delete_file(file_path)

    def delete_all_files(self) -> None:
        """Delete all blobs in the bucket, then clear local storage."""
        try:
            for blob in self.bucket.list_blobs():
                blob.delete()
        except NotFound as e:
            raise RuntimeError(f"Error deleting all files from GCS: {e}")

        LocalStorageProvider.delete_all_files()


class AzureStorageProvider(StorageProvider):
    """Storage backend backed by Azure Blob Storage."""

    def __init__(self) -> None:
        self.endpoint: str = AZURE_STORAGE_ENDPOINT
        self.container_name: str = AZURE_STORAGE_CONTAINER_NAME
        storage_key: str | None = AZURE_STORAGE_KEY

        if storage_key:
            self.blob_service_client = BlobServiceClient(
                account_url=self.endpoint, credential=storage_key
            )
        else:
            # Use DefaultAzureCredential for Managed Identity or other
            # environment-based authentication.
            self.blob_service_client = BlobServiceClient(
                account_url=self.endpoint, credential=DefaultAzureCredential()
            )
        self.container_client = self.blob_service_client.get_container_client(
            self.container_name
        )

    def upload_file(self, file: BinaryIO, filename: str) -> Tuple[bytes, str]:
        """Upload *file* to Azure Blob Storage via local staging."""
        contents, file_path = LocalStorageProvider.upload_file(file, filename)
        try:
            blob_client = self.container_client.get_blob_client(filename)
            blob_client.upload_blob(contents, overwrite=True)
            return contents, f"{self.endpoint}/{self.container_name}/{filename}"
        except Exception as e:
            raise RuntimeError(f"Error uploading file to Azure Blob Storage: {e}")

    def get_file(self, file_path: str) -> str:
        """Download a blob from Azure to the local staging directory."""
        try:
            filename = file_path.split("/")[-1]
            local_file_path = f"{UPLOAD_DIR}/{filename}"
            blob_client = self.container_client.get_blob_client(filename)
            with open(local_file_path, "wb") as download_file:
                download_file.write(blob_client.download_blob().readall())
            return local_file_path
        except ResourceNotFoundError as e:
            raise RuntimeError(f"Error downloading file from Azure Blob Storage: {e}")

    def delete_file(self, file_path: str) -> None:
        """Delete a blob from Azure and remove the local copy."""
        try:
            filename = file_path.split("/")[-1]
            blob_client = self.container_client.get_blob_client(filename)
            blob_client.delete_blob()
        except ResourceNotFoundError as e:
            raise RuntimeError(f"Error deleting file from Azure Blob Storage: {e}")

        LocalStorageProvider.delete_file(file_path)

    def delete_all_files(self) -> None:
        """Delete all blobs in the container, then clear local storage."""
        try:
            for blob in self.container_client.list_blobs():
                self.container_client.delete_blob(blob.name)
        except Exception as e:
            raise RuntimeError(f"Error deleting all files from Azure Blob Storage: {e}")

        LocalStorageProvider.delete_all_files()


def get_storage_provider(storage_provider: str) -> StorageProvider:
    """Instantiate and return the requested storage backend.

    Args:
        storage_provider: One of ``"local"``, ``"s3"``, ``"gcs"``, or ``"azure"``.

    Returns:
        A concrete :class:`StorageProvider` instance.

    Raises:
        RuntimeError: If *storage_provider* is not recognised.
    """
    providers = {
        "local": LocalStorageProvider,
        "s3": S3StorageProvider,
        "gcs": GCSStorageProvider,
        "azure": AzureStorageProvider,
    }
    cls = providers.get(storage_provider)
    if cls is None:
        raise RuntimeError(f"Unsupported storage provider: {storage_provider}")
    return cls()


# Module-level singleton used across the application.
Storage: StorageProvider = get_storage_provider(STORAGE_PROVIDER)
