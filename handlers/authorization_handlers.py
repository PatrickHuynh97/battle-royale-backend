import json

from handlers.lambda_helpers import endpoint
from models.player import PlayerModel
from exceptions import UserAlreadyExistsException
from models.user import User


@endpoint
def sign_up_handler(event, context):
    """
    Handler for signing up a user
    """
    body = json.loads(event['body'])
    username = body['username']

    # ensure username is not already in use
    if PlayerModel(username).exists():
        raise UserAlreadyExistsException

    res = User().sign_up(username=body['username'],
                         password=body['password'],
                         email=body['email'])

    PlayerModel(username).put_player()

    return json.dumps(res)


@endpoint
def sign_in_handler(event, context):
    """
    Handler for signing in a user
    """
    body = json.loads(event['body'])

    result = User().sign_in(username=body['username'], password=body['password'])

    return json.dumps(result)


@endpoint
def sign_out_handler(event, context):
    """
    Handler for signing out a user
    """
    body = json.loads(event['body'])

    result = User().sign_out(access_token=body['access_token'])

    return json.dumps(result)
