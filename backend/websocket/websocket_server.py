import asyncio
import websockets


class WebSocketServer:

    def __init__(self):

        self.clients = set()

    async def handler(self, websocket):

        self.clients.add(websocket)

        print("🟢 Electron Connected")

        try:

            async for message in websocket:
                print(message)

        finally:

            self.clients.remove(websocket)

            print("🔴 Electron Disconnected")

    async def send(self, message):

        if self.clients:

            await asyncio.gather(

                *[client.send(message) for client in self.clients]

            )

    async def start(self):
        try:
            server = await websockets.serve(
                self.handler,
                "127.0.0.1",
                8765
            )

            print("🚀 WebSocket Running on 127.0.0.1:8765")

            await server.wait_closed()

        except Exception as e:
            print("❌ WebSocket Error:", e)