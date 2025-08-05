import json
from channels.generic.websocket import AsyncWebsocketConsumer
from django.contrib.auth.models import AnonymousUser
from .models import SupportMessage, SupportTicket, UserStatus, PrestigeSettings
from django.core.exceptions import ObjectDoesNotExist
from channels.db import database_sync_to_async
from datetime import datetime


class ChatConsumer(AsyncWebsocketConsumer):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.ticket_id = None
        self.ticket_group_name = None
        self.user = None

    async def connect(self):
        self.ticket_id = self.scope['url_route']['kwargs']['ticket_id']
        self.ticket_group_name = f'chat_{self.ticket_id}'
        self.user = self.scope['user']

        if isinstance(self.user, AnonymousUser):
            await self.close(code=4001)
            return

        try:
            ticket = await self.get_ticket(self.ticket_id)
            if not await self.validate_user_access(ticket):
                await self.close(code=4003)
                return
        except ObjectDoesNotExist:
            await self.close(code=4004)
            return

        await self.update_user_status('ONLINE')
        await self.channel_layer.group_add(self.ticket_group_name, self.channel_name)
        await self.accept()

        # Send initial unread count
        unread_count = await self.get_unread_count(ticket)
        await self.send(text_data=json.dumps({
            'type': 'initial_data',
            'unread_count': unread_count
        }))

    async def disconnect(self, close_code):
        if hasattr(self, 'ticket_group_name') and self.ticket_group_name:
            await self.channel_layer.group_discard(self.ticket_group_name, self.channel_name)
        await self.update_user_status('OFFLINE')

    async def receive(self, text_data):
        try:
            data = json.loads(text_data)
            event_type = data.get('type')

            handlers = {
                'chat_message': self.handle_chat_message,
                'typing': self.handle_typing,
                'mark_read': self.handle_mark_read,
                'ping': self.handle_ping
            }

            if handler := handlers.get(event_type):
                await handler(data)
            else:
                await self.send_error('Invalid message type')

        except json.JSONDecodeError:
            await self.send_error('Invalid JSON format')
        except Exception as e:
            await self.send_error(f'Server error: {str(e)}')

    async def handle_chat_message(self, data):
        message = data.get('message', '').strip()
        if not message:
            return await self.send_error('Message cannot be empty')

        try:
            ticket = await self.get_ticket(self.ticket_id)
            is_admin = ticket.user != self.user
            receiver = None if not is_admin else await PrestigeSettings.get_support_user()

            message_obj = await self.create_message(
                ticket=ticket,
                sender=self.user,
                receiver=receiver,
                message=message
            )

            await self.channel_layer.group_send(
                self.ticket_group_name,
                {
                    'type': 'chat_message',
                    'message': message,
                    'sender_id': self.user.id,
                    'sender_name': self.user.get_full_name(),
                    'timestamp': message_obj.created_at.isoformat(),
                    'is_admin': is_admin
                }
            )

        except ObjectDoesNotExist:
            await self.send_error('Ticket not found')
        except Exception as e:
            await self.send_error(f'Failed to send message: {str(e)}')

    async def handle_typing(self, data):
        try:
            await self.channel_layer.group_send(
                self.ticket_group_name,
                {
                    'type': 'typing',
                    'user_id': self.user.id,
                    'user_name': self.user.get_full_name(),
                    'is_typing': bool(data.get('is_typing', False))
                }
            )
        except Exception as e:
            await self.send_error(f'Typing indicator error: {str(e)}')

    async def handle_mark_read(self):
        try:
            ticket = await self.get_ticket(self.ticket_id)
            await self.mark_messages_as_read(ticket)
        except ObjectDoesNotExist:
            await self.send_error('Ticket not found')

    async def handle_ping(self, data):
        await self.send(text_data=json.dumps({
            'type': 'pong',
            'timestamp': datetime.now().isoformat()
        }))

    async def chat_message(self, event):
        await self.send(text_data=json.dumps({
            'type': 'chat_message',
            'message': event['message'],
            'sender_id': event['sender_id'],
            'sender_name': event['sender_name'],
            'timestamp': event['timestamp'],
            'is_admin': event['is_admin']
        }))

    async def typing(self, event):
        await self.send(text_data=json.dumps({
            'type': 'typing',
            'user_id': event['user_id'],
            'user_name': event['user_name'],
            'is_typing': event['is_typing']
        }))

    async def send_error(self, message):
        await self.send(text_data=json.dumps({
            'type': 'error',
            'message': message
        }))

    @database_sync_to_async
    def get_ticket(self, ticket_id):
        return SupportTicket.objects.get(id=ticket_id)

    @database_sync_to_async
    def validate_user_access(self, ticket):
        return ticket.user == self.user or self.user.is_staff

    @database_sync_to_async
    def update_user_status(self, status):
        return UserStatus.objects.filter(user=self.user).update(status=status)

    @database_sync_to_async
    def create_message(self, ticket, sender, receiver, message):
        return SupportMessage.objects.create(
            ticket=ticket,
            sender=sender,
            receiver=receiver,
            message=message
        )

    @database_sync_to_async
    def mark_messages_as_read(self, ticket):
        return SupportMessage.objects.filter(
            ticket=ticket,
            is_read=False
        ).exclude(sender=self.user).update(is_read=True)

    @database_sync_to_async
    def get_unread_count(self, ticket):
        return SupportMessage.objects.filter(
            ticket=ticket,
            is_read=False
        ).exclude(sender=self.user).count()