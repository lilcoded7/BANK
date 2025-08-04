import json
from channels.generic.websocket import AsyncWebsocketConsumer
from django.contrib.auth.models import AnonymousUser
from .models import SupportMessage, SupportTicket, UserStatus


class ChatConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.ticket_id = self.scope['url_route']['kwargs']['ticket_id']
        self.ticket_group_name = f'chat_{self.ticket_id}'
        self.user = self.scope['user']

        # Reject connection if user is not authenticated
        if isinstance(self.user, AnonymousUser):
            await self.close()
            return

        # Join ticket group
        await self.channel_layer.group_add(
            self.ticket_group_name,
            self.channel_name
        )

        # Update user status to online
        if hasattr(self.user, 'status'):
            await UserStatus.objects.filter(user=self.user).aupdate(status='ONLINE')

        await self.accept()

    async def disconnect(self, close_code):
        # Leave ticket group
        await self.channel_layer.group_discard(
            self.ticket_group_name,
            self.channel_name
        )

        # Update user status to offline
        if hasattr(self.user, 'status'):
            await UserStatus.objects.filter(user=self.user).aupdate(status='OFFLINE')

    async def send_user_status(self, event):
        await self.send(text_data=json.dumps({
            'type': 'status_update',
            'status': event['status']
        }))

    # Receive message from WebSocket
    async def receive(self, text_data):
        text_data_json = json.loads(text_data)
        message_type = text_data_json.get('type')

        if message_type == 'chat_message':
            message = text_data_json['message']
            
            # Save message to database
            ticket = await SupportTicket.objects.aget(id=self.ticket_id)
            message_obj = await SupportMessage.objects.acreate(
                ticket=ticket,
                sender=self.user,
                message=message
            )

            # Send message to ticket group
            await self.channel_layer.group_send(
                self.ticket_group_name,
                {
                    'type': 'chat_message',
                    'message': message,
                    'sender_id': self.user.id,
                    'sender_username': self.user.username,
                    'timestamp': str(message_obj.created_at),
                }
            )
        elif message_type == 'typing':
            # Broadcast typing indicator
            await self.channel_layer.group_send(
                self.ticket_group_name,
                {
                    'type': 'typing',
                    'user_id': self.user.id,
                    'username': self.user.username,
                    'is_typing': text_data_json['is_typing']
                }
            )

    
    async def chat_message(self, event):
        await self.send(text_data=json.dumps({
            'type': 'chat_message',
            'message': event['message'],
            'sender_id': event['sender_id'],
            'sender_username': event['sender_username'],
            'timestamp': event['timestamp'],
        }))

    async def typing(self, event):
        await self.send(text_data=json.dumps({
            'type': 'typing',
            'user_id': event['user_id'],
            'username': event['username'],
            'is_typing': event['is_typing']
        }))