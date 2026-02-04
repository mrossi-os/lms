import hashlib
import json
import os
import uuid

import frappe
import redis
from frappe.utils import now_datetime


def get_settings():
	"""Get LMSA settings with defaults."""
	doc = frappe.get_single("LMSA Settings")
	return frappe._dict(
		enabled=doc.enabled,
		embedding_model=doc.embedding_model or "text-embedding-3-small",
		chunk_size=doc.chunk_size or 1000,
		chunk_overlap=doc.chunk_overlap or 200,
		top_k=doc.top_k or 6,
	)


def material_hash(text):
	"""Generate SHA256 hash of text content."""
	return hashlib.sha256(text.encode("utf-8")).hexdigest()


def normalize_lesson_text(lesson):
	"""Extract plain text from lesson content JSON or body markdown."""
	lesson_doc = frappe.get_doc("Course Lesson", lesson)
	text_parts = []

	if lesson_doc.content:
		try:
			content = json.loads(lesson_doc.content)
			for block in content.get("blocks", []):
				block_type = block.get("type")
				data = block.get("data", {})
				if block_type == "paragraph":
					text_parts.append(data.get("text", ""))
				elif block_type == "header":
					text_parts.append(data.get("text", ""))
				elif block_type == "list":
					items = data.get("items", [])
					for item in items:
						if isinstance(item, str):
							text_parts.append(item)
						elif isinstance(item, dict):
							text_parts.append(item.get("content", ""))
				elif block_type == "code":
					text_parts.append(data.get("code", ""))
				elif block_type == "quote":
					text_parts.append(data.get("text", ""))
		except json.JSONDecodeError:
			pass

	if lesson_doc.body:
		text_parts.append(lesson_doc.body)

	return "\n\n".join(text_parts).strip()


def chunk_text(text, settings=None):
	"""Split text into chunks by characters."""
	if not settings:
		settings = get_settings()

	chunk_size = settings.chunk_size
	chunk_overlap = settings.chunk_overlap

	if not text or len(text) == 0:
		return []

	chunks = []
	start = 0
	while start < len(text):
		end = start + chunk_size
		chunk = text[start:end]
		if chunk.strip():
			chunks.append(chunk.strip())
		start = end - chunk_overlap
		if start < 0:
			start = 0
		if end >= len(text):
			break

	return chunks


def get_openai_api_key():
	"""Get OpenAI API key from environment."""
	api_key = os.environ.get("OPENAI_API_KEY")
	if not api_key:
		frappe.throw("OPENAI_API_KEY environment variable is not set")
	return api_key


def embed_chunks(chunks, settings=None):
	"""Embed chunks using OpenAI API."""
	import requests

	if not settings:
		settings = get_settings()

	if not chunks:
		return []

	api_key = get_openai_api_key()

	response = requests.post(
		"https://api.openai.com/v1/embeddings",
		headers={
			"Authorization": f"Bearer {api_key}",
			"Content-Type": "application/json",
		},
		json={
			"input": chunks,
			"model": settings.embedding_model,
		},
		timeout=60,
	)

	if response.status_code != 200:
		frappe.throw(f"OpenAI API error: {response.text}")

	data = response.json()
	embeddings = [item["embedding"] for item in data["data"]]
	return embeddings


def get_redis_client():
	"""Get Redis client for vector operations."""
	redis_url = frappe.conf.get("redis_cache") or "redis://localhost:6379"
	return redis.from_url(redis_url)


def get_vector_prefix():
	"""Get the vector key prefix for current site."""
	site = frappe.local.site
	return f"lmsa:{site}"


def ensure_vector_index(client):
	"""Create Redis vector index if it doesn't exist."""
	from redis.commands.search.field import NumericField, TagField, TextField, VectorField
	from redis.commands.search.index_definition import IndexDefinition, IndexType

	prefix = get_vector_prefix()
	index_name = f"{prefix}:chunks_idx"

	try:
		client.ft(index_name).info()
	except redis.ResponseError:
		schema = (
			TagField("course_id"),
			TagField("lesson_id"),
			TagField("material_id"),
			TagField("chunk_id"),
			NumericField("chunk_index"),
			TextField("content"),
			VectorField(
				"embedding",
				"FLAT",
				{
					"TYPE": "FLOAT32",
					"DIM": 1536,
					"DISTANCE_METRIC": "COSINE",
				},
			),
		)
		definition = IndexDefinition(prefix=[f"{prefix}:chunk:"], index_type=IndexType.HASH)
		client.ft(index_name).create_index(schema, definition=definition)

	return index_name


