

# """
# NIST NBIS Fingerprint Matching Server - OPTIMIZED VERSION
# ✨ Features:
# - Parallel batch processing using ThreadPoolExecutor
# - Caching for repeated comparisons
# - Early termination on high-confidence matches
# - Optimized minutiae extraction
# - Better error handling and logging
# """

# from flask import Flask, request, jsonify
# from flask_cors import CORS
# import base64
# import subprocess
# import tempfile
# import os
# from PIL import Image
# import numpy as np
# from pathlib import Path
# import shutil
# import sys
# from concurrent.futures import ThreadPoolExecutor, as_completed
# import time
# import hashlib
# from functools import lru_cache

# app = Flask(__name__)
# CORS(app)

# # Configuration
# MAX_WORKERS = 8  # Number of parallel threads
# MATCH_THRESHOLD = 40
# HIGH_CONFIDENCE_THRESHOLD = 100
# EARLY_TERMINATION_SCORE = 200  # Stop searching if we find a match this good

# # NBIS executables paths
# def find_nbis_tools():
#     """Find NBIS tools in various possible locations"""
#     possible_paths = [
#         "/opt/nbis/bin",
#         "/usr/local/nbis/bin",
#         "/usr/local/bin",
#         "/usr/bin"
#     ]
    
#     mindtct = shutil.which("mindtct")
#     bozorth3 = shutil.which("bozorth3")
#     cwsq = shutil.which("cwsq")
    
#     if not mindtct:
#         for path in possible_paths:
#             test_path = os.path.join(path, "mindtct")
#             if os.path.exists(test_path) and os.access(test_path, os.X_OK):
#                 mindtct = test_path
#                 break
    
#     if not bozorth3:
#         for path in possible_paths:
#             test_path = os.path.join(path, "bozorth3")
#             if os.path.exists(test_path) and os.access(test_path, os.X_OK):
#                 bozorth3 = test_path
#                 break
    
#     if not cwsq:
#         for path in possible_paths:
#             test_path = os.path.join(path, "cwsq")
#             if os.path.exists(test_path) and os.access(test_path, os.X_OK):
#                 cwsq = test_path
#                 break
    
#     return mindtct, bozorth3, cwsq

# MINDTCT, BOZORTH3, CWSQ = find_nbis_tools()

# print("=" * 60)
# print("🚀 OPTIMIZED NBIS Fingerprint Server")
# print("=" * 60)
# print(f"MINDTCT: {MINDTCT} ({'✅' if MINDTCT and os.path.exists(MINDTCT) else '❌'})")
# print(f"BOZORTH3: {BOZORTH3} ({'✅' if BOZORTH3 and os.path.exists(BOZORTH3) else '❌'})")
# print(f"CWSQ: {CWSQ} ({'✅' if CWSQ and os.path.exists(CWSQ) else '❌'})")
# print(f"Max Workers: {MAX_WORKERS}")
# print("=" * 60)

# class OptimizedNBISMatcher:
#     """Optimized NIST NBIS-based fingerprint matcher with parallel processing"""
    
#     def __init__(self):
#         self.temp_dir = Path(tempfile.gettempdir()) / "nbis_fingerprints"
#         self.temp_dir.mkdir(exist_ok=True)
#         print(f"📁 Temp directory: {self.temp_dir}")
        
#         if not MINDTCT or not os.path.exists(MINDTCT):
#             raise RuntimeError("MINDTCT not found")
#         if not BOZORTH3 or not os.path.exists(BOZORTH3):
#             raise RuntimeError("BOZORTH3 not found")
#         if not CWSQ or not os.path.exists(CWSQ):
#             raise RuntimeError("CWSQ not found")
        
#         # Cache for minutiae extraction (stores hash -> xyt_file_path)
#         self.minutiae_cache = {}
        
#     def get_image_hash(self, base64_image):
#         """Generate hash for caching"""
#         return hashlib.md5(base64_image.encode()).hexdigest()
    
#     def extract_minutiae(self, base64_image, file_id, use_cache=True):
#         """
#         Extract minutiae from fingerprint image using MINDTCT
#         Returns: Path to .xyt minutiae file and minutiae count
#         """
#         try:
#             # Check cache first
#             if use_cache:
#                 img_hash = self.get_image_hash(base64_image)
#                 if img_hash in self.minutiae_cache:
#                     cached_xyt, cached_count = self.minutiae_cache[img_hash]
#                     if Path(cached_xyt).exists():
#                         print(f"💾 Cache hit for {file_id}")
#                         return cached_xyt, cached_count
            
