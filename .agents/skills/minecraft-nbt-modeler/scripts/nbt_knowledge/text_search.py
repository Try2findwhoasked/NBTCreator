"""Deterministic text segmentation and keyword scoring, independent of assets and workspaces."""
import re

# These names denote the same construction; this vocabulary only affects local
# search text. It never changes the user's selected document or library sources.
EQUIVALENTS=(
    ('旋梯','螺旋梯','螺旋楼梯','盘旋楼梯','spiral staircase'),
    ('歇山顶','歇山式屋顶','九脊顶','hip-and-gable roof'),
    ('玫瑰窗','玫瑰花窗','rose window'),
    ('隔扇','槅扇'),('飞扶壁','飞拱扶壁','flying buttress'),
)

def retrieval_query(query,book_vocabulary,offset=None):
    """Return a bounded indexed query and the inputs needed for a same-scope retry."""
    query=query.strip()
    if offset is not None and (type(offset) is not int or not 0<=offset<len(query)):
        raise ValueError('query_offset 须为当前检索文本内的字符位置（从 0 开始）')
    window=query if offset is None else query[offset:offset+300]
    lower=window.lower()
    additions=[word for group in EQUIVALENTS if any(word in lower for word in group)
               for word in group if word not in lower]
    if len(window)>300:
        # Inspect the entire task for named constructions, including the middle.
        # Keep both ends of otherwise unrecognized terms; an explicit window
        # lets the caller inspect any omitted text without changing sources.
        named=[term for term in book_vocabulary if term in window]
        named.extend(word for group in EQUIVALENTS for word in group if word in lower)
        prefix=' '.join(dict.fromkeys(named+additions))[:140]
        indexed=' '.join(filter(None,(prefix,window[:65],window[-90:])))
        return indexed,dict(mode='terms_head_tail',equivalents=[word for word in additions if word in indexed],next_offset=0)
    remaining=len(query)-(offset or 0)
    indexed=(window+' '+' '.join(additions)).strip()[:300]
    return indexed,dict(mode='window' if offset is not None else 'query',equivalents=[word for word in additions if word in indexed],
                        next_offset=offset+300 if offset is not None and remaining>300 else None)

def han_bigrams(text):
    for match in re.finditer(r'[\u3400-\u9fff]+', text):
        run = match.group()
        yield from (run[index:index+2] for index in range(len(run)-1))


def tokens(query):
    chunks=re.findall(r'[a-z0-9_]+|[\u3400-\u9fff]+',query.lower());values=[]
    for chunk in chunks:
        values.append(chunk)
        values.extend(han_bigrams(chunk))
    return list(dict.fromkeys(values))[:128]

def score(query,text):
    lowered=text.lower();terms=tokens(query)
    return sum(min(3,lowered.count(term))*(5 if len(term)>2 else 1) for term in terms)+(20 if query.lower() in lowered else 0)

def chunks(document):
    lines=document['text'].splitlines();start=0;heading=document['label']
    while start<len(lines):
        if lines[start].startswith('#'):heading=lines[start].lstrip('# ').strip()[:250]
        end=start;length=0
        while end<len(lines) and end-start<24:
            if end>start and lines[end].startswith('#'):break
            size=len(lines[end])+1
            if length+size>2600 and end>start:break
            length+=size;end+=1
        text='\n'.join(lines[start:end]);clipped=len(text)>2600;text=text[:2600]
        if text.strip():
            identifier='knowledge:'+document['id']+':'+document['sha256']+':'+str(start+1)+':'+str(end)
            yield dict(id=identifier,kind='knowledge',document_id=document['id'],label=document['label'],heading=heading,sha256=document['sha256'],locator=document['locator'],line_start=start+1,line_end=end,text=text,clipped=clipped)
        start=max(start+1,end)
