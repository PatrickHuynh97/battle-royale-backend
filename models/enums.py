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
