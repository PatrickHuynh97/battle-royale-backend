import json

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
    players = []
    for username in usernames:
        player = Player(username)
        player.put()
        players.append(player)
    return players
