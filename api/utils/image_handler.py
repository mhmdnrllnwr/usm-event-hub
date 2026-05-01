import httpx
import os
import uuid

async def download_telegram_image(file_id: str, bot_token: str):
    if not file_id:
        return None

    async with httpx.AsyncClient() as client:
        # 1. Get the file path from Telegram
        get_file_url = f"https://api.telegram.org/bot{bot_token}/getFile?file_id={file_id}"
        resp = await client.get(get_file_url)
        file_path = resp.json()["result"]["file_path"]

        # 2. Download the actual file
        download_url = f"https://api.telegram.org/file/bot{bot_token}/{file_path}"
        image_resp = await client.get(download_url)

        # 3. Save locally with a unique name
        ext = file_path.split('.')[-1]
        filename = f"{uuid.uuid4()}.{ext}"
        save_path = os.path.join("static/posters", filename)

        with open(save_path, "wb") as f:
            f.write(image_resp.content)

        # Return the local URL path for the database
        return f"/static/posters/{filename}"