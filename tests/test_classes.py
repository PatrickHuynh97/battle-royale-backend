import json
import uuid


class MockQueue:
    """
    Basic queue that allows the user to mock the behavior of a SQS.
    """

    def __init__(self, *args, **kwargs):
        self.records = []

    def send_message(self, message, delay):
        receipt_handle = uuid.uuid4()
        self.records.append({
            'receiptHandle': receipt_handle.hex,
            'body': json.dumps(message),
            'delay': delay
        })
        return receipt_handle

    def delete_message(self, receipt):
        pass
