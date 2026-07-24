"""Add compliance tables

Revision ID: f1a2b3c4d5e6
Revises: d3e4f5a6b7c8
Create Date: 2026-06-17 00:00:03.000000
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "f1a2b3c4d5e6"
down_revision = "d3e4f5a6b7c8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "ai_model_inventory",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("model_id", sa.String(), nullable=True),
        sa.Column("provider", sa.String(), nullable=True),
        sa.Column("display_name", sa.String(), nullable=True),
        sa.Column("version", sa.String(), nullable=True),
        sa.Column("risk_tier", sa.String(), nullable=True),
        sa.Column("is_high_impact", sa.Boolean(), nullable=True, default=False),
        sa.Column("high_impact_domain", sa.String(), nullable=True),
        sa.Column("business_owner_id", sa.String(), nullable=True),
        sa.Column("data_classification", sa.String(), nullable=True),
        sa.Column("intended_use", sa.Text(), nullable=True),
        sa.Column("out_of_scope_use", sa.Text(), nullable=True),
        sa.Column("validation_status", sa.String(), nullable=True, default="draft"),
        sa.Column("approved_at", sa.BigInteger(), nullable=True),
        sa.Column("approved_by", sa.String(), nullable=True),
        sa.Column("model_card_md", sa.Text(), nullable=True),
        sa.Column("license_info", sa.String(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=True, default=True),
        sa.Column("created_at", sa.BigInteger(), nullable=False),
        sa.Column("updated_at", sa.BigInteger(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_ai_model_inventory_model_id", "ai_model_inventory", ["model_id"]
    )
    op.create_index(
        "ix_ai_model_inventory_risk_tier", "ai_model_inventory", ["risk_tier"]
    )
    op.create_index(
        "ix_ai_model_inventory_business_owner_id",
        "ai_model_inventory",
        ["business_owner_id"],
    )

    op.create_table(
        "aiia_record",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("inventory_id", sa.String(), nullable=False),
        sa.Column("assessor_id", sa.String(), nullable=False),
        sa.Column("assessment_version", sa.String(), nullable=True, default="1.0"),
        sa.Column("status", sa.String(), nullable=True, default="draft"),
        sa.Column("intended_purpose", sa.Text(), nullable=True),
        sa.Column("user_population", sa.Text(), nullable=True),
        sa.Column("high_impact_domain", sa.String(), nullable=True),
        sa.Column("risk_scenarios", sa.JSON(), nullable=True),
        sa.Column("mitigation_measures", sa.JSON(), nullable=True),
        sa.Column("residual_risk", sa.String(), nullable=True),
        sa.Column("next_review_date", sa.BigInteger(), nullable=True),
        sa.Column("review_notes", sa.Text(), nullable=True),
        sa.Column("approved_at", sa.BigInteger(), nullable=True),
        sa.Column("approved_by", sa.String(), nullable=True),
        sa.Column("created_at", sa.BigInteger(), nullable=False),
        sa.Column("updated_at", sa.BigInteger(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_aiia_record_inventory_id", "aiia_record", ["inventory_id"])

    op.create_table(
        "ai_incident",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("severity", sa.String(), nullable=True, default="medium"),
        sa.Column("category", sa.String(), nullable=True),
        sa.Column("status", sa.String(), nullable=True, default="detected"),
        sa.Column("detected_at", sa.BigInteger(), nullable=False),
        sa.Column("detected_by", sa.String(), nullable=True),
        sa.Column("assigned_to", sa.String(), nullable=True),
        sa.Column("root_cause", sa.Text(), nullable=True),
        sa.Column("resolution", sa.Text(), nullable=True),
        sa.Column("timeline", sa.JSON(), nullable=True),
        sa.Column("reporting_regime", sa.String(), nullable=True),
        sa.Column("reporting_deadline", sa.BigInteger(), nullable=True),
        sa.Column("reported_at", sa.BigInteger(), nullable=True),
        sa.Column("report_reference", sa.String(), nullable=True),
        sa.Column("forensic_evidence", sa.JSON(), nullable=True),
        sa.Column("related_chat_id", sa.String(), nullable=True),
        sa.Column("related_user_id", sa.String(), nullable=True),
        sa.Column("created_at", sa.BigInteger(), nullable=False),
        sa.Column("updated_at", sa.BigInteger(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_ai_incident_severity", "ai_incident", ["severity"])
    op.create_index("ix_ai_incident_status", "ai_incident", ["status"])
    op.create_index("ix_ai_incident_detected_at", "ai_incident", ["detected_at"])
    op.create_index(
        "ix_ai_incident_related_chat_id", "ai_incident", ["related_chat_id"]
    )
    op.create_index(
        "ix_ai_incident_related_user_id", "ai_incident", ["related_user_id"]
    )

    op.create_table(
        "ai_fairness_test",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("test_name", sa.String(), nullable=False),
        sa.Column("model_id", sa.String(), nullable=True),
        sa.Column("test_config", sa.JSON(), nullable=True),
        sa.Column("status", sa.String(), nullable=True, default="pending"),
        sa.Column("started_at", sa.BigInteger(), nullable=True),
        sa.Column("completed_at", sa.BigInteger(), nullable=True),
        sa.Column("results", sa.JSON(), nullable=True),
        sa.Column("metrics_summary", sa.JSON(), nullable=True),
        sa.Column("threshold_passed", sa.Boolean(), nullable=True),
        sa.Column("created_by", sa.String(), nullable=True),
        sa.Column("created_at", sa.BigInteger(), nullable=False),
        sa.Column("updated_at", sa.BigInteger(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_ai_fairness_test_model_id", "ai_fairness_test", ["model_id"])

    op.create_table(
        "ai_rag_provenance",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("timestamp", sa.BigInteger(), nullable=False),
        sa.Column("user_id", sa.String(), nullable=True),
        sa.Column("model_name", sa.String(), nullable=True),
        sa.Column("model_version", sa.String(), nullable=True),
        sa.Column("prompt_hash", sa.String(), nullable=True),
        sa.Column("query_text", sa.Text(), nullable=True),
        sa.Column("retrieved_chunks", sa.JSON(), nullable=True),
        sa.Column("response_hash", sa.String(), nullable=True),
        sa.Column("response_text", sa.Text(), nullable=True),
        sa.Column("total_tokens", sa.Integer(), nullable=True, default=0),
        sa.Column("retention_until", sa.BigInteger(), nullable=True),
        sa.Column("signature", sa.String(), nullable=True),
        sa.Column("related_chat_id", sa.String(), nullable=True),
        sa.Column("created_at", sa.BigInteger(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_ai_rag_provenance_timestamp", "ai_rag_provenance", ["timestamp"]
    )
    op.create_index("ix_ai_rag_provenance_user_id", "ai_rag_provenance", ["user_id"])
    op.create_index(
        "ix_ai_rag_provenance_related_chat_id",
        "ai_rag_provenance",
        ["related_chat_id"],
    )

    op.create_table(
        "ai_vendor",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("vendor_name", sa.String(), nullable=False),
        sa.Column("service_type", sa.String(), nullable=True),
        sa.Column("contact_info", sa.JSON(), nullable=True),
        sa.Column("compliance_certifications", sa.JSON(), nullable=True),
        sa.Column(
            "data_processing_agreement", sa.Boolean(), nullable=True, default=False
        ),
        sa.Column("due_diligence_date", sa.BigInteger(), nullable=True),
        sa.Column("due_diligence_result", sa.Text(), nullable=True),
        sa.Column("risk_assessment", sa.String(), nullable=True),
        sa.Column("status", sa.String(), nullable=True, default="active"),
        sa.Column("exit_plan", sa.JSON(), nullable=True),
        sa.Column("related_inventory_ids", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.BigInteger(), nullable=False),
        sa.Column("updated_at", sa.BigInteger(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_ai_vendor_vendor_name", "ai_vendor", ["vendor_name"])

    op.create_table(
        "ai_dsar_request",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("request_type", sa.String(), nullable=False),
        sa.Column("user_id", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=True, default="pending"),
        sa.Column("requested_at", sa.BigInteger(), nullable=False),
        sa.Column("completed_at", sa.BigInteger(), nullable=True),
        sa.Column("export_url", sa.String(), nullable=True),
        sa.Column("export_expires_at", sa.BigInteger(), nullable=True),
        sa.Column("details", sa.JSON(), nullable=True),
        sa.Column("handled_by", sa.String(), nullable=True),
        sa.Column("rejection_reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.BigInteger(), nullable=False),
        sa.Column("updated_at", sa.BigInteger(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_ai_dsar_request_user_id", "ai_dsar_request", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_ai_dsar_request_user_id", table_name="ai_dsar_request")

    op.drop_index("ix_ai_vendor_vendor_name", table_name="ai_vendor")

    op.drop_index(
        "ix_ai_rag_provenance_related_chat_id", table_name="ai_rag_provenance"
    )
    op.drop_index("ix_ai_rag_provenance_user_id", table_name="ai_rag_provenance")
    op.drop_index("ix_ai_rag_provenance_timestamp", table_name="ai_rag_provenance")

    op.drop_index("ix_ai_fairness_test_model_id", table_name="ai_fairness_test")

    op.drop_index("ix_ai_incident_related_user_id", table_name="ai_incident")
    op.drop_index("ix_ai_incident_related_chat_id", table_name="ai_incident")
    op.drop_index("ix_ai_incident_detected_at", table_name="ai_incident")
    op.drop_index("ix_ai_incident_status", table_name="ai_incident")
    op.drop_index("ix_ai_incident_severity", table_name="ai_incident")

    op.drop_index("ix_aiia_record_inventory_id", table_name="aiia_record")

    op.drop_index(
        "ix_ai_model_inventory_business_owner_id", table_name="ai_model_inventory"
    )
    op.drop_index("ix_ai_model_inventory_risk_tier", table_name="ai_model_inventory")
    op.drop_index("ix_ai_model_inventory_model_id", table_name="ai_model_inventory")

    op.drop_table("ai_dsar_request")
    op.drop_table("ai_vendor")
    op.drop_table("ai_rag_provenance")
    op.drop_table("ai_fairness_test")
    op.drop_table("ai_incident")
    op.drop_table("aiia_record")
    op.drop_table("ai_model_inventory")
