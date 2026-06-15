# from dotenv import load_dotenv
# import os

# if __name__ == "__main__":
#     load_dotenv()

#     api_key = os.getenv("PINECONE_API_KEY")
#     env = os.getenv("PINECONE_ENVIRONMENT") or os.getenv("PINECONE_ENV")
#     project_name = os.getenv("PINECONE_PROJECT_NAME")
#     index_name = os.getenv("PINECONE_INDEX_NAME", "careslotly-rag-index")
#     namespace = os.getenv("PINECONE_NAMESPACE", "default")

#     print(f"PINECONE_API_KEY: {'***' + api_key[-8:] if api_key else 'NOT SET'}")
#     print(f"PINECONE_ENVIRONMENT: {env}")
#     print(f"PINECONE_PROJECT_NAME: {project_name}")
#     print(f"PINECONE_INDEX_NAME: {index_name}")
#     print(f"PINECONE_NAMESPACE: {namespace}")
#     print()

#     if not api_key or not env:
#         print("ERROR: Pinecone credentials missing")
#         exit(1)

#     try:
#         import pinecone
#     except ModuleNotFoundError:
#         print("ERROR: pinecone-client not installed")
#         exit(1)

#     try:
#         pinecone.init(
#             api_key=api_key,
#             environment=env
#         )

#         indexes = pinecone.list_indexes()

#         print("Connected successfully.")
#         print(f"Available indexes: {indexes}")

#         if index_name in indexes:
#             print(f"SUCCESS: Index '{index_name}' exists.")
#         else:
#             print(f"WARNING: Index '{index_name}' does not exist.")

#     except Exception as e:
#         print(f"ERROR connecting to Pinecone: {e}")



from dotenv import load_dotenv
import os

load_dotenv()

from pinecone import Pinecone

api_key = os.getenv("PINECONE_API_KEY")

pc = Pinecone(api_key=api_key)

print("Connected to Pinecone")

indexes = pc.list_indexes()

print(indexes)