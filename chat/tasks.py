from celery import shared_task


@shared_task()
def proof_of_concept_task(*args, **kwargs):
    print(f"Proof of concept task executed with args={args} and kwargs={kwargs}.")
