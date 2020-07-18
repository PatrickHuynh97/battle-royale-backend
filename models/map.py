from math import cos, pi
from geopy import distance
import random
import time

from configuration import Configuration
from websockets import connection_manager as cm

CIRCLE_CONFIG = Configuration().get_configuration()['DEFAULT_CIRCLE_CONFIG']


class MapObject:
    @staticmethod
    def coordinate_to_string(coordinate):
        return dict(longitude=str(coordinate['longitude']),
                    latitude=str(coordinate['latitude']))

    @staticmethod
    def coordinate_to_float(coordinate):
        return dict(longitude=float(coordinate['longitude']),
                    latitude=float(coordinate['latitude']))

    @staticmethod
    def distance_between(coordinate_1, coordinate_2):
        """
        Calculates distance between two longitude/latitude coordinates and returns value in meters
        :param coordinate_1: coordinates of first point
        :param coordinate_2: coordinates of second point
        :return: distance in meters between the two coordinates
        """
        return distance.distance((coordinate_1['latitude'], coordinate_1['longitude']),
                                 (coordinate_2['latitude'], coordinate_2['longitude'])).kilometers


class Circle(MapObject):
    # class representing a circle of playable area
    def __init__(self, circle):
        self.centre = circle.get('centre') if circle else None
        self.radius = float(circle.get('radius')) if circle.get('radius') else None

        # if we have circle data, and coordinates are strings, convert them to floats
        if self.centre:
            self.centre = self.coordinate_to_float(self.centre)

    def __eq__(self, other):
        """If a Circle object has the same centre and radius as another Circle, they are the same Circle"""
        if isinstance(other, Circle):
            return self.centre == other.centre and self.radius == other.radius
        return False

    def to_string_dict(self):
        """
        Returns a dict representation of the data which defines a circle, namely the centre coordinates and the radius
        :return: Dict containing centre of circle and the radius
        """
        return dict(
            centre=self.coordinate_to_string(self.centre),
            radius=str(self.radius)
        )

    def to_dict(self):
        """
        Returns a dict representation of the data which defines a circle, namely the centre coordinates and the radius
        :return: Dict containing centre of circle and the radius
        """
        return dict(
            centre=self.coordinate_to_float(self.centre),
            radius=self.radius
        )

    def contains_coordinates(self, coordinates):
        """
        Checks if the provided coordinates are contained self
        :param coordinates: set of coordinates to check if they are within self
        :return: True if the provided coordinates are contained within self, else False

        """
        return self.distance_between(self.centre, coordinates) < self.radius

    def generate_centre_within_distance(self, max_allowed_distance):
        """
        Generates another circle's centre that is within distance_from_centre kilometers of self.centre. Math from:
        https://stackoverflow.com/questions/7477003/calculating-new-longitude-latitude-from-old-n-meters
        :param max_allowed_distance: maximum allowed distance of new circle centre from self.centre in kilometers
        :return: a valid next circle centre given allowed distance from current circle
        """
        # change in latitude and longitude if self.centre is moved distance_from_centre kilometers
        latitude_adjustment = (max_allowed_distance / distance.EARTH_RADIUS) * (180 / pi)
        longitude_adjustment = (max_allowed_distance / distance.EARTH_RADIUS) * (180 / pi) / cos(self.centre['latitude'] * pi / 180)

        while True:
            # generate random coordinate within distance_from_centre metres from current self.centre
            new_centre_latitude = random.uniform(self.centre['latitude']-latitude_adjustment,
                                                 self.centre['latitude']+latitude_adjustment)
            new_centre_longitude = random.uniform(self.centre['longitude'] - longitude_adjustment,
                                                  self.centre['longitude'] + longitude_adjustment)
            coordinates = dict(latitude=new_centre_latitude, longitude=new_centre_longitude)

            # check if generated coordinates are acceptable. If it's not, repeat random coordinate generation
            if self.distance_between(self.centre, coordinates) < max_allowed_distance:
                return coordinates

    def generate_centre_within_distance_and_contains(self, distance_from_centre, new_radius, final_circle):
        """
        Generates another circle's centre that is within distance_from_centre kilometers of self.centre, but also
        contains the final_circle.
        :param distance_from_centre: allowed distance of new circle centre from self.centre
        :param new_radius: new_radius of the new circle
        :param final_circle: Circle object containing information about final circle
        :return: a valid next circle centre given allowed distance from current circle and the final circle position
        """
        # the distance between the new circle must contain the final circle in its entirety. This can be calculated by
        #   (distance(new_circle, final_circle) + final_circle.radius) < new_circle.radius
        # lazy solution is to spam generate_centre_within_distance, and check if the above math checks out. In the
        # future we should narrow down the search space for the new circle to improve response times but it's pretty
        # fast as is. If no solution is generated within 3 seconds, return false (https://stackoverflow.com/a/44723559)

        tCurrent = time.time()

        while True:
            if time.time() >= tCurrent + 2:
                return False
            # generate a valid circle which may or may not exclude the final circle
            proposed_centre = self.generate_centre_within_distance(distance_from_centre)
            # verify if the proposed circle centre excludes the final circle or not
            if self.distance_between(proposed_centre, final_circle.centre) + final_circle.radius < new_radius:
                # proposed next circle contains the final circle, return
                return proposed_centre

    def generate_intermediate_circles(self, inner_circle):
        """
        Generates a list of sequential circles which closes Self towards inner_circle
        :param inner_circle: Circle to close Self towards
        :return: dict containing each sequential circle to which will lead towards inner_circle
        """
        closing_rate = self.get_closing_rate()

        radius_difference = self.radius - inner_circle.radius
        if not radius_difference:
            radius_difference = self.radius  # circle is closing towards itself (final circle)
        number_of_intermediate_circles = round(radius_difference / closing_rate)

        # X and Y distance between self and inner_circle, and the differnece in radius
        lat_distance = self.centre['latitude'] - inner_circle.centre['latitude']
        long_distance = self.centre['longitude'] - inner_circle.centre['longitude']

        # amount to increment lat/long/radius with each intermediate circle
        lat_change = lat_distance / number_of_intermediate_circles
        long_change = long_distance / number_of_intermediate_circles
        radius_change = radius_difference / number_of_intermediate_circles

        intermediate_circles = []
        last_intermediate_circle_centre = None
        last_intermediate_circle_radius = None
        for i in range(0, number_of_intermediate_circles):
            # if we are on the penultimate intermediate circle, just make it the inner_circle exactly
            if i == number_of_intermediate_circles - 1:
                intermediate_circles.append(dict(centre=inner_circle.centre, radius=inner_circle.radius))
            elif not last_intermediate_circle_centre:
                intermediate_circle_centre = dict(
                    latitude=self.centre['latitude'] - lat_change,
                    longitude=self.centre['longitude'] - long_change
                )
                last_intermediate_circle_radius = self.radius - radius_change
                last_intermediate_circle_centre = intermediate_circle_centre

                intermediate_circles.append(dict(centre=intermediate_circle_centre,
                                                 radius=last_intermediate_circle_radius))
            else:
                intermediate_circle_centre = dict(
                    latitude=last_intermediate_circle_centre['latitude'] - lat_change,
                    longitude=last_intermediate_circle_centre['longitude'] - long_change
                )
                last_intermediate_circle_radius = last_intermediate_circle_radius - radius_change
                last_intermediate_circle_centre = intermediate_circle_centre

                intermediate_circles.append(dict(centre=intermediate_circle_centre,
                                                 radius=last_intermediate_circle_radius))

        return intermediate_circles

    def get_closing_rate(self):
        """
        Gets closing rate given radius of self
        :return: closing rate as float
        """
        last_rate = None
        for closing_rate, value in CIRCLE_CONFIG['CLOSING_RATES'].items():
            if not last_rate or not float(closing_rate) < self.radius < float(last_rate):
                last_rate = closing_rate
            else:
                return CIRCLE_CONFIG['CLOSING_RATES'][last_rate]
        # if the circle is very small and has no associated rate, just take the slowest
        return CIRCLE_CONFIG['CLOSING_RATES'][last_rate]


