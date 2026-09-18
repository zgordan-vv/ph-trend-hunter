FROM python:3.11-slim

WORKDIR /app

# Copy application files
COPY . /app

# Expose web dashboard port
EXPOSE 8000

ENV PORT=8000
ENV PYTHONUNBUFFERED=1

CMD ["python3", "server.py"]
