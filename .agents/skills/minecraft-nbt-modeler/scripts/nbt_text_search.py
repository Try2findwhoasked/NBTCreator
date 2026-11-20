"""Deterministic text segmentation and keyword scoring, independent of assets and workspaces."""
import re


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
