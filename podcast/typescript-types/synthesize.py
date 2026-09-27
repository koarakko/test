#!/usr/bin/env python3
import json, re, subprocess, time, urllib.parse, urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent
VOICE = ROOT / "voice.txt"
OUT = ROOT / "out"
WAV = OUT / "wav"
STYLE_ID = 13
MAX_CHARS = 240
SPEED_SCALE = 1.05

def post(url, data=None, headers=None):
    req = urllib.request.Request(url, data=data, headers=headers or {}, method="POST")
    with urllib.request.urlopen(req, timeout=120) as r:
        return r.read()

def wait_engine():
    for _ in range(120):
        try:
            with urllib.request.urlopen("http://127.0.0.1:50021/version", timeout=2) as r:
                print("VOICEVOX ENGINE", r.read().decode())
                return
        except Exception:
            time.sleep(1)
    raise RuntimeError("VOICEVOX ENGINE did not become ready")

def split_text(text):
    text = re.sub(r"\n{3,}", "\n\n", text.strip())
    paras = [p.strip() for p in text.split("\n\n") if p.strip()]
    chunks = []
    for p in paras:
        if len(p) <= MAX_CHARS:
            chunks.append(p)
            continue
        sentences = re.split(r"(?<=[。！？])", p)
        buf = ""
        for s in sentences:
            s = s.strip()
            if not s:
                continue
            if len(buf) + len(s) <= MAX_CHARS:
                buf += s
            else:
                if buf:
                    chunks.append(buf)
                while len(s) > MAX_CHARS:
                    cut = s.rfind("、", 0, MAX_CHARS)
                    if cut < MAX_CHARS // 2:
                        cut = MAX_CHARS
                    chunks.append(s[:cut+1])
                    s = s[cut+1:]
                buf = s
        if buf:
            chunks.append(buf)
    return chunks

def synthesize(text, out_path):
    qurl = "http://127.0.0.1:50021/audio_query?" + urllib.parse.urlencode({"speaker": STYLE_ID, "text": text})
    query = json.loads(post(qurl).decode("utf-8"))
    query["speedScale"] = SPEED_SCALE
    query["outputSamplingRate"] = 48000
    query["outputStereo"] = False
    surl = "http://127.0.0.1:50021/synthesis?" + urllib.parse.urlencode({"speaker": STYLE_ID})
    wav = post(surl, json.dumps(query, ensure_ascii=False).encode("utf-8"), {"Content-Type":"application/json"})
    out_path.write_bytes(wav)

def main():
    OUT.mkdir(exist_ok=True)
    WAV.mkdir(exist_ok=True)
    wait_engine()
    text = VOICE.read_text(encoding="utf-8")
    chunks = split_text(text)
    (OUT / "chunks.json").write_text(json.dumps(chunks, ensure_ascii=False, indent=2), encoding="utf-8")
    print("chunks:", len(chunks))
    for i, c in enumerate(chunks, 1):
        p = WAV / f"{i:04d}.wav"
        if p.exists() and p.stat().st_size > 1000:
            continue
        print(f"[{i}/{len(chunks)}] {c[:60]}")
        synthesize(c, p)
    concat = OUT / "concat.txt"
    concat.write_text("".join(f"file '{p.resolve()}'\n" for p in sorted(WAV.glob("*.wav"))), encoding="utf-8")
    subprocess.run([
        "ffmpeg","-y","-f","concat","-safe","0","-i",str(concat),
        "-ar","48000","-ac","1","-b:a","128k",str(OUT / "typescript-types-podcast.mp3")
    ], check=True)
    subprocess.run(["ffprobe","-v","error","-show_entries","format=duration,size,bit_rate","-of","json",str(OUT / "typescript-types-podcast.mp3")], check=True)

if __name__ == "__main__":
    main()
