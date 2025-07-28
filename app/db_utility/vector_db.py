# using milvus vector db
import os
from pymilvus import MilvusClient
from google import genai
from google.genai import types

embedding_client = genai.Client()

MILVUS_URI = os.getenv('MILVUS_URI')
MILVUS_TOKEN = os.getenv('MILVUS_TOKEN')
COLLECTION_NAME = os.getenv('MILVUS_COLLECTION_NAME')
VECTOR_DIMENSION = int(os.getenv('MILVUS_VECTOR_DIMENSION', 768))

class VectorDB:
    def __init__(self):
        self.client = MilvusClient(uri=MILVUS_URI, token=MILVUS_TOKEN)
        self.similarity_score_threshold = 0.7  # Example threshold for similarity score

    def get_similar_documents(self, text, top_k=3):
        """
        Retrieves similar documents from the Milvus vector database.
        """
        try:
            query_embedding = generate_embedding(text, vector_dimension=VECTOR_DIMENSION)
            results = self.client.search(
            collection_name=COLLECTION_NAME,
            anns_field="embedding",
            data=[query_embedding],
            search_params={
                "metric_type": "COSINE"
            },
            limit=top_k,
            output_fields=["metadata_json"])
            context_for_llm = {
                    "content": [],
                    "source": []
                }
            for result in results[0]:
                metadata = result["entity"].get("metadata_json", {})
                if metadata and result["distance"] >= self.similarity_score_threshold:
                    context_for_llm["content"].append(metadata.get("content", ""))
                    context_for_llm["source"].append(f"{metadata.get('board')} - {metadata.get('grade')} - {metadata.get('subject')} - {metadata.get('chapter')} - {metadata.get('subheading')}")
            return "\n".join(context_for_llm["content"]), context_for_llm["source"]
        except Exception as e:
            raise Exception(f"Error retrieving similar documents: {str(e)}")




def generate_embedding(text, vector_dimension=768):
    """
    Generates an embedding for the given text using Google GenAI.
    """
    try:
        response = embedding_client.models.embed_content(
            model="gemini-embedding-001",
            contents=text,
            config=types.EmbedContentConfig(
                output_dimensionality=vector_dimension,
                task_type="RETRIEVAL_DOCUMENT"
            )
        )
        return response.embeddings[0].values
    except Exception as e:
        print(f"Error generating embedding: {e}")
        return None