#             # Decode base64 to image
#             image_data = base64.b64decode(base64_image)
            
#             # Create temporary files
#             png_file = self.temp_dir / f"{file_id}.png"
#             raw_file = self.temp_dir / f"{file_id}.raw"
#             base_name = self.temp_dir / file_id
#             wsq_file = self.temp_dir / f"{file_id}.wsq"
#             xyt_file = self.temp_dir / f"{file_id}.xyt"
            
#             # Save PNG
#             with open(png_file, 'wb') as f:
#                 f.write(image_data)
            
#             # Convert PNG to grayscale and save as raw
#             img = Image.open(png_file).convert('L')
#             img_array = np.array(img)
#             width, height = img.size
            
#             # Save as raw grayscale
#             img_array.tofile(raw_file)
            
#             # CWSQ compression
#             cwsq_command = [
#                 CWSQ,
#                 "2.25",
#                 "wsq",
#                 str(raw_file),
#                 "-raw_in",
#                 f"{width},{height},8,500"
#             ]
            
#             cwsq_result = subprocess.run(
#                 cwsq_command,
#                 capture_output=True,
#                 text=True,
#                 timeout=30
#             )
            
#             if cwsq_result.returncode != 0:
#                 raise Exception(f"CWSQ failed: {cwsq_result.stderr}")
            
#             if not wsq_file.exists():
#                 alt_wsq = Path(f"{file_id}.wsq")
#                 if alt_wsq.exists():
#                     shutil.move(str(alt_wsq), str(wsq_file))
#                 else:
#                     raise Exception("WSQ file not created")
            
#             # Extract minutiae using MINDTCT
#             mindtct_result = subprocess.run([
#                 MINDTCT,
#                 str(wsq_file),
#                 str(base_name)
#             ], capture_output=True, text=True, timeout=30)
            
#             if mindtct_result.returncode != 0:
#                 raise Exception(f"MINDTCT failed: {mindtct_result.stderr}")
            
#             if not xyt_file.exists():
#                 raise Exception("Minutiae extraction failed - no .xyt file generated")
            
#             # Read minutiae count
#             with open(xyt_file, 'r') as f:
#                 lines = f.readlines()
#                 minutiae_count = len([l for l in lines if not l.startswith('#')])
            
#             # Cache the result
#             if use_cache:
#                 img_hash = self.get_image_hash(base64_image)
#                 self.minutiae_cache[img_hash] = (str(xyt_file), minutiae_count)
            
#             # Cleanup intermediate files
#             png_file.unlink(missing_ok=True)
#             raw_file.unlink(missing_ok=True)
#             wsq_file.unlink(missing_ok=True)
            
#             return str(xyt_file), minutiae_count
            
#         except Exception as e:
#             print(f"❌ Minutiae extraction error for {file_id}: {str(e)}")
#             raise
    
#     def match_fingerprints(self, xyt_file1, xyt_file2):
#         """Match two fingerprints using BOZORTH3"""
#         try:
#             result = subprocess.run([
#                 BOZORTH3,
#                 str(xyt_file1),
#                 str(xyt_file2)
#             ], check=True, capture_output=True, text=True, timeout=30)
            
#             score = int(result.stdout.strip())
#             return score
            
#         except Exception as e:
#             print(f"❌ Matching error: {str(e)}")
#             raise
    
#     def calculate_confidence(self, score):
#         """Calculate confidence percentage from BOZORTH3 score"""
#         if score >= HIGH_CONFIDENCE_THRESHOLD:
#             confidence = min(100, 80 + (score - HIGH_CONFIDENCE_THRESHOLD) / 5)
#         elif score >= MATCH_THRESHOLD:
#             confidence = 60 + (score - MATCH_THRESHOLD) / (HIGH_CONFIDENCE_THRESHOLD - MATCH_THRESHOLD) * 20
#         else:
#             confidence = (score / MATCH_THRESHOLD) * 60
        
#         return round(confidence, 1)
    
#     def cleanup(self, file_id):
#         """Remove temporary files"""
#         patterns = [".xyt", ".png", ".wsq", ".raw", ".brw", ".dm", ".hcm", ".lcm", ".lfm", ".min", ".qm"]
#         for pattern in patterns:
#             file = self.temp_dir / f"{file_id}{pattern}"
#             file.unlink(missing_ok=True)
    
