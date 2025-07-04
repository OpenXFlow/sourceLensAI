# How to Analyze YouTube Content with SourceLens

A powerful feature of the `FL02_web_crawling` flow is its ability to download, process, and analyze the content of YouTube videos. This guide details how this process works, how to configure it, and what to expect from the output.

## Table of Contents
1.  [The YouTube Processing Workflow](#1-the-youtube-processing-workflow)
2.  [How to Run a YouTube Analysis](#2-how-to-run-a-youtube-analysis)
3.  [Configuration Options](#3-configuration-options)
4.  [Understanding the Output Files](#4-understanding-the-output-files)
5.  [Hidden Feature: Audio Extraction](#5-hidden-feature-audio-extraction)

---

### 1. The YouTube Processing Workflow

When you provide a YouTube URL, `sourceLens` triggers a specialized sub-flow:

1.  **Metadata and Transcript Fetch:** The `FetchYouTubeContent` node uses the `yt-dlp` library to download the video's metadata (title, description, uploader) and the best available transcript (subtitles).
2.  **Transcript Prioritization:** The node prioritizes transcripts based on your configuration, typically preferring manually created subtitles over auto-generated ones (ASR) for better accuracy.
3.  **Initial Cleaning & Deduplication:** The downloaded transcript (in VTT format) is cleaned of any empty cues. Then, it undergoes an LLM-powered deduplication pass to remove stutters and repetitive phrases while carefully preserving the time-block headers (e.g., `#### [01:23]`).
4.  **Translation & Reformatting (LLM-Powered):** The `TranslateYouTubeTranscript` node takes the cleaned original transcript and uses an LLM to:
    *   Translate the text into your desired target language (defined in `config.json`).
    *   **Remove all time-block headers.**
    *   Reformat the entire text into clean, grammatically complete sentences, each on a new line, grouped into logical paragraphs.
5.  **Final Output Generation:** The `CombineWebSummary` node assembles the final output files, including the original and final transcripts.
6.  **Extended Analysis (Optional):** If `processing_mode` is set to `"llm_extended"`, the video's description and the final, clean transcript are passed to the rest of the web analysis pipeline to identify concepts, write chapters, and create a review, just like with a standard web page.

### 2. How to Run a YouTube Analysis

Use the `sourcelens web` command with the `--crawl-file` argument.

```bash
# Basic command to analyze a YouTube video
sourcelens web --crawl-file "https://www.youtube.com/watch?v=your_video_id_here"

# Analyze and generate the summary in a different language
sourcelens web --crawl-file "https://youtu.be/your_video_id_here" --language "slovak"
```

### 3. Configuration Options

You can fine-tune the YouTube processing in the `FL02_web_crawling.youtube_processing` section of your `config.json`.

*   **`expected_transcript_languages_on_yt`**: This is the most important setting. It's a **prioritized list** of language codes `sourceLens` should look for.
    *   **Example:** `["en", "sk", "de"]`
    *   **Behavior:** `sourceLens` will first search for an English (`en`) transcript. If it finds one, it will use it and stop searching. If not, it will then look for Slovak (`sk`), and so on.

### 4. Understanding the Output Files

The output for a YouTube analysis is created in a dedicated run folder (e.g., `output/20250627_1200_yt-my-video-title/`).

*   **`web_summary_index.md`**: The main landing page for the analysis, with links to the files below.
*   **`page_content/pg_{video_title}.md`**: A summary page containing the video's title, description, and links to the transcript files.

*   **`transcripts/` Subdirectory:** This is where the core transcript content is stored.
    *   **`ts_{video_title}_{lang}_orig.md`**: The **original transcript** as downloaded from YouTube, after the initial AI-powered cleaning. It **includes time-block headers** (e.g., `#### [01:23]`), making it useful for finding specific moments in the video.
    *   **`ts_{video_title}_{lang}_final.md`**: The **final, processed transcript**. This version is translated and fully reformatted by the LLM. It has **no time blocks** and is structured into clean sentences and paragraphs, making it highly readable and ideal for use as a knowledge source.

### 5. Hidden Feature: Audio Extraction

For advanced use cases, you can instruct `sourceLens` to download the audio track of the video as an `.mp3` file.

*   **How to Activate:** Add the hidden `--extract-audio` flag to your command. This flag is not shown in the `--help` menu.
    ```bash
    sourcelens web --crawl-file "https://www.youtube.com/watch?v=..." --extract-audio
    ```
*   **Output:** If successful, an `audio/` subdirectory will be created in your run folder containing the `{video_title}.mp3` file.
*   **Prerequisites:** This feature requires that you have `ffmpeg` installed on your system and available in your PATH, as `yt-dlp` uses it for audio conversion.

