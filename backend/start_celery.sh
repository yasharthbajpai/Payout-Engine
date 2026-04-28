#!/bin/sh
# Runs Celery worker + beat together in one container (for Railway free tier)
celery -A app.worker.celery_app worker --loglevel=info --concurrency=4 &
celery -A app.worker.celery_app beat --loglevel=info &
wait
