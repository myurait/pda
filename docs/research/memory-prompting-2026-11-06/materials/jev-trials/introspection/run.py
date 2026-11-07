import json,sys,concurrent.futures
sys.path.insert(0,"/Users/fox4foofighter/docs/.claude/worktrees/memory-prompt-rules-fix-0521b9/jev/lib")
import jev_api
key=jev_api.load_api_key()
qs=json.load(open(sys.argv[1])); qid=list(qs)[0]
rows=[json.loads(l) for l in open("corpus.jsonl")]
def call(r):
    st,res,ms=jev_api.send({"model":"jev-latest","state":{"sentence":r["sentence"]},"questions":qs},key)
    return res.get("answers",{}).get(qid,{})
with concurrent.futures.ThreadPoolExecutor(8) as p: outs=list(p.map(call,rows))
hit=0;n=0
for r,a in zip(rows,outs):
    if "noul" in a: lab="observable" if a["noul"]>=0.5 else "judgment"; v=round(a["noul"],2)
    else: lab=a.get("choice","ERR"); v=round(a.get("confidence",0),2)
    g=r["gold"]
    if g=="not_a_rule":
        ok = lab in ("not_a_rule","observable")
    else: ok = lab==g
    n+=1; hit+=ok
    print(("OK  " if ok else "MISS"), r["id"], g, lab, v, r["sentence"][:55])
print(sys.argv[1], hit,"/",n)