#     def cleanup_cache(self):
#         """Clear minutiae cache"""
#         self.minutiae_cache.clear()

# # Initialize matcher
# try:
#     matcher = OptimizedNBISMatcher()
#     NBIS_AVAILABLE = True
#     print("✅ OptimizedNBISMatcher initialized successfully")
# except Exception as e:
#     matcher = None
#     NBIS_AVAILABLE = False
#     print(f"❌ OptimizedNBISMatcher initialization failed: {e}")

# @app.route('/health', methods=['GET'])
# def health():
#     """Health check endpoint"""
#     mindtct_exists = MINDTCT and os.path.exists(MINDTCT)
#     bozorth3_exists = BOZORTH3 and os.path.exists(BOZORTH3)
#     cwsq_exists = CWSQ and os.path.exists(CWSQ)
#     nbis_available = mindtct_exists and bozorth3_exists and cwsq_exists
    
#     return jsonify({
#         'status': 'healthy',
#         'service': 'Optimized NIST NBIS Fingerprint Matcher',
#         'nbis_available': nbis_available,
#         'matcher_initialized': NBIS_AVAILABLE,
#         'max_workers': MAX_WORKERS,
#         'cache_size': len(matcher.minutiae_cache) if matcher else 0,
#         'nbis_details': {
#             'mindtct_path': MINDTCT,
#             'mindtct_exists': mindtct_exists,
#             'bozorth3_path': BOZORTH3,
#             'bozorth3_exists': bozorth3_exists,
#             'cwsq_path': CWSQ,
#             'cwsq_exists': cwsq_exists
#         }
#     })

# @app.route('/compare', methods=['POST'])
# def compare_fingerprints():
#     """Compare two fingerprints"""
#     if not NBIS_AVAILABLE:
#         return jsonify({'success': False, 'error': 'NBIS tools not available'}), 503
    
#     try:
#         data = request.json
        
#         if not data or 'image1' not in data or 'image2' not in data:
#             return jsonify({'success': False, 'error': 'Missing image data'}), 400
        
#         print("\n🔍 === NBIS FINGERPRINT COMPARISON ===")
#         start_time = time.time()
        
#         # Extract minutiae
#         xyt_file1, count1 = matcher.extract_minutiae(data['image1'], 'temp1')
#         xyt_file2, count2 = matcher.extract_minutiae(data['image2'], 'temp2')
        
#         print(f"✅ Image 1: {count1} minutiae | Image 2: {count2} minutiae")
        
#         # Match
#         score = matcher.match_fingerprints(xyt_file1, xyt_file2)
#         confidence = matcher.calculate_confidence(score)
#         matched = score >= MATCH_THRESHOLD
        
#         elapsed = time.time() - start_time
        
#         print(f"🎯 {'✅ MATCH' if matched else '❌ NO MATCH'} | Score: {score} | Confidence: {confidence}% | Time: {elapsed:.2f}s")
#         print("=" * 60 + "\n")
        
#         # Cleanup
#         matcher.cleanup('temp1')
#         matcher.cleanup('temp2')
        
#         return jsonify({
#             'success': True,
#             'matched': matched,
#             'score': score,
#             'confidence': confidence,
#             'threshold': MATCH_THRESHOLD,
#             'method': 'NIST_NBIS_BOZORTH3',
#             'processing_time': round(elapsed, 2),
#             'details': {
#                 'minutiae_count_1': count1,
#                 'minutiae_count_2': count2,
#                 'match_quality': 'excellent' if score >= 200 else 'good' if score >= 100 else 'possible' if score >= 40 else 'no_match'
#             }
#         })
        
#     except Exception as e:
#         print(f"❌ Error: {str(e)}")
#         return jsonify({'success': False, 'error': str(e)}), 500

# @app.route('/batch-compare', methods=['POST'])
# def batch_compare():
#     """
#     🚀 OPTIMIZED: Compare one fingerprint against multiple stored fingerprints in parallel
#     """
#     if not NBIS_AVAILABLE:
#         return jsonify({'success': False, 'error': 'NBIS tools not available'}), 503
    
#     try:
#         data = request.json
        
#         if not data or 'query_image' not in data or 'database' not in data:
#             return jsonify({'success': False, 'error': 'Missing data'}), 400
        
