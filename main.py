import asyncio
import json
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from typing import Set
from config import Config
from tiktok_client import TikTokService

app = FastAPI(title="TikTok Live Microservice")

# Instancia global del servicio TikTok
tiktok_service: TikTokService = None

# Conexiones WebSocket activas
active_connections: Set[WebSocket] = set()

# Buffer de últimos eventos (para nuevos clientes)
event_buffer = []
MAX_BUFFER_SIZE = 50


@app.on_event("startup")
async def startup_event():
    """Inicia el servicio de TikTok al arrancar"""
    global tiktok_service
    
    tiktok_service = TikTokService(unique_id=Config.TIKTOK_USERNAME)
    
    # Registrar callback para broadcast
    async def broadcast_to_websockets(data: dict):
        # Guardar en buffer
        event_buffer.append(data)
        if len(event_buffer) > MAX_BUFFER_SIZE:
            event_buffer.pop(0)
        
        # Enviar a todos los clientes conectados
        disconnected = set()
        for connection in active_connections:
            try:
                await connection.send_json(data)
            except:
                disconnected.add(connection)
        
        # Limpiar conexiones muertas
        active_connections.difference_update(disconnected)
    
    tiktok_service.register_callback(broadcast_to_websockets)
    
    # Iniciar conexión en background
    asyncio.create_task(tiktok_service.start())
    print(f"🚀 Conectando a TikTok Live: {Config.TIKTOK_USERNAME}")


@app.on_event("shutdown")
async def shutdown_event():
    """Detiene el servicio al cerrar"""
    if tiktok_service:
        await tiktok_service.stop()


@app.get("/")
async def root():
    """Página de prueba con WebSocket"""
    html = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>TikTok Live Monitor</title>
        <style>
            body { font-family: Arial; padding: 20px; background: #1a1a1a; color: #fff; }
            #events { 
                height: 500px; 
                overflow-y: auto; 
                border: 1px solid #333; 
                padding: 10px; 
                background: #000;
                font-size: 14px;
            }
            .event { 
                padding: 8px; 
                margin: 5px 0; 
                border-radius: 4px; 
            }
            .comment { background: #1e3a8a; }
            .gift { background: #9333ea; }
            .system { background: #15803d; }
            .status { 
                padding: 10px; 
                margin: 10px 0; 
                border-radius: 4px; 
                text-align: center;
                font-weight: bold;
            }
            .connected { background: #15803d; }
            .disconnected { background: #dc2626; }
        </style>
    </head>
    <body>
        <h1>🎥 TikTok Live Monitor</h1>
        <div id="status" class="status disconnected">Desconectado</div>
        <div id="events"></div>
        
        <script>
            const ws = new WebSocket("ws://localhost:8000/ws");
            const eventsDiv = document.getElementById("events");
            const statusDiv = document.getElementById("status");
            
            ws.onopen = () => {
                statusDiv.textContent = "🟢 Conectado al WebSocket";
                statusDiv.className = "status connected";
            };
            
            ws.onmessage = (event) => {
                const data = JSON.parse(event.data);
                const div = document.createElement("div");
                div.className = `event ${data.type}`;
                
                if (data.type === "comment") {
                    div.innerHTML = `
                        <strong>💬 ${data.nickname}</strong> (@${data.unique_id})<br>
                        ${data.comment}
                    `;
                } else if (data.type === "gift") {
                    div.innerHTML = `
                        <strong>🎁 ${data.nickname}</strong> (@${data.unique_id})<br>
                        Regalo: ${data.gift_name} x${data.repeat_count} (💎 ${data.cost})
                    `;
                } else if (data.type === "system") {
                    div.innerHTML = `<strong>🔔 ${data.message}</strong>`;
                }
                
                eventsDiv.insertBefore(div, eventsDiv.firstChild);
                
                // Limitar a 100 eventos
                while (eventsDiv.children.length > 100) {
                    eventsDiv.removeChild(eventsDiv.lastChild);
                }
            };
            
            ws.onclose = () => {
                statusDiv.textContent = "🔴 Desconectado del WebSocket";
                statusDiv.className = "status disconnected";
            };
        </script>
    </body>
    </html>
    """
    return HTMLResponse(content=html)


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket para streaming de eventos en tiempo real"""
    await websocket.accept()
    active_connections.add(websocket)
    
    # Enviar buffer de eventos recientes
    for event in event_buffer:
        try:
            await websocket.send_json(event)
        except:
            break
    
    try:
        while True:
            # Mantener conexión viva
            await websocket.receive_text()
    except WebSocketDisconnect:
        active_connections.remove(websocket)


@app.get("/api/status")
async def get_status():
    """Estado del servicio"""
    return {
        "connected": tiktok_service.is_connected if tiktok_service else False,
        "username": Config.TIKTOK_USERNAME,
        "active_websockets": len(active_connections),
        "buffered_events": len(event_buffer)
    }


@app.get("/api/events")
async def get_recent_events():
    """Últimos eventos (REST API)"""
    return {
        "events": event_buffer,
        "count": len(event_buffer)
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=Config.HOST, port=Config.PORT)