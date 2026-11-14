# Image de l'application : API FastAPI + interface web (frontend/)
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    DAAR_DB=/app/data/index.db

WORKDIR /app

# 1. Les dépendances d'abord : cette couche n'est reconstruite que si requirements.txt change
COPY backend/requirements.txt backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt

# 2. Le code (le corpus et l'index ne sont PAS dans l'image : ils sont montés depuis ./data)
COPY backend backend
COPY frontend frontend

WORKDIR /app/backend
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
