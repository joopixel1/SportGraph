import os
import logging
from functools import lru_cache

from dotenv import load_dotenv
from fastapi import Depends

from api.src.database.neo4j_connection_manager import Neo4jConnectionManager
from api.src.repository.neo4j_graph_repository import Neo4jGraphRepository
from api.src.service.soccer_service import SoccerService


load_dotenv()


logger = logging.getLogger(__name__)


# ============================================================
# 🔌 DATABASE CLIENT SETUP
# ============================================================


@lru_cache(maxsize=1)
def get_neo4j_connection_manager() -> Neo4jConnectionManager:
    """Create and return a Neo4j connection manager."""
    uri = os.environ["NEO4J_URI"]
    user = os.environ["NEO4J_USER"]
    password = os.environ["NEO4J_PASSWORD"]

    logger.info(f"Neo4j URI: {uri}, Neo4j User: {user}")
    return Neo4jConnectionManager(uri=uri, user=user, password=password)


# ============================================================
# 🏗️ REPOSITORY SETUP
# ============================================================


def get_neo4j_graph_repository(ncm: Neo4jConnectionManager = Depends(get_neo4j_connection_manager)) -> Neo4jGraphRepository:
    """Provide an Graph repository using the connection manager."""
    return Neo4jGraphRepository(ncm)


# ============================================================
# 🧩 SERVICE SETUP
# ============================================================


def get_soccer_service(ngr: Neo4jGraphRepository = Depends(get_neo4j_graph_repository)) -> SoccerService:
    """Provide an SoccerService using the Graph Repository."""
    return SoccerService(ngr)
