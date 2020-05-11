import json


def make_test_event(body=None, path_params=None, headers=None):
    return {
        "body": json.dumps(body) if body else '{}',
        "pathParameters": path_params if path_params else {},
        "headers": headers if headers else {},
    }


def make_lambda_call(method, event):
    res = method(event, None)
    return json.loads(res["body"])
