import json


def make_lambda_proxy_integration_event(path_params, body, headers=None):
    """
    Helper function to create API Gateway event.
    :param path_params: Dict of path parameters
    :param body: Dict of data
    :param headers: Dict of headers
    :return: An API Gateway event
    """

    if headers is None:
        headers = {}
    return {
        'headers': headers,
        'pathParameters': path_params,
        'body': body
    }


class MockResource(object):
    """
    Mocks the boto3 resource object. The type of resource object returned depends on parameter, so this class holds
    functionality from different microservices, e.g. send_message from SQS and Object class from S3.
    """
    class Object:
        def __init__(self, bucket_name, new_fw_version):
            pass

        def load(self):
            return

    def __init__(self, resource):
        self.resource = resource
        self.message = None

    def get_queue_by_name(self, QueueName):
        return self

    def send_message(self, MessageBody):
        self.message = json.loads(MessageBody)

    def load(self):
        return None
