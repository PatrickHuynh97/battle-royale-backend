import json
from configuration import Configuration
from enums import SQSEventType
from sqs.utils import SqsQueue

CIRCLE_CONFIG = Configuration().get_configuration()['DEFAULT_CIRCLE_CONFIG']


class CircleQueue(SqsQueue):
    def __init__(self):
        super().__init__()

    def send_first_circle_event(self, lobby):
        """
        Enqueues an event in which the first circle will be generated
        :param lobby: Lobby to enqueue first circle event for
        :return: None
        """

        _, __, diagonal = lobby.game_zone.get_game_zone_information()

        last_circle_timer = None
        for distance, value in CIRCLE_CONFIG['CIRCLE_TIMERS'].items():
            if not last_circle_timer or not float(distance) < diagonal < float(last_circle_timer):
                last_circle_timer = distance
            else:
                break
        first_circle_timer = CIRCLE_CONFIG['CIRCLE_TIMERS'][last_circle_timer]
        self.send_message(message=dict(lobby_name=lobby.name,
                                       lobby_owner=lobby.owner.username,
                                       event_type=SQSEventType.FIRST_CIRCLE.value),
                          delay=first_circle_timer)

    def send_close_circle_event(self, lobby):
        """
        Enqueues an event which will close current_circle to next_circle when picked up by a lambda
        :param lobby: Lobby to close circles for
        :return: None
        """
        gamezone = lobby.game_zone
        # delay until current_circle closes depends on it's radius
        circle_radius_limit = None
        circle_timer = None
        for distance, value in CIRCLE_CONFIG['CIRCLE_TIMERS'].items():
            if not circle_radius_limit or not float(distance) < gamezone.next_circle.radius < float(circle_radius_limit):
                circle_radius_limit = distance
                circle_timer = value
            else:
                break
        self.send_message(message=dict(lobby_name=lobby.name,
                                       lobby_owner=lobby.owner.username,
                                       event_type=SQSEventType.CLOSE_CIRCLE.value),
                          delay=circle_timer)
