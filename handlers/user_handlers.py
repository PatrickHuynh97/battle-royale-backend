import json

from handlers.lambda_helpers import endpoint
from exceptions import UserCannotBeDeletedException
from models.player import PlayerModel
from jwt import verify_token


@endpoint
def delete_user_handler(event, context):
    """
    Handler for deleting a user. Username and ID token must be provided.
    """

    body = json.loads(event['body'])

    access_token = body['access_token']

    # check that access token is valid, and matches that of user to be deleted
    claims = verify_token(access_token)
    if not claims:
        raise UserCannotBeDeletedException("Invalid Access Token")

    PlayerModel(claims['username']).delete_player(access_token=access_token)
