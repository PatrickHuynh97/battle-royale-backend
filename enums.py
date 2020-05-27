from enum import Enum


class LobbyState(Enum):
    """
    Different types of states a Lobby can be in
    """
    NOT_STARTED = 'not_started'
    STARTED = 'started'
    FINISHED = 'finished'


class PlayerState(Enum):
    """
    Different types of states a player can be in
    """
    ALIVE = 'alive'
    DEAD = 'dead'


class WebSocketEventType(Enum):
    CONNECT = 'connect'
    DISCONNECT = 'disconnect'
    AUTHORIZE = 'authorize'


class GameMasterMessageType(Enum):
    EXAMPLE = 'example'


class SQSEventType(Enum):
    FIRST_CIRCLE = 'first_circle'
    CLOSE_CIRCLE = 'close_circle'


class WebSocketPushMessageType(Enum):
    GAME_STATE = 'game_state'
    PLAYER_DEAD = 'player_dead'
    PLAYER_LOCATION = 'player_location'
    CIRCLE_CLOSING = 'circle_closing'
    NEXT_CIRCLE = 'next_circle'
    GAME_MASTER_MESSAGE = 'game_master_message'
