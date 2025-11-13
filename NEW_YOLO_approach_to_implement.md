# Comprehensive Workflow: Integrating Roboflow and LangGraph for Roof Damage Detection and Reasoning

This Markdown document outlines a complete, end-to-end workflow for building an AI system that detects, outlines, classifies roof damage from photos, and layers reasoning for severity assessment and classification certainty. The system uses:

- **Roboflow**: For computer vision (CV) tasks like fine-tuning YOLOv11 models for detection, segmentation (outlining), and classification.
- **LangGraph**: For orchestrating AI agents that reason over Roboflow outputs using an LLM (e.g., Grok or GPT-4o) to assess damage severity and provide certainty explanations.

The workflow is designed to be **parseable and implementable by an LLM** (e.g., via code generation or step-by-step execution). It includes:
- **Prerequisites**: Setup requirements.
- **Steps**: Sequential instructions, with code snippets.
- **Human Actions**: Marked where manual intervention is needed (e.g., API keys, data upload).
- **Integration Points**: How Roboflow feeds into LangGraph.
- **Deployment Notes**: Scaling and testing.

This assumes Python 3.10+ and access to AWS (as discussed previously) for fine-tuning. Total implementation time: 1-2 hours for a basic version, plus training time.

---

## Prerequisites

### Software and Libraries
- Install via uv:
  ```bash
  uv install roboflow ultralytics langgraph langchain langchain-openai python-dotenv opencv-python pillow
  ```
- For open-source LLM alternatives: Use `langchain-huggingface` instead of `langchain-openai`.

