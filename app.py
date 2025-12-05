"""
NIST NBIS Fingerprint Matching Server
Deploy this on Render.com as a Web Service

Requirements (requirements.txt):
flask==3.0.0
flask-cors==4.0.0
Pillow==10.1.0
numpy==1.24.3
gunicorn==21.2.0

System packages needed (in Render dashboard):
- nbis (NIST Biometric Image Software)
"""

from flask import Flask, request, jsonify
from flask_cors import CORS
import base64
import subprocess
import tempfile
import os
import json
from PIL import Image
import numpy as np
from pathlib import Path

app = Flask(__name__)
CORS(app)

# NBIS executables paths - try multiple locations
import shutil

# Try to find NBIS tools in PATH
MINDTCT = shutil.which("mindtct") or "/opt/nbis/bin/mindtct" or "/usr/local/bin/mindtct" or "/usr/bin/mindtct"
BOZORTH3 = shutil.which("bozorth3") or "/opt/nbis/bin/bozorth3" or "/usr/local/bin/bozorth3" or "/usr/bin/bozorth3"

print(f"🔍 NBIS Tool Locations:")
print(f"   MINDTCT: {MINDTCT}")
print(f"   BOZORTH3: {BOZORTH3}")
print(f"   MINDTCT exists: {os.path.exists(MINDTCT) if MINDTCT else False}")
print(f"   BOZORTH3 exists: {os.path.exists(BOZORTH3) if BOZORTH3 else False}")

class NBISMatcher:
    """NIST NBIS-based fingerprint matcher"""
    
    def __init__(self):
        self.temp_dir = Path(tempfile.gettempdir()) / "nbis_fingerprints"
        self.temp_dir.mkdir(exist_ok=True)
        
    def extract_minutiae(self, base64_image, file_id):
        """
        Extract minutiae from fingerprint image using MINDTCT
        Returns: Path to .xyt minutiae file
        """
        try:
            # Decode base64 to image
            image_data = base64.b64decode(base64_image)
            
            # Create temporary files
            png_file = self.temp_dir / f"{file_id}.png"
            wsq_file = self.temp_dir / f"{file_id}.wsq"
            xyt_file = self.temp_dir / f"{file_id}.xyt"
            
            # Save PNG
            with open(png_file, 'wb') as f:
                f.write(image_data)
            
            # Convert PNG to WSQ (NBIS standard format)
            # WSQ is the FBI standard for fingerprint compression
            img = Image.open(png_file).convert('L')  # Convert to grayscale
            
            # Resize if needed (NBIS works best with 500 DPI images)
            # DigitalPersona 4500 outputs at 500 DPI, so should be fine
            img_array = np.array(img)
            
            # Save as raw grayscale for NBIS
            raw_file = self.temp_dir / f"{file_id}.raw"
            img_array.tofile(raw_file)
            
            # Convert to WSQ using cwsq (NBIS tool)
            subprocess.run([
                "cwsq", "2.25", "wsq",
                str(wsq_file),
                "-raw_in", str(raw_file),
                str(img.width), str(img.height), "8", "500"
            ], check=True, capture_output=True)
            
            # Extract minutiae using MINDTCT
            result = subprocess.run([
                MINDTCT,
                str(wsq_file),
                str(self.temp_dir / file_id)
            ], check=True, capture_output=True, text=True)
            
            # Check if .xyt file was created
            if not xyt_file.exists():
                raise Exception("Minutiae extraction failed - no .xyt file generated")
            
            # Read minutiae count
            with open(xyt_file, 'r') as f:
                lines = f.readlines()
                minutiae_count = len([l for l in lines if not l.startswith('#')])
            
            print(f"✅ Extracted {minutiae_count} minutiae points from {file_id}")
            
            # Cleanup temporary files
            png_file.unlink(missing_ok=True)
            raw_file.unlink(missing_ok=True)
            wsq_file.unlink(missing_ok=True)
            
            return str(xyt_file), minutiae_count
            
        except subprocess.CalledProcessError as e:
            print(f"❌ NBIS Error: {e.stderr}")
            raise Exception(f"Minutiae extraction failed: {e.stderr}")
        except Exception as e:
            print(f"❌ Error: {str(e)}")
            raise
    
    def match_fingerprints(self, xyt_file1, xyt_file2):
        """
        Match two fingerprints using BOZORTH3
        Returns: Match score (higher = better match)
        """
        try:
            # Run BOZORTH3 matcher
            result = subprocess.run([
                BOZORTH3,
                str(xyt_file1),
                str(xyt_file2)
            ], check=True, capture_output=True, text=True)
            
            # Parse match score
            score = int(result.stdout.strip())
            
            print(f"🔍 BOZORTH3 Score: {score}")
            
            return score
            
        except subprocess.CalledProcessError as e:
            print(f"❌ Matching Error: {e.stderr}")
            raise Exception(f"Fingerprint matching failed: {e.stderr}")
        except Exception as e:
            print(f"❌ Error: {str(e)}")
            raise
    
    def cleanup(self, file_id):
        """Remove temporary files"""
        patterns = [".xyt", ".png", ".wsq", ".raw", ".brw", ".dm", ".hcm", ".lcm", ".lfm", ".min", ".qm"]
        for pattern in patterns:
            file = self.temp_dir / f"{file_id}{pattern}"
            file.unlink(missing_ok=True)

