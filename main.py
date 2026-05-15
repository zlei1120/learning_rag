
import shutil
from loguru import logger

from file_loader import FileLoader
from chunker import SemanticChunker
from config import  get_config
from vector import VectorStoreManager
from rag_chain import RAGChain
config = get_config()

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
    clear_history_data()
    chunks, vector = initialization("./data/")
    rag_chain = RAGChain(vector_store_manager=vector)
    show_sources = False
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
          if show_sources:
               result = rag_chain.ask_with_source(question)
               print(f"回答:\n{result['answer']}\n")
               print("参考来源:")
               for i, source in enumerate(result['sources'], 1):
                    print(f"  [{i}] {source['source']}")
                    print(f"      {source['content'][:100]}...\n")
          else:
              result = rag_chain.ask(question)
              print(f" 回答:\n{result}\n")


if __name__ == "__main__":
    main()
