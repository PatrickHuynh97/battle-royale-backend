from handlers.lambda_helpers import endpoint
from models.player import PlayerModel


@endpoint
def create_squad_handler(event, context):
    """
    Handler for creating a squad.
    """
    username = event['calling_user']
    squad_name = event['pathParameters']['squadname']

    PlayerModel(username).create_squad(squad_name=squad_name)


@endpoint
def delete_squad_handler(event, context):
    """
    Handler for deleting a squad.
    """
    username = event['calling_user']
    squad_name = event['pathParameters']['squadname']

    PlayerModel(username).delete_squad(squad_name=squad_name)


@endpoint
def add_user_to_squad_handler(event, context):
    """
    Handler for adding a player to a squad.
    """
    username = event['calling_user']
    squad_name = event['pathParameters']['squadname']
    user_to_add = event['pathParameters']['member']

    PlayerModel(username).add_member_to_squad(squad_name=squad_name,
                                              new_member=user_to_add)
