# The AI judge

The speech check (`tools/check_speech.py`) finds what rules can find. For tags and for builds you start by hand, a language model can also read `spoken.txt` and say whether a blind reader could follow it: PASS or FAIL, and on FAIL `speech-judge.pdf` in the *speech* artifact lists what a listener hears, why that is a problem and how to fix it. It reports only what the rules miss, such as maths that comes out garbled. This sends your thesis text to the model's provider, so leave it off if that is not allowed for your thesis. Without a key nothing is sent and the judge is skipped.

1. **Get a key.** For Claude: sign in at [platform.claude.com](https://platform.claude.com), open [Settings → API keys](https://platform.claude.com/settings/keys) and click *Create key* (give it a name and an expiry date, e.g. your submission date). API use is paid separately from a Claude subscription: add a little credit under *Billing*; a run on this template costs about ten cents, a whole thesis a few times that. Copy the key; you only need it for the next step, so you need not keep it (lost? make a new one).
2. **Give it to GitHub.** In your repository: *Settings → Secrets and variables → Actions → New repository secret*, name `ANTHROPIC_API_KEY`, value the key. Never put a key in a file in the repository.
3. **Run it.** *Actions → Build → Run workflow*, with *judge* set to `claude`; afterwards, the run's summary has the verdict and the *speech* artifact the report. Tags run it by themselves.

Settings, all optional (*Settings → Secrets and variables → Actions → Variables*): `SPEECH_JUDGE_MODEL` picks another Claude model (default `claude-sonnet-5-5`); `SPEECH_JUDGE_BACKEND` set to `claude` runs the judge on every push (`none`: never); `SPEECH_JUDGE_ADVISORY` set to `true` keeps the build green when only the model finds a problem. **Another provider** works too, if it offers an OpenAI-compatible API: a secret `SPEECH_JUDGE_API_KEY` with its key, and variables `SPEECH_JUDGE_URL` and `SPEECH_JUDGE_MODEL` with its address and model name:

| Provider | `SPEECH_JUDGE_URL` |
|---|---|
| OpenAI | `https://api.openai.com/v1` |
| Mistral | `https://api.mistral.ai/v1` |
| Google Gemini | `https://generativelanguage.googleapis.com/v1beta/openai` |
| OpenRouter (many models, one key) | `https://openrouter.ai/api/v1` |

Locally: `python3 tools/judge_speech.py` after `tools/check_speech.py`, with the key in the environment (`ANTHROPIC_API_KEY=... python3 tools/judge_speech.py`); `--focus` sends only the lines that can go wrong (about 40 % less), `--help` lists the rest, including a model on your own machine through [Ollama](https://ollama.com) (`http://localhost:11434/v1`, no key, nothing leaves your computer).
