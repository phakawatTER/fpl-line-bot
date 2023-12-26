import functools
import asyncio
import json
from typing import List, Optional
from flask import abort
from boto3.session import Session
from boto3_type_annotations.lambda_ import Client as LambdaClient
from loguru import logger
import models
import util
from app import App
from services import MessageService
from ._message_pattern import MessageHandlerActionGroup, PATTERN_ACTIONS

PLOT_GENERATOR_FUNCTION_NAME = "FPLPlotGenerator"


def run_in_error_wrapper(func=None, message_service: MessageService = None):
    def construct_error_message(e: Exception) -> str:
        return f"❌ Oops...something went wrong with error: {e}"

    def decorator(func):
        @functools.wraps(func)
        def inner_sync(*args, **kwargs):
            try:
                result = func(*args, **kwargs)
                return result
            except Exception as e:
                message_service.send_text_message(
                    text=construct_error_message(e),
                    group_id=kwargs["group_id"],
                )
                abort(e)

        async def inner_async(*args, **kwargs):
            try:
                result = await func(*args, **kwargs)
                return result
            except Exception as e:
                message_service.send_text_message(
                    text=construct_error_message(e),
                    group_id=kwargs["group_id"],
                )
                abort(e)

        if asyncio.iscoroutinefunction(func):
            return inner_async
        return inner_sync

    if func is not None:
        return decorator(func)

    return decorator


