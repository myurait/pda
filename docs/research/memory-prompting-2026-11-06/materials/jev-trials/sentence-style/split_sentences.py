import re,sys,json
FENCE=re.compile(r"^\s*(`{3,}|~{3,})")
def sentences(text):
    lines=text.splitlines()
    out=[];i=0
    if lines and lines[0].strip()=="---":
        j=1
        while j<len(lines) and lines[j].strip()!="---": j+=1
        i=j+1
    fence=False
    for no in range(i,len(lines)):
        l=lines[no]
        if FENCE.match(l): fence=not fence; continue
        if fence: continue
        s=l.strip()
        if not s or s.startswith("#") or re.fullmatch(r"\|?[-\s|:]+\|?",s): continue
        s=re.sub(r"^[-*]\s+|^\d+\.\s+","",s)
        if s.startswith("|"):
            cells=[c.strip() for c in s.strip("|").split("|")]
            out.append((no+1," | ".join(cells))); continue
        for part in re.split(r"(?<=。)",s):
            part=part.strip()
            if len(part)>=6: out.append((no+1,part))
    return out
for p in sys.argv[1:]:
    for no,s in sentences(open(p,encoding="utf-8").read()):
        print(json.dumps({"file":p,"line":no,"sentence":s},ensure_ascii=False))
