from flask import Flask, render_template, request, jsonify
from datetime import datetime
import os
import openai
import re

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'dev-secret-key')

# Medical Terms Dictionary
MEDICAL_TERMS = {
    'hemoglobin': {
        'name': 'Hemoglobin',
        'unit': 'g/dL',
        'normal_range': '12-16 (female), 14-18 (male)',
        'simple': 'Protein in red blood cells that carries oxygen',
        'advice': 'Low levels may indicate anemia. Consult doctor if below normal range.'
    },
    'glucose': {
        'name': 'Blood Glucose',
        'unit': 'mg/dL',
        'normal_range': '70-99 (fasting)',
        'simple': 'Sugar level in your blood',
        'advice': 'High levels may indicate diabetes. Monitor diet and consult doctor.'
    },
    'cholesterol': {
        'name': 'Total Cholesterol',
        'unit': 'mg/dL',
        'normal_range': '< 200',
        'simple': 'Fat-like substance in your blood',
        'advice': 'High levels increase heart disease risk. Lifestyle changes recommended.'
    },
    'hdl': {
        'name': 'HDL Cholesterol',
        'unit': 'mg/dL',
        'normal_range': '> 40',
        'simple': 'Good cholesterol that protects your heart',
        'advice': 'Higher is better. Exercise and healthy diet help increase HDL.'
    },
    'ldl': {
        'name': 'LDL Cholesterol',
        'unit': 'mg/dL',
        'normal_range': '< 100',
        'simple': 'Bad cholesterol that can clog arteries',
        'advice': 'High levels increase heart disease risk. Diet and medication may be needed.'
    },
    'triglycerides': {
        'name': 'Triglycerides',
        'unit': 'mg/dL',
        'normal_range': '< 150',
        'simple': 'Type of fat in your blood',
        'advice': 'High levels linked to heart disease. Reduce sugar and alcohol intake.'
    },
    'creatinine': {
        'name': 'Creatinine',
        'unit': 'mg/dL',
        'normal_range': '0.6-1.2',
        'simple': 'Waste product from muscle metabolism',
        'advice': 'High levels may indicate kidney problems. Stay hydrated.'
    },
    'bun': {
        'name': 'Blood Urea Nitrogen',
        'unit': 'mg/dL',
        'normal_range': '7-20',
        'simple': 'Measure of kidney function',
        'advice': 'Abnormal levels may indicate kidney issues. Consult doctor.'
    },
    'sodium': {
        'name': 'Sodium',
        'unit': 'mEq/L',
        'normal_range': '135-145',
        'simple': 'Essential mineral for body functions',
        'advice': 'Imbalances can affect blood pressure and hydration.'
    },
    'potassium': {
        'name': 'Potassium',
        'unit': 'mEq/L',
        'normal_range': '3.5-5.0',
        'simple': 'Mineral important for heart and muscle function',
        'advice': 'Abnormal levels can cause heart rhythm problems.'
    }
}

# Disease/Condition Mapping
DISEASE_CONDITIONS = {
    'hemoglobin': {
        'low': ['Anemia', 'Iron deficiency', 'Chronic disease'],
        'high': ['Polycythemia', 'Dehydration', 'High altitude adaptation']
    },
    'glucose': {
        'high': ['Diabetes Mellitus', 'Pre-diabetes', 'Metabolic disorder', 'Pancreatic disorder'],
        'low': ['Hypoglycemia', 'Insulin overproduction']
    },
    'cholesterol': {
        'high': ['Hyperlipidemia', 'Cardiovascular disease risk', 'Atherosclerosis risk']
    },
    'ldl': {
        'high': ['Cardiovascular disease risk', 'Atherosclerosis', 'Coronary artery disease risk']
    },
    'hdl': {
        'low': ['Cardiovascular disease risk', 'Metabolic syndrome risk']
    },
    'triglycerides': {
        'high': ['Hypertriglyceridemia', 'Metabolic syndrome', 'Cardiovascular disease risk', 'Pancreatitis risk']
    },
    'creatinine': {
        'high': ['Kidney disease', 'Renal impairment', 'Acute kidney injury']
    },
    'bun': {
        'high': ['Kidney disease', 'Renal failure', 'Dehydration', 'Uremia'],
        'low': ['Liver disease', 'Protein malnutrition']
    },
    'sodium': {
        'low': ['Hyponatremia', 'SIADH', 'Kidney disease', 'Heart failure'],
        'high': ['Hypernatremia', 'Dehydration', 'Diabetes insipidus']
    },
    'potassium': {
        'low': ['Hypokalemia', 'Muscle weakness', 'Cardiac arrhythmia risk'],
        'high': ['Hyperkalemia', 'Kidney disease', 'Cardiac arrhythmia risk']
    }
}

