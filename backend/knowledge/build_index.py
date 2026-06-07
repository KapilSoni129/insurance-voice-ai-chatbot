import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from langchain_community.vectorstores import FAISS
from langchain_openai import OpenAIEmbeddings
from langchain_core.documents import Document
from backend.knowledge.faq_data import FAQ_DOCUMENTS
from dotenv import load_dotenv

load_dotenv()


def build_faiss_index():
    documents = []
    for faq in FAQ_DOCUMENTS:
        content = f"Q: {faq['question']}\nA: {faq['answer']}"
        documents.append(Document(page_content=content, metadata={"topic": faq["topic"]}))

    embeddings = OpenAIEmbeddings(model="text-embedding-3-small")
    vectorstore = FAISS.from_documents(documents, embeddings)

    index_path = os.path.join(os.path.dirname(__file__), "faiss_index")
    vectorstore.save_local(index_path)
    print(f"FAISS index built with {len(documents)} documents at {index_path}")


if __name__ == "__main__":
    build_faiss_index()
