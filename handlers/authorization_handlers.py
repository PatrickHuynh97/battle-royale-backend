import json

from handlers.lambda_helpers import endpoint
from models import player
from exceptions import UserAlreadyExistsException
from models.user import User


@endpoint()
def sign_up_handler(event, context):
    """
    Handler for signing up a user
    """
    body = json.loads(event['body'])
    username = body['username']

    # ensure username is not already in use
    if player.Player(username).exists():
        raise UserAlreadyExistsException(f'User with username {username} already exists')

    res = User().sign_up(username=body['username'],
                         password=body['password'],
                         email=body['email'])

    player.Player(username).put()

    return json.dumps(res)


@endpoint()
def sign_in_handler(event, context):
    """
    Handler for signing in a user
    """
    body = json.loads(event['body'])

    result = User().sign_in(username=body['username'], password=body['password'])

    return json.dumps(result)


@endpoint()
def sign_out_handler(event, context):
    """
    Handler for signing out a user
    """
    body = json.loads(event['body'])

    result = User().sign_out(access_token=body['access_token'])

    return json.dumps(result)