#         query_image = data['query_image']
#         database = data['database']
        
#         print(f"\n🚀 === PARALLEL BATCH COMPARISON: 1 vs {len(database)} ===")
#         start_time = time.time()
        
#         # ⭐ STEP 1: Extract query minutiae ONCE (not in loop)
#         print("📊 Extracting query minutiae...")
#         extraction_start = time.time()
#         xyt_query, count_query = matcher.extract_minutiae(query_image, 'query', use_cache=True)
#         extraction_time = time.time() - extraction_start
#         print(f"✅ Query: {count_query} minutiae ({extraction_time:.2f}s)")
        
#         # ⭐ STEP 2: Define comparison function for parallel execution
#         def compare_single(db_entry, index):
#             """Compare query against a single database entry"""
#             try:
#                 file_id = f'db_{index}'
                
#                 # Extract minutiae from database entry
#                 xyt_db, count_db = matcher.extract_minutiae(
#                     db_entry['image'], 
#                     file_id, 
#                     use_cache=True
#                 )
                
#                 # Match
#                 score = matcher.match_fingerprints(xyt_query, xyt_db)
#                 confidence = matcher.calculate_confidence(score)
#                 matched = score >= MATCH_THRESHOLD
                
#                 # Cleanup
#                 matcher.cleanup(file_id)
                
#                 result = {
#                     'id': db_entry.get('id'),
#                     'studentId': db_entry.get('studentId'),
#                     'matricNumber': db_entry.get('matricNumber'),
#                     'studentName': db_entry.get('studentName'),
#                     'fingerName': db_entry.get('fingerName'),
#                     'score': score,
#                     'confidence': confidence,
#                     'matched': matched,
#                     'minutiae_count': count_db,
#                     'index': index
#                 }
                
#                 # Log progress
#                 if matched:
#                     print(f"  ✅ Entry {index+1}/{len(database)}: MATCH (score: {score})")
                
#                 return result
                
#             except Exception as e:
#                 print(f"  ❌ Entry {index+1} error: {str(e)}")
#                 return None
        
#         # ⭐ STEP 3: Parallel processing with ThreadPoolExecutor
#         print(f"🔄 Starting parallel comparison with {MAX_WORKERS} workers...")
#         comparison_start = time.time()
        
#         matches = []
#         best_match = None
#         highest_score = 0
#         completed_count = 0
        
#         with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
#             # Submit all tasks
#             future_to_index = {
#                 executor.submit(compare_single, db_entry, i): i 
#                 for i, db_entry in enumerate(database)
#             }
            
#             # ⭐ EARLY TERMINATION: Stop if we find excellent match
#             early_termination = False
            
#             # Process completed tasks as they finish
#             for future in as_completed(future_to_index):
#                 result = future.result()
#                 completed_count += 1
                
#                 if result:
#                     matches.append(result)
                    
#                     # Track best match
#                     if result['matched'] and result['score'] > highest_score:
#                         highest_score = result['score']
#                         best_match = result
                        
#                         # Early termination on excellent match
#                         if result['score'] >= EARLY_TERMINATION_SCORE:
#                             print(f"🎯 EXCELLENT MATCH FOUND (score: {result['score']}) - Early termination")
#                             early_termination = True
#                             # Cancel remaining tasks
#                             for f in future_to_index:
#                                 f.cancel()
#                             break
                
#                 # Progress update every 20%
#                 if completed_count % max(1, len(database) // 5) == 0:
#                     progress = (completed_count / len(database)) * 100
#                     print(f"  📊 Progress: {completed_count}/{len(database)} ({progress:.0f}%)")
        
#         comparison_time = time.time() - comparison_start
#         total_time = time.time() - start_time
        
#         # Cleanup
#         matcher.cleanup('query')
        
#         # Sort matches by score
#         matches.sort(key=lambda x: x['score'], reverse=True)
        
#         print(f"✅ Comparison complete")
#         print(f"🎯 Best match score: {highest_score}")
#         print(f"⚡ Total time: {total_time:.2f}s")
#         print(f"   - Query extraction: {extraction_time:.2f}s")
#         print(f"   - Parallel comparison: {comparison_time:.2f}s")
#         print(f"   - Throughput: {len(database)/comparison_time:.1f} comparisons/sec")
#         if early_termination:
#             print(f"🚀 Early termination saved {len(database) - completed_count} comparisons")
#         print("=" * 60 + "\n")
        
