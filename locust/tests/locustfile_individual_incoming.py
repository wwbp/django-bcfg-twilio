import itertools
import gevent
from locust import HttpUser, task, between
from locust.exception import StopUser


class IndividualUser(HttpUser):
    host = "https://dev.wwbp-bcfg-chatbot.org/"
    wait_time = between(0, 1)
    api_key = "hutiFn9nUhnq0DAYLX98c6XaXwyDRWZarZFrmzb9-5w"

    # how many messages **each** user should send
    messages_to_send = 10

    # global counter for deterministic user IDs
    user_id_counter = itertools.count(1)

    def on_start(self):
        self.user_num = next(self.user_id_counter)
        self.participant_id = f"user_{self.user_num}"
        self.messages_sent = 0

    @task
    def send_individual(self):
        # if we still have messages to send, fire one off
        if self.messages_sent < self.messages_to_send:
            payload = {
                "context": {
                    "school_name": f"School_{(self.user_num - 1) % 10 + 1}",
                    "school_mascot": f"Mascot_{(self.user_num - 1) % 5 + 1}",
                    "initial_message": f"Initial message for user {self.user_num}",
                    "week_number": 1,
                    "message_type": "initial",
                    "name": f"User_{self.user_num}",
                },
                "message": f"Ping {self.messages_sent + 1} from {self.participant_id}",
            }
            headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
            self.client.post(
                f"/api/participant/{self.participant_id}/incoming",
                json=payload,
                headers=headers,
                name="/participant/[id]/incoming",
            )
            self.messages_sent += 1
        else:
            # all this user's messages are done—sleep until
            # every user has sent theirs. We compute the total
            # needed from the CLI's user count * messages_to_send.
            total_needed = self.environment.runner.target_user_count * self.messages_to_send
            # wait without spinning CPU
            while self.environment.runner.stats.total.num_requests < total_needed:
                gevent.sleep(1)

            # now that everyone’s done, stop this user
            raise StopUser()
