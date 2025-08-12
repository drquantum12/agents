# from db_utility.vector_db import VectorDB
# from core_agents import get_chat_history
from utility.web_search import get_unique_image_urls
# vector_db = VectorDB()
# from db_utility.mongo_db import mongo_db
# conversations_collection = mongo_db.get_collection("conversations")


if __name__ == "__main__":
   # chat_history = get_chat_history("7e2432a2-8957-4a65-82f0-fc86769b0c45")
   # messages = list(chat_history.messages)
   # print(f"Messages: {messages}")

   # Test image search functionality
   unique_image_urls = get_unique_image_urls("Black holes in space", num_results=5)
   print(f"Unique Image URLs: {unique_image_urls}")