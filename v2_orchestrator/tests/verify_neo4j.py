"""CLI: Neo4j and E2E verification for the Latent Semantic Attractor Graph.

Run: NEO4J_DATABASE=ontologyv2 python -m v2_orchestrator.tests.verify_neo4j
     NEO4J_DATABASE=ontologyv2 python -m v2_orchestrator.tests.verify_neo4j --sync
"""

from __future__ import annotations

import argparse
import os
import sys

from v2_orchestrator.chunk_journal import ChunkJournal
from v2_orchestrator.settings import load_settings
from v2_orchestrator.storage import ConceptStore
from v2_orchestrator.verification import run_e2e_verification, sync_store_to_neo4j


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Latent Semantic Attractor Graph — Neo4j / E2E verification."
    )
    parser.add_argument(
        "--sync",
        action="store_true",
        help="Backfill Neo4j from disk state/journal before checks.",
    )
    args = parser.parse_args()

    os.environ.setdefault("NEO4J_DATABASE", load_settings().neo4j_database)
    settings = load_settings()
    store = ConceptStore.load()
    journal = ChunkJournal()

    if args.sync:
        sync_store_to_neo4j(settings, store, journal)

    errors = run_e2e_verification(settings, store, journal)
    if errors:
        sys.exit(1)


if __name__ == "__main__":
    main()