def new_line_message_handler(app: App):
    class _LineMessageAPIHandler:
        def __init__(self, app: App):
            self.__message_service = app.message_service
            self.__firebase_repo = app.firebase_repo
            self.__subscription_service = app.subscription_service
            self.__fpl_service = app.fpl_service
            sess = Session()
            self.__lambda_client: LambdaClient = sess.client("lambda")

        @run_in_error_wrapper(message_service=app.message_service)
        def unsubscribe_league(self, group_id: str):
            league_id = self.__get_group_league_id(group_id)
            if league_id is None:
                self.__message_service.send_text_message(
                    "⚠️ Subscribed league not found"
                )
                return
            self.__firebase_repo.unsubscribe_league(group_id)
            self.__message_service.send_text_message(
                text=f"🥲 You have unsubscribed league ID {league_id}",
                group_id=group_id,
            )

        @run_in_error_wrapper(message_service=app.message_service)
        async def subscribe_league(self, group_id: str, league_id: int):
            is_ok = await self.__subscription_service.subscribe_league(
                league_id=league_id,
                group_id=group_id,
            )
            text = f"🎉 You have subscribed to league ID {league_id}"
            if is_ok:
                is_ok = self.__subscription_service.update_league_sheet(
                    league_id=league_id,
                    url="https://docs.google.com/spreadsheets/d/1eciOdiGItEkml98jVLyXysGMtpMa06hbiTTJ40lztw4/edit#gid=1315457538",
                    worksheet_name="Sheet3",
                )
            if not is_ok:
                text = f"❌ Unable to subscribe to league ID {league_id}"

            self.__message_service.send_text_message(
                text=text,
                group_id=group_id,
            )

        # NOTE: We support only 1 league per channel for now
        def __get_group_league_id(self, group_id: str):
            league_ids = self.__firebase_repo.list_leagues_by_line_group_id(group_id)
            if league_ids is not None and len(league_ids) > 0:
                return league_ids[0]
            self.__message_service.send_text_message(
                text="⚠️ No subscribed league found. Please subscribe to some league",
                group_id=group_id,
            )
            abort(404)

        @run_in_error_wrapper(message_service=app.message_service)
        def handle_list_bot_commands(self, group_id: str):
            commands = MessageHandlerActionGroup.get_commands()
            commands_map_list: List[tuple[str]] = []
            for cmd, desc in commands.items():
                for pattern, _cmd in PATTERN_ACTIONS.items():
                    if cmd == _cmd:
                        commands_map_list.append((desc, pattern.replace("|", " | ")))
                        break
            self.__message_service.send_bot_instruction_message(
                group_id=group_id,
                commands_map_list=commands_map_list,
            )

        @run_in_error_wrapper(message_service=app.message_service)
        async def handle_batch_update_fpl_table(
            self, from_gameweek: int, to_gameweek: int, group_id
        ):
            self.__validate_gameweek_range(from_gameweek, to_gameweek, group_id)
            event_status = await self.__fpl_service.get_gameweek_event_status(
                gameweek=to_gameweek
            )
            current_gameweek_event = (
                None if event_status is None else event_status.status[0].event
            )

            gameweek_players: List[List[models.PlayerGameweekData]] = []
            event_statuses: List[Optional[models.FPLEventStatusResponse]] = []
            gameweeks: List[int] = []
            league_id = self.__get_group_league_id(group_id)
            self.__message_service.send_text_message(
                text=f"Procesing gameweek {from_gameweek} to {to_gameweek}",
                group_id=group_id,
            )
            for gameweek in range(from_gameweek, to_gameweek + 1):
                players = await self.__fpl_service.get_or_update_fpl_gameweek_table(
                    gameweek=gameweek,
                    league_id=league_id,
                    ignore_cache=False,
                )
                gameweek_players.append(players)
                event_statuses.append(
                    event_status
                    if current_gameweek_event is not None
                    and current_gameweek_event == gameweek
                    else None
                )
                gameweeks.append(gameweek)
            self.__message_service.send_carousel_gameweek_results_message(
                gameweek_players=gameweek_players,
                event_statuses=event_statuses,
                gameweeks=gameweeks,
                group_id=group_id,
            )

        @run_in_error_wrapper(message_service=app.message_service)
        async def handle_update_fpl_table(self, gameweek: int, group_id: str):
            league_id = self.__get_group_league_id(group_id)
            self.__message_service.send_text_message(
                f"Gameweek {gameweek} result is being processed. Please wait for a moment",
                group_id=group_id,
            )
            players = await self.__fpl_service.get_or_update_fpl_gameweek_table(
                gameweek=gameweek,
                league_id=league_id,
                ignore_cache=False,
            )
            event_status = await self.__fpl_service.get_gameweek_event_status(gameweek)
            self.__message_service.send_gameweek_result_message(
                gameweek=gameweek,
                players=players,
                group_id=group_id,
                event_status=event_status,
            )

        @run_in_error_wrapper(message_service=app.message_service)
        async def handle_get_revenues(self, group_id: str):
            league_id = self.__get_group_league_id(group_id)
            self.__message_service.send_text_message(
                "Players revenue is being processed. Please wait for a moment",
                group_id=group_id,
            )
            players = await self.__fpl_service.list_players_revenues(league_id)
            self.__message_service.send_playeres_revenue_summary(
                players_revenues=players,
                group_id=group_id,
            )

        @util.time_track(description="Gameweek plot handler")
        @run_in_error_wrapper(message_service=app.message_service)
        async def handle_gameweek_plots(
            self, from_gameweek: int, to_gameweek: int, group_id: str
        ):
            self.__validate_gameweek_range(from_gameweek, to_gameweek, group_id)

            self.__message_service.send_text_message(
                text=f"Plots for GW{from_gameweek} to GW{to_gameweek} are being processed. Please wait for a moment...",
                group_id=group_id,
            )
            league_id = self.__get_group_league_id(group_id)
            gameweeks_data: list[list[dict[str, any]]] = []
            for gw in range(from_gameweek, to_gameweek + 1, 1):
                gameweek_data = (
                    await self.__fpl_service.get_or_update_fpl_gameweek_table(
                        gameweek=gw,
                        league_id=league_id,
                    )
                )
                gameweeks_data.append([g.to_json() for g in gameweek_data])

            payload = {
                "start_gw": from_gameweek,
                "end_gw": to_gameweek,
                "gameweeks_data": gameweeks_data,
            }
            response = self.__lambda_client.invoke(
                FunctionName=PLOT_GENERATOR_FUNCTION_NAME,
                InvocationType="RequestResponse",
                Payload=json.dumps(payload),
            )
            if response.get("StatusCode") != 200:
                logger.error(response)
                abort(response.get("StatusCode"))
            logger.info(response)
            payload_bytes = response.get("Payload").read()
            urls: List[str] = json.loads(payload_bytes)
            logger.info(urls)
            for url in urls:
                self.__message_service.send_image_messsage(
                    image_url=url, group_id=group_id
                )

        @run_in_error_wrapper(message_service=app.message_service)
        def handle_list_league_players(self, group_id: str):
            league_id = self.__get_group_league_id(group_id)
            ignored_player_ids = self.__firebase_repo.list_league_ignored_players(
                league_id
            )
            players = self.__firebase_repo.list_league_players(league_id=league_id)
            text = ""
            for i, p in enumerate(players):
                first_name = p.name.split(" ")[0]
                is_ignored = p.player_id in ignored_player_ids

                text += (
                    f"{i+1}. {p.team_name} ({first_name})"
                    + (" - IGNORED❌" if is_ignored else "")
                    + "\n"
                )
                if p.bank_account is not None and p.bank_account != "":
                    text += f"- {p.bank_account}\n"
            self.__message_service.send_text_message(text=text, group_id=group_id)

        def handle_set_league_player_bank_account(
            self, group_id: str, bank_account: str, player_index: int
        ):
            league_id = self.__get_group_league_id(group_id)
            players = self.__firebase_repo.list_league_players(league_id)
            player: Optional[models.PlayerData] = None
            for i, p in enumerate(players):
                if i == player_index:
                    p.bank_account = bank_account
                    player = p
                    break

            if player is None:
                self.__message_service.send_text_message(
                    text="❌ No player found!", group_id=group_id
                )
                return

            self.__firebase_repo.put_league_players(
                league_id=league_id,
                players=players,
            )
            text = f'🎉 You have successfully update "{player.name}" \'s bank account'
            self.__message_service.send_text_message(text=text, group_id=group_id)

        @run_in_error_wrapper(message_service=app.message_service)
        async def handle_players_gameweek_picks(self, gameweek: int, group_id: str):
            league_id = self.__get_group_league_id(group_id)
            player_gameweek_picks = await self.__fpl_service.list_player_gameweek_picks(
                gameweek=gameweek,
                league_id=league_id,
            )
            self.__message_service.send_carousel_players_gameweek_picks(
                gameweek=gameweek,
                player_gameweek_picks=player_gameweek_picks,
                group_id=group_id,
            )

        def __validate_gameweek_range(self, start_gw: int, end_gw: int, group_id: str):
            # Validate if start_gw and end_gw are in the range (1, 38)
            if 1 <= start_gw <= 38 and 1 <= end_gw <= 38:
                # Validate if start_gw is less than or equal to end_gw
                if start_gw > end_gw:
                    self.__message_service.send_text_message(
                        "Validation error: start_gw should be less than or equal to end_gw",
                        group_id,
                    )
                    abort(403)
            else:
                self.__message_service.send_text_message(
                    "Validation error: start_gw and end_gw should be in the range (1, 38)",
                    group_id,
                )
                abort(403)

    return _LineMessageAPIHandler(app)
