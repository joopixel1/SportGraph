from typing import List, Dict, Any, Optional

from fastapi import HTTPException, status

from api.src.repository.neo4j_graph_repository import Neo4jGraphRepository


class SoccerService:

    def __init__(self, repo: Neo4jGraphRepository):
        self.repo: Neo4jGraphRepository = repo

    async def get_player_by_id(self, player_id: str) -> Dict[str, Any]:
        """Fetch a player record by ID from Neo4j."""
        player = await self.repo.get_player_by_id(player_id)
        if not player:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Player with id '{player_id}' not found")

        return player

    async def search_players(self, name: str) -> List[Dict[str, Any]]:
        """Normalize search text and fetch matching players with total appearances."""
        return await self.repo.search_players(name)

    async def get_player_id_club_history(self, player_id: str) -> List[Dict[str, Any]]:
        """Verify player exists, then fetch all PLAYED_FOR edges for that player."""
        player_row = await self.repo.get_player_by_id(player_id)
        if not player_row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Player with id '{player_id}' not found")

        return await self.repo.get_player_club_history(player_id)

    async def get_player_name_club_history(self, player_name: str) -> List[Dict[str, Any]]:
        """Find player by name then fetch their full club history."""
        players = await self.repo.search_players(player_name)
        if not players:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"No player found matching '{player_name}'")

        player_id = players[0]["id"]
        return await self.repo.get_player_club_history(player_id)

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
        """Fetch players who played for a club using filters (apps, seasons, ordering)."""
        return await self.repo.get_club_players(
            club_name=club_name,
            min_apps=min_apps,
            max_apps=max_apps,
            season_from=season_from,
            season_to=season_to,
            order_by=order_by,
            order_dir=order_dir,
        )

    async def get_n_step_teammate_question(self, steps: int = 2, num_questions: int = 10, num_options: int = 4) -> List[Dict[str, Any]]:
        """
        Build MCQ questions for N-step teammate chains:
        1. Fetch all valid N-step PLAYED_WITH paths
        2. For each path, identify middle players
        3. Fetch distractor options for each missing node
        4. Construct question with clubs, correct answers, and shuffled choices
        """
        rows = await self.repo.get_n_step_teammate_paths(steps=steps, limit=num_questions)
        if not rows:
            return []

        questions: List[Dict[str, Any]] = []

        # Each row has structure: { "path": { players: [...], clubs: [...], totalWeight: X } }
        for path in rows:
            players = path["players"]  # list of {id,name}
            clubs = path["clubs"]  # list of club names

            if len(players) != steps + 1 or len(clubs) != steps:
                continue

            result: Dict[str, Any] = {}
            result["Player_0"] = players[0]

            for i in range(1, steps):
                left = players[i - 1]
                mid = players[i]
                right = players[i + 1]

                options = await self.repo.get_options(left["id"], mid["id"], right["id"], num_options)

                result[f"Club_{i-1}_{i}"] = clubs[i - 1]
                result[f"Choices_{i}"] = options
                result[f"Correct_{i}"] = mid

            result[f"Club_{steps-1}_{steps}"] = clubs[-1]
            result[f"Player_{steps}"] = players[-1]

            questions.append(result)

        return questions

    async def get_shortest_teammate_path_by_id(self, player_a: str, player_b: str) -> Dict[str, Any]:
        """Validate both IDs then compute shortest PLAYED_WITH path between them."""
        a = await self.repo.get_player_by_id(player_a)
        if not a:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Player with id '{player_a}' not found")

        b = await self.repo.get_player_by_id(player_b)
        if not b:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Player with id '{player_b}' not found")

        path = await self.repo.get_shortest_teammate_path(player_a, player_b)
        if not path:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"No path from '{player_a}' to {player_b}")
        return path

    async def get_shortest_teammate_path_by_name(self, player_a: str, player_b: str) -> Dict[str, Any]:
        """Resolve both players by name, then compute their shortest connection path."""
        a = await self.repo.search_players(player_a)
        if not a:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"No player found matching '{player_a}'")
        player_a = a[0]["id"]

        b = await self.repo.search_players(player_b)
        if not b:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"No player found matching '{player_b}'")
        player_b = b[0]["id"]

        path = await self.repo.get_shortest_teammate_path(player_a, player_b)
        if not path:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"No path from '{player_a}' to {player_b}")
        return path
