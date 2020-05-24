import unittest
from models.map import GameZone, Circle
from geopy import distance


class TestGameZone(unittest.TestCase):

    def setUp(self):

        # gamezone coordinates based around Nyvang Airsoft Alliance:
        #   top right 56.132501, 12.903200
        #   top left 56.132757, 12.897615
        #   bottom left 56.130781, 12.896993
        #   bottom right 56.130309, 12.902884
        # final zone is middle of the CQB field and is 40 meters in diameter
        #   56.130722, 12.900430, radius 35 meters

        self.game_zone_coordinates = dict(
            c1=dict(latitude="56.132501", longitude="12.903200"),
            c2=dict(latitude="56.132757", longitude="12.897164"),
            c3=dict(latitude="56.130781", longitude="12.896993"),
            c4=dict(latitude="56.130309", longitude="12.902884")
        )
        self.final_circle = Circle(dict(centre=dict(latitude=56.130722, longitude=12.900430), radius=20 / 1000))

    def check_if_circle_contains_circle(self, outer_circle, inner_circle):
        """
        Helper function for checking if an outer circle contains an inner circle
        :param outer_circle: Outer circle
        :param inner_circle: Inner circle
        :return:
        """
        # make sure the outer_circle contains the inner_circle
        first_circle = (outer_circle.centre['latitude'], outer_circle.centre['longitude'])
        second_circle = (inner_circle.centre['latitude'], inner_circle.centre['longitude'])
        centre_distance = distance.distance(first_circle, second_circle).kilometers
        # distance between inner_circle centre and outer_circle centre should be less than the radius of the
        # outer_circle
        self.assertTrue(centre_distance < outer_circle.radius)
        # distance between inner_circle and the outer_circle, plus the radius of the outer_circle, should be less than
        # the radius of the outer_circle (draw a diagram if you're confused, because this makes sense!!)
        self.assertTrue(centre_distance + inner_circle.radius < outer_circle.radius)

    def test_point_in_circle(self):
        # test that a given coordinate is within a circle or not for a known set of coordinates
        coordinate_40m_out = dict(latitude=56.130751, longitude=12.901088)
        coordinate_21m_out = dict(latitude=56.130736, longitude=12.900766)

        coordinate_10m_out = dict(latitude=56.130741, longitude=12.900585)
        coordinate_19m_out = dict(latitude=56.130744, longitude=12.900732)

        self.assertFalse(self.final_circle.contains_coordinates(coordinate_40m_out))
        self.assertFalse(self.final_circle.contains_coordinates(coordinate_21m_out))

        self.assertTrue(self.final_circle.contains_coordinates(coordinate_10m_out))
        self.assertTrue(self.final_circle.contains_coordinates(coordinate_19m_out))

    def test_get_game_zone_information(self):

        expected_centre = dict(latitude=56.131533, longitude=12.9000965)

        game_zone = GameZone(
            game_zone_coordinates=self.game_zone_coordinates,
            final_circle=self.final_circle
        )

        centre, latitude_distance, longitude_distance = game_zone.get_game_zone_information()
        self.assertEqual(expected_centre, centre)

    def test_generate_next_circle_no_final_circle(self):
        # test create GameZone with no current_circle, and generating a first circle (becomes next_circle)
        game_zone = GameZone(
            game_zone_coordinates=self.game_zone_coordinates,
        )

        # generate next circle
        game_zone.create_next_circle()
        self.assertIsNotNone(game_zone.next_circle)

        next_circle_centre = game_zone.next_circle.centre
        next_circle_radius = game_zone.next_circle.radius
        self.assertIsNotNone(next_circle_centre)
        self.assertIsNotNone(next_circle_radius)

        # check that the centre of the next circle is within the game zone
        gz_minimum_latitude = min([value['latitude'] for coordinate, value in self.game_zone_coordinates.items()])
        gz_maximum_latitude = max([value['latitude'] for coordinate, value in self.game_zone_coordinates.items()])
        gz_minimum_longitude = min([value['longitude'] for coordinate, value in self.game_zone_coordinates.items()])
        gz_maximum_longitude = max([value['longitude'] for coordinate, value in self.game_zone_coordinates.items()])

        self.assertTrue(float(gz_minimum_latitude) < next_circle_centre['latitude'] < float(gz_maximum_latitude))
        self.assertTrue(float(gz_minimum_longitude) < next_circle_centre['longitude'] < float(gz_maximum_longitude))

    def test_generate_next_circle_with_final_circle(self):
        # test create GameZone with a final_circle, and generating two further circles
        game_zone = GameZone(
            game_zone_coordinates=self.game_zone_coordinates,
            final_circle=self.final_circle
        )

        # generate next circle
        game_zone.create_next_circle()
        self.assertIsNotNone(game_zone.next_circle)

        first_next_circle = game_zone.next_circle
        self.assertIsNotNone(first_next_circle)
        self.assertIsNotNone(first_next_circle)

        # check that the centre of the next circle is within the game zone
        gz_min_latitude = min([value['latitude'] for coordinate, value in self.game_zone_coordinates.items()])
        gz_max_latitude = max([value['latitude'] for coordinate, value in self.game_zone_coordinates.items()])
        gz_min_longitude = min([value['longitude'] for coordinate, value in self.game_zone_coordinates.items()])
        gz_max_longitude = max([value['longitude'] for coordinate, value in self.game_zone_coordinates.items()])

        self.assertTrue(float(gz_min_latitude) < first_next_circle.centre['latitude'] < float(gz_max_latitude))
        self.assertTrue(float(gz_min_longitude) < first_next_circle.centre['longitude'] < float(gz_max_longitude))

        self.check_if_circle_contains_circle(first_next_circle, game_zone.final_circle)

        # manually set current circle to the generated next circle, and generate another one
        game_zone.current_circle = game_zone.next_circle
        game_zone.create_next_circle()

        second_next_circle = game_zone.next_circle

        # game_zone.next_circle should be different now
        self.assertNotEqual(first_next_circle.centre, game_zone.next_circle.centre)
        self.assertNotEqual(first_next_circle.radius, game_zone.next_circle.radius)

        # second next_circle must be in the game zone, within the first_next_circle, and contain the final_circle
        self.assertTrue(float(gz_min_latitude) < game_zone.next_circle.centre['latitude'] < float(gz_max_latitude))
        self.assertTrue(float(gz_min_longitude) < game_zone.next_circle.centre['longitude'] < float(gz_max_longitude))

        self.check_if_circle_contains_circle(first_next_circle, second_next_circle)
        self.check_if_circle_contains_circle(second_next_circle, game_zone.final_circle)

    def test_generate_next_circle_until_final_circle(self):
        # create GameZone with a desired final_circle and generating circles until the final circle is used
        game_zone = GameZone(
            game_zone_coordinates=self.game_zone_coordinates,
            final_circle=self.final_circle
        )

        # get lat and long values for game zone
        gz_min_latitude = min([value['latitude'] for coordinate, value in self.game_zone_coordinates.items()])
        gz_max_latitude = max([value['latitude'] for coordinate, value in self.game_zone_coordinates.items()])
        gz_min_longitude = min([value['longitude'] for coordinate, value in self.game_zone_coordinates.items()])
        gz_max_longitude = max([value['longitude'] for coordinate, value in self.game_zone_coordinates.items()])

        # generate first circle, make sure it contains the final_circle and is in the game_zone
        game_zone.create_next_circle()
        self.check_if_circle_contains_circle(game_zone.next_circle, game_zone.final_circle)
        self.assertTrue(float(gz_min_latitude) < game_zone.next_circle.centre['latitude'] < float(gz_max_latitude))
        self.assertTrue(float(gz_min_longitude) < game_zone.next_circle.centre['longitude'] < float(gz_max_longitude))

        # manually set first circle to current_circle, and generate the second circle
        game_zone.current_circle = game_zone.next_circle
        game_zone.create_next_circle()
        self.check_if_circle_contains_circle(game_zone.next_circle, game_zone.final_circle)

        # manually set second circle to current_circle, and generate the third circle
        game_zone.current_circle = game_zone.next_circle
        game_zone.create_next_circle()
        self.check_if_circle_contains_circle(game_zone.next_circle, game_zone.final_circle)

        # manually set third circle to current_circle, and generate the fourth circle
        game_zone.current_circle = game_zone.next_circle
        game_zone.create_next_circle()
        self.check_if_circle_contains_circle(game_zone.next_circle, game_zone.final_circle)

        # manually set fourth circle to current_circle, and generate the fifth circle
        game_zone.current_circle = game_zone.next_circle
        game_zone.create_next_circle()
        self.check_if_circle_contains_circle(game_zone.next_circle, game_zone.final_circle)

        # manually set fifth circle to current_circle, and try to generate the sixth circle
        game_zone.current_circle = game_zone.next_circle
        game_zone.create_next_circle()
        # sixth circle will be the same as the final circle
        self.assertEqual(game_zone.next_circle, self.final_circle)
