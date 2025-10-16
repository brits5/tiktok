import asyncio
from TikTokLive import TikTokLiveClient
from TikTokLive.events import CommentEvent, GiftEvent, ConnectEvent, DisconnectEvent
from typing import Callable, List

class TikTokService:
    def __init__(self, unique_id: str):
        self.client = TikTokLiveClient(unique_id=unique_id)
        self.callbacks: List[Callable] = []
        self.is_connected = False
        self._setup_handlers()
    
    def _setup_handlers(self):
        @self.client.on(ConnectEvent)
        async def on_connect(event):
            self.is_connected = True
            await self._broadcast({
                "type": "system",
                "message": "Conectado al live",
                "room_id": self.client.room_id
            })
        
        @self.client.on(DisconnectEvent)
        async def on_disconnect(event):
            self.is_connected = False
            await self._broadcast({
                "type": "system",
                "message": "Desconectado del live"
            })
        
        @self.client.on(CommentEvent)
        async def on_comment(event: CommentEvent):
            data = {
                "type": "comment",
                "unique_id": event.user.unique_id,
                "nickname": event.user.nickname,
                "comment": event.comment,
                "timestamp": event.timestamp
            }
            await self._broadcast(data)
        
        @self.client.on(GiftEvent)
        async def on_gift(event: GiftEvent):
            data = {
                "type": "gift",
                "unique_id": event.user.unique_id,
                "nickname": event.user.nickname,
                "gift_name": event.gift.name,
                "gift_id": event.gift.id,
                "repeat_count": event.gift.repeat_count,
                "cost": event.gift.diamond_count,
                "streaking": event.streaking,
                "repeat_end": event.repeat_end,
                "timestamp": event.timestamp
            }
            await self._broadcast(data)
    
    async def _broadcast(self, data: dict):
        """Envía datos a todos los callbacks registrados"""
        for callback in self.callbacks:
            try:
                await callback(data)
            except Exception as e:
                print(f"Error en callback: {e}")
    
    def register_callback(self, callback: Callable):
        """Registra un callback para recibir eventos"""
        self.callbacks.append(callback)
    
    def unregister_callback(self, callback: Callable):
        """Elimina un callback"""
        if callback in self.callbacks:
            self.callbacks.remove(callback)
    
    async def start(self):
        """Inicia la conexión con TikTok"""
        await self.client.start()
    
    async def stop(self):
        """Detiene la conexión"""
        await self.client.disconnect()