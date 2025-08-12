from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
import os

GOOGLE_API_KEY = os.getenv('GOOGLE_SEARCH_API_KEY')
GOOGLE_CX = os.getenv('GOOGLE_SEARCH_CX')

def google_image_search(query, num_results=10):
    try:
        service = build("customsearch", "v1", developerKey=GOOGLE_API_KEY)
        response = service.cse().list(
            q=query,
            cx=GOOGLE_CX,
            num=num_results,
            searchType="image"
        ).execute()
        return response.get("items", [])
    except HttpError as e:
        print(f"Error occurred: {e}")
        return []
    
# to return unique image URLs with title
def get_unique_image_urls(query, num_results=10):
    items = google_image_search(query, num_results)
    valid_extensions = ('.jpg', '.jpeg', '.png', '.gif')
    unique_img_titles = []
    unique_imgs = []

    for item in items:
        if (
            item.get('title') not in unique_img_titles and
            item.get('link').lower().endswith(valid_extensions)
        ):
            unique_img_titles.append(item.get('title'))
            unique_imgs.append({
                'title': item.get('title'),
                'link': item.get('link')
            })

    return unique_imgs