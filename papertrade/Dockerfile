FROM debian:bookworm-slim
RUN apt-get update && apt-get install -y bash awk bc && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY analyze_trades.sh .
RUN chmod +x analyze_trades.sh
VOLUME ["/data"]
CMD ["/bin/bash", "/app/analyze_trades.sh"]
