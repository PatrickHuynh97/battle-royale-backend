import json
import requests

from enums import LobbyState
from exceptions import UserDoesNotExistException, UserAlreadyExistsException, AuthorizationException, \
    SquadAlreadyExistsException, SquadDoesNotExistException, PlayerNotInLobbyException, LobbyDoesNotExistException, \
    GameMasterNotInLobbyException
from handlers.schemas import SquadSchema, LobbySchema

BASE_URL = "https://2jvljq6cs5.execute-api.eu-central-1.amazonaws.com/dev"


class TestApiException(Exception):
    pass


def sign_up_and_sign_in(username, password):
    try:
        return sign_in_user(username, password)
    except UserDoesNotExistException:
        try:
            sign_up_user(username, password)
            return sign_in_user(username, password)
        except UserAlreadyExistsException as e:
            raise e


def sign_in_user(username, password):
    # try to sign a user in
    url = BASE_URL + '/user-management/sign-in'
    res = requests.post(url, data=json.dumps({'username': username, 'password': password}))
    if res.status_code == 200:
        return json.loads(res.text)
    elif res.status_code >= 400:
        error = json.loads(res.text)
        if error['type'] == UserDoesNotExistException.tag:
            raise UserDoesNotExistException()


def sign_up_user(username, password):
    # try to sign a user up
    url = BASE_URL + '/user-management/sign-up'
    res = requests.post(url, data=json.dumps({'username': username,
                                              'password': password,
                                              'email': f"{username}@gmail.com"}))
    if res.status_code == 200:
        return
    elif res.status_code == 400:
        error = json.loads(res.text)
        if error['type'] == UserDoesNotExistException.tag:
            sign_up_user(username, password)


def delete_user(id_token, access_token, force=False):
    url = BASE_URL + '/user-management/delete-user'
    res = requests.post(url,
                        data=json.dumps({'access_token': access_token}),
                        headers=dict(Authorization=id_token))
    if res.status_code == 200:
        return json.loads(res.text)
    elif 400 <= res.status_code <= 500:
        if not force:
            error = json.loads(res.text)
            raise AuthorizationException(error)


def refresh_tokens(refresh_token):
    url = BASE_URL + '/user-management/refresh'
    res = requests.post(url, data=json.dumps({'refresh_token': refresh_token}))
    if res.status_code == 200:
        return json.loads(res.text)


def test_user_management(username, password):
    tokens = sign_up_and_sign_in(username, password)
    refreshed_tokens = refresh_tokens(tokens['refresh_token'])
    delete_user(refreshed_tokens['id_token'], refreshed_tokens['access_token'])
    try:
        sign_in_user(username, password)
    except UserDoesNotExistException:
        print("Sign up, refresh, and delete user all successful")
        return
    raise TestApiException("Test user management failed")


def create_squad(id_token, squad_name):
    url = BASE_URL + '/player/squads/' + squad_name
    res = requests.post(url, headers=dict(Authorization=id_token))
    if res.status_code == 200:
        return json.loads(res.text)
    elif res.status_code == 400:
        error = json.loads(res.text)
        if error['type'] == SquadAlreadyExistsException.tag:
            raise SquadAlreadyExistsException()


def delete_squad(id_token, squad_name):
    url = BASE_URL + '/player/squads/' + squad_name
    res = requests.delete(url, headers=dict(Authorization=id_token))
    if res.status_code == 200:
        return json.loads(res.text)
    elif res.status_code == 400:
        error = json.loads(res.text)
        if error['type'] == SquadDoesNotExistException.tag:
            raise SquadDoesNotExistException()


def add_member_to_squad(id_token, squad_name, username):
    url = BASE_URL + f'/player/squads/{squad_name}/member/{username}'
    res = requests.post(url, headers=dict(Authorization=id_token))
    if res.status_code == 200:
        return json.loads(res.text)
    elif res.status_code >= 400:
        error = json.loads(res.text)
        if error['type'] == SquadDoesNotExistException.tag:
            raise SquadDoesNotExistException()
    else:
        raise Exception("something went wrong")


def get_owned_squads(id_token):
    url = BASE_URL + '/player/squads/me'
    res = requests.get(url, headers=dict(Authorization=id_token))
    if res.status_code == 200:
        return SquadSchema().loads(res.text, many=True)
    else:
        raise Exception(f"Failed to get owned squads: {res.text}")


def get_not_owned_squads(id_token):
    url = BASE_URL + '/player/squads/others'
    res = requests.get(url, headers=dict(Authorization=id_token))
    if res.status_code == 200:
        return SquadSchema().loads(res.text, many=True)
    else:
        raise Exception("Failed to get not-owned squads")


