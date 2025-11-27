import logging
from typing import Any, Dict, List, Optional
from neo4j import AsyncGraphDatabase, AsyncDriver, NotificationDisabledCategory


class Neo4jConnectionManager:
    """
    Async Neo4j connection manager using the official async driver.

    Helper methods:
      • query_all   – return multiple records
      • query_one   – return a single record
      • query_none  – write-only (CREATE/MERGE/DELETE)
      • close_all   – close driver
    """

    def __init__(self, uri: str, user: str, password: str) -> None:
        self.logger: logging.Logger = logging.getLogger(__name__)
        try:
            self.driver: AsyncDriver = AsyncGraphDatabase.driver(
                uri,
                auth=(user, password),
                max_connection_lifetime=3600,
                max_connection_pool_size=10,
                notifications_min_severity="OFF",
            )
        except Exception as e:
            self.logger.error(f"Failed to initialize async Neo4j driver: {e}")
            self.driver = None

    # ----------------------------------------------------------------------
    async def verify_connection(self) -> None:
        """Ping Neo4j by running a lightweight test query."""
        if self.driver is None:
            raise ConnectionError("Neo4j driver is not initialized.")

        try:
            await self.driver.verify_connectivity()
        except Exception as e:
            raise ConnectionError(f"Neo4j not reachable: {e}")

    # ----------------------------------------------------------------------
    def get_session(self):
        """Return an async session."""
        if self.driver is None:
            raise ConnectionError("Neo4j driver is not initialized.")
        return self.driver.session()

    # ----------------------------------------------------------------------
    # Query helpers
    # ----------------------------------------------------------------------
    async def query_all(self, cypher: str, params: Dict[str, Any] | None = None) -> List[Dict[str, Any]]:
        """Execute a query and return all rows."""
        try:
            async with self.get_session() as session:
                result = await session.run(cypher, params or {})
                return [record.data() async for record in result]
        except Exception as e:
            self._log_db_error(e, cypher)
            raise

    async def query_one(self, cypher: str, params: Dict[str, Any] | None = None) -> Optional[Dict[str, Any]]:
        """Execute a query and return the first row (or None)."""
        try:
            async with self.get_session() as session:
                result = await session.run(cypher, params or {})
                record = await result.single()
                return record.data() if record else None
        except Exception as e:
            self._log_db_error(e, cypher)
            raise

    async def query_none(self, cypher: str, params: Dict[str, Any] | None = None) -> None:
        """Execute a write-only Cypher query."""
        try:
            async with self.get_session() as session:
                result = await session.run(cypher, params or {})
                await result.consume()
        except Exception as e:
            self._log_db_error(e, cypher)
            raise

    # ----------------------------------------------------------------------
    async def close_all(self) -> None:
        """Shut down the Neo4j driver."""
        if self.driver is not None:
            await self.driver.close()

    def _log_db_error(self, error: Exception, cypher: str) -> None:
        """Log database error with details."""
        self.logger.error(f"[Neo4j Async Error] {error}")
        self.logger.debug(f"Cypher: {cypher}")
