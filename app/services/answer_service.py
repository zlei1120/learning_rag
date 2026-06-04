from __future__ import annotations

from dataclasses import dataclass

from app.core.config import Settings, get_settings
from app.services.retrieval_service import RetrievedChunk, RetrievedImage

try:
    from openai import OpenAI
except ImportError:  # pragma: no cover
    OpenAI = None  # type: ignore[assignment]


ANSWER_SYSTEM_PROMPT = """
你是博客问答助手，只能基于提供的博客上下文回答。
可以归纳、解释和连接多个片段，但不能编造上下文里没有的信息。
如果上下文不足，请明确说明当前已同步文章中没有足够依据。
回答使用中文，尽量简洁，但遇到教程步骤时要保留关键步骤和注意事项。
""".strip()


@dataclass(slots=True)
class AnswerResult:
    """回答生成结果。"""

    answer: str
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    total_tokens: int | None = None


class AnswerService:
    """根据召回上下文生成最终回答。"""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self.client = self._create_client()

    def generate_answer(
        self,
        *,
        question: str,
        chunks: list[RetrievedChunk],
        images: list[RetrievedImage],
    ) -> AnswerResult:
        """生成单轮问答答案。"""
        context = self._format_context(chunks, images)
        if not context:
            return AnswerResult(answer="根据当前已同步的文章内容，我还没有找到足够依据回答这个问题。")

        if self.client is None:
            return AnswerResult(answer=self._build_local_answer(question=question, context=context))

        try:
            completion = self.client.chat.completions.create(
                model=self.settings.chat_model,
                messages=[
                    {"role": "system", "content": ANSWER_SYSTEM_PROMPT},
                    {"role": "user", "content": f"【博客上下文】\n{context}\n\n【用户问题】\n{question}"},
                ],
                temperature=0.2,
            )
            message = completion.choices[0].message.content
            usage = getattr(completion, "usage", None)
            return AnswerResult(
                answer=(message or "").strip() or "根据当前上下文，我没有生成出有效回答。",
                prompt_tokens=getattr(usage, "prompt_tokens", None),
                completion_tokens=getattr(usage, "completion_tokens", None),
                total_tokens=getattr(usage, "total_tokens", None),
            )
        except Exception:
            return AnswerResult(answer=self._build_local_answer(question=question, context=context))

    def _create_client(self) -> OpenAI | None:
        """初始化百炼兼容的聊天模型客户端。"""
        if OpenAI is None or not self.settings.openai_api_key:
            return None

        return OpenAI(
            api_key=self.settings.openai_api_key,
            base_url=self.settings.openai_base_url,
        )

    @staticmethod
    def _format_context(chunks: list[RetrievedChunk], images: list[RetrievedImage]) -> str:
        """把文本片段和图片特征整理成模型上下文。"""
        context_parts: list[str] = []
        for index, chunk in enumerate(chunks, 1):
            title_path = f"，标题路径：{chunk.title_path}" if chunk.title_path else ""
            context_parts.append(
                f"[正文 {index}] 文章：{chunk.title}{title_path}\n{chunk.content.strip()}"
            )

        for index, image in enumerate(images, 1):
            title_path = f"，标题路径：{image.title_path}" if image.title_path else ""
            feature_text = image.feature_summary or image.caption or image.alt_text or ""
            if not feature_text.strip():
                continue
            context_parts.append(
                f"[图片 {index}] 文章：{image.title}{title_path}，图片：{image.url}\n{feature_text.strip()}"
            )

        return "\n\n---\n\n".join(context_parts).strip()

    @staticmethod
    def _build_local_answer(*, question: str, context: str) -> str:
        """本地开发兜底回答，保证没 Key 时问答链路也可验证。"""
        excerpt = context[:1000].strip()
        return (
            "我先基于当前检索到的博客内容给出回答：\n\n"
            f"{excerpt}\n\n"
            f"你的问题是：{question}\n"
            "如果需要更自然的总结式回答，请配置百炼 `OPENAI_API_KEY` 后再调用。"
        )
