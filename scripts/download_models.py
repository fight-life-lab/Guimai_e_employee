"""Download embedding model."""

import os

from sentence_transformers import SentenceTransformer

from app.config import get_settings

settings = get_settings()


def download_embedding_model():
    """Download embedding model."""
    model_name = settings.embedding_model
    cache_dir = "./models"

    print(f"Downloading embedding model: {model_name}")
    print(f"Cache directory: {cache_dir}")

    os.makedirs(cache_dir, exist_ok=True)

    try:
        # Download model
        model = SentenceTransformer(
            model_name,
            cache_folder=cache_dir,
        )

        # Test model
        test_text = "这是一个测试句子"
        embedding = model.encode(test_text)

        print(f"Model downloaded successfully!")
        print(f"Embedding dimension: {len(embedding)}")

        return True

    except Exception as e:
        print(f"Error downloading model: {e}")
        return False


if __name__ == "__main__":
    download_embedding_model()
