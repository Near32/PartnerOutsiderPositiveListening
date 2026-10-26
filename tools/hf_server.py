"""Minimal OpenAI-compatible /v1/chat/completions server for one transformers model (serial, bf16).

Used for the paraphraser, Qwen/Qwen2.5-7B-Instruct, with the same weights and chat template as the
NLA paper's rewriter. temperature 0 -> greedy (the NLA rewriter's first attempt), else sampling.
Run with the torch-ROCm venv, under the memory guard, with Ollama models unloaded:
  python tools/hf_server.py [model] [port]      # needs torch + transformers and a GPU (see README)
ponytail: serial, one request at a time; batching did not beat Ollama (data/timing/hf_bench_*.jsonl).
"""
import json
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer

MODEL = sys.argv[1] if len(sys.argv) > 1 else "Qwen/Qwen2.5-7B-Instruct"
PORT = int(sys.argv[2]) if len(sys.argv) > 2 else 8011
tok = AutoTokenizer.from_pretrained(MODEL)
lm = AutoModelForCausalLM.from_pretrained(MODEL, dtype=torch.bfloat16, device_map="cuda").eval()


class H(BaseHTTPRequestHandler):
    def do_POST(self):
        req = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        if req["model"] != MODEL:
            return self._send(400, {"error": {"message": f"this server serves {MODEL}, not {req['model']}"}})
        ids = tok.apply_chat_template(req["messages"], add_generation_prompt=True, return_tensors="pt").to(lm.device)
        t = req.get("temperature") or 0.0
        kw = dict(do_sample=True, temperature=t, top_p=req.get("top_p", 1.0)) if t > 0 else dict(do_sample=False)
        with torch.no_grad():
            out = lm.generate(ids, attention_mask=torch.ones_like(ids), pad_token_id=tok.eos_token_id,
                              max_new_tokens=min(req.get("max_tokens") or 1024, 4096), **kw)
        gen = out[0, ids.shape[1]:]
        self._send(200, {"choices": [{"index": 0, "finish_reason": "stop",
                                      "message": {"role": "assistant",
                                                  "content": tok.decode(gen, skip_special_tokens=True).strip()}}],
                         "usage": {"prompt_tokens": ids.shape[1], "completion_tokens": int(gen.shape[0])}})

    def _send(self, code, body):
        data = json.dumps(body).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


print(f"serving {MODEL} on 127.0.0.1:{PORT}", flush=True)
HTTPServer(("127.0.0.1", PORT), H).serve_forever()
