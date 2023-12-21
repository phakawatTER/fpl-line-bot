from dataclasses import dataclass, field
from typing import List
from .bootstrap import BootstrapElement


@dataclass
class PlayerGameweekData:
    name: str = ""
    player_id: int = 0
    points: float = 0
    reward_division: int = 1
    shared_reward_player_ids: List[int] = field(default_factory=list)
    reward: float = 0
    sheet_row: int = -1
    captain_points: int = 0
    vice_captain_points: int = 0
    bank_account: str = ""


@dataclass
class PlayerRevenue:
    name: str
    revenue: float


@dataclass
class PlayerSheetData:
    player_id: int
    bank_account: str
    season_rank: int
    name: str
    team_name: str


@dataclass
class PlayerGameweekPicksData:
    player: PlayerSheetData
    picked_elements: List[BootstrapElement]
