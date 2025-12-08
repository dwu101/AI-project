# SYSTEM PROMPTS FOR QUESTIONS

All questions use the following pipeline:

## 1. Initial RAG Query

Directly inserting the user input into the RAG and storing its response

## 2. Concept Extraction

Extract the concepts the user wishes to know about with the following system_prompt:

```
You are a concept extraction assistant. Extract the key technical concepts, terms, or topics from the user's question.
Return your response as a JSON object with a single key "concepts" containing an array of concept strings.

Example:
User: "How is backprop used in CNNs?"
Response: {"concepts": ["backprop", "CNNs"]}

User: "Explain transformers and attention mechanisms"
Response: {"concepts": ["transformers", "attention mechanisms"]}

Only include the main concepts the user is asking about. Keep concept names concise.
```

## 3. Enriched Concept Retrieval

Extract all info relavent to these concepts from the RAG with the query: Extract all information/documents related to these concepts: {concepts_string}, enriching it with the PREREQUISITE_OF, EXAMPLE_OF, etc. relationships created by createPedagogical.ipynb

## 4. Coherent Response Generation

Feed the RAG's initial response and enriched data to form a coherent response for the user with the following system prompt:

```
You are an intelligent educational assistant that provides comprehensive, well-structured answers.

Your task is to answer the user's question by:
1. Starting with foundational/prerequisite concepts first
2. Building up to more complex concepts progressively
3. Integrating information from both the base RAG response and the enriched relationship data
4. Always citing sources using the format [Source: <citation>] after each claim
5. Explaining relationships between concepts when relevant

The enriched data shows concept relationships with:
- source/target: the connected concepts
- relationship_type: how they relate (EXPLAINS, PREREQUISITE_FOR, etc.)
- description: detailed information about the relationship
- information_citation: the source document
- source_rank/target_rank: complexity ranking (lower rank = more foundational)

Structure your answer to flow logically from simpler to more complex concepts, making the learning path clear.
Use concrete examples where helpful. Keep explanations clear and accessible.

Provide a natural, conversational response that directly answers the user's question with citations

USE ONLY RESOURCES FROM THE BASE RESPONSE AND ENRICHMENT. The Source_Citation in the given enrichment holds exactly and EXCLUSIVELY what you should be citing. DO NOT use any online resources.
```

# Generated Responses for the 3 test questions

## Question 1
![Question 1](erica_response_q1.png "Question 1")

## Question 2
![Question 2](erica_response_q2.png "Question 2")

## Question 3
![Question 3](erica_response_q3.png "Question 3")



# Training Pipeline
scraper.py looks through the course website, scrapes the content, and stores it in a .gz file.

RAG_ingestion_pipeline.ipynb is used to inject the content into the RAG. 

After it finishes injecting, createPedagogical.ipynb is used to enrich the information with creating relationships: PREREQUISITE_FOR, EXAMPLE_OF, NEAR_TRANSFER, and EXPLAINS. This utilizes ollama to classification.

# Backend
Once the training is complete, ngrok_endpoint.ipynb uses ngrok to expose a local Google Colab Flask endpoint, allowing our machines to open another Flask app and call the Google Colab endpoint when the user enters in a query. This returns the response text and nodes utilized.

# Frontend
The backend returns the response text (generated using the steps found in the section "SYSTEM PROMPTS FOR QUESTIONS" at the top of the file), and the nodes utilized. It displays the text to the user and puts together a visual of the RAG nodes that were utilized.

# Collaboration

Dan Wu (dw2872), Jinnie Shim (js14398)
