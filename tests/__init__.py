""" When the tests are run, automatically start and stop a docker container
running a Dynamo DB on localhost.

The server runs at port 8005 to avoid conflicts with other services.
"""
import atexit
import docker


def initialize_package():
    """ Start a docker container running Dynamo DB and register a function that
    stops the container when the program exits.
    """
    client = docker.client.from_env()
    container = _run_database_container(client)
    atexit.register(_stop_database_container, container)


def _run_database_container(client, port='8005'):
    """ Start a docker container running Dynamo DB on port 8005.

    :param client: Docker client

    :return: Docker container object
    """

    try:
        return client.containers.run('amazon/dynamodb-local',
                                     command='-jar DynamoDBLocal.jar -inMemory -sharedDb',
                                     ports={'8000': port},
                                     detach=True)

    except docker.errors.APIError as error:
        print(error)
        print(f'Please make sure that nothing is running on localhost:{port}')
        exit(1)


def _stop_database_container(container):
    """ Stop a container or kill it if it fails.
    """
    try:
        container.stop()
    except docker.errors.APIError:
        container.kill()


initialize_package()
