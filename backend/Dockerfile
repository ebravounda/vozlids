FROM python:3.11-bookworm
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY requirements.txt .
RUN grep -v '^litellm' requirements.txt > /tmp/req.txt \
 && pip install --no-cache-dir -r /tmp/req.txt --extra-index-url https://d33sy5i8bnduwe.cloudfront.net/simple/
COPY . .
EXPOSE 8001
CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8001", "--proxy-headers", "--forwarded-allow-ips", "*"]
