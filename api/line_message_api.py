import re
import time
from flask import Flask, request, abort
from linebot import WebhookHandler
from linebot.models import MessageEvent,TextMessage,SourceGroup
from linebot.exceptions import InvalidSignatureError
from loguru import logger
from services import FPLService,MessageService
from adapter import GoogleSheet
from config.config import Config

SECOND = 1000

def _get_timestamp():
    return int(time.time()) * 1000

class LineMessageAPI:
    
    PATTERN_ACTIONS = {
        r"get (gw|gameweek) (\d+)": "update_fpl_table",
        r"get (revenue|rev)": "get_revenues",
    }

    def __init__(self,config:Config,credential:dict):
        self.app = Flask(__name__)
        self.handler = WebhookHandler(config.line_channel_secret)
        self.message_service = MessageService(config=config)
        self.config = config
        google_sheet = GoogleSheet(credential=credential)
        google_sheet.open_sheet_by_url(config.sheet_url)
        self.fpl_service = FPLService(config=self.config,google_sheet=google_sheet)
        
    def initialize(self):
        handler = WebhookHandler(self.config.line_channel_secret)

        @self.app.route("/callback", methods=['POST'])
        def callback():
            signature = request.headers['X-Line-Signature']
            body = request.get_data(as_text=True)
            try:
                handler.handle(body, signature)
            except InvalidSignatureError as e:
                logger.error(e)
                abort(400)
                
            return 'OK'

        @handler.add(MessageEvent, message=TextMessage)
        def handle_message(event:MessageEvent):
            source:SourceGroup = event.source
            if source.group_id != self.config.line_group_id:
                return
            message:TextMessage = event.message
            now = _get_timestamp()
            if now - event.timestamp > 15 * SECOND:
                return
            
            text:str = message.text
            print(LineMessageAPI.PATTERN_ACTIONS)
            for pattern,action in LineMessageAPI.PATTERN_ACTIONS.items():
                print(pattern,action)
                match = re.search(pattern, text.lower())
                print("math",match)
                if match:
                    if action == "update_fpl_table":
                        extracted_group = match.group(2)
                        game_week = int(extracted_group)
                        self._run_in_error_wrapper(self._handle_update_fpl_table)(game_week=game_week)
                    elif action == "get_revenues":
                        extracted_group = match.group(1)
                        self._run_in_error_wrapper(self._handle_get_revenues)()
                    else:
                        pass

                    break
                
        
        return self.app
    
    
    def _run_in_error_wrapper(self,callback):
        def wrapped_func(*args, **kwargs):
            try:
                return callback(*args, **kwargs)
            except Exception as e:
                self.message_service.send_text_message("Oops...something went wrong")
                logger.error(e)
        return wrapped_func
    
    def _handle_update_fpl_table(self,game_week:int):
        self.message_service.send_text_message(f"Gameweek {game_week} result is being processed. Please wait for a moment")
        players = self.fpl_service.update_fpl_table(gw=game_week)
        self.message_service.send_gameweek_result_message(game_week=game_week,players=players)
        
    def _handle_get_revenues(self):
        self.message_service.send_text_message("Players revenue is being processed. Please wait for a moment")
        players = self.fpl_service.list_players_revenues()
        self.message_service.send_playeres_revenue_summary(players_revenues=players)
        