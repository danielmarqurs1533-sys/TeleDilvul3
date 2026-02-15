from fastapi import FastAPI, HTTPException, Request
from telethon import TelegramClient
from telethon.sessions import StringSession
import os
import uvicorn

app = FastAPI()

# Configuração do Telegram
API_ID = int(os.environ.get("API_ID", "37601553"))
API_HASH = os.environ.get("API_HASH", "77a223dde9c4b04c9d2189c16a02afff")
SESSION_STRING = os.environ.get("SESSION_STRING", "1AZWarzQBu5f31XrVOYPbF0K4l1P298MDlScVZ92c6dLjvhD6i0TudiUIPIqUdSzg3zOsbBPz9tD40eVGFu88Ndb9DxS37VKLIXjjBce0wLeQwtWLVQ7gaJPicsUDadSblPk5z8lxS68rPWHDizx2357MUj36k2rv3YLB3-gMWtlCQ58NjVu-uLkuw_McE60NannndxXc9P4jO9KEYdG2nRQsTmuADMbB9sa92GKsN0IY2iNmomgcp9rKVz2h0a8i9szqa6ZDEUN0hK6wJXqaMsi00yTUA2HBsWQnmpBS4bz2-cZPdyNMhkO8BJkvTuJgVtQJSZmdrTNU2MUCFgI9dcNnKP_-NS0=

")

client = TelegramClient(StringSession(SESSION_STRING), API_ID, API_HASH)


@app.on_event("startup")
async def startup():
    await client.connect()
    if not await client.is_user_authorized():
        raise Exception("Session string inválida! Gere uma nova.")
    me = await client.get_me()
    print(f"✅ Logado como: {me.first_name} ({me.id})")


@app.get("/health")
async def health():
    me = await client.get_me()
    return {"status": "ok", "user": me.first_name, "user_id": me.id}


@app.post("/send")
async def send_message(request: Request):
    """Envia mensagem para um usuário/canal."""
    data = await request.json()
    username = data.get("username")
    message = data.get("message")

    if not username or not message:
        raise HTTPException(status_code=400, detail="username and message required")

    try:
        entity = await client.get_entity(username)
        sent = await client.send_message(entity, message)
        return {"success": True, "message_id": sent.id, "to": username}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/forward")
async def forward_message(request: Request):
    """Encaminha mensagem de um canal para outro."""
    params = request.query_params
    from_chat = params.get("from_chat")
    message_id = params.get("message_id")
    to_username = params.get("to_username")

    if not all([from_chat, message_id, to_username]):
        raise HTTPException(status_code=400, detail="from_chat, message_id, to_username required")

    try:
        # Resolver entidades
        if from_chat.lstrip("-").isdigit():
            from_entity = int(from_chat)
        else:
            from_entity = await client.get_entity(from_chat)

        to_entity = await client.get_entity(to_username)

        # Encaminhar mensagem
        result = await client.forward_messages(to_entity, int(message_id), from_entity)

        msg_id = result.id if hasattr(result, 'id') else (result[0].id if isinstance(result, list) else None)
        return {"success": True, "message_id": msg_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/read-channel")
async def read_channel(request: Request):
    """Lê mensagens de um canal e busca texto específico."""
    data = await request.json()
    channel = data.get("channel")
    limit = data.get("limit", 20)
    search_text = data.get("search_text", "")

    if not channel:
        raise HTTPException(status_code=400, detail="channel is required")

    try:
        if isinstance(channel, str) and channel.lstrip("-").isdigit():
            entity = int(channel)
        else:
            entity = await client.get_entity(channel)

        messages = []
        found = False

        async for message in client.iter_messages(entity, limit=limit):
            msg_data = {
                "id": message.id,
                "date": str(message.date),
                "text": message.text or "",
                "has_media": message.media is not None,
            }
            messages.append(msg_data)

            if search_text and message.text and search_text in message.text:
                found = True

        return {
            "success": True,
            "found": found,
            "messages": messages,
            "channel": str(channel),
            "checked": len(messages),
        }
    except Exception as e:
        error_msg = str(e)
        if any(word in error_msg.lower() for word in ["privacy", "access", "invite", "private"]):
            raise HTTPException(status_code=403, detail=f"Sem acesso: {error_msg}")
        raise HTTPException(status_code=500, detail=error_msg)


@app.post("/fetch-channel-posts")
async def fetch_channel_posts(request: Request):
    """Busca posts recentes de um canal."""
    data = await request.json()
    channel = data.get("channel")
    limit = data.get("limit", 5)

    if not channel:
        raise HTTPException(status_code=400, detail="channel is required")

    try:
        if isinstance(channel, str) and channel.lstrip("-").isdigit():
            entity = int(channel)
        else:
            entity = await client.get_entity(channel)

        posts = []
        async for message in client.iter_messages(entity, limit=limit):
            posts.append({
                "id": message.id,
                "date": str(message.date),
                "text": message.text or "",
                "has_media": message.media is not None,
                "link": f"https://t.me/{channel}/{message.id}" if isinstance(channel, str) else None,
            })

        return {"success": True, "posts": posts}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)