def test_player_squad(player_1_username, password):

    player_1_tokens = sign_up_and_sign_in(player_1_username, password)
    player_2_username = "integration-test-user-2"
    player_2_tokens = sign_up_and_sign_in(player_2_username, "second_player_password")
    player_1_id_token = player_1_tokens['id_token']
    player_2_id_token = player_2_tokens['id_token']
    try:
        p1_squad_name = "player_1_squad"
        p2_squad_name = "player_2_squad"

        # create squad as player_1, retrieve owned squads and assert that said squad is there
        create_squad(player_1_id_token, squad_name=p1_squad_name)
        owned_squads = get_owned_squads(player_1_id_token)
        assert (len(owned_squads) == 1)
        assert (len(owned_squads[0]['members']) == 1)
        assert (owned_squads[0]['members'][0]['username'] == player_1_username)
        assert (owned_squads[0]['owner'] == player_1_username)
        assert (owned_squads[0]['name'] == p1_squad_name)

        # create squad as player_2, retrieve owned squads and assert that said squad is there
        create_squad(player_2_id_token, squad_name=p2_squad_name)
        owned_squads = get_owned_squads(player_2_id_token)
        assert (len(owned_squads) == 1)
        assert (len(owned_squads[0]['members']) == 1)
        assert (owned_squads[0]['members'][0]['username'] == player_2_username)
        assert (owned_squads[0]['owner'] == player_2_username)
        assert (owned_squads[0]['name'] == p2_squad_name)

        # add player_2 to player_1 squad
        add_member_to_squad(player_1_id_token, p1_squad_name, player_2_username)
        owned_squads = get_owned_squads(player_1_id_token)
        assert (len(owned_squads[0]['members']) == 2)

        # add player_1 to player_2 squad
        add_member_to_squad(player_2_id_token, p2_squad_name, player_1_username)
        owned_squads = get_owned_squads(player_2_id_token)
        assert (len(owned_squads[0]['members']) == 2)

        player_1_not_owned_squads = get_not_owned_squads(player_1_id_token)
        assert (len(player_1_not_owned_squads) == 1)
        assert (len(player_1_not_owned_squads[0]['members']) == 2)
        assert (player_1_not_owned_squads[0]['owner'] == player_2_username)

        player_2_not_owned_squads = get_not_owned_squads(player_2_id_token)
        assert (len(player_2_not_owned_squads) == 1)
        assert (len(player_2_not_owned_squads[0]['members']) == 2)
        assert (player_2_not_owned_squads[0]['owner'] == player_1_username)

        # delete created squad and make sure it was actually deleted
        delete_squad(player_1_id_token, p1_squad_name)
        owned_squads = get_owned_squads(player_1_id_token)
        assert (len(owned_squads) == 0)

        player_2_not_owned_squads = get_not_owned_squads(player_2_tokens['id_token'])
        assert (len(player_2_not_owned_squads) == 0)
        player_2_owned_squads = get_owned_squads(player_2_id_token)
        assert (len(player_2_owned_squads) == 1)
        assert (len(player_2_owned_squads[0]['members']) == 2)

        delete_user(player_1_tokens['id_token'], player_1_tokens['access_token'])
        delete_user(player_2_tokens['id_token'], player_2_tokens['access_token'])

        print("Creating Squad, adding members, and retrieving squads all successful")

    except Exception as e:
        delete_user(player_1_tokens['id_token'], player_1_tokens['access_token'], force=True)
        delete_user(player_2_tokens['id_token'], player_2_tokens['access_token'], force=True)
        print("Something went wrong when testing squads")


def create_lobby(id_token, name, lobby_size, squad_size):
    data = json.dumps({'name': name, 'lobby_size': lobby_size, 'squad_size': squad_size})
    url = BASE_URL + '/game-master/lobby'
    res = requests.post(url, headers=dict(Authorization=id_token), data=data)
    if res.status_code == 200:
        return json.loads(res.text)
    else:
        raise Exception("Failed to create lobby")


def delete_lobby(id_token, lobby_name, force=False):
    url = BASE_URL + '/game-master/lobby/' + lobby_name
    res = requests.delete(url, headers=dict(Authorization=id_token))
    if res.status_code == 200:
        return json.loads(res.text)
    else:
        if not force:
            raise Exception("Failed to delete lobby")


def game_master_get_current_lobby(id_token):
    url = BASE_URL + '/game-master/lobby'
    res = requests.get(url, headers=dict(Authorization=id_token))
    if res.status_code == 200:
        return LobbySchema().loads(res.text)
    elif 400 <= res.status_code <= 500:
        error = json.loads(res.text)
        if error['type'] == GameMasterNotInLobbyException.tag:
            raise GameMasterNotInLobbyException()


def integration_add_squad_to_lobby(id_token, lobby_name, squad_name):
    url = BASE_URL + f'/game-master/lobby/{lobby_name}/squads/{squad_name}'
    res = requests.post(url, headers=dict(Authorization=id_token))
    if res.status_code == 200:
        return json.loads(res.text)
    elif 400 <= res.status_code <= 500:
        error = json.loads(res.text)
        if error['type'] == LobbyDoesNotExistException.tag:
            raise LobbyDoesNotExistException()


