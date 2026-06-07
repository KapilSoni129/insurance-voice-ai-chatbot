import os
from langchain_community.vectorstores import FAISS
from langchain_openai import OpenAIEmbeddings
from backend.config import settings

_vectorstore = None


def get_vectorstore() -> FAISS:
    global _vectorstore
    if _vectorstore is None:
        index_path = os.path.join(os.path.dirname(__file__), "faiss_index")
        embeddings = OpenAIEmbeddings(model="text-embedding-3-small", api_key=settings.openai_api_key)
        _vectorstore = FAISS.load_local(index_path, embeddings, allow_dangerous_deserialization=True)
    return _vectorstore


def search_faq(question: str, k: int = 2) -> str:
    vs = get_vectorstore()
    docs = vs.similarity_search(question, k=k)
    if not docs:
        return "I don't have specific information on that topic. Would you like me to connect you with a representative?"
    best = docs[0].page_content
    if "A: " in best:
        return best.split("A: ", 1)[1]
    return best