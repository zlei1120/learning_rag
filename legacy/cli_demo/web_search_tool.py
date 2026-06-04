from langchain_core.output_parsers import StrOutputParser


class WebSearchTool:
    """真实互联网搜索工具。

    这个类只负责搜索和基于搜索结果生成回答，不参与 LangGraph 的节点编排。
    """

    def __init__(self, llm, max_results: int = 5):
        self.llm = llm
        self.max_results = max_results

    def search(self, question: str) -> str:
        """执行真实互联网搜索，并把结果格式化成文本。"""
        try:
            from ddgs import DDGS

            with DDGS() as ddgs:
                results = list(
                    ddgs.text(
                        question,
                        region="cn-zh",
                        safesearch="moderate",
                        max_results=self.max_results,
                    )
                )
        except Exception as exc:
            return f"互联网搜索失败：{exc}"

        if not results:
            return "互联网搜索没有返回结果。"

        lines = []
        for index, item in enumerate(results, 1):
            title = item.get("title", "")
            href = item.get("href", "")
            body = item.get("body", "")
            lines.append(f"[搜索结果 {index}]\n标题：{title}\n链接：{href}\n摘要：{body}")

        return "\n\n".join(lines)

    def answer(self, question: str, web_results: str) -> str:
        """基于互联网搜索结果生成回答。"""
        prompt = f"""
你是一个联网搜索结果总结助手。请基于【搜索结果】回答【用户问题】。

要求：
- 如果搜索失败或没有结果，请明确说明。
- 不要编造搜索结果中没有的信息。
- 回答末尾简要列出使用到的链接。

【用户问题】
{question}

【搜索结果】
{web_results}
"""
        try:
            response = self.llm.invoke(prompt)
            return StrOutputParser().invoke(response)
        except Exception as exc:
            return (
                "LLM 总结搜索结果失败，下面直接返回原始搜索摘要。\n\n"
                f"失败原因：{exc}\n\n"
                f"{web_results}"
            )
