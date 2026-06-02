FROM python:3.12-slim

WORKDIR /app
COPY app ./app

ENV HOST=0.0.0.0
ENV PORT=8000
ENV DATABASE_URL=/data/links.db

EXPOSE 8000
CMD ["python", "-m", "app.main"]
