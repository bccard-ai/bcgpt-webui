"""Alembic migration environment configuration.

Configures the Alembic migration runner with the BCGPT SQLAlchemy metadata,
database URL, and online/offline execution strategies.
"""

from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from bcgpt.env import DATABASE_URL
from bcgpt.models import Auth

# Import models with their own tables so they register on Auth.metadata for
# autogenerate / metadata-aware operations.
from bcgpt.models.token_usage import LLMTokenUsage, ModelPricing  # noqa: F401
from bcgpt.models.user_mfa import UserMFA  # noqa: F401
from bcgpt.models.knowledge_graph import KnowledgeGraphStore  # noqa: F401
from bcgpt.models.chat_generations import ChatGeneration  # noqa: F401
from bcgpt.models.chats import ChatSearchMessage  # noqa: F401

from bcgpt.compliance.models.ai_inventory import AIModelInventory  # noqa: F401
from bcgpt.compliance.models.aiia import AIIARecord  # noqa: F401
from bcgpt.compliance.models.incident import AIIncident  # noqa: F401
from bcgpt.compliance.models.fairness_test import AIFairnessTest  # noqa: F401
from bcgpt.compliance.models.provenance import AIRAGProvenance  # noqa: F401
from bcgpt.compliance.models.vendor import AIVendor  # noqa: F401
from bcgpt.compliance.models.dsar import AIDSARRequest  # noqa: F401

from bcgpt.compliance.hitl.models import ApprovalTicket  # noqa: F401

# Alembic Config object — provides access to values in alembic.ini.
config = context.config

# Set up Python logging from the Alembic config file (if present).
if config.config_file_name is not None:
    fileConfig(config.config_file_name, disable_existing_loggers=False)

# SQLAlchemy metadata for autogenerate support.
target_metadata = Auth.metadata

# Override the database URL from the application environment.
DB_URL = DATABASE_URL
if DB_URL:
    config.set_main_option("sqlalchemy.url", DB_URL.replace("%", "%%"))


def run_migrations_offline() -> None:
    """Run migrations in offline mode.

    Configures the context with just a URL and no Engine, so no DBAPI
    is required.  Calls to ``context.execute()`` emit SQL to the script
    output.
    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in online mode.

    Creates an Engine and associates a connection with the Alembic context.
    Uses ``NullPool`` to avoid pool-related side-effects during migrations.
    """
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