class CircleNotComputableException(Exception):
    pass


class GameZone(MapObject):
    # class representing the entire playable area and the circles within it.
    def __init__(self,
                 coordinates=None,
                 current_circle: Circle = None,
                 next_circle: Circle = None,
                 final_circle: Circle = None):
        self.coordinates = self.game_zone_coordinates_to_float(coordinates)
        self.current_circle = current_circle
        self.next_circle = next_circle
        self.final_circle = final_circle

    def create_next_circle(self, size_decrease_pct=33):
        """
        Creates the next circle to be used as the play area.  If a final circle location was given, the generated
        circle will include it in it's entirety.
        :param size_decrease_pct: percentage to decrease the circle by. By default circle size is reduced by 33%
        :return: New circle coordinates
        """
        # if there is a circle already
        if self.current_circle:
            new_radius = self.current_circle.radius*(1-(size_decrease_pct/100))
            # get distance next circle can be from current circle (distance between circle centres) such that the
            # next circle is completely encapsulated by the current circle
            allowed_distance_from_current = self.current_circle.radius - new_radius

            # if a final circle has been defined, next circle must include that final circle in its entirety
            if self.final_circle:

                # if final circle radius is greater than new_radius but smaller than current_radius, take final circle
                if new_radius < self.final_circle.radius < self.current_circle.radius:
                    self.next_circle = self.final_circle
                    return

                # try to generate a random new circle which encapsulates final circle for 2 seconds
                next_circle_centre = self.current_circle.generate_centre_within_distance_and_contains(
                    allowed_distance_from_current,
                    new_radius,
                    self.final_circle)

                # this should not be the case, but in case we can't generate a circle just set it to the final circle
                if not next_circle_centre:
                    self.next_circle = self.final_circle

                self.next_circle = Circle(dict(centre=next_circle_centre, radius=new_radius))

            # generate completely random circle within current circle
            else:
                allowed_distance_from_current = self.current_circle.radius - new_radius
                next_circle_centre = self.current_circle.generate_centre_within_distance(allowed_distance_from_current)
                self.next_circle = Circle(dict(centre=next_circle_centre, radius=new_radius))
        # no current_circle exists to base next circle off, use entire GameZone to generate a sensible circle
        else:
            # diameter of next_circle will be 90% of the shortest side of the GameZone
            game_zone_centre, width, diagonal = self.get_game_zone_information()
            circle_radius = width*0.9/2

            # circle centre will be placed a maximum distance away from the centre of the gamezone equal to 30% the
            # shortest side of the Gamezone itself. This means it will never have a centre outside of the Gamezone
            allowed_distance = width*0.3
            fake_circle = Circle(dict(centre=game_zone_centre,
                                      radius=None))  # use fake circle where centre is centre of the map
            if self.final_circle:
                circle_centre = fake_circle.generate_centre_within_distance_and_contains(allowed_distance,
                                                                                         circle_radius,
                                                                                         self.final_circle)
                # this should not be the case, but in case we can't generate a circle just set it to the final circle
                if not circle_centre:
                    self.next_circle = self.final_circle
            else:
                circle_centre = fake_circle.generate_centre_within_distance(allowed_distance)

            self.next_circle = Circle(dict(centre=circle_centre, radius=circle_radius))

    def close_to_next_circle(self, lobby):
        """
        Contains the process of closing towards the next_circle. create_next_circle must be called before this in order
        to get a next_circle.
        To close a circle, we generate a set of "intermediate circles", where each intermediate centre is along the
        straight line between the outer and inner circle centres. Each intermediate circle moves some fraction closer
        to the inner circle, and the radius reduces by the same fraction, resulting in a smooth transition between
        outer and inner circle.
        The rate at which a circle closes is dependent on its radius- larger circles close faster than smaller ones.
        The default CLOSING_RATES in CIRCLE_CONFIG dictates how fast the circle should close with respect to the
        edges moving inwards.
        :return: None
        """
        if self.current_circle and self.current_circle == self.final_circle:
            # the current_circle is the final_circle
            intermediate_circles = self.current_circle.generate_intermediate_circles(self.final_circle)
        elif self.current_circle:
            # get closing rate of circle given the radius of the current circle
            intermediate_circles = self.current_circle.generate_intermediate_circles(self.next_circle)
        else:
            # game has not had a circle close yet. Mock a circle bigger than the whole map and close that
            game_zone_centre, width, diagonal = self.get_game_zone_information()
            mock_circle = Circle(dict(centre=self.next_circle.centre, radius=diagonal))
            intermediate_circles = mock_circle.generate_intermediate_circles(self.next_circle)

        # push each intermediate circle to clients. Once complete, set current_circle
        connection_manager = cm.ConnectionManager()
        connection_manager.push_circle_updates(intermediate_circles, lobby=lobby)
        self.current_circle = self.next_circle

    def get_game_zone_information(self):
        """
        Retrieves approximate coordinate of the centre of the map. We assume the earth to be flat and the game zone
        coordinates to represent an approximate rectangle. Also returns width and diagonal of game zone in degrees.
        :return: approximate centre of the map coordinates, width and height of game zone
        """
        # get length of shortest side and longest side of game zone
        l1 = self.distance_between(self.coordinates[0], self.coordinates[1])
        l2 = self.distance_between(self.coordinates[0], self.coordinates[2])
        l3 = self.distance_between(self.coordinates[0], self.coordinates[3])
        sorted_sides = sorted([l1, l2, l3])
        shortest_side = sorted_sides[0]
        diagonal = sorted_sides[2]

        # get coordinates of approximate centre of game zone
        all_latitudes = [coordinate['latitude'] for coordinate in self.coordinates]
        all_longitudes = [coordinate['longitude'] for coordinate in self.coordinates]

        corner_1 = min(all_latitudes), min(all_longitudes)
        corner_2 = max(all_latitudes), max(all_longitudes)

        latitude_distance = corner_2[0]-corner_1[0]
        longitude_distance = corner_2[1]-corner_1[1]
        centre = dict(latitude=corner_1[0] + latitude_distance / 2,
                      longitude=corner_1[1] + longitude_distance / 2)
        return centre, shortest_side, diagonal

    @staticmethod
    def game_zone_coordinates_to_float(game_zone_coordinates):
        """
        Converts coordinates in a game_zone_coordinates object to floats
        :param game_zone_coordinates: game_zone_coordinates
        :return: game_zone_coordinates where coordinate values are float
        """
        if game_zone_coordinates:
            return [dict(latitude=float(coordinate['latitude']),
                         longitude=float(coordinate['longitude'])) for coordinate in game_zone_coordinates]

    def dump_game_zone_coordinates(self):
        """
        Dumps game_zone_coordinates to string coordinate values
        :return: dict containing game_zone_coordinates as strings
        """
        return [dict(latitude=str(coordinate['latitude']),
                     longitude=str(coordinate['longitude'])) for coordinate in self.coordinates]
