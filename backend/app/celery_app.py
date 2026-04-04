# from celery import Celery
# import os

# celery = Celery(
#     "resume_optimizer",
#     broker=os.getenv("REDIS_URL", "redis://redis:6379/0"),
#     backend=os.getenv("REDIS_URL", "redis://redis:6379/0"),
# )

# celery.conf.update(
#     task_serializer="json",
#     result_serializer="json",
#     accept_content=["json"],
# )