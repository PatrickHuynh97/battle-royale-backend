import json
from random import randint

from models.game_master import GameMaster
from models.player import Player


def make_api_gateway_event(calling_user=None, path_params={}, body={}, headers=None):
    """
    Helper function to create fake API Gateway event.
    :param calling_user: User making the request.
    :param path_params: Dict of path parameters
    :param body: Dict of data
    :param headers: Dict of headers
    :return: An API Gateway event and context
    """

    if headers is None:
        headers = {}
    return {
        'headers': headers,
        'pathParameters': path_params,
        'body': json.dumps(body),
        'requestContext': {'authorizer': {'claims': {'cognito:username': calling_user.username}}}
        if calling_user else {}
    }, None


def create_test_players(usernames: list):
    # create test players
    players = []
    for username in usernames:
        player = Player(username)
        player.put()
        players.append(player)
    return players


def create_test_squads(players: list):
    # create a squad with players inside
    squads = []
    squad_count = 1
    for player in players:
        squad = player.create_squad(f'squad_{randint(0,10000)}_{squad_count}')
        squad_count += 1
        squads.append(squad)
    return squads


def create_test_game_masters(usernames: list):
    # create test game_masters
    game_masters = []
    for username in usernames:
        game_master = GameMaster(username)
        game_master.put()
        game_masters.append(game_master)
    return game_masters
