"""Create generation, revision, and import audit tables."""

from alembic import op

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE import_runs (
            id uuid PRIMARY KEY,
            filename text NOT NULL,
            checksum text,
            policy_version text NOT NULL,
            start_date date NOT NULL,
            end_date date NOT NULL,
            status text NOT NULL CHECK (status IN ('running','succeeded','no_change','failed')),
            started_at timestamptz NOT NULL DEFAULT now(),
            finished_at timestamptz,
            source_rows integer NOT NULL DEFAULT 0,
            measurement_records integer NOT NULL DEFAULT 0,
            inserted_count integer NOT NULL DEFAULT 0,
            updated_count integer NOT NULL DEFAULT 0,
            preserved_count integer NOT NULL DEFAULT 0,
            missing_count integer NOT NULL DEFAULT 0,
            warnings jsonb NOT NULL DEFAULT '[]'::jsonb,
            error text,
            CHECK (end_date > start_date)
        )
    """)
    op.execute("""
        CREATE TABLE generation_intervals (
            source text NOT NULL CHECK (source IN
                ('biomass','hydropower','wind_offshore','wind_onshore',
                 'photovoltaics','other_renewable')),
            interval_start_utc timestamptz NOT NULL,
            interval_end_utc timestamptz NOT NULL,
            energy_mwh numeric,
            import_run_id uuid NOT NULL REFERENCES import_runs(id),
            source_row integer NOT NULL CHECK (source_row >= 2),
            start_label text NOT NULL,
            end_label text NOT NULL,
            revision_number integer NOT NULL DEFAULT 1,
            PRIMARY KEY (source, interval_start_utc),
            CHECK (interval_end_utc - interval_start_utc = interval '15 minutes')
        )
    """)
    op.execute("CREATE INDEX generation_time_idx ON generation_intervals(interval_start_utc)")
    op.execute("""
        CREATE TABLE observation_revisions (
            id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            source text NOT NULL,
            interval_start_utc timestamptz NOT NULL,
            previous_energy_mwh numeric,
            previous_import_run_id uuid NOT NULL REFERENCES import_runs(id),
            previous_source_row integer NOT NULL,
            previous_start_label text NOT NULL,
            previous_end_label text NOT NULL,
            previous_revision_number integer NOT NULL,
            replacement_import_run_id uuid NOT NULL REFERENCES import_runs(id),
            changed_at timestamptz NOT NULL DEFAULT now()
        )
    """)


def downgrade() -> None:
    op.drop_table("observation_revisions")
    op.drop_table("generation_intervals")
    op.drop_table("import_runs")
