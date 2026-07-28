def chunk_text(pages: list[dict], chunk_size: int = 800, overlap: int = 150) -> list[dict]:
    """
    Splits text from pages into chunks of approximately `chunk_size` characters.
    Attempts to split at sentence boundaries, maintaining an `overlap` of characters.
    """
    chunks = []
    
    for page in pages:
        page_number = page.get("page_number")
        text = page.get("text", "")
        
        if not text:
            continue
            
        # Split on sentence boundaries
        sentences = text.split(". ")
        
        current_sentences = []
        current_len = 0
        
        for i, sentence in enumerate(sentences):
            # Restore the period lost in split (except for the very last sentence)
            suffix = ". " if i < len(sentences) - 1 else ""
            part = sentence + suffix
            
            # Edge Case: A single sentence is larger than the chunk size limit
            if len(part) > chunk_size:
                # Flush whatever we have so far
                if current_sentences:
                    chunk_str = "".join(current_sentences).strip()
                    if chunk_str:
                        chunks.append({
                            "page_number": page_number,
                            "chunk_text": chunk_str,
                            "chunk_type": "text"
                        })
                    current_sentences = []
                    current_len = 0
                
                # Hard slice the giant sentence to enforce the token/length limit
                start = 0
                while start < len(part):
                    slice_str = part[start:start+chunk_size]
                    if slice_str.strip():
                        chunks.append({
                            "page_number": page_number,
                            "chunk_text": slice_str.strip(),
                            "chunk_type": "text"
                        })
                    start += (chunk_size - overlap)
                continue
                
            # Normal case: add sentence if it fits
            if current_len + len(part) <= chunk_size:
                current_sentences.append(part)
                current_len += len(part)
            else:
                # Chunk is full, save it
                chunk_str = "".join(current_sentences).strip()
                if chunk_str:
                    chunks.append({
                        "page_number": page_number,
                        "chunk_text": chunk_str,
                        "chunk_type": "text"
                    })
                
                # Start the next chunk, keeping some sentences for overlap context
                overlap_len = 0
                overlap_sentences = []
                for s in reversed(current_sentences):
                    if overlap_len + len(s) <= overlap:
                        overlap_sentences.insert(0, s)
                        overlap_len += len(s)
                    else:
                        # Even if we can't fit a full sentence into the overlap limit, 
                        # we break. This prevents overlap from exceeding the limit.
                        break
                
                # If the overlap was too small because sentences were long, we just proceed
                current_sentences = overlap_sentences + [part]
                current_len = sum(len(s) for s in current_sentences)
                
        # Final flush for the remaining text on the page
        if current_sentences:
            chunk_str = "".join(current_sentences).strip()
            if chunk_str:
                chunks.append({
                    "page_number": page_number,
                    "chunk_text": chunk_str,
                    "chunk_type": "text"
                })
                
    return chunks
