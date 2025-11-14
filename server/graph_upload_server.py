import os
import base64
import tempfile
import json
import logging
import requests
from flask import Flask, request, jsonify
from werkzeug.utils import secure_filename
from flask_cors import CORS
import pymongo
# Azure API credentials (replace with your actual keys)
AZURE_API_KEY = os.getenv("AZURE_API_KEY")
AZURE_ENDPOINT = os.getenv("AZURE_ENDPOINT")
AZURE_DEPLOYMENT = os.getenv("AZURE_DEPLOYMENT")

# MongoDB Config
MONGO_URI = os.getenv("MONGO_URI")
DB_NAME = os.getenv("DB_NAME", "pdf_bot")

# Initialize clients
mongo = pymongo.MongoClient(MONGO_URI)
db = mongo[DB_NAME]
graph_coll = db["graph_analysis"]

# Function to send image to Azure OpenAI Vision
def analyze_chart(image_path):
    with open(image_path, "rb") as f:
        base64_image = base64.b64encode(f.read()).decode("utf-8")

    headers = {
        "Content-Type": "application/json",
        "api-key": AZURE_API_KEY,
    }
    payload = {
        "messages": [
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": "Extract data from this chart as JSON. Include: title, axes labels, data points (value, label). Return ONLY valid JSON."
                    },
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/jpeg;base64,{base64_image}"
                        }
                    }
                ]
            }
        ],
        "max_tokens": 4096,
        "temperature": 0,
        "stop":"None"
    }

    response = requests.post(
        f"{AZURE_ENDPOINT}/openai/deployments/{AZURE_DEPLOYMENT}/chat/completions?api-version=2023-12-01-preview",
        headers=headers,
        json=payload
    )
    response.raise_for_status()
    result = response.json()

    # Insert into MongoDB
    graph_coll.insert_one(result)

    return result
