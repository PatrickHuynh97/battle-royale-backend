import json
import requests
from exceptions import UserDoesNotExistException, UserAlreadyExistsException, AuthorizationException, \
    SquadAlreadyExistsException, SquadDoesNotExistException
from handlers.schemas import SquadSchema

BASE_URL = "https://ffh4p5qi99.execute-api.eu-central-1.amazonaws.com/dev"


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


def delete_user(id_token, access_token):
    url = BASE_URL + '/user-management/delete-user'
    res = requests.post(url,
                        data=json.dumps({'access_token': access_token}),
                        headers=dict(Authorization=id_token))
    if res.status_code == 200:
        return json.loads(res.text)
    elif res.status_code == 400:
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
    elif res.status_code == 400:
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
        raise Exception("Failed to get owned squads")


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


if __name__ == "__main__":
    username = "integration-test-user-1"
    password = "poo123456"

    #test_user_management(username, password)

    test_player_squad(username, password)
