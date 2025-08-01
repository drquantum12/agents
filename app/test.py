from db_utility.vector_db import VectorDB

vector_db = VectorDB()


if __name__ == "__main__":
    sample_query = "What is a shadow?"
    docs = vector_db.get_similar_documents(sample_query, top_k=3)
    print(docs)