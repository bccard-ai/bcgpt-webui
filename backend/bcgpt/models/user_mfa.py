"""Multi-factor authentication (TOTP) persistence + verification.

open-moai adoption 2.5. Stores a per-user TOTP secret and hashed single-use
backup codes, and gates sign-in when MFA is enabled. PostgreSQL-compatible.

Security notes:
  * The TOTP secret is stored as base32 plaintext (standard for TOTP; rotate by
    re-enrolling). Backup codes are stored as SHA-256 hashes and consumed on use.
  * ``verify_code`` accepts either a current TOTP code (±1 step drift) or an
    unused backup code (which is then consumed).
"""

import hashlib
import logging
import secrets
import time
from typing import Optional

import pyotp
from pydantic import BaseModel, ConfigDict
from sqlalchemy import BigInteger, Boolean, Column, JSON, String

from bcgpt.internal import Base, get_db
from bcgpt.env import SRC_LOG_LEVELS

log = logging.getLogger(__name__)
log.setLevel(SRC_LOG_LEVELS["MODELS"])

ISSUER_NAME = "bcgpt"
_BACKUP_CODE_COUNT = 10
# Bytes of entropy per backup code. 6 bytes = 48 bits (hex-encoded to 12 chars).
# Previously 4 bytes (32 bits) -- 48 bits makes online guessing infeasible even
# without relying solely on the account-lockout that guards the login path.
_BACKUP_CODE_BYTES = 6


def _hash_code(code: str) -> str:
    return hashlib.sha256(code.strip().encode("utf-8")).hexdigest()


def _generate_backup_codes(count: int = _BACKUP_CODE_COUNT) -> list[str]:
    """Generate ``count`` random single-use backup codes (hex).

    Each code carries ``2 * _BACKUP_CODE_BYTES`` hex chars (48 bits of entropy
    at the default). Codes are returned in plaintext exactly once (to show the
    user) and persisted only as SHA-256 hashes (see :func:`_hash_code`); each is
    consumed on first use (see :meth:`UserMFATable.verify_code`).
    """
    return [secrets.token_hex(_BACKUP_CODE_BYTES) for _ in range(count)]


############################
# DB Schema
############################


class UserMFA(Base):
    __tablename__ = "user_mfa"

    user_id = Column(String, primary_key=True)
    secret = Column(String, nullable=True)
    enabled = Column(Boolean, default=False)
    backup_codes = Column(JSON, nullable=True)  # list[str] of SHA-256 hashes
    created_at = Column(BigInteger, nullable=False)
    updated_at = Column(BigInteger, nullable=False)


class UserMFAModel(BaseModel):
    user_id: str
    secret: Optional[str] = None
    enabled: bool = False
    backup_codes: Optional[list] = None
    created_at: int
    updated_at: int

    model_config = ConfigDict(from_attributes=True)


############################
# CRUD
############################


class UserMFATable:
    def get(self, user_id: str) -> Optional[UserMFAModel]:
        try:
            with get_db() as db:
                row = db.query(UserMFA).filter_by(user_id=user_id).first()
                return UserMFAModel.model_validate(row) if row else None
        except Exception as e:
            log.exception("UserMFA.get failed: %s", e)
            return None

    def is_enabled(self, user_id: str) -> bool:
        row = self.get(user_id)
        return bool(row and row.enabled and row.secret)

    def start_enrollment(self, user_id: str, user_email: str) -> Optional[dict]:
        """Create (or reset) a not-yet-enabled TOTP secret. Returns the secret and
        the otpauth:// provisioning URI for QR rendering. Does NOT enable MFA."""
        try:
            secret = pyotp.random_base32()
            uri = pyotp.TOTP(secret).provisioning_uri(
                name=user_email or user_id, issuer_name=ISSUER_NAME
            )
            now = int(time.time() * 1000)
            with get_db() as db:
                row = db.query(UserMFA).filter_by(user_id=user_id).first()
                if row:
                    row.secret = secret
                    row.enabled = False
                    row.backup_codes = None
                    row.updated_at = now
                else:
                    row = UserMFA(
                        user_id=user_id,
                        secret=secret,
                        enabled=False,
                        backup_codes=None,
                        created_at=now,
                        updated_at=now,
                    )
                    db.add(row)
                db.commit()
            return {"secret": secret, "provisioning_uri": uri, "issuer": ISSUER_NAME}
        except Exception as e:
            log.exception("UserMFA.start_enrollment failed: %s", e)
            return None

    def verify_and_enable(self, user_id: str, code: str) -> Optional[dict]:
        """Verify the enrollment TOTP code; on success enable MFA and return a
        fresh set of plaintext backup codes (shown once). None on failure."""
        try:
            with get_db() as db:
                row = db.query(UserMFA).filter_by(user_id=user_id).first()
                if not row or not row.secret:
                    return None
                if not pyotp.TOTP(row.secret).verify(
                    (code or "").strip(), valid_window=1
                ):
                    return None
                plain = _generate_backup_codes()
                row.backup_codes = [_hash_code(c) for c in plain]
                row.enabled = True
                row.updated_at = int(time.time() * 1000)
                db.commit()
            return {"backup_codes": plain}
        except Exception as e:
            log.exception("UserMFA.verify_and_enable failed: %s", e)
            return None

    def verify_code(self, user_id: str, code: str) -> bool:
        """Verify a login code: a current TOTP code OR an unused backup code
        (which is consumed). Returns True on success."""
        code = (code or "").strip()
        if not code:
            return False
        try:
            with get_db() as db:
                row = db.query(UserMFA).filter_by(user_id=user_id).first()
                if not row or not row.enabled or not row.secret:
                    return False
                if pyotp.TOTP(row.secret).verify(code, valid_window=1):
                    return True
                # Backup-code fallback (single-use).
                hashed = _hash_code(code)
                codes = list(row.backup_codes or [])
                if hashed in codes:
                    codes.remove(hashed)
                    row.backup_codes = codes
                    row.updated_at = int(time.time() * 1000)
                    db.commit()
                    return True
                return False
        except Exception as e:
            log.exception("UserMFA.verify_code failed: %s", e)
            return False

    def disable(self, user_id: str) -> bool:
        try:
            with get_db() as db:
                db.query(UserMFA).filter_by(user_id=user_id).delete()
                db.commit()
            return True
        except Exception as e:
            log.exception("UserMFA.disable failed: %s", e)
            return False

    def backup_codes_remaining(self, user_id: str) -> int:
        row = self.get(user_id)
        return len(row.backup_codes or []) if row else 0


UserMFAs = UserMFATable()
