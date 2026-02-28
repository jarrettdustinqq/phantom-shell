FROM debian:bookworm-slim
RUN apt-get update && apt-get install -y bash curl jq bc && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY price_check.sh .
RUN chmod +x price_check.sh
VOLUME ["/data", "/config"]
ENV OPENAI_API_KEY=""
CMD ["/bin/bash", "-lc", "/app/price_check.sh"]