def integration_remove_squad_from_lobby(id_token, lobby_name, squad_name):
    url = BASE_URL + f'/game-master/lobby/{lobby_name}/squads/{squad_name}'
    res = requests.delete(url, headers=dict(Authorization=id_token))
    if res.status_code == 200:
        return json.loads(res.text)
    else:
        raise Exception("Failed to remove squad from lobby")


def player_get_current_lobby(id_token):
    url = BASE_URL + f'/player/lobby'
    res = requests.get(url, headers=dict(Authorization=id_token))
    if res.status_code == 200:
        return LobbySchema().loads(res.text)
    elif 400 <= res.status_code <= 500:
        error = json.loads(res.text)
        if error['type'] == PlayerNotInLobbyException.tag:
            raise PlayerNotInLobbyException()


def integration_pull_squad_from_lobby(id_token, squad_name):
    url = BASE_URL + f'/player/squads/{squad_name}/leave-lobby'
    res = requests.post(url, headers=dict(Authorization=id_token))
    if res.status_code == 200:
        return json.loads(res.text)
    else:
        raise Exception("Failed to get lobby")


def test_gamemaster_lobby(gm_username, password):
    # create account for game master
    game_master_tokens = sign_up_and_sign_in(gm_username, password)
    game_master_id_token = game_master_tokens['id_token']

    # create squad with 2 players in it
    player_1_username = "integration-test-player-1"
    player_2_username = "integration-test-player-2"
    player_1_tokens = sign_up_and_sign_in(player_1_username, password)
    player_2_tokens = sign_up_and_sign_in(player_2_username, password)
    player_1_id_token = player_1_tokens['id_token']
    lobby_name = "integration-test-lobby-1"

    try:
        squad_name = "player_1_squad"
        create_squad(player_1_id_token, squad_name=squad_name)
        add_member_to_squad(player_1_id_token, squad_name, player_2_username)
        owned_squads = get_owned_squads(player_1_id_token)
        assert (len(owned_squads[0]['members']) == 2)

        # create lobby which allows squad size of 2 in
        lobby_size = 5
        squad_size = 2
        create_lobby(game_master_id_token, lobby_name, lobby_size=lobby_size, squad_size=squad_size)

        current_lobby = game_master_get_current_lobby(game_master_id_token)
        assert(current_lobby['name'] == lobby_name)
        assert(current_lobby['owner'] == gm_username)
        assert(current_lobby['size'] == lobby_size)
        assert(current_lobby['squad_size'] == squad_size)
        assert(current_lobby['state'] == LobbyState.NOT_STARTED.value)
        assert(len(current_lobby['squads']) == 0)

        integration_add_squad_to_lobby(game_master_id_token, lobby_name, squad_name)
        current_lobby = game_master_get_current_lobby(game_master_id_token)
        assert(len(current_lobby['squads']) == 1)
        assert(current_lobby['squads'][0]['name'] == squad_name)

        current_lobby_player_1 = player_get_current_lobby(player_1_id_token)
        current_lobby_player_2 = player_get_current_lobby(player_2_tokens['id_token'])
        assert(current_lobby_player_1['name'] == lobby_name)
        assert(current_lobby_player_2['name'] == lobby_name)

        integration_pull_squad_from_lobby(player_1_id_token, squad_name)

        try:
            player_get_current_lobby(player_1_id_token)
        except PlayerNotInLobbyException:
            pass
        try:
            player_get_current_lobby(player_2_tokens['id_token'])
        except PlayerNotInLobbyException:
            pass
        current_lobby = game_master_get_current_lobby(game_master_id_token)
        assert(len(current_lobby['squads']) == 0)

        delete_lobby(game_master_tokens['id_token'], lobby_name)

        try:
            game_master_get_current_lobby(game_master_id_token)
        except GameMasterNotInLobbyException:
            pass

        delete_user(game_master_tokens['id_token'], game_master_tokens['access_token'])
        delete_user(player_1_tokens['id_token'], player_1_tokens['access_token'])
        delete_user(player_2_tokens['id_token'], player_2_tokens['access_token'])

        print("Creating Lobby, adding squads, and updating lobby all successful")

    except Exception as e:
        # something went wrong, clean up
        delete_lobby(game_master_tokens['id_token'], lobby_name, force=True)
        delete_user(game_master_tokens['id_token'], game_master_tokens['access_token'], force=True)
        delete_user(player_1_tokens['id_token'], player_1_tokens['access_token'], force=True)
        delete_user(player_2_tokens['id_token'], player_2_tokens['access_token'], force=True)
        raise Exception("Failed to test game master")


if __name__ == "__main__":
    test_player = "integration-test-player-1"
    test_game_master = "integration-test-gamemaster-1"
    password = "poo123456"

    test_user_management(test_player, password)

    test_player_squad(test_player, password)

    test_gamemaster_lobby(test_game_master, password)
