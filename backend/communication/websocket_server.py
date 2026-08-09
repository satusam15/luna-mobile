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

        server = await websockets.serve(

            self.handler,

            "localhost",

            8765

        )

        print("🚀 WebSocket Running")

        await server.wait_closed()