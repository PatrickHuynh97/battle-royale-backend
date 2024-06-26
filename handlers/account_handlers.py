from handlers.lambda_helpers import endpoint
from models import player
from exceptions import UserAlreadyExistsException, PasswordLengthException, InvalidUsernameException
from models.user import User
from exceptions import PlayerCannotBeDeletedException
from models.player import Player
from jwt import verify_token


@endpoint()
def sign_up_handler(event, context):
    """
    Handler for signing up a user
    """
    body = event['body']
    username = body['username']

    if username.startswith("test_player_") or username.startswith("test_game_master_"):
        raise InvalidUsernameException("Usernames beginning with test_player_ or test_game_master_ are not allowed")

    # ensure username is not already in use
    if player.Player(username).exists():
        raise UserAlreadyExistsException(f'User with username {username} already exists')

    password = body['password']
    if len(password) < 6:
        raise PasswordLengthException(f'Password must be at least 6 characters long')

    User().sign_up(username=username,
                   password=body['password'],
                   email=body['email'])

    player.Player(username).put()


@endpoint()
def sign_in_handler(event, context):
    """
    Handler for signing in a user
    """
    body = event['body']
    result = User().sign_in(username=body['username'], password=body['password'])
    return result


@endpoint()
def sign_out_handler(event, context):
    """
    Handler for signing out a user
    """

    User().sign_out(access_token=event['body']['access_token'])


@endpoint()
def refresh_tokens_handler(event, context):
    """
    Handler for signing out a user
    """

    result = User().refresh_tokens(refresh_token=event['body']['refresh_token'])

    return result


@endpoint()
def delete_user_handler(event, context):
    """
    Handler for deleting a user. Username and ID token must be provided.
    """

    access_token = event['body']['access_token']

    # check that access token is valid, and matches that of user to be deleted
    claims = verify_token(access_token)
    if not claims:
        raise PlayerCannotBeDeletedException("Invalid Access Token")

    Player(claims['username']).delete(access_token=access_token)
