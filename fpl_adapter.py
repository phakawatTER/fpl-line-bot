import requests as r
from fpl_type import H2HResponse,FantasyTeam,PlayerData,PlayerHistory,PlayerSeasonHistory
from http import HTTPStatus
import asyncio

class FPLAdapter:
    
    def __init__(self,league_id:int,cookies:str):
        self.cookies = cookies
        self.league_id = league_id
        
    def get_h2h_results(self,game_week:int)-> H2HResponse:
        url = f"https://fantasy.premierleague.com/api/leagues-h2h-matches/league/{self.league_id}/?page=1&event={game_week}"
        response = r.get(url,params={"cookies": self.cookies})
        if response.status_code != HTTPStatus.OK:
            raise Exception(f"unexpected http status code: {response.status_code} with response data: {response.content}")
        
        return H2HResponse(response=response.json())
    
    def get_player_gameweek_info(self,game_week:int,player_id:int):
        url = f"https://fantasy.premierleague.com/api/element-summary/{player_id}"
        response = r.get(url,params={"cookies": self.cookies})
        if response.status_code != HTTPStatus.OK:
            raise Exception(f"unexpected http status code: {response.status_code} with response data: {response.content}")
        data:dict = response.json()
        player_data = PlayerData(fixtures=data.get("fixtures"),history=data.get("history"),history_past=data.get("history_past"))
        history: PlayerHistory
        for h in player_data.history:
            if h.round == game_week:
                history = h
        if history is None:
            raise Exception(f"player data not found on gameweek {game_week}")
        return history
    
    def get_player_team_by_id(self,player_id:int,game_week:int):
        url = f"https://fantasy.premierleague.com/api/entry/{player_id}/event/{game_week}/picks"
        response = r.get(url,params={"cookies": self.cookies})
        if response.status_code != HTTPStatus.OK:
            raise Exception(f"unexpected http status code: {response.status_code} with response data: {response.content}")

        data:dict = response.json()
        return FantasyTeam(
            active_chip=data.get("active_chip"),
            automatic_subs=data.get("automatic_subs"),
            entry_history=data.get("entry_history"),
            picks=data.get("picks"),
        )
    
        
        
        
        