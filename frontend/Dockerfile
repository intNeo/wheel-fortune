FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt && useradd --uid 10001 --create-home app
COPY . .
RUN DJANGO_SECRET_KEY=collectstatic-only-key API_TOKEN=collectstatic-only-token-not-for-runtime WHEEL_ACCESS_TOKEN=collectstatic-only-token-not-for-runtime REDIS_URL=redis://127.0.0.1:6379/0 python manage.py collectstatic --noinput && chown -R app:app /app
USER app
EXPOSE 8000
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "--workers", "2", "--access-logfile", "-", "config.wsgi:application"]
