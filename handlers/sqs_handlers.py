from enums import SQSEventType
from handlers.lambda_helpers import sqs_handler
from models import game_master
from models.lobby import Lobby
from sqs.closing_circle_queue import CircleQueue
from websockets.connection_manager import ConnectionManager


@sqs_handler
def circle_queue_handler(event, context):
    """
    Handler for a single SQS event from the CircleQueue
    """
    event_type = SQSEventType(event['event_type'])
    lobby = Lobby(event['lobby_name'], game_master.GameMaster(event['lobby_owner']))
    lobby.get()

    if event_type == SQSEventType.FIRST_CIRCLE:
        _handle_first_circle(lobby)
    if event_type == SQSEventType.CLOSE_CIRCLE:
        _handle_close_circle(lobby)


def _handle_first_circle(lobby: Lobby):
    """
    Handle FIRST_CIRCLE event. Enqueues the closing of this circle once it has been generated.
    :param lobby: lobby to generate first circle of
    :return: None
    """
    # generate first next_circle for the given lobby
    lobby.generate_first_circle()
    connection_manager = ConnectionManager()
    connection_manager.push_next_circle(lobby)

    circle_queue = CircleQueue()
    circle_queue.send_close_circle_event(lobby)


def _handle_close_circle(lobby: Lobby):
    """
    Handle CLOSE_CIRCLE event
    :param lobby: lobby to close circle of
    :return: None
    """
    # closes current_circle to become next_circle, generates next circle, and push the next circle to all players
    lobby.close_current_circle()
    connection_manager = ConnectionManager()
    connection_manager.push_next_circle(lobby)

    # enqueue SQS message to close the next_circle after a certain amount of time
    circle_queue = CircleQueue()
    circle_queue.send_close_circle_event(lobby)
