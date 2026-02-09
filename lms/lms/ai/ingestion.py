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
	from redis.commands.search.indexDefinition import IndexDefinition, IndexType

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


def escape_tag_value(value):
	"""Escape special characters for Redis TAG field queries."""
	special_chars = [
		",",
		".",
		"<",
		">",
		"{",
		"}",
		"[",
		"]",
		'"',
		"'",
		":",
		";",
		"!",
		"@",
		"#",
		"$",
		"%",
		"^",
		"&",
		"*",
		"(",
		")",
		"-",
		"+",
		"=",
		"~",
		" ",
	]
	escaped = value
	for char in special_chars:
		escaped = escaped.replace(char, f"\\{char}")
	return escaped


def vector_search(query, course_id, lesson_id, settings=None):
	"""Search for similar chunks in Redis vector store."""
	import numpy as np
	from redis.commands.search.query import Query

	if not settings:
		settings = get_settings()

	client = get_redis_client()
	prefix = get_vector_prefix()
	index_name = f"{prefix}:chunks_idx"

	query_embedding = embed_chunks([query], settings)[0]
	query_vector = np.array(query_embedding, dtype=np.float32).tobytes()

	filter_parts = []
	if course_id:
		escaped_course = escape_tag_value(course_id)
		filter_parts.append(f"@course_id:{{{escaped_course}}}")
	if lesson_id:
		escaped_lesson = escape_tag_value(lesson_id)
		filter_parts.append(f"@lesson_id:{{{escaped_lesson}}}")

	filter_str = " ".join(filter_parts) if filter_parts else "*"

	top_k = settings.top_k

	q = (
		Query(f"({filter_str})=>[KNN {top_k} @embedding $vec AS score]")
		.sort_by("score")
		.return_fields("content", "lesson_id", "chunk_index", "score")
		.dialect(2)
	)

	try:
		results = client.ft(index_name).search(q, query_params={"vec": query_vector})
	except Exception:
		frappe.log_error("LMSA vector search failed")
		return []

	chunks = []
	for doc in results.docs:
		chunks.append(
			{
				"content": doc.content,
				"lesson_id": doc.lesson_id,
				"chunk_index": int(doc.chunk_index),
				"score": float(doc.score),
			}
		)

	return chunks


def generate_chat_response(question, context_chunks, settings=None):
	"""Generate a chat response using OpenAI with retrieved context."""
	import requests

	if not settings:
		settings = get_settings()

	api_key = get_openai_api_key()

	context_text = "\n\n---\n\n".join([c["content"] for c in context_chunks])

	system_prompt = """You are a helpful teaching assistant for an online learning platform.
Answer the student's question based on the provided lesson content.
If the answer cannot be found in the provided content, say so clearly.
Keep your answers concise and relevant to the question."""

	user_prompt = f"""Lesson Content:
{context_text}

Question: {question}

Please answer the question based on the lesson content above."""

	response = requests.post(
		"https://api.openai.com/v1/chat/completions",
		headers={
			"Authorization": f"Bearer {api_key}",
			"Content-Type": "application/json",
		},
		json={
			"model": "gpt-4o-mini",
			"messages": [
				{"role": "system", "content": system_prompt},
				{"role": "user", "content": user_prompt},
			],
			"max_tokens": 1000,
			"temperature": 0.7,
		},
		timeout=60,
	)

	if response.status_code != 200:
		frappe.throw(f"OpenAI API error: {response.text}")

	data = response.json()
	return data["choices"][0]["message"]["content"]


def ask_chat(course_id, lesson_id, question):
	"""Main chat function: retrieve context and generate answer."""
	settings = get_settings()
	if not settings.enabled:
		frappe.throw("LMSA is not enabled")

	context_chunks = vector_search(question, course_id, lesson_id, settings)

	if not context_chunks:
		return {
			"answer": "I couldn't find relevant information in the lesson content to answer your question.",
			"sources": [],
			"status": "not_found",
		}

	answer = generate_chat_response(question, context_chunks, settings)

	sources = []
	for chunk in context_chunks:
		sources.append(
			{
				"lesson_id": chunk["lesson_id"],
				"chunk_index": chunk["chunk_index"],
				"score": chunk["score"],
				"excerpt": chunk["content"][:200] + "..."
				if len(chunk["content"]) > 200
				else chunk["content"],
			}
		)

	return {
		"answer": answer,
		"sources": sources,
		"status": "answered",
	}


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
