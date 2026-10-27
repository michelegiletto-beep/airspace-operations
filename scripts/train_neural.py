"""Run a reproducible local teacher/student obligation-routing experiment.

All examples are actual source passages. Labels are machine-generated derived
annotations, never expert ground truth. Evaluation measures held-out agreement
with validated teacher annotations; it cannot establish legal reliability.
"""
from __future__ import annotations
import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import random
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
from airspace.neural import LocalEncoder, LocalTeacher, LABELS, MODAL, make_student


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def metrics(probabilities, labels):
    correct = sum(int(max(range(2), key=lambda i: p[i])) == y for p, y in zip(probabilities, labels))
    n = len(labels)
    if not n:
        return {"samples": 0, "accuracy": None}
    acc = correct / n
    z = 1.96
    mid = (acc + z*z/(2*n))/(1 + z*z/n)
    half = z*math.sqrt(acc*(1-acc)/n + z*z/(4*n*n))/(1 + z*z/n)
    confusion = [[0, 0], [0, 0]]
    for p, y in zip(probabilities, labels):
        confusion[y][max(range(2), key=lambda i: p[i])] += 1
    return {"samples": n, "accuracy": acc, "accuracy_wilson_95": [mid-half, mid+half],
            "brier_score": sum((p[1]-y)**2 for p,y in zip(probabilities, labels))/n,
            "confusion_rows_actual_columns_predicted": confusion,
            "meaning": "Agreement against unreviewed machine labels after source-span validation; not domain accuracy"}


def train_candidate(x, y, vx, vy, *, hidden_size, epochs, seed):
    import torch
    random.seed(seed)
    torch.manual_seed(seed)
    model = make_student(x.shape[1], hidden_size) if hidden_size else torch.nn.Linear(x.shape[1], 2)
    optimizer = torch.optim.AdamW(model.parameters(), lr=0.008, weight_decay=0.01)
    best_score, best_weights, history = float("inf"), None, []
    for epoch in range(epochs):
        model.train()
        optimizer.zero_grad()
        loss = torch.nn.functional.cross_entropy(model(x), y)
        loss.backward()
        optimizer.step()
        model.eval()
        with torch.inference_mode():
            value = float(torch.nn.functional.cross_entropy(model(vx), vy))
        if value < best_score:
            best_score = value
            best_weights = {k: v.detach().clone().contiguous() for k,v in model.state_dict().items()}
        if epoch % 10 == 0 or epoch == epochs-1:
            history.append({"epoch":epoch+1,"training_loss":float(loss.detach()),"validation_loss":value})
    model.load_state_dict(best_weights)
    return model, best_score, history


