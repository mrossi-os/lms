import logging

import frappe
from frappe.utils import now_datetime

from os_lms.os_lms.ai.utils.lesson_parser import LessonContentParser
from os_lms.os_lms.ai.utils.llm.chatbot import Chatbot
from os_lms.os_lms.ai.utils.llm.gpt_chatbot import GptChatbot
from os_lms.os_lms.ai.utils.oslms_settings import OsLmsSettings
from os_lms.os_lms.ai.utils.rag_db import RagDB


class IngestionService:
    _settings: OsLmsSettings | None = None
    _rag_db: RagDB | None = None
    _chatbot: Chatbot | None = None
    _logger: logging.Logger | None = None

    @property
    def settings(self) -> OsLmsSettings:
        if self._settings is None:
            doc = frappe.get_single("LMSA Settings")
            self._settings = OsLmsSettings(
                enabled=doc.enabled,
                embedding_model=doc.embedding_model or "text-embedding-3-small",
                llm_model=doc.llm_model or "gpt-4o-mini",
                chunk_size=doc.chunk_size or 1000,
                chunk_overlap=doc.chunk_overlap or 200,
                top_k=doc.top_k or 6,
                system_prompt=doc.system_prompt,
            )
        return self._settings

    @property
    def logger(self) -> logging.Logger:
        if self._logger is None:
            self._logger = frappe.logger("os_lmsa", allow_site=True)
        return self._logger

    @property
    def chatbot(self) -> Chatbot:
        if self._chatbot is None:
            chatbot = GptChatbot()
            chatbot.set_model(self.settings.llm_model)
            chatbot.set_system_prompt(self.settings.system_prompt)
            self._chatbot = chatbot
        return self._chatbot

    @property
    def rag_db(self) -> RagDB:
        if self._rag_db is None:
            self._rag_db = RagDB(self.settings)
        return self._rag_db

    def add_lesson_to_ingest_queue(self, lesson):
        if not self.settings.enabled:
            frappe.throw("LMSA is not enabled")
        if lesson.index_status == "processing":
            return
        lesson.index_status = "pending"
        lesson.save()

    def reindex_lesson_content(self):
        """Re-index all lessons with pending or null index_status."""
        if not self.settings.enabled:
            self.logger.info("LMSA is not enabled, skipping reindex")
            return

        lessons = frappe.get_all(
            "Course Lesson",
            filters=[["index_status", "in", ["pending", None, ""]]],
            pluck="name",
        )

        self.logger.info("Found %d lessons to reindex", len(lessons))

        for lesson_name in lessons:
            try:
                lesson = frappe.get_doc("Course Lesson", lesson_name)
                self.ingest_lesson(lesson)
            except Exception as e:
                self.logger.error("Reindex failed for lesson %s: %s", lesson_name, e)

    def ingest_lesson(self, lesson):
        """Main ingestion function for a lesson."""
        if not self.settings.enabled:
            frappe.throw("LMSA is not enabled")

        if lesson.index_status == "processing":
            self.logger.info("Lesson %s already processing, skipping", lesson.name)
            return

        self.logger.info("Starting ingestion for lesson %s", lesson.name)
        lesson.index_status = "processing"
        lesson.save()
        frappe.db.commit()

        try:
            parser = LessonContentParser(lesson)
            text = parser.extract_text()

            if not text:
                frappe.throw("No content found in lesson")

            self.rag_db.ingest_data(lesson.course, lesson.name, text)

            lesson.index_status = "indexed"
            lesson.indexed_at = now_datetime()
            self.logger.info("Lesson %s indexed successfully", lesson.name)
        except Exception as e:
            lesson.index_status = "failed"
            self.logger.error("Ingestion failed for lesson %s: %s", lesson.name, e)
            raise
        finally:
            lesson.save()
            frappe.db.commit()

    def ask(self, lesson, question: str) -> str:
        """Ask a question about a lesson using RAG context and LLM chatbot.

        Searches for relevant chunks in the vector store, sends them as context
        to the chatbot, and logs the interaction in LMSA Query Log.

        Args:
            lesson: The Course Lesson document.
            question: The student's question.

        Returns:
            The chatbot's answer as a string.

        Raises:
            frappe.ValidationError: If LMSA is not enabled or no context is found.
        """
        if not self.settings.enabled:
            frappe.throw("LMSA is not enabled")

        context_chunks = []
        answer = ""
        status = "Failed"

        try:
            # Search for relevant chunks in the vector store
            context_chunks = self.rag_db.search(lesson.course, lesson.name, question)
            if not context_chunks:
                frappe.throw("Lesson context not found")

            # Generate answer using the LLM chatbot
            answer = self.chatbot.ask(question, context_chunks)
            status = "Answered"
        except Exception as e:
            self.logger.error("Ask failed for lesson %s: %s", lesson.name, e)
            raise
        finally:
            # Always log the query, regardless of success or failure
            try:
                log = frappe.new_doc("LMSA Query Log")
                log.course = lesson.course
                log.lesson = lesson.name
                log.member = frappe.session.user
                log.question = question
                log.answer = answer
                log.context = (
                    "\n\n---\n\n".join(context_chunks) if context_chunks else ""
                )
                log.status = status
                log.save(ignore_permissions=True)
                frappe.db.commit()
            except Exception as e:
                self.logger.error("Failed to save query log: %s", e)

        return answer
