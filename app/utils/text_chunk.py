from __future__ import annotations

#按照一段一个向量进行分割，因为这里主要是上传反诈案例的，并不是上传文献资料，所以一段的内容是独立完整的。
def chunk_text(text: str, max_chars: int = None, overlap: int = None) -> list[str]:
    """按段落分段，一段一个向量。
    
    忽略 max_chars 和 overlap 参数，仅按段落（双换行）分割。
    
    Args:
        text: 待分段的文本
        max_chars: 已弃用（保留参数以兼容旧接口）
        overlap: 已弃用（保留参数以兼容旧接口）
        
    Returns:
        段落列表，每个元素是一个段落
    """
    text = text.strip()
    if not text:
        return []

    # 按双换行（段落分隔符）分割
    chunks: list[str] = []
    for paragraph in text.replace("\r\n", "\n").replace("\r", "\n").split("\n\n"):
        p = paragraph.strip()
        if p:
            chunks.append(p)

    return chunks