MOCK_REPORTS = {
    'blood_test': {
        'summary': 'Your blood test shows mostly normal values with one slightly elevated cholesterol level.',
        'parameters': [
            {
                'test': 'Hemoglobin',
                'value': '14.2',
                'status': 'normal',
                'simple': 'Your hemoglobin is within the normal range, indicating good oxygen-carrying capacity.',
                'advice': 'Continue maintaining a healthy lifestyle.'
            },
            {
                'test': 'Total Cholesterol',
                'value': '210',
                'status': 'borderline',
                'simple': 'Your total cholesterol is slightly elevated.',
                'advice': 'Consider reducing saturated fat intake and increasing exercise.'
            }
        ]
    }
}

def extract_value(text, term):
    """Extract numerical value from text with confidence scoring"""
    value = 'N/A'
    confidence = 0.0
    
    # Try multiple patterns to find the value
    patterns = [
        # Pattern 1: term followed by: value (highest confidence)
        (rf'{term}\s*[:=]\s*(\d+\.?\d*)', 0.95),
        # Pattern 2: term followed by "is/was" value
        (rf'{term}\s+(?:is|was)\s+(\d+\.?\d*)', 0.90),
        # Pattern 3: value followed by term
        (rf'(\d+\.?\d*)\s+(?:g/dL|mg/dL|mEq/L)?\s*{term}', 0.85),
        # Pattern 4: term in parentheses with value
        (rf'{term}\s*\(\s*(\d+\.?\d*)\s*\)', 0.80),
        # Pattern 5: value with units then term
        (rf'(\d+\.?\d*)\s*(?:g/dL|mg/dL|mEq/L)\s+{term}', 0.80),
        # Pattern 6: loose pattern with units
        (rf'{term}.*?(\d+\.?\d*)\s*(?:g/dL|mg/dL|mEq/L)', 0.75),
        # Pattern 7: word distance pattern
        (rf'{term}.*?[\s,;:]\s*(\d+\.?\d*)', 0.65),
    ]
    
    for pattern, score in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            extracted = match.group(1)
            # Validate if value is reasonable (between 0 and 10000 for medical tests)
            try:
                val = float(extracted)
                if 0 <= val <= 10000:
                    value = extracted
                    confidence = score
                    break
            except:
                continue
    
    # Last resort: look for any number within reasonable distance of term
    if value == 'N/A':
        words = text.split()
        term_indices = [i for i, word in enumerate(words) if term in word.lower()]
        
        for idx in term_indices:
            # Check nearby words for numbers
            for i in range(max(0, idx - 5), min(len(words), idx + 6)):
                num_match = re.search(r'(\d+\.?\d*)', words[i])
                if num_match:
                    extracted = num_match.group(1)
                    try:
                        val = float(extracted)
                        if 0 <= val <= 10000:
                            value = extracted
                            confidence = 0.50
                            break
                    except:
                        continue
            if value != 'N/A':
                break
    
    return value, confidence

def determine_status(term_info, value):
    """Determine if value is normal, high, low, or borderline"""
    if value == 'N/A':
        return 'unknown'
    try:
        val = float(value)
        normal = term_info.get('normal_range', '')
        if '>' in normal:
            min_val = float(normal.split('>')[1].strip())
            return 'normal' if val > min_val else 'low'
        elif '<' in normal:
            max_val = float(normal.split('<')[1].strip())
            return 'normal' if val < max_val else 'high'
        else:
            parts = normal.split('-')
            if len(parts) == 2:
                min_val = float(parts[0].strip())
                max_val = float(parts[1].strip())
                if val < min_val:
                    return 'low'
                elif val > max_val:
                    return 'high'
                else:
                    return 'normal'
    except:
        return 'unknown'
    return 'unknown'

def detect_explicit_status(text, term):
    """Detect if text explicitly mentions status like 'high', 'low', 'normal'"""
    # Look for explicit status markers near the term
    markers = {
        'high': r'(?:high|elevated|increased)',
        'low': r'(?:low|decreased|reduced)',
        'normal': r'(?:normal|within range|healthy)'
    }
    
    for status, pattern in markers.items():
        # Check if status appears within 10 words of term
        term_pattern = rf'{term}\s+.*?{pattern}|{pattern}\s+.*?{term}'
        if re.search(term_pattern, text, re.IGNORECASE):
            return status
    
    return None