def main():
    import torch
    from safetensors.torch import save_file
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--device", choices=["cpu", "cuda"], default="cpu")
    parser.add_argument("--per-family", type=int, default=96)
    parser.add_argument("--epochs", type=int, default=120)
    parser.add_argument("--seed", type=int, default=20261027)
    parser.add_argument("--run-id", default="explicit-obligation-20261027-1")
    parser.add_argument("--teacher-component", choices=["teacher","teacher-base"], default="teacher")
    args = parser.parse_args()
    if not 24 <= args.per_family <= 512:
        raise ValueError("Bounded sample size must be between 24 and 512 passages per family")
    start = time.perf_counter()
    torch.set_num_threads(4)
    torch.manual_seed(args.seed)
    random.seed(args.seed)
    corpus_file = ROOT / "sources" / "corpus.json"
    corpus = json.loads(corpus_file.read_text(encoding="utf-8"))
    output = ROOT / "models" / "runs" / args.run_id
    if output.exists():
        raise ValueError("Run directory exists; choose a new run ID to preserve run lineage")
    output.mkdir(parents=True)
    families = {"eu-2019-947":"train", "eu-2019-945":"validation", "eu-2021-664":"test"}
    selected, seen_text = [], set()
    for family, split in families.items():
        candidates = [p for p in corpus if p["source_family"] == family and p["legal_status"] == "binding_legislation" and p.get("organisation_id") is None and p.get("licence",{}).get("redistribution") == "cleared_text_only" and 60 <= len(p["text"]) <= 700]
        candidates.sort(key=lambda p: hashlib.sha256((str(args.seed)+p["text"]).encode()).hexdigest())
        for has_modal in [False, True]:
            group = [p for p in candidates if bool(MODAL.search(p["text"])) == has_modal]
            count = 0
            for passage in group:
                text_hash = hashlib.sha256(passage["text"].lower().encode()).hexdigest()
                if text_hash in seen_text:
                    continue
                seen_text.add(text_hash)
                selected.append({**passage, "split":split})
                count += 1
                if count >= args.per_family//2:
                    break
    (output / "selected-passages.json").write_text(json.dumps(selected, indent=2),encoding="utf-8")
    print(json.dumps({"stage":"selected", "counts":dict(Counter(p["split"] for p in selected))}),flush=True)
    teacher_start = time.perf_counter()
    teacher = LocalTeacher(ROOT/"models"/"pretrained"/args.teacher_component,device=args.device)
    annotations = teacher.annotate(selected)
    teacher_seconds = time.perf_counter()-teacher_start
    del teacher
    if args.device == "cuda":
        torch.cuda.empty_cache()
    by_id = {a["passage_id"]:a for a in annotations}
    dataset = [{**p,"annotation":by_id[p["id"]]} for p in selected]
    (output / "annotations.json").write_text(json.dumps(annotations, indent=2),encoding="utf-8")
    (output / "dataset.jsonl").write_text("\n".join(json.dumps(p) for p in dataset)+"\n",encoding="utf-8")
    accepted = [p for p in dataset if p["annotation"]["status"] != "Quarantined"]
    counts = {split:dict(Counter(p["annotation"]["label"] for p in accepted if p["split"] == split)) for split in families.values()}
    print(json.dumps({"stage":"annotated", "accepted":counts,"quarantined":len(dataset)-len(accepted),"teacher_seconds":teacher_seconds}),flush=True)
    if any(len(counts[s]) < 2 for s in families.values()):
        (output/"run.json").write_text(json.dumps({"run_id":args.run_id,"status":"Blocked — teacher produced insufficient validated label diversity","counts":counts,"teacher_seconds":teacher_seconds,"annotations_checksum":digest(output/"annotations.json"),"ground_truth":False},indent=2),encoding="utf-8")
        raise ValueError("Insufficient teacher label diversity; annotations saved, training not claimed")
    encode_start = time.perf_counter()
    encoder = LocalEncoder(ROOT/"models"/"pretrained"/"encoder",device=args.device)
    vectors = torch.tensor(encoder.encode([p["text"] for p in accepted]),dtype=torch.float32)
    encode_seconds=time.perf_counter()-encode_start
    splits={}
    for split in families.values():
        indices=[i for i,p in enumerate(accepted) if p["split"] == split]
        splits[split]=(vectors[indices],torch.tensor([LABELS.index(accepted[i]["annotation"]["label"]) for i in indices]))
    x,y=splits["train"];vx,vy=splits["validation"];tx,ty=splits["test"]
    experiments=[]
    candidate_models=[]
    training_start=time.perf_counter()
    # Architecture selection uses validation family only. Test family is held out.
    for hidden in [16,32,64]:
        model,val_loss,history=train_candidate(x,y,vx,vy,hidden_size=hidden,epochs=args.epochs,seed=args.seed)
        with torch.inference_mode():
            validation=metrics(torch.softmax(model(vx),1).tolist(),vy.tolist())
        experiments.append({"hidden_size":hidden,"validation_loss":val_loss,"validation":validation,"history":history})
        candidate_models.append(model)
    best=min(range(len(experiments)),key=lambda i:experiments[i]["validation_loss"])
    model=candidate_models[best]
    hidden_size=experiments[best]["hidden_size"]
    training_seconds=time.perf_counter()-training_start
    with torch.inference_mode():
        student_probs=torch.softmax(model(tx),1).tolist()
    # Deterministic, majority, lexical-trained, and frozen pretrained baselines.
    test_rows=[p for p in accepted if p["split"] == "test"]
    deterministic=[[0.,1.] if MODAL.search(p["text"]) else [1.,0.] for p in test_rows]
    majority=int(y.float().mean()>=0.5)
    majority_probs=[[float(majority==0),float(majority==1)] for _ in test_rows]
    prototypes=torch.tensor(encoder.encode(["A passage without the word shall.","An explicit shall-language passage for reviewer routing."]),dtype=torch.float32)
    pretrained_probs=torch.softmax(tx @ prototypes.T * 10,1).tolist()
    def lexical_vector(text):
        out=[0.]*256
        for word in __import__('re').findall(r'[a-z]+',text.lower()):
            out[int(hashlib.sha256(word.encode()).hexdigest()[:8],16)%256]+=1
        norm=math.sqrt(sum(v*v for v in out)) or 1
        return [v/norm for v in out]
    lx=torch.tensor([lexical_vector(p['text']) for p in accepted if p['split']=='train'])
    lv=torch.tensor([lexical_vector(p['text']) for p in accepted if p['split']=='validation'])
    lt=torch.tensor([lexical_vector(p['text']) for p in test_rows])
    lexical_model,_,_=train_candidate(lx,y,lv,vy,hidden_size=0,epochs=args.epochs,seed=args.seed)
    with torch.inference_mode():
        lexical_probs=torch.softmax(lexical_model(lt),1).tolist()
    evaluation={"student":metrics(student_probs,ty.tolist()),"deterministic_modal":metrics(deterministic,ty.tolist()),"lexical_trained_linear":metrics(lexical_probs,ty.tolist()),"pretrained_prototype":metrics(pretrained_probs,ty.tolist()),"majority":metrics(majority_probs,ty.tolist())}
    save_file({k:v.contiguous() for k,v in model.state_dict().items()},str(output/"student.safetensors"))
    failures=[{"passage_id":p["id"],"source_anchor":p["anchor"],"machine_label":LABELS[y],"student_label":LABELS[max(range(2),key=lambda i:prob[i])]} for p,prob,y in zip(test_rows,student_probs,ty.tolist()) if max(range(2),key=lambda i:prob[i])!=y]
    run={"run_id":args.run_id,"created_at":datetime.now(timezone.utc).isoformat(),"status":"Training and held-out machine-agreement evaluation completed",
         "promotion_status":"Experimental — Not promoted","task":"Classify the literal presence of shall in real source passages for reviewer routing; no assertion of legal obligation or dispatch authority",
         "architecture":{"type":"Frozen pretrained MiniLM encoder + trained two-layer ReLU MLP","input_size":384,"hidden_size":hidden_size,"outputs":LABELS,"trainable_parameters":sum(p.numel() for p in model.parameters())},
         "seed":args.seed,"epochs_max":args.epochs,"dataset":{"input_corpus_checksum":digest(corpus_file),"selected_checksum":digest(output/"selected-passages.json"),"annotations_checksum":digest(output/"annotations.json"),"rows":len(dataset),"accepted_rows":len(accepted),"quarantined_rows":len(dataset)-len(accepted),"split_label_counts":counts,"split_policy":families,"exact_text_overlap":False,"human_reviewed_rows":0,"ground_truth":False,"stratification":"Deterministic explicit-modal marker used for balanced sampling only","selection_bias":"Source-span validation removes inconsistent teacher labels; metrics are conditioned on that filter"},
         "base_models":{name:json.loads((ROOT/'models'/'pretrained'/name/'provenance.json').read_text()) for name in [args.teacher_component,'encoder']},
         "experiments":experiments,"evaluation":evaluation,"failure_cases":failures,
         "resources":{"device":args.device,"gpu":torch.cuda.get_device_name(0) if args.device=='cuda' else None,"torch":torch.__version__,"python":sys.version.split()[0],"teacher_seconds":teacher_seconds,"encoding_seconds":encode_seconds,"training_seconds":training_seconds,"total_seconds":time.perf_counter()-start},
         "artifact_checksum":digest(output/'student.safetensors'),"promotion_blockers":["No qualified human-labelled evaluation","Single snapshot per source family; time/version holdout unexecuted","No established benefit over deterministic explicit-marker routing","No calibrated legal reliability","No operational records or operational prediction training","Retrieval quality and legal citation support need expert evaluation"]}
    (output/"run.json").write_text(json.dumps(run,indent=2),encoding="utf-8")
    print(json.dumps({"stage":"completed","run_id":args.run_id,"architecture":run['architecture'],"evaluation":evaluation,"resources":run['resources']}),flush=True)


if __name__ == '__main__':
    main()
