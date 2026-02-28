FROM python:3.11-slim
WORKDIR /app
COPY binance_collector.py .
RUN pip install --no-cache-dir websockets
VOLUME ["/data"]
CMD ["python", "binance_collector.py"]
