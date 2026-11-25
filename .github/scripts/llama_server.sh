#!/bin/sh
# llama_server.sh: start an open model on the runner for tools/judge_speech.py --backend local.
#
#   LLAMA_CPP_TAG             llama.cpp release to use (e.g. b12700, or latest): its prebuilt Linux CPU binaries
#   SPEECH_JUDGE_LOCAL_MODEL  the model, as llama.cpp's -hf takes it: user/repo:quant (from Hugging Face)
#   LLAMA_CACHE               where the model is downloaded (cached between runs by the workflow)
#   GH_TOKEN                  (optional) for the GitHub API, to find the release's files
#
# Leaves llama-server running on http://127.0.0.1:8080 and its log in speech/llama-server.log.
set -eu
: "${LLAMA_CPP_TAG:?}" "${SPEECH_JUDGE_LOCAL_MODEL:?}"
mkdir -p speech "${LLAMA_CACHE:-$HOME/.cache/llama.cpp}"

api() {
  if [ -n "${GH_TOKEN:-}" ]; then curl -fsSL -H "Authorization: Bearer $GH_TOKEN" "$1"; else curl -fsSL "$1"; fi
}
if [ "$LLAMA_CPP_TAG" = latest ]; then rel=latest; else rel="tags/$LLAMA_CPP_TAG"; fi
api "https://api.github.com/repos/ggml-org/llama.cpp/releases/$rel" > /tmp/llama-release.json \
  || { echo "llama.cpp release $LLAMA_CPP_TAG not found (set LLAMA_CPP_TAG to an existing release, or latest)"; exit 1; }
url=$(python3 -c 'import json,sys; r=json.load(open("/tmp/llama-release.json")); a=[x["browser_download_url"] for x in r["assets"] if x["name"].endswith(("bin-ubuntu-x64.tar.gz","bin-ubuntu-x64.zip"))]; print(a[0] if a else "")')
[ -n "$url" ] || { echo "llama.cpp $LLAMA_CPP_TAG has no Linux x64 binaries"; exit 1; }
echo "llama.cpp: $url"
mkdir -p /opt/llama
curl -fsSL -o /opt/llama/llama.pkg "$url"
case "$url" in
  *.zip) python3 -m zipfile -e /opt/llama/llama.pkg /opt/llama ;;
  *) tar -xzf /opt/llama/llama.pkg -C /opt/llama ;;
esac
server=$(find /opt/llama -name llama-server -type f | head -n1)
chmod +x "$server"
export LD_LIBRARY_PATH="$(dirname "$server")${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
"$server" --version 2>&1 | head -n 2

# 32k tokens of context (a 24k-character part plus the instructions and the answer); all cores
nohup "$server" -hf "$SPEECH_JUDGE_LOCAL_MODEL" --no-mmproj --jinja -c 32768 -t "$(nproc)" \
  --host 127.0.0.1 --port 8080 > speech/llama-server.log 2>&1 &

# wait for the download and the load (up to 30 minutes)
i=0
until curl -fs http://127.0.0.1:8080/health >/dev/null 2>&1; do
  i=$((i + 1))
  if [ $i -gt 360 ] || ! kill -0 $! 2>/dev/null; then
    echo "llama-server did not start:"; tail -n 40 speech/llama-server.log; exit 1
  fi
  sleep 5
done
echo "llama-server ready after about $((i * 5)) s with $SPEECH_JUDGE_LOCAL_MODEL"
