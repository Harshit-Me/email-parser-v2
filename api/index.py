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

    # Check for duplicate products by removing first instance and looking for another
    duplicate_products = []
    for product, start, end in productindex:
        # Create text with this product's first occurrence removed
        modified_text = text[:start] + " " * (end - start + 1) + text[end+1:]
        
        # Try to find the product again in the modified text
        second_match = partial_ratio_alignment(product, modified_text, processor=utils.default_process, score_cutoff=90)
        if second_match is not None:
            duplicate_products.append(product)

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
        
        # Prioritize duplicate product error over quantity mismatch
        if duplicate_products:
            op['flag'] = 1
            duplicate_str = ", ".join(duplicate_products)
            op['reason'] = f"duplicate found: {duplicate_str}"
        # Then check quantity mismatch
        elif len(productindex) != len(qtfound):
            op['flag'] = 1
            op['reason'] = f"mismatch between products ({len(productindex)}) and quantities ({len(qtfound)})"
        else:
            op['flag'] = 0
        
        # Assign quantities to products
        for i in range(len(productindex)):
            if i < len(qtfound):
                op[productindex[i][0]] = qtfound[i]
            else:
                op[productindex[i][0]] = -1
    else:
        op = {'flag': 1, 'reason': 'No products matched in the text'}
    
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
