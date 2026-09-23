FROM python:3.12-slim
WORKDIR /service
COPY pyproject.toml requirements.lock ./
RUN pip install --no-cache-dir -r requirements.lock
COPY app ./app
COPY alembic ./alembic
COPY alembic.ini .
RUN pip install --no-cache-dir --no-deps . && useradd --create-home driveeval && chown -R driveeval:driveeval /service
USER driveeval
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
