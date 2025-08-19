from fastapi import APIRouter, HTTPException, Response, Query
import requests
from io import BytesIO
from PIL import Image


image_router = APIRouter(
    responses={404: {"description": "Not found"}},
)

# return optimized image thumbnail for the image url recieved in url params
@image_router.get("/proxy-image")
async def get_image_thumbnail(url: str, width:int = 300):
    try:
        resp = requests.get(url, timeout=5)
        image = Image.open(BytesIO(resp.content))
        image.thumbnail((width, width))
        thumb_io = BytesIO()
        image.save(thumb_io, format="JPEG", quality=50)
        thumb_io.seek(0)
        return Response(content=thumb_io.getvalue(), media_type="image/jpeg")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
