import json
import os

import boto3


class SqsQueue:
    """
    SQS queue class that abstracts interacting with an SQS queue
    """

    def __init__(self):
        """
        Create SQS queue based off of SQS URL in the environment
        """
        self.queue = boto3.client('sqs')
        self.url = os.getenv('SQS_URL')

    def send_message(self, message: dict, delay=None):
        """
        Send a message to the SQS queue
        :param message: message to be enqueued
        :param delay: message to be enqueued
        """
        self.queue.send_message(QueueUrl=self.url,
                                MessageBody=json.dumps(message),
                                DelaySeconds=delay)

    def delete_message(self, receipt_handle):
        """
        Delete message from the queue given its receipt handle
        :param receipt_handle: handle of the message to delete
        """
        self.queue.delete_message(QueueUrl=self.url,
                                  ReceiptHandle=receipt_handle)
