# api/index.py

from flask import Flask, request, jsonify
import json
import re
from rapidfuzz import fuzz, utils
from rapidfuzz.fuzz import partial_ratio_alignment
from collections import Counter

app = Flask(__name__)

def parse_products_text(products, text):
    productindex = []
    
    # Sort products by length (longest first) to avoid shorter names matching within longer ones
    sorted_products = sorted(products, key=len, reverse=True)
    
    for product in sorted_products:
        alignment = partial_ratio_alignment(product, text, processor=utils.default_process, score_cutoff=95)  # Increased threshold
        if alignment is not None:
            dest_start = alignment.dest_start
            dest_end = alignment.dest_end
            productindex.append((product, dest_start, dest_end))
    
    # Check for actual duplicates using exact product names
    product_names = [p[0] for p in productindex]
    product_counts = Counter(product_names)
    duplicate_products = [p for p, count in product_counts.items() if count > 1]
    
    def remove_substrings(text, removals):
        removals_sorted = sorted(removals, key=lambda x: x[1], reverse=True)
        for substring, start, end in removals_sorted:
            text = text[:start] + text[end+1:]
        return text

    if productindex:
        # Create a working copy of text for quantity extraction
        working_text = text[:]
        
        # Extract all quantities with their positions
        quantity_pattern = r'(\d{1,6} units|\d{1,6} unit|\d{1,6} pack|\d{1,6} meter|\d{1,6} kilogram|\d{1,6} l|\d{1,6} liter|\d{1,6} g|\d{1,6} m|\d{1,6} kg|\d{1,6} ml)'
        quantity_matches = [(m.group(), m.start(), m.end()) for m in re.finditer(quantity_pattern, working_text)]
        
        # Sort products by position in text
        productindex.sort(key=lambda x: x[1])
        
        op = {}
        
        # Detect which products are actually in the text
        products_in_text = set(p[0] for p in productindex)
        
        # Map each product to its nearest quantity
        for product, prod_start, prod_end in productindex:
            # Find the closest quantity that comes after this product
            best_quantity = None
            min_distance = float('inf')
            
            for qty, qty_start, qty_end in quantity_matches:
                if qty_start > prod_start and qty_start - prod_end < min_distance:
                    min_distance = qty_start - prod_end
                    best_quantity = qty
            
            if best_quantity:
                op[product] = best_quantity
            else:
                op[product] = "unknown quantity"
        
        # For products not found in text, set to -1 or suitable placeholder
        for product in products:
            if product not in products_in_text:
                op[product] = -1
        
        # Set flag based on duplicates or quantity mismatch
        if duplicate_products:
            op['flag'] = 1
            duplicate_str = ", ".join(duplicate_products)
            op['reason'] = f"duplicate found: {duplicate_str}"
        elif len([p for p in productindex if op.get(p[0]) != "unknown quantity"]) != len(quantity_matches):
            op['flag'] = 1
            op['reason'] = f"mismatch between products and quantities"
        else:
            op['flag'] = 0
    else:
        op = {'flag': 1, 'reason': 'No products matched in the text'}
        # Set all products to -1
        for product in products:
            op[product] = -1
    
    return op

@app.route('/api/parser', methods=['POST'])
def parse():
    try:
        data = request.json
        # Extract products and text from request body
        products = data.get('products', [])
        text = data.get('text', '')
        
        if not products or not text:
            return jsonify({"error": "Missing products or text", "flag": 1, "reason": "Missing required input data"}), 400
        
        # Process the data
        result = parse_products_text(products, text)
        return jsonify(result)
    
    except Exception as e:
        return jsonify({"error": str(e), "flag": 1, "reason": "Server error occurred during processing"}), 500

@app.route('/', methods=['GET'])
def home():
    return jsonify({"message": "Parser API is running. Send POST requests to /api/parser"})
