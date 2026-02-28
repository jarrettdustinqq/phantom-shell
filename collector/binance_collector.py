import asyncio
import json
import os
from datetime import datetime, timezone

import websockets

SYMBOL = os.getenv("BINANCE_SYMBOL", "btcusdt")
INTERVAL = os.getenv("BINANCE_INTERVAL", "1m")
DATA_PATH = os.getenv("DATA_PATH", "/data")


async def stream_candles() -> None:
    url = (
        f"wss://stream.binance.com:9443/ws/{SYMBOL}@kline_{INTERVAL}"
    )
    output_file = os.path.join(DATA_PATH, f"{SYMBOL}_klines.csv")
    os.makedirs(DATA_PATH, exist_ok=True)

    async with websockets.connect(url) as websocket, open(
        output_file, "a", encoding="utf-8"
    ) as handle:
        while True:
            message = await websocket.recv()
            payload = json.loads(message)
            kline = payload.get("k", {})
            if not kline:
                continue

            close_time = datetime.fromtimestamp(
                kline["T"] / 1000, tz=timezone.utc
            ).isoformat()
            row = ",".join(
                [
                    close_time,
                    str(kline.get("o")),
                    str(kline.get("h")),
                    str(kline.get("l")),
                    str(kline.get("c")),
                    str(kline.get("v")),
                ]
            )
            handle.write(row + "\n")
            handle.flush()


if __name__ == "__main__":
    asyncio.run(stream_candles())