def upsert_vectors(chunks, embeddings, metadata):
	"""Upsert vectors to Redis."""
	import numpy as np

	client = get_redis_client()
	ensure_vector_index(client)
	prefix = get_vector_prefix()

	vector_ids = []
	for i, (chunk, embedding) in enumerate(zip(chunks, embeddings, strict=False)):
		vector_id = str(uuid.uuid4())
		key = f"{prefix}:chunk:{vector_id}"

		embedding_bytes = np.array(embedding, dtype=np.float32).tobytes()

		client.hset(
			key,
			mapping={
				"course_id": metadata["course_id"],
				"lesson_id": metadata["lesson_id"],
				"material_id": metadata["material_id"],
				"chunk_id": vector_id,
				"chunk_index": i,
				"content": chunk,
				"embedding": embedding_bytes,
			},
		)
		vector_ids.append(vector_id)

	return vector_ids


def delete_material_vectors(material_id):
	"""Delete all vectors associated with a material."""
	client = get_redis_client()
	prefix = get_vector_prefix()

	chunks = frappe.get_all(
		"LMSA Chunk",
		filters={"material": material_id},
		fields=["vector_id"],
	)

	for chunk in chunks:
		if chunk.vector_id:
			key = f"{prefix}:chunk:{chunk.vector_id}"
			client.delete(key)


def ingest_lesson(lesson_id):
	"""Main ingestion function for a lesson."""
	settings = get_settings()
	if not settings.enabled:
		frappe.throw("LMSA is not enabled")

	lesson = frappe.get_doc("Course Lesson", lesson_id)
	course_id = lesson.course

	text = normalize_lesson_text(lesson_id)
	if not text:
		frappe.throw("No content found in lesson")

	content_hash = material_hash(text)

	material = frappe.db.get_value(
		"LMSA Material",
		{"lesson": lesson_id},
		["name", "source_hash"],
		as_dict=True,
	)

	if material and material.source_hash == content_hash:
		return {
			"status": "unchanged",
			"message": "Content has not changed since last ingestion",
			"material": material.name,
		}

	if material:
		material_doc = frappe.get_doc("LMSA Material", material.name)
		delete_material_vectors(material.name)
		frappe.db.delete("LMSA Chunk", {"material": material.name})
	else:
		material_doc = frappe.new_doc("LMSA Material")
		material_doc.course = course_id
		material_doc.lesson = lesson_id

	material_doc.status = "Processing"
	material_doc.source_hash = content_hash
	material_doc.save(ignore_permissions=True)
	frappe.db.commit()

	try:
		chunks = chunk_text(text, settings)
		if not chunks:
			material_doc.status = "Failed"
			material_doc.save(ignore_permissions=True)
			frappe.throw("No chunks generated from content")

		embeddings = embed_chunks(chunks, settings)

		metadata = {
			"course_id": course_id,
			"lesson_id": lesson_id,
			"material_id": material_doc.name,
		}

		vector_ids = upsert_vectors(chunks, embeddings, metadata)

		for i, (chunk, vector_id) in enumerate(zip(chunks, vector_ids, strict=False)):
			chunk_doc = frappe.new_doc("LMSA Chunk")
			chunk_doc.material = material_doc.name
			chunk_doc.chunk_index = i
			chunk_doc.content = chunk
			chunk_doc.vector_id = vector_id
			chunk_doc.source_hash = content_hash
			chunk_doc.save(ignore_permissions=True)

		material_doc.status = "Ready"
		material_doc.chunk_count = len(chunks)
		material_doc.last_ingested_on = now_datetime()
		material_doc.save(ignore_permissions=True)
		frappe.db.commit()

		return {
			"status": "success",
			"message": f"Ingested {len(chunks)} chunks",
			"material": material_doc.name,
			"chunk_count": len(chunks),
		}

	except Exception:
		material_doc.status = "Failed"
		material_doc.save(ignore_permissions=True)
		frappe.db.commit()
		frappe.log_error(f"LMSA ingestion failed for lesson {lesson_id}")
		raise
