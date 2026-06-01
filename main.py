
import shutil
import sys
from loguru import logger

from file_loader import FileLoader
from chunker import SemanticChunker
from config import  get_config
from vector import VectorStoreManager
from rag_chain import RAGChain
from multi_functional_chain import MutiFunctionalRAGChain
from rag_graph import RAGGraph

config = get_config()


def setup_logger():
    """配置日志格式，只显示时分秒和毫秒。"""
    logger.remove()
    logger.add(
        sys.stderr,
        format="{time:HH:mm:ss.SSS} | {level:<8} | {name}:{function}:{line} - {message}",
    )

def initialization(path:str):
    loader = FileLoader()
    documents = loader.load(path)
    if(not documents):
        raise ValueError(f"没得文档：{path}")
    logger.info("开始分块处理")
    chunker = SemanticChunker(
        config=config,
        breakpoint_threshold=0.6,
    )
    logger.info("chunker 配置好了，准备开始切分文档")
    chunks = chunker.split_documents(documents)
    logger.info("文档切分完成，共生成 {} 个块", len(chunks))
    logger.info("开始准备初始化向量数据库配置")
    vector = VectorStoreManager(config)
    vector.add_documents(chunks)
    return chunks, vector

def clear_history_data():
    shutil.rmtree("./data/chroma_db", ignore_errors=True)
    shutil.rmtree("./data/chunks", ignore_errors=True)
  
def main():
    setup_logger()
    clear_history_data()
    chunks, vector = initialization("./data/")
    # rag_chain = RAGChain(vector_store_manager=vector)
    base_chain = MutiFunctionalRAGChain(
        documents=chunks, config=config, vector_store_manager=vector)
    rag_chain = RAGGraph(base_chain)
    show_sources = False
    thread_id = "cli-session"
    while True:
          question = input("请输入您的问题: ").strip()
          if question.lower() in ["quit", "exit", "q"]:
                print("\n 拜拜！")
                break
            
          if question.lower() == "sources":
                show_sources = not show_sources
                status = "开启" if show_sources else "关闭"
                print(f"\n📋 来源显示已{status}\n")
                continue
            
          print("\n 正在思考...\n")
          result = rag_chain.ask_interactive(question, thread_id=thread_id)
          if show_sources:
               print(f"回答:\n{result['answer']}\n")
               print("参考来源:")
               for i, source in enumerate(result['sources'], 1):
                    print(f"  [{i}] {source['source']}")
                    print(f"      {source['content'][:100]}...\n")
          else:
              print(f" 回答:\n{result['answer']}\n")


if __name__ == "__main__":
    main()
