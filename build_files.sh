#!/bin/bash

# Build the project
echo "Building the project..."
python -m pip install -r requirements.txt

echo "Make Migration..."
python manage.py makemigrations
python manage.py migrate

echo "Collect Static..."
python manage.py collectstatic --noinput --clear 