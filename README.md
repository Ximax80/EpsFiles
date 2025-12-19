# House Oversight Committee: Document Processing Pipeline

## LIVE: Auto-Processing and Publishing

**This repository is processing committee documents and publishing findings in real-time.**

As House Oversight Committee documents are analyzed, images are processed, text is extracted, and connections are revealed. The system automatically commits and publishes updates every 5 minutes with detailed summaries of the latest findings.

P25-12-19 15:02:44  
**Update Frequency:** Every 5 minutes  
**Status:** Processing continue with Gemini 3.0 Flash

### Latest Context Update

**Latest Image Analysis:**

- **Entities identified:** Keller (ladder manufacturer), unidentified search personnel (placeholders on search area marker).
- **Document types:** Photographic evidence, including interior residential shots, construction site documentation, and a search area identification card.
- **Notable findings:** The images document two distinct environments: a luxury residence and a construction zone. Residential photos (EFTA00000185–EFTA00000190) show high-end finishes, including a tufted leather ottoman, ornate cabinetry with crests, a bidet equipped with a landline telephone, and multiple framed personal photographs. Construction photos (EFTA00000191–EFTA00000194) show blue scaffolding, extensive plastic containment sheeting, and inventory boxes.

**Latest Text Processing:**

- **Entities identified:** Keller (brand), Search Personnel (Agency/Name placeholders).
- **Key themes:** Investigative site documentation, construction inventory, and chain of custody/search protocols.
- **Notable findings:** Text extracted from image EFTA00000192 reveals an official "Search Personnel" log card marked with a large letter "T," used to track agency names and contact numbers during a site search. Image EFTA00000193 contains inventory codes (1025, C1225, C1425, A1025) and a quantity count (QTY. 146), likely related to construction materials.

**Summary Analysis:**

- **ENTITIES:** The documents primarily identify equipment brands like Keller. While individuals are visible in framed portraits (EFTA00000187, EFTA00000190), they are not explicitly named in the text.
- **CONTEXT:** These images appear to be official evidentiary records from a legal or oversight investigation, as evidenced by the sequential Bates stamps (EFTA00000185–EFTA00000194). The mix of luxury living spaces and active construction/containment areas suggests a property undergoing significant renovation or a search conducted during a transition in the property's state.
- **SETTINGS:** The locations include a multi-room luxury suite (dressing rooms, vanities, bathrooms) and a renovation site. A digital clock in one image (EFTA00000187) displays "9:00," though the specific date is not legible. 
- **KEY FINDINGS:** The presence of a "Search Personnel" marker (EFTA00000192) used by an unnamed "Agency" strongly indicates these photographs were taken during the execution of a search warrant or an official site inspection. The focus on landline telephones in bathrooms and vanities, along with specific inventory counts on construction boxes, suggests a high level of detail in documenting the environment and items present during the investigative action.

---

## How Does This Work?

When the data is released by the committee, we expect to see a file structure similar to this:

<p align="center">
  <img src="./public/Datastructure.jpg" alt="Data Structure">
</p>

The committee typically releases different file types organized in all-capital folders. Once these files are added to this codebase, the process becomes fully automatic:

- **Parsing & Extraction:** Every image and document is parsed for names, dates, context, and full text. Even for long-form articles or extensive text, everything is extracted using **Gemini 3**.
- **Organization:** Extracted text is organized into specialized file formats designed to reveal connections among people, timestamps, and other critical details.
- **API Safety Filters:** Much of the content of these files will be flagged by the Google api filters, in those cases, it might be the refusal by google to touch it that is most helpful to reporters because they can manually go to that exact file and see why google wouldn't process it. This might cut the workload by 10X.
- **Rapid Deployment:** This pipeline is designed to be fully operational within one hour of the files being released by the committee.

---

## How to Start the Pipeline

> [!IMPORTANT]
> **You don't actually need to run anything.** I am processing the files with this code and publishing the results in real-time—this documentation is provided here for transparency. Unless you are a reporter working on a story, the updates published every 5 minutes at the top of this page will likely be the easiest and most effective way to access the information.

Follow these steps to start the full automated processing and publishing pipeline:

### 1. Environment Setup
Ensure you have your `GEMINI_API_KEY` configured in a `.env` file within the `PIPELINE` directory.

### 2. Launch Document Processing
This command starts the core analysis engine. It will process all images, text, and data files in the target batch.
```powershell
python PIPELINE/run_pipeline.py --process all --source DecemberBatch
```

### 3. Enable Auto-Publishing
In a separate terminal, launch the auto-commit webhook. This script monitors for new findings every 5 minutes, updates this README with a summary, and pushes all updates to the remote repository.
```powershell
python PIPELINE/auto_commit_webhook.py --interval 5
```

---

## Technical Overview

This repository contains a generalized automated system that processes thousands of House Oversight Committee documents using AI-powered analysis.

### Automated Document Processing Pipeline

The system runs multimodal processing streams simultaneously:

#### 1. Image Analysis & Entity Extraction
**All images are analyzed by Gemini 3.0 Flash** with:
- **OCR Text Extraction** - Full text extraction from every image
- **Entity Discovery** - Identifying people, organizations, and relationships
- **Visual Intelligence** - Document type classification and layout analysis
- **Structured Data** - Dates, names, locations, and signatures

#### 2. Text Document Processing
**Volumes of text documentation** are processed:
- Content extraction and context understanding
- Grouping related events into coherent narratives
- Narrative assembly and connection mapping

#### 3. Visual Summarization (Nano Banana)
**Gemini 3 Pro Image (Nano Banana)** generates high-fidelity editorial illustrations summarizing the most significant recent discoveries.

---

## Repository Structure

```
GovernmentPipeline/
├── PIPELINE/                   ← Core processing engine and tools
├── DecemberBatch/              ← Active source documents being processed
└── README.md                   ← Real-time status and overview
```

---

## Technical Details

### Processing Technology

- **AI Model:** Google Gemini 3.0 Flash (for text, image analysis, and reasoning)
- **Visual Summaries:** Nano Banana / Gemini 3 Pro Image (for editorial summaries)
- **Processing Method:** LLM-powered extraction and analysis
- **Output:** Structured JSON with full provenance tracking
- **Publishing:** Automated git commits via scheduled updates

### Data Integrity

- All original documents are **preserved unchanged**
- Analysis files are **additive only** (JSON metadata alongside originals)
- Full **provenance tracking** in all outputs
- **Transparent and verifiable** processing history

---

## Contact

For questions about this repository or the processing pipeline, see the technical documentation in the `PIPELINE` folder.