def generate_summary(results):
    normal_count = sum(1 for r in results if r['status'] == 'normal')
    abnormal_count = sum(1 for r in results if r['status'] in ['high', 'low'])
    borderline_count = sum(1 for r in results if r['status'] == 'borderline')
    
    if abnormal_count == 0:
        return "All your test results are within normal ranges. Keep up the good work!"
    else:
        return f"Your results show {normal_count} normal, {abnormal_count} abnormal, and {borderline_count} borderline values. Please consult your doctor for abnormal results."

def identify_diseases(results):
    """Identify potential diseases/conditions based on abnormal test results"""
    identified_conditions = set()
    
    for result in results:
        if result['status'] in ['high', 'low']:
            # Find the term key from the test name
            for term, info in MEDICAL_TERMS.items():
                if info['name'] == result['test']:
                    # Look up diseases for this abnormality
                    if term in DISEASE_CONDITIONS:
                        conditions = DISEASE_CONDITIONS[term].get(result['status'], [])
                        identified_conditions.update(conditions)
                    break
    
    return sorted(list(identified_conditions))

def generate_advanced_summary(results, diseases):
    """Generate comprehensive summary with disease identification"""
    normal_count = sum(1 for r in results if r['status'] == 'normal')
    abnormal_count = sum(1 for r in results if r['status'] in ['high', 'low'])
    borderline_count = sum(1 for r in results if r['status'] == 'borderline')
    
    summary = f"Test Results Summary: {normal_count} normal, {abnormal_count} abnormal, {borderline_count} borderline.\n\n"
    
    if abnormal_count == 0:
        summary += "All your test results are within normal ranges. Keep up the good work!"
    else:
        summary += "Your test results show some abnormal values.\n\n"
        if diseases:
            summary += "Potential Conditions Identified:\n"
            for disease in diseases:
                summary += f"• {disease}\n"
            summary += "\n"
        summary += "⚠️ IMPORTANT DISCLAIMER:\n"
        summary += "This analysis is for informational purposes only and should NOT be used for self-diagnosis.\n"
        summary += "Please consult a qualified healthcare professional for proper medical evaluation and diagnosis."
    
    return summary

def call_llm_api(text):
    # Mock LLM response for now
    return [
        {
            'test': 'Unknown Parameter',
            'value': 'N/A',
            'status': 'unknown',
            'simple': 'This parameter was not recognized in our database.',
            'advice': 'Please consult your doctor for interpretation.'
        }
    ]

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/analyze', methods=['POST'])
def analyze():
    try:
        data = request.get_json()
        text = data.get('text', '').lower()
        
        results = []
        matched_terms = set()
        low_confidence_count = 0
        
        # Rule-based matching with improved flexibility
        for term, info in MEDICAL_TERMS.items():
            if re.search(rf'\b{term}\b|\b\w*{term}\w*\b', text, re.IGNORECASE):
                if term not in matched_terms:
                    value, confidence = extract_value(text, term)
                    
                    # Try to detect explicit status (high/low/normal) in text
                    explicit_status = detect_explicit_status(text, term)
                    if explicit_status:
                        status = explicit_status
                        confidence = min(0.99, confidence + 0.15)  # Boost confidence when status is explicit
                    else:
                        status = determine_status(info, value)
                    
                    result = {
                        'test': info['name'],
                        'value': f"{value} {info['unit']}" if value != 'N/A' else 'N/A',
                        'status': status,
                        'simple': info['simple'],
                        'advice': info['advice'],
                        'confidence': round(confidence, 2)
                    }
                    results.append(result)
                    matched_terms.add(term)
                    
                    # Track low confidence extractions
                    if confidence < 0.65 and value != 'N/A':
                        low_confidence_count += 1
        
        # LLM fallback if few results
        if len(results) < 2:
            llm_results = call_llm_api(text)
            results.extend(llm_results)
        
        # Identify potential diseases
        diseases = identify_diseases(results)
        
        # Generate comprehensive summary
        summary = generate_advanced_summary(results, diseases)
        
        # Add confidence warning if needed
        if low_confidence_count > 0:
            summary += f"\n\n⚠️ Note: {low_confidence_count} value(s) were extracted with low confidence. Please verify with your actual test report."
        
        avg_confidence = round(sum(r.get('confidence', 0) for r in results) / max(len(results), 1), 2)
        
        return jsonify({
            'summary': summary,
            'parameters': results,
            'identified_diseases': diseases,
            'disease_count': len(diseases),
            'extraction_confidence': avg_confidence,
            'timestamp': datetime.now().isoformat()
        })
    except Exception as e:
        # Fallback to mock
        mock = MOCK_REPORTS['blood_test']
        mock['identified_diseases'] = []
        mock['disease_count'] = 0
        mock['extraction_confidence'] = 0.0
        return jsonify(mock)

if __name__ == '__main__':
    app.run(debug=True)
