web: python main.py
worker: celery -A services.orchestrator.celery_app worker -Q agents,orchestrator,maintenance -c 3 --loglevel=info
clock: celery -A services.orchestrator.celery_app beat --loglevel=info --scheduler celery.beat.PersistentScheduler