### API Keys and Accounts
- **Human Action Needed**: Sign up for Roboflow (free tier) at [roboflow.com](https://roboflow.com) and get an API key from the dashboard.
- **Human Action Needed**: Sign up for an LLM provider (e.g., xAI for Grok API, OpenAI for GPT-4o) and obtain an API key.
- Create a `.env` file:
  ```
  ROBOFLOW_API_KEY=your_roboflow_key
  OPENAI_API_KEY=your_llm_key  # Or GROK_API_KEY if using xAI
  ```

### Hardware
- For fine-tuning: AWS EC2 GPU instance (e.g., g5.xlarge) as per previous setup.
- For inference/reasoning: Local machine or cloud CPU/GPU.

---

## Step 1: Roboflow - Dataset Preparation and Model Fine-Tuning

Roboflow handles CV: Combining datasets, fine-tuning YOLOv11 for detection (bounding boxes), segmentation (outlining masks), and classification (damage types like "crack", "hail_dent").

### 1.1 Combine Datasets
- Use Roboflow Universe to fork and merge datasets (as detailed previously).
- **Human Action Needed**: Manually fork 2-4 relevant datasets (e.g., "roof-damage" by reworked, "Roof Damage Detection" by Keyan) via the Roboflow UI.
- In Roboflow UI:
  1. Create a new project: `roof-damage-combined`.
  2. Add forked datasets.
  3. Normalize classes (e.g., map "fracture" to "crack").
  4. Apply augmentations: Flip horizontal, rotation ±15°, brightness ±25%.
  5. Generate version and export as "YOLOv11 PyTorch TXT".

- **LLM-Implementable Code** (after export):
  ```python
  from roboflow import Roboflow
  import os
  from dotenv import load_dotenv

  load_dotenv()
  rf = Roboflow(api_key=os.getenv("ROBOFLOW_API_KEY"))

  # Download merged dataset (replace with your project/version)
  project = rf.workspace("your_workspace").project("roof-damage-combined")
  dataset = project.version(1).download("yolov11", location="datasets/roof-damage")
  ```

### 1.2 Fine-Tune YOLOv11 Model
- Launch AWS EC2 GPU instance (human action if not automated).
- **Human Action Needed**: SSH into AWS instance and upload dataset ZIP via SCP or S3.
- Train on GPU:
  ```bash
  yolo train model=yolo11n-seg.pt data=datasets/roof-damage/data.yaml epochs=15 batch=32 imgsz=640 device=0
  ```
- **LLM-Implementable Python Equivalent** (for scripting):
  ```python
  from ultralytics import YOLO

  model = YOLO("yolo11n-seg.pt")
  results = model.train(
      data="datasets/roof-damage/data.yaml",
      epochs=15,
      imgsz=640,
      batch=32,
      device=0  # GPU
  )
  model.export(format="onnx")  # For deployment
  ```

- Output: Trained model (`best.pt` or `best.onnx`) with capabilities for detection, outlining (masks), classification, and confidence scores.

---

## Step 2: Roboflow - Inference for Detection, Outlining, and Classification

Run predictions on new photos to get raw CV outputs (JSON with boxes, masks, classes, confidences).

- **LLM-Implementable Code**:
  ```python
  from roboflow import Roboflow
  import os
  from dotenv import load_dotenv

  load_dotenv()
  rf = Roboflow(api_key=os.getenv("ROBOFLOW_API_KEY"))

  # Load fine-tuned model (replace with your project/version)
  project = rf.workspace("your_workspace").project("roof-damage-combined")
  model = project.version(1).model

  # Infer on a photo
  prediction = model.predict("path/to/roof_photo.jpg", confidence=40, overlap=30).json()

  # Example output structure
  # {
  #   "predictions": [
  #     {"class": "crack", "confidence": 0.87, "x": 640, "y": 320, "width": 200, "height": 80, "mask": "base64_polygon..."}
  #   ]
  # }

  # Save annotated image (with outlines/overlays)
  model.predict("path/to/roof_photo.jpg").save("annotated_roof.jpg")
  ```

- **Human Action Needed**: Provide photo paths or upload via API for batch processing.
- This step feeds JSON to LangGraph for reasoning.

---

## Step 3: LangGraph - Building the Reasoning Workflow

LangGraph creates a stateful graph with nodes for processing Roboflow outputs, LLM reasoning on severity/certainty, and output generation.

### 3.1 Define State and Nodes
- State tracks image path, Roboflow predictions, and reasoning results.

- **LLM-Implementable Code**:
  ```python
  from typing import TypedDict, List, Annotated
  from langgraph.graph import StateGraph, END
  from langchain_openai import ChatOpenAI  # Or your LLM provider
  from langchain_core.prompts import ChatPromptTemplate
  from langchain_core.messages import HumanMessage
  import operator
  import os
  from dotenv import load_dotenv
  import json

  load_dotenv()
  llm = ChatOpenAI(model="gpt-4o", api_key=os.getenv("OPENAI_API_KEY"))  # Swap for Grok if needed

  class RoofState(TypedDict):
      image_path: str
      predictions: dict  # Roboflow JSON
      severity_assessment: str
      certainty_explanation: str
      final_report: str

  # Node 1: Run Roboflow Inference
  def run_roboflow(state: RoofState) -> RoofState:
      # Integrate Roboflow code from Step 2
      rf = Roboflow(api_key=os.getenv("ROBOFLOW_API_KEY"))
      model = rf.workspace("your_workspace").project("roof-damage-combined").version(1).model
      state["predictions"] = model.predict(state["image_path"], confidence=40, overlap=30).json()
      return state

  # Node 2: LLM Reasoning on Severity
  def assess_severity(state: RoofState) -> RoofState:
      preds = json.dumps(state["predictions"])
      prompt = ChatPromptTemplate.from_messages([
          ("system", "Assess roof damage severity (1-10) based on type, size, location, and count. High conf + large area = severe."),
          ("human", "Predictions: {preds}")
      ])
      response = llm.invoke(prompt.format(preds=preds))
      state["severity_assessment"] = response.content
      return state

  # Node 3: LLM Reasoning on Certainty
  def explain_certainty(state: RoofState) -> RoofState:
      preds = json.dumps(state["predictions"])
      prompt = ChatPromptTemplate.from_messages([
          ("system", "Explain classification certainty: High if conf >0.8 and clear masks; low if ambiguous."),
          ("human", "Predictions: {preds}")
      ])
      response = llm.invoke(prompt.format(preds=preds))
      state["certainty_explanation"] = response.content
      return state

  # Node 4: Generate Final Report
  def generate_report(state: RoofState) -> RoofState:
      state["final_report"] = f"Severity: {state['severity_assessment']}\nCertainty: {state['certainty_explanation']}\nPredictions: {json.dumps(state['predictions'])}"
      return state
  ```

### 3.2 Build and Compile the Graph
- **LLM-Implementable Code**:
  ```python
  workflow = StateGraph(RoofState)

  workflow.add_node("roboflow_inference", run_roboflow)
  workflow.add_node("assess_severity", assess_severity)
  workflow.add_node("explain_certainty", explain_certainty)
  workflow.add_node("generate_report", generate_report)

  # Edges: Sequential flow
  workflow.add_edge("roboflow_inference", "assess_severity")
  workflow.add_edge("assess_severity", "explain_certainty")
  workflow.add_edge("explain_certainty", "generate_report")
  workflow.add_edge("generate_report", END)

  # Entry point
  workflow.set_entry_point("roboflow_inference")

  # Compile
  app = workflow.compile()
  ```

### 3.3 Run the Workflow
- **Human Action Needed**: Provide initial image path.
- **LLM-Implementable Code**:
  ```python
  initial_state = {"image_path": "path/to/roof_photo.jpg"}
  result = app.invoke(initial_state)
  print(result["final_report"])
  ```

- **Human Action Needed**: Review and iterate on LLM prompts if reasoning outputs are suboptimal.

---

## Step 4: Integration and Testing

- **Full Pipeline Execution**: The LangGraph entry node calls Roboflow automatically.
- **Testing**:
  1. Run on sample photos.
  2. Validate outputs: Check JSON for accuracy, severity scores for logic.
- **Edge Cases**: Handle no-damage photos (e.g., add conditional edges in LangGraph: `if not predictions: END`).
- **Human Action Needed**: Monitor for false positives; retrain model if needed by uploading more labeled data to Roboflow.

---

## Deployment Notes

- **Local/Cloud**: Run as Python script or deploy via FastAPI for API endpoint.
- **Scaling**: Use AWS Lambda for inference; Roboflow hosted models for CV to avoid local compute.
- **Monitoring**: Log states in LangGraph for debugging.
- **Extensions**: Add nodes for email reports or UI integration (e.g., Streamlit).
- **Costs**: Roboflow free tier (1k inferences/month); LLM calls ~$0.01/query.

This workflow is modular— an LLM can parse sections (e.g., via regex on headers) to generate code or automate sub-steps. If implementing via code gen, focus on replacing placeholders (e.g., workspace names). For production, add error handling (e.g., retries on API failures).