# DiagnoClear

A privacy-first web application that simplifies medical reports using AI.

## Features

- Upload medical reports (PDF or images)
- Client-side OCR processing for privacy
- AI-powered medical term simplification
- No data storage - everything processed in memory
- Responsive design works on all devices
- Download results as PDF
- Share results easily

## Setup

1. Clone or download the project
2. Install dependencies: `pip install -r requirements.txt`
3. Run the app: `python app.py`
4. Open http://localhost:5000 in your browser

## Deployment

This app is designed to run on PythonAnywhere:

1. Upload the files to your PythonAnywhere account
2. Set up a virtual environment and install requirements
3. Configure WSGI file as shown in the technical spec
4. Set environment variables for API keys if using LLM features

## Privacy

- No user data is stored
- All processing happens in memory
- Client-side OCR ensures medical data never leaves the user's device
- No tracking or analytics

## Disclaimer

This is not medical advice. Always consult healthcare professionals for medical concerns.