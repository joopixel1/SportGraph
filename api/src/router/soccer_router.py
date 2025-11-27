from fastapi import APIRouter, Depends, Query

from api.src.service.soccer_service import SoccerService
from api.src.dependencies import get_soccer_service


router = APIRouter(prefix="/soccer", tags=["Soccer"])


@router.get("/player/id", description="Fetch a player's basic information using their unique ID.")
async def get_player_by_id(
    player_id: str = Query(..., description="Player ID"),
    service: SoccerService = Depends(get_soccer_service),
):
    """Fetch player info by ID."""
    return await service.get_player_by_id(player_id)


@router.get("/player/name", description="Search for players using partial or full name text.")
async def search_players(
    name: str = Query(..., description="Player Name"),
    service: SoccerService = Depends(get_soccer_service),
):
    """Search players by partial or full name."""
    return await service.search_players(name)


@router.get("/player/history/id", description="Get a player's entire club history using their ID.")
async def get_player_history_by_id(
    player_id: str = Query(..., description="Player ID"),
    service: SoccerService = Depends(get_soccer_service),
):
    """Fetch a player's club history using ID."""
    return await service.get_player_id_club_history(player_id)


@router.get("/player/history/name", description="Get a player's club history by searching their name.")
async def get_player_history_by_name(
    name: str = Query(..., description="Player Name"),
    service: SoccerService = Depends(get_soccer_service),
):
    """Fetch a player's club history using name lookup."""
    return await service.get_player_name_club_history(name)


@router.get(
    "/club/players",
    description=("List all players who have played for a given club. " "Supports filtering by appearances, seasons, and sorting."),
)
async def get_club_players(
    club_name: str = Query(..., description="Club Name"),
    min_apps: int = Query(None, description="Minimum appearances"),
    max_apps: int = Query(None, description="Maximum appearances"),
    season_from: int = Query(None, description="Minimum start season"),
    season_to: int = Query(None, description="Maximum end season"),
    order_by: str = Query("appearances", description="Sort field"),
    order_dir: str = Query("desc", description="Sort direction"),
    service: SoccerService = Depends(get_soccer_service),
):
    """Fetch players who played for a club with optional filters."""
    return await service.get_club_players(
        club_name=club_name,
        min_apps=min_apps,
        max_apps=max_apps,
        season_from=season_from,
        season_to=season_to,
        order_by=order_by,
        order_dir=order_dir,
    )


@router.get(
    "/teammates/question",
    description=("Generate N-step teammate multiple-choice questions. " "Each question hides internal players and provides distractor choices."),
)
async def get_n_step_question(
    steps: int = Query(2, description="Number of PLAYED_WITH hops"),
    num_questions: int = Query(10, description="How many chains to fetch"),
    num_options: int = Query(4, description="Choices per missing node"),
    service: SoccerService = Depends(get_soccer_service),
):
    """Generate MCQ questions based on N-step teammate chains."""
    return await service.get_n_step_teammate_question(
        steps=steps,
        num_questions=num_questions,
        num_options=num_options,
    )


@router.get(
    "/teammates/shortest/id",
    description="Compute the shortest teammate connection path between two players using IDs.",
)
async def get_shortest_path_by_id(
    player_a: str = Query(..., description="Player A ID"),
    player_b: str = Query(..., description="Player B ID"),
    service: SoccerService = Depends(get_soccer_service),
):
    """Find shortest PLAYED_WITH path between two players using IDs."""
    return await service.get_shortest_teammate_path_by_id(player_a, player_b)


@router.get(
    "/teammates/shortest/name",
    description="Find the shortest teammate path between two players by searching their names.",
)
async def get_shortest_path_by_name(
    player_a: str = Query(..., description="Player A name"),
    player_b: str = Query(..., description="Player B name"),
    service: SoccerService = Depends(get_soccer_service),
):
    """Find shortest PLAYED_WITH path between two players using names."""
    return await service.get_shortest_teammate_path_by_name(player_a, player_b)