matcher = NBISMatcher()

@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint"""
    mindtct_exists = MINDTCT and os.path.exists(MINDTCT)
    bozorth3_exists = BOZORTH3 and os.path.exists(BOZORTH3)
    nbis_available = mindtct_exists and bozorth3_exists
    
    return jsonify({
        'status': 'healthy',
        'service': 'NIST NBIS Fingerprint Matcher',
        'nbis_available': nbis_available,
        'nbis_details': {
            'mindtct_path': MINDTCT,
            'mindtct_exists': mindtct_exists,
            'bozorth3_path': BOZORTH3,
            'bozorth3_exists': bozorth3_exists
        }
    })

@app.route('/extract', methods=['POST'])
def extract_minutiae():
    """
    Extract minutiae from a single fingerprint
    Request: { "image": "base64_string", "id": "unique_id" }
    Response: { "success": true, "minutiae_count": 45, "xyt_data": "..." }
    """
    try:
        data = request.json
        
        if not data or 'image' not in data:
            return jsonify({'success': False, 'error': 'Missing image data'}), 400
        
        image = data['image']
        file_id = data.get('id', 'temp')
        
        # Extract minutiae
        xyt_file, minutiae_count = matcher.extract_minutiae(image, file_id)
        
        # Read .xyt file content
        with open(xyt_file, 'r') as f:
            xyt_data = f.read()
        
        # Cleanup
        matcher.cleanup(file_id)
        
        return jsonify({
            'success': True,
            'minutiae_count': minutiae_count,
            'xyt_data': xyt_data,
            'message': f'Extracted {minutiae_count} minutiae points'
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/compare', methods=['POST'])
def compare_fingerprints():
    """
    Compare two fingerprints
    Request: { "image1": "base64", "image2": "base64" }
    Response: { "success": true, "matched": true, "score": 145, "confidence": 95 }
    """
    try:
        data = request.json
        
        if not data or 'image1' not in data or 'image2' not in data:
            return jsonify({'success': False, 'error': 'Missing image data'}), 400
        
        print("\n🔍 === NBIS FINGERPRINT COMPARISON ===")
        
        # Extract minutiae from both images
        print("📊 Extracting minutiae from image 1...")
        xyt_file1, count1 = matcher.extract_minutiae(data['image1'], 'temp1')
        
        print("📊 Extracting minutiae from image 2...")
        xyt_file2, count2 = matcher.extract_minutiae(data['image2'], 'temp2')
        
        print(f"✅ Image 1: {count1} minutiae points")
        print(f"✅ Image 2: {count2} minutiae points")
        
        # Match fingerprints
        print("🔄 Running BOZORTH3 matching...")
        score = matcher.match_fingerprints(xyt_file1, xyt_file2)
        
        # BOZORTH3 scoring:
        # 0-39: No match
        # 40-99: Possible match (low confidence)
        # 100-199: Good match (medium confidence)
        # 200+: Excellent match (high confidence)
        
        # CRITICAL THRESHOLDS (based on NIST standards)
        MATCH_THRESHOLD = 40  # Minimum for match
        HIGH_CONFIDENCE_THRESHOLD = 100  # High confidence match
        
        matched = score >= MATCH_THRESHOLD
        
        # Calculate confidence percentage
        if score >= HIGH_CONFIDENCE_THRESHOLD:
            confidence = min(100, 80 + (score - HIGH_CONFIDENCE_THRESHOLD) / 5)
        elif score >= MATCH_THRESHOLD:
            confidence = 60 + (score - MATCH_THRESHOLD) / (HIGH_CONFIDENCE_THRESHOLD - MATCH_THRESHOLD) * 20
        else:
            confidence = (score / MATCH_THRESHOLD) * 60
        
        confidence = round(confidence, 1)
        
        result_emoji = "✅ MATCH" if matched else "❌ NO MATCH"
        print(f"🎯 Result: {result_emoji}")
        print(f"📊 BOZORTH3 Score: {score}")
        print(f"🎯 Confidence: {confidence}%")
        print("=====================================\n")
        
        # Cleanup
        matcher.cleanup('temp1')
        matcher.cleanup('temp2')
        
        return jsonify({
            'success': True,
            'matched': matched,
            'score': score,
            'confidence': confidence,
            'threshold': MATCH_THRESHOLD,
            'method': 'NIST_NBIS_BOZORTH3',
            'details': {
                'minutiae_count_1': count1,
                'minutiae_count_2': count2,
                'match_quality': 'excellent' if score >= 200 else 'good' if score >= 100 else 'possible' if score >= 40 else 'no_match'
            }
        })
        
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/batch-compare', methods=['POST'])
def batch_compare():
    """
    Compare one fingerprint against multiple stored fingerprints
    Request: { "query_image": "base64", "database": [{"id": "123", "image": "base64"}, ...] }
    Response: { "success": true, "matches": [...], "best_match": {...} }
    """
    try:
        data = request.json
        
        if not data or 'query_image' not in data or 'database' not in data:
            return jsonify({'success': False, 'error': 'Missing data'}), 400
        
        query_image = data['query_image']
        database = data['database']
        
        print(f"\n🔍 === BATCH COMPARISON: 1 vs {len(database)} ===")
        
        # Extract minutiae from query image
        print("📊 Extracting minutiae from query image...")
        xyt_query, count_query = matcher.extract_minutiae(query_image, 'query')
        print(f"✅ Query: {count_query} minutiae points")
        
        matches = []
        best_match = None
        highest_score = 0
        
        # Compare against each database entry
        for i, db_entry in enumerate(database):
            print(f"🔄 Comparing with database entry {i+1}/{len(database)}...")
            
            # Extract minutiae from database entry
            xyt_db, count_db = matcher.extract_minutiae(db_entry['image'], f'db_{i}')
            
            # Match
            score = matcher.match_fingerprints(xyt_query, f"{matcher.temp_dir}/db_{i}.xyt")
            
            # Calculate confidence
            matched = score >= 40
            if score >= 100:
                confidence = min(100, 80 + (score - 100) / 5)
            elif score >= 40:
                confidence = 60 + (score - 40) / 60 * 20
            else:
                confidence = (score / 40) * 60
            
            match_result = {
                'id': db_entry.get('id'),
                'score': score,
                'confidence': round(confidence, 1),
                'matched': matched,
                'minutiae_count': count_db
            }
            
            matches.append(match_result)
            
            if matched and score > highest_score:
                highest_score = score
                best_match = match_result
            
            # Cleanup database entry
            matcher.cleanup(f'db_{i}')
        
        # Cleanup query
        matcher.cleanup('query')
        
        print(f"✅ Comparison complete")
        print(f"🎯 Best match score: {highest_score}")
        print("=====================================\n")
        
        return jsonify({
            'success': True,
            'matches': matches,
            'best_match': best_match,
            'total_compared': len(database),
            'query_minutiae': count_query
        })
        
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

if __name__ == '__main__':
    # For local development
    app.run(host='0.0.0.0', port=5000, debug=True)