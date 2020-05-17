import unittest

from models.map import GameZone, Circle


class TestMap(unittest.TestCase):

    def setUp(self):
        final_circle = Circle(dict(centre=dict(latitude=55.573487, longitude=13.018608), radius=30/1000))
        self.gamezone = GameZone(
            game_zone_coordinates=dict(c1="", c2="", c3="", c4=""),
            final_circle=final_circle
        )