#         return jsonify({
#             'success': True,
#             'matches': matches[:10],  # Return top 10 matches
#             'best_match': best_match,
#             'total_compared': completed_count,
#             'query_minutiae': count_query,
#             'early_termination': early_termination,
#             'performance': {
#                 'total_time': round(total_time, 2),
#                 'extraction_time': round(extraction_time, 2),
#                 'comparison_time': round(comparison_time, 2),
#                 'throughput': round(len(database)/comparison_time, 1)
#             }
#         })
        
#     except Exception as e:
#         print(f"❌ Error: {str(e)}")
#         return jsonify({'success': False, 'error': str(e)}), 500

# @app.route('/clear-cache', methods=['POST'])
# def clear_cache():
#     """Clear minutiae cache"""
#     if not NBIS_AVAILABLE:
#         return jsonify({'success': False, 'error': 'NBIS tools not available'}), 503
    
#     cache_size = len(matcher.minutiae_cache)
#     matcher.cleanup_cache()
    
#     return jsonify({
#         'success': True,
#         'message': f'Cleared {cache_size} cached entries'
#     })

# if __name__ == '__main__':
#     # Use production-ready server
#     port = int(os.environ.get('PORT', 5000))
#     app.run(host='0.0.0.0', port=port, debug=False, threaded=True)
# #     except Exception as e:
# #         print(f"❌ Error: {str(e)}")
# #         return jsonify({'success': False, 'error': str(e)}), 500

# # if __name__ == '__main__':
# #     app.run(host='0.0.0.0', port=5000, debug=True)



from flask import Flask, request, jsonify
from flask_cors import CORS
import os
import base64
import time
import subprocess
import uuid  # ⭐ ADD THIS
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

app = Flask(__name__)
CORS(app)

# Configuration - ⭐ FIXED PATH to match Dockerfile
NBIS_PATH = Path("/usr/local/nbis/bin")  # Changed from /opt/NBIS/Main/bin
TEMP_DIR = Path("/tmp/nbis_temp")
TEMP_DIR.mkdir(exist_ok=True)

# ⭐ DUAL THRESHOLDS
AUTHENTICATION_THRESHOLD = 40      # For login/attendance (same finger)
DUPLICATE_DETECTION_THRESHOLD = 80  # For enrollment (different fingers)
HIGH_CONFIDENCE_THRESHOLD = 100
MAX_WORKERS = 8

# Check NBIS availability
NBIS_AVAILABLE = (NBIS_PATH / "mindtct").exists() and (NBIS_PATH / "bozorth3").exists()

# ⭐ IMPROVED CACHING with UUID support
minutiae_cache = {}

def generate_cache_key():
    """Generate unique cache key for each image"""
    return f"img_{uuid.uuid4().hex[:8]}"

