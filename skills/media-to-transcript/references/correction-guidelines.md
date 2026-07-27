# Transcript Correction Guidelines

Use these rules after `scripts/media_to_transcript.py` creates `raw-transcript.md` and `correction-prompt.md`.

## Goal

Produce a final Markdown transcript, not subtitles and not a summary. The transcript should read like a faithful, lightly cleaned human transcript of the speaker's words.

## Allowed Edits

- Fix obvious ASR word errors, especially proper nouns, product names, English terms, model names, acronyms, numbers, and homophones.
- Add punctuation and paragraph breaks where they improve readability without changing meaning.
- Merge ASR utterance fragments into coherent transcript paragraphs.
- Use the title, topic, user context, glossary, nearby sentences, and visible source metadata to infer likely terminology.
- Keep section timestamps at paragraph/section level.

## Forbidden Edits

- Do not summarize or compress ideas.
- Do not rewrite into article prose or third-person narration.
- Do not delete口语词, repeated words, corrections, laughs, hesitations, or fillers unless they are duplicated only because of ASR chunking.
- Do not add information that is not supported by the transcript/context.
- Do not silently guess unclear names. Use `[听不清]` or `[疑似: 词语]` when uncertainty matters.

## Output Format

```markdown
# 标题

> 时长 12:34 | 来源: URL或文件名

## 1. 简短小标题 [00:00 - 01:20]

逐字稿正文。可以是多段，但不要切成字幕行。

## 2. 简短小标题 [01:20 - 03:05]

逐字稿正文。
```

Rules:

- Keep the title and source line from `raw-transcript.md` unless there is a clear correction.
- Section headings should be short and based on the content, not generic "逐字转写".
- Preserve chronological order and timestamps.
- For interviews or multi-speaker audio, keep clear speaker labels when AUC returned reliable labels.
- Remove only mechanical artifacts such as repeated ASR fragments, broken line wrapping, or duplicated speaker prefixes.

## Correction Pass Checklist

1. Scan title/topic/context for terms that ASR is likely to mishear.
2. Correct obvious technical vocabulary and names globally, but only when context supports it.
3. Rebuild paragraphs from ASR utterance chunks.
4. Rename generic section headings into content-based headings.
5. Check that timestamps remain monotonic.
6. Save the final transcript to `transcript.md`.
