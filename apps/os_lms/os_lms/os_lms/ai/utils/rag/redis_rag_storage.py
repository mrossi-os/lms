import frappe
import re


# redisvl library
from redisvl.schema import IndexSchema
from redisvl.index import SearchIndex
from redisvl.redis.utils import array_to_buffer
from redisvl.query import FilterQuery, VectorQuery
from redisvl.query.filter import Tag

from .rag_storage import RagStorage
from .embedding_item import EmbeddingItem


class RedisRagStorage(RagStorage):
    """Redis-backed RAG vector storage."""

    def __init__(self):
        self._redis_url = frappe.conf.get("redis_vector_store")
        if not self._redis_url:
            frappe.throw(
                "Redis vector store is not configured. "
                "Set 'redis_vector_store' in site_config.json."
            )
        self.__redisIndex = None

    @property
    def _redisIndex(self) -> IndexSchema:
        """Lazy Redis Search index (must use db 0)."""
        if self.__redisIndex is None:
            prefix = self._get_vector_prefix()
            schema_dict = {
                "index": {
                    "name": self._get_index_name(),
                    "prefix": f"{prefix}",
                    "storage_type": "hash",
                },
                "fields": [
                    {
                        "name": "embedding",
                        "type": "vector",
                        "attrs": {
                            "dims": 1536,  # text-embedding-3-small
                            "distance_metric": "cosine",
                            "algorithm": "HNSW",
                            "datatype": "float32",
                        },
                    },
                    {"name": "chunk_id", "type": "tag", "attrs": {"sortable": True}},
                    {"name": "chunk_index", "type": "numeric"},
                    {"name": "content", "type": "text"},
                    {"name": "course", "type": "tag"},
                    {"name": "lesson", "type": "tag"},
                ],
            }
            self.__redisIndex = SearchIndex.from_dict(
                schema_dict, redis_url=self._redis_url
            )
        return self.__redisIndex

    def _get_vector_prefix(self):
        """Get the vector key prefix for current site."""
        site = frappe.local.site
        return f"lmsa:{site}"

    def _get_index_name(self):
        """Get the RediSearch index name for current site."""
        return f"{self._get_vector_prefix()}:chunks"

    def save(self, course: str, lesson: str, items: list[EmbeddingItem]):
        self._redisIndex.load(
            [
                {
                    "content": item.text,
                    "embedding": array_to_buffer(item.vector, dtype="float32"),
                    "chunk_index": i,
                    "course": course,
                    "lesson": lesson,
                }
                for i, item in enumerate(items)
            ]
        )

    def search(self, course: str, lesson: str, query: EmbeddingItem, max_result: int) -> list[str]:
        tag_filter = Tag("course") == course
        tag_filter &= Tag("lesson") == lesson
        q = VectorQuery(
            vector=query.vector,
            vector_field_name="embedding",
            num_results=max_result,
            return_fields=["content"],
            filter_expression=tag_filter,
        )
        results = self._redisIndex.query(q)
        return [r["content"] for r in results]

    def delete_by_lesson(self, course: str, lesson: str):
        """Delete all vectors for a given course and lesson.

        Args:
            course: The course tag value.
            lesson: The lesson tag value.
        """
        if not course or not lesson:
            return

        tag_filter = Tag("course") == course
        tag_filter &= Tag("lesson") == lesson

        query = FilterQuery(
            filter_expression=tag_filter,
            return_fields=["chunk_id"],
        )

        try:
            results = self._redisIndex.query(query)
        except Exception as e:
            print(f"delete_by_lesson: query error: {e}")
            return

        if not results:
            return

        client = self._redisIndex.client
        keys = [doc["id"] for doc in results]
        client.delete(*keys)

    def create_index(self):
        if frappe.conf.get("regenerate_rag_index") == "1":
            print(f"Create index for redis -> {self._redis_url}")
            self._redisIndex.create(overwrite=True)

        try:
            self._redisIndex.info()
        except Exception:
            print(f"Create index for redis -> {self._redis_url}")
            self._redisIndex.create(overwrite=True)

    @staticmethod
    def _escape_tag(value: str) -> str:
        """Escape special characters for RediSearch TAG queries."""
        return re.sub(r"([,.<>{}\[\]\"':;!@#$%^&*()\-+=~ ])", r"\\\1", value)
