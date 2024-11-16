import json
from channels.generic.websocket import AsyncWebsocketConsumer

class VicidialConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        # Get session_id from URL parameters
        self.session_id = self.scope['url_route']['kwargs']['session_id']
        self.group_name = f"vicidial_{self.session_id}"

        # Add the WebSocket connection to the group
        await self.channel_layer.group_add(
            self.group_name,
            self.channel_name
        )

        # Accept the WebSocket connection
        await self.accept()

        # Send a welcome message to the WebSocket client
        await self.send(text_data=json.dumps({
            'message': 'Connected to WebSocket'
        }))

    async def disconnect(self, close_code):
        # Remove the WebSocket connection from the group
        await self.channel_layer.group_discard(
            self.group_name,
            self.channel_name
        )

    async def send_data(self, event):
        # Receive data from group_send and send it to WebSocket
        data = event["data"]
        await self.send(text_data=json.dumps(data))
