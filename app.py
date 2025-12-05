"""
NIST NBIS Fingerprint Matching Server
Deploy this on Render.com as a Web Service
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
import shutil
import sys

app = Flask(__name__)
CORS(app)

# NBIS executables paths - comprehensive search
def find_nbis_tools():
    """Find NBIS tools in various possible locations"""
    possible_paths = [
        "/opt/nbis/bin",
        "/usr/local/bin",
        "/usr/bin",
        "/opt/bin",
        "/app/nbis/bin"
    ]
    
    mindtct = shutil.which("mindtct")
    bozorth3 = shutil.which("bozorth3")
    cwsq = shutil.which("cwsq")
    
    # If not found in PATH, search in possible directories
    if not mindtct:
        for path in possible_paths:
            test_path = os.path.join(path, "mindtct")
            if os.path.exists(test_path) and os.access(test_path, os.X_OK):
                mindtct = test_path
                break
    
    if not bozorth3:
        for path in possible_paths:
            test_path = os.path.join(path, "bozorth3")
            if os.path.exists(test_path) and os.access(test_path, os.X_OK):
                bozorth3 = test_path
                break
    
    if not cwsq:
        for path in possible_paths:
            test_path = os.path.join(path, "cwsq")
            if os.path.exists(test_path) and os.access(test_path, os.X_OK):
                cwsq = test_path
                break
    
    return mindtct, bozorth3, cwsq

MINDTCT, BOZORTH3, CWSQ = find_nbis_tools()

print("=" * 60)
print("🔍 NBIS Tool Detection Report")
print("=" * 60)
print(f"Python Version: {sys.version}")
print(f"Working Directory: {os.getcwd()}")
print(f"PATH: {os.environ.get('PATH', 'Not set')}")
print("-" * 60)
print(f"MINDTCT Path: {MINDTCT}")
print(f"MINDTCT Exists: {os.path.exists(MINDTCT) if MINDTCT else False}")
print(f"MINDTCT Executable: {os.access(MINDTCT, os.X_OK) if MINDTCT and os.path.exists(MINDTCT) else False}")
print("-" * 60)
print(f"BOZORTH3 Path: {BOZORTH3}")
print(f"BOZORTH3 Exists: {os.path.exists(BOZORTH3) if BOZORTH3 else False}")
print(f"BOZORTH3 Executable: {os.access(BOZORTH3, os.X_OK) if BOZORTH3 and os.path.exists(BOZORTH3) else False}")
print("-" * 60)
print(f"CWSQ Path: {CWSQ}")
print(f"CWSQ Exists: {os.path.exists(CWSQ) if CWSQ else False}")
print(f"CWSQ Executable: {os.access(CWSQ, os.X_OK) if CWSQ and os.path.exists(CWSQ) else False}")
print("=" * 60)

# Test NBIS tools
if MINDTCT and os.path.exists(MINDTCT):
    try:
        result = subprocess.run([MINDTCT, "-version"], capture_output=True, text=True, timeout=5)
        print(f"✅ MINDTCT Test: Success")
        print(f"   Output: {result.stderr[:100] if result.stderr else result.stdout[:100]}")
    except Exception as e:
        print(f"❌ MINDTCT Test Failed: {e}")

if BOZORTH3 and os.path.exists(BOZORTH3):
    try:
        result = subprocess.run([BOZORTH3], capture_output=True, text=True, timeout=5)
        print(f"✅ BOZORTH3 Test: Success")
    except Exception as e:
        print(f"❌ BOZORTH3 Test Failed: {e}")

print("=" * 60)

class NBISMatcher:
    """NIST NBIS-based fingerprint matcher"""
    
    def __init__(self):
        self.temp_dir = Path(tempfile.gettempdir()) / "nbis_fingerprints"
        self.temp_dir.mkdir(exist_ok=True)
        print(f"📁 Temp directory: {self.temp_dir}")
        
        # Verify NBIS tools are available
        if not MINDTCT or not os.path.exists(MINDTCT):
            raise RuntimeError("MINDTCT not found. NBIS not properly installed.")
        if not BOZORTH3 or not os.path.exists(BOZORTH3):
            raise RuntimeError("BOZORTH3 not found. NBIS not properly installed.")
        if not CWSQ or not os.path.exists(CWSQ):
            raise RuntimeError("CWSQ not found. NBIS not properly installed.")
        
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
            img = Image.open(png_file).convert('L')  # Convert to grayscale
            img_array = np.array(img)
            
            # Save as raw grayscale for NBIS
            raw_file = self.temp_dir / f"{file_id}.raw"
            img_array.tofile(raw_file)
            
            # Convert to WSQ using cwsq (NBIS tool)
            cwsq_result = subprocess.run([
                CWSQ, "2.25", "wsq",
                str(wsq_file),
                "-raw_in", str(raw_file),
                str(img.width), str(img.height), "8", "500"
            ], check=True, capture_output=True, text=True, timeout=30)
            
            # Extract minutiae using MINDTCT
            mindtct_result = subprocess.run([
                MINDTCT,
                str(wsq_file),
                str(self.temp_dir / file_id)
            ], check=True, capture_output=True, text=True, timeout=30)
            
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
            ], check=True, capture_output=True, text=True, timeout=30)
            
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

# Initialize matcher (will fail if NBIS not available)
try:
    matcher = NBISMatcher()
    NBIS_AVAILABLE = True
    print("✅ NBISMatcher initialized successfully")
except Exception as e:
    matcher = None
    NBIS_AVAILABLE = False
    print(f"❌ NBISMatcher initialization failed: {e}")

@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint"""
    mindtct_exists = MINDTCT and os.path.exists(MINDTCT)
    bozorth3_exists = BOZORTH3 and os.path.exists(BOZORTH3)
    cwsq_exists = CWSQ and os.path.exists(CWSQ)
    nbis_available = mindtct_exists and bozorth3_exists and cwsq_exists
    
    return jsonify({
        'status': 'healthy',
        'service': 'NIST NBIS Fingerprint Matcher',
        'nbis_available': nbis_available,
        'matcher_initialized': NBIS_AVAILABLE,
        'nbis_details': {
            'mindtct_path': MINDTCT,
            'mindtct_exists': mindtct_exists,
            'mindtct_executable': os.access(MINDTCT, os.X_OK) if MINDTCT and mindtct_exists else False,
            'bozorth3_path': BOZORTH3,
            'bozorth3_exists': bozorth3_exists,
            'bozorth3_executable': os.access(BOZORTH3, os.X_OK) if BOZORTH3 and bozorth3_exists else False,
            'cwsq_path': CWSQ,
            'cwsq_exists': cwsq_exists,
            'cwsq_executable': os.access(CWSQ, os.X_OK) if CWSQ and cwsq_exists else False
        }
    })

@app.route('/extract', methods=['POST'])
def extract_minutiae():
    """Extract minutiae from a single fingerprint"""
    if not NBIS_AVAILABLE:
        return jsonify({'success': False, 'error': 'NBIS tools not available'}), 503
    
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
    """Compare two fingerprints"""
    if not NBIS_AVAILABLE:
        return jsonify({'success': False, 'error': 'NBIS tools not available'}), 503
    
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
        
        # BOZORTH3 scoring thresholds
        MATCH_THRESHOLD = 40
        HIGH_CONFIDENCE_THRESHOLD = 100
        
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
    """Compare one fingerprint against multiple stored fingerprints"""
    if not NBIS_AVAILABLE:
        return jsonify({'success': False, 'error': 'NBIS tools not available'}), 503
    
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