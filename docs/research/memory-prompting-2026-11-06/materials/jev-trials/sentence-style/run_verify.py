import json,sys,concurrent.futures,collections
sys.path.insert(0,"/Users/fox4foofighter/docs/.claude/worktrees/memory-prompt-rules-fix-0521b9/jev/lib")
import jev_api
key=jev_api.load_api_key()
pat=sys.argv[1]; qs=json.load(open(pat))
rows=[json.loads(l) for l in open("jev/corpus.jsonl")]
def call(r):
    try:
        st,res,ms=jev_api.send({"model":"jev-latest","state":{"sentence":r["sentence"]},"questions":qs},key)
        return res
    except Exception as e: return {"err":repr(e)}
with concurrent.futures.ThreadPoolExecutor(8) as p: outs=list(p.map(call,rows))
ok=collections.Counter(); conf=collections.Counter(); out=[]
for r,o in zip(rows,outs):
    resp=None
    body=resp if resp is not None else o
    try: a=body["answers"]["sentence_label"]; lab=a.get("answer") or a.get("choice") or max(a["probabilities"],key=a["probabilities"].get); c=a.get("confidence")
    except Exception: lab="ERR"; c=None
    passed= lab in ("prescriptive","not_a_rule")
    ok[passed==r["pass"]]+=1; conf[(r["gold"],lab)]+=1
    out.append({"id":r["id"],"gold":r["gold"],"label":lab,"conf":c,"s":r["sentence"][:70]})
json.dump(out,open(pat.replace(".json",".result.json"),"w"),ensure_ascii=False,indent=0)
print(pat,"pass/fail一致",ok[True],"/",len(rows))
for k,v in sorted(conf.items()): print(k,v)
for x in out:
    if (x["label"] in ("prescriptive","not_a_rule"))!=(x["gold"] in ("prescriptive","not_a_rule")): print("MISS",x)