class NBISMatcher:
    def __init__(self):
        self.mindtct = str(NBIS_PATH / "mindtct")
        self.bozorth3 = str(NBIS_PATH / "bozorth3")
    
    def cleanup(self, identifier):
        """Clean up temporary files and cache"""
        if identifier in minutiae_cache:
            del minutiae_cache[identifier]
            print(f"🧹 Removed cache for {identifier}")
        
        for ext in ['.png', '.xyt', '.min', '.brw', '.dm']:
            file_path = TEMP_DIR / f"{identifier}{ext}"
            if file_path.exists():
                file_path.unlink()
    
    def extract_minutiae(self, base64_image, identifier):
        """Extract minutiae from base64 PNG image with caching"""
        # ⭐ Check cache first
        if identifier in minutiae_cache:
            cached = minutiae_cache[identifier]
            print(f"💾 Cache hit for {identifier}")
            return cached['xyt_file'], cached['count']
        
        # Decode base64 to PNG
        try:
            if ',' in base64_image:
                base64_image = base64_image.split(',')[1]
            image_data = base64.b64decode(base64_image)
        except Exception as e:
            raise ValueError(f"Invalid base64 image: {str(e)}")
        
        # Save PNG
        png_path = TEMP_DIR / f"{identifier}.png"
        with open(png_path, 'wb') as f:
            f.write(image_data)
        
        # Run MINDTCT
        xyt_path = TEMP_DIR / f"{identifier}.xyt"
        try:
            result = subprocess.run(
                [self.mindtct, str(png_path), str(TEMP_DIR / identifier)],
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if result.returncode != 0 or not xyt_path.exists():
                raise RuntimeError(f"MINDTCT failed: {result.stderr}")
            
            # Count minutiae
            with open(xyt_path, 'r') as f:
                count = sum(1 for line in f if line.strip() and not line.startswith('#'))
            
            # ⭐ Cache the results
            minutiae_cache[identifier] = {
                'xyt_file': str(xyt_path),
                'count': count,
                'timestamp': time.time()
            }
            
            return str(xyt_path), count
            
        except subprocess.TimeoutExpired:
            raise RuntimeError("Minutiae extraction timeout")
    
    def match_fingerprints(self, xyt_file1, xyt_file2):
        """Match two fingerprint minutiae files"""
        try:
            result = subprocess.run(
                [self.bozorth3, xyt_file1, xyt_file2],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if result.returncode != 0:
                return 0
            
            score_line = result.stdout.strip().split('\n')[-1]
            return int(score_line.strip())
            
        except (subprocess.TimeoutExpired, ValueError):
            return 0
    
    def calculate_confidence(self, score):
        """Calculate confidence percentage"""
        if score >= 200:
            return 100
        elif score >= 100:
            return 90
        elif score >= 80:
            return 75
        elif score >= 40:
            return 60
        elif score >= 20:
            return 30
        else:
            return score * 1.5

matcher = NBISMatcher()

@app.route('/compare', methods=['POST'])
def compare_fingerprints():
    """
    Compare two fingerprints - supports dual thresholds
    ⭐ NOW USES UUID-BASED CACHE KEYS to prevent conflicts
    """
    if not NBIS_AVAILABLE:
        return jsonify({'success': False, 'error': 'NBIS tools not available'}), 503
    
    try:
        data = request.json
        
        if not data or 'image1' not in data or 'image2' not in data:
            return jsonify({'success': False, 'error': 'Missing image data'}), 400
        
        # ⭐ Generate unique identifiers for this comparison
        id1 = generate_cache_key()
        id2 = generate_cache_key()
        
        # ⭐ Determine threshold based on use case
        is_duplicate_check = data.get('is_duplicate_check', False)
        threshold = DUPLICATE_DETECTION_THRESHOLD if is_duplicate_check else AUTHENTICATION_THRESHOLD
        mode = 'DUPLICATE DETECTION' if is_duplicate_check else 'AUTHENTICATION'
        
        print(f"\n🔍 === NBIS {mode} COMPARISON ===")
        print(f"🔑 Using unique IDs: {id1}, {id2}")
        start_time = time.time()
        
        # Extract minutiae
        xyt_file1, count1 = matcher.extract_minutiae(data['image1'], id1)
        xyt_file2, count2 = matcher.extract_minutiae(data['image2'], id2)
        
        print(f"✅ Image 1: {count1} minutiae | Image 2: {count2} minutiae")
        
        # Match
        score = matcher.match_fingerprints(xyt_file1, xyt_file2)
        confidence = matcher.calculate_confidence(score)
        matched = score >= threshold
        
        elapsed = time.time() - start_time
        
        print(f"🎯 {'✅ MATCH' if matched else '❌ NO MATCH'} | Score: {score} | Confidence: {confidence}% | Time: {elapsed:.2f}s")
        print(f"📊 Threshold: {threshold} ({mode})")
        print("=" * 60 + "\n")
        
        # ⭐ Cleanup immediately after comparison
        matcher.cleanup(id1)
        matcher.cleanup(id2)
        
        return jsonify({
            'success': True,
            'matched': matched,
            'score': score,
            'confidence': confidence,
            'threshold': threshold,
            'method': f'NIST_NBIS_BOZORTH3_{mode}',
            'processing_time': round(elapsed, 2),
            'details': {
                'minutiae_count_1': count1,
                'minutiae_count_2': count2,
                'match_quality': 'excellent' if score >= 200 else 'good' if score >= 100 else 'possible' if score >= threshold else 'no_match'
            }
        })
        
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/batch-compare', methods=['POST'])
def batch_compare():
    """
    Compare one query fingerprint against multiple database fingerprints in parallel
    ⭐ NOW USES UUID-BASED CACHE KEYS
    """
    if not NBIS_AVAILABLE:
        return jsonify({'success': False, 'error': 'NBIS tools not available'}), 503
    
    try:
        data = request.json
        
        if not data or 'queryImage' not in data or 'database' not in data:
            return jsonify({'success': False, 'error': 'Missing required data'}), 400
        
        # ⭐ Determine threshold
        is_duplicate_check = data.get('is_duplicate_check', True)
        threshold = DUPLICATE_DETECTION_THRESHOLD if is_duplicate_check else AUTHENTICATION_THRESHOLD
        mode = 'DUPLICATE DETECTION' if is_duplicate_check else 'AUTHENTICATION'
        
        print(f"\n🔍 === NBIS BATCH {mode} ===")
        print(f"Database size: {len(data['database'])} fingerprints")
        print(f"Threshold: {threshold}")
        
        start_time = time.time()
        
        # ⭐ Extract query minutiae with unique ID
        query_id = generate_cache_key()
        query_xyt, query_count = matcher.extract_minutiae(data['queryImage'], query_id)
        print(f"✅ Query minutiae: {query_count}")
        
        # Parallel comparison
        def compare_one(db_entry):
            try:
                # ⭐ Generate unique ID for each database entry
                db_id = generate_cache_key()
                db_xyt, db_count = matcher.extract_minutiae(db_entry['imageData'], db_id)
                score = matcher.match_fingerprints(query_xyt, db_xyt)
                
                # ⭐ Cleanup database fingerprint immediately
                matcher.cleanup(db_id)
                
                if score >= 200:  # Early termination
                    print(f"⚡ Early match: {db_entry.get('studentName', 'Unknown')} (Score: {score})")
                
                return {
                    'score': score,
                    'entry': db_entry,
                    'confidence': matcher.calculate_confidence(score)
                }
            except Exception as e:
                print(f"⚠️ Comparison error: {str(e)}")
                return {'score': 0, 'entry': db_entry, 'confidence': 0}
        
        # Execute comparisons in parallel
        results = []
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            future_to_entry = {executor.submit(compare_one, entry): entry for entry in data['database']}
            
            for future in as_completed(future_to_entry):
                result = future.result()
                results.append(result)
                
                # Early termination if excellent match found
                if result['score'] >= 200:
                    print("⚡ Excellent match found, cancelling remaining tasks")
                    for f in future_to_entry:
                        f.cancel()
                    break
        
        # ⭐ Cleanup query fingerprint
        matcher.cleanup(query_id)
        
        # Find best match
        best_match = max(results, key=lambda x: x['score'])
        matched = best_match['score'] >= threshold
        
        elapsed = time.time() - start_time
        
        print(f"🎯 {'✅ MATCH' if matched else '❌ NO MATCH'} | Best score: {best_match['score']} | Time: {elapsed:.2f}s")
        print("=" * 60 + "\n")
        
        response = {
            'success': True,
            'matched': matched,
            'threshold': threshold,
            'mode': mode,
            'processing_time': round(elapsed, 2)
        }
        
        if matched:
            response['bestMatch'] = {
                'score': best_match['score'],
                'confidence': best_match['confidence'],
                **best_match['entry']
            }
        
        return jsonify(response)
        
    except Exception as e:
        print(f"❌ Batch error: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'nbis_available': NBIS_AVAILABLE,
        'nbis_path': str(NBIS_PATH),  # ⭐ Added for debugging
        'cache_size': len(minutiae_cache)
    })

@app.route('/clear-cache', methods=['POST'])
def clear_cache():
    """Clear minutiae cache"""
    global minutiae_cache
    cache_size = len(minutiae_cache)
    minutiae_cache.clear()
    print(f"🧹 Cleared {cache_size} cached items")
    return jsonify({'success': True, 'cleared': cache_size})

if __name__ == '__main__':
    print("\n" + "=" * 60)
    print("🚀 NBIS FINGERPRINT SERVER")
    print("=" * 60)
    print(f"✅ NBIS Available: {NBIS_AVAILABLE}")
    print(f"📁 NBIS Path: {NBIS_PATH}")
    print(f"🎚️  Authentication Threshold: {AUTHENTICATION_THRESHOLD}")
    print(f"🎚️  Duplicate Detection Threshold: {DUPLICATE_DETECTION_THRESHOLD}")
    print(f"⚡ Worker Threads: {MAX_WORKERS}")
    print("=" * 60 + "\n")
    
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)), debug=False)
