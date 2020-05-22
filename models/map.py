from math import cos, pi
from geopy import distance
import random

from configuration import Configuration

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

    def circle_to_string(self):
        return dict(
            centre=self.coordinate_to_string(self.centre),
            radius=str(self.radius)
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
        # fast as is
        while True:
            # generate a valid circle which may or may not exclude the final circle
            proposed_centre = self.generate_centre_within_distance(distance_from_centre)
            # verify if the proposed circle centre excludes the final circle or not
            if self.distance_between(proposed_centre, final_circle.centre) + final_circle.radius < new_radius:
                # proposed next circle contains the final circle, return
                return proposed_centre


class GameZone(MapObject):
    # class representing the entire playable area and the circles within it.
    def __init__(self,
                 game_zone_coordinates=None,
                 current_circle: Circle = None,
                 next_circle: Circle = None,
                 final_circle: Circle = None):
        self.coordinates = self.game_zone_coordinates_to_float(game_zone_coordinates)
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

                # generate a new circle which encapsulates final circle
                next_circle_centre = self.current_circle.generate_centre_within_distance_and_contains(
                    allowed_distance_from_current,
                    new_radius,
                    self.final_circle)
                self.next_circle = Circle(dict(centre=next_circle_centre, radius=new_radius))

            # generate completely random circle within current circle
            else:
                allowed_distance_from_current = self.current_circle.radius - new_radius
                next_circle_centre = self.current_circle.generate_centre_within_distance(allowed_distance_from_current)
                self.next_circle = Circle(dict(centre=next_circle_centre, radius=new_radius))

        # no current_circle exists to base next circle off, use entire GameZone to generate a sensible circle
        else:
            # diameter of next_circle will be 90% of the shortest side of the GameZone
            game_zone_centre, width, height = self.get_game_zone_information()
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

            else:
                circle_centre = fake_circle.generate_centre_within_distance(allowed_distance)

            self.next_circle = Circle(dict(centre=circle_centre, radius=circle_radius))

    def close_current_circle(self):
        """
        Begins the process of closing the current_circle to become the next_circle. create_next_circle should be called
        before this in order to get a next_circle. Closing a circle is done by first checkout how far the outer
        circle is from the inner circle. We then generate a set of "intermediate circles", where each intermediate
        circle centre is along the straight line between the outer and inner circle centres. Each intermediate circle
        moves some fraction closer to the inner circle, and the radius reduces by the same fraction, resulting in a
        smooth transition between outer and inner circle.

        :return: None
        """
        if self.current_circle:
            distance_between_centres = self.distance_between(self.current_circle.centre, self.next_circle.centre)
            # todo use CIRCLE_CONFIG to decide how fast the circle should be closed

    def get_game_zone_information(self):
        """
        Retrieves approximate coordinate of the centre of the map. We assume the earth to be flat and the game zone
        coordinates to represent an approximate rectangle. Also returns width and height of game zone in degrees.
        :return: approximate centre of the map coordinates, width and height of game zone
        """
        # get length of shortest side and longest side of game zone
        l1 = self.distance_between(self.coordinates['c1'], self.coordinates['c2'])
        l2 = self.distance_between(self.coordinates['c1'], self.coordinates['c3'])
        l3 = self.distance_between(self.coordinates['c1'], self.coordinates['c4'])
        sorted_sides = sorted([l1, l2, l3])
        shortest_side = sorted_sides[0]
        longest_side = sorted_sides[2]

        # get coordinates of approximate centre of game zone
        all_latitudes = [self.coordinates['c1']['latitude'],
                         self.coordinates['c2']['latitude'],
                         self.coordinates['c3']['latitude'],
                         self.coordinates['c4']['latitude']]
        all_longitudes = [self.coordinates['c1']['longitude'],
                          self.coordinates['c2']['longitude'],
                          self.coordinates['c3']['longitude'],
                          self.coordinates['c4']['longitude']]
        corner_1 = min(all_latitudes), min(all_longitudes)
        corner_2 = max(all_latitudes), max(all_longitudes)

        latitude_distance = corner_2[0]-corner_1[0]
        longitude_distance = corner_2[1]-corner_1[1]
        centre = dict(latitude=corner_1[0] + latitude_distance / 2,
                      longitude=corner_1[1] + longitude_distance / 2)
        return centre, shortest_side, longest_side

    def game_zone_coordinates_to_float(self, game_zone_coordinates):
        """
        Converts coordinates in a game_zone_coordinates object to floats
        :param game_zone_coordinates: game_zone_coordinates
        :return: game_zone_coordinates where coordinate values are float
        """
        if game_zone_coordinates:
            return dict(c1=self.coordinate_to_float(game_zone_coordinates['c1']),
                        c2=self.coordinate_to_float(game_zone_coordinates['c2']),
                        c3=self.coordinate_to_float(game_zone_coordinates['c3']),
                        c4=self.coordinate_to_float(game_zone_coordinates['c4']))

    def dump_game_zone_coordinates(self):
        """
        Dumps game_zone_coordinates to string coordinate values
        :return: dict containing game_zone_coordinates as strings
        """
        return dict(c1=self.coordinate_to_string(self.coordinates['c1']),
                    c2=self.coordinate_to_string(self.coordinates['c2']),
                    c3=self.coordinate_to_string(self.coordinates['c3']),
                    c4=self.coordinate_to_string(self.coordinates['c4']))
