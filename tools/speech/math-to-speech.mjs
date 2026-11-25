// math-to-speech.mjs: MathML to the words a screen reader says, with Speech Rule Engine
// (https://speechruleengine.org, the engine behind MathJax's speech; NVDA's MathCAT gives similar
// ClearSpeak wording). Used by tools/check_speech.py; not run on its own.
//
//   input  (stdin)   one JSON object per line: {"id": "...", "mathml": "<math>...</math>"}
//   output (stdout)  one JSON object per line: {"id": "...", "speech": "..."} or {"id": ..., "error": ...}
//
// Setup once:  npm ci --prefix tools/speech   (SRE's version is pinned in package-lock.json)
import { createInterface } from "node:readline";
import sre from "speech-rule-engine";

const style = process.env.SPEECH_STYLE || "clearspeak"; // or mathspeak
await sre.setupEngine({ locale: "en", domain: style, modality: "speech" });
await sre.engineReady();

const rl = createInterface({ input: process.stdin, crlfDelay: Infinity });
for await (const line of rl) {
  if (!line.trim()) continue;
  const { id, mathml } = JSON.parse(line);
  let out;
  try {
    out = { id, speech: sre.toSpeech(mathml).trim() };
  } catch (e) {
    out = { id, error: String(e && e.message ? e.message : e) };
  }
  process.stdout.write(JSON.stringify(out) + "\n");
}
