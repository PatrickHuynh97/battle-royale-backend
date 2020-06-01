import sys
import boto3
import subprocess


def get_api_id(apis, environment):
    # gets the rest_api_id of the
    for api in apis:
        if environment in api['name']:
            return api['id']
    raise Exception("RestApiId could not be found")


if __name__ == "__main__":

    if len(sys.argv) == 1:
        environment = 'dev'
    elif sys.argv[1] == 'dev':
        print("Deploying to dev environment")
        environment = sys.argv[1]
    elif sys.argv[1] == 'stage':
        print("Deploying to stage environment")
        environment = sys.argv[1]
    elif sys.argv[1] == 'prod':
        print("Deploying to prod environment")
        environment = sys.argv[1]
    else:
        raise Exception("Invalid environment given")
    documentation_bucket = f"{environment}-documentation"

    bashCommand = f"sls deploy --noDeploy --stage {environment}".split()

    process = subprocess.Popen(bashCommand, stdout=subprocess.PIPE, shell=True)
    test = subprocess.Popen(["ping", "-W", "2", "-c", "1", "192.168.1.70"], stdout=subprocess.PIPE)
    output = test.communicate()[0]
    client = boto3.client('apigateway')
    apis = client.get_rest_apis()
    rest_api_id = get_api_id(apis['items'], environment)

    print(apis)