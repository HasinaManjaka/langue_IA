"""US156 leçons originales et corrigés privés du parcours de démonstration."""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20261118_us156_contenu_demo"
down_revision: str | None = "20261110_diag_analyse_ia"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "lecon",
        sa.Column("id_lecon", sa.Integer(), nullable=False),
        sa.Column("id_parcours", sa.Integer(), nullable=False),
        sa.Column("numero_lecon", sa.Integer(), nullable=False),
        sa.Column("titre", sa.Text(), nullable=False),
        sa.Column("texte_original", sa.Text(), nullable=False),
        sa.Column("id_niveau", sa.Integer(), nullable=False),
        sa.CheckConstraint("numero_lecon >= 1", name="ck_lecon_numero_positive"),
        sa.ForeignKeyConstraint(["id_niveau"], ["niveau.id_niveau"], name="fk_lecon_id_niveau"),
        sa.ForeignKeyConstraint(
            ["id_parcours"],
            ["parcours.id_parcours"],
            name="fk_lecon_id_parcours",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id_lecon"),
        sa.UniqueConstraint("id_parcours", "numero_lecon", name="uq_lecon_parcours_numero"),
    )
    op.add_column("exercice", sa.Column("intitule", sa.Text(), nullable=True))
    op.create_table(
        "corrige_exercice",
        sa.Column("id_corrige", sa.Integer(), nullable=False),
        sa.Column("id_exercice", sa.Integer(), nullable=False),
        sa.Column("reponse_attendue", sa.Text(), nullable=False),
        sa.Column("explication", sa.Text(), nullable=False),
        sa.Column(
            "mots_cles",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column("exemple_reponse", sa.Text(), nullable=False),
        sa.Column("conseil", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(
            ["id_exercice"],
            ["exercice.id_exercice"],
            name="fk_corrige_exercice_id_exercice",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id_corrige"),
        sa.UniqueConstraint("id_exercice", name="uq_corrige_exercice_id_exercice"),
    )


def downgrade() -> None:
    op.drop_table("corrige_exercice")
    op.drop_column("exercice", "intitule")
    op.drop_table("lecon")
