
import shutil
from loguru import logger

from file_loader import FileLoader
from chunker import SemanticChunker
from config import  get_config
from vector import VectorStoreManager
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

    return documents

def clear_history_data():
    shutil.rmtree("./data/chroma_db", ignore_errors=True)
    shutil.rmtree("./data/chunks", ignore_errors=True)
def main():
    clear_history_data()
    initialization("./data/")


if __name__ == "__main__":
    main()
