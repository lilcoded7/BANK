import json
from channels.generic.websocket import AsyncWebsocketConsumer
from django.contrib.auth.models import AnonymousUser
from .models import SupportMessage, SupportTicket, UserStatus, PrestigeSettings


class ChatConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.ticket_id = self.scope['url_route']['kwargs']['ticket_id']
        self.ticket_group_name = f'chat_{self.ticket_id}'
        self.user = self.scope['user']

        # Reject unauthenticated users
        if isinstance(self.user, AnonymousUser):
            await self.close()
            return

        # Join group
        await self.channel_layer.group_add(self.ticket_group_name, self.channel_name)

        # Update user status to online
        if hasattr(self.user, 'status'):
            await UserStatus.objects.filter(user=self.user).aupdate(status='ONLINE')

        await self.accept()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(self.ticket_group_name, self.channel_name)

        if hasattr(self.user, 'status'):
            await UserStatus.objects.filter(user=self.user).aupdate(status='OFFLINE')

    async def receive(self, text_data):
        data = json.loads(text_data)
        event_type = data.get('type')

        if event_type == 'chat_message':
            await self.handle_chat_message(data)

        elif event_type == 'typing':
            await self.handle_typing(data)

        elif event_type == 'mark_read':
            await self.handle_mark_read()

    async def handle_chat_message(self, data):
        message = data.get('message')
        ticket_id = self.ticket_id

        try:
            ticket = await SupportTicket.objects.aget(id=ticket_id)
        except SupportTicket.DoesNotExist:
            await self.send(text_data=json.dumps({
                'error': 'Ticket not found.'
            }))
            return

        # Determine if it's an admin or user
        is_admin = not ticket.user == self.user

        # Save message
        message_obj = await SupportMessage.objects.acreate(
            ticket=ticket,
            sender=self.user,
            receiver=None if not is_admin else PrestigeSettings.load().user,
            message=message
        )

        # Broadcast to group
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

    async def handle_typing(self, data):
        await self.channel_layer.group_send(
            self.ticket_group_name,
            {
                'type': 'typing',
                'user_id': self.user.id,
                'username': self.user.username,
                'is_typing': data.get('is_typing', False)
            }
        )

    async def handle_mark_read(self):
        try:
            ticket = await SupportTicket.objects.aget(id=self.ticket_id)
            await SupportMessage.objects.filter(
                ticket=ticket,
                is_read=False,
            ).exclude(sender=self.user).aupdate(is_read=True)
        except SupportTicket.DoesNotExist:
            pass

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
            'is_typing': event['is_typing'],
        }))

    async def send_user_status(self, event):
        await self.send(text_data=json.dumps({
            'type': 'status_update',
            'status': event['status']
        }))
