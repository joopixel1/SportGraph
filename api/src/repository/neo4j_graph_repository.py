from typing import Optional, List, Dict, Any

from api.src.database.neo4j_connection_manager import Neo4jConnectionManager


class Neo4jGraphRepository:

    def __init__(self, ncm: Neo4jConnectionManager):
        self.ncm: Neo4jConnectionManager = ncm

    async def get_player_by_id(self, player_id: str) -> Optional[Dict[str, Any]]:
        row = await self.ncm.query_one(
            """
            MATCH (p:Player {id: $id})
            RETURN { id: p.id, name: p.name } AS player
            """,
            {"id": player_id},
        )
        return row.get("player") if row else None

    async def search_players(self, name: str) -> List[Dict[str, Any]]:
        rows = await self.ncm.query_all(
            """
            MATCH (p:Player)
            WITH 
                p,
                toLower(p.name) AS lo,
                toLower(replace(trim($name), ' ', '-')) AS normalized
            WHERE lo CONTAINS normalized
            OPTIONAL MATCH (p)-[r:PLAYED_FOR]->(:Club)
            WITH p, sum(r.appearances) AS apps
            RETURN
                p.id as id,
                p.name as name,
                apps AS appearances
            ORDER BY apps DESC, p.name
            LIMIT 25
            """,
            {"name": name},
        )
        return [{"id": row["id"], "name": row["name"], "appearances": row["appearances"]} for row in rows]

    async def get_player_club_history(self, player_id: str) -> List[Dict[str, Any]]:
        rows = await self.ncm.query_all(
            """
            MATCH (p:Player {id: $id})-[r:PLAYED_FOR]->(c:Club)
            RETURN 
                c.name AS club,
                r.start_year AS start,
                r.end_year AS end,
                r.appearances AS apps
            ORDER BY r.start_year
            """,
            {"id": player_id},
        )
        return [{"club": row["club"], "start": row["start"], "end": row["end"], "apps": row["apps"]} for row in rows]

    async def get_club_players(
        self,
        club_name: str,
        min_apps: Optional[int] = None,
        max_apps: Optional[int] = None,
        season_from: Optional[int] = None,
        season_to: Optional[int] = None,
        order_by: str = "appearances",
        order_dir: str = "desc",
    ) -> List[Dict[str, Any]]:

        allowed_order_by = {"name", "appearances", "first_season", "last_season"}
        allowed_order_dir = {"asc", "desc"}

        if order_by not in allowed_order_by:
            order_by = "appearances"

        if order_dir not in allowed_order_dir:
            order_dir = "desc"

        filters = ["c.name = $club_name"]
        params: Dict[str, Any] = {"club_name": club_name}

        if min_apps is not None:
            filters.append("apps >= $min_apps")
            params["min_apps"] = min_apps

        if max_apps is not None:
            filters.append("apps <= $max_apps")
            params["max_apps"] = max_apps

        if season_from is not None:
            filters.append("r.start_year >= $season_from")
            params["season_from"] = season_from

        if season_to is not None:
            filters.append("r.end_year <= $season_to")
            params["season_to"] = season_to

        where_clause = " AND ".join(filters)

        query = f"""
            MATCH (p:Player)-[r:PLAYED_FOR]->(c:Club)
            WHERE {where_clause}
            WITH p,
                 sum(r.appearances) AS appearances,
                 min(r.start_year) AS first_season,
                 max(r.end_year) AS last_season
            RETURN 
                p.id as id, 
                p.name as name,
                appearances,
                first_season,
                last_season
            ORDER BY {order_by} {order_dir}
        """

        rows = await self.ncm.query_all(query, params)
        return [
            {
                "id": row["id"],
                "name": row["name"],
                "appearances": row["appearances"],
                "first_season": row["first_season"],
                "last_season": row["last_season"],
            }
            for row in rows
        ]

    async def get_n_step_teammate_paths(self, steps: int = 2, limit: int = 10) -> List[Dict[str, Any]]:
        rows = await self.ncm.query_all(
            """
            MATCH (start:Player)
            CALL apoc.path.expandConfig(start, {
                relationshipFilter: "PLAYED_WITH>",
                minLevel: 2,
                maxLevel: 2,
                uniqueness: "NODE_GLOBAL",
                bfs: true,
                filterStartNode: true
            }) YIELD path

            WITH nodes(path) AS nds, relationships(path) AS rels
            WHERE size(rels) = 2
 
            // 1) Consecutive clubs must differ for all edges
            AND all(i IN range(0, size(rels) - 2) 
            WHERE rels[i].club <> rels[i + 1].club)

            // 2) No shortcuts between non-adjacent nodes
            AND all(i IN range(0, size(nds) - 3) WHERE
                all(j IN range(i + 2, size(nds) - 1) WHERE
                    NOT EXISTS {
                        WITH nds[i] AS ni, nds[j] AS nj
                        MATCH (ni)-[:PLAYED_WITH]-(nj)
                    }
                )
            )

            AND nds[0].id < nds[size(nds) - 1].id

            WITH nds, rels, reduce(w = 0, r IN rels | w + r.weight) AS total_weight

            RETURN {
                players: [x IN nds | { id: x.id, name: x.name }],
                clubs:   [r IN rels | r.club],
                totalWeight: total_weight
            } AS path
            ORDER BY total_weight * rand() DESC
            LIMIT $limit
            """,
            {"steps": steps, "limit": limit},
        )
        return [row["path"] for row in rows if row.get("path") is not None]

    async def get_options(self, a: str, b: str, c: str, limit: int) -> Optional[Dict[str, Any]]:
        row = await self.ncm.query_one(
            """
            MATCH (x:Player)
            WHERE x.id <> $a AND x.id <> $b AND x.id <> $c

            // XOR logic: x connects to exactly ONE of A or C
            WITH x,
                exists( (x)-[:PLAYED_WITH]-(:Player {id: $a}) ) AS toA,
                exists( (x)-[:PLAYED_WITH]-(:Player {id: $c}) ) AS toC
            WHERE toA <> toC

            ORDER BY rand()
            LIMIT $limit

            // Convert to list after limit
            WITH collect({ id: x.id, name: x.name }) AS distractors

            // B is the correct answer
            MATCH (bNode:Player {id: $b})
            WITH [{ id: bNode.id, name: bNode.name }] + distractors AS options

            // Shuffle final list
            RETURN apoc.coll.shuffle(options) AS options
            """,
            {"a": a, "b": b, "c": c, "limit": limit},
        )
        return row.get("options") if row else None

    async def get_shortest_teammate_path(self, player_a: str, player_b: str) -> Optional[Dict[str, Any]]:
        row = await self.ncm.query_one(
            """
            MATCH (a:Player {id: $a}), (b:Player {id: $b})
            MATCH path = shortestPath((a)-[:PLAYED_WITH*..10]-(b))
            WITH path,
                 [n IN nodes(path) | {id: n.id, name: n.name}] AS players,
                 [r IN relationships(path) | r.club] AS clubs
            RETURN {
                players: players,
                clubs: clubs,
                length: size(relationships(path))
            } AS result
            """,
            {"a": player_a, "b": player_b},
        )
        return row.get("result") if row else None
