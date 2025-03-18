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
    for product in products:
        alignment = partial_ratio_alignment(product, text, processor=utils.default_process, score_cutoff=90)
        if alignment is not None:
            dest_start = alignment.dest_start
            dest_end = alignment.dest_end
            productindex.append((product, dest_start, dest_end))

    def remove_substrings(text, removals):
        removals_sorted = sorted(removals, key=lambda x: x[1], reverse=True)
        for substring, start, end in removals_sorted:
            text = text[:start] + text[end+1:]
        return text

    if productindex:
        text = remove_substrings(text, productindex)
        quantpattern = r'\d{1,6} units|\d{1,6} pack|\d{1,6} meter|\d{1,6} kilogram|\d{1,6} l|\d{1,6} liter|\d{1,6} g|\d{1,6} m|\d{1,6} kg|\d{1,6} ml'
        qtfound = re.findall(quantpattern, text)
        productindex.sort(key=lambda x: x[1])
        
        op = {}
        
        # Check for duplicate products
        product_names = [p[0] for p in productindex]
        product_counts = Counter(product_names)
        duplicate_products = [p for p, count in product_counts.items() if count > 1]
        
        if duplicate_products:
            # Duplicate products found
            op['flag'] = 1
            duplicate_str = ", ".join(duplicate_products)
            op['reason'] = f"duplicate found: {duplicate_str}"
            
            # Assign quantities to products as far as possible
            for i in range(len(productindex)):
                if i < len(qtfound):
                    op[productindex[i][0]] = qtfound[i]
                else:
                    op[productindex[i][0]] = "unknown quantity"
        
        # Check if the number of products discovered matches the number of quantities extracted
        elif len(productindex) != len(qtfound):
            # Mismatch detected - set flag to 1
            op['flag'] = 1
            op['reason'] = f"mismatch between products ({len(productindex)}) and quantities ({len(qtfound)})"
            
            # Still assign quantities to products as far as possible
            for i in range(len(productindex)):
                if i < len(qtfound):
                    op[productindex[i][0]] = qtfound[i]
                else:
                    op[productindex[i][0]] = "unknown quantity" # For products without matching quantities
        else:
            # No mismatch - assign quantities and set flag to 0
            for i in range(len(productindex)):
                op[productindex[i][0]] = qtfound[i]
            op['flag'] = 0
    else:
        op = {'flag': 1, 'error': 'No products matched in the text', 'reason': 'No products matched in the text'}
    
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
